"""ldis.py with DUPTABLE templates decoded (keys, and values for constant tables).

usage: python3 -I ldisk.py FILE.bin [FUNCTION_NAME ...]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'decompile'))
import ldis  # noqa: E402


def kval(p, i):
    k = p['k'][i]
    if isinstance(k, tuple) and k[0] == 's':
        return repr(k[1])
    return repr(k)


def template(p, idx):
    k = p['k'][idx]
    if not isinstance(k, tuple):
        return repr(k)
    if k[0] == 'table':
        return '{' + ', '.join(kval(p, i) for i in k[1]) + '}'
    if k[0] == 'tablek':
        return '{' + ', '.join(f'{kval(p, a)}={kval(p, b) if b >= 0 else "nil"}' for a, b in k[1]) + '}'
    return repr(k)


ver, strings, protos, main = ldis.load(open(sys.argv[1], 'rb').read())
want = set(sys.argv[2:])
for idx, p in enumerate(protos):
    if want and p['name'] not in want:
        continue
    print(f'function {p["name"]} (line {p["line"]}, params {p["params"]}, proto {idx})')
    for line in ldis.dis(p, protos):
        parts = line.split()
        if len(parts) >= 4 and parts[2] == 'DUPTABLE':
            line += '  ' + template(p, int(parts[4]))
        print(line)
