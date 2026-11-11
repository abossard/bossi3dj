# Godot Colossus Scene: the real Wanderer and Colossus 1

Branch `integration/presentable`, main checkout. Brief: bring the Nomad (Wanderer) and Grock (Colossus 1) into the Godot Colossus Scene, cost first, in three stages. Numbers and decisions per stage: [docs/reports/godot-model-cost.md](../reports/godot-model-cost.md).

## State

- Stage 1 (cost): 7c6633c, c1ab047 (models out of git).
- Stage 2 (Wanderer): 80c8994 to 87b3d78.
- Stage 3 (Grock): ead637e (close grip), 90d1579 (Grock), 47ac35d and f0ff3be (stride, rig probe), b893340 (close grip room), be21465 (hitch option), e8f8154 (whole-scene cost), 4c36609 (report, sheet, README), and the commit that carries this note (round 5).
- Models are not in git (user decision of 2026-11-11). `godot/colossus/assets/models/`, `assets/incoming/` and `assets/mixamo/` are git-ignored; [godot/colossus/assets/MODELS.md](../../godot/colossus/assets/MODELS.md) lists pages, downloads, Mixamo slots and the command. `make godot-models` rebuilds them from `~/Downloads`.
- The scene: the Nomad is the Wanderer when `assets/models/nomad/` exists, Grock the first Colossus when `assets/models/grock/` exists; else their stand-ins, and the start prints one line naming what is missing. Titan and Golem are stand-ins.
- Wanderer code: `wanderer/wanderer_body.gd`, `wanderer/clips.gd`, `wanderer/wanderer_feet.gd`, `wanderer/wanderer_pose.gd`; movement in `wanderer/wanderer.gd`. `Wanderer.upper_body()` gives head, hands and hips for the close grip.
- Colossus code: `colossi/grock_colossus.gd` (rig, idle clip, Grab Points found on the mesh, foot IK, 17-body ragdoll), `colossi/rig_gait.gd` (stride, hips bob, Shake roll, head turn, foot targets on an imported rig), `Colossus.carrying` (stands while he holds on), `Roster` (`rig` per entry, `warm` prepares Grock once).
- Director: `_long_walk` raises the low camera over the Shrine slope (`clear_height`); the close grip aims at his head, hands and hips with `CLOSE_SWAY` 1.6 m of room.

## Numbers (stage 3)

- Grock: 17 ragdoll bodies; Grab Path complete (19 points); planted foot slides 0.10 m/s at 5 m/s; stands 0.00 m while carrying; ragdoll down in 4.5 s on flat land, 10.3 s on a 14° slope; haze contrast 0.99 at 1.6 km (stand-in 0.82).
- Hitch with the Reset rebuilding Grock: worst 35 ms (limit 50).
- `make godot-framing` five runs: exit 0 five times, 64 of 64 each; close grip 30 of 30; the 300 m walk 50 of 50 (it no longer crosses the 200 m shot switch, see Open).
- Whole scene, both real models against both stand-ins: +0.08 to 0.48 ms, 6 to 13 draws instead of 12 to 85.
- Look round 5: 27 of 27 pass.
- Green with and without the models folder: `make godot-test` (397), `make godot-lint`, `make godot-check` (22 effect), `make godot-smoke`.

## Decisions

- Source `.blend` over Sketchfab glTF for both. Nomad's rifle dropped. Nomad bones renamed to the humanoid profile in the prepare; Mixamo bones renamed at load.
- Stride and reach scale by leg length. Run clip `Fast Run`, walk `Walking-2`, shimmy `Braced Hang Shimmy`; `Braced Hang Hop Up` not used (pops when looped).
- Grock: the imported tree stays whole (clips address `Armature/Skeleton3D`); legs procedural over the idle clip; stride sweep from leg length and step length; Grab Points from the mesh, each on the bone that skins it; Attack and Defend clips not used (not tried for a shake-off).
- Probe timing: vsync off and `Engine.max_fps = 0`; poses read on `Skeleton3D.skeleton_updated`.

## Open

- The framing row "low hero walking from 300 m" now closes only 25 m (the giant stands while he walks toward it and roams away) and no longer crosses the 200 m switch to the near low hero camera; that switch was checked with the giant held still (320 of 320, stage 2), not in the probe.
- Telephoto low hero at 1000 and 450 m: the Wanderer (526 px at 25 m) shows larger than the Colossus behind him and pale in the haze; the reviewer could not tell which figure is which.
- Climb frames on Grock are dark: over-shoulder luma 38, close grip 25 (near black 30 and 35%); the rubric passed them.
- Grock without surface detail in the wide frames and not obviously 28 m without a reference (reviewer). Its derived normal map (median tilt 12°) was not judged separately.
- Grock has no hand bones and no eyes; the stand-in's eye glints are gone.
- Mixamo clips still to download: list in the report and in `MODELS.md`.
- Titan (302 joints, 15 textures) and Golem (59 textures, licence unconfirmed): what their archives need is in the report.
- `tests/*.gd.uid` of other sessions' probes (ablate, cost, framing, hitch, shake_osc, warmup) are left untracked.

## Commands

```bash
make godot-models            # unpack from ~/Downloads, prepare in headless Blender, copy Mixamo clips, import
make godot-model-cost        # Metal: each model, the animated Wanderer and the whole scene against the stand-ins
make godot-wanderer-motion   # headless: pose, foot sliding, pops, hands on the grips
make godot-colossus-rig      # headless: Grab Path, feet, carrying, ragdoll on flat and sloped land
make godot-wanderer-read OUT=/tmp/read   # Metal: Wanderer px and contrast in the low hero shot
make godot-hitch ARGS=again  # Metal: the Reset rebuilds the first Colossus
make godot-test
make godot-lint
make godot-check
make godot-smoke
make godot-framing
```
