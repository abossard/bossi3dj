# Robot live test in Magic (R8), review round 3: package v1 of 0f2d645 (31 Moves with the 10 Exchanges on the duel Angles, low-quality Eevee), effects on, solo and duel Angles (frozen 2026-11-18, before the review)

Same recording setup as rounds 1 and 2 (`rubric-live.md`, `rubric-live-r2.md`): 36 tiles of the 90 s recording of Magic's `Main Server`, one every 2.5 s, 6x6, 480 px tiles; Live World off, no backdrop, the fighters on black. New: duel Angles, where the Android fights the giant machine (Exchanges). Two sheets of the same tiles: plain (judge colour and grade here) and gamma-lifted 2.2 (judge shape and edges here). From the run's log: calm 1, 24, 25, 26; build 12-16, 27-29; drop all others. Duel Angle 3-11, 18-24, 31-36; solo Angle all others.

| ID | Pass when | Counterexample (fail) |
|---|---|---|
| L1 | The whole Android is in the frame, head to both feet, in every tile. | Head or a foot cut by the frame edge; a tile with no Android. |
| L2 | One Android per tile. | Two Androids side by side or overlaid. |
| L3 | At least two distinct views of the Android appear over the sheet. | Every tile shows the same view. |
| L4 | No visible rectangle, lighter box or halo shaped like a Clip's frame around a fighter. | A box or a frame-shaped edge. |
| L5 | The Android reads as a humanoid machine in a fighting or guard pose in every tile; no part missing, black or inside-out. | A missing limb, a black part, stray geometry. |
| L6 | The same Android in every tile: same colours and finish in every Angle (the tier grade aside). | One Angle with a different material. |
| D1 | Duel tiles show the giant machine with the Android, both readable as two separate fighters facing each other. | A duel tile with no giant, or the two merged into one shape. |
| D2 | Solo tiles show the Android alone, no giant or part of it. | A giant limb in a solo tile. |
| E1 | Grade: the calm tiles look less saturated than the drop tiles. | No visible difference, or calm more saturated. |
| E2 | Glow: in drop tiles the bright parts carry a soft bloom; calm tiles have none or less. | No glow anywhere, or glow so strong a fighter's shape is lost. |
| E3 | No effect breaks the picture: any colour split is a thin fringe round a fighter, no tile is washed out to white or grey. | A fighter doubled in colour, or a tile flashed to near white. |

Name the tile numbers for every fail; mark a line "not judged" when no tile can show it.
