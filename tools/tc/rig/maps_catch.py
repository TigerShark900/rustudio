"""Keep the newest /proc/<pid>/maps of every process of this rig whose cmdline
contains NEEDLE, until SECONDS pass, then resolve ADDRs found in a Wine trace
file against the last snapshot of the process with that Wine thread prefix.

usage: python3 -I maps_catch.py NEEDLE SECONDS OUTDIR
Writes OUTDIR/<pid>.maps. Pair with resolve: python3 -I maps_catch.py --resolve OUTDIR ADDR
"""
import os
import sys
import time

if sys.argv[1] == '--resolve':
    outdir, addr = sys.argv[2], int(sys.argv[3], 16)
    for f in sorted(os.listdir(outdir)):
        for line in open(os.path.join(outdir, f)):
            rng, perms, off, dev, inode, *path = line.split()
            lo, hi = (int(x, 16) for x in rng.split('-'))
            if lo <= addr < hi:
                print(f, hex(addr), (path or ['?'])[0], 'offset', hex(addr - lo + int(off, 16)), perms)
    sys.exit()

needle, secs, outdir = sys.argv[1], float(sys.argv[2]), sys.argv[3]
prefix = os.path.expanduser('~/.cache/rustudio-dev/tc/prefix')
os.makedirs(outdir, exist_ok=True)
end = time.time() + secs
while time.time() < end:
    for pid in os.listdir('/proc'):
        if not pid.isdigit():
            continue
        try:
            if needle not in open(f'/proc/{pid}/cmdline', 'rb').read().decode(errors='replace'):
                continue
            env = open(f'/proc/{pid}/environ', 'rb').read().split(b'\0')
            if f'WINEPREFIX={prefix}'.encode() not in env:
                continue
            data = open(f'/proc/{pid}/maps').read()
            open(os.path.join(outdir, pid + '.maps'), 'w').write(data)
        except OSError:
            pass
    time.sleep(0.02)
