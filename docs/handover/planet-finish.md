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

## Batch 2: the day look and the camera items (round 13)

Rubric `blender/review/rubric-round13.md`, frozen first. Grabs `blender/review/round13_jobs.py`, numbers `blender/review/round13_numbers.py`, sheets `round13_sheets.sh`, verdicts `docs/reports/planet-look-round13-verdict.json`. "Before" is the batch 1 build, "after" the round 13 build, "final" after the fix pass.

Found on the way: `check_jobs.py` grabbed at the wire default `/vj/blend` 1, so every cut was a Director blend that flies the rig up to 2 to 4 km for seconds, and grabs landed mid-blend. Round 12's day frames of `CAM_6` to `CAM_10` were such frames (mean 12, sd 19, all alike; its reviewer passed them). `check_jobs.py`, `matrix_jobs.py` and `readme_pairs.py` now cut hard (`/vj/blend` 0); `readme_pairs.py` keeps the default for the Flight shot, where a hard cut waits for the stream's hold on wall time and the reset Flight stops repeating (boost floor 20.9).

| Item | Cause | Change | Number before → final | Review |
|---|---|---|---|---|
| Day plain flat (`CAM_0`, `CAM_3`) | a 20° sun on 4 to 5° swells varies Lambert by about ±35 %, and half the plain's light is the flat ambient fill: ±17 % in all | the sun and key light read the land's normal with its tilt times 2.5 below 8° of slope, fading to 1 by 20° (`SHADE_TILT`); mesh, edges and all other terms unchanged | `CAM_0` spread across the band (luminance sd once each row's mean is out) 5.55 → 8.15, 5 to 95 % range 11.1 → 23.2 | pass both |
| `CAM_5` pale top band in fog | EEVEE volume tile size 4: tile 2 and 8 draw none (rows 0 to 5 against 8 to 13: 1.37 at 4, 1.00 at 2 and 8, `cam5_band.py`) | tile 8 tried (cost 36.02 against 36.04 ms): the reviewer saw the old checker in thick fog by day (`CAM_2`, `CAM_5`). Tile 2 costs 8.5 ms (34.8 → 43.3, `CAM_2` fog 1). Back to 4 | 1.18 / 1.41 day, 1.25 / 1.37 night → 1.25 / 1.51, 1.53 / 1.82 (band kept) | dropped: the band stays |
| `CAM_4` night haze at fog 1 | night fog tail 0.3 of the layer, 6 tops high, albedo (0.06, 0.05, 0.08) under the blue moon light | tail 0.12 and 4 tops (`FOG_TAIL_NIGHT`), albedo (0.055, 0.055, 0.06) | star points in the low sky at fog 1: 2259 → 4810 (fog 0: 4746) | pass |
| `CAM_10` glow at `/vj/nebula` 0 | the stars' lum² gain on the Milky Way core's texels | a 1024 px blurred copy of the map (`starmap_2020_8k_bg1024.exr`, made by the build next to the map, local) subtracted from the stars as the nebula goes to 0 (`STAR_BG_K` 1); nebula 1 unchanged | sky patch at nebula 0: mean 14.9 → 6.5, pixels over 50: 645 → 0 | pass |
| Square stars at 200 mm | Linear lookups of the 8k map: a texel is about 8 px there | star lookups Cubic (`STAR_INTERP`) | sky over 50 at 24 mm: 7602 → 7695 px (the points stay); frame time 46.4 against 51.3 ms, rounds overlap after the compile | pass (round points) |
| `CAM_4` hillside crease | not the bank's hard minimum: a soft minimum (`hc`, reach up to 8 m, never down to the water) left the crease as it was | reverted | | fail, open |
| `CAM_4` water step | lake level flat per 260 m hydrology triangle (`wl_face`) and the hard test in `in_r` | not changed: a fix moves every shore (a per-lake level or the lake extended over its rim triangles), a round of its own | | not regrabbed as its own line |

Review round 13 (the round 13 build): 35 entries, 26 pass, 8 fail (four frames, each on a sheet and full size: `CAM_4` 25 % and 50 % crease; `CAM_2` and `CAM_5` fog 1 checker from tile 8), 1 needs full size (`CAM_4` phase 0, the same crease). Fix pass: tile back to 4, soft bank reverted; final numbers above.

Open from batch 2: the `CAM_4` crease (next: per-patch normals at `stitch()` borders, read the normals across a patch border on the crease's line), the `CAM_4` water step, the `CAM_5` band (tile 4) unless 8.5 ms are worth it.

Sheets for the user: `docs/images/2026-11-12/planet-round13-day.jpg`, `planet-round13-night.jpg` (final build; the limb tile from the round 13 build, same star lookups).

## Batch 3: the missing manual pictures

Pair rule of `readme_pair_check.py` (mad of low against high at least twice the floor of low against low again, over 1 % of pixels moved, floor under 2). `readme_pairs.py` takes per-pair overrides now: camera (`readme_cam_for`), advance (`readme_advance`), held controls (`readme_set`) and python after the reset (`readme_exec`).

| Address | Camera and state | mad / floor / share | Run |
|---|---|---|---|
| `/vj/moon` | `CAM_6` (orbit) at night, path phase 60 s, `/vj/grid` 0: the moon well in frame (projection x 0.65, y 0.82); `CAM_3` has it behind the hills, `CAM_4` at phase 0 out of frame | 3.45 / 0.11 / 2.9 % | `out/readme/r13d` |
| `/vj/star_speed` | `CAM_10` at night, 30 s (30° of drift), grid 0, flock off: the Milky Way band moves as a whole; on `CAM_0` the drift moved every star but under 1 % of pixels | 5.35 / 1.40 / 28 % | `r13e` |
| `/vj/meteor` | `CAM_0` at night, grid 0, `random.seed(24)` after the reset: the first shooting star of seed 1 lies outside every camera; seed 24 crosses `CAM_0`'s sky (projected x 0.37 to 0.45, y 0.81 to 0.71 at 0.4 s) | 0.195 / 0.036 / 0.24 % | `r13e`, written with `--accept vj_meteor`: every changed pixel is in the sky (rows 0 to 293), strongest 247; a streak never covers 1 % |
| `/vj/boost` | `CAM_11`, `/vj/flight` 0.66, seed 1, the default blend | 15.2 / 0.74 / 63 % | `boost2` (batch 1 build) |

The camera pictures (`cam-planet-0` to `-10`, the strip) and the ten gallery frames were replaced from run `out/readme/r13` (hard cuts); `cam-planet-11` and `planet-flight-skim.jpg` from the Flight's Skim. `make osc-sync` wrote the four new pictures into the README's manual; `make osc-test` 40 OK.

```
# Blender MCP, for one pair:
DN["readme_out"] = "/abs/dir"; DN["readme_only"] = ["vj_meteor"]; DN["readme_cams"] = False; DN["readme_extra"] = False
DN["readme_cam_for"] = {"vj_meteor": 0}; DN["readme_set"] = {"vj_meteor": {"vj_grid": 0.0}}; DN["readme_exec"] = {"vj_meteor": "import random; random.seed(24)\n"}
exec(open(bpy.path.abspath("//../review/readme_pairs.py")).read())
.venv/bin/python blender/review/readme_pair_check.py DIR
python3 blender/review/readme_assemble.py DIR [--accept vj_meteor]
```

Batch 2 gate (final build, 2026-11-12): start check of `make blender-open` green, `health.py` clean, full self-check 36 of 37 (`/vj/grid_speed` only), bridge 37 of 37 applied (`docs/reports/blender-feature-check-planet-2026-11-12.json`), `make test` green (python 56, 40, 45; Godot 422; godot-check 22). A first run read 35 of 37 (`/vj/flamingos` lost, noise floor 14.9): the round's grabber had left its holds on, 7 bridge packets refused. `grabber.py` now releases its holds when it ends.
