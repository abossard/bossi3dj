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
