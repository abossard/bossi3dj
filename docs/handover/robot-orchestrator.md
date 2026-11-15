# Robot Scene orchestrator (2026-11-15)

Started by the main orchestrator (`local_17c27d7a-be6f-4ed6-8881-dd774b2e9a7c`). Owns `robot/` only. Terms: GLOSSARY.md, "Robot Scene".

## State

- Concept page version 3 (2026-11-15): round 1 mockups plus, on the main orchestrator's relay of the user's words, Hybrid ideas H1 to H8 (H1 is the user's: live world, pre-rendered Android), a comparison matrix, a "best combination" field, a framework proposal (modules per idea, example H4 + H2 + H7 + H1, contracts fixed now or later), a glossary proposal (26 terms, accept, rename or reject, scene and Android name options) and three direction proposals with first milestones. Waiting for the user's ratings: https://claude.ai/artifact/7D5wLjhFTi7hNr6xwecMP8 (source `robot/concept/robot-scene.html`, republish with the Artifact tool from that path).
- No Blender work yet. No contract, Magic or Blender file touched.

## Read the user's answers

- `ArtifactData list` on the artifact URL, collection `ratings` (doc id = mockup id: `stars` 1..5, `comment`) and collection `answers` (doc id = decision id, `answer`).
- Also: ratings `hybrid-h1` to `hybrid-h8` and `framework`; `answers` docs `best-combination`, `direction` (`choice` A, B or C plus `answer`), `name-ideas`; collection `terms` (doc id = term slug: `verdict` accept, rename or reject, `rename`, `comment`); collection `names` (option ratings).
- After the answers: accepted terms into `GLOSSARY.md` (replacing the provisional round-1 terms, e.g. Pose Key becomes Key Pose if accepted), the chosen direction into `robot/README.md` and this note. Build nothing before that.
- Mockups: look-chrome-foundry, look-neon-synthwave, look-brutalist-arena, look-ink-smoke, stage-swarm, stage-mirror-duel, stage-giant-machine, camera-cut-language, live-hud-layer.

## Concept as proposed

- Blender is a render framework: Clip Library (Clips of whole beats at 124 BPM, Pose Keys in and out, Cut Points) with Mattes (Android coverage, depth, ids), written as a Render Package (Hap files, `manifest.json`, rig and camera paths).
- Magic scene generated from the manifest with `magicproj.py`: VideoFile modules into an InputSelector picked by audio Globals on Cut Points; Speed = live BPM / 124; Mask and Blend (add) put a Live Layer from a SyphonClient on top.
- A small live Blender scene loads the same rig and camera path, set to the clip and frame Magic sends over OSC, and draws Live Layers on black.

## Decisions asked (decision ids on the page)

1. d1-direction: look and staging for round 2.
2. d2-android-source: library model and mocap, own stylised model, or both.
3. d3-camera: locked-off first, or full fight camera.
4. d4-tempo: one 124 BPM set stretched, or a second tempo set.
5. d5-budget: 1080p30 Hap, under 20 GB proposed.
6. d6-live-first: which Live Layers first.
7. d7-contract: new `/vj/*` rows (through the OSC owners) or a `/robot/*` prefix.

## Open questions and risks

- Magic does not report a VideoFile playhead: Magic must count Clip time and send it; drift moves sparks off the fist. Test with a sync Clip first.
- Hap size (estimate 25 to 35 MB/s at 1080p30) and Magic's memory with many open VideoFiles: measure before rendering the library.
- Renders need the one Blender slot; ask the main orchestrator for it.
- Read `docs/lessons-learned-blender.md` (704a3ee) before any build: judge the moving picture, settle the look first, contact and shadow, contract first.

## Sessions

- None started yet. Models for later: Opus 5.5 high for design, look, orchestration; Sonnet 5.5 medium for generators, code, tests; Haiku 5.5 for mechanical helpers.
