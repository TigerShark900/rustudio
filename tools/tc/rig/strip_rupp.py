"""Strip Roblox's relay (RUPP/UDMUX-style) header from RbxTransport datagrams so
tshark sees plain QUIC.

Each datagram on PORT starts with [u8 version=1][u8 0][u16 BE header length]
followed by TLVs, then the QUIC packet. The header is dropped; everything else
is rewritten as raw IPv4/UDP (linktype 101) with the original addresses and
ports. Input: a pcap written by tcpdump (LINUX_SLL2, linktype 276). Prints
counts only: the header carries a relay token.

usage: python3 -I strip_rupp.py IN.pcap OUT.pcap PORT
"""
import struct
import sys

src, dst, port = sys.argv[1], sys.argv[2], int(sys.argv[3])
data = open(src, 'rb').read()
magic = data[:4]
endian = '<' if magic == b'\xd4\xc3\xb2\xa1' else '>'
linktype = struct.unpack_from(endian + 'I', data, 20)[0]
if linktype != 276:
    sys.exit(f'expected LINUX_SLL2 (276), got {linktype}')
out = [struct.pack('<IHHiIII', 0xa1b2c3d4, 2, 4, 0, 0, 262144, 101)]
off, n_in, n_out, bad = 24, 0, 0, 0
while off + 16 <= len(data):
    ts_s, ts_us, incl, orig = struct.unpack_from(endian + 'IIII', data, off)
    pkt = data[off + 16: off + 16 + incl]
    off += 16 + incl
    n_in += 1
    ip = pkt[20:]  # SLL2 header is 20 bytes
    if len(ip) < 28 or ip[0] >> 4 != 4 or ip[9] != 17:
        continue
    ihl = (ip[0] & 15) * 4
    sport, dport, ulen = struct.unpack_from('>HHH', ip, ihl)
    if port not in (sport, dport):
        continue
    payload = ip[ihl + 8: ihl + ulen]
    if len(payload) < 4 or payload[0] != 1:
        bad += 1
        continue
    hlen = struct.unpack_from('>H', payload, 2)[0]
    quic = payload[hlen:]
    udp = struct.pack('>HHHH', sport, dport, 8 + len(quic), 0) + quic
    iph = bytearray(ip[:20])
    iph[0] = 0x45
    struct.pack_into('>H', iph, 2, 20 + len(udp))
    struct.pack_into('>H', iph, 10, 0)
    s = sum(struct.unpack('>10H', bytes(iph)))
    while s >> 16:
        s = (s & 0xffff) + (s >> 16)
    struct.pack_into('>H', iph, 10, ~s & 0xffff)
    frame = bytes(iph) + udp
    out.append(struct.pack('<IIII', ts_s, ts_us, len(frame), len(frame)) + frame)
    n_out += 1
open(dst, 'wb').write(b''.join(out))
print(f'read {n_in} frames, wrote {n_out} QUIC datagrams on port {port}, {bad} without the header')
