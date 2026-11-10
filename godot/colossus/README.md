# Godot Colossus Scene

A live VJ scene: a Colossus roams an overcast dusk plain, the Wanderer climbs it, Magic's music signals move weight, fog and light. Numbers in [docs/SPEC.md](docs/SPEC.md), build rules in [docs/GUIDELINES.md](docs/GUIDELINES.md), terms in [GLOSSARY.md](../../GLOSSARY.md).

## Run

Open `godot/colossus` in Godot 4.7 (Forward+, Metal) and press Play. Frames go to the window and to the Syphon server `COLOSSUS_OUT`.

For music signals, run `make lab`; it relays Magic's OSC to Godot on udp 9202. Without OSC the scene runs on an internal 90 BPM beat.

Keys: N next Phase, R Reset, Q Shake, C pick the next Colossus, 1 to 5 force a shot, F1 debug overlay, WASD/Shift/Space and the mouse for Takeover.

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

`run_tests.gd` checks the pure logic (Arc, Grab Path, Takeover, shots, OSC decoding, beat). `smoke.gd` plays one full Arc headless: climb to the head, Shake over OSC with the Wanderer swinging, the ragdoll Fall settling, Reset to the next Colossus. `capture.gd` renders the same Arc on Metal and saves the output frame of each Phase as PNG (`CAPTURE_SYPHON=0` skips Syphon). Both listen on udp 19202 and publish Syphon as `COLOSSUS_TEST`, so they never touch a running show.

## Status

First version, running end to end at 1080p on Metal:
- Land: Mælifellssandur from Copernicus GLO-30 in Terrain3D, with CC0 sand and rock textures, full collision, and a flat plain beyond the 8 km edge.
- Colossi: rigged stand-ins (Skeleton3D, Grab Points on bone attachments, feet planted by TwoBoneIK3D, physical-bone ragdoll for the Fall). They walk to meet the Wanderer in Climb.
- The Arc, Grab Path climbing with a sideways Shake swing, Takeover, and the auto director: telephoto wide shots, a Fall framing that follows the body, and `/vj/cam` pinning.
- Music: OSC in with per-address freshness and an internal beat while `/vj/beat` is quiet. Footfall dust sized by `/vj/bass`, and an impact dust cloud.
- Look: overcast dusk, volumetric fog, film grain and vignette in the output.
- Out: Syphon `COLOSSUS_OUT`.

Still to come:
- The Sketchfab Colossi and the Nomad Wanderer with Mixamo clips need a login to download. They replace the stand-in parts and keep the skeleton, Grab Path, IK and ragdoll setup. The Wanderer's hand IK waits for his rig.
- Ruins are stand-ins: the Shrine columns and a fallen head.
- A Colossus more than 450 m away is lost in the sunlit haze, so long Approach shots show the walk, not the giant.
