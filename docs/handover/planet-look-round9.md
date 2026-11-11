# Planet look, round 9 (Part A and Part B done; 26 of 35 shots pass, open items below)

Branch `blender/look-round9`. Rubric, frozen before the first grab: [blender/review/rubric-round9.md](../../blender/review/rubric-round9.md). A new wish is round 10.

## `/vj/nebula`: why it did nothing

- The graft hides the island's `Nebula` volume and drops its drivers (`build_planet.py`, `star_system()`, "an 18 km purple volume ... a smear from space"), and `space_sky` feeds the island's sky nebula layer a constant. Both on purpose (S6: no purple haze band). The only Attribute reader left sat in the hidden volume.
- Fix: `space_sky` adds the star map's diffuse light (the Milky Way and its dust lanes) linearly, weighted by `vj_nebula`, night or space, and the horizon fade. Same two texture lookups as the stars (`star_texels`), a few math nodes. Constants `NEB_LO, NEB_HI, NEB_K = 0.006, 0.03, 0.35`.
- Why linear: the stars' lum^2 gain crushes the band. Texels under 0.05 give 9 % of the drawn light, median texel 0, 90th percentile 0.008 (`blender/review/star_map_stats.py`). So the empty field stays black.
- Headless: `attribute_readers.py -- vj_nebula` lists a live reader in `VJ_Sky` (and `VJ_Sky Day`). Not yet seen in the check table (Part B).
- Contract text "night nebula strength" still fits; not changed.

## Round 8 leftovers

| Item | Cause | Decision |
|---|---|---|
| Day wires washed out on sunlit slopes | `thin_w^2` (made for 0.29 m wide lines) still dims the pixel-wide lines: 0.19 at 500 m, 0.05 at 1 km; day mix capped at 0.85 | fixed: day lattice without `thin_w^2`, cap 1.0. Night wires unchanged |
| CAM_1 bank lines | under a sloped bank the water draws `land_lit * 0.6`, about 1.8 x the dry bank above (`col * 0.33`) | fixed: 0.2 |
| CAM_1 night water blotches | night hill reflection colour (0.07, 0.025, 0.12) mixed by the ripple-tilted `rzl`: noise-shaped violet patches | fixed: (0.02, 0.007, 0.035) |
| CAM_1 square tile edges | water mesh drops whole MeshGrid cells drier than 1 m | open: `+1.0` to `+2.5` adds water faces (overdraw), needs an A/B; not done |
| CAM_4 fog terraces | 32 volume slices from 1 m: 90 to 140 m deep at 300 m against a 30 m fog layer | fixed: `volumetric_start` 30 m (the fog is clear within 37 m and more). Same slice count, no cost |
| CAM_4 water step | per-triangle lake level and a hard `GREATER_THAN` in `in_r` (PL_Surface): the level jumps along straight 300 m edges | accepted for round 9: the fix moves every river's waterline, so every ground shot; a round of its own |
| CAM_4 hillside crease | hard `min(h, max(bed, bank))` kink, or per-side normals at `stitch()` borders | accepted for round 9, same reason |
| CAM_5 pale top band in fog | nothing in the fog shader; likely a partial 4 px froxel row (viewport height not a multiple of 4) | open, judged at full size in Part B; tile size 2 costs 7.9 ms, so not that |
| CAM_9 dotted sky | not found: no lattice, voronoi or fog at 25 m; round 8 sky spectra show a weak 21 px period, also on CAM_3 (8-bit night gradient bands) | open, full-size check in Part B (also with `neb0`, the band could lift it) |
| Ragged limb, speckled coasts at 10 km | per-pixel dissolve between patches and globe (`globe_share`) where their silhouettes and coasts differ | partly: coast half-width in the band 6 to 15 m, relief shading fully flat in the band. The silhouette difference stays |
| River stubs from orbit | springs only on lowland, paths masked by `lowland` again; patches show water only within 1800 m of their anchor | accepted: needs a second river curve set for the globe (build-time GN), a round of its own |
| Moon smear | colour map box-filtered to 2048 (magnified past about 650 px), height map blurred six times | fixed: 4096 wide, four passes; new cache files `*_filtered_r9*.exr` in `starmaps/` (old files kept). Frame-time A/B in Part B |

## Part B result (2026-11-11, live Blender 5.3.0)

Blender was upgraded to 5.3 that morning. Its first start made a fresh `~/Library/Application Support/Blender/5.3` without the MCP add-on, and the scene opened out of camera view (no Syphon). Fix: moved the fresh folder to the session scratchpad and copied `5.2` to `5.3` (what Blender's "load 5.2 settings" does). After that `make blender-open` reported ready.

Load stayed 50 to 220 (dotnet, OneDrive, fileproviderd): `fps_trustworthy` false the whole run. Every frame time below is context only. No fps table recorded.

### Numbers

| Check | Result |
|---|---|
| `make blender-check ARGS="--only vj_nebula --no-fallback"` | effect, 247.5 x noise floor, CAM_10 |
| `health.py` | `problems` empty |
| `ground_check.py` | no misses; 9 floats, largest 9.9 m at 5.3 km = 1.3 px (CAM_4 @0.25); JSON in `blender/review/out/round9/` |
| `cut_jobs.py` M2 | pass: aim_jump 0.0 on every cut into CAM_3 and CAM_9 |
| `cut_jobs.py` M1 | 11 of 84 cuts over 70 ms (worst 138 ms, CAM_6 to CAM_7 by day), load ~86: not judged |

### Verdicts

[docs/reports/planet-look-round9-verdict.json](../reports/planet-look-round9-verdict.json): 32 ground and space grabs and 3 orbit frames, one `shot-reviewer` call on four contact sheets plus seven full-size frames, then one full-size re-check of R9-NEB0 and R9-CAM1.

| Camera | Result |
|---|---|
| CAM_0, CAM_2, CAM_3, CAM_7, CAM_8, CAM_9 | pass (day; night where grabbed; CAM_7, CAM_8 sunset) |
| CAM_1 | pass. Night failed R9-CAM1 on the tile, passed on the full-size re-check |
| CAM_4 | day f0, day f1, night f0 pass. p25: R9-CAM4W step and G2 (accepted, see round 8 table), R9-WIRE fail (far sunlit hillside on the left has almost no wires). p50: R9-CAM4W crease (accepted). Night f1: R9-CAM4F purple haze in the mid and far sky, T-night stars hidden |
| CAM_5 | f0 day and night pass; f05 and f1 fail R9-CAM5 (pale band along the top edge) |
| CAM_6 | pass day, sunset, night (moon crisp, disc whole, limb smooth) |
| CAM_9 neb0 | pass (crisp stars, no band; the dotted sky of round 8 not seen) |
| CAM_10 | day, night pass; neb0 fails R9-NEB0, also on the full-size re-check |
| `S9_pull_2_10k_*` | pass (limb, rivers) |
| `S9_orbit_limb` | S6 fail: stars right of the limb are smeared squares |

Per rubric line (pass/fail): R9-WIRE 14/1, R9-NEB1 10/0, R9-NEB0 1/1, R9-CAM1 1/1 on tiles (re-check pass), R9-CAM4W 4/2, R9-CAM4F 1/1, R9-CAM5 0/2, R9-CAM9 2/0, R9-MOON 3/0, R9-CAM6 3/0, R9-CAM7 3/0, R9-CAM8 3/0, R9-LIMB 6/0, R9-RIVER 3/0, S6 5/1, T-night 11/1, G2 28/1, every other line all pass.

### Frame-time A/B (interleaved, three rounds, clocks frozen, inputs held; `fps_trustworthy` false)

| A/B | A ms per round | B ms per round | Decision |
|---|---|---|---|
| CAM_6 night: moon maps 4096 (r9) vs old 2048 | 20.38, 19.98, 19.96 | 21.30, 19.93, 20.14 | no cost seen: keep 4096 (R9-MOON passes on 3 shots) |
| CAM_10 night: nebula band on vs unlinked | 35.82, 35.73, 35.31 | 36.14, 34.61, 35.80 | no cost seen: keep |
| CAM_1 water tile edges | not run: the full-size re-check finds no tile edges | | |

### Fix pass: what was tried

- R9-NEB0 CAM_10: the band at nebula 0 is the stars' own `lum * STAR_K` gain on the Milky Way core texels (same run, same sky patch x 300-700, y 0-120 of 960: stars 0 gives mean 10.4 sd 5.5, stars 1 gives 17.7 sd 12.6; the nebula band adds another 10). A live cut of the star gain, `smooth(lum, 0.05, 0.2)` faded in by `1 - vj_nebula`, removed the glow and every star point too (CAM_9 neb0: 0 pixels over 50, sky sd 0.46). Not kept, not in the build. Two traps: grabs from different runs show a different sky (rt_star_ang turns), and a node relink recompiles the sky for longer than the 3 s settle.
- CAM_1 night: re-check on the full-size grab passes. No change.
- No code change for the rest (below), so no re-grab.

## Open

| Item | Evidence | Next step |
|---|---|---|
| R9-NEB0 CAM_10 core glow at nebula 0 | numbers above | a cut between point stars and the core glow: map the texel luminance of stars against the core (`star_map_stats.py` per region), or a high-pass with one blurred lookup; measure the extra lookup |
| R9-CAM5 top band in fog | rows 0 to 5 of 540 brighten with fog only (row 0: 133 at f0, 183 at f05, 219 at f1; row 8 unchanged); bottom rows and side columns flat; CAM_4 f1 flat | screen-edge froxel effect on CAM_5 only; try a camera overscan of a few px or a region height that is a multiple of the tile size, measure frame time |
| R9-CAM4F night haze at fog 1 | night fog albedo (0.06, 0.05, 0.08) lit by the blue `Fog_Moon` and a thicker night tail (`fog_layer`) | a neutral night albedo or a lower night tail; changes every night fog shot, so a round of its own |
| R9-WIRE CAM_4 p25 far sunlit hillside | reviewer: almost no lines on the left hillside | check the day lattice width at the hillside's distance (500 m+) |
| S6 limb stars at 200 mm | 8k map texel about 8 px at that lens: Linear interpolation draws squares | procedural point stars for long lenses, or accept for the proof shot |
| R9-CAM4W step and crease | accepted for round 9 (round 8 table) | its own round |
| M1 cut timing | 11 of 84 over 70 ms at load ~86 | re-measure when `fps_trustworthy` |
| fps table | not recorded: `fps_trustworthy` false | `docs/reports/blender-fps-planet.md` when the machine is idle |

## Commands

```
make blender-rebuild && make blender-open
make blender-check ARGS="--only vj_nebula --no-fallback"
```

Through the MCP (paths absolute or `//../review/`):

- grabs: set `DN["check_out"]`, `DN["check_list"]` (list in git history of this note, commit acf053d), exec `check_jobs.py`, then `freeze_clocks.py` (holds the clocks until the grabber is done)
- orbit frames: `DN["orbit_out"]`, `DN["orbit_only"] = ["S9_pull_2_10k_day", "S9_pull_2_10k_night", "S9_orbit_limb"]`, exec `orbit_jobs.py`, then `freeze_clocks.py`
- sheets: `blender/review/named_sheet.sh OUT.png 3 <grabs>` (480 px tiles, labelled)
- frame-time A/B: `DN["ab"] = {"cells": [{"name", "set", "exec"}, ...], "rounds": 3, "settle": 5, "measure": 10, "out": ...}`, exec `ab_frametime.py`; restore the B variant afterwards (the last cell stays applied)

`make blender-kill` at the end.
