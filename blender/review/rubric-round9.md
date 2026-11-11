# Synthwave Planet, review round 9 rubric

Frozen before the first grab of round 9. It does not change during the round; a new wish is round 10. Base rules (G, T, F, E, S) are the ones of [the visual check](../../docs/research/synthwave-visual-check.md), condensed here so this file is the only one a reviewer reads.

## Reading a shot

- File name: `CAM_<n>_<day|sunset|night>_f<0|05|1>_e<0|1>[_<tag>].png`. Tags: `p<loop %>` (CAM_4 loop position), `neb0` (`/vj/nebula` 0; every other shot has 1). Orbit shots: `S9_*`, `PROOF_pull_out_*`.
- A shot passes when every line below that applies to it holds. One broken line fails it; name the line's id and where in the frame.
- Contact sheets are triage. Never fail for banding, grids or soft edges that montage scaling makes; if a verdict needs fine detail, give `needs_full_size`.

## Every ground shot (all cameras but CAM_6 and orbit shots)

| ID | Line |
|---|---|
| G1 | Reads as retro synthwave (magenta, pink, orange, violet, navy, neon cyan). No grey, washed-out or muddy frame. |
| G2 | No LOD seam, square patch border, height step or crack in the ground or its wireframe. No checker, blocky, stepped or banded pattern in fog, sky, water or ground. No flat slab, hole, magenta or black missing-texture patch. No bright blotch on water. |
| G3 | The camera's subject (table below) is in frame and readable; at most 60 % of the frame is featureless. |
| G4 | The horizon is visible and clean, no painted band or wall in front of it. At fog 1 the far horizon may be veiled, the near ground still reads. |
| G5 | Pyramids stand on the ground, flamingos on water or shore or in the air; nothing floats or is sunk; the camera is not inside geometry. |
| G6 | Water only in valleys, rivers, lakes and sea, and it reads as water. No glassy bowl, no sawtooth shore. |
| T-day | Pastel sky, bright ground, no stars. |
| T-sunset | Orange under the sun through pink and magenta to navy above. |
| T-night | Dark sky, neon cyan wireframe on silhouetted ground, visible stars. Only the neon lines and capstones glow; one line layer on the ground. |
| F05 / F1 | Haze (f05) or thick soft fog (f1) in the valleys; the sky above stays clear; fog edges smooth, no flat top plane, no slices or terraces. |

## Round 9 lines

| ID | Applies to | Line |
|---|---|---|
| R9-WIRE | day shots with terrain in frame | On sunlit slopes the cyan wireframe is as readable as on flat ground in the same frame: lines visible, not faded into the ground colour. |
| R9-NEB1 | night shots not tagged `neb0`, with sky in frame | The Milky Way shows as a soft band with darker dust lanes, in natural star colours (white to warm). The empty sky between stars stays near black. No purple or magenta smear, no grey veil, no haze band. |
| R9-NEB0 | night shots tagged `neb0` | Stars are crisp points on a near-black sky, without a diffuse band. |
| R9-CAM1 | CAM_1 | No straight line running along a river bank. At night the river water has no blotches and no square tile edges. |
| R9-CAM4W | CAM_4 | Water edges have no straight step or wedge; hillsides have no crease line. |
| R9-CAM4F | CAM_4 at fog 1 | The fog along the bottom of the frame has no terraces (stacked flat bands). At night no purple haze in the far sky. |
| R9-CAM5 | CAM_5 at fog 05 or 1 | No pale band along the top edge of the frame. |
| R9-CAM9 | CAM_9 at night | No dotted grid or regular pattern of dots in the sky; stars are irregular. |
| R9-MOON | shots with the moon in frame | The moon's surface is crisp: craters readable, no smear, blur streak or doubled edge, no black blotches, no moire. |
| R9-CAM6 | CAM_6 | The full planet disc is in frame and not cut by the frame edge (the moon may pass in front). |
| R9-CAM7 | CAM_7 | Many flamingos on water next to pyramids, the nearest clearly readable (not a few pixels). At sunset and night they may have taken off. |
| R9-CAM8 | CAM_8 | The river meets the sea, with a clean shore (no sawtooth). |
| R9-LIMB | CAM_6, `S9_*`, `PROOF_pull_out_*` | The limb is a round, smooth edge: no ragged, speckled or stepped edge, no visible triangles. Coasts without speckle. |
| R9-RIVER | `S9_*` and `PROOF_pull_out_*` from 10 km up | Rivers read as continuous lines, not as rows of short dashes. |

## Space shots (CAM_6, orbit shots): in place of G1, T and F

| ID | Line |
|---|---|
| S1 | A whole sphere: land, sea, mountains and rivers all round, no missing patches, black caps or square tiles. |
| S2 | Planet and moon lit by the sun: a soft terminator facing the sun. |
| S3 | One thin atmosphere hugging the limb, brighter on the day side, no offset ring. |
| S6 | Real star sky: crisp points, near-black between them, no rings, seams or purple haze band. |
| S8 | Same magenta and violet land, same water as from the ground: no Earth-blue ocean or grey-tan rock. |

## Camera subjects (G3)

| Camera | Subject |
|---|---|
| CAM_0 | Wide up the plaza: pyramids and the sun direction. |
| CAM_1 | Low over the river looking downstream: the river leads into the frame. |
| CAM_2 | Pyramid hero shot: the pyramids dominate. |
| CAM_3 | The moon over the pyramids when it is up; otherwise the sky just above the horizon. |
| CAM_4 | Flyover: horizon visible, no single hillside over half the frame. |
| CAM_5 | Orbit round the pyramids: pyramids in frame near the centre. |
| CAM_7 | Flamingo flock on water next to pyramids, toward the sun. |
| CAM_8 | River into the sea, looking downstream. |
| CAM_9 | Far pyramid group, the sun behind it (silhouettes at sunset). |
| CAM_10 | Low pass along a coast, sea on one side. |
