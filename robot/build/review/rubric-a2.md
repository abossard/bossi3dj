# Robot Android look, round A2 (frozen 2026-11-17)

Shots: one contact sheet per Move from the low-quality package (robot/package/v1/beauty, Eevee, RGBA) laid over dark grey 0x202020, the backdrop of the package reel. The package beauty has no floor (the floor is a holdout; its shadow is a separate Pass), so floor contact is not judged here: the build's check measures it. Row 1 is the front Angle, row 2 the side Angle. Tiles in order: the first frame, each Hit frame (up to 4), the last frame; labels end in the frame number. Idle Clips and calm Moves show only the first and last frame.

The Android is the HUMANOID M2000: a hard-surface humanoid robot of separate rigid shell pieces (light grey or white shell, darker metal joints), skinned hands and neck. Key Poses: `guard` (boxing guard, fists up, left foot forward), `low` (wide stance, fists low and wide), `crouch` (deep landing crouch, rear fist down, lead arm back).

| ID | Pass when | Counterexample (fail) |
|---|---|---|
| A1 | The Android reads as one assembled robot: every shell piece sits on its limb, joints connect, nothing floats or is missing. | A forearm plate detached from the arm, a gap through the knee or elbow, a shin piece hanging beside the leg, a missing hand or foot. |
| A2 | Hands are closed fists in every guard and Hit tile, fingers curled into the palm with the thumb across or beside them. Exception: palm_strike's Hit tiles may show open palms (by design); where they do, judge only that the fingers are straight together, not splayed or bent backwards. | Open, flat or splayed fingers; a thumb sticking straight up or out; fingers bent backwards. |
| A3 | The shell reads light (white or light grey) with visible form shading against the dark backdrop; metal parts are darker but not black holes; the surface is clean. | A shell so dark it merges with the backdrop, a flat white cut-out with no shading, speckle or noise on the surface. |
| A4 | Every tile reads as a deliberate, balanced humanoid pose, and no limb or shell piece passes through another or through the body. | A forearm inside the head or chest, a thigh through the other thigh, a body leaning past its feet with nothing holding it. |
| A5 | Every Hit tile shows its impact: a limb extended at a target, a fist driven down, a foot stomping or kicking, a body thrust. | A Hit tile that looks like a neutral stance. |
| A6 | The silhouette edge against the backdrop is clean and the Android stays inside the frame. | A light or dark halo around the body, background colour bleeding through the shell, a head, fist or foot cut by the frame edge. |

Name the sheet, tile and where in it for every fail. Mark a line "not judged" when no tile can show it.
