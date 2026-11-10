# Visual check, round 8 (planet session)

Build: commit d5e3323 on `research/synthwave-planet`, all 253 grabs, same layout as rounds 5 to 7. Graft of `synthwave_pyramids.blend` (unchanged), 8k star map, Blender 5.2.3, M1 Max. No flight runtime loaded: CAM_4 flies the planet's own LOD patch sets.
- 198 matrix, 12 CAM_4 loop, 6 CAM_SYS, 4 system views at `/vj/night` 0.5, 17 `PROOF_*` (960 x 540); 16 `S9_*` (1920 x 1080).
- Sheets: `sheet_CAM_<n>.png`, `sheet_CAM_4_loop.png`, `sheet_CAM_SYS.png`, `sheet_CAM_SYS_views.png`, `sheet_PROOF_pull_out.png`, `sheet_PROOF_lod_stars.png`, `sheet_S9_pull_out.png`, `sheet_S9_orbit.png`.
- The machine ran at a load average of 30 to 280 from about 13:00 (other work on it); the grabs are settled frames, so this changes their timing, not their look.

## Changes since round 7 (cause first)

| Review item | Cause | Fix |
|---|---|---|
| Two wireframe styles: a coarse square grid on the plaza, a fine triangle mesh on the hills, faint or pink by day (G2, user: "In the same style") | every line had one width in lattice units, so lines across the view thinned away on a low view of flat ground; by day the cyan was added to the sunlit ground | each line family gets its width from its gradient along the surface and its foreshortening from the camera, about a pixel on screen everywhere; by day the wires are drawn over the ground in their cyan (93f6741) |
| Wires dropping out in patches on far slopes, changing at the LOD rings (PROOF lod rings) | their fade into the mean glow followed each facet's slant | the fade by distance alone |
| 10 km night: a second, wavy cyan line layer | the orbit lattice (600 m) lay over the ground's own wires | the orbit lattice only from 12 km up, where the ground's wires have faded |
| Concentric ring moire on the night side (CAM_6, CAM_SYS_MOON) | the orbit lattice's latitude rings round the spin axis's poles | faded out within about 16 deg of those poles |
| No warm band along the terminator; no glint (S9) | the warm band was only where the terminator meets the limb; the glint at 0.15 had gone | a warm pink-orange band along the terminator on the ground; the glint at 0.24 |
| Moon: black crater blotches (S9 CAM_6) | crater self-shadow at 10 | 5, slope gain 50 |

## Measured

- Star "seam" at x~840 (`PROOF_stars_space_north_pole`, `_south_pole`, round 7): column medians a flat 4/255 over x 830 to 850; column means at x 838 to 842 are 5.0 to 5.4 against 3.9 to 4.4 beside them, about one grey level over 5 px, at the same screen column in both shots. A faint band in screen space rather than in the map; cause not found.

## Open

- 10 km pull-out: speckled coasts and limb where the ground's patches and the globe trade pixels (softer since round 7, not gone).
- Orbit rivers: short dashes. The terrain's rivers are short coastal ones; longer rivers need the hydrology changed, which moves every ground shot's rivers.
- Limb close-up: soft land (the globe's 70 m vertices), stars magnified by the narrow lens.
- CAM_4 water wedge with a straight step and the hillside crease: the planet's own LOD patch sets (not with the Flight blocks). Not the land's mirror copies.
- CAM_4 f1 fog terraces along the bottom, CAM_4 night f1 purple haze in the far sky: not re-checked since a179c28's fog floor and moonlight changes.
- CAM_10 sunset waterline line: dimmer, (126,61,122) at (300,243), not gone. CAM_10 sunset e1: a pink oval on the water at (700,382).
- CAM_5 pale band along the top edge in fog; CAM_0 day f1 e1 band along the moon's top edge; CAM_9 night dotted grid in the sky.
- CAM_1 night water blotches and square tile edges.
- The Flight session's dark sea at 22 to 27 km out: the Flight LOD blocks (my patch sets draw a proper sea there, `../sea_test/`).
- With the user: CAM_SYS e1 (moon beside the sun from space), the straight show valley.
- M1 and M2 not re-measured.
