"""Find direct `call rel32` sites to given addresses in a PE's .text.

usage: python3 -I callscan.py EXE 0xADDR ...
"""
import struct
import sys

import numpy as np

exe = sys.argv[1]
data = open(exe, 'rb').read()
pe = struct.unpack_from('<I', data, 0x3c)[0]
nsec = struct.unpack_from('<H', data, pe + 6)[0]
optsz = struct.unpack_from('<H', data, pe + 20)[0]
base = struct.unpack_from('<Q', data, pe + 24 + 24)[0]
for i in range(nsec):
    o = pe + 24 + optsz + i * 40
    if data[o:o + 8].rstrip(b'\0') == b'.text':
        vsize, va, rsize, raw = struct.unpack_from('<IIII', data, o + 8)
buf = np.frombuffer(data, dtype=np.uint8, count=rsize, offset=raw)
cand = np.nonzero(buf[:-5] == 0xE8)[0]
rel = (buf[cand + 1].astype(np.int64) | (buf[cand + 2].astype(np.int64) << 8) | (buf[cand + 3].astype(np.int64) << 16) | (buf[cand + 4].astype(np.int64) << 24))
rel = np.where(rel >= 1 << 31, rel - (1 << 32), rel)
tgt = base + va + cand + 5 + rel
for a in sys.argv[2:]:
    t = int(a, 16)
    print(a, [hex(base + va + int(h)) for h in cand[tgt == t]][:20])
