# Godot Colossus Scene: the real Wanderer and Colossus 1

Branch `integration/presentable`, main checkout. Brief: bring the Nomad (Wanderer) and Grock (Colossus 1) into the Godot Colossus Scene, cost first, in three stages. Numbers and decisions per stage: [docs/reports/godot-model-cost.md](../reports/godot-model-cost.md).

## State

- Stage 1 (cost) done: 7c6633c (prepare, probe, table), c1ab047 (models out of git).
- Stage 2 (Wanderer) done: 80c8994, d295f39, 1063b3f, 0129a27, 9f9aabb, and the commit that carries this note (report, look round 4, contact sheet). Stage 3 (Grock) not started.
- Models are not in git (user decision of 2026-11-11). `godot/colossus/assets/models/`, `assets/incoming/` and `assets/mixamo/` are git-ignored; [godot/colossus/assets/MODELS.md](../../godot/colossus/assets/MODELS.md) lists pages, downloads, Mixamo slots and the command. `make godot-models` rebuilds all three from `~/Downloads`, including the import settings (`tools/godot_model_import.py`) and the Mixamo copies (`tools/godot_mixamo_copy.py`).
- The scene: the Nomad is the Wanderer when `assets/models/nomad/` exists (`Wanderer.MODEL`), else the stand-in; the start prints one line naming what is missing. The Colossus is still the stand-in (`Roster` names Grock's model path but does not load it yet).
- Wanderer code: `wanderer/wanderer_body.gd` (model, clips, AnimationTree, retarget, IK, look-at, hang fit), `wanderer/clips.gd` (slots, fallbacks, Mixamo bone names, in place, stride: pure, tested), `wanderer/wanderer_feet.gd` (feet on the land, hang fit from the clip pose), `wanderer/wanderer_pose.gd` (pose without clips). `wanderer/wanderer.gd` keeps the movement; new there: the hang offsets come from the body, the turn to a grip is a damped spring, a low grip keeps him on the land, let go drops under gravity, `use_model` (probes build the stand-in).
- Director: `_long_walk` raises the low camera until it sees his knees over the Shrine slope (`Director.clear_height`).

## Numbers (stage 2)

- Walk slide 0.08 m/s median at 1.6 m/s; run slide 0.37 m/s at 4.5 m/s; hands 1.4 cm from the grip; joint velocity jumps at state changes 2.9 to 5.9 m/s against 3.3 (walk) and 15.4 (run) in steady motion; head 10° off the Colossus.
- Low hero at the Shrine start: he was hidden by the slope (contrast 0.03); now 244 px, contrast 0.71. No rim or light added.
- Cost: the animated Wanderer +0.14 to 0.42 ms over the stand-in, the same as the bare mesh.
- `make godot-framing`: exit 0 on the last run; the row "low hero walking from 300 m" failed twice after the camera change (33 and 45 of 50) and passed once (50 of 50). It depends on where the roaming giant has gone; with the giant held still, 320 of 320 samples from eight directions keep him whole, with and without the rise. The probe now prints why a sample misses.

## Decisions

- Source `.blend` over Sketchfab glTF for both (one Grock mesh, real bone list). Nomad's rifle dropped.
- Nomad bones renamed in Blender to the humanoid profile: no import BoneMap needed; Mixamo bones are renamed at load. Mixamo `Spine2` drives the Nomad's `Chest` (the Nomad has no upper chest).
- Stride and reach scale by leg length, not hip height (the Nomad's hips bone sits 0.2 m lower).
- Run clip `Fast Run` (fits 4.5 m/s), walk `Walking-2` (same as `Walking`, without skin), shimmy left `Braced Hang Shimmy` (in place; leads with the left hand, checked against the root-motion `-2`). `Braced Hang Hop Up` not used: it pops when looped.
- Grock's normal map made from its height map at a median tilt of 12°. To be judged in the stage 3 round.
- Probe timing: vsync off and `Engine.max_fps = 0` give uncapped frame times on Metal; Metal has no GPU timer.
- Poses are read on `Skeleton3D.skeleton_updated`: outside it Godot holds the pose without the modifiers.

## Open

- Look round 4: 26 of 27 pass; `4-shake-close-grip` fails `wanderer-visible` (only his hands show at the top edge). The close grip aims at `wanderer + 1.2 m` from 3 m off the grip; the Nomad hangs lower than the stand-in did (origin 2.36 m below the grip, was 1.7 m). Measure where his body lands in that frame before changing the aim.
- Stage 3: Grock swap, Grab Points on its bones, foot IK, ragdoll (at most 24 bodies), Idle on the upper body, Shake clips, hitch check, look round 5. Grock's imported material has no `disable_fog`: the haze would swallow it on the long walk as it did the stand-in. Once Grock stands still while he climbs (SPEC: "stands while he climbs"; today the stand-in roams once he holds on), the framing walk row may settle.
- Mixamo clips still to download: list in the report and in `MODELS.md`.
- `tests/*.gd.uid` of other sessions' probes (ablate, cost, framing, hitch, shake_osc, warmup) appeared on import and are left untracked.

## Commands

```bash
make godot-models            # unpack from ~/Downloads, prepare in headless Blender, copy Mixamo clips, import
make godot-model-cost        # Metal: each model and the animated Wanderer against the stand-ins
make godot-wanderer-motion   # headless: pose, foot sliding, pops, hands on the grips
make godot-wanderer-read OUT=/tmp/read   # Metal: Wanderer px and contrast in the low hero shot
make godot-test
make godot-lint
make godot-check
make godot-smoke
make godot-framing
```
