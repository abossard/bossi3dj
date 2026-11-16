# Robot live test in Magic (R8), review round 1 (frozen 2026-11-16, before the run)

One sheet: 36 tiles of the 90 s recording of Magic's Syphon output (`Main Server`), one tile every 2.5 s, left to right, top to bottom, 960x540 source. The Live World is off (no ROBOT_LIVE): the Android stands alone on transparent black, so the background is black and no Shadow Pass is visible. Judge the Android and the composite only. The recording is a viewer's view: tiles may repeat when Magic repeats a frame.

## Numbers bar (checked by `robot/magic/live_test.py analyze`, not by the reviewer)

| ID | Pass when |
|---|---|
| N1 | Magic's Graphics FPS median is at least 29 and p5 at least 24 (counts only on a quiet machine: `make status` `fps_trustworthy`). |
| N2 | Black frames 0. Stale frames at most 1 % of the video's frames. |
| N3 | Every Move change happens on a bar line (Beats a multiple of 4) and shows in the OutClip no more than 6 frames after the Beats event. |
| N4 | Every Angle cut lands on a cut point of its Move. |
| N5 | The Tier changes only on a bar line, and at every bar line equals the tier of the Section one frame before (State 3 drop, State 2 build, else calm). |
| N6 | Intensity: Move changes per bar are not lower in a higher tier. |
| N7 | At every Idle loop seam the frame difference is at most 3 times the video's median difference. |
| N8 | No frame-difference spike over 5 times the median outside 0.15 s of a cut or Move change. |
| N9 | Magic's bar lines are within 100 ms of the track's true bar lines after the first 12 s. |

## Picture rubric (the reviewer judges these per tile)

| ID | Pass when | Counterexample (fail) |
|---|---|---|
| L1 | The whole Android is in the frame, head to both feet, on the dark background, in every tile. | Head or a foot cut by the frame edge; a tile with no Android. |
| L2 | One Android per tile. | Two Androids side by side or overlaid (two Angles drawn at once). |
| L3 | Over the sheet at least two distinct views of the Android appear (a cut to another Angle shows as a different camera position or scale). | Every tile shows the same view. |
| L4 | The Android's edge is clean: no light or dark fringe, no visible rectangle or lighter box where a Clip's frame ends. | A halo, a box, or stair-stepped edge at tile size. |
| L5 | The Android reads as a humanoid machine in a pose of a fighting Move or the guard in every tile; no part is missing, black or inside-out. | A tile with a missing limb, a black part or stray geometry. |
| L6 | Tile to tile the same Android: same colours and finish in every Angle. | One Angle with a different colour, brightness or surface finish. |

Name the tile numbers (1 to 36) for every fail. Mark a line "not judged" when no tile can show it.
