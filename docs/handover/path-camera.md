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
- Step 2, `blender/scenes/path_camera.py` (no bpy): the four paths, the seven targets, the log height glide (0.5 e-folds/s), the phase as the one integrated number, changes as Director blends, a floor of 10 m over the ground. Its check is `docs/research/path-camera/verify_paths.py` in `make verify`: every path with every target at five heights at speed 1 and at the top speed, 420 changes, four frame times, the cut.
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

### Failed or not verified

- **No night edges on the Planet.** The stream never drew them (its regular grid read as a lattice, Flight review 2026-11-12); they came from the fixed shots' sets, which are gone. The start check fails on that (`edge_guard` line share 0.0006, needs 0.03), everything else in it is green. Fix options: an irregular stream lattice like round 12 (vertex shift in `lod_stream`, then `make verify` for cracks and pops), or accept no edges and retire the guard. The user's call.
- The flock appears only after the camera's first 600 m below 3 km (the first anchor move copies it); at the start the Flamingos mesh is empty. A one-line fix in `planet_runtime.py`, which is embedded in the .blend, so it needs a rebuild.
- Capstone lamps have no per-shot mask any more (it was a bit per `/vj/cam`): behind a ridge their glow may show in the night fog. Not looked at.
- Not measured: holes (the off-output hole test), frame times on an idle machine.
- Stale after option A, not changed here: `synthwave_check.py` (the self-check's camera cells), `terrain_test_flight.py` and the old `flight_*` review scripts, `bench_fps.py` (CAM_0 cases).
