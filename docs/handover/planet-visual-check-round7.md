# Visual check, round 7 (planet session)

Build: commit 45d7b4d on `research/synthwave-planet`, all 253 grabs. Graft of `synthwave_pyramids.blend` (unchanged), 8k star map, Blender 5.2.3, M1 Max. No flight runtime loaded: CAM_4 flies the planet's own LOD patch sets.
- Same layout as rounds 5 and 6: 198 matrix, 12 CAM_4 loop, 6 CAM_SYS, 4 system views at `/vj/night` 0.5, 17 `PROOF_*` (960 x 540); 16 `S9_*` (1920 x 1080).
- Sheets: `sheet_CAM_<n>.png`, `sheet_CAM_4_loop.png`, `sheet_CAM_SYS.png`, `sheet_CAM_SYS_views.png`, `sheet_PROOF_pull_out.png`, `sheet_PROOF_lod_stars.png`, `sheet_S9_pull_out.png`, `sheet_S9_orbit.png`.
- Sunset and night grabs about 3 s into the flamingos' take-off; day grabs have them standing.

## Changes since round 6 (cause first)

| Review item | Cause | Fix |
|---|---|---|
| User: "Wireframe can cover everything / in the same style" (G2) | wires on ground flatter than 14 deg and within 3.5 km only, bluer on the peaks | one cyan on all ground at every distance; line width kept near a pixel on slopes; lines while a cell is over about 3 px, then their mean glow by day and nothing at night (2bbbb56) |
| Orbit night: black dash strokes (rivers) | the globe's rivers mixed in with an unlit colour at night | rivers by day only, about 200 m wide at 70% over the land |
| 10 km: ragged limb and land edge; speckle at coasts | a sea-level globe dissolving into the patches' true relief; coasts placed from different resolutions | the globe displaced to the true height inside the band (a sphere again from 20 km); coasts softer (6 m) inside the band |
| Limb close-up: smeared stars | the plate carree's sideways stretch, up to 3x at 70 deg declination | star caps to 35 deg from each pole (at most 1.7x) |
| Moon pole smear, black crater blotches (CAM_6 day, S9) | spokes from the maps' polar data; crater self-shadow at 20 | cap blur strong out to 27 deg from the pole; self-shadow at 10 |
| CAM_2 f1: dotted grid in the night sky, checker in sunset fog, white slab by day | its fog-free radius 80 m, under the 150 m where the volume's froxels dither; the sky light in the day fog at 0.5 | 150 m; 0.3 |
| CAM_4 f1: stepped fog terraces | the fog floor took each texel from the nearest hydrology vertex (260 m) | weighted over the 4 nearest |
| CAM_4 night f1: purple glow over the far sky | moonlight on the night haze at 0.25 | 0.12 |
| CAM_4 65% blank sky | 42% ground target | 48% |
| CAM_1 night: violet blotches on the water | the horizon reflection at 0.07 blue | 0.04 |
| CAM_10 sunset: bright line at the waterline | the ground just under the water near a bank drew the sea's sky reflection in front of the hill's mirror image | under a sloped bank, down to 2 m, it draws the bank; the line went from (170,85,165) to (126,61,122) at (300,243), not gone |
| CAM_5 night: fog glowing on its own | 300 kW capstone lamps | 120 kW (round 6, 1cea14f) |
| Eclipsed moon's image on the night sea | pale while the moon is copper | dim copper, no glitter (round 6, 5c284d9) |

## Measured

- CAM_10 sunset waterline at (300,243): sRGB (170,85,165) in round 5, (146,72,141) in round 6, (126,61,122) now.
- CAM_0 fog stipple fix (volume tiles 4 to 2 px): 7.9 ms per frame, not applied.

## Not defects

- CAM_4 night: the moon's dark limb is its night side (a full moon here stays at least 34 deg from opposition, star system check 11c).
- `PROOF_lod_rings_day`: palm crowns, not flamingos.

## Open

- CAM_4 water wedges and the hillside crease: from the planet's own LOD patch sets (the Flight LOD blocks show neither). Not the land's mirror copies (no change with them off). The left wedge is submerged ground showing where no water face covers it (it changed with the bed's colour); the right one, with its straight edge, looks like a step between two water levels.
- CAM_10's waterline line: dimmer, not gone.
- Pale band along the frame top in fog (CAM_5, CAM_0 top): the fog volume at the frame edge; cause not found.
- Limb close-up: soft land (the globe's 70 m vertices).
- CAM_1: square edges in the water (likely water patch borders).
- Flight finding (Hover, Skim): lakes 200 to 300 m up seen from 4 to 45 m read as a flat dark slab with no reflection; at night almost black. Lakes reflect only their own sky by Fresnel, which is little at steep angles.
- With the user: CAM_SYS e1 (moon beside the sun from space), the straight show valley.
- M1 and M2 not re-measured.
