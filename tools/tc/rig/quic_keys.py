"""Recover the QUIC 1-RTT traffic secrets of a live RbxTransport connection from
the capture Studio's memory, verified by trial decryption.

OpenSSL keeps a connection's client_random and its TLS 1.3 secrets in the
same SSL object. We find every copy of the ClientHello's client_random in the
process's writable memory, try each WINDOW-byte neighbourhood at STEP-byte
alignment as a traffic secret, derive the QUIC packet keys (RFC 9001 5.1:
HKDF-Expand-Label "quic key"/"quic iv"/"quic hp") and accept a candidate only
if it removes header protection and AEAD-opens a captured 1-RTT packet of the
right direction. Accepted secrets go to OUT_KEYLOG (NSS format, mode 0600);
nothing secret is printed.

Must run where /proc/PID/mem is readable (inside the rig's userns: `tcstudio run`).

usage: python3 -I quic_keys.py PID STRIPPED.pcap CLIENT_RANDOM_HEX CIPHER(0x1302|0x1303) CLIENT_IP OUT_KEYLOG
       [CID_LEN=20] [WINDOW=32768] [STEP=8]
"""
import os
import re
import struct
import sys

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand

pid, pcap, cr_hex, cipher, client_ip, out = sys.argv[1:7]
cid_len = int(sys.argv[7]) if len(sys.argv) > 7 else 20
window = int(sys.argv[8]) if len(sys.argv) > 8 else 32768
step = int(sys.argv[9]) if len(sys.argv) > 9 else 8
client_random = bytes.fromhex(cr_hex)
# The in-memory byte pattern to anchor the window on (default: the client_random
# itself). Set TC_ANCHOR to a known secret's hex to search near it instead.
anchor_pat = bytes.fromhex(os.environ.get('TC_ANCHOR', cr_hex))
# TC_ANCHOR_FROM_KEYLOG=client|server: anchor the window on a secret already in
# the OUT keylog (so the server secret can be found next to the known client
# one, without the value touching the shell).
_akl = os.environ.get('TC_ANCHOR_FROM_KEYLOG')
if _akl and os.path.exists(out):
    _lab = 'CLIENT_TRAFFIC_SECRET_0' if _akl == 'client' else 'SERVER_TRAFFIC_SECRET_0'
    for _ln in open(out):
        _p = _ln.split()
        if len(_p) == 3 and _p[0] == _lab:
            anchor_pat = bytes.fromhex(_p[2])
cipher = int(cipher, 16)
if cipher == 0x1302:
    H, SLEN, KLEN = hashes.SHA384, 48, 32
elif cipher == 0x1303:
    H, SLEN, KLEN = hashes.SHA256, 32, 32
elif cipher == 0x1301:
    H, SLEN, KLEN = hashes.SHA256, 32, 16
else:
    sys.exit('unknown cipher')


def expand_label(secret, label, length):
    full = b'tls13 ' + label
    info = struct.pack('>H', length) + bytes([len(full)]) + full + b'\x00'
    return HKDFExpand(algorithm=H(), length=length, info=info).derive(secret)


def hp_mask(hp, sample):
    if cipher == 0x1303:
        c = Cipher(algorithms.ChaCha20(hp, sample[:16]), mode=None).encryptor()
        return c.update(b'\x00' * 5)
    c = Cipher(algorithms.AES(hp), modes.ECB()).encryptor()
    return c.update(sample[:16])[:5]


# DCID lengths to try per 1-RTT packet. The client's DCID (server's chosen CID)
# is known (cid_len); server→client packets may carry a different-length CID
# issued during the handshake, so try a range.
CIDLENS = list(range(0, 21))


def try_open(secret, pkt):
    key = expand_label(secret, b'quic key', KLEN)
    iv = expand_label(secret, b'quic iv', 12)
    hp = expand_label(secret, b'quic hp', KLEN)
    aead = ChaCha20Poly1305(key) if cipher == 0x1303 else AESGCM(key)
    ivn = int.from_bytes(iv, 'big')
    for cl in CIDLENS:
        pn_off = 1 + cl
        if len(pkt) < pn_off + 4 + 16:
            continue
        mask = hp_mask(hp, pkt[pn_off + 4: pn_off + 20])
        first = pkt[0] ^ (mask[0] & 0x1f)
        pnl = (first & 3) + 1
        pn_bytes = bytes(b ^ m for b, m in zip(pkt[pn_off: pn_off + pnl], mask[1:1 + pnl]))
        pn = int.from_bytes(pn_bytes, 'big')
        aad = bytes([first]) + pkt[1:pn_off] + pn_bytes
        nonce = (ivn ^ pn).to_bytes(12, 'big')
        try:
            aead.decrypt(nonce, pkt[pn_off + pnl:], aad)
            return True
        except Exception:
            continue
    return False


# Pick a few large short-header (1-RTT) packets per direction from the stripped
# pcap (raw IPv4, linktype 101): large ones are app-data STREAM packets, past
# any transitional first packet. try_open accepts a secret if it opens ANY of
# them.
data = open(pcap, 'rb').read()
off = 24
cands = {'client': [], 'server': []}
cip = bytes(int(x) for x in client_ip.split('.'))
while off + 16 <= len(data):
    incl = struct.unpack_from('<I', data, off + 8)[0]
    ip = data[off + 16: off + 16 + incl]
    off += 16 + incl
    q = ip[28:]
    if not q or q[0] & 0x80 or not q[0] & 0x40:
        continue  # long header or not QUIC
    d = 'client' if ip[12:16] == cip else 'server'
    cands[d].append(q)
# Up to 8 of the largest datagrams among the FIRST 1500 per direction (early,
# so pre- any key update) plus the overall first packet.
first_pkt = {}
for d, v in cands.items():
    if not v:
        continue
    early = v[:1500]
    first_pkt[d] = ([v[0]] + sorted(early, key=len, reverse=True))[:8]
print('1-RTT samples:', ', '.join(f'{k}:{len(v)} (max {len(v[0])}B)' for k, v in first_pkt.items()))

# A direction already known from a prior run's keylog is skipped (so a second
# pass can hunt only the missing one).
found = {}
prior = {}
if os.path.exists(out):
    for ln in open(out):
        p = ln.split()
        if len(p) == 3 and p[1] == cr_hex:
            d = 'client' if p[0].startswith('CLIENT') else 'server'
            prior[d] = bytes.fromhex(p[2])
want = [d for d in ('client', 'server') if d in first_pkt and d not in prior]

maps = open(f'/proc/{pid}/maps').read().splitlines()
mem = open(f'/proc/{pid}/mem', 'rb', buffering=0)
hits = 0


def high_entropy(b):
    # a TLS secret is ~random: many distinct bytes, no long zero run.
    if b.count(0) > 4:
        return False
    return len(set(b)) >= SLEN * 3 // 4


def test_window(win, base, anchor):
    for i in range(0, len(win) - SLEN, step):
        cand = win[i:i + SLEN]
        if not high_entropy(cand):
            continue
        for d in want:
            if d not in found and any(try_open(cand, p) for p in first_pkt[d]):
                found[d] = cand
                where = f'(offset {base + i - anchor:+d} from client_random)' if anchor is not None else f'(addr {hex(base + i)})'
                print(f'{d} traffic secret: verified by decrypting a 1-RTT packet {where}')


for line in maps:
    f = line.split()
    if 'rw' not in f[1] or (len(f) > 5 and f[5].startswith('[v')):
        continue
    lo, hi = (int(x, 16) for x in f[0].split('-'))
    if hi - lo > (1 << 28):  # skip > 256 MB (GPU/texture arenas)
        continue
    pos = lo
    while pos < hi and len(found) < len(want):
        n = min(64 << 20, hi - pos)
        try:
            mem.seek(pos)
            buf = mem.read(n)
        except OSError:
            break
        if window == 0:
            # whole-memory: numpy pre-filter to windows with <=4 zero bytes,
            # then trial-decrypt only those (far fewer AEAD calls).
            import numpy as np
            a = np.frombuffer(buf, dtype=np.uint8)
            if len(a) > SLEN:
                zc = np.cumsum(a == 0)
                wins = zc[SLEN - 1:] - np.concatenate(([0], zc[:-SLEN]))
                for i in np.nonzero(wins <= 4)[0]:
                    i = int(i)
                    if i % step:
                        continue
                    cand = buf[i:i + SLEN]
                    if len(set(cand)) < SLEN * 3 // 4:
                        continue
                    for d in want:
                        if d not in found and any(try_open(cand, p) for p in first_pkt[d]):
                            found[d] = cand
                            print(f'{d} traffic secret: verified (addr {hex(pos + i)})')
                    if len(found) >= len(want):
                        break
        else:
            for m in re.finditer(re.escape(anchor_pat), buf):
                hits += 1
                a = pos + m.start()
                wlo = max(lo, a - window)
                try:
                    mem.seek(wlo)
                    win = mem.read(min(hi, a + window) - wlo)
                except OSError:
                    continue
                test_window(win, wlo, a)
                if len(found) >= len(want):
                    break
        pos += n
    if len(found) >= len(want):
        break
found.update(prior)
print(f'client_random copies found: {hits}; secrets found: {sorted(found)}')
if found:
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    lines = []
    if 'client' in found:
        lines.append(f'CLIENT_TRAFFIC_SECRET_0 {cr_hex} {found["client"].hex()}')
    if 'server' in found:
        lines.append(f'SERVER_TRAFFIC_SECRET_0 {cr_hex} {found["server"].hex()}')
    os.write(fd, ('\n'.join(lines) + '\n').encode())
    os.close(fd)
    print('wrote keylog', out)
