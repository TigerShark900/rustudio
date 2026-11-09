from pathlib import Path
import re,struct
p=Path(__file__).parent; root=p.parents[2]
# Preserve every NUL-terminated printable string in bridge neighborhood, plus global conversion/error matches.
d=Path.home().joinpath('.local/share/rustudio/studio/RobloxStudioBeta.exe').read_bytes();pe=struct.unpack_from('<I',d,60)[0];opt=pe+24; base=struct.unpack_from('<Q',d,opt+24)[0];sections=[]
for i in range(struct.unpack_from('<H',d,pe+6)[0]):
 o=opt+struct.unpack_from('<H',d,pe+20)[0]+40*i;vs,va,sz,raw=struct.unpack_from('<IIII',d,o+8);sections.append((raw,sz,va))
strings={}
for m in re.finditer(rb'[\x20-\x7e]{3,}\x00',d):
 a=next((base+va+m.start()-raw for raw,sz,va in sections if raw<=m.start()<raw+sz),0);s=m.group()[:-1].decode()
 if 0x1490eed00<=a<=0x1490f0800 or re.search(r'Unable to cast|Unable to assign property|Argument \d*%?d? missing|Expected \x27:\x27|invalid argument #|missing argument #',s):strings[a]=s
(p/'bridge-strings.txt').write_text('\n'.join(f'{a:#x}\t{s}' for a,s in strings.items())+'\n')
def parse(file):
 out={}
 for line in (p/file).read_text().splitlines():
  if 'BRIDGE|' not in line:continue
  x=line[line.index('BRIDGE|'):].split('|');side,key=x[1:3];value=' | '.join(x[3:]).split('  —  harness:')[0]
  out[side,key]=value
 return out
studio=parse('studio-extended.log');rc=parse('rustudio-client.log');rs=parse('rustudio-server.log');rust=rc|rs
keys=list(dict.fromkeys(k for side,k in studio))+[k for side,k in rust if k not in {k for side,k in studio}]
def category(k):
 if k.startswith('library.') or any(k.startswith(n+'.') for n in ['WaitForChild','Invoke','InvokeServer','InvokeClient','AddItem','GetMaxCollisionGroups']):return 6
 if k.startswith(('enum.','enums.','item.','GetEnumItems.','GetEnums.','FromName.','FromValue.','IsA.')):return 5
 if k.startswith(('GetService.','Destroy.','Connect.','Disconnect.')):return 3
 if k in ['unknown','wrongcase','propertycall','eventcall'] or '.unknown' in k or '.namecall' in k:return 2
 if any(x in k for x in ['.index.','.newindex.','.write.']) or k in ['readonly','wrongtype','name.table','parent.number']:return 4
 return 1
def esc(x):return x.replace('|','\\|').replace('\n','<br>')
def address(k):
 if 'readonly' in k:return '0x148a9a2a0'
 if k.startswith('GetService.') and any(s in k for s in ['noself','wrong']):return '0x1490f05e0'
 if 'missing' in k:return '0x148a9aa88'
 if k.startswith('library.') or k.endswith(('.noself','.wrongself','.wrongclass')):return '0x1490f05e0 (Instance family)'
 if k.startswith('enum.') or k.startswith('enums.'):return '0x1490eee50 / 0x1490eedf8'
 if k.startswith('item.'):return '0x1490eee88'
 if 'table' in k or 'nil' in k or 'empty' in k or '.self' in k:return '0x148f23328 / 0x148f23380 (format family)'
 if k in ['unknown','wrongcase','propertycall','eventcall'] or '.unknown' in k:return '0x1490f0640'
 return 'runtime capture; native address unresolved'
text='''# Luau ↔ Instance/Enum bridge research (2026-11-08)

Research only; no src changes. Reference PE SHA256 `81be5bc2916ba979e0ecc68b5fd039a48821765c6e9a7bcfd8d27ad877cf1692` (REA open_binary confirmed). Studio slot 2 was created hidden for this investigation and closed afterward. Measurements ran in `ServerScriptService.BridgeProbe` and `Players.Player.PlayerScripts.BridgeProbe` during Play, not the command bar. Command bar only installed scripts. `studio-extended.log` contains both script contexts. rustudio used the requested headless gamescope harness, no rebuild; `rustudio-{client,server}.log` and harness outputs capture both runs. `probe.luau` is the final corpus. `studio-play.log` preserves the earlier main pass including Destroy, removed from final corpus because calling Destroy(workspace) is unnecessarily disruptive (Studio refused it as locked).

Tables preserve pcall success flags, exact captured messages and debug metadata. Function pointers are process-local tostring observations, not executable addresses. Studio source/line prefixes are expected to differ by script location. Rustudio columns contain client then server. A native address names a literal or format family unless explicitly identified as a function; it is not proof every row executes that literal. Missing rows are marked unmeasured.

## Findings and implementation spec

1. Set Instance `__metatable` to `The metatable is locked` (currently false). Captured __index, __newindex, __namecall report `[C], -1, empty name, 0, true` for s/l/n/a (a includes isvararg). Each is shared across game, Part and Player within a VM; __namecall differs from __index. typeof Instance and tostring instance name match. Full raw-metatable enumeration remains unresolved: ordinary scripts cannot read the locked table. __tostring/__eq behavior does not expose their function objects, so this report does not invent metadata or absence for unobservable metamethods.

2. Add an Instance C __namecall that reads `lua_namecallatom` immediately on entry and saves/copies the method name before any protected nested call. Reuse cmeta's unnamed trampoline/error conversion, passing the saved name explicitly to a dispatcher (do not read the atom after entering Rust callbacks). A direct call of a captured namecall has the VM's last namecall atom, as the repeated unknown-member results show; its second argument is not the method name. Resolve callable method descriptors only; properties, events and unknown names all produce `%s is not a valid member of %s "%s"`. Preserve legacy casing only when Studio supports it; `getservice` is rejected. Enum/EnumItem/Enums/signal/connection colon errors instead captured the same function as __index: do not assume these need an independent __namecall.

3. Replace `rs_wrap` Lua method closures with named C closures (`lua_pushcclosurek` debugname = stable interned method name). Instance method functions are cached by descriptor per VM, independent of receiver. Current name cache is insufficient for identically named methods with unrelated owners; use descriptor identity unless cross-owner probes prove shared identity. `game.GetService == workspace.GetService` errors because Workspace has no GetService, so this expression establishes no equality. Test inherited methods such as Part.IsA against game.IsA before choosing a broader cache key. Validate self before conversions: absent/non-Instance/wrong-owner produces exactly `Expected ':' not '.' calling member function X`, without location. Enum and signal methods are fresh named C closures on every read, not Instance-style cached functions. Their bad self uses named standard Luau argument errors with source/line.

4. Keep engine semantic errors location-free; use the Lua caller location for argument checker/VM errors. Distinguish omitted arguments (`missing argument #N (...)`) from explicit nil (`invalid argument #N (... expected, got nil)`). Preserve the physical slot number for metamethods (key is #2; assigned value #3). Instance named method missing reflected argument is instead `Argument 1 missing or nil`. Avoid mlua's `bad argument #N: error converting Lua ...` leakage. Name assignment uses `Unable to assign property Name. string expected, got table`. Parent wrong type uses location plus `invalid argument #3 (Instance expected, got number)`. Anchored={} succeeds in both runtimes (truthiness conversion); do not impose strict boolean validation. GetService converts table/boolean/number to service-name strings (`'{}'`, `'true'`, `'3'`) before invalid-service rejection.

5. Implement Enums.GetEnums, Enum.FromName and FromValue. Missing lookup returns nil. Material contains 45 items in this build; first Plastic, Value 256. Enums.GetEnums returns 652 in this build. EnumItem Name/Value/EnumType are readable, writes even to those fields produce `X is not a valid member of EnumItem`. Unknown reads use quoted `Enum.Material.Plastic`. Global tostring(Enum) is `Enums`, not `Enum`; tostring(Enum.Material) is `Material`. Equality succeeds for repeated enum/item reads, unequal items compare false, ordering raises a VM error. See rows for full metadata and type checks.

6. Every successfully inspected Studio Instance method, including yieldable methods and library method counterparts, is a named C function with 0,true arity; rustudio exposes prelude/library source and actual Lua arity. Put yielding Lua implementations behind named C closures with an explicit continuation and `lua_pcall`/resume strategy that preserves yields; the existing plain cmeta trampoline is not itself proof of yield safety. Preserve self validation before scheduling. Prevent internal Lua frames from becoming the error raiser or source of parameter errors. WaitForChild currently reaches FindFirstChild before validating self; other Lua methods expose inconsistent error locations. The 137 candidate library receiver/method pairs below include unrelated same-name registrations and nonconstructible classes: failed construction is a coverage gap, not proof a method is absent. Full construction of AnimationTrack/Tween/abstract receivers and per-method argument conversion remain unresolved.

## Coverage limits

Items 2–5 have direct core-case measurements in all four contexts. Items 1 and 6 are partial: locked raw metatable inventory (__type/__eq/__tostring function metadata) and every nonconstructible library receiver remain unmeasured. Static literal extraction is exhaustive for the stated bridge address range and regex families across printable ASCII NUL strings, not proof of every possible conversion error in the entire executable. Dynamic format construction, UTF-16 and unrelated reflection-specific error branches are not exhaustively attributed. No claim of complete parity is made.

'''
for num,title in enumerate(['Instance metatable','Namecall dispatch','Method functions','Index/newindex errors','Enums and EnumItems','Lua implementation methods'],1):
 text+=f'## {num}. {title}\n\n| Probe | Studio server | Studio client | rustudio client / server | Evidence address |\n|---|---|---|---|---|\n'
 for k in keys:
  if category(k)!=num:continue
  vals=[k,studio.get(('server',k),'unmeasured'),studio.get(('client',k),'unmeasured'),rust.get(('client',k),'unmeasured')+' / '+rust.get(('server',k),'unmeasured'),address(k)]
  text+='| '+' | '.join(esc(v) for v in vals)+' |\n'
 text+='\n'
text+='''## Executable strings and static evidence

`bridge-strings.txt` includes every printable NUL string in VA 0x1490eed00–0x1490f0800 plus matching argument/cast/assignment families across the PE; `exe-strings.txt` is a broader initial candidate scan. These are literal evidence, not runtime attribution. Full bounded extraction follows.

| VA | Literal |
|---|---|
'''
for a,s in strings.items():text+=f'| {a:#x} | {esc(s)} |\n'
text+='''
Ghidra decompilation: `dc/0x143d6e420.c` is Enums index: resolves an enum name, otherwise recognizes GetEnums and creates a C function with debug name at 0x1490eede8; error uses 0x1490eedf8. `dc/0x143d74970.c` caches reflected method closures in a Lua table keyed by descriptor, constructs named C closures with descriptor upvalue (FUN_143d7a390 / FUN_143d7ab30), then stores the closure in the cache. This supports descriptor-based caching. `xrefs.txt` preserves string references. Decompiling an instruction inside a function can produce misleading tiny output; use the recovered function-start files, not the initial interior-address files. Static analysis does not establish runtime execution by itself.
'''
(root/'docs/RE-BRIDGE.md').write_text(text)
print(root/'docs/RE-BRIDGE.md',len(keys),'probes')
