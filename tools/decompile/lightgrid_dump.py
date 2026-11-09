"""Dumps a running Studio's light grid (LightGridCPU) from /proc/<pid>/mem.

usage: python3 -I lightgrid_dump.py PID OUTPREFIX
writes OUTPREFIX.hdr (origin voxel x y z, size x y z), .occ.bin (3 planes,
each Y×Z×X bytes: occupancy seen along X, Y, Z), .sky.bin and .sun.bin
(Y×Z×X) — the files lightgrid.rs's lightgrid_vs_studio test reads.

Layout (RobloxStudioBeta 0.746, docs/STUDIO-SKY-RE.md "Light grid (skylight)"):
the LightGridCPU object starts with vtable 0x149226388; +0x50 dims in chunks,
+0x5c origin in chunks, +0x18128 → context, context+0x53448 → chunk pointer
vector. Chunk: +0 flags, +8 chunk coords, +0x14 occupancy (3 × 16 × 32 × 32),
+0x1c01c skylight / sun byte pairs (16 × 32 × 32 × 2). Lighting.GlobalShadows
must be on (else the skylight stays 255).
"""
import re
import struct
import sys

import numpy as np

VT = 0x149226388


def main():
    pid, out = int(sys.argv[1]), sys.argv[2]
    mem = open(f'/proc/{pid}/mem', 'rb')

    def rd(a, n):
        mem.seek(a)
        return mem.read(n)

    objs = []
    pat = struct.pack('<Q', VT)
    for line in open(f'/proc/{pid}/maps'):
        m = re.match(r'([0-9a-f]+)-([0-9a-f]+) (\S+)', line)
        s, e = int(m[1], 16), int(m[2], 16)
        if not m[3].startswith('rw') or e - s > 1 << 31:
            continue
        try:
            d = rd(s, e - s)
        except OSError:
            continue
        objs += [s + x.start() for x in re.finditer(re.escape(pat), d) if x.start() % 8 == 0]
    o = objs[0]
    dims = struct.unpack('<3i', rd(o + 0x50, 12))
    org = struct.unpack('<3i', rd(o + 0x5c, 12))
    ctx = struct.unpack('<Q', rd(o + 0x18128, 8))[0]
    b, e = struct.unpack('<2Q', rd(ctx + 0x53448, 16))
    ptrs = struct.unpack(f'<{(e - b) // 8}Q', rd(b, e - b))
    X, Y, Z = dims[0] * 32, dims[1] * 16, dims[2] * 32
    occ = np.zeros((3, Y, Z, X), np.uint8)
    sky = np.zeros((Y, Z, X), np.uint8)
    sun = np.zeros((Y, Z, X), np.uint8)
    for p in ptrs:
        h = rd(p, 0x2541c)
        cx, cy, cz = struct.unpack_from('<3i', h, 8)
        i, j, k = cx - org[0], cy - org[1], cz - org[2]
        sl = (slice(j * 16, j * 16 + 16), slice(k * 32, k * 32 + 32), slice(i * 32, i * 32 + 32))
        occ[(slice(None),) + sl] = np.frombuffer(h, np.uint8, 0xc000, 0x14).reshape(3, 16, 32, 32)
        pair = np.frombuffer(h, np.uint8, 0x8000, 0x1c01c).reshape(16, 32, 32, 2)
        sky[sl], sun[sl] = pair[..., 0], pair[..., 1]
    occ.tofile(out + '.occ.bin')
    sky.tofile(out + '.sky.bin')
    sun.tofile(out + '.sun.bin')
    open(out + '.hdr', 'w').write('%d %d %d %d %d %d\n' % (org[0] * 32, org[1] * 16, org[2] * 32, X, Y, Z))
    print('grid', dims, 'origin chunks', org, 'at', hex(o))


main()
