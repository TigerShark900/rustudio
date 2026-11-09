"""Remove every saved Wine Credential Manager entry from a prefix's user.reg.

The capture Studio's prefix starts as a copy of the offline Studio's (it has WebView2),
which holds the offline Studio's fake local login. Studio must start signed out and sign in
through "Login via Browser", so the entries go. Prints only counts.

usage: python3 -I strip_creds.py PREFIX
"""
import re
import sys

reg_path = sys.argv[1].rstrip('/') + '/user.reg'
reg = open(reg_path, encoding='utf-8', errors='surrogateescape').read()
pat = re.compile(
    r'^\[Software\\\\Wine\\\\Credential Manager\\\\Generic: [^\]]+\][^\n]*\n(?:(?!\[)[^\n]*\n)*',
    re.M)
n = len(pat.findall(reg))
reg = pat.sub('', reg)
open(reg_path, 'w', encoding='utf-8', errors='surrogateescape').write(reg)
print(f'removed {n} saved credential entries')
