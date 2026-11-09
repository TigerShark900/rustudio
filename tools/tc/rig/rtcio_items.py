"""Walk the 0x83 (ID_DATA) items of a decrypted rbx-rtcio capture and decode
the incremental replication items (research decoder). Prints structure and a
few decoded examples per item type; no secrets are involved, but the output
carries place data, so keep it local.

Item layouts [verified: capture]:
  02 new instance   <ref> <u16 LE class> ff { <u8 prop> <value> }* ff <parent ref>
  03 prop change    <ref> <u16 LE global prop index> <u8 version?> <value>
  07 event          <ref> <u16 LE global event index> <args, typed by the schema event>
  10 batch          <u32 LE count> <count items>
  13 (ref, ref)     <ref> <ref>
  16 initial chunk  <u8 stage> <u32 clen> <u32 dlen> <zstd> [<u32 LE> <u8> if stage != 1]
  0d instance batch <u32 count> <u32 clen> <u32 dlen> <zstd> <u8 04>
  23                <u32 LE>
  05 / 06           ping / ping-back (opaque, alone in their message)
  00 end of message
Global indices count through the schema's classes in order (props / events).
A ref is `01 <u32 LE id>` (`00` = nil).

usage: python3 -I rtcio_items.py OUTDIR [STREAM_ID] [--show N] [--schema SERVER_STREAM.bin]
  (the client direction carries no 0x97 schema: pass the server stream that does)
"""
import os
import struct
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rtcio_instances as ri  # noqa: E402
import rtcio_schema  # noqa: E402
from rtcio_split import split  # noqa: E402


class Items:
    def __init__(self, schema):
        self.s = schema
        self.props = [(c['name'], p) for c in schema['classes'] for p in c['props']]
        self.events = [(c['name'], e) for c in schema['classes'] for e in c['events']]
        ri.VALUE[0x31] = ri.v_name(schema['names'])

    def value(self, t, d, o):
        fn = ri.VALUE.get(t)
        if fn is None:
            raise ri.Bad(f'value type {t:#x}')
        return fn(d, o)

    def item(self, d, o):
        k = d[o]
        o += 1
        if k == 0x02:
            ref, o = ri.v_ref(d, o)
            ci = struct.unpack_from('<H', d, o)[0]
            o += 2
            if d[o] != 0xff:
                raise ri.Bad(f'new-instance byte {d[o]:#x}')
            o += 1
            cls = self.s['classes'][ci]
            props = {}
            while d[o] != 0xff:
                p = cls['props'][d[o]]
                v, o = self.value(p['type'], d, o + 1)
                props[p['name']] = v
            parent, o = ri.v_ref(d, o + 1)
            return ('new', ref, cls['name'], props, parent), o
        if k == 0x03:
            ref, o = ri.v_ref(d, o)
            gi = struct.unpack_from('<H', d, o)[0]
            cn, p = self.props[gi]
            ver = d[o + 2]
            v, o = self.value(p['type'], d, o + 3)
            return ('prop', ref, f"{cn}.{p['name']}", ver, v), o
        if k == 0x07:
            ref, o = ri.v_ref(d, o)
            gi = struct.unpack_from('<H', d, o)[0]
            o += 2
            cn, e = self.events[gi]
            args = []
            for a in e['args']:
                v, o = self.value(int(a[:2], 16), d, o)
                args.append(v)
            return ('event', ref, f"{cn}.{e['name']}", args), o
        if k == 0x10:
            n = struct.unpack_from('<I', d, o)[0]
            o += 4
            sub = []
            for _ in range(n):
                it, o = self.item(d, o)
                sub.append(it)
            return ('batch', n, sub), o
        if k == 0x13:
            a, o = ri.v_ref(d, o)
            b, o = ri.v_ref(d, o)
            return ('pair13', a, b), o
        if k == 0x16:
            clen = struct.unpack_from('<I', d, o + 1)[0]
            # trailer: stages 2-4 a u32 LE (record count of the chunk?) then u8; stage 1 none
            return ('chunk16', d[o]), o + 9 + clen + (0 if d[o] == 1 else 5)
        if k == 0x0d:
            cnt, clen = struct.unpack_from('<II', d, o)
            return ('batch0d', cnt), o + 12 + clen + 1   # + u8 (04 seen)
        if k == 0x23:
            return ('x23', struct.unpack_from('<I', d, o)[0]), o + 4
        if k in (0x05, 0x06):
            # ping / ping-back: opaque here, always the only item of its message
            return ('ping' if k == 5 else 'pingback', len(d) - o - 1), len(d) - 1
        raise ri.Bad(f'item {k:#x}')

    def message(self, m):
        o, out = 1, []
        while o < len(m) and m[o] != 0:
            it, o = self.item(m, o)
            out.append(it)
        if o != len(m) - 1:
            raise ri.Bad(f'trailing {len(m) - o} bytes')
        return out


def main():
    d = sys.argv[1]
    want = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else None
    show = int(sys.argv[sys.argv.index('--show') + 1]) if '--show' in sys.argv else 3
    allm = {}
    for f in sorted(os.listdir(d)):
        if f.startswith('stream_'):
            allm[f[7:-4]] = split(open(os.path.join(d, f), 'rb').read())[1]
    schema = None
    for ms in allm.values():
        for m in ms:
            if m and m[0] == 0x97:
                schema = rtcio_schema.from_message(m)
    if schema is None:
        schema = rtcio_schema.from_message(next(m for m in split(open(sys.argv[sys.argv.index('--schema') + 1], 'rb').read())[1] if m[0] == 0x97))
    it = Items(schema)
    ok, bad, kinds, shown = 0, Counter(), Counter(), Counter()
    for sid, ms in allm.items():
        if want and sid != want:
            continue
        for m in ms:
            if not m or m[0] != 0x83:
                continue
            try:
                for x in it.message(m):
                    kinds[x[0]] += 1
                    if x[0] in ('new', 'prop', 'event', 'batch', 'pair13') and shown[x[0]] < show:
                        shown[x[0]] += 1
                        print(f'stream {sid}:', str(x)[:220])
                ok += 1
            except (ri.Bad, IndexError, struct.error) as e:
                bad[str(e)[:60]] += 1
    print(f'0x83 messages decoded completely: {ok}; failed: {sum(bad.values())} {dict(bad.most_common(6))}')
    print('items:', dict(kinds))


if __name__ == '__main__':
    main()
