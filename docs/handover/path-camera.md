# Path camera: design (phase 1)

The direction is the user's (STATE.md, "Decided by the user", 2026-11-12). This note proposes how to build it. Nothing here is built yet; contract, Magic and page wait for the user's yes.

One camera, the **Path Camera**, replaces the 12 shots of the Planet. Where it goes is three choices: a path type, a target and a height. It runs on the one streamed terrain from the terrain test ([terrain-test.md](terrain-test.md)).

## 1. Contract rows (proposed)

| Address | Wire | Default | Label | Plain |
|---|---|---|---|---|
| `/vj/path` | int 0..3 | 0 | Path | Picks how the camera moves: 0 orbit the target, 1 follow the land, 2 rise and descend, 3 vantage with a slow push. |
| `/vj/target` | int 0..6 | 0 | Target | Picks what the camera looks at: 0 pyramids, 1 lake, 2 river, 3 coast, 4 moon, 5 sun, 6 planet. |
| `/vj/height` | float 0..1 | 0.3 | Height | Lifts the camera from just over the ground (0) to space with the whole Planet in frame (1). |
| `/vj/blend` | float 0..1 | 0.5 | Fade Time | How long a change of path or target flies; 0 cuts at once. |
| `/vj/takeover` | float 0..1 | 0.33 | Takeover Pause | How long a control you touched stays yours before the music steers it again. |

- `/vj/blend` keeps its address and gets the new label; it already means "0 cuts, else fly".
- Scene scaling (Blender): height on a log scale, 10 m to 64 km over the ground (default 0.3 is about 140 m); blend 0 to 60 s; takeover 0 to 60 s (0.33 is 20 s).
- The two index rows get `stops` with the names, so QLC+, the page and Magic show the same seven target names.
- Kept as they are: `/vj/cam_speed` (path speed), `/vj/energy`, `/vj/hit`.
- Gone on the Planet: `/vj/flight`, `/vj/boost` (the Flight becomes path 1 at a low height).

## 2. `/vj/cam`, `/vj/cam_auto`, the 12 shots and their terrain sets

Today `/vj/cam` 0..11 cuts between 11 fixed shots and the Flight; each fixed shot brings its own terrain set (`LOD_Anchor`, `LOD_PATH_SETS` in `build_planet.py`), and palms and flocks are placed round that set's anchor. `/vj/cam_auto` is read by Godot only.

| Option | What it is | What it breaks |
|---|---|---|
| A, remove (recommended) | Blender stops reading `/vj/cam`, `/vj/cam_auto`, `/vj/flight`, `/vj/boost`. Both cam rows stay for Godot (group "Godot only"). The shots, their sets and the anchor leave the build; palms and flocks follow the stream. | Magic: the auto cutter, `CamCount`, `Flight`, `Boost` go; `show.magic` regenerated. QLC+: one channel per Blender address in contract order, so channels from 8 on move; fixture and workspace regenerate, a desk patch made by hand must be redone (QLC+ was never run live, so none exists yet). Page: the shot buttons and the Flight group go. Handbook and README: the 12 shot pictures and the camera chapter are rewritten. Tests: director check 6 and the per-camera tests change. |
| B, shots as presets | `/vj/cam` N sets path, target and height to a stored triple; the sets go. | Same build work as A, plus two ways to steer one camera that fight (last change wins). The old shots only come back approximately. |
| C, keep both | Fixed shots stay; the Path Camera is shot 12. | Nothing today. Keeps three terrains, the per-camera set swaps and the cut glitches the user saw on 2026-11-12. |

## 3. Takeover: who knows a touch, who times the pause

The rule is **Takeover** (GLOSSARY): any touch makes the control the user's; after a pause with no touch the music steers it again. Magic decides what the music means; the scene only decides whose value to take. That is input order, not music logic, so it may live in the scene.

| Source | Reaches | Knows a touch | Times the pause |
|---|---|---|---|
| Scene page (9210) | the Blender bridge | the bridge (the page already holds a control with H) | the bridge |
| QLC+ / desk, Art-Net 6454 | the Blender bridge, not Magic | the bridge (it applies only changed channels, so a change is a touch) | the bridge |
| MIDI controller | Magic (MIDI learn on the control Globals) | Magic | Magic |
| Magic's own controls | Magic | Magic | Magic |

- The bridge: after a page or Art-Net touch it applies that source's value and keeps Magic's latest value for the address without applying it. When `/vj/takeover` has passed since the last touch, it goes back to Magic's value; a path or target change flies with `/vj/blend`, a height change glides.
- Magic: per steered address, a Global holds the clock of the control's last change; `Out` is the control while that is newer than the pause, else the music's value. Same pause, from the same `Takeover` Global that Magic sends as `/vj/takeover`.
- So two timers, one length. MIDI could go to the bridge instead to have one timer, but then the scene would need a MIDI port and Magic would lose MIDI learn.

## 4. A flight between paths: pure in time, steady on the terrain

- Every path pose is a pure function: `pose(path, target, height, speed, t)`, in a module without bpy (like `director.py`), with ground heights from the map, as the terrain test's script did.
- A change starts a blend: start pose and velocity, start time, the new path. The pose during the blend is a function of those and `t` (the director's rise, traverse and descend phases, quintic ease, Hermite carry of the start velocity). A change mid-blend starts a new blend from the current pose; nothing is integrated frame by frame.
- Never under ground: every sample keeps 10 m over the highest ground from 20 m behind to 80 m ahead (the terrain test's skim rule, 10.0 m at least on every frame), and the hump between the ends keeps `CLEAR` over the ground.
- The stream keeps up: ground speed is capped by the ground's flow past the camera (`FLOW`, 1 rad/s of speed over clearance), so the camera never outruns the selection near the ground.
- The hand-over band (8 to 12 km, `GLOBE_BAND`): the height curve is monotonic through rise and descend, so the band is crossed once and never hovered in; the near clip grows with height so the Planet's skin is never cut by the near plane. Paths whose height sits in the band (height 0.76 to 0.81) get a check of their own.
- Moving targets (moon, sun): the blend aims at the target's live pose at its end, as the director does for a moving shot today.

## 5. Build plan

| Step | Work | Check | Rebuild |
|---|---|---|---|
| 1 | Contract rows, `make osc-sync`, bridge scaling | `make test` | 0 |
| 2 | Path module (no bpy): 4 paths, blends, clearance | `make verify` gets a path check: all 28 path and target pairs at 5 heights over 120 s, and every pair of changes: least clearance over the map, worst ground flow, worst turn rate, band crossings | 0 |
| 3 | Targets in the build: 7 named points (pyramids = the hero pyramid, lake, river, coast nearest the valley; moon and sun live; planet = centre); if option A, the shots, sets and anchor leave the build | start check lists 7 targets, each probed on land or water; health check green | 1 |
| 4 | Runtime: the Path Camera on air, stream always on, palms and flocks round the stream | terrain-test script reused: a 3 min run over every path, target and change, the same per-stage table (frame time with load and `fps_trustworthy`, clearance, lag, pops, off-output holes) | 0 (files load from disk) |
| 5 | Takeover in the bridge and in Magic; Magic's music steering of path, target, height | bridge tests with a fake clock; Magic expression tests; the Art-Net sender test; a test sender on 19202, never on 9201 | 0 |
| 6 | Page, QLC+ fixture, handbook, README regenerate | page test, `make qlc-fixture`, `make test` | 0 |
| 7 | Recording for the user: 3 min with show defaults, a scripted music stand-in and two touches, `docs/video/path-camera.mp4` | load and `fps_trustworthy` stamped; the user judges | 0 |

At most 2 rebuilds: one planned (step 3), one spare.

## 6. Questions for the user

1. The 12 fixed shots: remove them (A), keep them as presets (B), or keep them next to the Path Camera (C)? Recommendation: A, the one way to "simple again" and one terrain.
2. Takeover pause: how long does a touched control stay yours? Recommendation: 20 s, then it flies back to the music with the fade time.
3. What may the music change by itself? Recommendation: height and speed all the time (down on builds, up in breakdowns), path and target on drops and every 16 bars.
4. The targets: one fixed place each (the lake, river and coast nearest the pyramids' valley), or the nearest one to wherever the camera is? Recommendation: fixed places, so a name always shows the same place.
5. Height range: just over the ground (10 m) to the whole Planet in frame (64 km), on a log fader? Recommendation: yes; the middle of the fader is then about 800 m.

## Phase 2: steps 1 to 4 (2026-11-13)

The user chose option A, a 20 s takeover pause, music on height and speed always and on path and target at drops and every 16 bars, fixed target places and the log height (STATE.md, "Decided by the user").

### What is built

- Step 1, contract (2c370ae): `/vj/path`, `/vj/target`, `/vj/height`, `/vj/takeover`; `/vj/blend` is the fade time, 0 to 60 s; `/vj/flight` and `/vj/boost` are gone; `/vj/cam` and `/vj/cam_auto` are Godot only, so the island scene has no camera control any more. The bridge no longer cuts cameras; an Art-Net index channel splits 0..255 into equal ranges. Group "Camera and Flight" is now "Camera".
- Step 2, `blender/scenes/path_camera.py` (no bpy): the four paths, the seven targets, the log height glide (0.5 e-folds/s), the phase as the one integrated number, changes as Director blends, a floor of 10 m over the ground. Its check is `blender/review/verify_paths.py` (moved there in round 2) in `make verify`: every path with every target at five heights at speed 1 and at the top speed, 420 changes, four frame times, the cut.
- The Director (`director.py`) changed in two places, found by that check: a blend's duration now budgets the lens change (a doubling a second at most) and the view's bend toward travel on top of its turn; the bend follows the traverse's ease instead of the momentary ground flow, which dropped within one frame on short hops at 64 km (one frame turned 9.5 degrees). A third change came after the run: a new blend also budgets how fast the target's own view turns (orbit moon to orbit planet turned 75.8 deg/s, now 61.6; gate 60 times 36/30). verify_flight passes all checks (the full run before the third change; its blend and energy sections after it), verify_paths passes all checks.
- Step 3, build: four empties `PathTarget.<name>` (pyramids at the hero pyramid, the river of the old CAM_1, the lake of the old CAM_7, the coast of the old CAM_10); 5.6 km (lake), 13.9 km (river) and 8.5 km (coast) round the Planet from the pyramids. CAM_0 to CAM_10, their targets and paths, the per-camera sets and the anchored land and water are out of the build; the system and proof cameras stay. Props and the flamingo flock keep `LOD_Anchor`, which the runtime moves under the camera. Two rebuilds: the second fixed the coast target (the hydrology's points are centre-relative).
- Step 4, runtime: `flight_rt.py` drives `CAM_RIG` with the Path Camera and runs the stream all the time; `planet_runtime.py` turns the sky under the viewer and moves the props anchor after 600 m of travel below 3 km.

### The run

`blender/review/path_camera_run.py`, 180 s at show defaults, 15 steps through every path and every target, ground to space; the step changes path, target or height, `/vj/blend` stays at 30 s, so most steps start while the last change still flies. Log: `blender/review/out/path_camera/run.json` (git-ignored). The run flew the Director before its third change. Video: `docs/video/path-camera-run.mp4` (git-ignored, 180 s, 3,896 new frames of 5,400, 14.2 MB), for the user, not judged here.

**Under load, not trustworthy**: load 125 at the start, 134 at the end, `fps_trustworthy` false; frame times say what this machine did under that load.

| Step (path, target, height) | Frames | Median ms | p95 ms | Worst ms | Over 33 ms | Least height over ground (m) | Height over sea (m) | Swaps | Pops over 0.05 | Shown lag median / max (m) | Frames waiting on near nodes | Frames in a blend |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 00 orbit pyramids 0.3 | 296 | 39.4 | 49.7 | 53.7 | 99 % | 138.6 | 255 to 340 | 51 | 0 | 4.8 / 11.3 | 0 % | 0 % |
| 01 orbit lake 0.3 | 238 | 47.6 | 79.6 | 201.7 | 91 % | 138.6 | 139 to 2754 | 29 | 1 | 262.1 / 2492.0 | 32 % | 93 % |
| 02 follow lake 0.3 | 227 | 48.9 | 80.4 | 134.6 | 100 % | 138.6 | 139 to 1329 | 24 | 2 | 71.0 / 997.4 | 25 % | 64 % |
| 03 follow river 0.3 | 283 | 37.1 | 75.5 | 263.9 | 61 % | 162.6 | 418 to 8904 | 43 | 3 | 655.0 / 5877.2 | 13 % | 100 % |
| 04 rise river 0.5 | 216 | 50.0 | 92.5 | 283.9 | 90 % | 56.3 | 117 to 1972 | 18 | 2 | 129.2 / 6761.7 | 32 % | 85 % |
| 05 rise coast 0.5 | 319 | 32.3 | 62.5 | 94.7 | 48 % | 56.3 | 117 to 12510 | 47 | 1 | 564.1 / 2549.1 | 3 % | 100 % |
| 06 vantage coast 0.5 | 328 | 30.2 | 66.6 | 219.4 | 39 % | 800.0 | 806 to 12441 | 28 | 1 | 325.4 / 5146.4 | 6 % | 93 % |
| 07 vantage moon 0.5 | 239 | 43.6 | 79.2 | 227.9 | 99 % | 800.0 | 806 to 3673 | 24 | 1 | 238.3 / 2508.5 | 14 % | 71 % |
| 08 orbit moon 0.7 | 247 | 41.7 | 96.2 | 170.2 | 93 % | 813.2 | 1079 to 4738 | 30 | 1 | 255.4 / 15549.4 | 12 % | 46 % |
| 09 orbit planet 1.0 | 382 | 28.2 | 49.4 | 94.5 | 26 % | 4617.4 | 4642 to 64342 | 19 | 0 | 1296.5 / 8398.8 | 1 % | 16 % |
| 10 vantage planet 1.0 | 422 | 28.2 | 35.6 | 47.3 | 11 % | 62044.0 | 62152 to 64281 | 5 | 0 | 665.3 / 4094.5 | 0 % | 55 % |
| 11 vantage sun 0.5 | 276 | 31.1 | 98.5 | 338.4 | 41 % | 825.9 | 1122 to 64000 | 16 | 2 | 205.9 / 44178.3 | 23 % | 34 % |
| 12 follow sun 0.2 | 301 | 39.8 | 65.1 | 144.8 | 60 % | 78.5 | 115 to 2940 | 27 | 0 | 127.6 / 898.8 | 3 % | 74 % |
| 13 follow pyramids 0.0 | 252 | 46.7 | 58.2 | 89.3 | 100 % | 66.7 | 139 to 203 | 18 | 0 | 5.1 / 25.9 | 0 % | 18 % |
| 14 rise pyramids 0.3 | 240 | 47.8 | 63.8 | 170.6 | 100 % | 43.4 | 114 to 205 | 18 | 3 | 5.4 / 83.8 | 0 % | 26 % |

- All 4,266 frames: median 40.0 ms, p95 69.8 ms. In the hand-over band (8 to 12 km), 230 frames: median 29.5 ms, worst 338.4 ms.
- The least height over the ground is 43.4 m (the map's conservative ground, a 3x3 max with the pyramids stamped in); at height 0 the follow path keeps 66.7 m because its 100 m window takes in the pyramids.
- Lag: during blends the shown terrain trails the camera by hundreds of metres (up to 44 km on the fall from space in step 11); a third of the frames of steps 01 and 04 waited on near nodes.
- Pops: 17 level changes in 3 minutes had a visible pop (over 0.05), 13 of them during blends.

### Failed or not verified (phase 2, see round 2 for what is fixed)

- **No night edges on the Planet.** The stream never drew them (its regular grid read as a lattice, Flight review 2026-11-12); they came from the fixed shots' sets, which are gone. The start check fails on that (`edge_guard` line share 0.0006, needs 0.03), everything else in it is green. Fix options: an irregular stream lattice like round 12 (vertex shift in `lod_stream`, then `make verify` for cracks and pops), or accept no edges and retire the guard. The user's call.
- The flock appears only after the camera's first 600 m below 3 km (the first anchor move copies it); at the start the Flamingos mesh is empty. A one-line fix in `planet_runtime.py`, which is embedded in the .blend, so it needs a rebuild.
- Capstone lamps have no per-shot mask any more (it was a bit per `/vj/cam`): behind a ridge their glow may show in the night fog. Not looked at.
- Not measured: holes (the off-output hole test), frame times on an idle machine.
- Stale after option A, not changed here: `synthwave_check.py` (the self-check's camera cells), `terrain_test_flight.py` and the old `flight_*` review scripts, `bench_fps.py` (CAM_0 cases).

## Round 2: night edges, flock, live checks, run 2 (2026-11-13)

### What changed

- Night edges on the stream (the user chose "Irregular net"): `lod_stream.jitter()` moves every lattice point up to 0.30 cells sideways, hashed from face, depth and global lattice position, so neighbours of one depth agree; points on the cube's edges stay. The morph target of an even vertex is its parent depth's own shifted point, of an odd one the midpoint of two of those (`morph_targets()`), so a fully morphed node is its parent. `lod_scene.build_group` does the same in geometry nodes (`lattice_dir`; the parent points through a second `PL_Surface` on the even vertices only, as points, about a third more surface evaluations per bake). The `Terrain LOD` material keeps its Wireframe node again.
- Checks: `verify_flight` 5b/5c (cracks, pops) pass with the shift, new 5f (no triangle folds at any morph, even with a random morph per vertex) passes: the thinnest triangle is 0.029 of its lattice share, so the net has slivers but no folds; in the live scene the baked nodes sit up to 0.30 cells off the lattice, same-depth seams match exactly (299 pairs, 0 m), a fully morphed child's even vertices land on its parent's within 1 micrometre (200 pairs).
- Flock: `planet_runtime.follow_props` copies the flock on its first call (97 birds at the start). One rebuild (round 2), no spare used.
- `verify_paths.py` lives in `blender/review/` now; `make verify` runs it from there.
- New review script: `blender/review/path_edges.py` (night grid 1/0 pairs per pose, for `net_regularity.py`). `path_camera_run.py` takes passes (day, night) and logs capstone lamps hidden behind land.

### Run 2

`path_camera_run.py` with two passes, day (show defaults) then night (`vj_night` 1), the same 15 steps each, 360 s, current Director. Log `blender/review/out/path_camera/run2.json` (git-ignored). Video `docs/video/path-camera-run-2.mp4` (git-ignored, 360 s, 8,279 new frames of 10,860, 166 MB), not judged.

**Under load, not trustworthy**: load 61.7 at the start, 21.0 at the end, `fps_trustworthy` false.

| Step | Frames | Median ms | p95 ms | Worst ms | Over 33 ms | Least height over ground (m) | Height over sea (m) | Swaps | Pops over 0.05 | Shown lag median / max (m) | Waiting on near nodes | In a blend | Hidden lit lamp (share / most) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| day 00 orbit pyramids 0.3 | 258 | 45.5 | 54.7 | 57.1 | 100 % | 138.6 | 148 to 158 | 51 | 0 | 5.0 / 11.6 | 0 % | 0 % | 0 / 0 |
| day 01 orbit lake 0.3 | 240 | 45.7 | 72.8 | 164.1 | 90 % | 141.8 | 158 to 2317 | 32 | 1 | 181.2 / 1896.6 | 29 % | 83 % | 0 / 0 |
| day 02 follow lake 0.3 | 271 | 43.6 | 66.5 | 230.3 | 71 % | 138.6 | 139 to 3219 | 31 | 1 | 290.0 / 2458.4 | 26 % | 97 % | 0 / 0 |
| day 03 follow river 0.3 | 316 | 30.1 | 68.4 | 210.6 | 43 % | 138.6 | 139 to 10326 | 40 | 0 | 734.1 / 3449.2 | 10 % | 100 % | 0 / 0 |
| day 04 rise river 0.5 | 348 | 27.6 | 61.0 | 198.9 | 27 % | 689.7 | 742 to 4678 | 24 | 2 | 162.5 / 6961.7 | 17 % | 100 % | 0 / 0 |
| day 05 rise coast 0.5 | 338 | 27.4 | 64.9 | 324.1 | 36 % | 391.4 | 443 to 12404 | 40 | 0 | 776.3 / 10804.7 | 10 % | 100 % | 0 / 0 |
| day 06 vantage coast 0.5 | 260 | 43.0 | 68.5 | 207.8 | 70 % | 227.6 | 310 to 3501 | 29 | 1 | 360.5 / 11039.5 | 24 % | 97 % | 0 / 0 |
| day 07 vantage moon 0.5 | 244 | 43.1 | 77.4 | 183.8 | 99 % | 800.0 | 800 to 4019 | 27 | 1 | 247.9 / 2689.8 | 15 % | 71 % | 0 / 0 |
| day 08 orbit moon 0.7 | 295 | 32.0 | 90.2 | 223.6 | 48 % | 794.3 | 1059 to 4835 | 31 | 1 | 182.7 / 12809.9 | 16 % | 41 % | 0 / 0 |
| day 09 orbit planet 1.0 | 428 | 26.0 | 47.9 | 75.3 | 13 % | 4526.2 | 4526 to 64448 | 16 | 0 | 1018.5 / 9115.2 | 0 % | 29 % | 0 / 0 |
| day 10 vantage planet 1.0 | 479 | 25.2 | 28.9 | 38.2 | 1 % | 63519.1 | 64000 to 64568 | 6 | 2 | 717.1 / 8069.2 | 0 % | 76 % | 0 / 0 |
| day 11 vantage sun 0.5 | 292 | 27.9 | 80.2 | 615.6 | 35 % | 803.0 | 1223 to 64000 | 31 | 1 | 393.5 / 43388.4 | 20 % | 36 % | 0 / 0 |
| day 12 follow sun 0.2 | 307 | 41.3 | 55.8 | 127.3 | 62 % | 57.7 | 90 to 1431 | 22 | 1 | 53.4 / 339.8 | 2 % | 60 % | 0 / 0 |
| day 13 follow pyramids 0.0 | 259 | 46.2 | 54.5 | 68.5 | 100 % | 10.0 | 44 to 92 | 17 | 0 | 4.3 / 16.0 | 0 % | 14 % | 0 / 0 |
| day 14 rise pyramids 0.3 | 254 | 46.1 | 63.3 | 90.7 | 100 % | 10.0 | 44 to 336 | 27 | 0 | 10.2 / 103.1 | 2 % | 69 % | 0 / 0 |
| night 00 orbit pyramids 0.3 | 244 | 47.5 | 60.1 | 77.8 | 100 % | 129.2 | 151 to 201 | 42 | 1 | 5.6 / 34.4 | 0 % | 13 % | 96 % / 6 |
| night 01 orbit lake 0.3 | 295 | 32.7 | 68.9 | 222.8 | 48 % | 142.4 | 148 to 3846 | 38 | 1 | 366.7 / 3130.3 | 14 % | 99 % | 21 % / 2 |
| night 02 follow lake 0.3 | 225 | 50.8 | 79.4 | 177.8 | 100 % | 139.3 | 139 to 3133 | 27 | 1 | 252.1 / 2073.6 | 22 % | 100 % | 22 % / 3 |
| night 03 follow river 0.3 | 333 | 29.9 | 62.2 | 189.5 | 41 % | 196.4 | 743 to 7992 | 42 | 0 | 443.2 / 5438.4 | 11 % | 100 % | 6 % / 3 |
| night 04 rise river 0.5 | 247 | 44.2 | 68.1 | 210.6 | 100 % | 261.9 | 324 to 1260 | 30 | 1 | 107.0 / 6064.4 | 9 % | 97 % | 0 / 0 |
| night 05 rise coast 0.5 | 343 | 29.2 | 62.7 | 80.3 | 37 % | 317.1 | 379 to 12542 | 48 | 0 | 777.5 / 5779.4 | 9 % | 99 % | 0 / 0 |
| night 06 vantage coast 0.5 | 270 | 40.1 | 67.6 | 200.6 | 84 % | 658.8 | 713 to 4327 | 39 | 0 | 293.9 / 1231.3 | 6 % | 100 % | 7 % / 2 |
| night 07 vantage moon 0.5 | 311 | 34.9 | 58.0 | 130.4 | 56 % | 801.2 | 803 to 3961 | 35 | 0 | 167.0 / 913.3 | 3 % | 72 % | 7 % / 2 |
| night 08 orbit moon 0.7 | 286 | 35.3 | 84.4 | 171.9 | 67 % | 803.1 | 1222 to 4926 | 37 | 2 | 143.4 / 9958.3 | 12 % | 46 % | 0 / 0 |
| night 09 orbit planet 1.0 | 391 | 29.5 | 43.2 | 62.7 | 18 % | 4616.6 | 4617 to 64127 | 22 | 0 | 1149.2 / 5834.5 | 0 % | 11 % | 0 / 0 |
| night 10 vantage planet 1.0 | 433 | 27.9 | 31.8 | 41.1 | 3 % | 63939.4 | 63987 to 64433 | 2 | 0 | 429.5 / 4040.8 | 0 % | 55 % | 0 / 0 |
| night 11 vantage sun 0.5 | 251 | 42.6 | 89.3 | 379.9 | 64 % | 810.5 | 1090 to 64057 | 36 | 2 | 913.3 / 38439.2 | 14 % | 21 % | 0 / 0 |
| night 12 follow sun 0.2 | 275 | 41.1 | 64.0 | 102.0 | 96 % | 67.2 | 148 to 2549 | 35 | 0 | 113.7 / 420.2 | 2 % | 90 % | 29 % / 3 |
| night 13 follow pyramids 0.0 | 252 | 47.1 | 57.1 | 74.2 | 100 % | 15.9 | 42 to 147 | 16 | 0 | 5.4 / 42.9 | 0 % | 13 % | 100 % / 7 |
| night 14 rise pyramids 0.3 | 249 | 46.3 | 63.2 | 86.5 | 100 % | 15.8 | 41 to 358 | 27 | 2 | 8.7 / 106.6 | 1 % | 64 % | 100 % / 8 |

- All 8,994 frames: median 37.9 ms, p95 64.7 ms; 8 to 12 km band 357 frames, median 27.6 ms, worst 615.6 ms.
- Pops over 0.05: day pass 11 (run 1, same steps by day: 17), night pass 10.
- Least height over ground 10.0 m (the floor) at height 0 by the pyramids.

### Night edges per pose

`path_edges.py`, one cut to each step's pose, clocks frozen, night 1, grid 1 and 0; `net_regularity.py` on the pairs (files in `blender/review/out/path_camera/edges/`). Line share is the frame's share of edge pixels; run is the longest straight line of edge pixels in a tenth-of-frame window (round 12 references: synthetic lattice 275, irregular net 170 to 185, round 11's failed lattice 264).

| Pose | Line share | Run max / median (px) |
|---|---|---|
| orbit pyramids 0.3 | 0.140 | 196 / 108 |
| orbit lake 0.3 | 0.068 | 272 / 202 |
| follow lake 0.3 | 0.145 | 226 / 154 |
| follow river 0.3 | 0.211 | 285 / 182 |
| rise river 0.5 | 0.071 | 130 / 67 |
| rise coast 0.5 | 0.185 | 295 / 238 |
| vantage coast 0.5 | 0.064 | 176 / 85 |
| vantage moon 0.5 | 0.011 | 44 / 40 |
| orbit moon 0.7 | 0.007 | 73 / 64 |
| orbit planet, vantage planet, vantage sun | 0.000 to 0.000 | no window with lines |
| follow sun 0.2 | 0.087 | 231 / 188 |
| follow pyramids 0.0 | 0.141 | 159 / 83 |
| rise pyramids 0.3 | 0.228 | 249 / 168 |

## Round 3: net in pictures, lamps, holes, stale tools (2026-11-13)

### Night net

- First pass (round 2 build), `shot-reviewer` on the 15 pairs against R12-NET: 4 pass, 6 fail (orbit pyramids, follow lake, follow river, rise coast, follow pyramids, rise pyramids: evenly spaced rows of dashed edges), 5 not judged (space, sky).
- Cause found: the Terrain material fades the edges where a cell is under about 10 px on screen, from `pl_l` (a cell is `PATCH_M / 2^pl_l`). The stream never stored `pl_l`, so every streamed cell counted as 785 m and the fade never acted. `lod_scene.build_group` now stores `pl_l = depth + log2(N) - 5`. No rebuild (`lod_scene` loads from disk); JITTER stays 0.30, `make verify` unchanged.
- After: start check edge line share 0.097 (was 0.129, bar 0.03). Longest straight run per pose 29 to 155 px (was 130 to 295), line share 0.007 to 0.150.
- Second pass, same rubric: 6 pass (orbit pyramids, rise coast, vantage coast, vantage moon, follow sun, rise pyramids), 5 fail, 4 not judged (no terrain). Magic (MagicBeta, show.magic) was running and may have sent to 9201 then; the script held only its own six controls.
- Third pass, every control held against OSC and Art-Net (both run scripts now do this): 3 pass (orbit pyramids, vantage moon, follow sun), 8 fail, 4 not judged. The camera stands a little elsewhere on each run (the paths move with time), so verdicts per pose vary between runs; the net fails R12-NET either way. Longest straight run 43 to 158 px, line share 0.012 to 0.115.
- What fails: plains and smooth slopes at a distance or a grazing angle, where 1 px dashed edges stack into evenly spaced rows. Not fixed: next candidates are a stronger fade on grazing plains (the `ndv` term of the fade), a coarser spacing on screen, or a wider line; JITTER 0.35 alone is unlikely to break rows of this kind.
- Pairs and sheets: `blender/review/out/path_camera/edges3/` (second pass), `edges3h/` (held, third pass), `sheet_net_0..2.png` in each.

### Capstone lamps

`flight_rt.lamp_sight`: one lamp per frame, in turn, tested for land between it and the camera within 3 km against the baked surface (`ClearanceMap.land_between`: no 3x3 max, no pyramid stamps, 60 m spared at the lamp); a hidden lamp's colour fades to black over 0.4 s, a farther lamp shines as before. `stop()` puts the colours back. The run's probe now counts a lamp as shining by energy times colour.

Night pass with every control held (`run3_night.json`; a first run while Magic may have steered is `run3_night_magic.json`), share of probes with a lit lamp hidden by the clearance map (max lamps), run 2 then run 3: orbit pyramids 0.96 (6) to 0; orbit lake 0.21 (2) to 0.19 (3); follow lake 0.22 to 0; follow river 0.06 to 0; vantage coast 0.07 to 0; vantage moon 0.07 to 0; follow sun 0.29 to 0; follow pyramids 1.0 (7) to 0.71 (1); rise pyramids 1.0 (8) to 0.44 (5). The rest stay at 0. The probe's map is padded (3x3 max) and has the pyramids stamped in, the runtime test has neither: the remainder is most likely lamps behind a pyramid or a ridge the padding raises (not checked in pictures). Night pass under load (26 to 20): median 45.6 ms against 38.5 ms in run 2, pops 14 against 10; under this load neither difference can be laid on the lamp test.

### Holes

`path_edges.py` with `"holes": true` renders each pose with the sea's underside pure green (off the Syphon output, one frame on it). Green share per pose, second pass then held pass: rise coast 0.0173 / 0.0108, vantage coast 0.0093 / 0.0101, follow sun 0.0131 / 0.0016, orbit lake 0.0004 / 0.0036, vantage sun 0.0008 / 0; the rest under 0.0001. In the second pass the large ones lie from the middle of the frame down (rise coast and vantage coast y 541 to 993 of 1080, follow sun the bottom quarter), with the camera 765 to 1509 m over the ground; not looked at in pictures.

### Live checks of the others' work

Closed: after 98da66a, a2b0c63 and 5680760 the Art-Net live test is 8 of 8 and the page test 24 of 24 live (orchestrator, 2026-11-13).

### Frame times

Not measured: load 25 to 38 when checked, `fps_trustworthy` false.

### Stale tools

- Deleted (each needed a fixed camera or the Flight's camera, nothing used them): `terrain_test_flight.py`, `flight_cracks.py`, `flight_frame_stats.py`, `flight_grabs.py`, `flight_numbers.py`, `flight_repeat.py`, `flight_seams.py`, `flight_trace.py`, `fps_table.py` (per fixed camera), `planet_proto/bench_fps.py` (CAM_0 cases); `flight_rt`'s test-flight hook (`vj_flight_script`), whose one user was `terrain_test_flight.py`.
- `energy.move` (a fixed shot's move) and its constants, with `verify_flight` 7d to 7g: no scene code called it.
- `synthwave_check.py`: cells look through named Path Camera views (`VIEWS`: path, target, height) instead of camera numbers; the `vj_cam`, `vj_flight` and `vj_boost` rows are gone (Blender has none of them; the fallback read `vj_cam`'s range and would have failed). Live on 6 changed rows: 5 effect, `vj_flamingos` no effect in all five views (the flock is 700 m off at the nearest in "orbit lake" 0.3, too small at preview size).
- Left: `readme_assemble.py` (README pictures of the /vj/cam row and its `--flight` option), the round scripts (`round*_jobs.py`, `cut_*`), history.

## Open items (for a fresh session)

Start: `make status`, then `make blender-open SCENE=planet` (start check must end "start state: ready"). Pure checks: `make verify` (about 15 minutes; `verify_flight.py --lod-only` is the stream part, 2 minutes). Logic: `make test`.

1. **Night net on plains at a distance or a grazing angle** (round 3, held pass: 8 of 11 judged fail R12-NET): see above. The next round (the user's "too fine, strobey") takes this over. Re-measure:
   `DN["pe_job"] = {"out": "<abs>/blender/review/out/path_camera/edges4", "poses": [[path, target, w], ...], "holes": true}; exec(open("<abs>/blender/review/path_edges.py").read())` through the Blender MCP (poses: `jq -c '[.[].pose]' blender/review/out/path_camera/edges3/pe.json`), wait for `DN["pe_done"]`, then `.venv/bin/python blender/review/net_regularity.py <dir> $(jq -r '.[].pair' <dir>/pe.json)` and the sheets with `blender/review/named_sheet.sh` to `shot-reviewer`.
2. **Holes** at the coast and toward the sun (1 to 1.7 % of the frame), above: look at `edges3/*_holes.png` and find what shows through.
3. **Lamps behind pyramids**: the runtime test ignores pyramids; up to 5 lamps near the pyramids may shine behind one. `build_planet.fog_lights` still evaluates 11 views for the dead `seen` mask (build time only).
4. **Lag and pops in blends**: shown terrain trails the camera by up to 43 km on the fall from space (step 11) and up to 11 km elsewhere in blends; 21 pops in 6 minutes, most in blends. Likely cause: in a blend the camera covers kilometres per second while the stream selects round where it is and bakes new nodes within a per-frame budget, so the fine nodes reach a place after the camera. Cheapest fix: at a blend's start, stage the end pose's terrain as a cut already does (`lod_scene` staging), so the arrival has its nodes; about 30 lines, no rebuild, the cost is bake work in the blend's first seconds (a frame-time bump there). The step-4 prefetch along the velocity was tried and dropped; this one targets the blend's end pose.
5. **Frame times on an idle machine**: every run so far was under load.
6. **`vj_flamingos` in the feature check**: no view shows the flock large enough; it needs a view with the flock near, or a flock placed in the view.

Run 2 again: open the scene, start `PYTHONPATH=~/.local/lib/python3.13/site-packages python3.13 tools/syphon_record.py --seconds 362 --fps 30 --size 960x540 --vflip --flag /tmp/pc.flag --out docs/video/path-camera-run-2.mp4 &`, then through the Blender MCP `DN["pc_job"] = {"out": "<abs>/blender/review/out/path_camera/run2.json", "flag": "/tmp/pc.flag", "passes": [{"name": "day", "set": {}}, {"name": "night", "set": {"vj_night": 1.0}}]}; exec(open("<abs>/blender/review/path_camera_run.py").read())`, wait for `DN["pc_done"]`; the table comes from `jq '.summary' run2.json`.
