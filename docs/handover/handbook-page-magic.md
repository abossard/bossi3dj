# Handbook, control page, Magic project (B11)

State 2026-11-12, Blender-free part done and committed on `integration/presentable`. The live part waits for the Blender slot.

## What exists

- `docs/handbook.md`: install, start in order, steering (Magic and page, the hold rule), cameras and Flight, what Magic sends and why, end, a table of what goes wrong. The camera list and the Magic table are generated: `python3 magic/magic_manual.py sync` (also run by `make magic-build`), a test fails when they drift. Linked from the README top and "Read next".
- Magic (`magic/synthwave_magic.py`, `show_magic.py`, rebuilt projects):
  - every address has a control Global named like it (`/vj/fog_height` is `FogHeight`), holding the contract default; a test checks all 38.
  - `Live` (sound on the input: `EnergyNow` above 0.004, fades over 3 s) times `React` is `Follow`. Twelve addresses follow the music, each Out is `control + Follow * (music - control)`; with no sound they send their control. The auto camera cutter needs `CamAuto` 1 and `Follow` above 0.5, else `Cam` picks the shot.
  - renamed: `HueBase` to `Hue`, `CamSel` to `Cam`, `CamEnergy` to `Energy`; the analysis `Beat` is `BeatNow`, `Energy` is `EnergyNow`. New controls `Level`, `Bass`, `Beat`, `Intensity`. `GridSpeed` default 0.15 and `CamSpeed` 0.25 (the contract defaults; the old floors are gone, so the music-driven speeds changed a little).
  - Magic's own Syphon output is on in `show.magic`: `MAGIC_OUT`, 1920x1080. `show_magic.py --synthetic` builds a test project with the synthetic EDM signal.
- Control page (`blender/scenes/synthwave_control.html`, `synthwave_web.py`, new `page_model.py` without bpy):
  - controls come with address, group and sentence from the contract, ordered like the README manual; `coverage` in `/api/state` lists addresses without a control (none: 37 of 37) and properties the contract lacks.
  - one column, 44 px sliders and buttons, no horizontal scroll at 375 px (checked in the built-in browser against `tools/blender_page_mock.py`, not against Blender yet). Sticky bar: scene, camera with number and name, fps, Syphon live or stalled (counter advancing), value sources, night-edge guard, check progress. Camera buttons and Hold all, Release all, Reset (two taps) first. Triggers are buttons. Tools, the OSC monitor and the check table are folded.
  - presets are a file now (`blender/local/presets.json`, git-ignored): the browser-only version was half built (per browser, so the phone saw nothing of the laptop's). Recall sets values and does not hold them.
  - POST needs a JSON type (415 otherwise); on loopback the Host header must be loopback (403). Same rules as the Godot page.
  - the page listens on 127.0.0.1. For a phone: `python3 tools/blender_page_lan.py on` writes `blender/local/page.json` and the next start listens on every interface. Not switched on. Decision for the user: this lets any device on the network drive the scene.
- Tests: `blender/tests/test_page_model.py` (grouping, coverage, presets, settings, Host rule), `magic/tests/test_synthwave.py` (controls, Follow, output), `magic/tests/test_manual.py`. `make test` green.

## Live part (after the slot)

All commands from the repo root. Tell the orchestrator before the `load` steps: `load` replaces the project open in Magic; note the open project first (`python3 magic/magicproj.py load` prints window titles) and load it back at the end.

1. `make blender-open` (start state ready). `python3 tools/blender_page_test.py --check`: the page's JSON, the refusals, set, hold, camera, presets, Check all, defaults restored.
2. Built-in browser at the mobile preset on http://127.0.0.1:9210: no horizontal scroll, Check all started from the page, a hold, camera buttons, Hold all and Release all, a preset saved and recalled; delete the test preset.
3. `python3 magic/magicproj.py load magic/projects/show.magic` (or `open -a /Applications/MagicBeta.app magic/projects/show.magic`). `python3 tools/magic_show_proof.py osc`: all 38 addresses reached the bridge (`/vj/cam_auto` is recorded but ignored by Blender).
4. `python3 tools/magic_show_proof.py picture --app <app name>`: Magic's `MAGIC_OUT` frame against `CAM_OUT - Blender`, upright and reversed correlation. The app name of MagicBeta's Syphon server is not known; `magicproj.py grab` prints the servers it sees when it finds none.
5. `python3 tools/magic_show_proof.py global Fog 0.9`: the scene's `vj_fog` follows a Global changed in the project file and reloaded; the project is loaded back after.
6. Silence check: with no sound on BlackHole, every value should sit at its default (`blender/review/health.py` `off_default` or the page). With sound (or `show_magic.py --synthetic --out <scratch file>` loaded) the twelve music addresses should move: this proves `Live` and `Follow`; the 0.004 threshold is a guess until it runs.
7. `make blender-kill`; leave Magic as found.

## Open

- `Live` threshold (0.004 on `EnergyNow`) not tried with real input.
- The Syphon server name Magic reports (handbook says `MAGIC_OUT`), and whether its frame is upright: both unverified.
- `.claude/skills/magic-projects/evals/grade.py` lists the old Global names (`HueBase`, `CamSel`); not mine, not changed.
- Art-Net on the page: the bridge has it (another session); the page shows its source as the badge text and nothing else.
