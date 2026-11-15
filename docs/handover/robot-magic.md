# Robot Scene: Clip Graph model and Magic generator (R3, R4)

Branch `integration/presentable`. Code in `robot/magic/`, fixture in `robot/package/fixture/`. Nothing was loaded into Magic; no port bound.

## Commands

```
python3 -m unittest discover robot/magic/tests                       # 32 tests, no ffmpeg or Magic needed
python3 robot/magic/fixture.py [--media]                             # manifest, Clip Data, Camera Tracks; --media: ffmpeg placeholder Clips (57 MB, git-ignored)
python3 robot/magic/manifest.py robot/package/fixture/manifest.json  # validate
python3 robot/magic/robot_magic.py robot/package/fixture/manifest.json   # -> robot/package/fixture/robot.magic (git-ignored)
python3 magic/magicproj.py check robot/package/fixture/robot.magic   # 0 errors, 0 warnings
```

## What works

- `manifest.py`: validates every rule of `robot/CONTRACTS.md` (frames from beats, bpm and fps; Key Poses; one timing per Move across Angles; every Move has every Angle; cut points; wire limits 8 Angles and 256 Clips; files, Clip Data frame count and Hits).
- `clip_graph.py`: pure model, `step(state, beat, energy)` per beat. Next Move on a bar boundary among Moves with `key_in == key_out`, in the Intensity Tier of the energy (any tier if empty, never the same Move unless alone). Angle cut at Cut Points with `cut_rate`. Picks are `frac(sin(n*12.9898 + seed*78.233 + salt*37.719)*43758.5453)`, so a seed repeats a run.
- `robot_magic.py`: Robot scene (SyphonClient `ROBOT_LIVE - Blender` into Blend Multiply with the Shadow InputSelector, Mask on the beauty InputSelector, Transparency Amount 0 (1 is fully transparent and draws nothing) with the Android in front, then an InputSelector gate on the Global `LiveOn`) and `OSC Out` scene (3 OSCSenders to 127.0.0.1:9201). 8 VideoFiles per selector, ordered move-major, Angle minor. Speed linked to `SpeedRatio` = BPM / manifest bpm. `Goto Start` linked to `StartPulse` (2 frames at each Move change). OSC rows live in one table, `OSC_ROWS`.
- Beat clock, kick, energy: the Globals of `magic/synthwave_magic.py`, picked by name (`CLOCK_GLOBALS`), so the audio analysis is the one the other show uses.
- The graph fits Magic Globals. No arrays needed: the transition table, tier, cut points and Clip numbers are nested `if` chains written from the Manifest; state is held by `y` latches; picks use a hash of the beat count.
- `tests/test_robot_magic.py` runs the generated Globals in a small ExprTk-subset interpreter with Magic's one-frame-lag rule and compares Move, Angle, Clip index and Clip frame with the model over 4 seeds and cut rates, three tiers. The interpreter is not Magic.

## Limits and choices

- Latency: the pipeline is BeatEv (b+1), Wrap and NxtMove (b+3), Move and Angle (b+4), Sel (b+5), b = frame the beat count changes. About 5 frames (80 ms at 60 fps) behind the beat clock. A test holds it under 6.
- Expression size grows with tiers x Moves x candidates. Fixture: 12 table entries, about 700 characters. A real Library of 10 Moves is about 30 entries; Magic's expression length limit is not known.
- No `var` locals in the expressions: `magicproj.check` flags their names as unknown Globals. The hash is therefore split into two Globals (`PickH`, `AngleH`, `AngleH2`).
- Beats count the music's beat clock, which free-runs at 128 BPM with no kicks. Moves are bar aligned to the count, not to the song's downbeat. A manual downbeat nudge is not built.
- Depth Pass is not loaded in Magic (decode cost, no v1 use). `/vj/clip` is the Manifest index (`OutClip` table), not the selector index.
- Mask gets the beauty selector on both pins (alpha from its own alpha: identity). It is there so the Matte can become its own Pass later.
- Placeholder Clips are 480x270 (the committed fixture Manifest says so; production is 1920x1080). Beauty ProRes 4444 with an alpha disc, shadow and depth ProRes 422.

## Magic checks

Answered (the user, 2026-11-15, and live runs):
- VideoFile plays ProRes 4444 and keeps the alpha.
- A VideoFile the InputSelector is not drawing keeps playing, so an Angle cut mid-Clip shows the right frame.
- Duplicate `Child` id in Mask (`20,20`) is accepted and draws.
- Blend `Mode 3` multiplies the Shadow Pass onto the live layer (pixels checked with `ROBOT_TEST`).
- Relative `File` paths next to the `.magic` resolve (every Clip played in the live runs).
- `Goto Start` on a 2-frame pulse restarts the VideoFile exactly once and the frames rise monotonically after it (2026-11-16, `robot/magic/restart_check.py`, 30 Hz Syphon samples of a counter clip, grey level 4 per frame: pulse at 2.01 s gives frame 0 at 2.01 s, at 3.01 s frame 1 at 3.04 s, at 8.01 s frame 0 at 8.04 s, no second drop).
- `Looping 0` does not hold the last frame: after frame 59 (level 236) the output is black (0.0 on every sample for 3 s). Fix: the generator sets `Looping 1`, which replays from frame 0 and never goes black (levels cycle 4 to 236; restart check passes). A Clip that outlasts its Move, or a stopped clock, now shows its Key Pose cycle instead of black.

Open:
1. `ROBOT_LIVE - Blender` is the Syphon server name once the live scene exists (R7); tests use `ROBOT_TEST`.
2. OSCSender sends floats; the live scene should accept them as integers.

## Contract

`/vj/clip`, `/vj/clip_frame`, `/vj/angle` and `/vj/live_layer` are rows in `osc/contract.json`; `ContractRowTests` fails when `robot_magic.py` drifts from them.

## Missing live source (2026-11-15, proven in Magic Beta 3)

- A module wired to a missing Syphon server draws black, even bypassed or at Power 0. An InputSelector evaluates only the input it draws, so the output gate picks the Android alone at `LiveOn` 0 and the composite at 1.
- `LiveOn` follows a heartbeat: `/vj/live_layer`, int toggling 0/1 at 2 Hz from Blender's live layer to Magic's OSC input (udp 127.0.0.1:9202). Each change of the value sets `LiveTimer` to 1.5 s; `LiveOn` is 1 while it runs. No heartbeat, `LiveOn` 0, never black. The contract row is in `osc/contract.json`.
- Sender: `robot/live/heartbeat.py` (`Heartbeat.beat()` for a Blender timer, CLI `--port --rate --seconds`), tests in `robot/live/tests/`. Generator: `live_globals()` in `robot_magic.py`, `--osc-in PORT` for test copies.
- Magic: a Global that links another Global with no modifier reads the same frame, only an Expression reads the last one, so `LivePrev` is `Expression(LiveRaw)`. A plain link made the change detector never fire.
- Proof (test copy: OSC input 19404, SyphonClient `ROBOT_TEST - Python` with `robot/magic/syphon_test_pattern.py`, sampler `robot/magic/syphon_sample.py`): heartbeat off, lit 0.283, mean RGB about (20, 34, 29) or (32, 36, 37), the Android. Heartbeat on, lit 1.0, mean about (110 to 123, 79 to 81, 119 to 127), live layer with the Android in front. Heartbeat killed at t, composite until t + 0.95 s, then lit 0.282 with the Android, no frame below that over 9 s.
- Transparency Amount was 1 (fully transparent) and blanked the composite; now 0.
