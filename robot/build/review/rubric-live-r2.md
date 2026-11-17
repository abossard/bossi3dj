# Robot live test in Magic (R8), review round 2: package v1 (21 Moves, low-quality Eevee) with the MMV effects (frozen 2026-11-17, before the review)

Same recording setup as round 1 (`rubric-live.md`): 36 tiles of the 90 s recording of Magic's `Main Server`, one every 2.5 s, 6x6, 480 px tiles; Live World off, the Android alone on black. New: the effects of #21 are on (grade per tier, glow on drops pulsing with the kick, flash and colour split on Hits, strobe on Angle cuts). Two sheets of the same tiles: plain (judge colour and grade here) and gamma-lifted 2.2 (judge shape and edges here). Tier per tile, from the run's log: calm 1, 24, 25, 26; build 27, 28, 29; drop all others.

| ID | Pass when | Counterexample (fail) |
|---|---|---|
| L1 | The whole Android is in the frame, head to both feet, in every tile. | Head or a foot cut by the frame edge; a tile with no Android. |
| L2 | One Android per tile. | Two Androids side by side or overlaid. |
| L3 | At least two distinct views of the Android appear over the sheet. | Every tile shows the same view. |
| L4 | No visible rectangle, lighter box or halo shaped like a Clip's frame around the Android. | A box or a frame-shaped edge. |
| L5 | The Android reads as a humanoid machine in a fighting or guard pose in every tile; no part missing, black or inside-out. | A missing limb, a black part, stray geometry. |
| L6 | The same Android in every tile: same colours and finish in every Angle (the tier grade aside). | One Angle with a different material. |
| E1 | Grade: the calm tiles look less saturated than the drop tiles. | No visible difference, or calm more saturated. |
| E2 | Glow: in drop tiles the bright parts of the Android carry a soft bloom; calm tiles have none or less. | No glow anywhere, or glow so strong the Android's shape is lost. |
| E3 | No effect breaks the picture: any colour split is a thin fringe round the Android, no tile is washed out to white or grey. | The Android doubled in colour, or a tile flashed to near white. |

Name the tile numbers for every fail; mark a line "not judged" when no tile can show it.
