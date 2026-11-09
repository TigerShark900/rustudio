"""Parse the RbxTransport replication schema (Roblox packet 0x97) from a
decrypted rbx-rtcio stream [verified: capture, Studio 0.746 Team Create join].

0x97 message: 97 <u32 LE compressed len> <u32 LE decompressed len> <zstd frame>
Decompressed:
  9-byte prefix (03 01 + 7 zero bytes in the capture)
  varint nEnums,  nEnums x { varstr name, u8 bits }
  varint nClasses, varint totalProps, varint totalEvents
  nClasses x { varstr name, varint nProps,
               nProps x { varstr name, u8 type, extra (type 0x07 enum: u16 LE enum index; type 0x3c: 1 byte) },
               u16 (ff ff in every class seen),
               varint nEvents, nEvents x { varstr name, varint nArgs, nArgs x { u8 type, u16 LE enum (ffff=none) } } }
  varint nPrefixes,  nPrefixes x varstr     (content-URL prefixes: rbxassetid://, ...)
  varint nNames,     nNames x varstr        (common instance-name dictionary: AccessoryWeld, Animate, ...)
varint = unsigned LEB128, varstr = varint length + bytes.

usage: python3 -I rtcio_schema.py OUTDIR [OUT.json]
"""
import json
import struct
import sys

EXTRA = {0x07: 2, 0x3c: 1}


class R:
    def __init__(self, d, o=0):
        self.d, self.o = d, o

    def u8(self):
        self.o += 1
        return self.d[self.o - 1]

    def uv(self):
        v = s = 0
        while True:
            b = self.u8()
            v |= (b & 0x7f) << s
            s += 7
            if not b & 0x80:
                return v

    def bytes(self, n):
        self.o += n
        return self.d[self.o - n:self.o]

    def str(self):
        return self.bytes(self.uv()).decode('utf-8', 'replace')


def parse(d):
    r = R(d, 9)
    enums = []
    for _ in range(r.uv()):
        enums.append({'name': r.str(), 'bits': r.u8()})
    nc = r.uv()
    r.uv(), r.uv()
    classes = []
    for _ in range(nc):
        c = {'name': r.str(), 'props': [], 'events': []}
        for _ in range(r.uv()):
            name, t = r.str(), r.u8()
            p = {'name': name, 'type': t}
            ex = r.bytes(EXTRA.get(t, 0))
            if t == 0x07:
                p['enum'] = enums[ex[0] | ex[1] << 8]['name']
            elif ex:
                p['extra'] = ex.hex()
            c['props'].append(p)
        c['tail'] = r.bytes(2).hex()
        for _ in range(r.uv()):
            name = r.str()
            args = [r.bytes(3).hex() for _ in range(r.uv())]
            c['events'].append({'name': name, 'args': args})
        classes.append(c)
    prefixes = [r.str() for _ in range(r.uv())]
    names = [r.str() for _ in range(r.uv())]
    return {'prefix': d[:9].hex(), 'enums': enums, 'classes': classes, 'content_prefixes': prefixes,
            'names': names, 'trailing': len(d) - r.o}


def from_message(m):
    from compression import zstd
    assert m[0] == 0x97
    clen, dlen = struct.unpack_from('<II', m, 1)
    d = zstd.decompress(m[9:9 + clen])
    assert len(d) == dlen
    return parse(d)


if __name__ == '__main__':
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from rtcio_split import split
    import glob
    for f in glob.glob(os.path.join(sys.argv[1], 'stream_*.bin')):
        _, msgs, _ = split(open(f, 'rb').read())
        for m in msgs:
            if m and m[0] == 0x97:
                s = from_message(m)
                from collections import Counter
                print(f'{os.path.basename(f)}: {len(s["enums"])} enums, {len(s["classes"])} classes, '
                      f'{sum(len(c["props"]) for c in s["classes"])} props, {len(s["content_prefixes"])} prefixes, '
                      f'{len(s["names"])} names, trailing {s["trailing"]}')
                print('prop types:', sorted(Counter(p['type'] for c in s['classes'] for p in c['props']).items()))
                if len(sys.argv) > 2:
                    json.dump(s, open(sys.argv[2], 'w'), indent=0)
