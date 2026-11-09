"""Print the RbxTransport relay (RUPP) header of the first few datagrams per
direction, correlated with the QUIC connection ids, to pin the header layout.

usage: python3 -I rupp_parse.py STRIPPED_OR_RAW.pcap CLIENT_IP PORT
(works on a tcpdump LINUX_SLL2 capture; the relay header is cleartext.)
"""
import struct
import sys

data = open(sys.argv[1], 'rb').read()
cip = bytes(int(x) for x in sys.argv[2].split('.'))
port = int(sys.argv[3])
endian = '<' if data[:4] == b'\xd4\xc3\xb2\xa1' else '>'
linktype = struct.unpack_from(endian + 'I', data, 20)[0]
sll = 20 if linktype == 276 else (16 if linktype == 113 else 0)
off, seen = 24, {'c': 0, 's': 0}
while off + 16 <= len(data) and (seen['c'] < 4 or seen['s'] < 4):
    incl = struct.unpack_from(endian + 'I', data, off + 8)[0]
    frame = data[off + 16: off + 16 + incl]
    off += 16 + incl
    ip = frame[sll:] if linktype in (276, 113) else frame
    if len(ip) < 29 or ip[0] >> 4 != 4 or ip[9] != 17:
        continue
    ihl = (ip[0] & 15) * 4
    sp, dp, ul = struct.unpack_from('>HHH', ip, ihl)
    if port not in (sp, dp):
        continue
    pl = ip[ihl + 8: ihl + ul]
    if len(pl) < 4 or pl[0] != 1:
        continue
    hl = struct.unpack_from('>H', pl, 2)[0]
    hdr, quic = pl[:hl], pl[hl:]
    d = 'c' if ip[12:16] == cip else 's'
    if quic and quic[0] & 0x80:
        dl = quic[5]
        dcid = quic[6:6 + dl]
        sl = quic[6 + dl]
        scid = quic[7 + dl:7 + dl + sl]
        q = f'LONG v={quic[1:5].hex()} dcid={dcid.hex()} scid={scid.hex()}'
    else:
        q = f'SHORT dcid?20={quic[1:21].hex()}'
    if seen[d] < 4:
        print(f'{"C->S" if d=="c" else "S->C"} hdr[{hl}]={hdr.hex()} | {q}')
        seen[d] += 1
