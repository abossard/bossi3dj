# Planet look, round 9 (interim: Part A done, Part B waits for the Blender slot)

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

## Part B plan (after the orchestrator's go)

Numbers first:

```
make blender-rebuild && make blender-open
make blender-check ARGS="--only vj_nebula --no-fallback"
```

Then through the MCP: `health.py` (empty `problems`), `ground_check.py`, `cut_jobs.py` (M1, M2).

Grabs, 35 shots, one `shot-reviewer` call. Set before exec of `//../review/check_jobs.py`:

```python
N = {"set": {"vj_nebula": 0.0}, "tag": "neb0"}
DN["check_out"] = "<repo>/blender/review/out/round9"
DN["check_list"] = (
    [(c, "day", 0, 0) for c in range(11)]                      # R9-WIRE, CAM_6..8 framing
    + [(c, "night", 0, 0) for c in (0, 1, 3, 4, 5, 9, 10)]    # R9-NEB1, R9-CAM1, R9-CAM9, R9-MOON
    + [(9, "night", 0, 0, None, N), (10, "night", 0, 0, None, N)]
    + [(4, "day", 1, 0), (4, "night", 1, 0), (4, "day", 0, 0, 25), (4, "day", 0, 0, 50)]
    + [(5, "day", 0.5, 0), (5, "day", 1, 0)]
    + [(c, t, 0, 0) for c in (6, 7, 8) for t in ("sunset", "night")])
```

Plus three orbit frames from `orbit_jobs.py` (the 10 km pull-out day and night, the limb close-up), `sheets.sh` or `check_sheet.sh` to 480 px tiles, the reviewer with this rubric, verdicts to `docs/reports/planet-look-round9-verdict.json`.

Frame-time A/B (context only while `fps_trustworthy` is false): moon map 4096 against the old `*_filtered.exr` on CAM_6 night, swapped live, interleaved, three rounds. The nebula band is math only; one A/B with the band node muted on CAM_10 night.

One fix pass on failed shots, one re-grab of exactly those. `make blender-kill` at the end.
