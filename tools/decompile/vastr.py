"""Print C strings / floats / dwords stored at virtual addresses of a PE.

usage: python3 -I vastr.py EXE [s|f|d|q]:0xADDR ...
"""
import struct
import sys

exe = sys.argv[1]
data = open(exe, 'rb').read()
pe = struct.unpack_from('<I', data, 0x3c)[0]
nsec = struct.unpack_from('<H', data, pe + 6)[0]
optsz = struct.unpack_from('<H', data, pe + 20)[0]
opt = pe + 24
base = struct.unpack_from('<Q', data, opt + 24)[0]
secs = []
for i in range(nsec):
    o = opt + optsz + i * 40
    vsize, va, rsize, raw = struct.unpack_from('<IIII', data, o + 8)
    secs.append((va, vsize, raw, rsize))


def off(addr):
    rva = addr - base
    for va, vs, raw, rs in secs:
        if va <= rva < va + vs:
            return raw + rva - va
    raise ValueError(hex(addr))


for arg in sys.argv[2:]:
    kind, a = arg.split(':')
    o = off(int(a, 16))
    if kind == 's':
        end = data.index(b'\0', o)
        print(a, repr(data[o:end].decode('utf-8', 'replace')))
    elif kind == 'f':
        print(a, struct.unpack_from('<4f', data, o))
    elif kind == 'd':
        print(a, [hex(x) for x in struct.unpack_from('<4I', data, o)])
    elif kind == 'q':
        print(a, struct.unpack_from('<2d', data, o))
