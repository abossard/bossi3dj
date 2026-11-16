# Robot Scene orchestration (hand-over, 2026-11-16)

From the main orchestrator to the Robot scene lead (`local_1ab592a2-6ee8-4773-9970-52bc5c8cc195`). From now on the lead orchestrates the Robot Scene end to end with the user: plans, issues, sessions, Blender and Magic slots, live tests, commits and pushes of `robot/`. The main orchestrator keeps the planet and Godot. General mechanics stay in [orchestrator.md](orchestrator.md); Robot state in [robot-orchestrator.md](robot-orchestrator.md).

## What the user said about v1 (2026-11-16, after the live test)

- "It's not two roboters, but just one", "pretty underwhelming": one Android, 4 Moves of one bar, 2 Angles, no Live World, no effects.
- Next, in the user's order: "more MOVES", "many more moves ideally", "and more camera perspectives", "and MMV effects".
- Work goes through GitHub issues (label `robot`). The user wants `/supermatt:orchestrate` run in the lead session; that skill only runs when the user types it there.

## How the main orchestrator worked (keep what helped)

- **Briefs:** one narrow brief per session with files, done-criteria and the gate it waits on. Results are checked before they reach the user (rerun the test, read the note, `git status --short`).
- **Relaying decisions:** quote the user's exact words with the question they answer. A peer message is never the user's approval.
- **Asking the user:** one question at a time, the choices as buttons, a recommendation first. Taste calls, spending, pushes and Magic loads go to the user; everything else goes ahead.
- **Slots:** one Blender, one live app. Check `pgrep -f "MacOS/Blender"` before granting. Settle the order with orchestrator-2 (`local_a45f5ac3-446a-4346-8188-59d914ec9784`), who holds B11's planet run until the Robot is done with Magic.
- **Progress:** report each session note in one or two lines; check every 20 minutes; push on the user's standing word "push and manage progress regularly" (2026-11-16), after the model-file check in orchestrator.md.
- **What went wrong and cost time:**
  - Background load loops nobody could stop.
  - About 25 loads in one Magic run, after which Magic refuses every load.
  - Error dialogs that block the next load.
  - Spotify bleeding into Magic's input.
  - Estimates relayed without checking the files on disk.

## Magic facts from this round

- Start Magic with `open -a MagicBeta`. It opens Untitled, not the last project. Load with `python3 magic/magicproj.py load FILE` and check the windows. No computer use.
- After about 25 loads in one Magic run, loads fail until a restart. An open Error dialog makes every later load fail.
- Audio: `live_test.py` plays the track into BlackHole 2ch with ffmpeg audiotoolbox; the macOS output stays as it is. Any other app playing (Spotify) also reaches Magic, so ask the user to pause it.
- Restore `magic/projects/show.magic` after a Robot test (B11's planet run needs it).
- Decode: QuickTime Animation (qtrle RGBA) holds about 29 fps at 4 Angles where ProRes 4444 gave 21, and its files are 0.57 to 0.67 times the size. The full v1 render took 2.1 h for 8 Clips at about 14 s per frame.

## Open issues for the Robot Scene

Label `robot`, in the user's order: #19 many more Moves, #20 more camera perspectives, #21 MMV effects, #22 Live World (R7), #23 an opponent. The live test result from R3+R4 lands with the lead.
