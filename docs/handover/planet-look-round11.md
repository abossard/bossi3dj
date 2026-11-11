# Planet look, round 11: relief on the plains (Blender-free part done; live part waits for the go)

Branch `integration/presentable`. Rubric: `blender/review/rubric-round11.md` (frozen, commit 4058500). Verdicts: not yet (live part).

## Why

Round 10 kept the real triangle edges of `Terrain` at night. On flat ground the patch mesh is a regular grid of cells, so those edges read as a lattice (CAM_0, CAM_3 night `/vj/grid` 1 failed R10-LATTICE). The user, 2026-11-11: "the solution to have real wireframe at night on the flat planes is to make it a little bit less flat." The edges stay; the ground gets gentle relief. Mesh topology unchanged.

## What changed (`build_planet.py`)

- `PL_Surface` adds relief after the hydrology: swells `PLAIN_SWELL = (12.0, 320.0)` and knolls `PLAIN_KNOLL = (4.0, 90.0)`, each `(noise - 0.5) x 2 x gain`. Noise output has a std of about 0.09, so the swells are about 2 m std (peaks 4 to 6 m) over about 320 m, the knolls about 0.7 m std over about 90 m.
- Why these sizes: a lift `dz` at distance `d` moves an edge on screen by about `dz x d / (cell x eye height)` cell spacings. At CAM_0 (eye 80 m, cells 12 to 25 m at 300 to 1000 m) 2 m moves an edge by most of a spacing over about 9 cells, so the lines wave rather than run straight. The knolls (90 m, 15 cells of the 6 m near LOD) bend the near field, where the swells are too long to bend a line within the frame. Larger knolls alias on the coarse far LOD (the build's note on `KNOLLS_M`: taller knolls left far pyramids floating).
- Water stays where it was, by construction:
  - The hydrology still reads `PL_Elevation` without relief: same lakes, rivers, river levels.
  - No relief at or under the sea or a river within its shore. Rises fade in over the first 3 m above that level; dips go at most half way down to it, so no pit can reach water. The reference level is continuous: sea 0, the river's level falling 1 m per m past its shore.
  - Lake levels are flat per 260 m hydrology triangle, so using them would step the relief along triangle edges. Lakes and their first ring get no relief instead: a new hydrology point attribute `lake_near` (blurred lake mask, interpolated by Sample Nearest Surface).
  - `in_r` (where river water is drawn) reads the height without relief.
- Level under the island's pyramids: the relief fades from zero within each pyramid's half-diagonal plus 20 m to full 150 m further (read from `Pyramid_A` to `_D` in graft mode). Site pyramids elsewhere stand on their own ground per part, as before. Cameras and pyramids are placed on the evaluated ground at build time, so they follow the new heights.
- Not changed: `PL_Elevation`, the patch mesh, stitching (the relief goes through the same per-vertex height, so patch borders stitch as before), the Wireframe block of `Terrain`.

## Numbers (headless, `blender/review/plain_relief.py`; before = committed round 10 build, after = the same build script with relief, built to a scratch file)

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

## Live part (after the orchestrator's go)

- `make blender-rebuild`, `make blender-open`, `health.py` (empty `problems`), `ground_check.py`, cut timing, `make verify`.
- `grid_numbers.py` at night (running clocks move no line), line share on CAM_0 and CAM_3. Frame time CAM_0 day and night before and after.
- Grabs: CAM_0 to CAM_10 day; CAM_0, CAM_1, CAM_3, CAM_4 night `/vj/grid` 1; CAM_0, CAM_3 night `/vj/grid` 0; one flyover pair. One `shot-reviewer` call with `rubric-round11.md` and the counterexample `blender/scenes/planet_proto/visual_check/user/2026-11-11-dummy-wireframe.webp`. Verdicts to `docs/reports/planet-look-round11-verdict.json`. Sheets `docs/images/2026-11-11/planet-round11-day.jpg` and `planet-round11-night.jpg`.

## Open items

| Item | Next |
|---|---|
| R11-BEND not yet observed | live part |
| If a plain still reads as a lattice | first raise `PLAIN_KNOLL` (cheap, one constant). Then (orchestrator's word needed) a different triangulation: per-cell diagonal flipped by a hash of the cell's lattice coordinates in `patch_mesh`. That costs one node chain per patch and keeps the vertex set, so stitching holds, but must be checked on every LOD level. Or a small in-plane jitter of interior patch vertices: it breaks straight lines in plan view too, but border vertices must stay put for the stitch and the edges change when the LOD changes. |
| The level ground under the island's pyramids keeps flat cells | by design (the pyramids stand at one height); about 250 m around each |

## Commands

```
cd blender/scenes/planet_proto && /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -Y ../synthwave_pyramids.blend --python build_planet.py -- --graft --out SCRATCH/after.blend
/Applications/Blender.app/Contents/MacOS/Blender -b --disable-autoexec FILE.blend --python blender/review/plain_relief.py [-- CAM_0 CAM_3]
```

A headless build takes about 3 to 4 min on this machine under load. `make blender-kill` kills headless builds too (one of this round's builds died that way).
