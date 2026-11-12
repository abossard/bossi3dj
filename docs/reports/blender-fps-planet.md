# Synthwave Planet: frame times (2026-11-12)

**Context only.** `make status` never said `fps_trustworthy` on 2026-11-12: load average 32.8 at the start of the table and 24.4 at its end (foreign jobs), 45.5 during the Flight run. Blender 5.3.0, M1 Max, Syphon 1920 x 1080, the round 13 build (`5c2b1d1`). Clocks running, wire defaults, hard cuts (`/vj/blend` 0), 3 s settle, then every drawn frame of the camera view for 10 s. Draw interval in ms.

Rerun (planet open, Blender MCP): `DN["fps_job"] = {"out": "/abs/fps.json"}; exec(open(bpy.path.abspath("//../review/fps_table.py")).read())`, then `flight_numbers.py`, `cut_jobs.py` and `cut_flight_jobs.py` as below. Only on an idle machine do the numbers count.

## Fixed shots

| Camera | Day median | Day p95 | Day fps | Night median | Night p95 | Night fps |
|---|---|---|---|---|---|---|
| `CAM_0` Plaza View | 41.8 | 44.1 | 23.9 | 41.5 | 44.2 | 24.1 |
| `CAM_1` River Skim | 50.4 | 53.2 | 19.8 | 51.0 | 54.8 | 19.6 |
| `CAM_2` Pyramid Hero | 41.1 | 43.2 | 24.3 | 40.9 | 43.9 | 24.4 |
| `CAM_3` Moon Watch | 39.3 | 41.7 | 25.5 | 40.0 | 42.0 | 25.0 |
| `CAM_4` Pole Flyover | 37.3 | 39.3 | 26.8 | 37.3 | 39.3 | 26.8 |
| `CAM_5` Pyramid Orbit | 46.0 | 48.7 | 21.7 | 45.9 | 48.3 | 21.8 |
| `CAM_6` Planet Orbit | 26.8 | 29.9 | 37.3 | 28.2 | 30.1 | 35.5 |
| `CAM_7` Flamingo Lake | 45.9 | 48.4 | 21.8 | 47.6 | 49.5 | 21.0 |
| `CAM_8` River Mouth | 47.4 | 50.8 | 21.1 | 47.9 | 50.4 | 20.9 |
| `CAM_9` Far Pyramids | 31.5 | 33.4 | 31.8 | 45.7 | 48.1 | 21.9 |
| `CAM_10` Coast | 49.9 | 53.0 | 20.1 | 53.4 | 59.5 | 18.7 |

## The Flight shot `CAM_11` per stage (`flight_numbers.py`, seed 1, by day, `CAM_0` in the same run)

| Stage | Frames | Median | p95 | Worst |
|---|---|---|---|---|
| `CAM_0` before | 253 | 41.3 | 45.3 | 70.7 |
| Orbit | 344 | 29.3 | 32.4 | 36.3 |
| Approach | 247 | 39.1 | 53.0 | 58.6 |
| Skim | 174 | 54.6 | 72.8 | 80.9 |
| Hover | 201 | 49.4 | 58.1 | 71.9 |
| `CAM_0` after | 246 | 41.5 | 43.4 | 46.1 |

Skim and Hover cost 9 to 14 ms more than the same run before the Flight fixes (45.6 and 35.2 ms at load 69): the stream draws its water now (`Sea LOD`, the sea's own shader), and the sky frame follows the Flight every frame. Not split by an A/B.

## Cut stalls (M1: the worst draw interval within 1.5 s after a hard cut, budget 70 ms)

- Fixed shots (`cut_jobs.py`, 28 cuts each by day, at sunset and at night, cameras moving): 5 of 84 over 70 ms, median 58.2 ms, worst 102.2 ms. Over 70: n0 102, n0 101, n0 72, n0.5 72, n1 71.
- With the Flight (`cut_flight_jobs.py`, by day): into the Flight 79, 98, 81, 82, 89 ms; out of it 67, 107, 69, 70, 80 ms; between fixed shots 54, 57, 50, 56, 55, 60 ms.
- M2 (the tracking shots' aim at the first frame) is not measured any more: `grabber.py` finds a cut by `scene.camera`, which is the On-Air rig since `flight_rt`.

