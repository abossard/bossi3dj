# Robot Scene

A pre-rendered Android fights to the music in Magic, inside a Live World that Blender draws live. Terms: [GLOSSARY.md](../GLOSSARY.md), "Robot Scene". State and plan: [docs/handover/robot-orchestrator.md](../docs/handover/robot-orchestrator.md). Concept page: https://claude.ai/artifact/7D5wLjhFTi7hNr6xwecMP8 (source `concept/robot-scene.html`).

## Direction (the user, 2026-11-15: directions A and B)

- Video-led: the Android, its Moves and its Angles are rendered ahead at full quality. Magic walks a Clip Graph on the bar (H4), cuts Angles on the beat (H6) and later scrubs time (H5).
- Live World around it: Blender draws the surroundings live and lets them react to the music, replaying the Camera Track (H1). Live accents land at the Hits (H7).
- Look: Chrome Foundry (steel Android, sodium light, molten channel, sparks). Staging later: the giant machine.
- One framework, switchable modules. Relight (H2, H3) comes later; the Swarm (H8) is out.

## v1 scope

- One Android, one Key Pose (guard), 4 Moves: idle, jab-cross, front kick, take hit. Each a 4 beat Clip at 124 BPM.
- 2 Angles with locked Shot Cameras (static Camera Track, so the Live World lines up without per-frame sync).
- Passes: beauty with alpha (Matte), Shadow Pass, Depth Pass. Clip Data with Hits.
- Magic scene generated from the Manifest: Clip Graph on bars, Angle cuts on beats, Speed from BPM, Live World over Syphon behind the Android, Shadow Pass on the Live World's ground.
- Live World: the foundry set in Blender, lamps and molten glow on the beat, sparks at the Hits.
- Done means a 60 s recording of Magic's output with music, judged in motion.
- Later: slow motion (H5, needs 120 fps renders), more Angles, camera moves, Relight, the giant machine, more Key Poses.

## Contracts

| Contract | State | Where |
|---|---|---|
| Manifest schema | fixed now | [CONTRACTS.md](CONTRACTS.md) |
| Clip Data format | fixed now | [CONTRACTS.md](CONTRACTS.md) |
| Folder layout | fixed now | below |
| Syphon names | fixed now | `ROBOT_LIVE` (live Blender), tests `ROBOT_TEST` |
| OSC rows | proposed, through the `osc/` owner | [CONTRACTS.md](CONTRACTS.md) |
| Light Pass set | later | with Relight |

## Folder layout

| Folder | Holds |
|---|---|
| `build/` | Blender build and render scripts for the Android, Moves, Shot Cameras, Passes |
| `live/` | the live Blender scene: Live World, Live Layers, Syphon `ROBOT_LIVE` |
| `magic/` | the generator from Manifest to `.magic`, the Clip Graph model, tests |
| `concept/` | the concept page |
| `package/` | Render Packages; media are git-ignored, only the Manifest and Clip Data are committed |
