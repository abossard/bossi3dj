# Planet: round 5 review part 1, triage and code status

Branch `research/synthwave-planet`, nothing committed yet: everything below is code only, unbuilt, until the Blender slot.

| # | Item | Cause found | Change in code |
|---|---|---|---|
| 1 | Fog f1 thin (CAM_1, 7, 9), f05 haze missing (CAM_1), CAM_10 muddy veil, CAM_0 stippled lower edge | fog banks left gaps at 25% density; CAM_7 at fog_k 0.5. CAM_1 and CAM_9 need the valley floor height read in Blender; the stipple is the volume's froxels | gaps 25% to 40%, CAM_7 fog_k 0.8. CAM_1, CAM_9, CAM_10 colour and the stipple: tune in the slot |
| 2 | CAM_0 sunset: dark blotch on the sun | likely the flamingos 3 s into their take-off, crossing the sun (same spot in f0, f05, f1 only) | none yet: check in the slot (grab with the flock landed) |
| 3 | CAM_1: crack lines on the banks, zigzag waterline, cyan streaks at night | the cracks and streaks are wire fragments on slopes; the zigzag is the pink neon waterline tracing the land's triangles | wires on flat ground only (under 14 deg), day and night; waterline removed (it is a magenta line too). Glassy water and slab bank: not touched |
| 3, 4 | CAM_1 and CAM_8 night: water a flat glowing violet slab, no stars | a violet "horizon glow" term had a 30% floor, so even the near water glowed; the mirrored moon came from the island's moon arc | the glow follows Fresnel with no floor (only water seen toward the horizon carries it); star reflection 0.5 to 0.7; the mirrored moon at the real moon, its magenta rim by day only |
| 5 | E1-night: CAM_7, CAM_8 moon white | the moon is not in frame in those shots; the white point is a star (same spot at e0). E1-night applies with the moon in frame | none |
| 5 | CAM_SYS night e1: half black, half copper, oval | in the umbra the sunlit shading was tinted copper, so the far half stayed black; the oval is a 19 mm lens at 125 km stretching the moon at the frame edge | umbra: an even copper glow on the moon's rock colour; CAM_SYS 300 km out at 40 mm (the moon stays within the middle 60% of the frame) |
| 6 | CAM_6: stair-stepped coasts, lattice in patches with holes, moon smudge | sea level stopped one hydrology ring past the last sea vertex, so the coast ran along 260 m triangle edges where the fine terrain dips under 0; the lattice drew on land only | sea level carried 3 rings inland; the orbit lattice over land and sea. Moon pole smudge: not touched this pass |
| 7 | CAM_10 featureless, grey sea by day | sea colour is the pastel day sky mirrored | not touched yet: try a deeper sea colour and the framing in the slot |
| 8 | CAM_SYS day/sunset e1: moon misses the sun | from 125 km at 55 deg the camera's sun ray never crosses the moon's 50 km orbit | in a solar eclipse CAM_SYS swings to 7 deg, where its sun ray crosses the orbit; star_system.py puts the moon at the orbit point nearest the ray while it misses (no jump); verify_star_system.py passes |
| 8 | CAM_SYS_MOON: near-black moon with the glare at its edge | the view sat on the moon's side away from the sun | the view moves to the moon's sun side |
| 9 | PROOF 1 km: pyramids float; PROOF 10 km: straight pink band, muddy patches | no shadows (emission only) on an even ground; the 10 km shots predate the globe handover (45b3cc5, 08d52c1) | none yet: regrab 10 km after the build; contact shadows for the island pyramids are a possible next step |

Also in this build: the wireframe-only change (violet grid removed; wires, orbit lattice and the fog's under-glow cyan).

## Part 2 (proofs and S9)

| # | Item | Cause found | Change in code |
|---|---|---|---|
| 1 | Double grid at night (CAM_9, LOD rings, S9 pull 0 and 1 km) | the violet grid | removed (wireframe-only); re-check after the build |
| 2 | Orbit night pattern coarse, bold, patches with holes; city lights as blobs | 900 m cells at 0.12, land only; lights as city^2 | 600 m cells at 0.07 over land and sea; lights city^3 (peak within about 30 m of a site). Orientation change near the spin axis's poles stays (the lattice follows its meridians) |
| 3 | Floating pyramids at 1 km (G5) | emission-only scene: no shadows on an even ground | the island's four pyramids cast a sun shadow on the terrain (cone hull, 2 m soft edge) |
| 4 | Flamingos on dry ground (LOD rings day) | not found in code yet | check in the slot which flock they are |
| 5 | Grey-brown blocky blotches; straight valley strip | relief x3 with a 0.12 shade floor; the strip is the island's show valley (10 km long, straight north from the plaza) | relief x2, shade floor 0.3. The valley: not changed (moving it moves every ground shot); proposal below |
| 5 | Smeared land at the limb close-up | the globe's 70 m vertices seen up close | not changed this pass |
| 5 | Stair-stepped coasts, white glint blob | coasts: see part 1 (sea level 3 rings inland); glint at 0.35 burnt white | glint 0.15, a broader lobe (power 30) |
| 6 | Atmosphere "ears" | the warm terminator band as bright as the day side, its tail visible over the dark night limb | warm band at 0.7 and fading twice as fast past the limb |
| 7 | Moon pole smear, black blotches | the plate carree pole (cap blend from 65 deg is not enough) | not changed: needs the moon's node tree in Blender (caps like the star map's) |
| 8 | Star seam at x~840, smudge at (790,420) | no seam measurable: column medians 4/255 flat over x 820-860, largest column step 1/255 in the whole frame. The smudge sits about 20 deg from the south celestial pole, where the Magellanic Clouds are | none |

Proposal (needs the user's OK, it changes every ground shot's composition): bend the island's show valley beyond 2.5 km from the plaza so it reads as a natural valley from orbit.
