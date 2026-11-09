from pathlib import Path
import re
p=Path(__file__).parent
names=re.findall(r'^\{"(\w+)",function', (p/'probe.luau').read_text(),re.M)
def parse(files):
 d={}
 for file in files:
  if not (p/file).exists():continue
  for l in (p/file).read_text().splitlines():
   if 'DT|' not in l: continue
   x=l[l.index('DT|'):].split('|',3)
   if len(x)<4:continue
   side,k,v=x[1:];v=v.split('  —  ')[0].replace('\\r','');d[side,k]=v
 return d
st=parse(['studio.log']);ru=parse(['rustudio-client.log','rustudio-server.log','rustudio-extras.log','rustudio-actor.log'])
def esc(s):return s.replace('|',' \\| ').replace('<','&lt;').replace('>','&gt;')
def cell(d,k):
 a=d.get(('client',k),'unmeasured'); b=d.get(('server',k),'unmeasured')
 return esc(a if a==b else 'client: '+a+' / server: '+b)
text='''# Roblox datatypes and signals: script parity research (2026-11-08)

Research only. No src changes. Probe sources and raw evidence: `tools/parity_probe/datatypes/`. Reference executable SHA256 `81be5bc2916ba979e0ecc68b5fd039a48821765c6e9a7bcfd8d27ad877cf1692` (REA open_binary confirmed). Own hidden Studio slot 2, PID 1304; original start-page PID 1344 was closed and replaced with a demo-place instance. Other Studios were untouched. Measurements run in actual Script/LocalScript children during Play. `studio.log` preserves lines from this instance's C71FE log. Rustudio uses the requested headless gamescope harness and installed release binary, no rebuild. Existing unrelated worktree changes were preserved.

## Reading the evidence

Each row preserves success flag, and on failure the **type of error**, then its text. `create` returns type, typeof, tostring, getmetatable. `values` returns equality, rawequal between independent constructions, table lookup using the other construction, equality with Color3, rawequal with itself. Mutable state objects are independent, so false equality is not evidence of a defect. Signals are fetched twice from the same Part; connections are separately connected. RaycastResult is made by raycasting an anchored test Part. Hashes/pointers are process dependent. Numeric text and trailing spaces are preserved in raw logs.

`*.info` is debug.info s/l/n/a (arity then vararg). A captured function is the **raiser**, not necessarily a metamethod: Lua-source rows for unsupported arithmetic/comparison/length/concat identify the probe's own operation closure. Do not implement those as Lua metamethods just because a function was captured. Successful operations cannot expose a hidden metamethod this way. Studio locks the raw metatable; exhaustive __eq/__tostring function metadata is therefore unobservable from normal scripts. `index.namecall.same` distinguishes the captured read and colon-error raisers.

The full corpus crashed rustudio with SIGILL in `lua_gc` called by `mlua::userdata::util::lua_error_impl` during direct calls of captured functions (see `crash.txt`). The safe corpus removes only direct captured-function calls; both sides complete DONE. Studio ran the full corpus. Rustudio direct-call cells are explicitly unmeasured after this crash, not assumed to return Studio's errors. The crash is not yet minimized to one type/call. Supplemental constructor/known-field measurements ran on rustudio client; corresponding server cells remain unmeasured. No exhaustive overload or all-method survey is claimed. `crash-minimal.luau` ruled out the single Vector3 add raiser called with no arguments: it fails normally (minimal.log), so the full crash still needs isolation. Supplemental Studio rows and rustudio extras are client-only; primary corpus covers both sides. REA search_strings timed out after 300 seconds; mapped PE byte extraction supplied the format strings instead. Both owned Studio instances were closed without saving.

## Implementation specification

1. Vector3 must become Luau's native vector value (type `vector`, typeof `Vector3`). Current LVector3 is userdata. Updating only typeof is insufficient: Studio equal vectors are rawequal and interchangeable table keys; rustudio equal userdata are not. Convert all engine property and argument boundaries accordingly; preserve float32 components and negative zero. The observed Vector3 text uses expanded native-number formatting; Vector2 uses nine significant digits (`0.333333343`), while NumberRange uses six (`0.333333`). Current Rust Display of f32 (`0.33333334`) is insufficient. Match per-type formatting rather than one global formatter. Samples below are exact; infinity/NaN/exponent thresholds still need a larger numerical sweep.

2. For every userdata metatable, replace mlua-generated __index/__newindex and failing operator callbacks with unnamed native C closures using `src/cmeta.rs::wrap(lua, inner, false)` (or checked=true for a `(ok,...)` dispatcher). Cache by type and operation per VM with cmeta::cached. Install wrappers on the actual userdata metatable through controlled internal access; wrapping only exported methods leaves mlua's generated __index visible. Preserve the existing __type and set __metatable to `The metatable is locked`. Verify debug.info `[C], -1, empty name, 0, true` and identity across independently created values for each observed C raiser. Some types have distinct native namecall; use the captured identity rows, not one blanket rule. Keep unsupported operations absent so Luau emits its native VM message.

3. cmeta's wrapper converts mlua Error objects into strings and raises at the unnamed C boundary. That fixes error object type/raiser but **does not fix message text**: replace mlua argument conversion errors with explicit physical-slot validation and Studio text before wrapping. Semantic member errors are location-free. Standard argument errors include caller source/line; missing and explicit nil differ. Unknown-member families differ in quotes: `%s is not a valid member of %s` versus `'%s' is not a valid member of %s`. Immutable known members use `%s member of %s is read-only and cannot be assigned to`; native Vector3 uses `%s cannot be assigned to`. Connection writes reject Connected as invalid member. Mutable Font and params permit the tested valid writes. Every observed expected message is recorded below; the final mismatch table is the actionable message replacement inventory.

4. Global constructors are frozen tables in Studio (nil metatable); rustudio tables are writable. Freeze after populating constants/functions and preserve named C constructor metadata. PhysicalProperties.new's debug name is `newPhysicalPropertiesWithClampedMsgClosure`, not `new`. Missing global constructors for RaycastResult/RBXScriptSignal/RBXScriptConnection should stay absent. Constructor coercions are intentionally permissive: Vector3.new('a'), Color3.fromRGB(nil), UDim2.new({}) succeed; CFrame.new(1,2) fails expecting Vector3 argument #1. Do not introduce blanket strict number checks.

5. Method functions need the observed named C metadata and identity behavior. Signal and connection methods return fresh named closures on each read; invalid self uses standard argument errors. Connect/Once with invalid callbacks return Connection while emitting `Attempt to connect failed: Passed value is not a function` to Output (not a pcall exception); preserve this separate diagnostic. ConnectParallel outside Actor fails first with `Scripts that connect in parallel must be rooted under an Actor.` even for bad self/callback. rustudio currently permits it. Once fires once and disconnects; Wait yields and resumes with all fired args; Disconnect twice succeeds and Connected stays false. Actor-rooted parallel callback execution was additionally measured (signal.Actor rows); exact scheduling order remains unmeasured.

6. RaycastResult and SharedTable are userdata in Studio but ordinary tables in rustudio. Implement real typed userdata before fixing individual member errors. Content's string must include its SourceType/Uri wrapper. PhysicalProperties now prints a sixth component in Studio; current rustudio prints five. Match the per-type rows for the remaining text differences. Keep native string format evidence separate from function attribution: the PE literals below were extracted from mapped sections and are not proof of a particular call path.

## Coverage checklist

Every listed type has create, values, read/write, arithmetic, ordering, len/concat/unm/idiv/mod, constructor mutation and bad-constructor probes below. Representative available methods have metadata and dot/wrong-self checks. Known-field writes and constructor function metadata are supplemental. Item 1 is partial only for hidden successful metamethod identities and exhaustive numeric formatting; item 2 is partial for rustudio direct captured-function calls (crash); item 3 is measured for the listed expressions; item 4 is measured both outside and inside Actor, with exact scheduling order still open. This is a bounded parity corpus, not exhaustive API coverage.

'''
text+='| Type | Item 1 | Item 2 | Item 3 | Item 4 |\n|---|---|---|---|---|\n'
for n in names:
 text+=f'| {n} | Partial: hidden functions / numeric boundaries | Partial: rustudio direct-call crash | Done: corpus expressions | '+('Done: signal corpus' if n in ['RBXScriptSignal','RBXScriptConnection'] else 'N/A')+' |\n'
text+='\n'
for n in names+['signal','connection']:
 keys=list(dict.fromkeys(k for side,k in st if k.startswith(n+'.')))
 keys+=sorted({k for side,k in ru if k.startswith(n+'.')}-set(keys))
 text+='## '+n+'\n\n| Probe | Studio | rustudio |\n|---|---|---|\n'
 for k in keys:text+=f'| {k[len(n)+1:]} | {cell(st,k)} | {cell(ru,k)} |\n'
text+='\n## Executable format strings\n\nMapped VA and literal from the supplied PE; broad string extraction is in exe-strings.txt.\n\n| VA | Literal |\n|---|---|\n'
for l in (p/'exe-strings.txt').read_text().splitlines():
 if any(x in l for x in ['cannot be assigned','not a valid member','invalid argument #','missing argument #','rooted under','readonly table','0x149119330','0x148f252b0']):
  a,s=l.split('\t',1);text+=f'| {a} | {esc(s)} |\n'
text+='\n## Message replacement inventory\n\nRows whose captured failure text or error value type differs, after removing script locations. Includes rows where one side incorrectly succeeds. Source prefixes belong to the caller and should not be hardcoded.\n\n| Probe | Expected Studio | Current rustudio |\n|---|---|---|\n'
def norm(s):return re.sub(r'(?:Players\.[^|]*?|ServerScriptService\.[^|]*?|harness|rustudio\.[^|]*?):\d+: ', '',s)
for k in dict.fromkeys(k for side,k in st):
 a=st.get(('client',k));b=ru.get(('client',k))
 if a is not None and b is not None and (a.startswith('false|') or b.startswith('false|')) and norm(a)!=norm(b):text+=f'| {k} | {esc(a)} | {esc(b)} |\n'
(p.parents[2]/'docs/RE-DATATYPES.md').write_text(text)
print(len(text),len(st),len(ru))
