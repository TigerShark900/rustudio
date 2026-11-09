"""Decode the initial DataModel stream of a decrypted rbx-rtcio capture into
instances (research decoder; the Rust port is replicator::decode_frame).

Input: quic_decode.py OUTDIR (server direction). Uses the 0x97 schema
(rtcio_schema.py) and the 0x83 ID_DATA messages whose items are 0x16
"initial stream chunks":
  16 <u8 stage> <u32 LE clen> <u32 LE dlen> <zstd frame> <5-byte trailer>
  stage 1: shared strings  { 16B hash, u8 0, varint len, bytes }*
  stage 2/3/4: instance records:
    01 <u32 LE id> <u16 LE class index> { <u8 prop index> <value> }* ff  <parent ref: 01 <u32 LE id>>
Prop index and class index point into the schema (class list / class prop
list order). Value encodings per schema type are in VALUE below; an unknown
type stops that chunk and is reported.

usage: python3 -I rtcio_instances.py OUTDIR [--dump OUT.json] [--tree N]
"""
import json
import os
import struct
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compression import zstd  # noqa: E402

import rtcio_schema  # noqa: E402
from rtcio_split import split  # noqa: E402


TRACE = os.environ.get('TC_TRACE', '').split(',')


class Bad(Exception):
    pass


def uv(d, o):
    v = s = 0
    while True:
        b = d[o]
        o += 1
        v |= (b & 0x7f) << s
        s += 7
        if not b & 0x80:
            return v, o


def zz(v):
    return (v >> 1) ^ -(v & 1)


def f32(d, o, n=1):
    return list(struct.unpack_from(f'<{n}f', d, o)), o + 4 * n


def v_str(d, o):
    n, o = uv(d, o)
    return d[o:o + n].decode('utf-8', 'replace'), o + n


def v_bin(d, o):
    n, o = uv(d, o)
    return {'len': n, 'head': d[o:o + min(n, 32)].hex()}, o + n


def v_ref(d, o):
    k = d[o]
    if k == 0:
        return None, o + 1
    if k == 1:
        return ('ref', struct.unpack_from('<I', d, o + 1)[0]), o + 5
    raise Bad(f'ref kind {k:#x}')


def v_cframe(d, o):
    # [verified: capture] f32 x,y,z then a rotation: u8 id (0 = full 3x3 follows as 9 f32, else axis-aligned id)
    pos, o = f32(d, o, 3)
    rid = d[o]
    o += 1
    if rid == 0:
        rot, o = f32(d, o, 9)
        return {'pos': pos, 'rot': rot}, o
    return {'pos': pos, 'rot_id': rid}, o


def v_ocframe(d, o):
    # OptionalCFrame [verified: capture]: u8 0 = none, else 0x80 | rotation id (0 = 9 f32 follow), then 3 f32 position
    b = d[o]
    o += 1
    if b == 0:
        return None, o
    rid = b & 0x7f
    rot = None
    if rid == 0:
        rot, o = f32(d, o, 9)
    pos, o = f32(d, o, 3)
    return {'pos': pos, 'rot': rot} if rot else {'pos': pos, 'rot_id': rid}, o


def v_font(d, o):
    # Font [verified: capture]: u16 LE weight, u8 style, u32 LE len + family, u32 LE len + cached face id
    w, st, n = struct.unpack_from('<HBI', d, o)
    o += 7
    fam = d[o:o + n].decode('utf-8', 'replace')
    o += n
    n2 = struct.unpack_from('<I', d, o)[0]
    o += 4 + n2
    return {'family': fam, 'weight': w, 'style': st}, o


def v_seq(width):
    def f(d, o):
        n = struct.unpack_from('<I', d, o)[0]
        if n > 64:
            raise Bad(f'sequence count {n}')
        vals, o = f32(d, o + 4, n * width)
        return [vals[i:i + width] for i in range(0, len(vals), width)], o
    return f


def v_physprops(d, o):
    # PhysicalProperties [verified: capture]: u8 flags (0 = default); bit0: density, friction, elasticity,
    # frictionWeight, elasticityWeight; bit1: + acousticAbsorption (all f32)
    fl = d[o]
    o += 1
    if not fl:
        return None, o
    n = 5 + (1 if fl & 2 else 0)
    vals, o = f32(d, o, n)
    return vals, o


def v_solidmesh(d, o):
    # SolidMeshHolder [verified: capture, meaning partly opaque]: u32 LE n, then n x
    # { u8 1, u16 0, varint id, u32 LE 3, u32 LE 0 }
    n = struct.unpack_from('<I', d, o)[0]
    if n > 64:
        raise Bad(f'solidmesh count {n}')
    o += 4
    ents = []
    for _ in range(n):
        k, z = d[o], d[o + 1:o + 3]
        i, o = uv(d, o + 3)
        a, b = struct.unpack_from('<II', d, o)
        o += 8
        ents.append((k, i, a, b))
    return ents, o


def v_name(names):
    # Name [verified: capture]: u8 b; b & 0x80 -> the schema's common-name dictionary entry b & 0x7f,
    # else b is the length of a UTF-8 string that follows
    def f(d, o):
        b = d[o]
        if b & 0x80:
            return names[b & 0x7f], o + 1
        return v_str(d, o)
    return f


def v_content(d, o):
    k = d[o]
    if k == 0:
        return None, o + 1
    if k == 1:
        return v_str(d, o + 1)
    raise Bad(f'content kind {k:#x}')


VALUE = {
    0x02: v_str,                                            # string
    0x06: lambda d, o: (('sharedsrc', d[o:o + 16].hex()), o + 16),   # ProtectedString by shared-string hash
    0x07: lambda d, o: uv(d, o),                            # enum (varint)
    0x08: v_bin,                                            # BinaryString
    0x09: lambda d, o: (bool(d[o]), o + 1),                 # bool
    0x0a: lambda d, o: (lambda v, p: (zz(v), p))(*uv(d, o)),   # int32, zigzag varint
    0x0b: lambda d, o: (lambda v, p: (v[0], p))(*f32(d, o)),   # float
    0x0c: lambda d, o: (struct.unpack_from('<d', d, o)[0], o + 8),  # double
    0x13: lambda d, o: f32(d, o, 3),                        # Color3
    0x14: lambda d, o: (list(d[o:o + 3]), o + 3),           # Color3uint8
    0x15: lambda d, o: f32(d, o, 2),                        # Vector2
    0x16: lambda d, o: f32(d, o, 3),                        # Vector3
    0x1a: v_cframe,                                         # CFrame
    0x1c: v_ref,                                            # Instance ref
    0x2c: lambda d, o: (lambda v, p: (zz(v), p))(*uv(d, o)),   # int64, zigzag varint
    0x31: None,                                             # Name: set below (needs the schema name dictionary)
    0x34: lambda d, o: (d[o:o + 16].hex(), o + 16),         # UniqueId
    0x2e: lambda d, o: (('shared', d[o:o + 16].hex()), o + 16),   # SharedString (hash into the stage-1 table)
    0x3d: v_content,                                        # Content (new-style)
    0x32: v_ocframe,                                        # OptionalCFrame (WorldPivotData)
    0x0e: lambda d, o: ((struct.unpack_from('<fifi', d, o)), o + 16),  # UDim2: x.scale f32, x.offset i32, y...
    0x37: lambda d, o: (struct.unpack_from('<Q', d, o)[0], o + 8),   # SecurityCapabilities (u64)
    0x36: v_font,                                           # Font
    0x26: v_seq(5),                                         # ColorSequence: u32 n, n x (time, r, g, b, envelope)
    0x23: v_seq(3),                                         # NumberSequence: u32 n, n x (time, value, envelope)
    0x0d: lambda d, o: (struct.unpack_from('<fi', d, o), o + 8),     # UDim
    0x25: lambda d, o: f32(d, o, 2),                        # NumberRange
    0x29: v_physprops,                                      # PhysicalProperties
    0x12: lambda d, o: (struct.unpack_from('<H', d, o)[0], o + 2),  # BrickColor (u16 LE)
    0x19: lambda d, o: (struct.unpack_from('<3h', d, o), o + 6),     # Vector3int16
    0x3c: v_solidmesh,
    0x21: v_str,                                            # Content (old-style string)                                      # SolidMeshHolder
    0x22: lambda d, o: uv(d, o),                            # SystemAddress (NetworkOwnerV3): one byte seen (02)
}


def shared_strings(d, table):
    o = 0
    while o + 17 <= len(d):
        h = d[o:o + 16].hex()
        fmt = d[o + 16]
        n, o2 = uv(d, o + 17)
        table[h] = (fmt, d[o2:o2 + n])
        o = o2 + n
    return o == len(d)


def records(d, schema, out, stats, limit=None):
    ctx = {'last': None}
    try:
        return _records(d, schema, out, stats, ctx, limit)
    except (IndexError, struct.error) as e:
        raise Bad(f'{type(e).__name__} after {ctx.get("prev")} then {ctx["last"]}')
    except Bad as e:
        if str(e).startswith(('ref kind', 'record marker', 'content kind')):
            raise Bad(f'{e} after {ctx["last"]}')
        raise


def _records(d, schema, out, stats, ctx, limit=None):
    o = n = 0
    while o < len(d) and (limit is None or n < limit):
        n += 1
        if d[o] != 1:
            raise Bad(f'record marker {d[o]:#x} at {o}')
        iid, ci = struct.unpack_from('<IH', d, o + 1)
        o += 7
        cls = schema['classes'][ci]
        props = {}
        while d[o] != 0xff:
            pi = d[o]
            o += 1
            p = cls['props'][pi]
            fn = VALUE.get(p['type'])
            if fn is None:
                stats['stop'][(p['type'], cls['name'], p['name'])] += 1
                raise Bad(f"type {p['type']:#x} ({cls['name']}.{p['name']}) at {o}: {d[o:o + int(os.environ.get('TC_HEX', 24))].hex()}")
            o0 = o
            v, o = fn(d, o)
            ctx['prev'] = ctx.get('last')
            ctx['last'] = (cls['name'], p['name'], hex(p['type']), d[o0:o].hex()[:80], d[o:o + 40].hex())
            props[p['name']] = v
            if TRACE and stats['classes'][cls['name']] < 2 and cls['name'] in TRACE:
                print(f"  {cls['name']}.{p['name']} [{pi:#x} t{p['type']:#x}] {d[o0:o].hex()[:96]} -> {str(v)[:60]}")
        o += 1
        parent, o = v_ref(d, o)
        out[iid] = {'class': cls['name'], 'parent': parent[1] if parent else None, 'props': props}
        stats['classes'][cls['name']] += 1
    return o


def main():
    d = sys.argv[1]
    msgs = []
    for f in sorted(os.listdir(d)):
        if f.startswith('stream_'):
            msgs += split(open(os.path.join(d, f), 'rb').read())[1]
    schema = next(rtcio_schema.from_message(m) for m in msgs if m and m[0] == 0x97)
    VALUE[0x31] = v_name(schema['names'])
    ss, inst = {}, {}
    stats = {'classes': Counter(), 'stop': Counter(), 'chunks': Counter(), 'ok': Counter(), 'first': {}}
    # chunks are slices of one continuous stream per stage: records cross chunk boundaries
    streams = defaultdict(list)
    for m in msgs:
        if len(m) < 2 or m[0] != 0x83 or m[1] != 0x16:
            continue
        stage = m[2]
        clen, dlen = struct.unpack_from('<II', m, 3)
        streams[stage].append(zstd.decompress(m[11:11 + clen]))
        stats['chunks'][stage] += 1
    # item 0x0d: <u32 LE record count> <u32 LE clen> <u32 LE dlen> <zstd> <u8 04>; the payload is `count`
    # records as in the stage streams, then shared-string entries (post-join instance batches)
    for m in msgs:
        if len(m) < 2 or m[0] != 0x83 or m[1] != 0x0d:
            continue
        cnt, clen, dlen = struct.unpack_from('<III', m, 2)
        before = len(inst)
        stats['chunks']['0d'] += 1
        try:
            # `cnt` records, then this batch's shared strings
            dd = zstd.decompress(m[14:14 + clen])
            used = records(dd, schema, inst, stats, cnt)
            stats['ok']['0d'] += (len(inst) - before) == cnt and shared_strings(dd[used:], ss)
        except Bad as e:
            stats['first']['0d'] = str(e)
    for stage in sorted(streams, key=str):
        c = b''.join(streams[stage])
        try:
            if stage == 1:
                ok = shared_strings(c, ss)
            else:
                records(c, schema, inst, stats)
                ok = True
            stats['ok'][stage] += ok
        except Bad as e:
            stats['first'][stage] = str(e)
    for k, v in stats['first'].items():
        print('first stop:', v)
    print('chunks per stage:', dict(stats['chunks']), 'stage streams fully decoded:', dict(stats['ok']))
    print(f'shared strings: {len(ss)}; instances: {len(inst)}')
    print('top classes:', stats['classes'].most_common(12))
    print('stopped on (type, class, prop):', stats['stop'].most_common(12))
    if '--dump' in sys.argv:
        json.dump({str(k): v for k, v in inst.items()}, open(sys.argv[sys.argv.index('--dump') + 1], 'w'))
    if '--tree' in sys.argv:
        n = int(sys.argv[sys.argv.index('--tree') + 1])
        kids = defaultdict(list)
        for k, v in inst.items():
            kids[v['parent']].append(k)
        roots = [k for k, v in inst.items() if v['parent'] not in inst]
        shown = 0

        def walk(k, depth):
            nonlocal shown
            if shown >= n:
                return
            v = inst[k]
            print('  ' * depth + f"{v['class']} {v['props'].get('Name', '?')!r}")
            shown += 1
            for c in kids[k]:
                walk(c, depth + 1)
        for r in sorted(roots, key=lambda k: inst[k]['class']):
            walk(r, 0)


if __name__ == '__main__':
    main()
