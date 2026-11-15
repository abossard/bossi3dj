# Synthwave Planet, review round 17 rubric

Frozen before the build of round 17 (2026-11-15). It does not change during the round. The user (2026-11-15): "during a pulse, the pyramids need to pulse with it, and their connection to the ground needs to be realistic. edges are better, but still glitchy. frame rate is not an issue, but physical realism and good visual coherence."

## Numbers (measured before and after, same flights, same seconds)

| ID | Bar |
|---|---|
| N17-GAP | Ground-gap scan: along every site pyramid's base edge, the terrain the GPU grid draws (map plus near noise, at every ring from 3 m to 96 m cells) never lies under the pyramid's base (no floating; tolerance 0.3 m), and the pyramid's buried depth stays under 6 % of its height (no visible cut). |
| N17-PULSE | On a pulse the pyramid pixels' mean luminance swings by at least 25 % of its resting value, and no single frame step exceeds 40 % of that swing at 30 fps (an envelope, not a strobe). The pyramid's screen outline does not move with the pulse (mask IoU between pulse peak and rest at least 0.99). |
| N17-EDGE | Edge stability while the camera moves: the share of toggling pixels (more than 16 of 255 one way, then back) inside the pyramid masks drops against round 16 on the same seconds; at orbit 0.15 by at least half. |
| N17-FLICKER | The whole-frame flicker at show defaults does not rise against round 16 on the same seconds (A/B within 5 %). |

## Images (shot-reviewer)

Frames are full size (1920x1080) Syphon grabs of the live GPU terrain, controls held at show defaults unless a shot says otherwise. Set M is frames from the 90 s recording.

| ID | Line |
|---|---|
| R17-PULSE | In a pulse pair (rest, peak) the whole pyramid brightens together: faces, edges and capstone, not the edges or capstone alone. Peak and rest show the same shape and size. |
| R17-GROUND | Every pyramid sits on the ground: no gap or shadowless seam under any base edge, no sky or terrain visible through the bottom; the ground meets the faces like a buried stone (no hard straight slice through a hill, no sliver of terrain cutting across a face). |
| R17-CONTACT | The pyramid's foot reads as touching the land: the ground right round it is darkened or dusted by the pyramid (contact shade on the sun side away from it, or a soft band), not one even tone up to the edge. |
| R17-EDGE | The neon edges read as clean continuous lines along every visible ridge, near and far: not dotted, dashed, beaded or broken into specks; a far ridge reads as one line. |
| R17-COHERENT | The pyramids look part of the land: lit from the same sun side as the terrain round them, faded by the same haze at the same distance, their colours in the scene's palette. No pyramid reads as pasted on (brighter or crisper than the ground at its distance). |
| R17-HOLE | No hole or see-through opening in the ground or in a mountain peak. |
| R17-MOTION | Across set M (consecutive frames of the moving picture): no frame where a pyramid jumps, jitters, flashes as a strobe, or loses contact with the ground; edges stay continuous between neighbouring frames. |
