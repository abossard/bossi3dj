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

## Line motion at night (step 6): closed
`grid_numbers.py` night, CAM_0, `blender/review/out/edge-guard/night*`; masks by `line_motion.py`, camera by `camera_drift.py`, mesh by `edge_stability.py`.
| run | /vj/grid 0 pair mad | /vj/grid 1 pair mad | line overlap (T 24 / T 8) |
|---|---|---|---|
| clocks running | 0.485 | 11.0 | 0.147 / 0.217 |
| clocks frozen | 0.030 | 0.468 | 0.894 / 0.855 |
| running, rig held on the shot's pose (`terrain_equality.py` HOLD) | 0.301, 0.323 | 8.0, 6.3 | 0.215 / 0.352, 0.449 |
| running, rig held and `/vj/energy` 0 | 0.039 | 0.442 | 0.923 / 0.874 |
- Cause: the on-air camera's lens pulses with the beat and the energy (`energy.py`: `BEAT_LENS` 2 % at full pulse and energy, `TIGHT`), by 0.1 % between two grabs with the rig held (lens 24.007 to 24.028), up to 0.4 px at the frame edge. It moves 1 px lines onto other pixels; smooth shading barely changes (grid 0 pair mad 0.3). The rig's position and rotation did not move (0 deg, under 0.1 mm). With the rig held and the energy at 0 the overlap is back at 0.92.
- The mesh is not it: the evaluated `Planet.CAM_0.0` (215895 vertices, 379306 triangles, 589025 edges) is identical over four snapshots 1.5 s apart (0 edges differ, 0 vertices moved by 1 mm).
- So the lines do not move against the terrain; the camera's beat push moves them with it. Round 11's 0.78 was before the Flight runtime applied the energy on every shot. Closed.
- Hold used: `DN["grid_exec"]` (new in `grid_numbers.py`) with `FR.moved_pose = lambda ob, dg, drive: FR.pose_of(ob, dg)` and `S['vj_energy'] = 0.0` (the drive eases to 0 in a few seconds: set it a few seconds before). Restore: `FR.moved_pose` back, release the bridge hold, reset the vj_* values.

## Open
- Blank build cause. If it returns, `edge_guard` reports `repaired` or `missing` with the first-probe share in the start state.
- The committed `synthwave_planet.blend` is unchanged (rebuilds were not committed).
