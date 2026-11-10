# OSC contract at 0..1 (node C1, branch `osc/contract`)

State 2026-11-10: done and committed on `osc/contract`, not pushed. `make test` green (magic 44 + 1 skipped live, osc 21, blender 6, godot 71 after `make godot-import` in this worktree).

## What changed

- `osc/contract.json` is the one source of the 38 rows: wire kind, range, default, and per scene the scene range, unit and effect. `osc/contract.py sync` (`make osc-sync`) writes the table in `osc/CONTROLS.md` and the `SCALES` block in `blender/blender_osc_bridge.py`. `osc/tests/test_contract.py` fails when either copy drifts, and reads `blender/scenes/synthwave_runtime.py` (`DEFAULTS`, `RANGES`, `TRIGGERS`, by `ast`, no bpy) to check that each wire default maps to the runtime default.
- Rules in CONTROLS.md replace "Open mismatches": 0..1 on the wire, indices are whole numbers, triggers keep their strength, wire values are clamped to the row, `/vj/cam N` is the Nth shot 0-based and clamped, `/vj/cam_auto` (0 or 1, default 1) hands cuts to the scene's director (Godot follows, Blender ignores), a scene ignores unknown addresses and keeps the last value (nothing expires).
- Bridge: `scale_wire`, `wire_to_scene`, `camera_index` are pure (bpy import is optional). Scaling happens where OSC enters `tick()`, so `apply()` and the scene page on 9210 still work in scene units. Unknown addresses (and `/vj/cam_auto`) are counted in `bridge.ignored` and never written. A scaled float is also clamped to the property's own UI min and max. `/vj/cam N` takes `CAM_N` or the highest camera below it.
- Magic generator: every Out Global is 0..1, seeds equal the wire defaults, senders clamp to the row's wire max. New senders for `cam_auto`, `flight`, `boost`, `blend`, `energy`, `hit` (Globals `Flight`, `Boost`, `Blend`, `CamEnergy`, `Hit`, `CamCount`, `OutCamAuto`). `CamAuto` drives both the cutter and `/vj/cam_auto`. `FogScale` default is now 0.26 (x1000 m).
- `magic/show_magic.py` builds `magic/projects/show.magic`: the same project with `SyphonClient` `CAM_OUT - Blender` and `COLOSSUS_OUT - Godot`, a `Mix` (Amount = Global `SceneMix`, 0 Blender, 1 Godot) in front of the effects, OSC to the relay on 9200.
- `osc/lab.py` serves `/api/contract`; `osc/index.html` has one slider per row in wire units at the wire default, a trigger button per trigger, "all to default", and generator ranges that follow the picked row.
- `osc/sweep.py` (`make osc-sweep`): min, default, max per address (trigger fires once), sends only.

## Commands

```bash
make test
make osc-sync
make magic-build
make osc-sweep ARGS=--dry-run
make osc-sweep ARGS="--target godot --seconds 2 --only '^/vj/fog'"
python3 magic/magicproj.py check magic/projects/show.magic
```

## Live check left for Blender (orchestrator, needs the live Blender)

1. The `.blend` holds an internal copy of the bridge (text block `blender_osc_bridge.py`, filepath `//../blender_osc_bridge.py`). It must be the new file: in Blender `"SCALES" in bpy.data.texts["blender_osc_bridge.py"].as_string()` is `True`. If not, reload the block from the file and restart the bridge (`bpy.app.driver_namespace["vj_osc_bridge"].close()`, then `bpy.data.texts["blender_osc_bridge.py"].as_module().start()`), or rebuild.
2. Send to udp 9201 (`make osc-sweep ARGS="--target blender --only '^/vj/(intensity|fog_height|fog_scale|cam|cam_auto|shock)$' --seconds 1"` or five single sends from the lab page) and read `bpy.context.scene`:

| Message | Expected |
|---|---|
| `/vj/intensity 0.5` | `vj_intensity` 1.0 |
| `/vj/fog_height 0.42` | `vj_fog_height` 25.2 |
| `/vj/fog_scale 0.26` | `vj_fog_scale` 260.0 |
| `/vj/cam 12` | `vj_cam` 10.0 and `scene.camera` is the highest `CAM_k` that exists (`CAM_10` planet, `CAM_6` island) |
| `/vj/shock 1.4` | `vj_shock` 1.4, a shockwave fires |
| `/vj/cam_auto 0` | no `vj_cam_auto` property, `bridge.ignored` +1 |

3. At wire defaults the scene must look as before: `make osc-sweep ARGS="--target blender --seconds 1"` ends every address on its default, then `health.py` reports no problems.

## Asks for the other sessions (rows change first, say so if a number is wrong)

- G1 (Godot): the Godot column of the table is what the contract asks. The ranges are chosen so the wire default gives today's rest look: `/vj/level` energy 1.0..2.6, `/vj/bass` weight 0.5..1, `/vj/intensity` exposure 0.2..1.8, `/vj/fog` density 0..0.0086, `/vj/fog_height` 0..95 m, `/vj/haze` 0..0.00025 (so wire 1, the default, is the tuned haze and lower only clears it). `/vj/cam` is now 0-based (0..4 for 5 shots, clamped), not "1..5, 0 auto"; `/vj/cam_auto` 1 is the director. Values are held, not dropped after 2 s. The shock trigger keeps its value, 1.4 and above is a drop.
- B1 (Blender page and runtime): suggest `RANGES["vj_fog_height"] = (1, 60)` (the shader caps at 60 m, the property says 200). The table scales `/vj/fog_height` onto 0..60 m and the bridge clamps to the property, so nothing breaks either way.

## Open

- Magic confirms (user only): `show.magic` loads without warnings and the Program scene shows both sources; the Server list offers `COLOSSUS_OUT - Godot` (the app part is a guess from `Godot_mono.app`, `--syphon-godot` changes it); both frames upright (the earlier Blender grab was flipped); `SceneMix` 0 shows Blender, 1 shows Godot, in between a crossfade (`Mix` Amount 0 is input 1); the lab page lists 38 addresses from Magic, all within 0..1 (`/vj/cam` up to 10, `/vj/shock` up to 1.5); `CamAuto` 0 plus `CamSel` moves the Blender camera and holds Godot's shot.
- Not driven or loaded in Magic by this node (the user's app). The projects are checked with `magicproj.py` (parse, `check`, round trip, tests) only.
- Staleness (Godot drops an address after 2 s, Magic sends on change) was not part of the user's decision. The contract rule "scenes keep the last value" asks Godot to hold, which is G1's "values persist without packets".
- `CamCount` defaults to 11 shots (the planet). On the island scene shots 7..10 all take `CAM_6`. Set `CamCount` to 0.6 for 7.
- `synthwave_pyramids.magic` still sends to 9201 (Blender only); `show.magic` goes through the relay.
- `/vj/cam` wire max is 10 (planet has `CAM_0`..`CAM_10`); the runtime's `RANGES` says 0..6 for `vj_cam`. The bridge does not clamp it to the property.
