"""Small Luau bytecode disassembler (format of Luau's Bytecode.h; tolerant of
newer versions where the proto layout is unchanged).

usage: python3 -I ldis.py FILE.bin [FUNCTION_NAME ...]
"""
import struct
import sys

OPS = ("NOP BREAK LOADNIL LOADB LOADN LOADK MOVE GETGLOBAL SETGLOBAL GETUPVAL SETUPVAL CLOSEUPVALS GETIMPORT "
       "GETTABLE SETTABLE GETTABLEKS SETTABLEKS GETTABLEN SETTABLEN NEWCLOSURE NAMECALL CALL RETURN JUMP JUMPBACK "
       "JUMPIF JUMPIFNOT JUMPIFEQ JUMPIFLE JUMPIFLT JUMPIFNOTEQ JUMPIFNOTLE JUMPIFNOTLT ADD SUB MUL DIV MOD POW ADDK "
       "SUBK MULK DIVK MODK POWK AND OR ANDK ORK CONCAT NOT MINUS LENGTH NEWTABLE DUPTABLE SETLIST FORNPREP FORNLOOP "
       "FORGLOOP FORGPREP_INEXT FASTCALL3 FORGPREP_NEXT NATIVECALL GETVARARGS DUPCLOSURE PREPVARARGS LOADKX JUMPX "
       "FASTCALL COVERAGE CAPTURE SUBRK DIVRK FASTCALL1 FASTCALL2 FASTCALL2K FORGPREP JUMPXEQKNIL JUMPXEQKB "
       "JUMPXEQKN JUMPXEQKS IDIV IDIVK").split()
AUX = {"GETGLOBAL", "SETGLOBAL", "GETIMPORT", "GETTABLEKS", "SETTABLEKS", "NAMECALL", "JUMPIFEQ", "JUMPIFLE",
       "JUMPIFLT", "JUMPIFNOTEQ", "JUMPIFNOTLE", "JUMPIFNOTLT", "NEWTABLE", "SETLIST", "FORGLOOP", "LOADKX",
       "FASTCALL2", "FASTCALL2K", "FASTCALL3", "JUMPXEQKNIL", "JUMPXEQKB", "JUMPXEQKN", "JUMPXEQKS"}
FAST = {1: "assert", 2: "math.abs", 3: "math.acos", 4: "math.asin", 5: "math.atan2", 6: "math.atan", 7: "math.ceil",
        8: "math.cosh", 9: "math.cos", 10: "math.deg", 11: "math.exp", 12: "math.floor", 13: "math.fmod",
        14: "math.frexp", 15: "math.ldexp", 16: "math.log10", 17: "math.log", 18: "math.max", 19: "math.min",
        20: "math.modf", 21: "math.pow", 22: "math.rad", 23: "math.sinh", 24: "math.sin", 25: "math.sqrt",
        26: "math.tanh", 27: "math.tan", 46: "math.clamp", 47: "math.sign", 48: "math.round", 39: "type",
        42: "typeof", 54: "Vector3.new", 64: "vector.create"}


class R:
    def __init__(self, b):
        self.b, self.o = b, 0

    def u8(self):
        v = self.b[self.o]
        self.o += 1
        return v

    def u32(self):
        (v,) = struct.unpack_from('<I', self.b, self.o)
        self.o += 4
        return v

    def i32(self):
        (v,) = struct.unpack_from('<i', self.b, self.o)
        self.o += 4
        return v

    def f64(self):
        (v,) = struct.unpack_from('<d', self.b, self.o)
        self.o += 8
        return v

    def f32(self):
        (v,) = struct.unpack_from('<f', self.b, self.o)
        self.o += 4
        return v

    def var(self):
        r = s = 0
        while True:
            x = self.u8()
            r |= (x & 127) << s
            s += 7
            if not x & 128:
                return r


def load(b):
    r = R(b)
    ver = r.u8()
    tver = r.u8() if ver >= 4 else 0
    strings = [None]
    for _ in range(r.var()):
        ln = r.var()
        strings.append(b[r.o:r.o + ln].decode('utf-8', 'replace'))
        r.o += ln
    if tver == 3:
        while True:
            idx = r.u8()
            if idx == 0:
                break
            r.var()
    protos = []
    for _ in range(r.var()):
        p = {}
        p['maxstack'], p['params'], p['nups'], p['vararg'] = r.u8(), r.u8(), r.u8(), r.u8()
        if ver >= 4:
            p['flags'] = r.u8()
            ts = r.var()
            r.o += ts
        n = r.var()
        p['code'] = [r.u32() for _ in range(n)]
        ks = []
        for _ in range(r.var()):
            t = r.u8()
            if t == 0:
                ks.append(None)
            elif t == 1:
                ks.append(bool(r.u8()))
            elif t == 2:
                ks.append(r.f64())
            elif t == 3:
                ks.append(('s', strings[r.var()]))
            elif t == 4:
                ks.append(('import', r.u32()))
            elif t == 5:
                ks.append(('table', [r.var() for _ in range(r.var())]))
            elif t == 6:
                ks.append(('closure', r.var()))
            elif t == 7:
                ks.append(('vector', r.f32(), r.f32(), r.f32(), r.f32()))
            elif t == 8:
                n2 = r.var()
                ks.append(('tablek', [(r.var(), r.i32()) for _ in range(n2)]))
            elif t == 9:
                ks.append(('int', r.var()))
            else:
                raise ValueError(f'const type {t} at {r.o}')
        p['k'] = ks
        p['protos'] = [r.var() for _ in range(r.var())]
        p['line'] = r.var()
        p['name'] = strings[r.var()]
        if r.u8():
            gap = r.u8()
            n_int = ((len(p['code']) - 1) >> gap) + 1
            deltas = list(b[r.o:r.o + len(p['code'])])
            r.o += len(p['code'])
            abss = [r.i32() for _ in range(n_int)]
            lines, last = [], 0
            for i in range(len(p['code'])):
                last = (last + deltas[i]) & 255 if i & ((1 << gap) - 1) else deltas[i]
                if not i & ((1 << gap) - 1):
                    last = deltas[i]
                lines.append(abss[i >> gap] + (last if (last < 128) else last - 256))
            p['lines'] = lines
        if r.u8():
            p['locals'] = []
            for _ in range(r.var()):
                p['locals'].append((strings[r.var()], r.var(), r.var(), r.u8()))
            p['upvals'] = [strings[r.var()] for _ in range(r.var())]
        protos.append(p)
    main = r.var()
    return ver, strings, protos, main


def kstr(k):
    if isinstance(k, tuple):
        if k[0] == 's':
            return repr(k[1])
        return str(k)
    return repr(k)


def import_name(p, k):
    v = k[1]
    n = v >> 30
    ids = [(v >> 20) & 1023, (v >> 10) & 1023, v & 1023][:n]
    return '.'.join(p['k'][i][1] if isinstance(p['k'][i], tuple) else str(p['k'][i]) for i in ids)


def dis(p, protos):
    code = p['code']
    i = 0
    out = []
    while i < len(code):
        ins = code[i]
        op = ins & 255
        name = OPS[op] if op < len(OPS) else f'OP{op}'
        a, b, c = (ins >> 8) & 255, (ins >> 16) & 255, (ins >> 24) & 255
        d = ins >> 16
        if d >= 32768:
            d -= 65536
        e = ins >> 8
        if e >= 1 << 23:
            e -= 1 << 24
        aux = code[i + 1] if name in AUX and i + 1 < len(code) else None
        txt = f'{name} {a} {b} {c}'
        if name in ('LOADK',):
            txt = f'LOADK R{a} {kstr(p["k"][d])}'
        elif name == 'LOADN':
            txt = f'LOADN R{a} {d}'
        elif name == 'LOADB':
            txt = f'LOADB R{a} {b} +{c}'
        elif name == 'MOVE':
            txt = f'MOVE R{a} R{b}'
        elif name in ('GETTABLEKS', 'SETTABLEKS'):
            txt = f'{name} R{a} R{b} {kstr(p["k"][aux])}'
        elif name == 'NAMECALL':
            txt = f'NAMECALL R{a} R{b} :{kstr(p["k"][aux])}'
        elif name in ('GETGLOBAL', 'SETGLOBAL'):
            txt = f'{name} R{a} {kstr(p["k"][aux])}'
        elif name == 'GETIMPORT':
            txt = f'GETIMPORT R{a} {import_name(p, p["k"][d])}'
        elif name in ('GETUPVAL', 'SETUPVAL'):
            ups = p.get('upvals') or []
            txt = f'{name} R{a} U{b}' + (f' ({ups[b]})' if b < len(ups) else '')
        elif name in ('ADDK', 'SUBK', 'MULK', 'DIVK', 'MODK', 'POWK', 'IDIVK', 'ANDK', 'ORK'):
            txt = f'{name} R{a} R{b} {kstr(p["k"][c])}'
        elif name in ('SUBRK', 'DIVRK'):
            txt = f'{name} R{a} {kstr(p["k"][b])} R{c}'
        elif name in ('ADD', 'SUB', 'MUL', 'DIV', 'MOD', 'POW', 'IDIV', 'AND', 'OR', 'CONCAT'):
            txt = f'{name} R{a} R{b} R{c}'
        elif name in ('NOT', 'MINUS', 'LENGTH'):
            txt = f'{name} R{a} R{b}'
        elif name in ('JUMP', 'JUMPBACK', 'JUMPIF', 'JUMPIFNOT', 'FORNPREP', 'FORNLOOP', 'FORGPREP', 'FORGPREP_INEXT', 'FORGPREP_NEXT'):
            txt = f'{name} R{a} -> {i + 1 + d}'
        elif name in ('JUMPIFEQ', 'JUMPIFLE', 'JUMPIFLT', 'JUMPIFNOTEQ', 'JUMPIFNOTLE', 'JUMPIFNOTLT'):
            txt = f'{name} R{a} R{aux} -> {i + 1 + d}'
        elif name in ('JUMPXEQKNIL', 'JUMPXEQKB', 'JUMPXEQKN', 'JUMPXEQKS'):
            kk = kstr(p['k'][aux & 0xffffff]) if name in ('JUMPXEQKN', 'JUMPXEQKS') else (aux & 1)
            txt = f'{name} R{a} {kk} {"NOT " if aux >> 31 else ""}-> {i + 1 + d}'
        elif name == 'JUMPX':
            txt = f'JUMPX -> {i + 1 + e}'
        elif name in ('CALL',):
            txt = f'CALL R{a} args={b - 1 if b else "multi"} rets={c - 1 if c else "multi"}'
        elif name == 'RETURN':
            txt = f'RETURN R{a} n={b - 1 if b else "multi"}'
        elif name in ('NEWCLOSURE',):
            child = protos[p['protos'][d]]
            txt = f'NEWCLOSURE R{a} {child["name"]}'
        elif name == 'DUPCLOSURE':
            k = p['k'][d]
            txt = f'DUPCLOSURE R{a} {protos[k[1]]["name"] if isinstance(k, tuple) else k}'
        elif name in ('FASTCALL', 'FASTCALL1', 'FASTCALL2', 'FASTCALL2K', 'FASTCALL3'):
            txt = f'{name} {FAST.get(a, a)}'
        elif name == 'GETTABLEN':
            txt = f'GETTABLEN R{a} R{b}[{c + 1}]'
        elif name == 'GETTABLE':
            txt = f'GETTABLE R{a} R{b}[R{c}]'
        elif name == 'SETTABLE':
            txt = f'SETTABLE R{a} R{b}[R{c}]'
        elif name == 'CAPTURE':
            txt = f'CAPTURE {["VAL", "REF", "UPVAL"][a] if a < 3 else a} R{b}'
        ln = p.get('lines', [None] * len(code))[i]
        out.append(f'  {i:4d} L{ln}: {txt}')
        i += 2 if aux is not None else 1
    return out


if __name__ == '__main__':
    ver, strings, protos, main = load(open(sys.argv[1], 'rb').read())
    want = set(sys.argv[2:])
    for idx, p in enumerate(protos):
        if want and p['name'] not in want:
            continue
        print(f'function {p["name"]} (line {p["line"]}, params {p["params"]}, proto {idx})')
        if p.get('locals'):
            print('  locals:', ', '.join(f'{n}=R{reg}' for n, s, e, reg in p['locals']))
        print('\n'.join(dis(p, protos)))
