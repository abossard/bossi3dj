# Building the Blender scenes

What each control does is in [README.md](README.md). The pass rules for images are in [the visual check](../docs/research/synthwave-visual-check.md). Every rule below cost at least one lost hour in November 2026; the retrospective has the receipts.

## Source of truth

- `scenes/synthwave_planet.blend` is generated: `make blender-rebuild` runs `planet_proto/build_planet.py --graft` on `synthwave_pyramids.blend` (5 to 11 s headless). Change the build script, never only the live scene.
- A live patch through the MCP is an experiment. It is done when the same change is in the build script, the file is rebuilt, and the check passes on the rebuilt file. Commit after that, not before.
- `synthwave_pyramids.blend` (the island) has no builder any more: its script lived in a scratchpad that a reboot wiped. Edit it in Blender or through the MCP, and keep changes small.
- The `.blend` files point at their scripts and textures with `//` relative paths. `make blender-paths` lists them; `tools/blend_paths.py -- --fix` repoints paths from an old checkout.

## The loop

1. `make status`. One Blender, the lock free or yours, load low enough if you will read fps.
2. Edit the build script or runtime. Run the pure checks that need no Blender first (`make verify`).
3. `make blender-kill`, `make blender-rebuild`, `make blender-open`.
4. Health: `exec(open(bpy.path.abspath("//../review/health.py")).read())` through the MCP. Fix every entry in `problems` before going on.
5. Numbers: `review/ground_check.py`, `review/cut_jobs.py` (M1, M2), the fps line of `make status`.
6. Images, only for the cameras whose material, geometry or camera changed: a `review/*_jobs.py` matrix, `review/sheets.sh`, then the `shot-reviewer` subagent with the rubric.
7. Record the round in `docs/handover/` (what changed, numbers, verdict file).

## Pitfalls

| Symptom | Cause | Rule |
|---|---|---|
| Syphon stops, fps 0, grabs show an old camera | the 3D view left camera view | check `health.py` before every grab; the user keeps camera view |
| Camera jumps back after you set it | Magic, the page or another session holds or re-sends `/vj/cam` | one holder at a time; release every hold on the 9210 page before you stop |
| Black Syphon frames at the right size and rate | sender publishes an empty texture | check pixel content (mean, variance) of a grabbed frame, never only size and fps |
| Image upside down in Magic but fine in a Metal read-back | flip validated on the wrong consumer | validate output in the consumer that the show uses |
| Scene values wrong after reopening | live `/vj/*` values were saved into the `.blend` | reset to defaults before saving; `health.py` lists `off_default` |
| Value overdrives the scene (`/vj/fog` 5.75) | sender not clamped | the Magic generator clamps to the range in `osc/CONTROLS.md`; the runtime's `RANGES` match |
| Driver does nothing or half of it | expression over 256 characters is cut silently | chain drivers; `health.py` lists `long_drivers` |
| Everything re-scatters each frame, fps halves | lookup by name prefix (`Pyramid_*`) caught a helper object | look objects up by collection, never by prefix |
| Node cycle after relinking sun or moon | links created before the old targets were captured | capture targets first, then create nodes |
| Fog flickers, shows blocks or stops at 8 km | EEVEE volume froxels and clip | camera-following fog box, 16 slices |
| Six draw handlers after six rebuilds, fps falls | old handlers survive a file reload | every module replaces its previous instance through `driver_namespace` (see `syphon_out.start`) |
| "Timer is dead" although it runs | `is_registered` on a bound method is always False | keep the function object you registered |
| Runtime not running after reopen | Auto Run Python Scripts is off for the file | `make blender-open` passes `--enable-autoexec` |
| OSC arrives but only some messages apply | padding bug class in an OSC parser; or an orphan instance still holds udp 9201 | send five known messages and count them at the bridge (`make lab` page); `make status` shows a second Blender |
| MCP call returns nothing | the add-on wants `result` to be a dict | always assign a dict to `result` |
| A sheet shows banding or a grid | montage scaling | sheets are for triage; judge fine detail on the full-size frame |
| Texture looks washed out | float TIFF or EXR loaded as sRGB | set the colour space when loading data maps |
| Lines on the ground that are not the drawn mesh's edges (a shader lattice, a projected grid, a proxy mesh's edges) | user, 2026-11-11: no dummy wireframe, ever | lines only as the real edges of the drawn mesh, from sunset, or none |

## Measuring fps

- Drawn fps is Syphon frames per second (`fps` in `make status`), not the frame counter.
- Freeze the clocks, hold the OSC inputs, compare A and B back to back in one run, three rounds, base cells interleaved. A moving camera alone varies by 30 %.
- Skip the first cell after start and the frame after a cut.
- What paid off on the planet (day mean 18.8 to 59.2 fps): render border on the camera frame, one Attribute node per shader tree (`shader_dedupe.py`), a day-only world (`day_world.py`), fixing the prefix lookup. Tested without gain: bloom quality, backface culling, overlap, water LOD, sea resolution, world probe.
- Build features first, tune after. The first tuning pass on the island was thrown away with the island.

## Syphon and OSC

- OSC in: `blender_osc_bridge.py`, a `bpy.app.timers` callback, no threads, udp 127.0.0.1:9201. `/vj/<name>` lands in `scene["vj_<name>"]`, latest value wins. It answers `/lab/ping`.
- Syphon out: `scenes/syphon_out.py` publishes the camera-view viewport as `CAM_OUT - Blender`, 1920x1080, without a CPU copy. It needs `syphon-python` and PyObjC in `~/.local/lib/python3.13/site-packages` and the Metal backend.
- Magic sends one float per datagram and only on change; unchanged values are sent during the first 2 s after a project loads. Load the Magic project after Blender is up.
