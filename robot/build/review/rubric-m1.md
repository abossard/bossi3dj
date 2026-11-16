# Robot Moves review, round M1 (frozen 2026-11-16)

Shots: one contact sheet per Move from the Eevee preview (960x540, mid-grey backdrop; Eevee draws the Shadow Catcher as a plain floor, so the floor and its shadow are visible). Row 1 is the front Angle, row 2 the side Angle. Tiles in order: the first frame, each Hit frame (up to 4), the last frame; labels end in the frame number. Idle Clips and calm Moves have no Hits, so they show only the first and last frame. Judge pose and motion only, not materials or light.

Key Poses: `guard` (boxing guard, fists up, left foot forward), `low` (wide stance squared to the camera side, fists low and wide), `crouch` (deep landing crouch, rear fist down by the floor, lead arm back). The sheet name is the Move; its start and end Key Poses are in robot/build/DESIGN.md.

| ID | Pass when | Counterexample (fail) |
|---|---|---|
| M1 | Every tile reads as a deliberate humanoid pose: head, torso, two arms, two legs, balanced over the feet. | A tangled or broken pose, limbs through the body, a body leaning past its feet with nothing holding it. |
| M2 | Every Hit tile shows its impact: a limb extended at a target, a fist on the floor, a foot stomping or kicking, a body or head knocked or thrust. | A Hit tile that looks like a neutral stance. |
| M3 | No part of the Android goes through the floor; planted feet sit flat on it. | A foot, knee, fist or shin cut by the floor, a planted foot hovering. |
| M4 | The first and last tiles show the Move's start and end Key Poses as named above (both the same for a Move that starts and ends in one Key Pose). | A first or last tile in a pose other than a Key Pose. |

Name the tile and where in it for every fail. Mark a line "not judged" when no tile can show it.
