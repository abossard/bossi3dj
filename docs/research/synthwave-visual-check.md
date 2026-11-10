# Synthwave planet: visual check

The look a retro sunset round must pass before it counts as done. The shots and rules are written before
the build. A reviewer on a different model than the author judges every grab against them.

## Shot list

Every camera, CAM_0 to CAM_10, in every combination:

| Control | Values |
|---|---|
| Time (`/vj/night`) | day 0 (sun +20°), sunset 0.5 (sun on the horizon), night 1 (sun -18°) |
| Fog (`/vj/fog`) | 0, 0.5, 1 |
| Eclipse (`/vj/eclipse`) | 0, 1 |

- Moon Phase: 1 (full) for every shot, except eclipse 1 at day and sunset, which uses 0 (new) so the moon can cover the sun.
- 11 × 3 × 3 × 2 = 198 grabs. CAM_4 also gets 4 positions around its loop (0, 25, 50, 75%) at fog 0 and eclipse 0 for each time (12 more grabs).
- Moving cameras (CAM_4, CAM_5, CAM_6) are grabbed at loop position 0 in the main matrix.
- Each grab is the On-Air Camera's view as Syphon sends it, 960×540, taken after the frame has settled (fog, TAA and the flamingo flock after the cut).
- File name: `CAM_<n>_<day|sunset|night>_f<0|05|1>_e<0|1>.png`. CAM_4's loop grabs add `_p<0|25|50|75>`.
- Contact sheet: one per camera, with time down the rows and fog × eclipse across the columns, every tile labelled. There's one more sheet for the CAM_4 loop.

## Pass rule

- A shot passes when every global rule, its time rule, its fog rule, its eclipse rule and its camera rule hold.
- One broken rule fails the shot.
- A fail names the rule ID and where in the frame the problem is.
- The round is done when every shot passes.

## Global rules (every shot)

| ID | Rule |
|---|---|
| G1 Palette | Reads as retro synthwave (magenta, pink, orange, violet, navy, neon cyan). No grey, washed-out or muddy frame. |
| G2 Artefacts | The wireframe covers all terrain (flats, hills and mountains) at every distance, in the same style everywhere: the same cyan, line width, glow and spacing on slopes as on flat ground. No LOD seams: the wireframe keeps the same spacing and line width across the whole ground, with no square patch borders, height steps, cracks or sudden pattern changes. This holds from the cameras and from a free view. No checkerboard, blocky, stepped or banded pattern in fog, sky, water or ground. No flat-coloured slabs, holes, cracks, magenta or black missing-texture patches. No bright blotches on water. |
| G3 Subject | The camera's subject (see the camera rules) is in frame and readable. No more than 60% of the frame is featureless (blank sky, one hillside, solid fog), except CAM_6. |
| G4 Horizon | The horizon is visible and clean, with no painted band or "ocean" wall in front of it. At fog 1 the far horizon may be veiled, but the near ground still reads. |
| G5 Grounding | Pyramids stand on the ground, flamingos stand on water or shore (or fly). Nothing floats or is sunk, and the camera isn't inside geometry. |
| G6 Water | Water sits only in valleys, rivers, lakes and sea, never on slopes or mountains. It reads as water (reflection, ripples). No glassy bowl, no sawtooth shore edge. |

## Time rules

| ID | Rule |
|---|---|
| T-day | Clean pastel sky, bright ground, sun disc with a tight glow when in frame. No stars. |
| T-sunset | A poster gradient: orange under the sun, through pink and magenta, to navy above. The sun sits on the visible horizon with level stripes when in frame. |
| T-night | Dark sky with the neon wireframe on the ground, a faint violet horizon and visible stars. The ground reads as silhouettes, not pure black. The moon is visible when it's in frame. The only things that glow are the neon lines (the cyan terrain wireframe and the pyramid edge lines, each with a slight glow, not bright white outlines). There is one line layer on the ground, the wireframe: no second grid of violet or magenta lines on top of it and the pyramid capstones (point lights). Palms, banks and other surfaces don't glow. Water doesn't glow and only reflects. Shockwaves never glow, at any time of day. In fog, the capstones get a soft halo and the wireframe lights the fog faintly from below. |

## Fog rules

| ID | Rule |
|---|---|
| F0 | No fog. Far mountains crisp. |
| F05 | Haze lies in the valleys and low ground. Mountain tops and sky stay clear, and the subject is fully readable. |
| F1 | Thick, soft, rolling fog fills the valleys and veils the far mountains. The sky above stays clear and the subject still reads. Fog edges are smooth, with no hard flat top plane and no visible slices or checker pattern. It glows at sunset. |

Photo references for the fog rules are in `visual_check/reference_fog/` on the planet branch (Wikimedia Commons, credits in `credits.tsv`):
- **Day:** a bright, lumpy sea of fog fills the valleys, with ridges standing out of it as islands. Low layers hug the fields, with trees dark against them.
- **Sunset:** the fog takes the sky's colours, warm where the sun hits it and blue-violet in the shade. The sun glows through it with a halo, and each farther ridge is paler.
- **Night:** the fog is dark and shows only where light hits it, as halos and beams around lights and a glow over lit ground. The sky above stays dark and clear. It has no glow of its own.

## Eclipse rules

| ID | Rule |
|---|---|
| E0 | Normal full moon (where the moon is in frame). |
| E1-day, E1-sunset | With the sun in frame, the moon disc covers the sun with a ring of corona. With the sun out of frame, the shot only has to meet the other rules. |
| E1-night | With the moon in frame, it is fully red to copper. |

## Camera rules

| Camera | Subject and rule |
|---|---|
| CAM_0 | Wide, up the plaza: pyramids and the sun direction in frame. |
| CAM_1 | Low over the nearest river, looking downstream: the river leads into the frame, and the near shore is natural (no glassy bowl). |
| CAM_2 | Pyramid hero shot: the pyramids dominate. At fog 1 the fog around them is smooth (no checker). |
| CAM_3 | Tilt up to the moon over the pyramids: the moon is in frame when it's above the horizon. When it's below, the shot holds the sky just above the horizon, not the ground. |
| CAM_4 | Flyover loop: at every loop position the horizon is visible and no single hillside covers more than half the frame. |
| CAM_5 | Orbit around the pyramids: the pyramids are in frame and near the centre. |
| CAM_6 | Orbit, whole planet: the full disc is in frame and not cut by the frame edge (the moon may pass in front of it). It's a space shot: judge it by S1-S7 in place of G1, the time rules and the fog rules (fog doesn't reach orbit). |
| CAM_7 | Flamingo flock on water next to pyramids, low, toward the sun: many flamingos, the nearest clearly readable (not a few pixels). At sunset and night they may have taken off. |
| CAM_8 | River into the sea, looking downstream: the river meets the sea, with a clean shore (no sawtooth). |
| CAM_9 | Far pyramid group with the sun behind: the pyramids are silhouetted against the sun at sunset. |
| CAM_10 | Low pass along a coast: sea on one side, with no surf blotches by day and no cyan blotches at night. |

## System view (zoomed out)

The scene must be one coherent model, seen from anywhere and not only through its cameras. Zoomed out, it reads as a serious star system simulation. A new camera, CAM_SYS, sits far out with the Planet, the moon and the sun's direction in frame. It's grabbed at day, sunset and night × eclipse 0 / 1. It also gets 4 free viewpoints around the system (front, back, above, the moon's far side) at night 0.5.

| ID | Rule |
|---|---|
| S1 Planet | A whole sphere modelled all the way round: land, sea, mountains and rivers on every side, with no missing patches, black caps or square tiles. |
| S2 Light | The Planet and moon are lit by the sun: a soft day/night terminator that faces the sun, and a moon phase that matches the angle seen from that viewpoint. |
| S3 Atmosphere | A thin atmosphere limb, concentric with the Planet and brighter on the day side. No offset ring. |
| S4 Moon | A whole sphere from every side. No dome, cut or flat face. |
| S5 Sun | Round from every angle, with bright glare. Never an ellipse or flat card. |
| S6 Sky | The real sky, from NASA's Deep Star Maps 2020 (Hipparcos, Tycho-2 and Gaia), the same from the ground and from space: real constellations, real star colours and the real Milky Way. No procedural star noise, no repeated or mirrored patches, no seams, no rings or circles of stars, and no stars pulsing on the beat. Dark-sky contrast: the empty sky between stars is near black, not a grey speckled veil. Bright stars stand out as crisp points, the faint field stays subdued, and the Milky Way is a subtle band with dark dust lanes. No purple haze band or smear. |
| S7 Scale | Sizes and distances agree with the Star System (Planet 16 km, moon 11.5 km at 50 km). Nothing pops in, flips or changes size as the view moves. |

The Planet looks like the same place at every distance. Its land, sea, mountains and rivers keep their colours and shapes from the ground to orbit: magenta and violet land, the same water, the same coastlines. Only the wireframe lines thin out as they shrink on screen. What makes the system view a serious simulation is the light (a real terminator, the atmosphere limb, sun glint, the star sky) and the scale, not a different palette.

| ID | Rule |
|---|---|
| S9 Orbit quality | From far away the Planet is a showpiece:<br>- a perfectly round, smooth limb with no facets, ragged edge or visible triangles;<br>- one thin atmosphere hugging the limb all the way round, brighter on the day side, with a warm pink-orange band along the terminator, and no detached or offset crescents;<br>- mountain ranges readable through relief shading, plus rivers and lakes;<br>- crisp, smooth coastlines with clear land/sea contrast;<br>- a sun glint that is a soft round or elongated highlight, not a white blob;<br>- a night side that is dark, with the wireframe as a faint fine pattern;<br>- a moon with a clean, sun-lit, unaliased surface. |
| S8 Continuity | A space shot (CAM_6, CAM_SYS) and a ground shot of the same region show the same colours and the same coastlines, so you can tell it's the same Planet. No Earth-blue ocean or grey-tan rock that exists only from far away, and no blocky or stair-stepped coastlines. |

## Flight (one continuous camera, `/vj/flight` 0..1)

A procedural camera, different each run, that one OSC value carries from orbit down to the water without a cut. Moving the value flies the camera; it never teleports.

| Range | Stage | Looks like |
|---|---|---|
| 0 | Orbit | A slow orbit around the Planet that frames the star system: the Planet with the moon, the sun's glare and their alignments. |
| ~0.33 | Approach | A spaceship landing approach: a descending curve toward a landing region. The atmosphere edge grows and the horizon flattens out. |
| ~0.66 | Skim | Fast and low over the mountains, following the ridges with look-ahead and banking through passes. |
| 1 | Hover | Hovering a few metres over the sea, lakes or rivers, drifting. `/vj/boost` pushes the accelerator: a surge forward with a wider view. |

| ID | Rule |
|---|---|
| FL1 Smooth | The camera eases between stages and never jumps, stalls or turns sharply, even when the OSC value jumps. |
| FL2 Detail | Terrain and water detail follow the moving camera continuously: no pop, no seam and no coarse patch near the camera at any point of the flight (not only on cuts). |
| FL3 Clearance | The camera never touches or enters the terrain or water, and never flies through a pyramid. |
| FL4 Framing | Each stage is composed: the horizon or the Planet's edge is readable, the subject leads the frame, and the frame isn't more than 60% featureless. |
| FL5 Rate | The flight holds the frame rate of the fixed cameras through a full sweep from 0 to 1 and back, including boosts. |

Proof: recorded sweeps from 0 to 1 and back at day, sunset and night, a boost sequence at the Hover stage, an fps trace over each sweep, and a frame-difference trace that shows no detail pops.

## Energy (every camera always moves)

No camera is ever static: every shot, CAM_0 to CAM_10, CAM_SYS and the Flight, is always moving. The scene knows nothing about music. It exposes plain controls over OSC, and Magic maps the music onto them (a buildup raises the energy, a drop fires a hit, a breakdown lowers the energy). Blender does no audio analysis.

| ID | Rule |
|---|---|
| EN1 Never static | Every camera moves at all times (a drift, dolly, orbit, crane or flight), even with no control input. No two consecutive frames are the same frame. The camera rules above still hold throughout the move. |
| EN2 Energy up | Raising the energy control speeds up and tightens the motion: the camera pushes in or climbs, and the pulse accents grow. It reads as winding up, not as a jitter. |
| EN3 Hit | A hit is the biggest moment: a surge of speed, a wide-angle kick, a fast swoop or blend to a new view, starting on the frame it arrives. |
| EN4 Energy down | Low energy slows and widens the motion into a floating glide. It stays moving and never stops. |
| EN5 Pulse | Each pulse (`/vj/beat`) gives a small accent (a push, a dip or a slight roll) that never shakes the frame unreadable or breaks the camera's framing rule. |

Proof: a recorded sequence per camera sweeping the energy up, firing a hit and dropping the energy, driven over OSC, plus a motion trace showing no frame without camera movement.

## Motion checks (numbers, not stills)

The planet session measures these and the reviewer reads the numbers:

| ID | Rule |
|---|---|
| M1 Cut | The worst frame on a camera cut is at most 70 ms, with the flamingo flock rebuild included. |
| M2 CAM_3 aim | The first frame after a cut to CAM_3 already has the new aim. |

Steady-60 fps is tracked separately and isn't part of this sign-off.

## Known defects going into the round

- CAM_2: checker pattern in thick fog.
- CAM_1: glassy bowl near the shore.
- CAM_10: surf blotches by day and cyan blotches on night water.
- CAM_4: flight frames looking into hills.
- CAM_8: near-shore sawtooth (re-check after the terrain change).
- The moon's horizon cut is flat and sits a few degrees above the visible horizon in low shots.
- CAM_3: aims with the old target on the first frame after a cut.
- Flamingo flock rebuild on a cut: 30-60 ms.
- Pyramids float above the ground (user screenshot `user_floating_pyramids.webp`).
- Zoomed out (user screenshot `user_zoomed_out_broken.webp`):
  - The moon is a cut dome.
  - The Planet is a black ball with one modelled cap.
  - The atmosphere ring is offset from the Planet.
  - The sun is a flat ellipse.
  - A purple haze band lies across the sky.
