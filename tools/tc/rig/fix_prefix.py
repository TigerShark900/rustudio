"""Make a copied an offline Studio prefix the capture Studio's own.

- "Local AppData" (Shell Folders and User Shell Folders) -> APPDATA_DIR, so
  Studio's logs, caches and settings stay in the capture home and never touch
  the offline Studio's appdata.
- Every [Software\\Roblox...] section is dropped (recent files, autosave
  records, ContentFolder pointing at the offline Studio's Studio), so Studio starts fresh.
Prints only counts.

usage: python3 -I fix_prefix.py PREFIX APPDATA_DIR
"""
import re
import sys

prefix, appdata = sys.argv[1].rstrip('/'), sys.argv[2].rstrip('/')
win = 'Z:' + appdata.replace('/', '\\\\')  # each \ is written \\ in .reg text
path = prefix + '/user.reg'
reg = open(path, encoding='utf-8', errors='surrogateescape').read()

reg, n_app = re.subn(r'^"Local AppData"=(?:str\(2\):)?"[^"\n]*"$',
                     lambda m: f'"Local AppData"="{win}"', reg, flags=re.M)
sec = re.compile(r'^\[Software\\\\Roblox[^\n]*\n(?:(?!\[)[^\n]*\n)*', re.M)
n_sec = len(sec.findall(reg))
reg = sec.sub('', reg)
open(path, 'w', encoding='utf-8', errors='surrogateescape').write(reg)
left = reg.count('offline-studio')
print(f'Local AppData repointed: {n_app}; Roblox sections dropped: {n_sec}; '
      f'remaining offline-studio mentions: {left}')
