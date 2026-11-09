"""Dump script sources (SharedString Source) from a binary .rbxm.

usage: python3 -I rbxm_src.py MODEL.rbxm OUTDIR
"""
import os
import struct
import sys

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import rbxm  # noqa: E402

path, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
data = open(path, 'rb').read()
objs = rbxm.load(path)
classes = {}
shared = []
src_refs = {}
for name, body in rbxm.chunks(data):
    if name == b'INST':
        cid, ln = struct.unpack_from('<II', body, 0)
        o = 8 + ln + 1
        (count,) = struct.unpack_from('<I', body, o)
        raw = body[o + 4:o + 4 + 4 * count]
        acc, refs = 0, []
        for k in range(count):
            v = int.from_bytes(bytes(raw[k + j * count] for j in range(4)), 'big')
            acc += (v >> 1) ^ -(v & 1)
            refs.append(acc)
        classes[cid] = refs
    elif name == b'SSTR':
        ver, count = struct.unpack_from('<II', body, 0)
        o = 8
        for _ in range(count):
            o += 16
            (ln,) = struct.unpack_from('<I', body, o)
            o += 4
            shared.append(body[o:o + ln])
            o += ln
    elif name == b'PROP':
        cid, ln = struct.unpack_from('<II', body, 0)
        pname = body[8:8 + ln].decode()
        o = 8 + ln
        if pname == 'Source' and body[o] == 29:
            refs = classes[cid]
            count = len(refs)
            vals, _ = rbxm.read_strings(body, o + 1, count)
            for r, v in zip(refs, vals):
                src_refs[r] = v
n = 0
for r, idx in src_refs.items():
    fn = rbxm.full_name(objs, r).replace('/', '_')
    open(os.path.join(out, fn + '.bin'), 'wb').write(idx)
    n += 1
print(n, 'sources;', len(shared), 'shared strings')
