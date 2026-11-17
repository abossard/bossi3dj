# Giant machine probe, round G1 (frozen 2026-11-17)

Shots: the Security Bot (Blender Studio, CC-BY) scaled to 6 m as the giant machine, 2.5 m in front of the Android, on a duel camera (profile from the side, both full figures). Exchange `hammer_hit`: the giant raises its right arm and brings it down on the Android at frame 29; the Android blocks with both arms up and is driven into a crouch, ending crouched at 57. Tiles: Eevee preview frames 0, 15, 29, 36, 57 over mid grey; plus frame 29 full-size in Cycles (64 samples) and in Eevee. Mid grey is not the Live World. The giant's materials are the asset's own, not yet converted.

| ID | Pass when | Counterexample (fail) |
|---|---|---|
| G1 | Both fighters are fully in frame in every tile. | A head, foot or arm of either cut by the frame edge. |
| G2 | The giant reads as a giant machine: heavy, massive, detail at a scale that says big. | It reads as a small robot blown up: toy-like proportions, detail too coarse for its size. |
| G3 | The giant's pose is plausible in every tile: feet on the floor, legs and arms bent sensibly, no limbs through its body. | A leg or arm flipped, twisted or stretched; a foot floating or below the floor. |
| G4 | At frame 29 the giant's striking arm comes down onto the Android. | The arm is nowhere near the Android, or nothing reads as a strike. |
| G5 | Both read against the backdrop: shapes and materials visible, not black blobs. | Either fighter mostly black or lost in the backdrop. |

Name the tile and where in it for every fail. Mark a line "not judged" when no tile can show it.
