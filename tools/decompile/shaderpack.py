import struct, sys, os, collections
p, out = sys.argv[1], sys.argv[2]
d = open(p, 'rb').read()
names = []
i = 0x54
while True:
    n = d[i:i+64].split(b'\0')[0]
    if not n or not all(32 < c < 127 for c in n): break
    names.append(n.decode()); i += 0x44
first = d.find(b'#version') if b'#version' in d else None
# blob table: find by scanning for entries whose offset/size are sane, starting where the flag table ends
start = d.find(b'isVR\0') ; start = start + 64 - 1 + 0x0  # rough; refine below
for s in range(start - 80, start + 200):
    o, z = struct.unpack_from('<II', d, s + 16)
    if 0 < z < len(d) and o + z <= len(d) and d[s+28:s+29] in (b'p', b'v', b'c', b'g'):
        o2, z2 = struct.unpack_from('<II', d, s + 0x40 + 16)
        if 0 < z2 < len(d) and o2 + z2 <= len(d): start = s; break
cnt = collections.Counter(); k = start; n = 0
while True:
    o, z = struct.unpack_from('<II', d, k + 16)
    t = d[k+28:k+29]
    if not (0 < z < len(d) and o + z <= len(d)) or t not in (b'p', b'v', b'c', b'g'): break
    idx = struct.unpack_from('<H', d, k + 30)[0]
    nm = names[idx] if idx < len(names) else f'idx{idx}'
    cnt[nm] += 1
    open(os.path.join(out, f'{nm}.{cnt[nm]-1}.glsl'), 'wb').write(d[o:o+z])
    k += 0x40; n += 1
print(len(names), 'names', n, 'blobs')
