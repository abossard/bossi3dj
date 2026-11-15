# Robot build (R5)

Node R5 of [robot-orchestrator.md](robot-orchestrator.md). Design: [robot/build/DESIGN.md](../../robot/build/DESIGN.md).

## State (2026-11-15)

- Done, Blender-free: `robot/build/moves.py` (guard Key Pose, idle, jab_cross, front_kick, take_hit), tests green (`python3 -m unittest discover robot/build/tests`, 5 tests, about 250 subtests).
- Written, never run: `robot/build/build_robot.py` (build, export, render, check, check-renders). It needs the Blender slot.
- Fastest frame steps in the tables: jab_cross 13.2°/0.23 m, front_kick 12.1°/0.21 m, take_hit 9.9°/0.06 m, idle 0.7°/0.007 m (limits 20° and 0.25 m).

## Blender part (waits for the slot)

```
B=/Applications/Blender.app/Contents/MacOS/Blender
$B -b --factory-startup -P robot/build/build_robot.py -- build
$B -b robot/build/robot.blend -P robot/build/build_robot.py -- check --out /tmp/robot_check.json
$B -b robot/build/robot.blend -P robot/build/build_robot.py -- export --package robot/package/v1
$B -b robot/build/robot.blend -P robot/build/build_robot.py -- render --package robot/package/v1 --clip jab_cross__side
$B -b robot/build/robot.blend -P robot/build/build_robot.py -- check-renders --package robot/package/v1
```

Pass bars for `check`: IK reach error ≤ 5 mm, planted sole error ≤ 5 mm, lowest point ≥ -5 mm, Key Pose end gap 0. For `check-renders`: Key Pose end diff near 0, no spikes. Then contact sheets to `shot-reviewer`.

## Unverified on Blender 5.3 (fix in the first run)

- Compositor: `compositing_node_group`, `NodeGroupOutput` as the composite, `ShaderNodeMath` in the compositor, `CompositorNodeSetAlpha` inputs, File Output items named `####` (expect `0000.png`, not `####0000.png`).
- Whether the beauty alpha stays 0 on the floor (Shadow Catcher must not leak into the beauty Pass).
- Pole angles from `calibrate_poles` (elbows out and back, knees forward), bevel `harden_normals` shading.

## Open items for the orchestrator

- Encode step: frames to `<pass>/<clip>.mov` (codec from R4); the Depth Pass range in that video is not in `CONTRACTS.md` yet.
- Camera names are `ShotCamera.front` and `ShotCamera.side` (the R3 fixture uses `CAM_FRONT`, close to the Avoid word `CAM_N`).
- Cut Points come from the tables (idle 0 to 3, jab_cross and take_hit 0 and 3, front_kick 0); the R3 fixture assumes `[0, 2]`.
- No `make` target for these tests yet (`Makefile` is shared).
