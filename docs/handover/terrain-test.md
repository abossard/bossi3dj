# Terrain test: can one terrain carry every view?

Question (the user's direction of 2026-11-12): can ONE terrain centred on the camera carry every view from skimming the ground to orbit, including the flights between, at a steady 30 fps? Today there are three terrains (the per-camera sets, the Flight's stream, the globe). This note holds the "before" state (the Flight's stream as it was, flown along one script), step 4 (cheap tries), the "after" run and the verdict.

## What exists (2026-11-13)

- `blender/scenes/flight_rt.py`: a hook. While `driver_namespace["vj_flight_script"]` holds a function, the Flight shot's pose is that function's (the Flight's integrator is skipped). Unset by default: the show's Flight and the fixed shots are unchanged.
- `blender/review/terrain_test_flight.py`: the 90 s flight, a pure function of wall time since its start (`Path.pose(t)`), and a per-frame log. Stages: skim 0-14 s (10 m over the river of `CAM_1`, 40 m/s downstream), climb 14-38 s (on along the river, 2.4 km, up to 64 km on a log height, the view turning down), orbit 38-44 s (64 km, the whole planet in frame at 24 mm), cross 44-54 s (to above the valley, 47 degrees round the planet), descent 54-70 s (to 450 m over the ground beside the pyramids, the view turning onto them), circle450 70-80 s (450 m radius, 450 m up, looking at the pyramids), circle60 80-90 s (the same circle, down to 60 m in 4 s). Clocks run, nothing is held, wire defaults.
- `tools/syphon_record.py`: records a Syphon server as a viewer gets it (the newest frame every 1/30 s of wall time, a slow sender shows as repeated frames), raw BGRA into ffmpeg, H.264. Blender's `CAM_OUT` frames arrive upside down: `--vflip`. A frame copy costs 3.8 ms median.
- `docs/video/*.mp4` is git-ignored.

## Before: the stream as it is (run of 2026-11-13, `blender/review/out/terrain_test/before.json`)

**Under load, not trustworthy.** `make status`: load_1m 176 before, 113 after, `fps_trustworthy` false; the job's own stamps 167 at the start, 118 at the end. Blender drew about 10 fps on `CAM_0` before the run. The recording got 1,156 new frames of 2,700 (12.8 fps). Frame times below say what the machine did under that load, not what the scene costs.

Video: `docs/video/terrain-test-before.mp4` (90 s, 30 fps, 960x540, 8.0 MB). For the user; not judged here.

| Stage | Frames | Median ms | p95 ms | Worst ms | Over 33 ms | Swaps | Level changes < 1.5 km / < 300 m | Lower-third cell on screen (px) | Its depth, distance | Stream lag median / max (m) | Frames with near nodes missing | Height (m) | Shown nodes, max depth |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| skim | 115 | 110.3 | 165.8 | 380.4 | 100 % | 0 | 0 / 0 | 273 | 9, 29 m | 3.4 / 8.0 | 49 % | 42-69 (5.1 over ground at least) | 2182, 9 |
| climb | 216 | 104.7 | 149.6 | 415.9 | 100 % | 7 | 3 / 1 | 48 | 7, 655 m | 8.1 / 2024 | 34 % | 70-64,000 | 1830, 9 |
| orbit | 128 | 42.1 | 92.9 | 114.1 | 92 % | 0 | 0 / 0 | - | - | 0 / 47 | 0 % | 64,000 | 27, 2 |
| cross | 246 | 40.9 | 50.3 | 61.2 | 90 % | 4 | 0 / 0 | - | - | 511 / 2029 | 0 % | 64,000 | 24, 2 |
| descent | 251 | 61.6 | 100.1 | 334.3 | 98 % | 29 | 4 / 0 | 13 | 9, 2.4 km | 209 / 2035 | 10 % | 461-64,000 | 261, 4 |
| circle450 | 130 | 74.1 | 99.5 | 129.3 | 100 % | 23 | 23 / 0 | 16 | 9, 478 m | 7.5 / 16 | 15 % | 458-519 | 1374, 9 |
| circle60 | 122 | 80.5 | 107.7 | 138.6 | 100 % | 20 | 20 / 0 | 24 | 9, 348 m | 7.8 / 32 | 22 % | 217-527 (54.8 over ground at least) | 1542, 9 |

- Hand-over at the globe band (8 to 12 km, `GLOBE_BAND` in `build_planet.py`, where the globe takes the pixels over from the ground's patches by eye height): crossed on the climb at 29.8 s and on the descent at 61.4 s, 13 drawn frames in all (median 95.7 ms, worst 161.9 ms), 576 to 1,830 nodes shown, deepest level 6 to 9, one swap inside the band. The stream keeps drawing at all heights (27 nodes, depth 2, from orbit); the globe is a shader blend over it, not a second mesh.
- Near-field detail: the deepest level is 9 (`lod_stream.Params.d_max`), cells of 6.1 m. Skimming at 10 m, the ground in the lower third is 29 m off and one cell spans 273 px of 1920: the near field is as fine as the stream goes, and it is coarse. On the circles the lower third looks 350 to 480 m out, a cell 16 to 24 px.
- Level changes: on the circles every swap changes nodes within 1.5 km (23 and 20), none within 300 m. The morph is meant to hide them; whether it does is for the video.
- Lag: the stream's selection trails the camera by up to 2 km on the climb and the descent (selections every 8 m of travel, built between frames within 8 ms; at 10 fps and km/s the camera outruns them), and a third to a half of the frames on the skim and the climb wait for near nodes.

Not measured in this run: holes (the off-output hole test needs one OpenGL render per sample; left for step 4), and frame times on an idle machine.

## Commands (the before run)

```
make blender-open SCENE=planet
# the recorder waits for the flight's flag file
PYTHONPATH=~/.local/lib/python3.13/site-packages python3.13 tools/syphon_record.py --seconds 90 --fps 30 --size 960x540 --vflip --flag /tmp/tt_go.flag --out docs/video/terrain-test-before.mp4 &
# Blender MCP (flight_rt reloaded so the hook is live):
sw = next(h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "synthwave_tick").__globals__
sw["_state"]["flight_rt"] = sw["start_sibling"](sw["FLIGHT_FILE"], "Flight")
DN["tt_job"] = {"out": "/abs/before.json", "flag": "/tmp/tt_go.flag"}; exec(open(bpy.path.abspath("//../review/terrain_test_flight.py")).read())
# wait for DN["tt_done"]; the summary per stage is in the JSON under "summary"
make blender-kill
```

## Step 4: the script fixed, the cheap tries (2026-11-13)

The script first: the skim dipped to 5.1 m over the ground (the height was the ground averaged over 80 m). It now takes the highest ground from 20 m behind to 80 m ahead: 10.0 m at least on every frame. The log gained the shown lag (camera to where the shown selection was made, `lod_scene` `shown_cam`), a pop per swap (1 minus the morph factor of the nearest finer-side vertex when a level changes: 0 means invisible), and an off-output hole mode (`holes_at`: the view at a script time held until the stream has settled, one OpenGL render with `Sea_Underside` as pure green, green pixels counted; the swapped material is on the Syphon output for about one frame). A job can override `lod_stream.Params` fields (`lod`) and `lod_scene` constants (`consts`).

Every run below is under load (`fps_trustworthy` false throughout); load is given per run. No rebuild: all tries are in `lod_stream.py` and `lod_scene.py`, which load from disk (three Blender restarts).

| Try | Load start/end | Skim median ms | Skim swaps | Skim frames waiting on near nodes | Skim shown lag median (m) | Skim lower-third cell (px) | Skim nodes | Result |
|---|---|---|---|---|---|---|---|---|
| baseline, fixed script (d_max 9) | 96 / 89 | 67.6 | 43 | 27 % | 13.1 | 210 | 1830 | |
| (a) d_max 10 | 120 / 123 | 70.0 | 15 | 30 % | 26.4 | 105 | 2322 | in the after run; not the default (verify_flight fails) |
| (a) d_max 11 | 126 / 159 | 71.4 | 6 | 39 % | 55.0 | 52 | 2991 | dropped: the near field starves (7 of 33 climb probes 1 to 2 levels short of the detail asked for) |
| (b) prefetch 1 s ahead, d_max 10 | 146 / 155 | 83.3 | 0 | 38 % | 297 | 200 | 2226 | dropped: the extra selection per update ate the build budget; the shown view stopped following on the skim |
| (d) land's water level follows its morph | see holes | | | | | | | kept |

- (a) d_max 10 halves the near cell (3.1 m; 105 px of 1920 in the lower third skimming at 10 m, from 210). Cost: 22 to 27 % more nodes on the skim; its frame-time cost can't be separated from the load (70.0 ms at load 120 against 67.6 at load 96). Under higher load the skim's stream stalls (the "after" run below). `verify_flight.py` fails with d_max 10: pops up to 0.25 m (5c: skim, boost, descend; depth 9 merges about 234 m away) and cracks up to 0.013 m (5b: skim, boost; depth 10 about 289 m away), gate 0.01 m. K 9 with M0 0.75 no longer covers the lag's travel against 24 m nodes. So the default stays `Params(d_max=9)`. d_max 10 needs a larger K at the deepest levels (more nodes) or a shorter lag before it can be the default.
- (b) Stream lag near the ground is not what costs detail: with d_max 9 the shown lag on the skim is 13 m median, 25 m max, and no lower-third probe was short of its wanted level on any stage. The lag of 2 to 5 km happens on the climb and the descent at km heights (0.04 to 0.25 of the height at p95 on the descent). The prefetch made it worse and was removed.
- (c) Level switches are already hidden in geometry: on the baseline the pop is 0 on every near swap (one swap over 0.05 on the climb, one at 64 km). No change was made. If the video shows popping, it is not the morph's geometry (candidates: shading, or the near nodes waiting).
- (d) Shore holes. Cause: the land material draws land only down to `SHALLOW` (1 m) under its own water level `pl_w`, and a coarse node's morph lowered dry land beside hillside lakes by tens of metres under that level, so it was cut out. Fix: `lod_scene.MORPH_WATER_LEVEL`. In `Terrain LOD`, `pl_w` moves with the morph's radial shift (mirrored on the mirror copy), so the height over its own water is the unmorphed one. Settled views, the fix switched live on the same stream:

| View (script time) | Height | Green px, fix off | Green px, fix on |
|---|---|---|---|
| descent 62 s | 5.4 km | 42,237 / 42,148 | 20 |
| descent 66 s | 1.5 km | 27 / 0 | 33 / 0 |
| circle450 75 s | 450 m | 0 | 0 |
| skim 7 s, climb 20 s, circle60 86 s | | 0 | 0 |

  Renders taken right after a flight, before the stream had settled, varied (up to 17,682 px at 66 s); the settled ones are the numbers. Above about 10 km, 2.5 to 4.5 % of the frame is green with the fix on or off (30 to 58 s): that is the reflection backdrop seen through the sea, which `Sea_Underside` is for, not holes.
- (e) Globe hand-over: the band is crossed in 20 to 30 drawn frames with 3 to 6 swaps and no pop; no number shows a problem, so it was not touched.

## After: d_max 10 and the water level fix, otherwise show defaults (run of 2026-11-13, `blender/review/out/terrain_test/after.json`)

**Under load, not trustworthy.** Load 144 at the start, 83 at the end (`make status` 175 before Blender opened, 98 after the run), `fps_trustworthy` false. The recording got 1,669 new frames of 2,700 (18.5 fps).

Video: `docs/video/terrain-test-after.mp4` (90 s, 30 fps, 960x540, 8.7 MB). For the user; not judged here.

Before is the baseline with the fixed script (load 96 / 89); the first table above it (load 167 / 118) used the old script.

| Stage | Median ms before / after | p95 ms before / after | Swaps before / after | Pops > 0.05 before / after | Lower-third cell px before / after | Shown lag median / max m, before | after | Frames waiting on near nodes before / after |
|---|---|---|---|---|---|---|---|---|
| skim | 67.6 / 77.4 | 82.3 / 94.5 | 43 / 1 | 0 / 1 | 210 / 109 | 13 / 25 | 162 / 425 | 27 % / 42 % |
| climb | 41.7 / 54.1 | 72.6 / 95.7 | 68 / 34 | 1 / 2 | 25 / 24 | 321 / 2290 | 528 / 4635 | 12 % / 24 % |
| orbit | 27.2 / 27.9 | 33.0 / 33.1 | 0 / 0 | 0 / 0 | - | 0 / 373 | 0 / 114 | 0 / 0 |
| cross | 25.2 / 27.7 | 31.5 / 32.2 | 4 / 4 | 1 / 1 | - | 523 / 2044 | 490 / 2030 | 0 / 0 |
| descent | 33.5 / 45.4 | 70.9 / 91.8 | 36 / 30 | 0 / 0 | 12 / 12 | 346 / 4096 | 384 / 4979 | 4 % / 9 % |
| circle450 | 46.0 / 55.9 | 65.6 / 73.7 | 25 / 25 | 0 / 0 | 29 / 29 | 11 / 22 | 13 / 29 | 7 % / 12 % |
| circle60 | 52.0 / 61.6 | 77.2 / 87.8 | 28 / 23 | 0 / 1 | 21 / 21 | 15 / 58 | 17 / 198 | 14 % / 27 % |

- The after run's skim stalled: one swap in 14 s, 7 of 17 lower-third probes one level short of the wanted detail. At load 120 the same settings swapped 15 times. The "before" run of the old script (d_max 9, load 167) stalled the same way (0 swaps). The stream's build throughput under load decides the skim, not d_max alone.
- Holes on the after run, settled: 0 to 33 px on every view below 10 km.
- The after run had d_max 10, set as the default at the time; it went back to 9 when `verify_flight.py` failed (above). What is committed: d_max 9 and the water level fix.
- `make test` green (422 Godot, 22 godot-check, Python suites); `verify_flight.py` with d_max 9: all checks passed.

## Verdict: can one camera-centred terrain carry every view at 30 fps?

Not yet, and not provable on this machine under load. In shape it can: one stream carries every height from 10 m to 64 km with no visible level change (pop 0), no shore holes, and the globe as a shader dissolve over it from 8 to 12 km. What fails is time and detail near the ground:

- Frame time: under load no stage below 1 km reaches 33 ms (skim and circles over 33 ms on 100 % of frames, before and after). The idle number is missing; it decides the question and needs a quiet machine (the user's measurement).
- Build throughput: the near field depends on the baking timer (GN builders evaluated on the main thread, 8 ms a frame). At 40 m/s and 10 to 15 fps it waits for near nodes on a quarter to two fifths of the frames and stalls under higher load. A prefetch can't help while the budget is spent; it needs baking off the frame (precomputed nodes along the show's paths, or a cheaper builder).
- Near detail: 6.1 m cells span 210 px at 10 m over the river; d_max 10 (3.1 m, about 105 px) breaks the morph's crack and pop guarantee at speed with K 9, and d_max 11 starves the stream. Detail under 3 m would have to come from the GPU (displacement or normal detail in the shader), not from more nodes.
- Still separate: the fixed shots show their own per-camera sets, and the globe is its own mesh blended in. "One terrain" today means one stream for the Flight plus a globe skin.

## Commands (step 4 and after)

```
make blender-open SCENE=planet
PYTHONPATH=~/.local/lib/python3.13/site-packages python3.13 tools/syphon_record.py --seconds 90 --fps 30 --size 960x540 --vflip --flag /tmp/tt_go.flag --out docs/video/terrain-test-after.mp4 &
# Blender MCP:
DN["tt_job"] = {"out": "/abs/after.json", "name": "after", "flag": "/tmp/tt_go.flag", "holes_at": [7, 20, 26, 58, 62, 66, 75, 86]}
exec(open(bpy.path.abspath("//../review/terrain_test_flight.py")).read())
# a try: "lod": {"d_max": 11}, "consts": {...}; holes only: "fly": False; wait for DN["tt_done"]
make blender-kill
```
