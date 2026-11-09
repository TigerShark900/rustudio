#!/usr/bin/env python3
"""Read this Studio build's disconnect-message switch without executing Studio.

Addresses apply only to SHA-256 7005e4f9…; fail closed on another build.
Uses only Python's standard library. Does not read session credentials.
"""
import hashlib
import struct
import sys
from pathlib import Path

EXPECTED = '7005e4f922fa44034884e84ad03fef943672c2b0b2eca46df5cc154331e46297'


def main():
    data = Path(sys.argv[1]).read_bytes()
    if hashlib.sha256(data).hexdigest() != EXPECTED:
        raise SystemExit('Unsupported Studio build: disconnect switch addresses differ')
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    opt = pe + 24
    base = struct.unpack_from('<Q', data, opt + 24)[0]
    sections = opt + struct.unpack_from('<H', data, pe + 20)[0]

    def read(va, size):
        for i in range(struct.unpack_from('<H', data, pe + 6)[0]):
            _, rva, length, raw = struct.unpack_from('<IIII', data, sections + 40*i + 8)
            offset = va - base - rva
            if 0 <= offset and offset + size <= length:
                return data[raw + offset:raw + offset + size]
        raise ValueError(f'Unmapped address {va:#x}')

    print(f'Studio SHA-256 {EXPECTED}')
    print('Disconnect message switch 0x145fef0c0, jump table 0x145fef4f0')
    for code in range(0x102, 0x10a):
        target = base + struct.unpack('<I', read(0x145fef4f0 + (code-0x102)*4, 4))[0]
        block = read(target, 13)
        # mov r8d, length; lea rdx, [rip+disp32]
        assert block[:2] == b'\x41\xb8' and block[6:9] == b'\x48\x8d\x15'
        length = struct.unpack_from('<I', block, 2)[0]
        string = target + 13 + struct.unpack_from('<i', block, 9)[0]
        print(f'{code:#05x}: block {target:#x}, text {string:#x}: {read(string, length).decode().rstrip(chr(0))}')


if __name__ == '__main__':
    main()
