"""Show the strings that code near each reference to STRING also loads.

For every RIP-relative lea/mov in .text that points at the exact C string
STRING, print the other C strings referenced by lea/mov within +-WINDOW bytes,
in code order. That is usually enough to read how a request is built (method,
path, JSON keys, headers) without a full decompile.

usage: python3 -I strctx.py EXE STRING [WINDOW]
"""
import struct
import sys

import numpy as np

exe, needle = sys.argv[1], sys.argv[2].encode()
window = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0x400
data = open(exe, 'rb').read()
pe = struct.unpack_from('<I', data, 0x3c)[0]
nsec = struct.unpack_from('<H', data, pe + 6)[0]
optsz = struct.unpack_from('<H', data, pe + 20)[0]
base = struct.unpack_from('<Q', data, pe + 24 + 24)[0]
secs = []
for i in range(nsec):
    o = pe + 24 + optsz + i * 40
    name = data[o:o + 8].rstrip(b'\0').decode()
    vsize, va, rsize, raw = struct.unpack_from('<IIII', data, o + 8)
    secs.append((name, va, vsize, raw, rsize))


def va_of(off):
    for _, va, vs, raw, rs in secs:
        if raw <= off < raw + rs:
            return base + va + off - raw
    return None


def off_of(addr):
    rva = addr - base
    for _, va, vs, raw, rs in secs:
        if va <= rva < va + min(vs, rs):
            return raw + rva - va
    return None


def cstr(addr):
    o = off_of(addr)
    if o is None:
        return None
    end = data.find(b'\0', o, o + 300)
    if end <= o:
        return None
    s = data[o:end]
    if o > 0 and data[o - 1] != 0:
        return None  # not the start of a string
    if all(32 <= c < 127 for c in s) and len(s) >= 2:
        return s.decode()
    return None


targets = []
i = data.find(b'\0' + needle + b'\0')
while i >= 0:
    targets.append(va_of(i + 1))
    i = data.find(b'\0' + needle + b'\0', i + 1)
text = next(s for s in secs if s[0] == '.text')
_, tva, _, traw, trs = text
buf = np.frombuffer(data, dtype=np.uint8, count=trs, offset=traw)
cand = np.nonzero(((buf[1:-5] == 0x8D) | (buf[1:-5] == 0x8B)) & ((buf[2:-4] & 0xC7) == 0x05)
                  & ((buf[:-6] == 0x48) | (buf[:-6] == 0x4C)))[0]
disp = (buf[cand + 3].astype(np.int64) | (buf[cand + 4].astype(np.int64) << 8)
        | (buf[cand + 5].astype(np.int64) << 16) | (buf[cand + 6].astype(np.int64) << 24))
disp = np.where(disp >= 1 << 31, disp - (1 << 32), disp)
tgt = base + tva + cand + 7 + disp
for t in targets:
    for h in cand[tgt == t]:
        at = base + tva + int(h)
        print(f'--- ref to {needle.decode()!r} at {hex(at)}')
        sel = (cand >= h - window) & (cand <= h + window)
        for c, tt in zip(cand[sel], tgt[sel]):
            s = cstr(int(tt))
            if s is not None:
                mark = '>>' if int(c) == int(h) else '  '
                print(f'{mark} {hex(base + tva + int(c))} {s[:160]!r}')
