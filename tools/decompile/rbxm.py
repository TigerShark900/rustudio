"""Reads a binary .rbxm: decompresses chunks (LZ4 block or zstd via the CLI) and
returns {class: {prop: [values...]}} for string properties, plus instance names.

usage (module): rbxm.load(path) -> list of dicts {class, name, props{name: bytes}}
"""
import struct
import subprocess


def lz4_block(src, size):
    out = bytearray()
    i = 0
    while i < len(src):
        tok = src[i]
        i += 1
        lit = tok >> 4
        if lit == 15:
            while True:
                b = src[i]
                i += 1
                lit += b
                if b != 255:
                    break
        out += src[i:i + lit]
        i += lit
        if i >= len(src):
            break
        off = src[i] | (src[i + 1] << 8)
        i += 2
        ml = tok & 15
        if ml == 15:
            while True:
                b = src[i]
                i += 1
                ml += b
                if b != 255:
                    break
        ml += 4
        start = len(out) - off
        for k in range(ml):
            out.append(out[start + k])
    return bytes(out)


def chunks(data):
    assert data[:8] == b'<roblox!'
    o = 32
    while o < len(data):
        name = data[o:o + 4]
        clen, ulen, _ = struct.unpack_from('<III', data, o + 4)
        o += 16
        if clen == 0:
            body = data[o:o + ulen]
            o += ulen
        else:
            raw = data[o:o + clen]
            o += clen
            if raw[:4] == b'\x28\xb5\x2f\xfd':
                body = subprocess.run(['zstd', '-d', '-c', '-q'], input=raw, capture_output=True).stdout
            else:
                body = lz4_block(raw, ulen)
        yield name, body
        if name == b'END\0':
            break


def read_strings(body, o, n):
    out = []
    for _ in range(n):
        (ln,) = struct.unpack_from('<I', body, o)
        o += 4
        out.append(body[o:o + ln])
        o += ln
    return out, o


def load(path):
    data = open(path, 'rb').read()
    classes = {}
    inst_class = {}
    props = {}
    for name, body in chunks(data):
        if name == b'INST':
            cid, ln = struct.unpack_from('<II', body, 0)
            cname = body[8:8 + ln].decode()
            o = 8 + ln
            o += 1  # object format
            (count,) = struct.unpack_from('<I', body, o)
            o += 4
            raw = body[o:o + 4 * count]
            # interleaved, zigzag, delta-encoded int32 referents
            vals = []
            for k in range(count):
                b = bytes(raw[k + j * count] for j in range(4))
                v = int.from_bytes(b, 'big')
                v = (v >> 1) ^ -(v & 1)
                vals.append(v)
            acc = 0
            refs = []
            for v in vals:
                acc += v
                refs.append(acc)
            classes[cid] = (cname, refs)
            for r in refs:
                inst_class[r] = cname
        elif name == b'PROP':
            cid, ln = struct.unpack_from('<II', body, 0)
            pname = body[8:8 + ln].decode()
            o = 8 + ln
            ptype = body[o]
            o += 1
            if ptype == 0x01 and cid in classes:  # String / ProtectedString / BinaryString
                refs = classes[cid][1]
                vals, _ = read_strings(body, o, len(refs))
                for r, v in zip(refs, vals):
                    props.setdefault(r, {})[pname] = v
        elif name == b'PRNT':
            o = 1
            (count,) = struct.unpack_from('<I', body, o)
            o += 4

            def ints(o):
                raw = body[o:o + 4 * count]
                vals = []
                for k in range(count):
                    b = bytes(raw[k + j * count] for j in range(4))
                    v = int.from_bytes(b, 'big')
                    vals.append((v >> 1) ^ -(v & 1))
                acc, out = 0, []
                for v in vals:
                    acc += v
                    out.append(acc)
                return out

            kids = ints(o)
            parents = ints(o + 4 * count)
            for k, p in zip(kids, parents):
                props.setdefault(k, {})['__parent'] = p
    out = {}
    for r, cname in inst_class.items():
        p = props.get(r, {})
        out[r] = {'class': cname, 'name': p.get('Name', b'').decode('utf-8', 'replace'), 'props': p}
    return out


def full_name(objs, r):
    parts = []
    while r in objs:
        parts.append(objs[r]['name'])
        r = objs[r]['props'].get('__parent', -1)
    return '.'.join(reversed(parts))
