"""Split decrypted rbx-rtcio streams (quic_decode.py OUTDIR) into messages and
summarise them. Prints structure only: per stream the channel header, message
count, the histogram of first bytes (Roblox packet ids) and sizes.

Stream layout [verified: capture]:
  06 01 <u8 channel> <4 bytes: u32 BE sequence, or ASCII "ctrl">
  then messages, each  <u32 BE: bit31 set | length> <length bytes>

usage: python3 -I rtcio_split.py OUTDIR [--dump SID IDX OUT]   (dump one message body to OUT)
"""
import os
import struct
import sys
from collections import Counter


def split(b):
    """-> (header, [messages], leftover bytes)."""
    hdr, o, msgs = b[:7], 7, []
    while o + 4 <= len(b):
        w = struct.unpack_from('>I', b, o)[0]
        n = w & 0x7fffffff
        if not w >> 31 or o + 4 + n > len(b):
            break
        msgs.append(b[o + 4:o + 4 + n])
        o += 4 + n
    return hdr, msgs, len(b) - o


if __name__ == '__main__':
    d = sys.argv[1]
    files = sorted((f for f in os.listdir(d) if f.startswith('stream_')), key=lambda f: int(f[7:-4]))
    if '--dump' in sys.argv:
        i = sys.argv.index('--dump')
        sid, idx, out = sys.argv[i + 1], int(sys.argv[i + 2]), sys.argv[i + 3]
        _, msgs, _ = split(open(os.path.join(d, f'stream_{sid}.bin'), 'rb').read())
        open(out, 'wb').write(msgs[idx])
        sys.exit(0)
    for f in files:
        b = open(os.path.join(d, f), 'rb').read()
        hdr, msgs, left = split(b)
        tag = hdr[3:7].decode() if hdr[3:7] == b'ctrl' else str(struct.unpack('>I', hdr[3:7])[0])
        ids = Counter(f'{m[0]:02x}' for m in msgs if m)
        print(f'{f}: hdr {hdr[:3].hex()} ch={hdr[2]} tag={tag} msgs={len(msgs)} '
              f'bytes={sum(map(len, msgs))} left={left} ids={dict(ids.most_common(12))}')
