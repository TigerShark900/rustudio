"""Decrypt one direction of a stripped RbxTransport QUIC flow and reassemble it.

Keys come either from a traffic secret in an NSS keylog (`--secret KEYLOG
LABEL`, e.g. the client secret quic_keys.py recovers) or from installed key
material (`--km KMFILE DIR`, the `DIR key iv hp` lines quic_rxkm.py writes;
this is how the server->client direction is read, its secret is not resident).

Packet numbers are reconstructed per RFC 9000 A.3. All QUIC frames are parsed;
STREAM data is reassembled per stream id and DATAGRAM payloads are kept in
order. With OUTDIR, writes `OUTDIR/stream_<id>.bin` per stream and
`OUTDIR/datagrams.bin` (each payload as u32-LE length + bytes, prefixed by the
u32-LE packet number) — decrypted place data, so OUTDIR belongs under
~/.cache/rustudio-dev/tc, never in the repo. Stdout carries structure only.

usage: python3 -I quic_decode.py STRIPPED.pcap SRC_IP DCID_LEN (--secret KEYLOG LABEL CIPHER | --km KMFILE DIR)
                                 [OUTDIR]
  SRC_IP: the source IP of the direction to decrypt
"""
import os
import struct
import sys
from collections import Counter, defaultdict

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand

pcap, src_ip, cidl = sys.argv[1], sys.argv[2], int(sys.argv[3])
mode = sys.argv[4]
cipher = 0x1302
if mode == '--secret':
    keylog, label, cipher = sys.argv[5], sys.argv[6], int(sys.argv[7], 16)
    rest = sys.argv[8:]
    H = hashes.SHA384 if cipher == 0x1302 else hashes.SHA256
    secret = None
    for ln in open(keylog):
        p = ln.split()
        if len(p) == 3 and p[0] == label:
            secret = bytes.fromhex(p[2])
    if not secret:
        sys.exit('secret not in keylog')

    def el(lbl, n):
        full = b'tls13 ' + lbl
        info = struct.pack('>H', n) + bytes([len(full)]) + full + b'\x00'
        return HKDFExpand(algorithm=H(), length=n, info=info).derive(secret)
    key, iv, hp = el(b'quic key', 32), el(b'quic iv', 12), el(b'quic hp', 32)
elif mode == '--km':
    kmfile, want = sys.argv[5], sys.argv[6]
    rest = sys.argv[7:]
    key = None
    for ln in open(kmfile):
        p = ln.split()
        if len(p) == 4 and p[0] == want:
            key, iv, hp = (bytes.fromhex(x) for x in p[1:])
    if key is None:
        sys.exit('direction not in key file')
else:
    sys.exit(__doc__)
outdir = rest[0] if rest else None

aead = ChaCha20Poly1305(key) if cipher == 0x1303 else AESGCM(key)
ivn = int.from_bytes(iv, 'big')


def mask(sample):
    if cipher == 0x1303:
        return Cipher(algorithms.ChaCha20(hp, sample[:16]), None).encryptor().update(b'\0' * 5)
    return Cipher(algorithms.AES(hp), modes.ECB()).encryptor().update(sample[:16])[:5]


def rvar(b, o):
    ln = 1 << (b[o] >> 6)
    v = b[o] & 0x3f
    for i in range(1, ln):
        v = (v << 8) | b[o + i]
    return v, o + ln


largest = -1


def decode_pn(trunc, nbits):
    exp = largest + 1
    win = 1 << nbits
    hwin, msk = win // 2, win - 1
    cand = (exp & ~msk) | trunc
    if cand <= exp - hwin and cand < (1 << 62) - win:
        return cand + win
    if cand > exp + hwin and cand >= win:
        return cand - win
    return cand


def decrypt(pkt):
    global largest
    po = 1 + cidl
    if len(pkt) < po + 4 + 16:
        return None, None, None
    m = mask(pkt[po + 4: po + 20])
    first = pkt[0] ^ (m[0] & 0x1f)
    pnl = (first & 3) + 1
    pnb = bytes(x ^ y for x, y in zip(pkt[po:po + pnl], m[1:1 + pnl]))
    t = int.from_bytes(pnb, 'big')
    aad = bytes([first]) + pkt[1:po] + pnb
    # RFC 9000 A.3 reconstruction. Before the first success the high bits are
    # unknown: RbxTransport's 1-RTT packet numbers don't start at 0 (one join:
    # server 0x90f9, client 0x70fc2d45 [verified: capture]), so the first
    # packet tries every high part.
    if largest < 0:
        cands = [t + (k << (8 * pnl)) for k in range(1 << (24 - 8 * pnl) if pnl < 3 else 1)]
    else:
        pn0 = decode_pn(t, 8 * pnl)
        cands = [pn0]
    for pn in cands:
        try:
            pt = aead.decrypt((ivn ^ pn).to_bytes(12, 'big'), pkt[po + pnl:], aad)
        except Exception:
            continue
        largest = max(largest, pn)
        return pt, pn, (first >> 2) & 1
    return None, cands[0], (first >> 2) & 1


def frames(pt):
    """yield (type_name, info) for every frame; raises on an unknown type."""
    o = 0
    while o < len(pt):
        t, o = rvar(pt, o)
        if t == 0x00:
            continue
        if t == 0x01:
            yield 'PING', None
        elif t in (0x02, 0x03):
            _, o = rvar(pt, o)
            _, o = rvar(pt, o)
            rc, o = rvar(pt, o)
            _, o = rvar(pt, o)
            for _ in range(rc):
                _, o = rvar(pt, o)
                _, o = rvar(pt, o)
            if t == 0x03:
                for _ in range(3):
                    _, o = rvar(pt, o)
            yield 'ACK', None
        elif t == 0x04:
            sid, o = rvar(pt, o)
            _, o = rvar(pt, o)
            _, o = rvar(pt, o)
            yield 'RESET_STREAM', sid
        elif t == 0x05:
            sid, o = rvar(pt, o)
            _, o = rvar(pt, o)
            yield 'STOP_SENDING', sid
        elif t == 0x06:
            _, o = rvar(pt, o)
            n, o = rvar(pt, o)
            o += n
            yield 'CRYPTO', None
        elif t == 0x07:
            n, o = rvar(pt, o)
            o += n
            yield 'NEW_TOKEN', None
        elif 0x08 <= t <= 0x0f:
            sid, o = rvar(pt, o)
            doff = 0
            if t & 4:
                doff, o = rvar(pt, o)
            if t & 2:
                n, o = rvar(pt, o)
            else:
                n = len(pt) - o
            yield 'STREAM', (sid, doff, pt[o:o + n], bool(t & 1))
            o += n
        elif t in (0x10, 0x12, 0x13, 0x14, 0x16, 0x17):
            _, o = rvar(pt, o)
            yield {0x10: 'MAX_DATA', 0x12: 'MAX_STREAMS', 0x13: 'MAX_STREAMS', 0x14: 'DATA_BLOCKED',
                   0x16: 'STREAMS_BLOCKED', 0x17: 'STREAMS_BLOCKED'}[t], None
        elif t in (0x11, 0x15):
            _, o = rvar(pt, o)
            _, o = rvar(pt, o)
            yield 'MAX_STREAM_DATA' if t == 0x11 else 'STREAM_DATA_BLOCKED', None
        elif t == 0x18:
            _, o = rvar(pt, o)
            _, o = rvar(pt, o)
            n = pt[o]
            o += 1 + n + 16
            yield 'NEW_CONNECTION_ID', None
        elif t == 0x19:
            _, o = rvar(pt, o)
            yield 'RETIRE_CONNECTION_ID', None
        elif t in (0x1a, 0x1b):
            o += 8
            yield 'PATH_CHALLENGE' if t == 0x1a else 'PATH_RESPONSE', None
        elif t in (0x1c, 0x1d):
            _, o = rvar(pt, o)
            if t == 0x1c:
                _, o = rvar(pt, o)
            n, o = rvar(pt, o)
            o += n
            yield 'CONNECTION_CLOSE', None
        elif t == 0x1e:
            yield 'HANDSHAKE_DONE', None
        elif t in (0x30, 0x31):
            if t & 1:
                n, o = rvar(pt, o)
            else:
                n = len(pt) - o
            yield 'DATAGRAM', pt[o:o + n]
            o += n
        else:
            raise ValueError(f'unknown frame type {t:#x}')


data = open(pcap, 'rb').read()
sip = bytes(int(x) for x in src_ip.split('.'))
off = 24
hist = Counter()
fails = Counter()
segs = defaultdict(dict)  # sid -> {offset: bytes}
fin = {}
dgrams = []
n_ok = n_pk = 0
while off + 16 <= len(data):
    incl = struct.unpack_from('<I', data, off + 8)[0]
    ip = data[off + 16: off + 16 + incl]
    off += 16 + incl
    q = ip[28:]
    if not q or q[0] & 0x80 or not q[0] & 0x40 or ip[12:16] != sip:
        continue
    n_pk += 1
    pt, pn, kp = decrypt(q)
    if pt is None:
        fails[f'kp{kp}'] += 1
        continue
    n_ok += 1
    try:
        for name, info in frames(pt):
            hist[name] += 1
            if name == 'STREAM':
                sid, doff, chunk, f = info
                if chunk:
                    segs[sid][doff] = chunk
                if f:
                    fin[sid] = doff + len(chunk)
            elif name == 'DATAGRAM':
                dgrams.append((pn, info))
    except ValueError as e:
        hist[str(e)] += 1

print(f'direction src={src_ip}: {n_ok}/{n_pk} 1-RTT packets decrypted; failures by key phase: {dict(fails)}')
print('frame types:', dict(hist))
streams = {}
holes = 0
for sid, parts in segs.items():
    buf = bytearray()
    for o in sorted(parts):
        c = parts[o]
        if o > len(buf):
            holes += 1
            buf.extend(b'\0' * (o - len(buf)))
        buf[o:o + len(c)] = c
    streams[sid] = bytes(buf)
kinds = Counter(('uni' if sid & 2 else 'bidi') + ('-srv' if sid & 1 else '-cli') for sid in streams)
print(f'streams: {len(streams)} ({dict(kinds)}), {sum(map(len, streams.values()))} bytes, holes {holes}, fin {len(fin)}')
big = sorted(streams, key=lambda s: -len(streams[s]))[:6]
print('largest streams:', ', '.join(f'{s}:{len(streams[s])}B head={streams[s][:6].hex()}' for s in big))
print(f'datagrams: {len(dgrams)}, {sum(len(d) for _, d in dgrams)} bytes')
if outdir:
    os.makedirs(outdir, mode=0o700, exist_ok=True)
    for sid, b in streams.items():
        open(os.path.join(outdir, f'stream_{sid}.bin'), 'wb').write(b)
    with open(os.path.join(outdir, 'datagrams.bin'), 'wb') as fh:
        for pn, d in dgrams:
            fh.write(struct.pack('<II', pn & 0xffffffff, len(d)) + d)
    print('wrote', outdir)
