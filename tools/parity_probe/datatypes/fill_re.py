"""Fill docs/RE-DATATYPES.md rustudio cells marked `unmeasured` from a run.sh
OUTDIR (only those cells; everything else is left as researched)."""
import re,sys
from pathlib import Path
p=Path(__file__).parent; re_md=p.parents[2]/'docs/RE-DATATYPES.md'
sys.argv=[sys.argv[0],sys.argv[1]]
src=open(p/'compare.py').read().split('st=parse(')[0]
exec(src)
ru=parse([Path(sys.argv[1])/f for f in ('client.log','server.log','extras.log','actor.log')])
def esc(s):return s.replace('|',' \\| ').replace('<','&lt;').replace('>','&gt;')
def cell(k,old):
    a=ru.get(('client',k)); b=ru.get(('server',k))
    if a is None and b is None: return None
    a=a if a is not None else 'unmeasured'; b=b if b is not None else 'unmeasured'
    return esc(a if a==b else 'client: '+a+' / server: '+b)
out=[];cur=None;filled=0
for l in re_md.read_text().split('\n'):
    if l.startswith('## '): cur=l[3:].strip()
    m=re.match(r'^\| (\S+) \| (.*) \| (unmeasured|client: .*unmeasured.*) \|$',l)
    if cur and m and cur not in ('Message replacement inventory',):
        new=cell(cur+'.'+m.group(1),m.group(3))
        if new and new!=m.group(3):
            l=f'| {m.group(1)} | {m.group(2)} | {new} |'; filled+=1
    out.append(l)
re_md.write_text('\n'.join(out)); print('filled',filled)
