# Building the Colossus Scene

Read [SPEC.md](SPEC.md) for numbers, [GLOSSARY.md](../../../GLOSSARY.md) for terms and [osc/CONTROLS.md](../../../osc/CONTROLS.md) for the `/vj/*` addresses. Name nodes, scripts and signals with glossary terms (`Colossus`, `Wanderer`, `GrabPoint`, `GrabPath`, `Shake`, `Phase`, `Takeover`), never with their _Avoid_ words.

## Code

- GDScript with static types on every variable, parameter and return.
- Run `gdlint` and `gdformat --check` on changed scripts. gdtoolkit 4.5 may reject newer 4.7 syntax; note the rule and move on, don't rewrite code to please it.
- Keep calculations pure (grab link choice, shot choice, Phase transitions take values and return values) and keep node access at the edges (`io/`, scene scripts). Pure functions get parameterized tests, run in a headless test scene.
- One owner per state: the Phase lives in `arc/`, Takeover timers in `io/`. Others read signals, never set each other's fields.
- No per-frame allocations in `_process` / `_physics_process` on the Colossus, Wanderer or director.

## Colossi are swappable

- Every Colossus is one scene with the same root script and the same exported fields: height, foot bones, head bone, physical bone list, Grab Path.
- Nothing outside `colossi/` refers to a specific Colossus or bone name. Code reads bones through the exported fields.
- A new Colossus is done when its Grab Path reaches the head and its ragdoll settles on flat and sloped ground.

## Assets

- Import glTF where offered, FBX only when no glTF exists. Apply scale so the Wanderer is 1.75 m.
- Check the license on the download page at download time and write the `CREDITS.md` line in the same commit as the asset.
- Golem Rock stays out of git until its author confirms the CC-BY license.
- Mixamo files live in `assets/mixamo/` only. Retarget onto the Wanderer with `RetargetModifier3D` at runtime; never bake Mixamo data into committed `.tres` / `.res` files.
- Decimate scans (statue fragment, cliffs) in Blender before import, to the budgets in SPEC.md.

## Look

- Every change that affects the image is checked against the art book frames at 1080p, from the director's shot list.
- No HUD, no text, no UI in the Syphon output. Debug overlay (F1) draws to the editor window only.
- Colour and exposure changes go through the shared `Environment` resource, not per-object.

## Performance

- Profile with Godot's profiler (or the godot-mcp profiler tool) on every heavy change: Fall ragdoll, fog, SDFGI cascade count.
- If the frame goes past 16.6 ms, cut in this order: SDFGI cascades, fog volume resolution, internal scale (down to 0.67), ruin LODs. Don't drop Colossus detail first.

## Verifying

- `make godot-check` after every change to a control or a value mapping: one row per control, effect / no effect / error. A new control is a row in `io/feature_check.gd` and in `io/vj_map.gd`.
- `make godot-test` after every logic change, `make godot-smoke` after every scene change, `make godot-lint` before both.
- After adding addons or assets: `make godot-import`. Zero load errors, and check that `project.godot` did not change.
- Drive the scene without Magic using the `lab.py` generators (beat pulse on `/vj/beat`, pad on `/vj/shock`).
- Check the Syphon server `COLOSSUS_OUT` appears in Magic's SyphonClient list and holds 60 fps through a full Arc.
- Look: `make godot-capture OUT=<dir>` renders one frame per Phase on Metal; build a contact sheet and give it to the `shot-reviewer` subagent.
- godot-mcp (editor open, addon on) is for what tests cannot see: `godot_runtime_state` digests, the profiler, `godot_validate_meshes` when rendering looks wrong with nothing in the log. Prefer text digests to screenshots.

## Pitfalls

| Symptom | Cause | Rule |
|---|---|---|
| Syphon drops to 0.3 fps | macOS stops drawing an occluded window | `RenderingServer.force_draw(false)` while `window_can_draw()` is false, `max_fps=60` (in `main.gd`) |
| Method not found on an addon class | GDExtension API guessed | dump the class from `ClassDB` first, then write the call |
| Terrain textures blurry or wrong | imported with 2D defaults | `compress/mode=2`, `mipmaps/generate=true` in the `.import` file |
| Ragdoll launches the body | physical bone bodies not mid-segment, joints not at bone heads | body at the segment centre, joint at the bone head |
| Collision reads `inf` on Terrain3D | collision mode not set | set the mode before the first query |
| Test steals the show's OSC or Syphon | test bound 9202 or `COLOSSUS_OUT` | tests use udp 19202 and `COLOSSUS_TEST` |
| Flaky timing assert | wall-clock assert under GPU load | report timings, assert only on logic |
| fps drops with nothing changed | Blender holds 52 to 65 % of the GPU | `make status`; the show runs Godot alone, hand Blender-free measurements to the user |

## Assets with a login

- Sketchfab and Mixamo downloads need the user's login. Ask for the file, don't search for a way around it.
- Scenario (`.mcp.json`, skill `scenario`) needs the user to authorize it once via OAuth.

## Git

- Commit assets and their `CREDITS.md` lines together.
- `.godot/` and `assets/mixamo/` are git-ignored.
