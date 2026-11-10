# Visual check, round 6 (planet session)

Build: commit 1cea14f on `research/synthwave-planet` for 229 grabs; 5c284d9 for the 24 re-grabs of CAM_1, CAM_7, CAM_8 and CAM_10 at sunset and night with eclipse 1 (the only change between them: an eclipsed moon's image on the water). Graft of `synthwave_pyramids.blend` (unchanged), 8k star map, Blender 5.2.3, M1 Max. No flight runtime loaded: CAM_4 flies the planet's own LOD patch sets.
- **All 253 grabs predate the user's "Wireframe can cover everything / in the same style" (2bbbb56):** in them the wires draw on ground flatter than 14 deg and within 3.5 km only, bluer on the peaks. Check shots of the new wireframe: `../wire_all/` and `../wire_all/b/`.
- 253 grabs, same layout as round 5:
  - 198 matrix, 12 CAM_4 loop, 6 CAM_SYS, 4 system views at `/vj/night` 0.5 (960 x 540);
  - 17 proof shots `PROOF_*.png` (960 x 540);
  - 16 S9 shots `S9_*.png` (1920 x 1080).
- Sheets: `sheet_CAM_<n>.png`, `sheet_CAM_4_loop.png`, `sheet_CAM_SYS.png`, `sheet_CAM_SYS_views.png`, `sheet_PROOF_pull_out.png`, `sheet_PROOF_lod_stars.png`, `sheet_S9_pull_out.png`, `sheet_S9_orbit.png`.
- Sunset and night grabs are about 3 s into the flamingos' take-off; day grabs have them standing.

## Fixes since round 5 (cause first)

| Review item | Cause | Fix |
|---|---|---|
| User: "ONLY the wireframe please" (T-night, G2, S8, S9) | a planar violet grid over the wires at night, magenta wires by day, a magenta waterline | one line layer: the cyan 24 m triangle wireframe, on ground flatter than 14 deg; no grid, no waterline; the orbit lattice, and the fog lit from below, in the wireframe's cyan |
| Night water a flat glowing violet slab, no stars (CAM_1, CAM_8) | the water's own violet and a horizon-glow term with a 30% floor | near black at night; the violet only where the water mirrors the horizon; stars reflect at 0.7 |
| Eclipsed moon half black, half copper, oval (CAM_SYS night e1) | sunlit shading tinted copper; a 19 mm lens at 125 km | an even copper glow over the whole disc; CAM_SYS 300 km out at 40 mm |
| Bright moon band on the night sea at e1 (CAM_10, found in this round) | the moon's image on the water stayed pale while the moon is copper | dim copper, no glitter |
| CAM_SYS_MOON a near-black disc | the view sat on the moon's side away from the sun | the view sits on its sunlit side |
| Stair-stepped coasts (CAM_6, S8) | sea level stopped one hydrology ring past the sea | sea level 3 rings (about 800 m) inland |
| Orbit: bold lattice patches with holes, blob lights, grey-brown blotches, white glint, atmosphere "ears", 10 km speckle | see the cause column in `docs/research/synthwave-planet.md` (round 5 review) | 600 m lattice at 0.07 over land and sea; small lights; softer relief and glint; warm limb band dimmer and tighter; relief flat inside the 8 to 12 km handover |
| Floating pyramids at 1 km (G5) | emission only: no shadows | the island's four pyramids cast a sun shadow on the ground |
| Fog: thin f1 (CAM_1, CAM_7, CAM_9), mauve-grey over the sea (CAM_10), ruler-straight top (CAM_5) | gaps between banks at 25%; low strength; no sky light in the volume; the stars' elevation fade cut the layer at eye level | gaps at 40%; CAM_1 3.5x, CAM_7 1.2x; the sky's light as a faint day emission; the fade on the haze over the layer only |
| CAM_5 night: fog glowing on its own | 300 kW capstone lamps washed half the frame through the night haze | 120 kW: a tight halo, still clear on CAM_2 and CAM_9 |
| CAM_10 grey sea, over 60% blank | the sea reflected at least half the pastel sky; framing | at least 30% reflection, a deep teal-indigo of its own by day; aimed 60 m off the shore and 45 m down |
| CAM_4 one ridge over 55% of the frame | 120 m clearance, 45% ground target | 170 m, 42% |
| Moon: pole smear, magenta rim at sunset | the plate carree pole; the rim at night only was off | polar caps from 62 deg, blurred more toward the pole; the rim by day only |
| Sun: dark blotch (CAM_0 sunset) | the island sun's spot noise, up to 30% darker (the same with the flock landed) | 8% |

## Measured

- Night water, near water at (480,520): CAM_1 sRGB (36,15,63) to (3,1,11); CAM_8 (39,17,67) to (2,0,11).
- CAM_0 fog stipple: the fix (volume tiles 4 px to 2 px) costs 7.9 ms per frame at f1 (20.4 to 28.3 ms, CAM_0 day, viewport 2832 x 1893). **Not applied**; the stipple is fainter since the fog banks have fewer gaps.
- Star map from space: no seam (column medians 4/255 over x 820 to 860, largest step between columns 1/255).
- Night sky on CAM_3 and CAM_4: no dark rectangle; median 2/255 over x 0 to 780 above y 170, rising smoothly to 3 to 6 at the right edge.

## Not defects

- `PROOF_lod_rings_day`: the "flamingos on dry ground" at (400,380), (290,220), (750,320) are palm crowns seen from above (teal fronds).
- CAM_4 night: the dark limb beside the moon is its night side. A full moon stays at least 34 deg from opposition so it misses the planet's shadow (star system check 11c), which leaves 8 to 12% of the disc dark.
- In space a solar eclipse is aligned for the camera area (the pole), so CAM_SYS e1 shows the moon beside the planet toward the sun, not over the sun. With the user (E1 in space).

## Open, not in this round's fixes

- CAM_4 water wedges (pale by day, pink at sunset) and the hillside crease at x~690: they come from the planet's own LOD patch sets, the ones the fixed cameras use without the flight runtime. With the Flight LOD blocks loaded, CAM_4 at loop 0 shows neither (Flight session grabs, notes folder `flight-proofs-r2/cam4/`). On the planet session's list; two tries failed (opaque lakes from 3.5 m, water faces kept up to 4 m dry), and the shapes point to holes at patch borders.
- The straight show valley from orbit: with the user.
- The limb close-up (S9) keeps soft land: the globe's 70 m vertices.
- M1 and M2 were not re-measured this round.

## Self-check per sheet

| Sheet | Self-check | Notes |
|---|---|---|
| CAM_0 | pass | one cyan wireframe; f1 a rolling white layer; sun clean at sunset |
| CAM_1 | risk | night water dark with horizon reflections; f1 veils the far river; the day river still shows the bed's pink patches |
| CAM_2 | pass | outlines a slight glow; tight capstone halo at night f1 |
| CAM_3 | pass | copper moon at night e1 |
| CAM_4 | **risk** | water wedges and facets (LOD) |
| CAM_5 | pass | fog top rolls; night halo tight |
| CAM_6 | pass | faint continuous lattice, small lights; moon pole soft, no spokes |
| CAM_7 | pass | f1 visible; flamingos |
| CAM_8 | pass | night water dark, reflects the horizon |
| CAM_9 | pass | halos on the capstones |
| CAM_10 | **risk** | deeper sea, more coast in frame; a thin bright line along the coast by day and sunset |
| CAM_SYS | risk | e1 by day: moon beside the sun (with the user) |
| Proofs, S9 | pass | pyramids' shadows at 1 km; coasts and limb glow even |
