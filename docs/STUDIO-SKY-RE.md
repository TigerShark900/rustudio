# Studio's sky, Atmosphere and fog — read from Studio itself

Started 2026-11-05 after the user compared Place B [DEV] in rustudio and
real Studio (night, Atmosphere Haze 1.9, custom Sky, Terrain Clouds): rustudio's
fitted Atmosphere model (round 26, `ATMOS_*` in mech.rs) filled the whole sky with
a bright blue band and fogged the scene to it. The user asked for the real code,
not fits. Everything below is from the shipped binaries of an offline Studio copy
(`~/.local/share/rustudio/studio`, 0.746) unless marked otherwise.

## Tooling

- **Shader pack:** `tools/decompile/shaderpack.py PACK OUTDIR` unpacks
  `shaders/shaders_glsl3.pack` into `<Name>.<variant>.glsl` (407 names, 2789
  blobs). Pack layout: `RBXS` header; name table from 0x54, 0x44 bytes per entry
  (name[64] + u32); feature-flag table (u8 index + name[64]); blob table, 0x40 per
  entry: md5[16], offset u32, size u32, u32 0, stage char (`p`/`v`/`c`) at +28,
  u16 name index at +30. Sources are plain GLSL 150 (cross-compiled; constant
  buffers as `CB<n>[]` with the struct layout in a header comment).
- **Decompiler:** Ghidra 12.1.4 at `~/tools/ghidra_12.1.4_PUBLIC` runs headless
  with `JAVA_HOME=/usr/lib/jvm/java-27-openjdk` (REA's MCP looks for JDK 21 and
  fails). The exe is imported once without analysis into
  `~/code/rs-re-ghidra/studio.gpr`; `DecompileAt.java` (a 30-line GhidraScript:
  create function at address, decompile, write `<addr>.c`) decompiles named
  addresses in ~3 s per run:
  `analyzeHeadless ~/code/rs-re-ghidra studio -process RobloxStudioBeta.exe
  -noanalysis -scriptPath DIR -postScript DecompileAt.java OUTDIR 0xADDR…`
- `tools/decompile/leascan.py` (RIP-relative refs to a string),
  `callscan.py` (direct callers), `pdata.py` (function bounds).
  Imports: `powf` = IAT 0x1489f75b0 (thunk 0x1478c029c), `exp2f` 0x1489f7508.

## Atmosphere instance (class registration 0x1403c7700…)

Getters are `movss xmm0,[rcx+k]` on the subobject at +0xc0:

| Property | Offset | Notes |
|---|---|---|
| Color | 0xc8 (vec3) | |
| Decay | 0xd4 (vec3) | |
| Density | 0xe0 | default 0.395 (ctor 0x1445cfd60) |
| Glare | 0xe4 | |
| Haze | 0xe8 | setter 0x141172630 clamps to [0, 10] |
| Offset | 0xec | |
| derived A | 0xf4 | `clamp(Haze − 1.98, 0.02, 1)` (0x1445d0120, the +0xc0 vtable's slot 0x20, run on every change) |
| derived B | 0xf8 | `0.5·Haze + (Haze ≠ 0 ? 0.6 : 0)` |

Decay as the sky uses it (0x1445cffd0): per channel
`exp2((1 − d)² + 4·(1 − d)) − 1`.

## AdvSky (the sky with an Atmosphere)

Renderer → AdvSky props (0x144a2b450 builds them, 0x144c1bfb0 stores them at
AdvSky+0x6c and sets kDirtyProps). Props, as floats from +0x6c:

| # | AdvSky offset | Source |
|---|---|---|
| 0 | 0x6c | Density |
| 1 | 0x70 | Offset |
| 2 | 0x74 | Glare → `glare.w` |
| 3 | 0x78 | derived A × (−1/ln 2) → `fogOffset.x` |
| 4 | 0x7c | derived B → `fogOffset.y` |
| 5–7 | 0x80 | Decay transform → `glare.xyz` (pow exponents) |
| 8–10 | 0x8c | Color |
| 27–29 | 0xd8 | Lighting render state +0x160 → `color0` |
| 30–32 | 0xe4 | Lighting render state +0x1a0 → `color1` |

Draw (0x144c19ed0) fills `AdvSkyFS`'s Params: `color0 = (+0xd8…, 1)`,
`color1 = (+0xe4…, 1)`, `fogOffset = (+0x78, +0x7c, 0, ·)`,
`glare = (+0x80, +0x84, +0x88, +0x74)`, `irradiance[6]` = the skybox's
6-axis irradiance (0x144c15060: solid-angle-exact integral of the squared
texels × 1/π).

`AdvSkyFS` (`shaders_glsl3.pack`), per pixel, dir = normalised view ray:

```
tex  = skyboxTexel · mix(color1, color0, clamp(worldY / 1700, 0, 1))   (VS)
base = tex.rgb²
t    = clamp(exp2(fogOffset.x / (0.001 + max(dir.y, 1e-5)^fogOffset.y)), 0, 1)
haze = Σ irradiance[axis] · clamp(±dir.axis, 0, 1)²  ×  FogColor (CB0[19])
     + SunColor (CB0[15]) · clamp((0.5 + 0.5·dot(dir, −SunDir))^glare.xyz · (1 − t)) · glare.w
sky  = mix(haze, base, t)
out  = sqrt(clamp(sky · Exposure)) · tex.a   (Linear variants: sky · tex.a; the tone pass follows)
```

So below Haze ≈ 2 the band is the 0.02 floor of derived A: x = −0.0289, a thin
bright rim (at Haze 1.9: 70 % haze at the horizon, ~15 % at 6°, ~5 % at 23°,
matching the Studio captures). The CPU AdvSky Compute job (0x144c16ce0) colours
a vertex sky with exponent `(B − 0.6)²` instead; the captures match the GPU
path, which is what desktop Studio draws.

## Part fog (DefaultUnified*FS)

```
vis   = clamp(exp2(FogParams.z · dist + FogParams.x) − FogParams.w, 0, 1)
fogC  = FogParams.w ≠ 0 ? FogColor : textureLod(PrefilteredEnv, viewDir, max(FogParams.y, vis) · 5)
color = mix(fogC, lit, vis)
```

With an Atmosphere (FogParams.w = 0) parts fade into the prefiltered sky cube
along the view ray, blurrier the more fogged. Still to read: how FogParams and
FogColor come from Density / Offset / Lighting (the per-frame globals build),
and the Lighting render-state fields +0x160 / +0x1a0 / +0x188 / +0x194 /
+0x164 (time-of-day sky colours).

## Fog with an Atmosphere (0x144a82df0, called from 0x144a23390 when AdvSky is on)

`FogParams = (0, Offset, −0.14427·clamp(Density,0,1)⁴, 0)` → visibility
`e^(−0.1·Density⁴·studs)`. **Desktop modern path: `FogColor = Color²`.**
The previously documented `Color² ⊙ meanSkyIrradiance ⊙ 0.5·(L160² + L1a0²)`
is only the other branch: renderer+0x690 → +0x118 is null or its byte +0x90
is below 2. L160 / L1a0 are Lighting +0x160 / +0x1a0 (AdvSky color0/1). Without an Atmosphere: `FogColor²`, `FogParams = (End/(End−Start), 0,
−1/(End−Start), 1)` (0x144a82d60).

Lighting instance offsets (getters at registration 0x14037c000…, subobject
+0xd0): Ambient 0xe0, ColorShift_Bottom 0xec, ColorShift_Top 0xf8, FogColor
0x104, OutdoorAmbient 0x110, ShadowColor 0x11c, Brightness 0x128,
EnvironmentDiffuseScale 0x12c, EnvironmentSpecularScale 0x130,
ExposureCompensation 0x134, FogEnd 0x13c, FogStart 0x140, GeographicLatitude
0x144, ShadowSoftness 0x14c, Sky* 0x1e0, Atmosphere* 0x1f0.

Measured against Studio (tools: scratch `atm` calibration, Haze 0 / 0.6 / 1.9
/ 3, red Color, default sky, 14:00): the haze is the same by day and night
with a custom sky, and nearly black with the default sky at night (its night
faces), so the 0.5·(L160² + L1a0²) factor is constant: rustudio uses
`ATMOS_HAZE_K` 2.65 for it until those members are read.

## Tone / ColorCorrection (ImageProcessFXCompositionLinearFS)

`x = scene²·4 + glow + bloom·k; y = x(ax+b)/(x(ax+c)+d)·e` with a..e from
CB1[6].xyzw / CB1[7].x (CPU constants, not yet read: rustudio's
`TONE_CURVE` is still the round-11 fit of this same form); then a 3×4 colour
matrix (ColorCorrection).

## Found on the way

- rustudio ignored `Sky.SkyboxBackContent`… (newer places save only the
  Content twins) and drew its default sky instead: fixed in `doc.rs` (saved
  Content twins now win over class defaults; Sky / Sun / Moon names added).

## Unions (PartOperation geometry)

Three stores, in the order rustudio tries them (`scene::union_mesh`,
`mesh::parse`):

- **SolidMeshHolder** (NetAssetRef; 5375 of Place B's 5624): holder header
  `03 01 <u32 size> <u32 0> <u16 0> <u32 size>` then `SolidMesh` + u32
  version 0 (reader 0x14297fc60): positions `u64 n, vec3[]`, normals `vec3[]`,
  UVs `u64 n, (f32,f32)[]`, colours `vec3[]` (sRGB 0..1, the child parts'),
  then four delta-coded u32 lists (0x14298c740: u64 count; per value 1 byte
  = 7-bit signed delta, or high bit set = 23-bit signed delta over 3 bytes,
  big-endian; first value from 0): per corner the position, normal, UV and
  colour index. UsePartColor drops the colours.
- **CSGMDL** in MeshData2 / MeshData (223): reader 0x1428a05d0. The first 10
  bytes are XOR-hidden with a 31-byte key from MSVC `rand()` seeded 1337
  (`x = x·214013 + 2531011`, byte = ((x >> 16) & 0x7fff) % 127; 0x1428a0390)
  and read `CSGMDL` + u32 version; the body is plain. Version 5
  (0x1428a1970): u16-counted per-vertex arrays — positions vec3, normals
  (u32 bytes = 6n, then u16×3, (v − 0x7fff)/32767), colours RGBA8, a byte
  each, UVs (2 f32), tangents (packed) — then i32 index count, u32 byte
  length, delta-coded indices (0x14298c9b0, as above), u8 LOD count + u32
  offsets (LOD 0 = indices[lod0..lod1]; its triangle count equals the
  union's TriangleCount). Versions 2–4 (0x1428a1050) aren't read (none in
  Place B).
- **Neither** (26): Studio rebuilds from ChildData2 (needs a CSG solver; not
  done).

Team Create: SolidMeshHolder replicates as a reference (wire type 0x3c) and
the blob comes on the 0xa5 channel (PROTOCOL.md), LZ4-compressed.

## Environment light and AO (2026-11-05)

Read from the HQ part shaders (variant 3 of `DefaultUnifiedFlatOpaqueFS`,
`DefaultUnifiedTiledFS`, `DefaultUnifiedPlasticReflectionFS`), the CPU cube
build `FUN_144a830a0` (caller `FUN_144a1e970`, colour mix `FUN_144a0e7c0`),
and a running offline Studio's memory: Lighting members (instance found by
setting FogEnd / FogStart / GeographicLatitude to sentinels and scanning
`/proc/<pid>/mem`; wine processes are readable) and the uploaded `Globals`
constant buffer (found by sentinel EnvironmentDiffuse / SpecularScale in
rows 30.w / 31.w). Tooling: scratch `mem/*.py` (not in the repo).

**Globals rows** (CB0, vec4 index): 13 AmbientColor, 14 SkyAmbient, 15
Lamp0Color, 16 Lamp0Dir, 17 Lamp1Color, 18 FogParams, 19 FogColor, 20
Exposure (`.y` = 2^ExposureCompensation / 4: the scene is stored /4, the
compose pass ×4), 28 `.y` spec fade 0.0008/stud, 30 SkyGradientTop (`xyz`
c0², `w` EnvironmentDiffuseScale), 31 SkyGradientBottom (`xyz` c1², `w`
EnvironmentSpecularScale), 32 AmbientColorNoIBL = Ambient², 33
SkyAmbientNoIBL = max(OutdoorAmbient² − Ambient², 0), 34–39 AmbientCube sky
part (minus indoor), 40–45 AmbientCube indoor.

**Time-of-day sky levels.** Lighting `+0x160` c0, `+0x1a0` c1 (vec3), `+0x16c`
k (vec3, grey), keyed on ClockTime only, piecewise linear: c0/c1 =
lerp(table(s=0), table(s=1), EnvironmentDiffuseScale), k = max(k0, s·k1).
17 keyframes in `mech::SKY_LEVELS` reproduce 1/8-h samples to 6e-8 (and
1/64-h samples across 06:00 and 17:30). By day c0 = c1 = 1, k = 0.75.

**AmbientCube** (`0x144a830a0`): sky part per axis = s · irr_sky[axis] ·
(+Y c0², −Y c1², sides ½(c0² + c1²)); indoor = s · irr(`textures/sky/
indoor512_*`) (a constant: independent of Ambient, Outdoor, the Sky; checked
against the faces). `AmbientColor += s·mean(indoor)`, `SkyAmbient +=
½s(c0²+c1²)·mean(irr_sky) − s·mean(indoor)` (LQ shaders only).

**Lamp0 / Lamp1** (`0x144a1e970`): with `f(a, b, c) = ((c·|a| − b)·|dc| + b −
(a + dc·|a|))·s + (a + dc·|a|)`, `dc = c − 0.3333·Σc`:
`Lamp0 = 0.9·Brightness·f(k², k², ColorShift_Top²)`,
`Lamp1 = 0.36·Brightness·f(k², 0, ColorShift_Bottom²)` (reproduces the dumped
CB0 to 4 digits). Lamp0Dir = −(Lighting `+0x178`): the sun while sun.y ≥ −0.3
(measured switch, both latitudes), else the moon (−sun). Lighting `+0x188`
is GetSunDirection, `+0x194` the moon direction.

**HQ part FS** (r = 0.089 + 0.911 × material roughness — SpecularMap `.y` for
Tiled, a per-material vertex byte `inversesqrt(COLOR1.y · 0.17453)` for flat
parts; m = metalness (SpecularMap `.x`) × sS; sS = EnvSpecular ×
clamp(1 − 0.0008·dist)):

```
F0 = mix(0.04, albedo, m);  (A,B) = brdfLUT(r, N·V);  Fe = (F0·A + B)/(A + B)
diffuse = (1−m)(1 − Fe·sS) · lerp(indoorCube(N²), skyCube(N²), skylight)
        + Ambient² + SkyAmbientNoIBL·skylight
        + (1−m)(1 − Fs·sS) · Lamp0·N·L·shadow + Lamp1·(1−m)·clamp(−N·L·shadow)
        + local
spec    = lerp(Indoor(R, 5r), Env(R, 5r)·mix(c1², c0², clamp(R.y·1.588)), skylight) · Fe · sS
        + GGX(r⁴)·Fs·Lamp0          (not × sS)
out     = diffuse · albedo + spec
```
Parts with Reflectance > 0 (PlasticReflectionFS): albedo → mix(albedo,
Env(R, mip 0)·tint, Reflectance), m = 0. `brdfLUT` is PlatformContent
`textures/brdfLUT.dds` (256², R16G16F).

**SSAO** is on in Studio's edit view (a white block on a white floor lit only
by Ambient: contact 125 vs 140; only by the sun: 177 vs 190 — it multiplies
all light). Passes: `LinearizeDepthFS` (x = min(viewZ·0.002, 0.998), sky 1;
y = Lighting linear fog amount via Params1 = (0, 0.1, FogEnd, 1/(FogEnd −
FogStart)), read from memory), `SSAODepthDownFS` (half res, min of 4),
`SSAOFS` (8 pairs at 45°, t = 0.1(i+1), radius = SSAOParams.xy·0.004/depth
clamped to 10–100 half-res texels, SSAOParams.xy = 0.5·(P00, P11) per
`0x144bff6d0`; occlusion (Δdepth·125/√(1−t²) + 0.5), weights clamp(min + 0.75),
ao = clamp(sum/count·2)), `SSAOBlurX/YFS` (7 taps, exp(−i²·2/9), depth
threshold clamp(d·0.064, 8e-5, 0.008)), `SSAOCompositFS` (depth-aware 4-tap
upsample, ao' = (1 − fog)·ao + fog), applied by multiplication (`SSAOApply`).

Implemented in rustudio: `lighting::sky_levels`, Globals `env` / `env_indoor`
/ `sky_grad` / `lamp1` / `ssao`, shader `env_cube` / `brdf_ab` /
`env_reflect`, the part lighting block, terrain's `env_cube`, the SSAO
passes (`fs_ssao_*`, render.rs `ssao_*`), Lamp0/Lamp1 replacing the
SUN_/MOON_ fits.

**Env prefilter (2026-11-07).** `PrefilteredEnvTexture` is built per face
and level by `0x144b3abb0` with `FastConvolutionPS` (Manson & Sloan's fast
filtering: 24 taps per texel from the level above, tap table in CB4, CB2[3].x
= level − 1); the FS reads level 5r, so level m holds GGX for roughness m/5.
rustudio's reflections read the skybox's box-filtered mips instead, which kept
rough parts mirror-sharp (Place A's lobby: glossy heads, floors, guns);
`render::cube_mips` now GGX-filters the levels below `ENV_PREFILTER_SIZE`
(importance-sampled, α = r², N = V). The tap table itself isn't dumped.

**Flat roughness byte (read, values not dumped).** COLOR1 =
`0x144c4a2f0`: x bone, y = clamp(18 / (π·((b + 1)/256)²) + 0.5, 1, 255)
from the material record's byte +0x55 (`0x144c9e280`; a MaterialVariant's
u16 +0x218), z = record +0x54 (metalness byte; variant +0x214), w =
`0x144f18040(part)`·255 (Reflectance, by its use). The VS's `inversesqrt(COLOR1.y · 0.17453)` gives back
(b + 1)/256. In the decompile `0x144b5e790` writes those two bytes as one
u16 (`uStack_a4`: 0x101 or 0 per material), which would put every built-in
flat material at COLOR1.y 255 (r ≈ 0.23); unconfirmed (no memory dump yet),
so rustudio keeps its fitted `ENV_SPEC_ROUGHNESS`.

Still not read: the flat parts' per-material roughness byte values (above;
rustudio keeps `ENV_SPEC_ROUGHNESS`), the size of Studio's prefiltered env
cube (rustudio assumes 8 mips: `ATMOS_ENV_CUBE_LEVELS`), the SSAO noise tile (randMap;
rustudio rotates by the pixel's place in a 4×4 tile) and depth mips
(KSSAOMipLevels: rustudio samples the half-res depth only), and whether the
quality profile ever turns SSAO off.

## Local light shadows (Future / Realistic)

From the Vulkan pack (`DefaultUnifiedTiledFS` variant 8 through spirv-cross; names
from the D3D11 pack's RDEF) and a running Studio's buffers (`/proc/<pid>/mem`):

- Lights are clustered (froxel `isampler3D` + index list); each record (64 B):
  position, `m1 = Range·1000 + 0.71` (flat to 0.71·Range, then
  `(t²(2t−3)+1)·110/(110+d²)` to Range), colour **Color^2.2 × Brightness**
  (checked on 4 lights to 4 digits), shadow slot (−1 none), spot axis /
  cos, surface-light extents.
- Shadowed lights get a slot (binding 7: position, w = 1 for a cube, 1/Range,
  strength) and 6 face matrices (binding 8, 128 slots × 6): FOV 93°
  (projection 0.94896), near 0.1, far = Range; faces packed in an atlas at
  3/32 × 1/20 of it (absolute size not read).
- The atlas holds **EVSM** moments of `z = 2·(viewdepth/Range) − 1`:
  `(e^{5.54z}, e^{2·5.54z}, −e^{−5.54z}, e^{−2·5.54z})`; the test is Chebyshev on
  both with minimum variance `(5.54 · 0.0075 · e)²`, light-bleed cut
  `(p − 0.2)·1.25`, the lesser kept, scaled by the slot's strength.
- Globals: `localLightDist` 580, `hybridLerpSlope` 0.05 (beyond 580 studs
  Studio blends to its voxel light map over 20 studs), `sunDist` 580,
  `evsmPos/NegExp` 5.54, `shadowBias` 0.0075; sun cascades 4 (radii ≈ 22 /
  50 / 158 / 680) — the sun's map is EVSM too (not yet in rustudio).

rustudio (2026-11-05): `LightShadows` in render.rs (2048² RGBA16F atlas,
192-px faces, 16 lights), slots from `lighting::gather`, `light_shadow` in
shader.wgsl; redrawn when the static scene or the lights change. Not yet:
terrain and moving parts as casters, spot lights' single face, the 580-stud
voxel hand-off, the sun's EVSM cascades.

## Open

- FogParams / FogColor with an Atmosphere (Density, Offset).
- Clouds (`CloudsVS`, `Clouds*FS`, `CloudsParams`): not drawn by rustudio at all.
- ColorCorrection / Bloom passes (`ImageProcess*FS`).

## Light grid (skylight)

Read 2026-11-05 from the exe (Ghidra, objdump) and checked against a running
offline Studio's memory (`tools/decompile/lightgrid_dump.py PID PREFIX`, then
`RS_LG_DUMP=PREFIX RS_LG_PARTS=… cargo test --release --bin rustudio
lightgrid_vs_studio -- --ignored --nocapture`; parts dumps come from the
scratch `pdump.py`, ≤ 4 parts per `run_luau` because its reply is cut at
~930 characters). Note: with Lighting.GlobalShadows false the CPU grid skips
the skylight altogether (LightGridCPU +0xba, set from Lighting +0x154 in
0x144cda860; FUN_144cd19e0 "lightingClearSkylightSunlightChunk" fills it
with 255) — an rbxlx without GlobalShadows loads it false.

**Grid.** `LightGridCPU` (vtable 0x149226388, ctor 0x144ccd1f0, created by
0x144ccf980): 8 × 4 × 8 chunks (+0x50, read from memory; same in an empty
place and Place B) of 32 × 16 × 32 four-stud voxels = 1024 × 256 × 1024 studs.
Chunk struct 0x2541c bytes: +0 dirty flags (0x20 occupancy, 0x10 sun, 0x8
skylight, 0x6 local lights), +8 chunk coords, +0x14 three occupancy planes
(16 × 32 × 32 each, y-z-x), +0x1c01c skylight/sun byte pairs, +0x2401c…
boundary faces for the neighbours. Follow (0x144cd9980): camera voxel v =
floor(pos/4); the grid moves only when the camera's chunk (v>>5, v>>4, v>>5)
leaves the middle two, then origin = ((v + 16) >> 5, (vy + 8) >> 4, …) − dims/2.
Textures: "LightGrid Chunk 3D" (local lights, format 4) and "LightGrid Chunk
Skylight 3D" (format 2: two unorm8 channels), X·32 × Z·32 × Y·16.
Shaders: VS `uvw = (pos + 6·normal).yxz · LightConfig0 + LightConfig1`, FS
samples `.yzx` (texture X, Z, Y); read from CB0 in Place B: LightConfig0 =
(1/256, 1/1024, 1/1024), LightConfig1 = (0, 1, 1) — toroidal (wrapping)
addressing — LightConfig2 = grid centre in uvw, LightConfig3 = 0.4921875:
outside |uvw − centre| ≥ that on any axis, skylight = sun = 1, light map 0.

**Occupancy.** `updateChunkOccupancy` (0x144cd8940) → per part
FUN_146656750 (via thunk 0x1466580d0), record from FUN_146654ff0: skipped if
CastShadow is off (prim +0x79), Transparency ≥ 1 or prim +0x78; record type by
SpecialMesh type (Head 1, Torso 8, Wedge 7, Sphere 3, Cylinder 2, Brick 4,
FileMesh and others: none), else BlockMesh 4 / CylinderMesh 1, else physics
shape (Ball 5, Block 4, Cylinder 2, Truss 4 with T·0.25 + 0.75, Wedge 7,
CornerWedge 6, MeshPart / union 9 when its physics has convex pieces).
Value per voxel, saturating-added into all three planes:
`(int)(coverX · coverY · coverZ · (1 − clamp(T)) · 255.5)` where
cover = clamp(t, 0, cap), t = 0.5 − (signed distance outside the shape along
that axis)/4, cap = min(size/4, 1):
- Block, axis-aligned (|R00|, |R11|, |R22| ∉ (1e-4, 0.9999); 0x14664ba10):
  world extent e = |R|·size, max(e, 1), t = e/8 + 0.5 − |Δ/4|; range trimmed
  by 0.01 voxel at the top. Turned (0x146649f00): the same in the part's
  local frame (Δ rotated by Rᵀ), sizes max(·, 1).
- Ball (0x1466534c0): t = 0.5 − (|Δ| − Size.X/2)/4 on all axes. Cylinder X
  (0x146651cf0): t_x from |l_x| − Size.X/2, t_y = t_z from √(l_y² + l_z²) −
  min(Size.Y, Size.Z)/2 (type 1: the same along Y). Sphere mesh (type 3,
  0x146652c90): q = √Σ(l/h)², t_i = 0.5 − (q − 1)·h_i/4. Wedge (0x1466544c0)
  and CornerWedge (0x146651480): per-axis distances to their slope planes.
- Thin parts (any Size < 4; the "small" twins 0x14664ab70, 0x146649580,
  0x14664d9b0, …): the planes differ: per local axis i the projection
  p_i = n_i · Π_{j≠i} cover_j with n_i = clamp((t_i + off_i)/cap_i, 0, 1)
  (off from FUN_146655d20: (1 − cap)(rowsum − 1)/2 of |R|), plane A/B/C =
  |R| · p (world X/Y/Z); axis-aligned: n_i = min(1, raw_i/(cap_i − frac_i)).
  A 2×40×2 pillar centred in its voxels gives (127, 63, 127).
- Meshes (type 9, FUN_146656f60; the piece boxes come from the physics
  data, not read here): per convex piece's part-space box (×1.3
  when there are several): world box half extents h, g = max(0, |Size|/300 −
  0.25)²·1.7 + 1, q = Σ_i (Δ_i·g / (2h_i))², value = (1 − √q (bit-trick
  sqrt))³ clamped to max cap, over the world box only.
- Terrain (FUN_146657c10, after the parts): + the voxel's occupancy byte
  unless Air or Water, to all three planes.

**Skylight** (`lightingUpdateChunkSkylight` = FUN_144cd3200 →
FUN_144cd3c80, chunk at a time, y from 15 down, scratch 34 × 34 × 18 with
neighbour faces as padding, 255 where a neighbour chunk is missing):
```
recv  = (Σ the 8 voxels around (x, z) in the layer above, not (x, z) itself, + 7) >> 3
out   = 252 − ((255 − recv)⁴ >> 24)           → skylight byte (open air 252 = 0.988)
block = max(max(occX, occZ) · 180 >> 8, occY)   (180 = (int)(255/√2))
pass  = max(recv − block, 0)                    → the layer below's input
```
Faces that change by more than 4 re-dirty the neighbour (so Studio's own grid
is a few levels off a full solve near chunk edges).

**Checks.** Calibration scene (floor, 7×7 pillars 2×40×2, roof, wall,
Transparency 0.5, CastShadow off, unanchored, a turned 1×24×12 plank, a
ball): rustudio's occupancy equal to Studio's in all 12.6 M bytes; skylight
from it equal in 97.8 % of voxels, the rest under the floor or ≤ 6 levels
(Studio's stale chunk faces). Place B at the pillar view (3771 parts): the
left-over differences are at MeshParts / unions as one piece
(rustudio has no convex decomposition: 13 k of 12.6 M bytes off, most where
Studio splits a mesh into several pieces; 102 k with meshes left out); skylight equal in 99.0 % of
voxels (Studio's own occupancy through rustudio's kernel: 99.04 %).

### Sun channel

Read from Studio 0.746 on 2026-11-08: `lightingUpdateChunkGlobal`
FUN_144cd34e0, called by FUN_144cd3200 with LightGridCPU +0xbc.
FUN_144cda860 normalizes and negates Lighting's vector at +0x178..0x180
before putting it there (light travel direction). The public Rust function
`sunlight(occ: &Occupancy, grid: &mut LightGrid, sun: glam::Vec3)` takes
**toward** the light instead. It writes only the second byte of each pair.

Let `a = abs(direction)` (unit length). Pick the largest component, ties
preferring Z then Y then X. For the other two components' ratios `u,v` to
that largest component, their weights are `u/2-u*v/6`, `v/2-u*v/6`;
the largest component's weight is `(1-first)-second` (float operations).
Constants: 1 at 0x148a67998, 0.5 at 0x148a6d730, 6 at 0x148ae4fa0,
255 at 0x148a7fbe4. FUN_144cced50 quantizes the XYZ weights:

```
q = trunc(clamp(weight,0,1)*256 + 0.5)
qZ = max(qZ + trunc((256-qX-qY-qZ)/3), 0)
qX = max(qX + trunc((256-qZ-qY-qX)/2), 0)
qY = max(256-qZ-qX, 0)
attenuationXYZ = trunc(aXYZ * 255)
```

The quadrant sweeps are 0x144cc5990 (travel X<0,Z<0), 0x144cc6f50
(X<0,Z>=0), 0x144cc8540 (X>=0,Z<0), 0x144cc9b70 (X>=0,Z>=0).
All descend Y and visit X/Z in travel order. Each voxel reads three
**outgoing** values from its immediate upstream X, above Y, upstream Z
neighbours, with their respective q weights (no diagonal samples):

```
received = (upstreamX*qX + above*qY + upstreamZ*qZ + 255) >> 8
sunByte = received
block = (occX*attenuationX + occY*attenuationY + occZ*attenuationZ + 127) >> 8
outgoing = max(received-block, 0)
```

There is no skylight-style fourth-power stored-byte transform. A full
axis-aligned occupied voxel passes 1 rather than 0 (255*255 rounds to 254).
Missing upstream chunks provide 255; chunk faces carry outgoing values.
The Rust full-grid solve crosses chunk boundaries directly, so Studio's
incremental face updates can differ. Scalar and SIMD paths implement the
same recurrence. GlobalShadows false skips FUN_144cd34e0; the clear routine
FUN_144cd19e0 supplies 255. Callers should skip `sunlight` in that mode.
The kernel takes abs(Y) and never tests the horizon: its caller supplies the
active celestial direction. Live Studio at ClockTime 2 confirmed the active moon direction: flip X
and Y of the astronomical sun, preserving Z (not a vector negation).
The Rust API performs this conversion when sun.y < 0. GetSunDirection
was (0.49678591,-0.86045843,0.11320364), GetMoonDirection was
(-0.49678609,0.86045831,0.11320364), and LightGridCPU +0xbc was
(0.49678609,-0.86045831,-0.11320364), the negated moon.

Regression coverage: open air 255; solid slab blocking; partial roof
transmission; sideways shadow from a low sun. `sunlight_vs_studio` is an
ignored memory comparison taking `RS_LG_DUMP` and `RS_LG_SUN=x,y,z`.
Live calibration: ClockTime 16.8, GeographicLatitude 30, GlobalShadows true,
64x4x64 floor, 48x0.4x48 roof, two solid walls, three 2x24x2 pillars,
open sides. Sun direction (-0.94491744,0.30709815,0.113232784).
Daytime: 4,194,234 / 4,194,304 bytes exact (99.998331%); 100% within
6, mean absolute error 0.000019. Night at ClockTime 2: 4,194,304 /
4,194,304 bytes exact (100%), mean error zero. Release lightgrid tests:
7 passed, 4 ignored; both live sun comparisons passed. The fixture has Technology token 3;
Studio blocks plugin reads/writes of Technology, so no live property override
was possible. Studio was started for this check and closed afterwards.

Remaining unrelated work: mesh convex pieces and the texture sampler state
(rustudio: linear, clamp, with the border test).

## Part materials

Read 2026-11-05 from the shader packs (GL3 + Vulkan through spirv-cross), the
exe (Ghidra) and running offline Studios' memory (`/proc/<pid>/mem`; scratch
`mem/mattab.py`, `mem/iscan2.py`, `mem/vtscan.py`, not in the repo).

**Material records** (read). `0x14dc59730`: `[table 0 pre-2022 | 1 2022][43
materials] × 0x130` bytes (index = 0x2b × table + material index,
`0x144b5eff0`); +0x08 the pack id string, +0x30 the detail pack, +0x58 the
shader type, +0x5c the 80-byte PartMaterialConsts that `0x144aab710` uploads as
CB2 (`0x144beab70(obj, 2, record + 0x5c)`). All 86 dumped into
`mech::PART_MATERIAL_PRE2022 / _2022` (CrackedLava's emissive (2, 2, 2) lands
in `emissive`, confirming the field order). Slate: pre-2022 type 7, (1, 1, 0, 5,
1, 0.25, 1, 1, 0.75, 0, 0, 0, 4, 1, 1, 1); 2022 type 21, (1, 1, 0, 5, 1, 1, 1, 1,
0, 0, 0, 0.03, 1, 1, 1, 1). Types 21–22 bind `textures/noise.dds` at slot 9
(`0x144abbf20`) and are drawn by `DefaultUnifiedDetiledFS`.

**Texture slots** (read). Table `0x14cb002c0` (24 B each): diffuse → s3,
normal → s4, specular → s5 (pack 0), normaldetail → s8 (pack 1 = the record's
detail pack). The "normaldetail" is the material's own detail pack's normal
map, not `plastic/normaldetail.dds` (that one is Plastic's). Pre-2022 Slate's
detail pack 7547298323 → normal 7547298243 (512², crumpled rock); 2022 Slate's
(9439613006 / 4K 75747241361350) are flat single-colour images.

**Shaders** (read). HQ Tiled (`DefaultUnifiedTiledFS` 3/7/11/15, Vulkan 8):
`uv = VARYING0 × textureTiling`; normal = map(uv).wy·2−1, z rebuilt; `xy +=
NormalDetail(uv × normalDetailTiling).wy·2−1 × normalDetailScale` (z kept); `xy
×= clamp(1 − FadeDistance·viewDepth)` (CB0[28].y = 0.0008). The far-tiling
fields are used only by the LQ variants (0–2, 4–6, 8–10, 12–14): diffuse =
`mix(D(uv × farTilingDiffuse), D(uv), clamp(clamp(1 − w/300)·s − 0.6·s))`, s =
farDiffuseCutoffScale; the HQ path ignores them. HQ Detiled: `k =
noise(uv × noiseScale).x × 8`; samples at `uv + sin((3, 7)·floor k)` and
`floor k + 1`, explicit gradients of uv, mixed by `fract k` (albedo, normals
after decoding, specular); textureTiling unused; detail at uv × normalDetailTiling.

**UV scale** (measured). VS: `uv = TEXCOORD0 × (uvScale·faceU, uvScale·faceV) +
uvOffset` (CB1 rows 5 and 6 per instance, DefaultUnified*VS instanced
variants). Found the rows by sentinel part sizes: uvScale = size / S with S =
8 for every material when Use2022Materials is on; with it off (a clean place,
and Place B): Wood / DiamondPlate / Metal 5, Marble / Slate / Granite
/ Pebble / CorrodedMetal / Foil / Sand / Ice 10, Concrete / Grass / Fabric 6.667,
Glass / ForceField 4, Cobblestone 14.81, others 8 (`PART_MATERIAL_*[..][5]`).
Not from MaterialVariants (the place's `*_Pre2022` variants' StudsPerTile
differ). uvOffset is a per-part random offset (not reproduced). Where S comes
from in the exe isn't found (no float table matches; not in the records).

**Filtering** (read + measured). Material maps bind with SamplerState filter
2 (anisotropic: linear min/mag/mip, GL table `0x14ad08330`), anisotropy 0, minLod
0, maxLod FLT_MAX (`0x144abb9a0`); anisotropy 0 means the context default
(`0x147a39a30` GL, `0x147a832d0` Vulkan; slot 1 of the context vtables sets
it). A running offline Studio's D3D11 context (vtable `0x14ad0ea50`) holds 8
at +0x58. Vulkan's sampler: mipLodBias 0, maxAnisotropy = min(state, device
max) (`0x147a8d220`). The noise sampler is plain linear. rustudio: 8×,
trilinear, no bias (unchanged; the studs sampler that also samples materials
now uses `mech::TEXTURE_ANISOTROPY`).

**Place B.** `Use2022MaterialsXml` is false in the saved place and in
every cached cloud version, so Studio draws pre-2022 Slate: the 10-stud
blotchy maps plus the crumpled detail normal 5× per repeat (2 studs). That
detail map is the fine relief in the user's Studio screenshot; rustudio had no
detail map and tiled at 8 studs, hence "larger, flatter". Wall view
(camera 117,179,327 → 156,183,333; 1700×1500 window, wall ≈ 550 px like the
screenshot's 540): power-spectrum median 23 cycles/wall before, 34 after,
Studio 40.

rustudio (2026-11-05): `matpack::consts` / `detile_noise`, the per-layer
`mat_params` uniform (render.rs `MaterialArrays`, binding 18), detail packs
as their own material layers, the Tiled / Detiled sampling in `fs_part`.
Not done: the Wang-tiled materials (`DefaultUnifiedWang*`, wangIndex.dds; which
materials use them isn't read), uvOffset, the LQ far tiling, the per-type
shader differences beyond Tiled / Detiled (types 4, 6, 8, 9, 10, 12), mesh
parts' material UV scale, and whether the 4K 2022 table has its own constants
(the dumped 2022 row is the non-4K table this offline Studio built).

### Material continuation (Studio 0.746, 2026-11-06)

Static evidence retained in `~/.cache/rustudio/agents/materials/dc/` and the
unpacked `glsl/` shaders; no live Studio was driven for this continuation.

- **Wang answered / implemented.** `0x144aab710` case 6 loads
  `rbxasset://textures/wangIndex.dds` (`0x1491f9f70`); `0x144abbf20`
  binds it at s9 with filter 0 (point), wrapping. Type 6 is pre-2022
  WoodPlanks, Marble, Brick, Grass, Cobblestone; none of the 2022 entries.
  Shader selection is the jump table at `0x144c9f000`, type 6 ->
  `0x144c9e4dd`: WangFS when available, WangFallbackFS otherwise.
  WangFS.3: q=uv*textureTiling, t=4q, index=point(wangIndex,t/128).xy,
  atlas=index*(255/256)+fract(t)/4; all three maps use atlas with gradients
  of q, and detail normals use q*normalDetailTiling. The DDS is 128² A8L8,
  exposed as RG by Studio (our generic DDS decoder exposes L in RGB, A in A).
  Both bytes take values 0,64,128,192, giving exact quarter-atlas offsets.
  rustudio packs the 4-bit cells into exactly representable uniform integers.
- **UV offset answered / implemented for primitive materials.**
  `0x148159ec0` hashes the eight bytes of the instance allocation address
  with 64-bit FNV-1a (offset cbf29ce484222325, prime 100000001b3).
  `0x1443ec480`: u=(hash>>3)&63, v=(hash>>9)&63; ordinary materials return
  `(2*table[u,v]-1)*((Size.X+Size.Y+Size.Z)*0.5)`, using the 64 floats at
  `0x1491588d0` (now MATERIAL_UV_RANDOM). Plastic/SmoothPlastic clear the
  low bit of each integer index; WoodPlanks/Brick/materials 2304..2311 use
  integer indices directly. A MaterialVariant returns zero. The global
  DebugRenderingSetDeterministic (`0x14dbc1c30`, registered at
  `0x1441853e6`) zeros the seed indices. The hash also returns zero for
  the special ancestor condition in `0x148159ec0`; that predicate is not
  yet ported. rustudio uses the low 64 bits of its random DOM referent as
  allocation identity: the algorithm/distribution match, but individual
  offsets cannot match addresses in a separate Studio process. Offsets
  stay fixed when a part moves. Authored mesh UVs are left alone.
- **UV scale source answered.** `0x1443ec610(material,variant,use2022)`:
  variant -> 1/variant.StudsPerTile (+0x228); 2022 -> 0.125; otherwise a
  material switch (including Cobblestone 0.0675 at `0x149159440`). This
  confirms the previously measured primitive scales. MeshPart path:
  `0x144c407e0` case 8 -> `0x144c3c060`; its authored-UV vertex copy keeps
  UVs, while generated face UVs use `0x144c4af70` (size on the face's two
  axes times `0x1443ec610`) and offsets from `0x144c4ae20`. The authored
  mesh path's unit scale is already rustudio's behavior; generated face
  UVs for meshes/unions still need tracing through all branch conditions.
- **Far-tiling sampling implemented; selector partial.** The old statement that all HQ
  paths ignore these fields applies to plain Tiled, not every type.
  Jump-table types 4/5 -> TiledFS; 6 -> WangFS; 7 ->
  TiledHideDiffuseRepFS; 8 -> TiledHideAllRepFS; 9 ->
  TiledEmissiveHideDiffuseRepFS; 10/11 -> GlassFS/GlassTransparentFS;
  12 -> ForcefieldFS (`0x144c9e2e0`, jump table `0x144c9f000`).
  HQ type 7 blends diffuse far/near by
  clamp((clamp(1-viewZ/300)-farDiffuseCutoff)*farDiffuseCutoffScale).
  HQ type 8 does the same and blends normal/specular with their own tiling,
  cutoff and scale, using clamp(1-viewZ*FadeDistance). Plain Tiled LQ
  uses unscaled VARYING0 and a hardcoded diffuse cutoff 0.6. rustudio
  implements these sampling branches, selecting LQ with its existing
  lighting-path selector; complete LQ lighting and WangFallback remain open.
  HQ type 9's actual shader has no far diffuse blend, despite its name.
- **4K constants answered.** `0x144b5f0c0` constructs only two 43-entry
  constant tables, calling `0x144b5e790(index,table!=0)`. The 4K flag is in
  the asset-info constructor (`0x148163960`), not the constant constructor.
  Both 2022 asset resolutions share constants. All shader type + 20-float
  rows are retained as PART_MATERIAL_FULL_*; the builder recomputes cutoff
  scales as 1/(1-cutoff) (or FLT_MAX near 1).

Validation so far: `RUSTUDIO_NO_AUDIO=1 cargo build --release` succeeds;
headless gamescope screenshot initializes the real wgpu pipelines and saves
`~/.cache/rustudio/agents/materials/smoke.png`. No pixel-parity claim is made.
Still open at the first commit (type 9 is implemented below): exact Glass/Forcefield rendering;
complete LQ lighting and WangFallback; variant/custom-mesh branch coverage;
the special ancestor predicate in the pointer-hash function.

**Type 9 follow-up.** Implemented `DefaultUnifiedTiledEmissiveHideDiffuseRepFS`
(HQ variant 3 and the LQ variant 0): `emissive * SpecularMap.z` is added to
*diffuse illumination before multiplying by albedo*, not added to the final
colour. CrackedLava's row is (2,2,2); its pack contains an explicit
`<emissive>` asset (legacy pack 9438582231 -> 9438581672). `matpack::Pack`
now reads it, and MaterialArrays binds a linear mipmapped R8 mask array at
our s19. The diffuse alpha is now the colour map's alpha rather than the
height map; the built-in mask formula in Wang/HideDiffuse/HideAll/Emissive
is `square(diffuse.rgb * mix(1,Color3,mix(1,diffuse.a,isNonSmoothPlastic)))`.
CrackedLava's colour alpha really varies 0..255, so preserving it matters.
The flat/SurfaceAppearance alpha modes remain outside this built-in path.

Additional type evidence (not yet fully ported): GlassFS.3 samples the
specular map at both near and far scales, uses 10× normal z (weaker bump),
alpha `clamp(2*partAlpha-1+diffuseAlpha)`, and grazing blend
`0.8*(1-NdotV)^2*clamp(2*partAlpha)`. GlassTransparentFS also uses the scene
colour/depth. ForcefieldFS.3 is **unlit**, with rim
`1-clamp(2*abs(NdotV))`, animated diffuse-red pulse
`(1-clamp(13*abs(red-GlobalForceFieldTime)))*diffuseAlpha` (zero if red=0),
then alpha `partAlpha*max(mix(pulse,1,max(rim,pulse))*max(rim,pulse),
VARYING1)`. Its VS makes VARYING1=max(0.05,COLOR1.w/255). The current
scene maps ForceField to its approximate glass path and halves alpha;
this still needs replacing together with the animated built-in texture and
time source. These are explicitly remaining work, not claims of parity.

Validation: release build succeeds, 3/3 existing matpack unit tests pass,
and the headless material calibration screenshot (six actual material
packs, including Wang, HideDiffuse, HideAll and CrackedLava) completes at
`~/.cache/rustudio/agents/materials/materials.png`. There is no matched
Studio capture for this continuation, so visual parity is not yet measured.

### Materials2 continuation (2026-11-06; partial implementation)

Evidence and before/after captures: `~/.cache/rustudio/agents/materials2/`.
`dc/` uses the existing no-analysis Ghidra database and the supplied `dc.sh`;
`vk/` is the unpacked Vulkan pack (24-byte header before SPIR-V),
`glass-vk.glsl` is spirv-cross output of GlassTransparentFS.8.

Implemented:
- ForceField has a distinct renderer kind 6, always sorted as transparent.
  The scene builder still supplies half alpha; `to_raw` restores the original
  alpha for material 1584, without changing scene.rs in this shared checkout.
  ForcefieldFS.3: unlit Color3 squared, rim `1-clamp(2*abs(NdotV))`,
  pulse `(1-clamp(13*abs(texture.r-time)))*texture.a` when red > 0,
  alpha `partAlpha*max(mix(pulse,1,max(rim,pulse))*max(rim,pulse),0.05)`.
  Texture is a phase map, not coloured albedo. No texture means no pulse.
  Current pulse clock is a provisional one-second sawtooth: Studio's actual
  GlobalForceFieldTime producer/rate and COLOR1.w coverage source remain unread.
  The regular sRGB texture sample is converted back to encoded red for phase.
- GlassFS.3 sampling: alpha `clamp(2*partAlpha-1+diffuse.a)`, normal z times
  10, far specular blend, outdoor tinted reflection `env*(1+albedo)/2`,
  grazing `0.8*(1-NdotV)^2*clamp(2*partAlpha)`, and separate additive
  environment BRDF / sun terms. Replaces the earlier fitted pow(1-NdotV,3.5).
  This is the non-refracting approximation; it is not the complete glass pass.

New static findings:
- `0x144aab710` cases 10/11 conditionally bind scene colour at s9, depth at
  s10; GL3 GlassTransparentFS.3 has neither input, whereas Vulkan
  GlassTransparentFS.8 does. Refraction is backend/capability dependent.
  Vulkan uses eta `mix(.66,1,Transparency^2)`, a 3-stud refracted displacement,
  projected and attenuated by `clamp(1-4*(uv-.5)^2)`. Two biased depth samples
  reject foreground distortion: `clamp(min(depthA,depthB)*500-viewZ)`.
  The refracted scene is tinted by `mix(1,Color3,clamp(2*partAlpha))`, mixed
  with lit glass by remapped alpha, then grazing reflection is mixed in.
  It also preserves/adjusts scene alpha by a colour-energy ratio. Porting
  this requires a dedicated scene-reading pass; current transparent pass
  uses the depth texture as an attachment and cannot also sample it.
- WangFallback exists only as FS.0, unlike WangFS.0..3. At `0x144c9e4dd`,
  Studio first requests WangFS, then selects WangFallbackFS if unavailable.
  **It is not the ordinary distance-LQ variant**: WangFS.0 still samples the
  Wang index atlas. FallbackFS samples DiffuseMap directly at VARYING0,
  colour-mask alpha then square, no normal/specular maps, vertex lighting
  plus vertex specular and light grid. Its VS.0 passes TEXCOORD0 unchanged.
  No fallback branch was forced on rustudio's capable GPU.
- `0x144c3c060` generated-UV branch tests an empty data pointer
  (`param_4+0x2d8 == 0`, with param_4 nonnull; field identity provisional). The alternate branch copies
  authored UVs. Generated branch expands six faces (or the decal face), calls
  `0x144c4af70` / `0x144c4ae20` per face. `0x144c4a240`: Texture offsets are
  OffsetStuds / StudsPerTile; other decals read +0x278 directly. In
  `0x144c4af70`, Texture scale is face-size / StudsPerTile; another decal
  uses decal scale times face-size / original part-size. These branches
  still need typed object identification and integration, not guessed UVs.

Validation: release build passed (existing warnings); real pipelines were
initialized in headless captures. New reproducible `make_materials2_place.py`
and corpus `materials2` test glass overlap and ForceField on sphere,
untextured MeshPart and textured MeshPart. Matched 863x675 captures at 5s:
material-row crop [170,280:690,390] RGB MAE 17.263 before, 4.668 after.
ForceField shells match closely; glass still visibly differs. Capture isn't
phase-locked and does not validate the provisional pulse cadence. Studio
was opened/closed in an offline Studio's new_instance/close_instance only.

Remaining: full glass scene-depth compositor and sorting/state parity;
ForceField clock producer and non-default coverage byte; CPU distance /
graphics-quality HQ-LQ selector and full LQ vertex lighting; WangFallback
capability selection; generated mesh/decal UV implementation. No parity or
completion claim for those paths.

### Round 28 sky regression investigation (2026-11-06)

This corrects the earlier claim that the Place B grey sky is Atmosphere haze.
The round-27 Place B-water FIDCAP class inventory contains **no Atmosphere**;
its built place likewise has none. A temporary renderer trace on that built
place reports `sky_size=1024`, `params.w=1`, `atmos=(0,0,0,0)`, custom-sky
`tint.w=0`. Thus `sky_color_lod` returns the sampled texel before haze.
The trace was removed after the investigation.

The actual saved Sky uses Content twins: sides 6444884337 (blue above,
white horizon, grey below), bottom 6444884785 (grey gradient), top
6412503613 (plain blue). The cached images really have those colours.
Round 26 ignored these saved twins; 0a673f4 made them win over reflection
defaults (`Document::prop`). The old cloudy reference and current grey
render therefore use different sky images. Restoring the old score by
ignoring the saved faces would discard this real property support.
A fresh offline an offline Studio instance reads back the saved bottom id and no
Atmosphere, but still shows cloudy sky. The precise reason its renderer
uses different images (asset availability versus loading/update behavior)
remains unresolved; this investigation does not claim to have measured
successful loading of those custom faces in Studio.

**One independently confirmed port error fixed.** 0x144a23390 squares
Atmosphere.Color and calls 0x144a82df0. The latter multiplies by sky mean
irradiance and by the average of renderer fields +0x3c8 / +0x3d8. These
are the squared sky levels c0/c1 (the globals SkyGradientTop/Bottom).
`atmos_haze_cube` now uses `0.5*(c0*c0+c1*c1)` instead of the fitted 2.65.
The raw custom sky sampling and the 79a70d0 undimmed non-Atmosphere night
path are unchanged. The old ATMOS_HAZE_K constant is retained as obsolete
history because mech.rs was append-only for this investigation.

Re-read executable constants at 0x14919f090=1.98,
0x148aa58cc=0.02, 0x148ade930=0.6, 0x148a6d730=0.5,
0x1491f43f8=-1.442695 and 0x1491f8b18=-0.14426951: the existing
Haze A/B, natural-log conversion and density units were correct.
AdvSkyFS.0 confirms the directional squared-axis irradiance blend and
exp2 transmittance already implemented. Its VS also multiplies texels by
the sky levels; reproducing that separately from the raw reflection cube
still needs care (do not double-apply env_reflect's existing sky levels).
No speculative shared sky/reflection multiplier was retained.

**Night validation limitation.** Re-ran the existing 02:48 / Haze 1.9
calibration. Studio shows its dark fallback, while rustudio can load the
custom storm faces (15542516997 etc.). Replacing URIs with local PNGs and
reassigning the legacy Sky properties in Studio did not establish matched
loaded faces. Consequently original custom-night pixel parity is **not
confirmed**, and this is not a completed fidelity repair. The recovered
Haze curve is unchanged; the corrected CPU fog colour is dimmer at night.

Evidence: `~/.cache/rustudio/agents/r28/` contains fresh decompilations,
Studio capture/log, the diagnostic benchmark and night captures; scratch
commands/logs are `/tmp/r28-*`. REA opened the supplied PE with SHA-256
81be5bc2916ba979e0ecc68b5fd039a48821765c6e9a7bcfd8d27ad877cf1692;
Ghidra used the supplied dc.sh with Java 27. These are static decompilation
and bounded runtime observations, not proof of complete renderer parity.

Round 28 render scores (round 27 → 28): water 48.5 → 48.5,
terrain 65.6 → 65.6, newer 71.8 → 72.0, Place B 67.3 → 67.3,
Place D 58.1 → 57.6. These are not recovered round-26 scores.
The new run's Place B Play benchmark is 71.6 fps (1% low 24.2),
versus 66.3 in round 27 and 91.8 in round 26; Edit is 447.6 fps.
An earlier diagnostic run under concurrent probes gave 52.0 fps, with
`lightgrid` gathering at 0.03 ms/frame. Round 26's Play/viewport sections
were 5.25/4.68 ms; round 27's were 7.06/6.79 ms. OBS replay buffering,
the host's own Studio, wallpaper decoders, and other rustudio work
were active (load averages rose from 2.79 to about 9 during investigation).
This does not isolate a GPU pass regression; CPU Play/UI costs and load
are material confounders. No shader/grid performance workaround was added.

Validation: final `RUSTUDIO_NO_AUDIO=1 cargo build --release` succeeds
(existing dead-code warnings plus the now-unused historical ATMOS_HAZE_K).
Existing lightgrid tests: 3 passed, 3 ignored. `git diff --check` passes.
All an offline Studio process trees started by these probes were stopped; the user's
Vinegar Studio was not touched. No push was made.

### Materials3 continuation (2026-11-06; partial, not full parity)

Scratch/evidence: `~/.cache/rustudio/agents/materials3/`. REA opened the
specified 0.746 PE, SHA-256
`81be5bc2916ba979e0ecc68b5fd039a48821765c6e9a7bcfd8d27ad877cf1692`.
Fresh Ghidra output is in `dc/`; `clock-stores.txt`, `runtime.log`, build
logs, the before binary and matched screenshots are retained there.

**ForceField clock recovered and ported.** `0x144a74d90`, specifically
`0x144a74ebd..0x144a74f1b`, adds renderer/context `+0x20` (double frame
step) to renderer `+0x748` (double elapsed time), converts the result to
float, computes `abs(cos(0.3*t)*cos(t))`, and stores it at renderer
`+0x324` = FogColor_GlobalForceFieldTime.w. `0x148aa58d8` is float
0.30000001192092896; `0x1478c0290` jumps through IAT `0x1489f75d0`, whose
import is **cosf**, not sinf. `0x148aa5970` clears the sign bit. With
DebugRenderingSetDeterministic (`0x14dbc1c30`) enabled, this writer sets
0.5 instead. ForcefieldVS.3 does not scroll UVs with time: FS compares the
sample's red phase against this global. Thus there is no one-second pulse
period. rustudio now uses this cosine product and a clock owned by each
Renderer, continuous across scene rebuilds/Play, instead of process-global
one-second sawtooth. Wall elapsed time approximates Studio's accumulated
frame steps during active rendering; suspension/frame-step clamping and
initial renderer phase are not established. Deterministic flag wiring is
not implemented. The sampled red is converted back with the actual sRGB
transfer curve instead of the previous gamma-2.2 approximation; encoded
phase interpolation still differs from a native UNORM texture sampler.

**Glass scene-read path implemented.** The GlassTransparentFS.8 SPIR-V
from materials2 and scene bindings `0x144aab710` remain the evidence.
The renderer now resolves opaque HDR colour before see-through draws and
resolves the nearest MSAA depth sample into a separate R32Float target.
Glass can sample those immutable snapshots while depth-testing against the
original attachment. Refraction uses eta `mix(.66,1,(1-partAlpha)^2)`, the
three-stud displacement and screen-edge attenuation. Two one-pixel-biased
depth tests reconstruct clip-w from reverse Z and reject distortion crossing
foreground geometry with `clamp(min(viewZA,viewZB)-glassViewZ)` (Studio's
copy stores viewZ/500, so its multiplication by 500 is implicit here).
Tinted scene is mixed with lit glass by remapped material alpha, then the
existing grazing reflection and additive specular terms are applied. The
result goes through fog and replaces the scene pixel. Opaque Glass skips
scene sampling. Only visible blended Glass triggers the extra split/depth
resolve; ordinary transparency keeps the previous pass count.

Limits: this preserves existing centre-distance back-to-front sorting,
not newly proven Studio sorting/state. All Glass shares the opaque snapshot;
other transparent objects and terrain water are absent from that snapshot.
Scene-alpha energy-ratio preservation and Studio's precise fog alpha/state
are not ported (the viewport HDR composite uses alpha 1). GL3's
GlassTransparentFS.3 has no scene inputs; backend selection remains to be
modeled. This is a functional refraction port, not complete glass parity.

**LQ semantics partially corrected.** DefaultUnifiedTiledFS.0 has no normal
map input; it uses geometric/vertex normals and AmbientColorNoIBL /
SkyAmbientNoIBL instead of the HQ environment BRDF contribution. rustudio's
existing low-quality path now leaves its geometric normal intact and omits
the HQ irradiance-cube addition. Its diffuse far-tiling implementation is
unchanged. CPU quality-level/distance selection is **still unresolved**:
`env_spec.z` currently chooses the path by lighting technology, which is not
proof of Studio's CPU selector. Full LQ vertex diffuse/specular lighting
also remains. Fresh `dc/0x144aac960.c` and `0x144aad2a0.c` trace material
shader cache/flag assembly toward `0x144aab710` / `0x144c9f1e0`; they do not
establish a distance threshold. No guessed distance cutoff was installed.

**WangFallback and generated mesh/decal UVs remain unported.** Re-read
`0x144c3c060`, `0x144c4af70`, `0x144c4ae20` and the existing fallback
selection evidence `0x144c9e4dd`. The generated branch requires a nonnull
fourth object argument whose +0x2d8 pointer is empty; null fourth argument
selects the authored branch. `0x144c4af70` also performs a runtime Texture
class check via `0x1410139b0`; Texture uses face-size/StudsPerTile, the
alternate decal uses decal-scale*face-size/original-size. This is not evidence
that arbitrary untextured MeshParts should lose their authored UVs. Typed
identification/dispatch remains necessary. WangFallback remains a capability
fallback, not a distance-LQ choice; no capable-GPU default was changed.

**Validation.** `RUSTUDIO_NO_AUDIO=1 cargo build --release` succeeds with
existing warnings. Actual GUI capture initializes the new WGSL and pipelines
and runs without validation errors; `git diff --check` passes. No audio was
enabled, no game repository was modified, and all reference Studios started
here were closed with an offline Studio instance lifecycle plus `stop_host` for the
owned host. The host's own Studio was untouched.

New `make_materials3_place.py` / corpus `materials3` provide a checker
backdrop, three glass opacities, overlapping glass, a foreground rejection
bar, and ForceField on a sphere / bundled head mesh with bundled phase
texture. Use `rbxasset://avatar/heads/head.mesh`: the initial
`rbxasset://fonts/head.mesh` experiment failed in Studio and was replaced;
those initial captures are not the final results. Final rustudio asset audit
reports both bundled mesh and phase texture loaded, and final Studio log
has no failure for either. Studio still fails to download Glass's
7546645118 / 7547304948 maps. This limitation is recorded in corpus.json;
rustudio asset loading was **not** disabled or modified to fit that fallback.

Matched 863x675 screenshots at 5s (RGB MAE, byte range 0..255):
- Existing materials2 crop x170:690,y280:390: 4.681 -> 4.587;
  glass-only x170:385,y280:390: 7.517 -> 7.323 (before clock change).
- Final materials3 crop x170:690,y275:400: 9.207 -> 8.045;
  glass-only x170:465,y275:400: 11.319 -> 9.271.
The latter's ForceField animation is not phase-locked, and missing cloud
Glass maps prevent a claim of matched material assets or full parity. The
clock formula is established statically, not by these single-time scores.


## Skybox brightness (Sky pass)

2026-11-08 investigation. **Partial result: the proposed 0.33 texel multiplier
is not reproduced. Do not install it as a recovered Studio constant.** Fresh
static evidence establishes white mesh colours and the same Lighting sky
colours used by AdvSky. Runtime reads verify their time dependence and
Brightness independence. The supplied screenshot discrepancy remains unexplained.
Evidence retained in `~/.cache/rustudio/sky-bright-re/` (decompiled functions,
assembly, unbuffered memory sweep script and results). Only this document was
edited in the checkout.

### Static draw and input chain

- Shader strings SkyVS `0x149209c94`, SkyFS `0x149209c9c` lead to plain
  Sky draw `0x144c11e50` (direct caller `0x144a7c54b`). It selects SkyFS or
  SkyLinearFS, then calls six-face drawing helper `0x144c12f60`.
- Sky constructor `0x144c0f8e0` calls mesh builder `0x144c10260` with
  subdivisions 3 (main mesh) and 1 (secondary mesh). Vertex stride is 24:
  position float3, packed colour at +12, UV float2 at +16.
  `0x144c10318` sets the packed colour to **0xffffffff**, copied unchanged
  to every generated vertex. Thus normalized `COLOR0 = (1,1,1,1)`;
  Ghidra prints its float bit reinterpretation as `-NAN`, which is not a
  floating-point colour calculation. Static input layout is `0x14dc84540`.
- At `0x144c135b3..0x144c13617`, helper `0x144c12f60` fills CB1[12].rgb
  from Sky renderer +0x158/+0x15c/+0x160 and CB1[13].rgb from
  +0x164/+0x168/+0x16c; both alpha components are 1. It can override both
  RGBs to white when its tenth argument is false or flag `0x14dc84490`
  is enabled. Plain draw supplies tenth argument 1.
- Setter `0x144c14dd0` copies those RGBs from input +0 and +0x40.
  Its caller `0x144a2ba9c` in `0x144a2b450` supplies Lighting +0x160
  (decompiler's `undefined2 *param_2 + 0xb0`). Therefore CB1[12] =
  Lighting +0x160, CB1[13] = Lighting +0x1a0. These really are the AdvSky
  colours; Lighting +0x16c (k) is **not** either plain-sky input.

### Formula and scope

For encoded sampled texture RGB T, transformed mesh height y, and ordinary
colour-enabled draw:

```
q = clamp(y / 1700, 0, 1)
c0(t,s) = lerp(table_c0_at_s0(t), table_c0_at_s1(t), s)
c1(t,s) = lerp(table_c1_at_s0(t), table_c1_at_s1(t), s)
vertexColor = (1,1,1,1)
CB1[12] = (c0,1); CB1[13] = (c1,1)
preExposureLinearRGB = (T * lerp(c1,c0,q))^2
```

Here t is ClockTime and s is EnvironmentDiffuseScale. The piecewise-linear
17-keyframe tables are the previously recovered `mech.rs SKY_LEVELS`, documented
above. Brightness, ColorShift_Top and GeographicLatitude do not appear in this
input copy or mesh builder. At 16.8 h both tables give white regardless of s:
**preExposureLinearRGB = T^2**, with no 0.33 factor. Exposure and tone mapping
remain subsequent operations and must not be inferred from displayed RGB as
though it were shader output.

Default sky uses the same generated white mesh; texture selection differs.
Stars and celestial sprites have separate draws: `0x144c14dd0` stores
CelestialBodiesShown at Sky+0x17c and clears star collections when false or
StarCount is zero. It stores sun/moon directions and derives separate sprite
colours. An exact star/sun/moon brightness formula was not completed here.
SkyboxOrientation is stored at +0x170..+0x178 and handled in `0x144c12f60` by
rotation construction `0x143179850`; this changes sample direction and transformed
height, not vertex-colour magnitude. Atmosphere selects the AdvSky path described
above, which adds haze/glare to its squared tinted texture. This investigation
does not establish every feature-flag/backend selection condition.

### Runtime verification

Started an owned hidden offline Studio, opened the existing
`sumpf_shadowmap.rbxlx`, removed Atmosphere, set latitude 30, diffuse scale .45,
ColorShift_Top (180,205,190), then swept ClockTime and Brightness via a Studio MCP bridge.
Linux PID 1013119; Lighting object `0x7f573406ba00`, located by its unique
adjacent Brightness=1.1 and EnvironmentDiffuseScale=.45 floats. Read
`/proc/1013119/mem` **unbuffered**; buffered repeated short reads initially
returned stale values and were discarded. ClockTime 16.8 quantizes to
16.79972267150879. Results below repeat identically for Brightness 0, 1.1 and 3:

| ClockTime | observed c0 | observed c1 | observed k | table prediction |
|---|---|---|---|---|
| 8 | (1, 1, 1) | (1, 1, 1) | (0.75, 0.75, 0.75) | agrees to float precision |
| 12 | (1, 1, 1) | (1, 1, 1) | (0.75, 0.75, 0.75) | agrees to float precision |
| 16.8 | (1, 1, 1) | (1, 1, 1) | (0.75, 0.75, 0.75) | agrees to float precision |
| 18 | (0.44499999, 0.245, 0.094999999) | (0.40000001, 0.30000001, 0.2) | (0.1575, 0.1575, 0.1575) | agrees to float precision |
| 22 | (0.074117646, 0.074117646, 0.074117646) | (0.074999996, 0.074999996, 0.074999996) | (0.16363636, 0.16363636, 0.16363636) | agrees to float precision |

This verifies CPU lighting inputs, not a white-sky screenshot or GPU constant
capture. At 16.8 h the shader predicts linear (0.62,0.75,0.79) for the supplied
unscaled reference texels; the supplied Studio measurement (0.062,0.083,0.094)
would instead require encoded multipliers (0.31623,0.33267,0.34494). Neither
white vertex colours nor the observed CB source colours provide those factors.
Consequently step 3's required reproduction is **unresolved**, not verified.
Potential next evidence is a GPU capture tying the exact roof-hole pixel to its
draw, bound face resource/mip and postprocessing state. No assertion that the
screenshots sampled identical GPU texels is independently established here.

Tool limitations encountered: the first an offline Studio start without a place had no
command bar; opening the existing place resolved that. Full decompilation of
`0x144a7a9e0` exceeded Ghidra's response buffer; its direct call site is known
from callscan, but its complete pass-selection logic remains unread. A temporary
DB lock was avoided using a private `/tmp` project; `~/code/rs-re-ghidra` was
untouched. a Studio MCP bridge refused close_instance because the shell-started Studio was
not in its agent lifecycle registry; only its owned Linux PID was terminated.


## Atmosphere live-input correction (2026-11-08)

Hidden offline an offline Studio, sumpf_built.rbxl, ShadowMap, ClockTime 16.8,
Brightness 1.1, EnvironmentDiffuseScale .45; camera and no-post state from
sumpf_ref/sky_nopost. Read `/proc/1120165/mem` unbuffered. AdvSky at
0x7fd9a1aa69e0; renderer at 0x7fd9a2543cd0 points to it through +0x648.
Renderer+0x690 → +0x118 → byte +0x90 is **5**, so 0x144a82df0 takes
the direct Color² branch. Renderer+0x308..+0x324 and multiple CB0 copies
agree on FogParams/FogColor. Do not infer that this byte is Technology;
its type has not been recovered.

- FogParams: (0, .1, -.00448922813, 0).
- FogColor: (.141730115, .251964658, .147697046) = (96,128,98)²/255².
  Rustudio previously used approximately (.02789, .06412, .04061).
- color0 = color1 = (1,1,1); fogOffset = (-.461662322, 1.75).
- glare = (13.5402098, 8.29252625, 12.2744532, 0).
- AdvSky+0x4b0 contains six float4 irradiances, stride 16; +0x510 is
  mean (.196773276, .256541044, .277928442). The fourth components
  are about 1.021435, not colour channels.

| axis | Studio RGB | rustudio RGB, source frame |
|---|---|---|
| +X | .184478 .244065 .262493 | .187924 .245310 .263557 |
| -X | .255819 .314365 .335615 | .256034 .311148 .330305 |
| +Y | .382456 .506673 .553859 | .379948 .501311 .547873 |
| -Y | .001443 .001448 .001446 | .001242 .001244 .001244 |
| +Z | .209110 .275777 .296939 | .205520 .268908 .287587 |
| -Z | .147335 .196918 .217218 | .149937 .199023 .219239 |

Draw 0x144c19ed0 copies those six float4s into AdvSkyFS Params directly.
They remain in the source sky frame, despite SkyboxOrientation (0,90,0).
Rustudio's reflection irradiance was already rotated; globals now undo that
rotation for Atmosphere. Quarter turns are exact permutations; arbitrary
rotations reconstruct from the existing ambient cube and are approximate.
Exact general rotation would require retaining pre-rotation irradiance in
viewport's sky preparation (outside this change's ownership).

The fix removes the legacy mean/level multiplier from desktop Atmosphere
haze and restores its source-frame irradiance. No fitted constants.
The transmittance and glare formulas needed no change.

| sky_hole, display RGB | Studio | before | after |
|---|---|---|---|
| no post, sky camera | 40.25 68.68 57.76 | 19.15 32.21 32.05 | 35.92 63.68 52.06 |
| full scene | 19.54 49.03 32.85 | see prior captures | 19.08 49.63 33.91 |

Full scene is within 1.1 display levels. No-post sky still differs by
4.3/5.0/5.7 levels; exact parity is not established. The residual includes
small measured irradiance differences and the previously documented base
sky mismatch. Those must not be hidden with a haze multiplier.

This supersedes the r28 claim that the legacy FogColor branch completes
the desktop port. Place B's inventory still has no Atmosphere, and the
Place B custom-night comparison still lacks matched loaded Studio faces;
its old pixel measurements do not validate the legacy multiplier.
Default-sky night dimming remains as before. New night parity is untested.

Raw inputs, scripts, captures and self-test outputs:
`~/.cache/rustudio/atmos-live/` and `lightov/edit/{s,e}_atmos_*`.

Validation: release build succeeds. Isolated final self-test is **62/64**;
only `perf` and `fidelity-place_a` (zero concurrent enemies) fail, matching the
baseline. A first run alongside two capture processes gave a blank
union-material-density frame; the isolated rerun passes that check.
Fresh REA analyze_function(0x144a82df0) timed out after 300 seconds;
static branch details above come from the existing r28 decompile, checked
against the live renderer pointer chain and FogColor. The native session
was closed. Only the two Studios started for this investigation were closed.
