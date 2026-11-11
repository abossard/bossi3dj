# Godot Colossus Scene

A live VJ scene: a Colossus roams an overcast dusk plain, the Wanderer climbs it, Magic's music signals move weight, fog and light. Numbers in [docs/SPEC.md](docs/SPEC.md), build rules in [docs/GUIDELINES.md](docs/GUIDELINES.md), terms in [GLOSSARY.md](../../GLOSSARY.md).

## Run

Open `godot/colossus` in Godot 4.7 (Forward+, Metal) and press Play. Frames go to the window and to the Syphon server `COLOSSUS_OUT`.

Music signals come from Magic (`magic/projects/show.magic`) straight to udp 9201, the scene port Blender's bridge uses too (never run both). `make lab` is an optional debug relay to the same port. Without OSC the scene runs on an internal 90 BPM beat.

Control page: http://127.0.0.1:9211 while the scene runs (see [Control page](#control-page)).

Keys: N next Phase, R Reset, Q Shake, C pick the next Colossus, 1 to 5 force a shot, F1 debug overlay, WASD/Shift/Space and the mouse for Takeover.

## Control page

The running scene serves its own control page on `127.0.0.1:9211`, the counterpart of Blender's page on 9210 (`io/control_server.gd`, `io/control_page.html`). It is a node beside the output viewport, so nothing of it reaches the Syphon frame, and with no browser open it costs one accept check per frame.

- One slider per level address (`/vj/level`, `bass`, `fog`, `fog_height`, `haze`, `intensity`), in wire values 0..1 like OSC, with its default and what it drives. Moving a slider writes the value and holds it, so a live OSC sender cannot fight the page; the lock gives the address back to OSC. Only the page overrides a hold, OSC and the simulator yield to it.
- A pin per director shot (sets `/vj/cam` and `/vj/cam_auto` 0) and Auto (`/vj/cam_auto` 1), a jump to each Phase (going back is a Reset), Shake, Shake + drop and Beat triggers, a beat simulator that stands in for Magic, Defaults and Release holds.
- Header: Phase, director shot, fps and frame time, OSC packets, Syphon server and frames, where the Wanderer is. `GET /api/state` has the same as JSON, with the current value per address and the numbers the scene acts on. `make status` shows it as `godot_scene`.
- Self-check: "Check all" drives every control through the OSC path, reads the number the scene acts on (`Environment` fog and exposure, sun energy, Colossus weight, director shot, beat count, Shake roll, Phase) and shows effect, no effect or error per control. Values and holds are left as found and the Phase ends in Approach. `make godot-check` runs the same code headless.

All values live in `io/vj_signals.gd` (one owner). OSC, the page, the simulator and the check write through `apply()`, and a value stays until the next write, as in Blender. Only `/vj/beat` keeps a fallback: an internal 90 BPM beat while it is quiet. The map from wire value to scene value (range, clamp, scaling, rest value) is one data table, `io/vj_map.gd`: every continuous control is 0..1 on the wire, and the wire default lands on the tuned look.

```bash
make godot-check
```

```bash
make godot-page-test
```

`godot-check` prints one row per control and writes the JSON to `CHECK_OUT` (default `/tmp/colossus-feature-check.json`). `godot-page-test` starts the scene headless on 19211 and sends HTTP requests to the page, including "Check all". Both use udp 19202 and never touch 9202, 9211 or `COLOSSUS_OUT`. The page file is read from `res://` at request time, so an exported build needs `*.html` in its export filter.

## Test

```bash
/Applications/Godot_mono.app/Contents/MacOS/Godot --headless --path godot/colossus --script res://tests/run_tests.gd
```

```bash
/Applications/Godot_mono.app/Contents/MacOS/Godot --headless --path godot/colossus --script res://tests/smoke.gd
```

```bash
/Applications/Godot_mono.app/Contents/MacOS/Godot --path godot/colossus --script res://tests/capture.gd -- /tmp/colossus-capture
```

`run_tests.gd` checks the pure logic (Arc, Grab Path, Takeover, shots, OSC decoding, beat, the value table, held and persistent values, the beat simulator, HTTP parsing, check verdicts). `smoke.gd` plays one full Arc headless: climb to the head, Shake over OSC with the Wanderer swinging, the ragdoll Fall settling, Reset to the next Colossus. `capture.gd` renders the same Arc on Metal and saves the output frame of each Phase as PNG (`CAPTURE_SYPHON=0` skips Syphon). Both listen on udp 19202 and publish Syphon as `COLOSSUS_TEST`, so they never touch a running show.

## Status

First version, running end to end at 1080p on Metal:
- Land: Mælifellssandur from Copernicus GLO-30 in Terrain3D, with CC0 sand and rock textures, full collision, and a flat plain beyond the 8 km edge.
- Colossi: Grock (Colossus 1) on its own rig once `make godot-models` has prepared it (`assets/MODELS.md`): idle clip with a procedural stride, Grab Points on its bones, feet planted by TwoBoneIK3D, a 17-body ragdoll for the Fall. Titan and Golem, and Grock without its model, are rigged stand-ins (Skeleton3D, Grab Points on bone attachments, foot IK, ragdoll). They walk to meet the Wanderer in Climb and stand while he climbs.
- Wanderer: the Nomad on Mixamo clips (retargeted at runtime, feet and hands by IK, head toward the Colossus), or the stand-in without the model.
- The Arc, Grab Path climbing with a sideways Shake swing, Takeover, and the auto director: telephoto wide shots, a Fall framing that follows the body, and `/vj/cam` pinning.
- Music: OSC in; a value stays until the next packet, and an internal beat runs while `/vj/beat` is quiet. Footfall dust sized by `/vj/bass`, and an impact dust cloud.
- Look: overcast dusk, volumetric fog, film grain and vignette in the output.
- Out: Syphon `COLOSSUS_OUT`.

Still to come:
- Titan and Golem on their own rigs (`docs/reports/godot-model-cost.md` says what their archives need); the Mixamo clips for hanging, climbing, falling and standing up (`assets/MODELS.md`).
- Ruins are stand-ins: the Shrine columns and a fallen head.
- A Colossus more than 450 m away is lost in the sunlit haze, so long Approach shots show the walk, not the giant.
