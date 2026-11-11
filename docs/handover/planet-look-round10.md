# Planet look, round 10: no dummy wireframe (not started, plan only)

Round 9 is closed (`planet-look-round9.md`, commit 93385cc). The session that ran it stopped at half context. A fresh session runs this round on its own branch.

## The user's rule (2026-11-11, four messages through the orchestrator; the last one wins)

- "I NVER want to see ANY dummy wireframe. If anything, it's fine to show the real wireframe. But the dummy wireframe makes 0 sense."
- A dummy wireframe is any line pattern that is not the edge set of the mesh drawn at that pixel. That includes shader lattices, projected or texture grids, and the edges of a proxy or coarser mesh drawn over finer ground. None of them may show, at any camera, altitude, time of day or control value.
- A real wireframe is allowed but not required. It means the true triangle edges of the drawn terrain mesh, for example the Wireframe shader node with pixel size. It shows only from sunset to night (fades in over `/vj/night` 0.25 to 0.5, full at night), its strength is `/vj/grid`, and `/vj/bass` and `/vj/beat` may pulse it. Build it only if it is cheap and holds on patches and on the globe. Show it as its own pair of night shots, `/vj/grid` 0 and 1, so the user can choose. Edges that change when the streaming LOD changes the mesh are accepted.
- If real edges are not feasible, the planet has no lines at all and `/vj/grid` is unused there. Nothing may replace them.
- By day (`/vj/night` 0 to 0.25) there are no lines in either case. If the land looks flat or empty without them, report it with the reviewer's words. Do not invent a replacement look.
- Lines must never move against the terrain. The scroll goes, and `/vj/grid_speed` has no reader on the planet: take the reader and the driver out instead of feeding 0.
- The island (`synthwave_pyramids.blend`) keeps its look. Report in one line what its grid is made of.
- Reference of what must never appear: `blender/scenes/planet_proto/visual_check/user/2026-11-11-dummy-wireframe.webp` (main checkout path, orbit view, triangle lattice over the dark land). Do not open it yourself; give its path to `shot-reviewer` as the counterexample.

This reverses round 9 Part A's "day lattice without `thin_w^2`, cap 1.0" and withdraws rubric line R9-WIRE. In `docs/reports/planet-look-round9-verdict.json`, mark R9-WIRE "withdrawn", unscored. The frozen file `rubric-round9.md` stays as it is.

## Line sources found so far in `build_planet.py` (line numbers at 93385cc)

| Source | Where | Kind |
|---|---|---|
| Terrain lattice, day part `dwire` (`lattice`, `thin_w`, `wres`, `graze`), times `gk` (`vj_grid`, `vj_bass`, `rt_beat`) | `WIRE_CELL` 1587; 1724 to 1776 | dummy: remove |
| Terrain lattice, night part `wire` (`lat_` = lattice with `thin_w^2`) | 1786 | dummy: remove |
| Scroll: `rt_grid_phase` in `la` (1733); clock in `synthwave_runtime.py:165` (`rt_grid_phase += dt * vj_grid_speed`); defaults 83, 98 | | remove the reader on the planet. The runtime clock is shared with the island, so keep it there |
| Orbit night lattice (`la`, `lo`, `wp`) | `ORBIT_LATTICE` 722; 750 to 800 | dummy: remove |
| `vj_grid` in a fog or light term (`near_ * 0.03`, Night phase) | 2893 | read it: probably lattice light on the fog, so remove it with the lattice |
| Pyramid neon edges, Wireframe node on the pyramid faces | 2113 | real edges of the pyramid mesh: keep |

Before calling it done, search for a third source (other node groups, the graft's island materials on planet objects, water reflections of the lattice, `Wireframe` nodes, modifiers). List every source in the round 10 note, each marked real or dummy.

## Plan

1. Branch, for example `blender/wire-round10`, from `integration/presentable` or from wherever the orchestrator says.
2. Write the rubric first: `blender/review/rubric-round10.md`, three lines:
   - by day, no lines on land or water, and the land still reads through shading and haze;
   - no regular lattice or grid lines anywhere, on the ground or from orbit (counterexample: the reference image); any line ends at a vertex of the drawn mesh;
   - lines do not move against the terrain.
3. `build_planet.py`: remove both lattices, their drivers and readers, and the `gk` and `wire` terms. Fix the comments that still call the lattice the wireframe. Optionally add real edges: the Wireframe node with pixel size on the terrain material, times a 0.25 to 0.5 night smoothstep and `vj_grid`. Check that patch borders (`stitch()`) and the globe do not show a coarser mesh's edges over finer ground. If they do, that counts as dummy: no lines.
4. Contract: rewrite the Blender text of `/vj/grid` (real edges from sunset, or unused), `/vj/grid_speed` (island only, planet not used) and `/vj/night` in `osc/contract.json`, then run `make osc-sync`. In `blender/scenes/synthwave_check.py`, change only the `vj_grid` row (night precondition, or no effect if there are no lines) and the `vj_grid_speed` row (no effect on the planet). Another session edits the Flight rows of that table.
5. `blender/GUIDELINES.md`: add one pitfalls row: "lines that are not the drawn mesh's edges / user: no dummy wireframe, ever / lines only as real edges, from sunset, or none".
6. `make verify`, `make blender-rebuild`, `make blender-open`, `health.py`.
7. Numbers first:
   - node scan (`attribute_readers.py -- rt_grid_phase`, `-- vj_grid_speed`; also scan for `WIRE_CELL` and `ORBIT_LATTICE` math): no readers;
   - `/vj/grid` 0 against 1 by day: within the noise floor on two ground cameras and one orbit camera (`frame_diff.py`, or `make blender-check ARGS="--only vj_grid"` with day held);
   - night, static camera, clocks running: two frames 1 s apart differ no more with `/vj/grid` 1 than with 0.
8. Grabs (`check_jobs.py` + `freeze_clocks.py`, as in round 9): the day shots of round 9 (`CAM_0` to `CAM_10` day), `CAM_4` day p25, the night pair `/vj/grid` 0 and 1 on two ground cameras if real edges were built, one orbit night frame framed like the reference (`orbit_jobs.py` with `orbit_only`, `S9_orbit_night`), one flyover pair (`CAM_4`, 1 s apart, moving) for "lines stay attached". Sheets: `named_sheet.sh`. One `shot-reviewer` call with `rubric-round10.md` and the reference path. Verdicts go to `docs/reports/planet-look-round10-verdict.json`.
9. `make test`, commit, update this note, `make blender-kill`.

## Machine notes from round 9

- Blender is 5.3.0. Its settings were copied from 5.2, so the MCP add-on is present. A fresh 5.3 folder opened the scene out of camera view.
- The load was 50 to 220. `fps_trustworthy` was false. If it is true, the fps table (`docs/reports/blender-fps-planet.md`) is still owed.
- Grabs from different runs show a different star sky (`rt_star_ang` turns): compare only within one run. A node relink recompiles the sky for longer than the 3 s settle, so put a warm-up grab first.
