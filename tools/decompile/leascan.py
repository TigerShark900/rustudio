"""Find RIP-relative lea/mov instructions in a PE's .text that point at given addresses.

usage: python3 -I leascan.py EXE 0xADDR [0xADDR ...]
"""
import struct
import sys

import numpy as np

exe = sys.argv[1]
targets = [int(a, 16) for a in sys.argv[2:]]
data = open(exe, 'rb').read()
pe = struct.unpack_from('<I', data, 0x3c)[0]
nsec = struct.unpack_from('<H', data, pe + 6)[0]
optsz = struct.unpack_from('<H', data, pe + 20)[0]
base = struct.unpack_from('<Q', data, pe + 24 + 24)[0]
sec = pe + 24 + optsz
text = None
for i in range(nsec):
    o = sec + i * 40
    name = data[o:o + 8].rstrip(b'\0').decode()
    vsize, va, rsize, raw = struct.unpack_from('<IIII', data, o + 8)
    if name == '.text':
        text = (va, raw, rsize)
va, raw, rsize = text
buf = np.frombuffer(data, dtype=np.uint8, count=rsize, offset=raw)
# opcode 8D (lea) or 8B (mov) with modrm mod=00 rm=101 (rip-relative), preceded by REX 48/4C
cand = np.nonzero(((buf[1:-5] == 0x8D) | (buf[1:-5] == 0x8B)) & ((buf[2:-4] & 0xC7) == 0x05) & ((buf[:-6] == 0x48) | (buf[:-6] == 0x4C)))[0]
disp = (buf[cand + 3].astype(np.int64) | (buf[cand + 4].astype(np.int64) << 8) | (buf[cand + 5].astype(np.int64) << 16) | (buf[cand + 6].astype(np.int64) << 24))
disp = np.where(disp >= 1 << 31, disp - (1 << 32), disp)
tgt = base + va + cand + 7 + disp
for t in targets:
    hits = cand[tgt == t]
    print(hex(t), [hex(base + va + int(h)) for h in hits])
