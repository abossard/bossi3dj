# Terrain test: can one terrain carry every view?

Question (the user's direction of 2026-11-12): can ONE terrain centred on the camera carry every view from skimming the ground to orbit, including the flights between, at a steady 30 fps? Today there are three terrains (the per-camera sets, the Flight's stream, the globe). This note holds the "before" state: the Flight's stream as it is, flown along one script. Step 4 (cheap tries) and the verdict wait for the next brief.

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

## Commands

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

## Next (step 4, waits for its brief)

The cheap tries, each with its number, at most three rebuilds: the near field finer (`d_max` 10 or 11, or a finer node grid; what the 33 ms buy on an idle machine), the shore holes (water following the land's level, or the planet's coarse land under the stream), the level switches hidden (morph range, hysteresis, switching outside the frame), one continuous hand-over to the globe; then the "after" run and video with the same script, and the verdict.
