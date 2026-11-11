# Planet look, round 11: relief on the plains (done; R11-BEND still fails, the next step needs the orchestrator's word)

Branch `integration/presentable`. Rubric: `blender/review/rubric-round11.md` (frozen, commit 4058500). Verdicts: `docs/reports/planet-look-round11-verdict.json`. Sheets for the user: `docs/images/2026-11-11/planet-round11-day.jpg`, `planet-round11-night.jpg` (labelled with the pass each grab comes from).

## Why

Round 10 kept the real triangle edges of `Terrain` at night. On flat ground the patch mesh is a regular grid of cells, so those edges read as a lattice (CAM_0, CAM_3 night `/vj/grid` 1 failed R10-LATTICE). The user, 2026-11-11: "the solution to have real wireframe at night on the flat planes is to make it a little bit less flat." The edges stay; the ground gets gentle relief. Mesh topology unchanged.

## What changed (`build_planet.py`)

- `PL_Surface` adds relief after the hydrology: swells `PLAIN_SWELL = (24.0, 320.0)` and knolls `PLAIN_KNOLL = (8.0, 90.0)`, each `(noise - 0.5) x 2 x gain`. Noise output has a std of about 0.09, so the swells are about 4 m std over about 320 m, the knolls about 1.4 m std over about 90 m. Pass 1 had half these (12, 4); the fix pass doubled them.
- Why these sizes: a lift `dz` at distance `d` moves an edge on screen by about `dz x d / (cell x eye height)` cell spacings. At CAM_0 (eye 80 m, cells 12 to 25 m at 300 to 1000 m) 2 m moves an edge by most of a spacing over about 9 cells, so the lines wave rather than run straight. The knolls (90 m, 15 cells of the 6 m near LOD) bend the near field, where the swells are too long to bend a line within the frame. Larger knolls alias on the coarse far LOD (the build's note on `KNOLLS_M`: taller knolls left far pyramids floating).
- Water stays where it was, by construction:
  - The hydrology still reads `PL_Elevation` without relief: same lakes, rivers, river levels.
  - No relief at or under the sea or a river within its shore. Rises fade in over the first 3 m above that level; dips go at most half way down to it, so no pit can reach water. The reference level is continuous: sea 0, the river's level falling 1 m per m past its shore.
  - Lake levels are flat per 260 m hydrology triangle, so using them would step the relief along triangle edges. Lakes and their first ring get no relief instead: a new hydrology point attribute `lake_near` (blurred lake mask, interpolated by Sample Nearest Surface).
  - `in_r` (where river water is drawn) reads the height without relief.
- Level under the island's pyramids: the relief fades from zero within each pyramid's half-diagonal plus 10 m to full 60 m further (pass 1: plus 20 m, 150 m) (read from `Pyramid_A` to `_D` in graft mode). Site pyramids elsewhere stand on their own ground per part, as before. Cameras and pyramids are placed on the evaluated ground at build time, so they follow the new heights.
- Not changed: `PL_Elevation`, the patch mesh, stitching (the relief goes through the same per-vertex height, so patch borders stitch as before), the Wireframe block of `Terrain`.

## Numbers (headless, `blender/review/plain_relief.py`; before = round 10 build, after = pass 1 relief built to a scratch file; the committed pass 2 build below the table)

Plains = drawn land faces under 15 deg in the camera's frame. Local std = height std after a plane fit per 200 m square, closer than 1 km, median over squares. CAM_3 is measured in its hold-rig pose (pyramids under the sky).

| | CAM_0 before | CAM_0 after | CAM_3 before | CAM_3 after |
|---|---|---|---|---|
| local std (m) | 0.22 | 0.91 | 0.19 | 0.80 |
| slope median 30 to 300 m (deg) | 0.87 | 3.14 | 0.33 | 2.70 |
| slope median 300 to 1000 m | 0.34 | 2.80 | 0.43 | 1.94 |
| slope median 1 to 3 km | 0.79 | 2.12 | 0.31 | 2.48 |
| faces under 1 deg, 30 to 300 m | 57 % | 5 % | 96 % | 8 % |
| faces under 1 deg, 300 to 1000 m | 71 % | 9 % | 80 % | 23 % |
| faces under 1 deg, 1 to 3 km | 56 % | 25 % | 82 % | 11 % |

The flat faces left are mostly the level ground under the island's pyramids (CAM_3 looks across it at 300 to 1000 m, CAM_0 at about 1.3 km).

Water: hydrology lake vertices 123 before and after, rivers 44 and 53.8 km before and after. Inland water vertices in frame: CAM_1 (river) 2828 and 2828, CAM_0, CAM_3, CAM_7 0 and 0.

`make test` green (357 Godot, 44 + 21 + 6 Python). `make verify` does not depend on the height field: `verify_flight.py` builds its own synthetic terrain. Run it again after the Flight merge.

Committed pass 2 build (`out/round11/plain_relief_pass2.json`): local std CAM_0 1.69 m, CAM_3 1.49 m; slope median 300 to 1000 m 5.25 and 4.28 deg; faces under 1 deg there 3 % and 18 %, 30 to 300 m 1.4 % and 2.6 %. Lakes 123, rivers 44 and 53.8 km, CAM_1 inland water 2828: unchanged.

## Live (pass 1 and pass 2 builds)

- `make blender-open`: start state ready, `health.py` clean on both builds.
- `ground_check.py`: no misses, no camera under ground. Pass 2: 10 floats, all far sites, largest 11.1 m at 5.3 km = 1.47 px (CAM_4 @0.25). Round 9 had 9, largest 9.9 m at 5.3 km = 1.3 px at the same site. JSON in `blender/review/out/round11/` (git-ignored).
- `cut_jobs.py` (pass 1): M2 aim jump 0 on all 36 cuts into CAM_3 and CAM_9. M1: 24 of 84 cuts over 70 ms, worst 625 ms (night, CAM_10 to CAM_3); load about 100, context only.
- `make verify`: one failing check, `5d descend` (the known old Flight failure, fixed only on `blender/flight`). Nothing else fails; `verify_flight.py` builds its own terrain, so the height field cannot move it.
- `make blender-check ARGS="--only vj_bass,vj_grid --no-fallback"`, `vj_bass` now with a night precondition in `synthwave_check.py`: `vj_bass` effect, 20.1x the noise floor; `vj_grid` effect, 52.3x. The make exited 1 because the run reported `holds released: False` (the frame-time run before it held controls), not because of a row.
- Night numbers (`grid_numbers.py`, CAM_0, pass 1): clocks running, /vj/grid 0 mad 0.070; /vj/grid 1 mad 0.945, line overlap 0.78. Clocks frozen, /vj/grid 1: mad 0.683, overlap 0.82: the same 1 px jitter floor as round 10 (0.637, 0.83). The running pair is a little over that floor; the fly pair passed R11-R10 on "lines do not move against the terrain".
- Line share at night, /vj/grid 1 (pass 1): CAM_0 5.8 % (round 10 5.3 %), CAM_3 2.6 % (2.2 %).
- Frame time (`ab_round11.py`, 3 rounds interleaved, load about 100, `fps_trustworthy` false: context only): pass 1 build CAM_0 day 28.0 ms, night 29.0 ms; pass 2 build day 27.9 ms, night 27.8 ms. Not measured on the round 10 build this round, so no before and after pair; round 10 measured 33.9 ms for CAM_0 day under other load.

## Verdicts (two `shot-reviewer` calls, frozen rubric): 14 pass, 5 fail of 19

- Pass 1 (19 shots): 13 pass, 5 fail, 1 undecided (CAM_9 day on the sheet). Pass 2 re-grabbed the six on the stronger relief: CAM_9 day passes, the other five still fail.
- R11-BEND and R11-R10 fail on CAM_0, CAM_1 and CAM_3 at night, /vj/grid 1. Reviewer, pass 2: "Bottom third, full width: foreground plain is still evenly spaced parallel and converging lines in a regular lattice" (CAM_0). CAM_1: "Lower-left slope ... is a regular quad lattice with straight evenly spaced lines". Edges read as terrain only on steep hills (CAM_3 upper left, CAM_4, the fly pair).
- R11-SHAPE fails on CAM_0 and CAM_3 by day: "only very faint, low-contrast swells. The foreground is nearly one flat purple tone" (CAM_0).
- R11-WATER holds wherever water shows. No lines by day in any shot.
- Why relief does not do it: CAM_1's lattice is on smooth slopes, not on flat ground. A regular grid of cells reads as a lattice wherever the ground is smooth at the scale of a few cells. Relief that would break it at CAM_0's 80 m eye height would have to be rough at cell scale (tens of metres), which is no longer gentle and aliases on the coarse LOD.

## Open items

| Item | Next |
|---|---|
| R11-BEND fails on smooth ground (CAM_0, CAM_3 plains, CAM_1 slopes) | needs the orchestrator's word. Option A: a different triangulation, the diagonal of each cell flipped by a hash of its lattice coordinates in `patch_mesh`. Same vertex set, so stitching holds, but must be checked on every LOD level. Cost: one hash and switch per patch cell in GN, the night edge look on every patch. Option B: in-plane jitter of interior patch vertices (border vertices fixed for the stitch). It breaks straight lines in plan view, but the edges change when the LOD changes. Option C: drop the night edges on the planet (the round 10 fallback; `/vj/grid` then unused there). |
| R11-SHAPE on the CAM_0 and CAM_3 day plains | the relief is there (slope median 4 to 5 deg) but reads with too little contrast at camera height. A shading change is a new look and needs the user's ask. |
| Relief kept at pass 2 strength or back to pass 1 | kept at pass 2 (CAM_9 day passes SHAPE only there); water and ground checks hold on it |
| Frame time before and after | no round 10 build run this round; needs an idle machine anyway |
| CAM_9 day: thin cyan seam lines on the pyramid edges | the pyramids' real edges (round 10 kept them); the reviewer asked whether R11-R10 covers them. It does not (land and water only). |

## Commands

```
cd blender/scenes/planet_proto && /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -Y ../synthwave_pyramids.blend --python build_planet.py -- --graft --out SCRATCH/after.blend
/Applications/Blender.app/Contents/MacOS/Blender -b --disable-autoexec FILE.blend --python blender/review/plain_relief.py [-- CAM_0 CAM_3]
```

A headless build takes about 3 to 4 min on this machine under load. `make blender-kill` kills headless builds too (one of this round's builds died that way).
