# Planet finish (2026-11-12)

The user's order of 2026-11-12: finish the Synthwave Planet end to end. Five batches: the Flight shot, the day look and camera items, the missing manual pictures, the island, numbers. Branch `integration/presentable`, main checkout. Load 52 to 70 all day: every frame time here is context only (`make status` never said `fps_trustworthy`).

## Batch 1: the Flight shot

### Numbers first (`blender/review/flight_numbers.py`, seed 1, `out/flight/numbers_seed1.json`, load 69)

The Flight shot on air, stage by stage, against `CAM_0` in the same run (draw interval in ms):

| label | frames | median | p95 | worst |
|---|---|---|---|---|
| `CAM_0` before | 261 | 38.6 | 42.5 | 45.7 |
| cut in (1.5 s) | 35 | 43.1 | 54.2 | 84.9 |
| Orbit | 338 | 24.3 | 46.7 | 68.7 |
| Approach | 290 | 33.4 | 44.4 | 50.8 |
| Skim | 205 | 45.6 | 68.2 | 91.5 |
| Hover | 282 | 35.2 | 42.1 | 54.4 |
| cut out (3 s) | 75 | 40.3 | 44.9 | 52.7 |
| `CAM_0` after | 249 | 40.5 | 44.0 | 45.5 |

- Stages reached from the step of `/vj/flight`: Approach 23.8 s, Skim 23.7 s, Hover 38.4 s (the control is damped by design, `FLIGHT_RATE` 1/50 per s).
- Holes: none. `lod_scene.swap` shows a selection only once all its near blocks are baked; until then the previous selection stays. The stream lags behind the camera at most 7 frames (descent to the Skim, 172 near nodes waiting), 2 frames on the Skim and in the Hover.
- Cut in: the first frame after the cut is the old shot (54 ms), the second the Flight (85 ms), then 40 to 50 ms. Cut out: 52.7 ms worst. Both under M1's 70 ms except the 85 ms frame into the Flight.

### Review, round flight-1 (rubric `blender/review/rubric-flight.md`, 12 full-size frames, `out/flight/grabs_seed1/`)

3 of 12 pass (the three Orbit frames). Fails and their causes, found by numbers (`flight_grabs.py` with `"probe": True`: a ray through 9 x 5 points of the view and a column straight down):

| Fail | Cause | Fix |
|---|---|---|
| Hover: "one flat dark plum slab", no water; black at night | `lod_scene.read_nodes` mapped face materials by comparing the builder's evaluated materials (copy-on-write copies) with the original `Sea LOD`: never equal, so every water face of the stream was drawn with `Terrain LOD`. The probe: the surface 4 m under the Hover camera at sea level carried `Terrain LOD`. | compare `m.original` (`lod_scene.py`) |
| Approach and Skim: vertical hard-edged bands in the sky, black sky beside a glow at night | `planet_runtime.planet_tick` never placed the sky frame while the stream was on air: sky, stars and fog box stayed over the last fixed shot's ground point, thousands of km away | while streamed, `place_sky` under the On-Air rig every frame; back from the Flight, the fixed shot's anchor and sky again (`planet_runtime.py`, embedded: needs `make blender-rebuild`) |
| Approach and Skim at night: a regular lattice | the stream's blocks are a regular grid; their real edges read as one | no night edges on the stream (`lod_scene.morph_material` cuts the Wireframe node); the fixed shots keep the planet's irregular net. Rubric FL-EDGES allows "absent" |
| Skim: a dark diagonal crack | a river drawn with the land shader (same cause as the Hover) | as the Hover |

Not a bug: a run after the `/vj/boost` pair flew the Hover in a 38 s cycle (on the loop, 700 m off, back), because the pair's high grab had left `/vj/boost` at 1, and a held boost carries the camera off its loop by design (`flight_trace.py`, `out/flight/trace_seed1_jump.json`: speed 76 m/s in the Hover). The Flight scripts now start from the wire defaults.

### Seed

`flight_rt.quiesce(seed=None)` and `flight_rt.set_seed(n)`: a reset Flight flies `seed` (default `CHECK_SEED` 1, or the one `set_seed` chose). The `/vj/boost` pair counts on seed 1: mad 15.2 and 15.2 against floors 0.79 and 0.74 in two runs (`out/readme/boost1`, `boost2`). The 6.6 floor of the earlier run did not come back.

### Review after the fix pass, round flight-1-fix (`out/flight/grabs_seed1_fix3/`, verdicts `docs/reports/planet-flight-verdict.json`)

9 of 12 pass: Orbit, Skim and Hover by day and at night (water present, no lines, sky whole). The three Approach frames fail FL-WHOLE: holes in the terrain, dark blue by day.

Measured (`flight_grabs.py` `"holes": True`: `Sea_Underside`, seen only through a hole, painted pure green for one more grab):

| Approach, seed 1 | hole pixels of 1920 x 1080 | rows |
|---|---|---|
| as built | 17,288 and 17,323 (two runs) | 585 |
| morph displacement off (`Vector Displacement` Scale 0 in `Terrain LOD`, `Sea LOD`) | 3,664 | 336 |
| morph start `m0` 0.9 instead of 0.75 (`lod_stream.Params`) | 13,890 | 531 |
| Skim | 0 | 0 |

- At every sampled hole pixel the CPU ray (the undisplaced mesh) hits land of one block on all four sides 4 px away: the gaps open on the GPU. Four fifths go with the morph off; the rest are depth-transition cracks that a full morph should close. `verify_flight` 5b proves the pure model crack-free at m0 0.75, so the shader's morph and the model disagree somewhere (candidates: the look-ahead segment the selection uses against the morph's distance to `rt_cam`; the morph range at a block border). Not fixed: past the one fix pass. `m0` stays 0.75.
- Next step: read the displaced border vertices of two neighbouring blocks of different depth (positions, `pl_morph`, `pl_mr`, `rt_cam`) and compute the shader's morph in numpy; the crack is where the two sides land apart.

### Open from batch 1

- The Approach holes (above).
- Frame times of the Flight after the fixes (the sky frame is now placed every frame while streamed): batch 5.
- `README.md` gallery: `docs/images/readme/planet-flight-skim.jpg` (960 x 540) is new; the caption is the orchestrator's to place.

### Commands

```
# in the open planet Blender, Blender MCP:
DN["flight_job"] = {"out": "/abs/numbers.json", "seed": 1, "dwell": 10}; exec(open(bpy.path.abspath("//../review/flight_numbers.py")).read())
DN["fgrab_job"] = {"out": "/abs/dir", "seed": 1, "probe": True, "holes": True}; exec(open(bpy.path.abspath("//../review/flight_grabs.py")).read())
DN["ftrace_job"] = {"out": "/abs/trace.json", "seed": 1, "flight": [(0.0, 1.0)], "seconds": 150}; exec(open(bpy.path.abspath("//../review/flight_trace.py")).read())
.venv/bin/python blender/review/flight_frame_stats.py DIR
python3 blender/review/readme_assemble.py --flight DIR/skim_day.ppm
```
