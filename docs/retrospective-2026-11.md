# Retrospective: agent work on the Blender and Godot scenes, 2026-11-03 to 2026-11-09

Source: 16 Claude Code session transcripts of the swift-vj project and 133 subagent transcripts, condensed and read on 2026-11-10. Numbers are counted from the transcripts; "(inferred)" marks a reading, not a count.

## Cost by session

Output tokens in millions, cache-read tokens in millions.

| Session | Assistant turns | Out, main | Out, subagents | Cache read | Compactions | Messages from other sessions | Images read |
|---|---|---|---|---|---|---|---|
| Procedural planet | 5737 | 8.81 | 0.07 | 3208 | 4 | 92 | 456 |
| Retro sunset scene (first half) | 1954 | 2.49 | 2.47 | 527 | 4 | 39 | 105 |
| Retro sunset scene (second half, review rounds) | 896 | 0.85 | 15.49 | 261 | 2 | 28 | 23 |
| Retro sunset Syphon visual (Magic side) | 1321 | 1.23 | 0 | 378 | 3 | 22 | 54 |
| Magic skill and tooling | 675 | 0.74 | 0.69 | 264 | 1 | 1 | 3 |
| Flight, four sessions | 2033 | 2.35 | 0 | 685 | 0 | 26 | 21 |
| Performance tuning | 767 | 0.61 | 0 | 210 | 1 | 33 | 28 |
| Godot Colossus | 684 | 1.11 | 2.58 | 210 | 1 | 3 | 11 |
| EDM analysis in Magic | 319 | 0.62 | 0.09 | 93 | 0 | 1 | 6 |

All 16 sessions: 19.4 M output tokens in main threads, 22.3 M in subagents, 5.9 G cache-read tokens in main threads, 17 compactions, 245 messages between sessions.

## Where the cost went

- **One session as builder, reviewer, slot broker and writer.** The planet session ran 50 h with a context kept about half full: 3.2 G cache-read tokens over 5,737 turns is about 560 k tokens re-read per turn (inferred). It handled 92 incoming and 87 outgoing coordination messages and read 449 images itself.
- **Image review without a budget.** Five reviewer subagents re-read the same PNGs up to 34 times; the worst made 1,805 reads of 83 files and produced 4.9 M output tokens in 95 minutes. Those five account for 12.2 M of the 18 M subagent tokens of the review rounds. In total 7,701 image reads.
- **A review bar that moved.** Pass counts per round: 97, 78, 136, 84 of 220, then 119, 184 of 253. Rubric, method and requirements changed between and during rounds, so the numbers do not compare. 17 full grab runs of 220 to 253 frames, 8 to 25 minutes each, each needing Blender alone on an idle machine.
- **One Blender, many sessions, no arbiter.** Slots were negotiated by message: "our messages crossed again", a grant that arrived after the work was done, a session that held Blender idle for 36 minutes until it was killed, two Blender processes nobody had started knowingly, 65 kill commands.
- **Permission stalls.** The auto-mode classifier denied `execute_blender_code` in two sessions; they waited 43 minutes and 3 h 51 for "Yes, allow Blender".
- **Scratchpad as source of truth.** A reboot wiped `/private/tmp`: the island builder (patched 56 times by string replace), the grab tools and 237 grabs. Restored scripts were older versions; 220 grabs then all showed one camera at sunset.
- **Done without looking.** An interim Syphon sender was reported as "1920×1080 with bloom, about 19.5 fps" and published black; an 8-minute recording was wasted. A flip was validated on a Metal read-back and was upside down in Magic. fps fell from 60 to 16 during feature work before anyone measured.
- **Rework.** Fog was rebuilt five times (volume, per pixel, 3D bank, shader, volume). Water LOD went in, out, in, out. A first tuning pass on the island was discarded with the island.
- **Foreign load.** A 47 GB Python job, Godot on the same GPU, load averages of 100 to 250. Blender start took 30 minutes once; cut timing was skipped for two rounds.
- **Worktree names.** `qlc-os2l-verification` held the Flight branch, `nostalgic-mayer` the planet, `gallant-nobel` the EDM analysis. 15 worktrees in two roots, planet fixes merged into Flight branches 7 times.
- **Godot specifics.** godot-mcp was vetted, installed and never called in 43 h. godOSC was installed and replaced by a 76-line decoder 46 minutes later. Chosen Sketchfab and Mixamo models were never downloaded (login). The first landscape pick was "all rugged mountains". An 18-agent code review cost twice the main thread; one finder (271 k tokens) found nothing unique. A 7-agent chain took 63 minutes to learn that Blender held 52 to 65 % of the GPU.

## What worked

- **Scripted build as source of truth.** Headless planet rebuild in 5 to 11 s, 46 rebuilds, 5 Python tracebacks.
- **Numbers before images.** Ground check in pixels, cut timing in ms, frame diff against a noise floor, a driver scan. The perf session found the planet's fps regression with one profile after the planet session had spent 11 minutes hiding objects by hand.
- **Measured A/B.** Clocks frozen, inputs held, cells interleaved, three rounds. Day mean 18.8 to 59.2 fps from four changes; eight tempting levers measured as null and dropped.
- **Pure model first.** Flight, LOD and blend logic passed checks while Blender was blocked. Godot had 52 green tests three minutes after the first code.
- **Text probes instead of screenshots.** The Godot ragdoll was fixed in about 10 runs with printed chest height and velocity, 0 images.
- **Grilling before building.** 18 minutes of option questions in the Godot session, no design reversal later.
- **Narrow sessions with hand-over notes.** The four Flight sessions stopped at half context and had 0 compactions; the long sessions had 4 each and re-read their own transcripts afterwards.
- **Contact sheets.** One image for 9 to 18 frames.
- **Ground-truth probes.** Counting five known OSC messages at the bridge found a padding bug in 3 minutes.
- **File-based tooling for Magic.** `magicproj.py` plus Syphon grabs parsed 45 Magic-saved files with 0 errors and no computer use; the session that drove Magic by screen clicks spent 54 calls and 54 images.

## Human corrections that became rules

- "only one instance at a time" (Blender)
- "you're allowed to kill blender"
- "the review needs images"
- "the scnee should have jsut CONTROLs" (after music rules had been committed into the scene)
- "should we maybe first implementa all features and then do the perforamnce tuning?"
- "the recording should be 1 min max"
- "Magic should not add additional filter and blooms now."
- "the skill should not be biased for that blender stuff, right?"
- "Report it, don't fail" (wall-clock assert in a Godot test)
- "I think ut's not doing anythign currently" / "one sessions is waiting of the other"

## What the harness in this repo does about it

| Finding | Answer here |
|---|---|
| Slots negotiated by message | `tools/blender_lock.py` as a PreToolUse hook: first writer owns Blender, 5 min idle expiry, others are denied with the reason |
| Second Blender, unknown PIDs | `make blender-open` and `make blender-rebuild` refuse a second instance; `make status` lists processes |
| fps numbers under load | `make status` reports load and `fps_trustworthy` |
| Stale grabs, saved live values, long drivers | `blender/review/health.py`, one dict with a `problems` list |
| Runtime not started after reopen | `make blender-open` passes `--enable-autoexec` |
| Images in the builder's context, runaway reviewers | `shot-reviewer` subagent: one read per file, 36 images per call, JSON verdict, frozen rubric |
| Scratchpad loss | review tools are in `blender/review/`, notes in `docs/handover/`, state in `STATE.md` |
| Absolute paths in `.blend` files | `tools/blend_paths.py`, `make blender-paths` |
| Music logic drifting into scenes, units drifting between scenes | `osc/CONTROLS.md` as the one contract, with the open mismatches listed |
| Repeated pitfalls | tables in `blender/GUIDELINES.md` and `godot/colossus/docs/GUIDELINES.md` |
| Worktree and session sprawl | session rules in `AGENTS.md` |

Not solved here: the classifier stall on `execute_blender_code` (needs a permission rule the user adds), a per-round review runner that re-grabs only changed cameras, an island builder.

## Ideas for the minime flow

minime's four phases assume the proof is a test in the project's suite. This work had three properties it does not model: the proof is partly visual, the test rig is a shared live app, and one round takes 20 minutes of exclusive GPU.

- **Evidence kind `look:`.** Today a criterion ends in `ran:`, `data:`, `research:`, `user:`, `default:` or `open:`. Visual criteria need `look:` with a rubric id and a frame list, proven by a reviewer verdict file, so the board can show them without calling them tests.
- **Numeric gate before visual gate.** Replicate should refuse to request images while a numeric criterion of the same boundary fails. The planet rounds reviewed frames whose ground check or cut timing was already known to fail.
- **Frozen rubric per round.** Hash the rubric into the blueprint; a changed rubric is a new round, never a re-score. This is the ratchet idea applied to criteria instead of the diff.
- **Reviewer budget in the inspector.** `frau` gets a read cap per file and per run, and returns verdicts only. The fuel gauge (`--requests`, `--minutes`) would have stopped the five runaway reviewers; give subagents their own gauge.
- **Shared-resource lease as a blueprint field.** A blueprint names the exclusive resources it needs (live Blender, Magic, GPU alone). The conductor grants the lease, queues other runs and refuses measurements when the host is loaded. The `PAUSED` file is the same mechanism at coarser grain.
- **Environment preflight as phase zero.** Process list, GPU users, load, ports, app state, before blueprint. Half of the "surprises" were environment, not code.
- **Scratch promotion in extract.** Extract lists every script under a scratch path that a criterion's evidence used and fails until it is in the repo.
- **Definition of done by observation.** A criterion about output needs evidence from the consumer side (pixel statistics of the Syphon frame in Magic), not from the producer's own counters.
- **Red pen from cross-session messages.** `redpen.mjs` reads restated rules from the user. Relayed corrections ("from the user, via the coordinator") were at least six of the planet session's corrections and are invisible to it.
- **Wave size from context, not boundary rows.** Stop a worker at half context with a hand-over note. The sessions that did had 0 compactions.
- **Asset phase.** Search, licence, login requirement, download, import settings and credits as one worker with a "needs the user's login" exit, before any criterion depends on the asset.
