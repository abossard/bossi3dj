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

## Open items for the orchestrator

- Encode step: frames to `<pass>/<clip>.mov` (codec from R4); the Depth Pass range in that video is not in `CONTRACTS.md` yet. The validator's only errors are the missing `.mov` files.
- Camera names are `ShotCamera.front` and `ShotCamera.side` (the R3 fixture uses `CAM_FRONT`, close to the Avoid word `CAM_N`).
- Cut Points come from the tables (idle_guard 0, jab_cross and take_hit 0 and 3, front_kick 0); the R3 fixture assumes `[0, 2]`.
- Remaining Clips (front_kick, take_hit, jab_cross__front) not rendered yet.
- No `make` target for these tests yet (`Makefile` is shared).
