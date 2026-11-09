"""Recover the installed QUIC 1-RTT packet keys (key / iv / hp) of a live
RbxTransport connection from the capture Studio's memory — for the direction
whose *secret* is not resident (server->client).

ngtcp2 (crypto_ossl) keeps the AEAD and header-protection keys as OpenSSL
EVP_CIPHER_CTXs, i.e. as expanded AES key schedules, and the first 32 bytes of
an AES-256 encryption schedule are the raw key. So:

1. scan the process's writable memory for AES-256 encryption key schedules
   (numpy test of the first expanded word, then a full 240-byte check) and
   collect the distinct raw keys;
2. the header-protection key of a direction is the candidate that unmasks a
   run of that direction's captured 1-RTT packets to reserved-bits-zero
   headers with increasing packet numbers;
3. the AEAD key is the candidate for which the GCM tag of a captured packet,
   un-GHASHed and decrypted, yields a pre-counter block J0 = nonce || 00000001
   (so the 12-byte static IV falls out as nonce XOR pn, no IV scan needed);
4. accept only if (key, iv, hp) AEAD-opens several packets of that direction.

The result is written to OUT (mode 0600) as `DIR key iv hp` hex lines, for
quic_decode.py's --km mode. Nothing secret is printed.

usage (as rig root: tcstudio runroot python3 -I quic_rxkm.py ...):
  python3 -I quic_rxkm.py PID STRIPPED.pcap CLIENT_IP OUT [DCID_LEN_S2C=20] [DCID_LEN_C2S=20]
"""
import os
import struct
import sys

import numpy as np
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

pid, pcap, client_ip, out = sys.argv[1:5]
cidl = {'server': int(sys.argv[5]) if len(sys.argv) > 5 else 20,
        'client': int(sys.argv[6]) if len(sys.argv) > 6 else 20}

# --- AES S-box / key expansion ---------------------------------------------
SBOX = [0] * 256
p = q = 1
while True:
    p = (p ^ (p << 1) ^ (0x1b if p & 0x80 else 0)) & 0xff
    q ^= q << 1
    q ^= q << 2
    q ^= q << 4
    q &= 0xff
    if q & 0x80:
        q ^= 0x09
    x = q ^ ((q << 1) | (q >> 7)) ^ ((q << 2) | (q >> 6)) ^ ((q << 3) | (q >> 5)) ^ ((q << 4) | (q >> 4))
    SBOX[p] = (x ^ 0x63) & 0xff
    if p == 1:
        break
SBOX[0] = 0x63
S = np.array(SBOX, dtype=np.uint8)
RCON = [1, 2, 4, 8, 16, 32, 64]


def expand256(k):
    w = [list(k[i:i + 4]) for i in range(0, 32, 4)]
    for i in range(8, 60):
        t = list(w[i - 1])
        if i % 8 == 0:
            t = [SBOX[b] for b in t[1:] + t[:1]]
            t[0] ^= RCON[i // 8 - 1]
        elif i % 8 == 4:
            t = [SBOX[b] for b in t]
        w.append([a ^ b for a, b in zip(w[i - 8], t)])
    return bytes(sum(w, []))


def wordswap(b):
    return b''.join(b[i:i + 4][::-1] for i in range(0, len(b), 4))


def scan_buf(buf):
    """Offsets (4-aligned) where buf holds an AES-256 encryption schedule, as
    (offset, raw_key). Tries byte order as stored (AES-NI) and per-word swapped
    (OpenSSL's C AES keeps rd_key as native u32 of big-endian words)."""
    a = np.frombuffer(buf, dtype=np.uint8)
    res = []
    if len(a) < 240:
        return res
    n = len(a) - 240
    for swapped in (False, True):
        if not swapped:
            c = (a[32:32 + n] == (a[0:n] ^ S[a[29:29 + n]] ^ 1))
            c &= (a[33:33 + n] == (a[1:1 + n] ^ S[a[30:30 + n]]))
            c &= (a[34:34 + n] == (a[2:2 + n] ^ S[a[31:31 + n]]))
            c &= (a[35:35 + n] == (a[3:3 + n] ^ S[a[28:28 + n]]))
        else:
            # word j byte b lives at 4j + (3-b)
            c = (a[35:35 + n] == (a[3:3 + n] ^ S[a[30:30 + n]] ^ 1))
            c &= (a[34:34 + n] == (a[2:2 + n] ^ S[a[29:29 + n]]))
            c &= (a[33:33 + n] == (a[1:1 + n] ^ S[a[28:28 + n]]))
            c &= (a[32:32 + n] == (a[0:0 + n] ^ S[a[31:31 + n]]))
        for i in np.nonzero(c)[0]:
            i = int(i)
            if i % 4:
                continue
            sched = bytes(buf[i:i + 240])
            if swapped:
                sched = wordswap(sched)
            k = sched[:32]
            if len(set(k)) < 20:
                continue
            if expand256(k) == sched:
                res.append((i, k))
    return res


# --- captured 1-RTT packets per direction ----------------------------------
data = open(pcap, 'rb').read()
cip = bytes(int(x) for x in client_ip.split('.'))
pk = {'client': [], 'server': []}
off = 24
while off + 16 <= len(data):
    incl = struct.unpack_from('<I', data, off + 8)[0]
    ip = data[off + 16: off + 16 + incl]
    off += 16 + incl
    qp = ip[28:]
    if not qp or qp[0] & 0x80 or not qp[0] & 0x40:
        continue
    pk['client' if ip[12:16] == cip else 'server'].append(qp)
# TC_SKIP=server:440,client:179 drops each direction's first N 1-RTT packets (to hunt a later key set)
for _kv in filter(None, os.environ.get('TC_SKIP', '').split(',')):
    _d, _n = _kv.split(':')
    pk[_d] = pk[_d][int(_n):]
print('1-RTT packets:', {k: len(v) for k, v in pk.items()})


def unmask(hp, pkt, cl):
    po = 1 + cl
    m = Cipher(algorithms.AES(hp), modes.ECB()).encryptor().update(pkt[po + 4: po + 20])[:5]
    first = pkt[0] ^ (m[0] & 0x1f)
    pnl = (first & 3) + 1
    pnb = bytes(x ^ y for x, y in zip(pkt[po:po + pnl], m[1:1 + pnl]))
    return first, pnl, pnb, po


def hp_score(hp, d):
    """count of the first 40 packets whose unmasked header has reserved bits 0
    and a packet number within +64 of the previous (truncated pn arithmetic)."""
    cl = cidl[d]
    ok, last = 0, None
    for pkt in pk[d][:40]:
        first, pnl, pnb, _ = unmask(hp, pkt, cl)
        if first & 0x18:
            continue
        pn = int.from_bytes(pnb, 'big')
        if last is None or 0 <= (pn - last) % (1 << (8 * pnl)) <= 64:
            ok += 1
        last = pn
    return ok


def gf_mul(x, y):
    R = 0xe1 << 120
    z, v = 0, y
    for i in range(127, -1, -1):
        if (x >> i) & 1:
            z ^= v
        v = (v >> 1) ^ R if v & 1 else v >> 1
    return z


def ghash(h, aad, ct):
    def blocks(b):
        for i in range(0, len(b), 16):
            yield int.from_bytes(b[i:i + 16].ljust(16, b'\0'), 'big')
    y = 0
    for blk in list(blocks(aad)) + list(blocks(ct)):
        y = gf_mul(y ^ blk, h)
    y = gf_mul(y ^ ((len(aad) * 8) << 64 | len(ct) * 8), h)
    return y


def nonce_from_tag(key, aad, ct_and_tag):
    ct, tag = ct_and_tag[:-16], ct_and_tag[-16:]
    ecb = Cipher(algorithms.AES(key), modes.ECB())
    h = int.from_bytes(ecb.encryptor().update(b'\0' * 16), 'big')
    s = ghash(h, aad, ct)
    ekj0 = (int.from_bytes(tag, 'big') ^ s).to_bytes(16, 'big')
    j0 = ecb.decryptor().update(ekj0)
    return j0[:12] if j0[12:] == b'\0\0\0\1' else None


# --- scan memory -----------------------------------------------------------
keys = {}
maps = open(f'/proc/{pid}/maps').read().splitlines()
mem = open(f'/proc/{pid}/mem', 'rb', buffering=0)
CH = 64 << 20
for line in maps:
    f = line.split()
    if 'rw' not in f[1]:
        continue
    lo, hi = (int(x, 16) for x in f[0].split('-'))
    if hi - lo > (1 << 30):
        continue
    pos = lo
    while pos < hi:
        n = min(CH + 256, hi - pos)
        try:
            mem.seek(pos)
            buf = mem.read(n)
        except OSError:
            break
        for i, k in scan_buf(buf):
            keys.setdefault(k, pos + i)
        pos += CH
print(f'AES-256 key schedules found: {len(keys)} distinct keys')

found = {}
for d in ('server', 'client'):
    if not pk[d]:
        continue
    hps = sorted(((hp_score(k, d), k) for k in keys), reverse=True)
    hps = [k for s, k in hps if s >= 36]
    print(f'{d}: {len(hps)} header-protection key candidate(s)')
    for hp in hps:
        # smallest early packets keep the GHASH cheap
        # The IV falls out as nonce XOR pn, and only the header's pn bits are
        # known, so derive it from a packet with a 2-byte (or longer) packet
        # number: the RbxTransport pn spaces don't start near 0, and a 1-byte
        # pn would leave IV bits 8-15 wrong. Small packets keep GHASH cheap.
        multi = [i for i, x in enumerate(pk[d][:20000]) if (unmask(hp, x, cidl[d])[1]) >= 2]
        si = min(multi[:400], key=lambda i: len(pk[d][i])) if multi else 0
        sample = [pk[d][si]]
        verify = [x for x in pk[d][si:si + 400] if unmask(hp, x, cidl[d])[1] >= 2][:50]
        for key in keys:
            if key == hp:
                continue
            first, pnl, pnb, po = unmask(hp, sample[0], cidl[d])
            aad = bytes([first]) + sample[0][1:po] + pnb
            nonce = nonce_from_tag(key, aad, sample[0][po + pnl:])
            if nonce is None:
                continue
            iv = (int.from_bytes(nonce, 'big') ^ int.from_bytes(pnb, 'big')).to_bytes(12, 'big')
            # full verification: AEAD-open more packets (pn reconstructed from truncation, small here)
            g = AESGCM(key)
            okc = 0
            for pkt in verify:
                first, pnl, pnb, po = unmask(hp, pkt, cidl[d])
                pn = int.from_bytes(pnb, 'big')
                aad = bytes([first]) + pkt[1:po] + pnb
                try:
                    g.decrypt((int.from_bytes(iv, 'big') ^ pn).to_bytes(12, 'big'), pkt[po + pnl:], aad)
                    okc += 1
                except Exception:
                    pass
            print(f'{d}: key/iv/hp candidate opens {okc}/{len(verify)} multi-byte-pn packets '
                  f'(key schedule at {hex(keys[key])}, hp schedule at {hex(keys[hp])})')
            if okc >= min(5, len(verify)) and okc >= 3:
                found[d] = (key, iv, hp)
                break
        if d in found:
            break

if found:
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.write(fd, ''.join(f'{d} {k.hex()} {i.hex()} {h.hex()}\n' for d, (k, i, h) in found.items()).encode())
    os.close(fd)
    print('wrote key material for', sorted(found), 'to', out)
else:
    print('no key material verified')
