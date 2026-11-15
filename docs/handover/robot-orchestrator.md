# Robot Scene orchestrator

Started 2026-11-15 by the main orchestrator (`local_17c27d7a-be6f-4ed6-8881-dd774b2e9a7c`). Owns `robot/` only. Terms: GLOSSARY.md, "Robot Scene". Direction, v1 scope and contracts: [robot/README.md](../../robot/README.md), [robot/CONTRACTS.md](../../robot/CONTRACTS.md). Read [docs/lessons-learned-blender.md](../lessons-learned-blender.md) before any build.

## Concept review (2026-11-15, "I filled what I want, continue, review done")

Page: https://claude.ai/artifact/7D5wLjhFTi7hNr6xwecMP8 (source `robot/concept/robot-scene.html`). Read back with `ArtifactData list`, collections `ratings`, `answers`, `terms`, `names`.

| Group | Ratings (1 to 5) |
|---|---|
| Look | Chrome Foundry 5, Brutalist Arena 4, Neon Synthwave 3, Ink and Smoke 2 |
| Staging | Against the giant machine 5, One against the swarm 4, Mirror duel 3 |
| Camera, Live Layer | Cut on the bar 4, Tactical HUD 4 |
| Hybrids | H4 Clip Graph 5, H5 time scrub 5, H6 multi-angle 5, H1 live world 4, H2 Light Passes 4, H3 Normal relight 4, H7 depth effects 4, H8 Swarm 2 |
| Framework | 5, "love it" |
| Scene name | Robot Scene 5, Arena 4, Machine Fight 4, Steel Bout 3 |
| Android name | all five options 2 |

- Direction: picked A, wrote "Direction A and B".
- Glossary: 16 terms accepted, none renamed or rejected. 10 left open (Shadow Pass, Clip Data, Hit, Clip Library, Manifest, Render Package, Live Layer, Live World, Relight, Swarm).
- Best combination and decisions 1 to 7: not answered. No comments besides the framework's.

## Assumed (missing answers, filled from the highest ratings)

- Direction A + B together: video-led Android with a Live World (README).
- Best combination: H4 + H6 + H1 + H7 for v1, H5 next (needs 120 fps renders), Relight later, H8 out.
- Glossary: the 9 open terms the framework needs are written as proposed; Swarm left out (H8 rated 2).
- Android stays "Android" (no name option rated above 2).
- d1: Chrome Foundry look, giant machine staging after v1. d2: an own stylised hard-surface Android, built by script in Blender, Moves keyed by script (no asset that needs a login). d3: locked Shot Cameras in v1. d4: one 124 BPM set, Magic's Speed stretches. d5: 1080p30, under 20 GB. d6: sparks at Hits and beat-lit lamps first. d7: rows in `osc/contract.json` through the `osc/` owner.

## v1 plan (milestone: 60 s recording of Magic's output with music)

| Node | Work | Needs | Model, effort | State |
|---|---|---|---|---|
| R1 | Contracts: Manifest, Clip Data, Camera Track, Syphon, folder layout | nothing | orchestrator | done (`robot/CONTRACTS.md`) |
| R2 | OSC rows `/vj/clip`, `/vj/clip_frame`, `/vj/angle` into the contract, plus `/vj/live_layer` (Blender to Magic, udp 9202) | B11 via the main orchestrator | Sonnet 5.5 medium (B11) | done (716497d, 4535025) |
| R3 | Pure Clip Graph model and Manifest validator (stdlib, parametrized tests), a fixture Render Package with placeholder Clips made by ffmpeg | R1 | Sonnet 5.5 medium | done (415f0c6) |
| R4 | Magic generator: Manifest to `.magic` (VideoFile per Clip, InputSelector, Clip Graph and Angle cuts in Globals, Speed from BPM, SyphonClient `ROBOT_LIVE`, Mask and Blend, OSCSender for R2); `magicproj.py check`; codec spike (this ffmpeg has ProRes 4444, no Hap encoder) | R3 | Sonnet 5.5 medium (same session as R3) | done (415f0c6); missing live layer never black (78f3978); `LiveOn` follows the heartbeat (71988e4, b9674cb), proven with grabs |
| R5 | Android, Moves and foundry set as a build script; pure Move key tables with tests first | R1 | Opus 5.5 high | pure part done (8eba3ae); holds the Blender slot for the build and a test Clip render |
| R6 | Render the v1 Clip Library (4 Moves x 2 Angles, beauty, Shadow, Depth, Clip Data) | R5, Blender slot (headless renders count) | R5 session | waits for the slot |
| R7 | Live World scene in `robot/live/`: foundry set, beat-lit lamps, sparks at Hits, Syphon `ROBOT_LIVE`, reads R2 | R5, R2, Blender slot | R5 session | waits |
| R8 | Load in Magic, 60 s recording with music, flicker numbers, the user judges | R4, R6, R7 | orchestrator | later |

- Blender-free first: R3, R4 and the pure part of R5 run now; R5's Blender part, R6 and R7 ask the main orchestrator for the slot first.
- Magic is the user's app: R4 proves the file with `magicproj.py check` and a fixture; loading it into Magic and the recording (R8) wait for the user.

## Open checks for the user (Magic)

- Answered by the user (2026-11-15): ProRes 4444 alpha plays; an unselected VideoFile keeps playing; a Mask with the same Child id on both pins is accepted.
- Open, the user tests it later: restart and hold. Does Goto Start on a 2-frame pulse restart a VideoFile, and does Looping 0 hold the last frame?
- Open, the user's call: which Magic project to reopen. Magic has `robot.magic` open; the project before it (`PostTest.magic`) was another session's scratch test file.

## Sessions

- R3 + R4: `local_ffd73c0e-3e19-4460-863e-4508560ceccd` (Sonnet 5.5 medium), note `docs/handover/robot-magic.md`.
- R5: `local_6a0e527e-a8db-4997-a367-8bf99da5d819` (Opus 5.5 high).
