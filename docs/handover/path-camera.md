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
