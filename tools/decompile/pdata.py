"""Function bounds from a PE's .pdata (RUNTIME_FUNCTION entries) for given addresses.

usage: python3 -I pdata.py EXE 0xADDR [0xADDR ...]
"""
import bisect
import struct
import sys

exe = sys.argv[1]
data = open(exe, 'rb').read()
pe = struct.unpack_from('<I', data, 0x3c)[0]
nsec = struct.unpack_from('<H', data, pe + 6)[0]
optsz = struct.unpack_from('<H', data, pe + 20)[0]
opt = pe + 24
base = struct.unpack_from('<Q', data, opt + 24)[0]
exc_rva, exc_size = struct.unpack_from('<II', data, opt + 112 + 3 * 8)
secs = []
for i in range(nsec):
    o = opt + optsz + i * 40
    vsize, va, rsize, raw = struct.unpack_from('<IIII', data, o + 8)
    secs.append((va, vsize, raw))


def off(rva):
    for va, vs, raw in secs:
        if va <= rva < va + vs:
            return raw + rva - va
    raise ValueError(hex(rva))


o = off(exc_rva)
ents = [struct.unpack_from('<III', data, o + 12 * i) for i in range(exc_size // 12)]
ents.sort()
starts = [e[0] for e in ents]
for a in sys.argv[2:]:
    rva = int(a, 16) - base
    i = bisect.bisect_right(starts, rva) - 1
    b, e, u = ents[i]
    # chained unwind info: walk back to the primary entry
    while True:
        uo = off(u & ~1)
        flags = data[uo] >> 3
        if not flags & 4:
            break
        cnt = data[uo + 2]
        co = uo + 4 + ((cnt + 1) & ~1) * 2
        b, e, u = struct.unpack_from('<III', data, co)
    print(a, '->', hex(base + b), '..', hex(base + e))
