# Planet look, round 12: irregular patch mesh (fix built in the live scene only; rebuild and review open)

Branch `integration/presentable`. Rubric: `blender/review/rubric-round12.md` (frozen, commit 3d8cc1e). No verdicts yet: the session stopped at half context.

## Why

Round 11: the real triangle edges of `Terrain` at night read as a regular lattice wherever the ground is smooth over a few cells (R11-BEND failed on CAM_0, CAM_1, CAM_3). The user's decision of 2026-11-11: make the mesh irregular (round 11 note, options A and B). The mesh stays the real drawn geometry; no pattern in any shader.

## What changed (`build_planet.py`)

- `JITTER = 0.30`: `patch_dir` moves every interior patch vertex up to 0.30 of a cell sideways, uniform over a disc, direction and radius from `lattice_hash` (4D white noise of lattice x, y, the patch level, W = the patch index). The height is read at the moved position, so the surface keeps its shape and only the sampling moves. Border vertices stay on the lattice: `stitch` and the neighbour patch see the same border. Under 0.35 no triangle can fold over (two vertices moving toward each other close at most 2 x 0.30 of the 0.707 cell altitude).
- `cell_triangles`: one Triangulate node, quad method "Fixed", on land (after the `pl_facet` store, so both triangles of a cell keep its shade; before the mirror copy and `stitch`) and on water (after the wet delete, so the wet test is per cell as before).
- Water follows the land: it uses the same `patch_dir`, so land and water sample the same points and meet on the same faces. Without that the shore would move by up to a third of a cell against the water faces.
- Vertex and triangle counts unchanged (CAM_0 set: 215895 vertices, 379306 triangles); the polygon count doubles because cells are now triangles.
- No hashed diagonals (option A is out, see below). The first commit (b1154c6) had them.
- Across an LOD change: the hash depends on the level, so a patch that changes level gets new offsets on all its interior vertices; its edges change at that switch (accepted by the user). A neighbour's level change touches only the shared border, which is not jittered. While the anchor and the LOD stand still nothing moves.
- Hand-over to the globe: the globe is its own sphere and is not touched. Patches near the hand-over sit on levels 0 and 1, which have no or one interior vertex, so the jitter there is nearly nothing.
- Flight: its stream builds its own grids (FLT_Lod in `lod_scene.py`, `lod_stream.py`), not through `patch_mesh`; it is not changed and stays a regular lattice in plan view.

## Finding: EEVEE's Wireframe node and flipped diagonals

Built with hashed diagonals (b1154c6), the night edges almost vanished. Live experiments in the open scene (Triangulate nodes of `PL_Land` muted or switched, not saved), CAM_0 night, lines = `/vj/grid` 1 over 0, over 24:

| CAM_0 night | line share | rows top to bottom (tenths of the frame) | longest straight run (px) |
|---|---|---|---|
| round 11 build (before) | 0.095 | .00 .02 .04 .08 .09 .06 .05 .22 .23 .15 | 196 |
| jitter + hashed diagonals (b1154c6 build) | 0.013 | .01 everywhere, .05 at the bottom | (no window with lines) |
| jitter, quads left to the draw tessellation | 0.169 | .01 .20 .26 .21 .30 .23 .14 .13 .17 .05 | 342 |
| jitter + every cell "Fixed" (the committed fix) | 0.095 | .01 .02 .04 .08 .08 .06 .05 .23 .22 .15 | 157 |

- Randomly flipped diagonals: EEVEE's Wireframe node draws almost no edge (the mechanism is not known; a consistent diagonal works).
- Jittered quads without explicit triangles flood the far field with edges.
- The fix (every cell "Fixed") keeps the round 11 line density and row profile; the longest straight run falls from 196 to 157 px, the spectrum peak median from 73 to 31, the direction share rises (0.31 to 0.57 median: one diagonal family).
- Whether that reads as an uneven net is for the reviewer: the sampling moved by 0.30 cell, but the diagonals all run one way.

## Numbers

- Health on the b1154c6 build: `problems` empty, no missing image.
- Water (headless `plain_relief.py`, b1154c6 build; the fix does not change positions): lakes 123, rivers 44 and 53.8 km (unchanged), CAM_0 and CAM_3 inland water 0, CAM_1 inland water vertices 2839 (round 11: 2828; the wet vertices now sit at moved sample points). JSON in `blender/review/out/round12/` (git-ignored).
- Regularity before (`net_regularity.py`, round 11 build, night pairs in `out/round12/before/`): longest run CAM_0 196, CAM_1 275, CAM_3 33 (CAM_3 shows few plain lines in this pose, share 0.013). After: only the CAM_0 fix experiment above (157).
- Frame time before (`ab_round11.py`, round 11 build, load about 80, `fps_trustworthy` false, context only): CAM_0 day 34.8 ms, night 34.5 ms. After: not measured.
- LOD build (`lod_build_ms.py`, headless, the CAM_0 land and water set, each tag re-evaluates its dependents too; load-bound, context only): land 5395 ms before, 5748 ms after (b1154c6, two Triangulate nodes); water 4683 and 4866 ms.
- Flight shot CAM_11 at night (b1154c6 build): line share 0.015 for `/vj/grid` 1 over 0, longest run 125 px, but the shot flies, so the pair differs by motion too. Not conclusive on whether the streamed terrain shows edges or how regular they are; it needs a look in the review.
- Not done: ground check, cut timing, night numbers (`grid_numbers.py`), the review, the sheets.

## Other findings

- The committed `synthwave_planet.blend` (from the Flight merge, 5da0cef) points its star and moon maps at `.claude/worktrees/blender-flight/...` (absolute). With that worktree gone the night sky draws magenta. The next `make blender-rebuild` writes the file from the main checkout and fixes it; commit the rebuilt file.
- `lod_build_ms.py` must run headless: in the live UI its loop blocked Blender's main thread for over 10 minutes (Blender was killed).

## Open items (next session, in order)

1. `make blender-rebuild`, `make blender-open`, `health.py`.
2. Grabs: `round12_jobs.py` with `DN["check_out"]` = `out/round12/grabs` (rename the b1154c6 grabs first), flyover pair (`grid_numbers.py` mode "fly"), orbit hand-over frame (`orbit_jobs.py`, `DN["orbit_only"] = ["S9_pull_2_10k_day"]`).
3. Numbers: `net_regularity.py` on CAM_0, CAM_1, CAM_3 night pairs against `out/round12/before/`; `grid_numbers.py` mode "night"; `ground_check.py`; `cut_jobs.py`; `ab_round11.py` with `DN["ab_out"]`.
4. One `shot-reviewer` call with `rubric-round12.md` and the counterexample `blender/scenes/planet_proto/visual_check/user/2026-11-11-dummy-wireframe.webp`; verdicts to `docs/reports/planet-look-round12-verdict.json`. Ask it also whether CAM_11's streamed terrain shows edges and whether they are regular.
5. Sheets for the user `docs/images/2026-11-11/planet-round12-night.jpg` and `-day.jpg` (640 px tiles, labelled), commit the rebuilt `.blend` and the sheets, `make blender-kill`.
6. If R12-NET fails with one diagonal family: the hashed diagonal is not available with the Wireframe node. Remaining levers are the jitter (0.35 is the fold limit) or option C (no night edges on the planet).

## Commands

```
make blender-rebuild && make blender-open
.venv/bin/python blender/review/net_regularity.py blender/review/out/round12/grabs CAM_0_night_f00_e0_grid1:CAM_0_night_f00_e0_grid0 CAM_1_night_f00_e0_grid1:CAM_1_night_f00_e0_grid0 CAM_3_night_f00_e0_grid1:CAM_3_night_f00_e0_grid0
.venv/bin/python blender/review/net_regularity.py --sim 0.30 1
/Applications/Blender.app/Contents/MacOS/Blender -b --disable-autoexec blender/scenes/synthwave_planet.blend --python blender/review/lod_build_ms.py -- CAM_0 Planet.CAM_0.0 Water.CAM_0.0
/Applications/Blender.app/Contents/MacOS/Blender -b --disable-autoexec blender/scenes/synthwave_planet.blend --python blender/review/plain_relief.py [-- CAM_1]
```

Grabs through the MCP: set `DN["check_out"]`, then `exec(open(bpy.path.abspath("//../review/round12_jobs.py")).read())`.
