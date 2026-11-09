"""Print the string table of Luau bytecode files (printable runs), one block per file.

Built-in Studio plugins ship as Luau bytecode; rbxm_src.py extracts them as
.bin. Their constant strings (URLs, JSON keys, flag names) are enough to read
endpoints and request bodies.

usage: python3 -I lstr.py [-n MIN] FILE...
"""
import re
import sys

args = sys.argv[1:]
n = 3
if args and args[0] == '-n':
    n = int(args[1])
    args = args[2:]
pat = re.compile(rb'[\x20-\x7e]{%d,}' % n)
for p in args:
    d = open(p, 'rb').read()
    print('=== ' + p.rsplit('/', 1)[-1])
    print(' | '.join(m.decode() for m in pat.findall(d)))
