# Robot build (R5)

Node R5 of [robot-orchestrator.md](robot-orchestrator.md). Design: [robot/build/DESIGN.md](../../robot/build/DESIGN.md).

## State (2026-11-16)

- `robot/build/moves.py`: guard Key Pose, idle_guard (Idle Clip), jab_cross, front_kick, take_hit. Tests green: `python3 -m unittest discover robot/build/tests` (7 tests, incl. the Idle Clip loop seam).
- `robot/build/build_robot.py` runs on Blender 5.3 (build, export, render, check, check-renders). `robot/build/robot.blend` is generated and git-ignored.
- Rendered in `robot/package/v1/` (media git-ignored): jab_cross__side (58 frames, frames 0 and 29 re-rendered with the final visor), idle_guard__front and idle_guard__side (58 frames each). Manifest, Clip Data and Camera Track exported for all 8 Clips; the Manifest has `idle: true` on idle_guard only.
- Render: Cycles Metal, 128 samples, adaptive 0.02, OIDN, bounces 6/2/3, caustics off, about 28 s per frame on the M1 Max.

## Numbers

- `check` (all 4 Moves): planted ankle gap 0, planted sole error 0, lowest point 0, Key Pose end gap 0. Hand reach "error" at punch and kick Hits is intended overreach.
- `check-renders` (mean abs pixel diff, 0..1):

| Clip | last to first | seam neighbours | median step | max step | spikes |
|---|---|---|---|---|---|
| idle_guard__front | 0.00001 | 0.00008, 0.00008 | 0.00041 | 0.00082 | none |
| idle_guard__side | 0.00001 | 0.00007, 0.00007 | 0.00029 | 0.00040 | none |
| jab_cross__side | 0.00002 | 0.0001, 0.0002 | 0.00071 | 0.00376 | none |

- Idle loop step is about 3% of the median frame step: no visible seam.

## Fixes from the first Blender run

- File Output: `format.media_type = "IMAGE"` before PNG, `file_name = ""` (else `robot0029.png`).
- Shadow Pass coverage 13.6% from set shadows: set objects `visible_shadow = False` (1.9%).
- Dark streak at the right edge: one unbroken 12 m catcher plus a camera-invisible floor.
- Visor read cream-white: AgX desaturates bright emitters. Strength 1.5, colour (1, 0.35, 0.03), no specular.

## Commands

```
B=/Applications/Blender.app/Contents/MacOS/Blender
$B -b --factory-startup -P robot/build/build_robot.py -- build
$B -b robot/build/robot.blend -P robot/build/build_robot.py -- check --out /tmp/robot_check.json
$B -b robot/build/robot.blend -P robot/build/build_robot.py -- export --package robot/package/v1
$B -b robot/build/robot.blend -P robot/build/build_robot.py -- render --package robot/package/v1 --clip idle_guard__front [--frames 0-57]
$B -b robot/build/robot.blend -P robot/build/build_robot.py -- check-renders --package robot/package/v1
zsh robot/build/review/clip_sheet.sh robot/package/v1 idle_guard__front OUT.png 0 15 29 57
```

Review: `robot/build/review/rubric-r1.md` (frozen), sheets to `shot-reviewer`.

## Review (rubric R1, frozen)

- jab_cross__side: all of R1 to R7 pass after the visor fix. The reviewer calls the visor a borderline pass (a little pale at its centre).
- idle_guard__side: all lines pass.
- idle_guard__front: R1 fails because the arms and legs stack along the body axis, so two of each can't be told apart at tile size. R3 can't be judged because left foot forward isn't readable from the front. The camera at (2.41, -3.44, 0.55) reads too frontal. Next round: move it further to the side for a real three-quarter view, then re-render.

## Beauty Pass as qtrle (2026-11-16)

- `render` writes the beauty Pass with Blender's FFmpeg writer as QuickTime Animation (qtrle, argb) to `beauty/<clip id>.mov`; `--beauty prores|png` for comparison. Shadow and Depth stay frame sequences.
- Alpha proof (`robot/build/review/beauty_alpha_check.py`, jab_cross__side frames 13 to 16, 16 samples, decoded with ffmpeg against the PNG render of the same frames): alpha 0 wherever the PNG is 0, 255 wherever it is 255, edge pixels (4k to 7k per frame) within 1 step. RGB on covered pixels: qtrle mean 0.66, max 3 (of 255); ProRes 4444 mean 2.1, max 26.
- Size per Clip, 58 frames (`robot/build/review/encode_sizes.py`: the same 128-sample PNG frames through Blender's writer): idle_guard__front qtrle 19.8 MB / ProRes 29.6 MB, idle_guard__side 16.7 / 29.1, jab_cross__side 17.6 / 29.3. qtrle is 0.57 to 0.67 of ProRes: the transparent background compresses well under run length coding.
- `check-renders` and `clip_sheet.sh` decode the movie with ffmpeg. `check-renders` on a movie measures display values (8 bit), on PNG linear floats: compare ratios, not absolute numbers across the two.
- The package Clips are still PNG frames; re-rendering them as qtrle takes about 28 s per frame.

## Front Angle camera (rubric-r2, frozen, 2026-11-16)

- Round 2 (-45°): fail F1/F2, figure small and its visible side dark. Round 3 (-70°, 32 mm, camera-side fill): fail F1/F2 (read as profile), F7 (the fill mirrored white in the polished head).
- Round 4 (-35°, 32 mm, aim 1.05 m, no fill): all four sheets pass F1 to F7. `review/camera_sweep.py`: chest 3° off face-on, eye points 37 px apart, feet 259 px, hands 121 px, points inside x 783..1197, y 250..972.
- One F6 fail on the full-size jab_cross frame 29 ("no shadow discernible") is a review-backdrop artefact: the Shadow Pass alpha peaks at 0.97 under the feet (side Angle 0.97, passed R6), black over the near-black #2a2420 backdrop. Shadow strength is the user's taste call, to be judged over the Live World in Magic.
- `review/round4.sh` reproduces the round; `review/full_render.sh idle|rest` renders the Clip Library.

## v1 Clip Library render (R6, 2026-11-16)

- `review/full_render.sh idle` then `rest`: 8 Clips x 58 frames at 64 samples, beauty qtrle `.mov`, Shadow PNG and Depth EXR frames, then export. 7414 s in all (2.1 h, about 16 s per frame, machine load 40 to 80).
- Flicker at 64 against 128 samples, qtrle against qtrle, idle_guard__side: median step 0.00044 (128: 0.00043), seam 0.00013 (0.00012), last to first 0.00002 (0.00002).
- `check-renders` (8-bit display values): last to first 0.00002 to 0.00009 on every Clip. The flagged "spikes" (steps over 3x the median) fall in runs around the Hits (frames 13 to 20 and 23 to 39), where the punches and the kick move fastest: motion, not flicker (flicker would be single frames).
- Size: beauty qtrle 16.8 to 18.3 MB per side Clip, 29.7 to 31.3 MB per front Clip (the bigger figure), 212 MB in all; Shadow PNG frames 31 to 42 MB per Clip; Depth EXR frames 471 MB per Clip. Package 4.1 GB with the frame sequences (d5 budget 20 GB).
- Validator (`robot/magic/manifest.py`): 16 errors, all `file missing` for `shadow/<clip>.mov` and `depth/<clip>.mov`; every beauty file is found. They wait for the encode step.
- `make test`: exit 0 (python suites 59, 65, 66 OK; Godot 430 passed; feature check 22 effect, 0 error). `robot/build/tests` is not in it (7 tests OK on their own).

## Open items for the orchestrator

- Encode step: frames to `<pass>/<clip>.mov` (codec from R4); the Depth Pass range in that video is not in `CONTRACTS.md` yet. The validator's only errors are the missing `.mov` files.
- Camera names are `ShotCamera.front` and `ShotCamera.side` (the R3 fixture uses `CAM_FRONT`, close to the Avoid word `CAM_N`).
- Cut Points come from the tables (idle_guard 0, jab_cross and take_hit 0 and 3, front_kick 0); the R3 fixture assumes `[0, 2]`.
- No `make` target for these tests yet (`Makefile` is shared).
