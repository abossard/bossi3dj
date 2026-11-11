# Planet look, round 10: no dummy wireframe (done; one choice open for the user)

Branch `integration/presentable`, commits 326de02 and the one after it. Rubric: `blender/review/rubric-round10.md` (frozen). Verdicts: `docs/reports/planet-look-round10-verdict.json`. Sheets for the user: `docs/images/2026-11-11/planet-round10-day.jpg`, `planet-round10-night-orbit.jpg`.

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

## Line sources (every one found, `line_sources.py` and `attribute_readers.py` on the rebuilt file)

| Source | Kind | Now |
|---|---|---|
| Terrain lattice, day part (`WIRE_CELL` 24 m, `lattice`, `thin_w`, `wres`, `graze`, `gk`) | dummy | removed |
| Terrain lattice, night part (`wire`, `lat_`) | dummy | removed |
| Scroll: `rt_grid_phase` reader on the planet; its init in the build | dummy (lines moving over the ground) | removed; the clock in `synthwave_runtime.py` stays for the island |
| Orbit night lattice (`ORBIT_LATTICE` 600 m in `orbit_look`, globe and patches) | dummy | removed |
| `vj_grid` cyan light on the lowest fog at night (`VJ_Fog`) | light of the lattice | removed |
| Water reflections of the lattice | dummy | gone with the lattice; the new edges are off on the mirror copy and under water |
| Pyramid edges: Wireframe node on `Pyramid` (planet copy), Wireframe modifiers on `Pyramid_A` to `_D` | real (the pyramid mesh) | kept |
| New: Wireframe node (pixel size 1) on `Terrain` | real (the drawn patch mesh's triangles) | added: `/vj/night` 0.25 to 0.5 fade, full at night, strength `/vj/grid`, bass and beat pulse; only on dry land, not on the mirror copy, faded where a cell's smaller on-screen side is under 4 to 10 px; none on the globe (a proxy sphere under shaded relief) |

Other hits of the scan are not lines: Curve to Mesh in the land, water, props and globe trees (rivers), Mesh to Points in the flamingo flock. No tree reads `rt_grid_phase` or `vj_grid_speed`; `vj_grid` is read only by `Terrain`.

Island (`synthwave_pyramids.blend`, unchanged): its grid is two Wireframe nodes on its `Terrain` material (its real low-poly edges, pixel size 1.2 and 1.4) plus a projected scrolling grid read from `rt_grid_phase` on the night ground, and the `Water Grid` group.

## Numbers (`grid_numbers.py`, `grid_diff.py`; mad 0..255, frames 960x540)

- Day, `/vj/grid` 0 against 1, clocks frozen (noise floor = two `/vj/grid` 1 replicates): CAM_0 0.050 (floor 0.049), CAM_3 0.045 (0.045), CAM_PULL_10K 0.084 (0.111). Within the floor on all three.
- Night, static CAM_0, clocks running, frames 1 s apart: `/vj/grid` 0 0.041, `/vj/grid` 1 0.335 (line overlap 0.92, line brightness ratio median 1.01). With clocks frozen the same `/vj/grid` 1 pair differs more (0.637, overlap 0.83): the difference is the viewport's frame-to-frame jitter on 1 px lines, not motion. Running clocks move no line. The strict wording (no larger with 1 than with 0) does not hold because of that jitter.
- Line share of the frame at night: first build 29 % on CAM_0 (47 % of the middle third, the far ground crowded into a web); after the fade by the cell's smaller on-screen side 5.3 % on CAM_0, 2.2 % on CAM_3.
- Frame time (`ab_round10.py`, 3 rounds interleaved per build, the builds in sequence, load 35 to 66, `fps_trustworthy` false: context only): CAM_0 day 35.4 ms (round 9 build) to 33.9 ms; orbit night 23.9 ms to 20.3 ms.

## Verdicts (one `shot-reviewer` call, 19 shots): 17 pass, 2 fail

- All 12 day shots pass R10-DAY. Reviewer on flatness: CAM_0 "a little empty but the mountains carry the shading"; CAM_3 "foreground plain is a flat uniform purple band, the emptiest day frame".
- S9_orbit_night passes (no lines on the globe). The fly pair passes R10-ATTACHED ("same ridges and vertex pattern, shifted only by camera motion").
- CAM_0 and CAM_3 night `/vj/grid` 1 fail R10-LATTICE: the flat plain "renders as a regular fixed-spacing grid, the counterexample's failure mode"; slopes show irregular mesh edges. Overall: "messy, not a clean real wireframe".
- Why: the patch mesh is a regular grid of cells, so on flat ground its real edges look like a lattice. No fix keeps real edges and passes R10-LATTICE there, so the fix pass was not spent.

## Open items

| Item | State | Next |
|---|---|---|
| Keep the real edges at night or drop them | the build has them, `/vj/grid` default 1 shows them at night | user's choice from `planet-round10-night-orbit.jpg` (grid0 against grid1). Dropping them: delete the edge block in `terrain_build` (from `# the only lines on the planet`), then `/vj/grid` is unused on the planet (contract text, `vj_grid` check row) |
| 1 px line jitter between frames | mad 0.64 between frozen replicates | only if the user keeps the edges: a wider line (Size 1.5) or a softer threshold |
| Day plain reads a little empty (CAM_0, CAM_3) | reviewer words above | no replacement look without the user's ask |
| fps table | `fps_trustworthy` false | when the machine is idle |

## Commands

```
make blender-rebuild && make blender-open
blender -b --disable-autoexec blender/scenes/synthwave_planet.blend --python blender/review/line_sources.py
blender -b --disable-autoexec blender/scenes/synthwave_planet.blend --python blender/review/attribute_readers.py -- rt_grid_phase vj_grid_speed vj_grid
.venv/bin/python blender/review/grid_diff.py DIR "A:B@BASE"
```

Through the MCP: `DN["grid_out"]`, `DN["grid_mode"]` = `day` (then exec `freeze_clocks.py`), `night` or `fly`, exec `grid_numbers.py`. Frame time: `DN["ab_out"]`, `exec(open(.../ab_round10.py).read(), {})` (own namespace). The round 9 build for a before run: `git show 93385cc:blender/scenes/synthwave_planet.blend > blender/scenes/synthwave_planet_r9.blend`, `make blender-open SCENE=r9 BLEND_r9=blender/scenes/synthwave_planet_r9.blend`, delete it afterwards. Grabs: `check_jobs.py` and `orbit_jobs.py` as in round 9, out in `blender/review/out/round10/`.

