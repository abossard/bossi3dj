# Planet night edges: guard at the start (2026-11-11)

Result: the blank night-edge build was not reproduced (three rebuilds, two suspects). A guard now notices it at every start and repairs it once.

## What the probe measures
- `blender/scenes/edge_guard.py`: night 1, `/vj/grid` 1, wait 3 Syphon frames, read the Syphon texture (1920x1080); `/vj/grid` 0, again. Line share = pixels where the grid frame is brighter by more than 24 in a channel. Present from 0.03.
- Clocks frozen while it runs; `vj_night`, `vj_grid`, their sources and the bridge's hold are put back; nothing runs between probes (draw handler and timer exist only while it runs).
- Numbers: present builds 0.065 to 0.106 (1080p, 24 threshold, on the on-air camera CAM_0); the blank builds of round 12 were 0.008 to 0.013 (960x540). Threshold 0.03 sits between.
- Cost at start (held controls, after the first frame with a picture): 541 to 685 ms, six opens. Total with the wait for the picture and the first interval: about 2 s.

## Guard
- `synthwave_runtime.py` loads `edge_guard.py` at the start (planet scenes only: it needs a Wireframe node on the `Terrain` material; not in background).
- Probe once. Under 0.03: mute and unmute the Triangulate node of `PL_Land` (a frame apart, the action that brought the edges back by hand), probe again.
- Result in `driver_namespace["edge_guard"]`, `/api/health`: `status` present, repaired, missing, no_picture, error; `shares`; `probe_ms`. `health.py` lists missing and error as a problem ("no night edges on the terrain"); `start_check.py` (behind `make blender-open`) prints a "night edges" row, waits for the guard, and fails on missing.
- On demand: `exec(open(bpy.path.abspath("//../review/edge_probe.py")).read())` through the Blender MCP, optional `DN["edge_probe_args"] = {"force_blank": 1, "repair": False}`.
- Unit test: `blender/tests/test_edge_guard.py` (decision logic, line share).

## Builds tried
| build | fresh open | share |
|---|---|---|
| committed scene (179ba64's rebuild) | present | 0.079 |
| rebuild 1 | present | 0.106 |
| committed scene headless re-saved | present | 0.083 |
| same, saved with `vj_night` 1 | present | 0.084 |
| rebuild 2 | present | 0.105 |
| rebuild 3 | present | 0.101 |
- Rebuilds take 5.5 to 10 min (load). The blank state came only with the two builds of 9a8d405 and b1154c6; cause still unknown.
- Repair path proven by forcing the probe's blank answer once (`force_blank=1`): shares [0.0 (forced), 0.103], status repaired, controls restored (hold empty, no off-default values), total 16.7 s under load 50 (the land re-evaluation is the slow part). With a real blank build the smallest action was never measured; the mute/unmute is the one known to work.

## Check rows
- `make blender-check ARGS="--only vj_grid,vj_bass,vj_flamingos --no-fallback"` on a fresh open of rebuild 3: all effect (grid 37.6x, bass 38.2x, flamingos 28.5x the floor).
- `vj_flamingos` row now `cams: [7]` in `synthwave_check.py`. `CAM_1` (225 flock points) has no effect: its flock covers 0.01 % of the preview. Rebuild 3 flock points: CAM_0 0, CAM_1 225, CAM_2 80, CAM_3 168, CAM_4 97 per set, CAM_10 825/765/727. CAM_7 was found by the check's fallback.

## Line motion at night (step 6)
`grid_numbers.py` night, CAM_0, rebuild 2, load 160+, `blender/review/out/edge-guard/night` and `night_frozen`; `blender/review/line_motion.py` for the masks.
- Clocks running: `/vj/grid` 0 pair mad 0.485 (quiet, counts), `/vj/grid` 1 pair mad 11.0, changed 22.6 %, line overlap 0.147 (threshold 24), 0.217 (threshold 8, so not only a brightness pulse); shift up to 2 px does not help. Round 11 had 0.78.
- Clocks frozen: grid 0 pair mad 0.030, grid 1 pair mad 0.468, overlap 0.894 (0.855 at threshold 8).
- So the lines are static in the picture and change only while the clocks run. The edge multiplier is `1 + 1.6 rt_beat + 1.2 vj_bass` (at most 1.72), which a pure brightness pulse cannot turn into overlap 0.2. Cause not found; open. Next: a running pair with `rt_beat` read in each frame, and one with the idle pulse off.

## Open
- Line motion above (running clocks).
- Blank build cause. If it returns, `edge_guard` reports `repaired` or `missing` with the first-probe share in the start state.
- The committed `synthwave_planet.blend` is unchanged (rebuilds were not committed).
