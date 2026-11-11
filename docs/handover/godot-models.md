# Godot Colossus Scene: the real Wanderer and Colossus 1

Branch `integration/presentable`, main checkout. Brief: bring the Nomad (Wanderer) and Grock (Colossus 1) into the Godot Colossus Scene, cost first, in three stages. Cost table: [docs/reports/godot-model-cost.md](../reports/godot-model-cost.md).

## State

- Stage 1 (cost) done, committed. Stage 2 (Wanderer) and stage 3 (Colossus) not started; they wait for the orchestrator's go.
- Prepared models committed under `godot/colossus/assets/models/{nomad,grock}/` (glTF separate: `.gltf`, `.bin`, `textures/`), 44 MB. Not used by the scene yet: `Roster` and `Wanderer` still build the stand-ins.
- Import settings that matter (in the `.import` files, committed): every model texture `compress/mode=2`, `mipmaps/generate=true`, normal maps `compress/normal_map=1`, `detect_3d/compress_to=0`; Grock `nodes/root_scale=14.0339` (28 m). Godot's headless first import had picked lossless without mipmaps.
- License: read from each archive's `license.txt` (Sketchfab's own, CC-BY 4.0, author and page URL), not from the live page.

## Numbers (stage 1, load 65 to 75, not fps-trustworthy)

- Grock: 48,675 tris, 1 surface, 17 bones, 10.7 MB textures; 3 to 5 draws with shadow; +0.2 to 0.5 ms over the stand-in; LOD 1 (24k) on the long walk.
- Nomad: 43,786 tris, 2 surfaces, 53 bones, 24 MB textures; 6 draws with shadow; +0.4 to 0.5 ms close and medium, nothing on the long walk; skinning not measurable.
- Grock's shadow, switched off: 0.2 ms at medium, nothing elsewhere. No trick built beyond the skeleton cut and texture formats (table in the report).

## Decisions

- Source `.blend` over Sketchfab glTF for both (one Grock mesh, real bone list).
- Nomad's rifle dropped (it sits in the right hand, where the grip goes).
- Nomad bones renamed in Blender to Godot's humanoid profile names: the BoneMap at import is one to one.
- Grock's normal map made from its height map at a median tilt of 12°: its own normal map is flat. Look to be judged in the stage 3 round.
- Probe timing: vsync off and `Engine.max_fps = 0` give uncapped frame times on Metal (7 to 11 ms here); the old note in `tests/cost.gd` that Metal pins 16.7 ms holds only with vsync on. Metal has no GPU timer (`viewport_get_measured_render_time_gpu` reads 0).

## Open

- Stage 2: Wanderer swap, BoneMap, AnimationTree with clip slots, hand IK, foot planting, look-at, rim light if needed, look round 4.
- Stage 3: Grock swap, Grab Points on its bones, foot IK, ragdoll (at most 24 bodies), Idle on the upper body, Shake clips, hitch check, look round 5. Grock's imported material has no `disable_fog`: the haze would swallow it on the long walk as it did the stand-in.
- Mixamo: `~/Downloads` now also holds `Walking.fbx`, `Walking-2.fbx`, `Walk In Circle.fbx`, `Sneak Walk.fbx` and `Idle-3.fbx` besides the idles; stage 2 copies what it uses into `assets/mixamo/` (git-ignored).
- `tests/*.gd.uid` of other sessions' probes (ablate, cost, framing, hitch, shake_osc, warmup) appeared on import and are left untracked.

## Commands

```bash
make godot-models          # unpack from ~/Downloads, prepare in headless Blender, re-import
make godot-model-cost      # Metal: each model alone against its stand-in, three shot distances
make godot-test
make godot-lint
make godot-check
make godot-framing
```
