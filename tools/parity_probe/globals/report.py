import json,re
from pathlib import Path
p=Path(__file__).parent
for name in ['studio','studio-final','studio-complete','studio-extra']:
 f=p/(name+'.json')
 if f.exists(): (p/(name+'.log')).write_text('\n'.join(x.get('text','') for x in json.loads(f.read_text())['content']))
data={};loc={}
files=['studio.log','studio-final.log','studio-complete.log','rustudio-client-final.log','rustudio-server-final.log','rustudio-extra-client.log','rustudio-extra-server.log']
for fn in files:
 for n,l in enumerate((p/fn).read_text().splitlines(),1):
  m=re.search(r'GLOBALS\|(server|client)\|([^|]+)\|(.*)',l)
  if not m:continue
  side,key,val=m.groups();val=val.split('  —  ')[0];target=('Studio ' if fn.startswith('studio') else 'rustudio ')+side
  data.setdefault(key,{})[target]=val;loc.setdefault(key,{})[target]=f'{fn}:{n}'
# Candidate tables omit nil entries by Luau table semantics. A missing candidate
# in a completed inventory pass is an observed nil lookup, not an unrun probe.
visible=[k for k in data if k.startswith('inventory.visible.')]
for k in visible:
 for target in ['Studio server','Studio client','rustudio server','rustudio client']:
  if target not in data[k]:
   data[k][target]='nil (candidate lookup; omitted from table)'
   loc[k][target]='probe.luau:14-15; completed inventory'
def esc(s):return s.replace('|','\\|').replace('\n','<br>')
def table(keys):
 out=['| Probe | Studio server | Studio client | rustudio (server / client) | Evidence |','|---|---|---|---|---|']
 for k in keys:
  d=data[k];ev='; '.join(v for t,v in loc[k].items())
  out.append('| '+ ' | '.join(esc(x) for x in [k,d.get('Studio server','unmeasured'),d.get('Studio client','unmeasured'),d.get('rustudio server','unmeasured')+' / '+d.get('rustudio client','unmeasured'),ev])+' |')
 return '\n'.join(out)
text='''# Global environment and standard library parity (2026-11-08)

Research only. No src changes. Evidence files and runnable probes are in `tools/parity_probe/globals/`; table evidence is relative to that directory. Studio reported **0.744.0.7441077**, rather than assuming the version from sibling research. Private hidden Studio slot 1, pid 2852, was created from demo.rbxlx and closed without saving. All behavioral measurements ran as game Scripts under ServerScriptService and LocalScripts under PlayerScripts. Command-bar code only installed scripts. Two scripts on each side test identity using shared. Rustudio used the installed `rustudio` binary with the requested headless gamescope command, script-creating harness chunks at 3 s and capture after 6 s. Source checkout and installed binary can differ; runtime tables describe the installed binary. Other agents' source changes were neither staged nor reverted.

`true` / `false` at the start of protected probe rows is the pcall result. Inventory function rows contain pcall, type, typeof, source, line, name, arity, vararg, tostring. Ordinary inventory rows contain type, typeof, tostring. Escaped `\\n` preserves traceback newlines. Dynamic addresses, memory use and timing values are samples, not constants. Initial passes stopped in rustudio when non-UTF8 charpattern reached its output converter, and when setfenv(print,{}) succeeded on the Lua print wrapper and broke its subsequent debug lookup. Final probes escape bytes and use math.abs for the native setfenv check; initial evidence is retained separately. Some rustudio launch logs report a previous process SIGILL; the final behavioral runs reached DONE/EXTRA_DONE, which is the coverage criterion, not a clean shutdown claim.

## 1. Environment inventory and identities

**Boundary:** pairs(getfenv()) in Studio exposes exactly `_G`, `shared`, `script` in these scripts; getmetatable(getfenv()) returns `The metatable is locked`. A game script therefore cannot enumerate its hidden __index chain. The visible inventory below is a bounded candidate lookup against every key enumerated in rustudio plus explicit Roblox candidates in candidates.txt, not proof of a complete hidden Studio inventory. Rustudio exposes two unlocked __index levels. Full enumeration of that reference hidden chain remains unresolved; do not implement a fictional list from absence in pairs.

Identity true for an absent candidate means nil == nil, not shared function identity. Consult visible inventory to establish presence first. Studio require is shared between scripts; rustudio binds a different Lua require closure per script. `_G` and shared are shared per side but distinct from one another. Script differs per script. The two sides are separate VMs; pointer differences do not measure cross-VM object equality.

'''
text+=table(sorted(k for k in data if k.startswith(('inventory.env','inventory.visible','meta.env','metakey.env','identity.'))))
text+='\n\n### Internal globals visible to game scripts\n\nEvery row below was enumerated through rustudio’s exposed environment chain. Nil candidate lookups are inferred from omission after table assignment, which removes nil keys; this is evidence of nil lookup for those explicit candidates only. Yes means ordinary script lookup succeeds; all corresponding tested Studio lookups were absent unless shown in the main table.\n\n| Name | Server visible | Client visible |\n|---|---|---|\n'
for k in sorted(k for k in data if k.startswith('inventory.visible.__')):
 d=data[k];text+='| '+k.removeprefix('inventory.visible.')+' | '+('yes' if 'rustudio server' in d else 'unmeasured')+' | '+('yes' if 'rustudio client' in d else 'unmeasured')+' |\n'
sections=[('2. tostring',('tostring.',)),('3. Garbage collection',('gc.',)),('4. Output, errors and debug',('error.','assert.','xpcall.','trace.','debug.')),('5. Environments, compilation and require',('getfenv.','setfenv.','safeenv.','loadstring','require.')),('6. Coroutines and scheduling',('coroutine.','task.','spawn','delay','wait')),('7. Miscellaneous globals and library inventory',('misc.','string.','rawlen.','rawequal.','newproxy.','freeze','os','random.','shared.','script.','clock.'))]
notes={2:'''Studio prints 16 lowercase hex digits for address-bearing objects, stable across repeated tostring of the same live object. Same native library function stays identical across sibling scripts; sampled server/client representations differ. Rustudio prints zero-padded native-looking Linux pointer values (0x00005...). Instance tostring is its name in both. Buffer addresses repeated between two fresh allocations in Studio, so these strings are not globally unique lifetime identifiers. The exact scrambling transform, key lifetime and per-process versus per-VM salt are unresolved; no cryptographic or algebraic scheme is inferred from samples.''',3:'''Studio count and gcinfo return equal integer-valued numbers in this pass, despite allocations between calls; do not promise equality across arbitrary intervening GC/allocation. Rustudio gcinfo is integer-valued but count includes fractional KiB. Studio rejects all tested non-count options with the same exact instruction, while rustudio permits collect/stop/restart/step/isrunning and accepts no argument. Match the restrictive API before matching memory totals.''',4:'''print and warn metadata are in the library table below: native [C] in Studio, Lua prelude in rustudio. error/assert come from Luau. Levels 2/10 in the main error probe encounter protected C frames and lose position; the extra Lua caller probe disambiguates level 2. Non-string table errors preserve identity; displayed addresses do not imply conversion of the raised value. Traceback samples omit a Lua 5.x “stack traceback:” header in Studio. Debug absence rows explicitly test forbidden desktop-Lua debug APIs.''',5:'''Reference loadstring was unavailable on both sides. Attempting to enable ServerScriptService.LoadStringEnabled through the private Studio command bar failed: `LoadStringEnabled is not a valid member of ServerScriptService "ServerScriptService"`. Thus true-enabled Studio chunk naming and syntax-return behavior are **unresolved**, not inferred from rustudio. Rustudio permits compilation on the client and returns nil script / `(loadstring)` for default source; named source is `[string "chosen"]`. Its syntax failure raises instead of the usual nil/error pair. Numeric server require can wait on offline asset resolution; rows without an eventual message are unmeasured. Module tests distinguish direct recursion, missing returns, extra returns and module-context environments. Safeenv is not directly introspectable: the import mutation probe only observes that getfenv invalidates cached builtin assumptions.''',6:'''Game scripts are scheduled coroutines: running returns a thread, isyieldable true in ordinary code and pcall, false in the __index metamethod. This does not measure the host VM main thread, which game scripts cannot enter. Task spawn/defer/delay return threads in Studio; legacy spawn/delay return no values. task.wait resumes on scheduler frames: values are measured elapsed times, not proof of a fixed universal minimum. wait returns elapsed and game time. Running cancellation errors in Studio but succeeds in rustudio. Native coroutine.close behavior is tabulated.''',7:'''Library inventory includes every enumerable key of coroutine/task/debug/os/math/string/table/utf8/buffer/bit32, with metadata. Seed 123 reproduces the same three random values and reset sequence on both sides in these samples. os.clock measures process wall-time progress, time is game simulation time, elapsedTime includes Studio process lifetime; rustudio aliases elapsedTime to game time. Studio tick is local-time epoch-like and differs from os.time by 28800 seconds in this timezone; rustudio tick uses Unix epoch. Studio string metatable is locked. stats/UserSettings return Instances in Studio and tables in rustudio. Permissions overlap is recorded only as global-call outcomes; capability propagation belongs to docs/RE-SECURITY.md. Datatype internals belong to docs/RE-DATATYPES.md.'''}
for i,(title,prefixes) in enumerate(sections,2):
 text+='\n\n## '+title+'\n\n'+notes[i]+'\n\n'
 keys=[k for k in data if k.startswith(prefixes)]
 if i==7:keys += [k for k in data if k.startswith('inventory.') and not k.startswith(('inventory.env','inventory.visible'))]
 text+=table(sorted(set(keys)))
text+='''

## Prioritized implementation spec

1. **Hide implementation globals and lock environments.** Put engine helpers in registry/private upvalues; expose only measured public lookups. Set environment and string metatable protection to the exact Studio sentinel. Preserve per-script script and per-side shared/_G; use a shared native require entry point with caller context held privately. Exposed __rs_*, __ac_*, __ws_* names and Lua source names are immediate anti-cheat fingerprints. The table above lists each measured helper individually.
2. **Native output and global wrappers.** Make print/warn/require/version true C entries and supply task entries with Studio's observed names, [C], -1, 0/vararg metadata. cmeta.rs demonstrates raising stable strings in a C frame; its unnamed wrapper alone does not supply the native debug names measured here. Keep error/assert protected-call payload and traceback semantics from Luau; do not stringify arbitrary table/userdata errors.
3. **Restrict GC and compilation.** Only allow collectgarbage('count'), matching exact missing/invalid-argument and forbidden-option strings. Return integer-valued memory count consistently with gcinfo. Disable loadstring in normal script contexts by default and on clients; gate a server-enabled path only after measuring a reference build that exposes the flag. Preserve nil/error syntax returns where subsequently measured, not inferred.
4. **Match require failures and scheduler returns.** Return position-free invalid argument and client asset-id errors as measured, including the surprising false -> assetId 0 conversion. Preserve direct recursive-require text separately from module wrapper failure and wrong return count. task.cancel(current) must raise `cannot cancel thread`; legacy spawn/delay return nothing, task APIs return threads. Correct traceback/source-prefix differences rather than inserting synthetic Lua frames.
5. **Close cheap miscellaneous fingerprints.** Implement Version alias, match version string to target compatibility version, expose DebuggerManager/PluginManager with measured refusal instead of nil, and return actual Stats/GlobalBasicSettings Instances. Separate elapsedTime/process clock from simulation time, and match tick's local offset. Keep library key sets/frozen state and string protection consistent with the captured tables.
6. **Scramble printable object addresses.** Provide stable 64-bit, 16-digit lowercase display identities for live address-bearing objects without exposing raw host pointers. Exact Studio transform is still unknown, so this is a format/relationship target pending binary recovery, not a claim of bit-for-bit reconstruction. Preserve custom/Instance tostring behavior.

## Coverage limits

All seven areas have server and client measurements and rustudio comparisons. Full hidden Studio global enumeration is blocked by its locked metatable; enabled-loadstring behavior is blocked by the missing property in this an offline Studio build; offline numeric server require responses and the exact address transform remain unresolved. Main-thread behavior is outside reachable game-script context. These are partial areas, not completed exact parity claims. No implementation changes were made.
'''
(p.parent.parent.parent/'docs/RE-GLOBALS.md').write_text(text)
print('rows',len(data),'report bytes',len(text))
