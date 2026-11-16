# Robot Scene: Clip Graph model and Magic generator (R3, R4)

Branch `integration/presentable`. Code in `robot/magic/`, fixture in `robot/package/fixture/`. Nothing was loaded into Magic; no port bound.

## Commands

```
python3 -m unittest discover robot/magic/tests                       # 48 tests, no ffmpeg or Magic needed
python3 robot/magic/fixture.py [--media]                             # manifest, Clip Data, Camera Tracks; --media: ffmpeg placeholder Clips (57 MB, git-ignored)
python3 robot/magic/manifest.py robot/package/fixture/manifest.json  # validate
python3 robot/magic/robot_magic.py robot/package/fixture/manifest.json   # -> robot/package/fixture/robot.magic (git-ignored)
python3 magic/magicproj.py check robot/package/fixture/robot.magic   # 0 errors, 0 warnings
```

## What works

- `manifest.py`: validates every rule of `robot/CONTRACTS.md` (frames from beats, bpm and fps; Key Poses; one timing per Move across Angles; every Move has every Angle; cut points; wire limits 8 Angles and 256 Clips; files, Clip Data frame count and Hits).
- `clip_graph.py`: pure model, `step(state, beat, section)` per beat. Next Move on a bar boundary among Moves with `key_in == key_out`, in the Intensity Tier (Music X-Ray State: 2 buildup is build, 3 drop is drop, anything else calm; the tier follows the section on a bar boundary only) (no pick when that tier has none: the Idle Clip, below; never the same Move unless alone). Angle cut at Cut Points with `cut_rate`. Picks are `frac(sin(n*12.9898 + seed*78.233 + salt*37.719)*43758.5453)`, so a seed repeats a run.
- `robot_magic.py`: Robot scene (SyphonClient `ROBOT_LIVE - Blender` into Blend Multiply with the Shadow InputSelector, Mask on the beauty InputSelector, Transparency Amount 0 (1 is fully transparent and draws nothing) with the Android in front, then an InputSelector gate on the Global `LiveOn`) and `OSC Out` scene (3 OSCSenders to 127.0.0.1:9201). 8 VideoFiles per selector, ordered move-major, Angle minor. Speed linked to `SpeedRatio` = BPM / manifest bpm. `Goto Start` linked to `StartPulse` (2 frames at each Move change). OSC rows live in one table, `OSC_ROWS`.
- Beat clock and section: `xray.py`, the Music X-Ray Globals cut down to what the graph reads (copied from mmv-skills, no import across repos). The graph reads four names: `Section` (the one source of the tier, a link to `State`; re-point it to swap the source), `Beats` (running count, a bar line is a multiple of 4, built from X-Ray's `BeatPulse` and `BeatInBar`), `BeatFrac` (0..1 in the beat) and `Bpm`. One audio bank per show: the synthwave Globals are not in the Robot project any more. Names are case-insensitive in ExprTk, so the graph reads `Bpm` (not `BPM`) and `BeatFrac` (X-Ray owns `Phase`); a test fails on a clash.
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
- A VideoFile the InputSelector is not drawing keeps playing (the user's answer; the 2026-11-16 measurement under Idle Clips says it does not advance).
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

## Idle Clips (2026-11-16)

- Manifest: `idle` is required; an Idle Clip has `key_in == key_out`; every Key Pose has exactly one Idle Clip per Angle (`manifest.py`, rejected cases in `RejectTests`).
- Clip Graph: the pick draws from the non-idle Moves that start in the Key Pose and sit in the section's tier, not the current Move unless it is alone. No candidate: the Idle Clip of that Key Pose (`pool`). An Idle Clip is left on a bar boundary once it has played at least a bar, only when a pick exists; otherwise it stays. The tier no longer falls back to another tier, so calm music with no calm Move idles. Idle frames wrap (`frame`).
- Magic: `IsIdle`, `Wrap`, `NxtMove`, `NxtOff` and `OutFrame` carry the idle rules; the simulator test compares them with the model (calm, build and drop runs, so idles are entered and left).
- Fixture: the old `idle` Move is the guard Idle Clip (`idle: true`). Its media is a still card with a disc that breathes once per Clip, first and last frame equal.
- Looping: every VideoFile stays on `Looping 1`. An Idle Clip needs it. A Move Clip keeps it as the fallback: `Looping 0` goes black after the last frame (measured), and a pulse that arrives a few frames late would show black. The cost is a replay of the Move from frame 0 in that gap, in its `key_in` pose.
- Live proof (`python3 robot/magic/idle_check.py --cut-rate 0`, OSC clock on 19406, counter Clips, 30 Hz Syphon samples, no black sample): idle until beat 16.12, jab_cross from beat 16.19 (0.09 s after the bar line, first level frame 0), idle again from beat 20.13 (0.06 s after the bar line, Move ended at level 228), idle until beat 32.11, jab_cross from 32.17 (0.08 s). In the idle from beat 20.5 to 31.5: 3 loop seams, largest step between samples 8.4 levels, longest flat run 0.07 s, so no black or stuck frame at the loop point.
- Found: with Angle cuts on and one VideoFile selected per pass, the other Angle's Clip was at frame 0 at the cut (idle at beat 22: level 132 to 23; Move at beat 18: frame 29 to 0). A VideoFile the InputSelector is not drawing does not advance in this project. Fixed by all Angles playing, below.
- The card levels come back through a `v^2 / 255` curve here (Mask path); `idle_check.py` decodes them.

## All Angles play (2026-11-16)

- User decision "keep all angles playing". Per pass, every Angle has its own InputSelector over the Moves (`Input #` follows `Move`), a Transparency whose Amount follows `HideAngle<i>` (0 while Angle i is on air, else 1), and a Null that draws them all. A drawn VideoFile advances, so the Angles stay in step and a cut lands on the same frame. The one StartPulse restarts every VideoFile, so all Angles of a Move start together.
- Tests: the generated project has the layers, the pulse and `Move` links for 1, 2 and 3 Angles; the simulator checks `HideAngle<i>` against the model's Angle for 1, 2 and 3 Angles over a walk with cuts; the pulse stays two frames at each Move change for 2 and 3 Angles.
- Live proof (`python3 robot/magic/idle_check.py --cut-rate 1`, same counter Clips): 14 cuts inside a Clip, 12 of them inside an Idle Clip. Steps across a cut: 3.2 to 5.1 levels (0.8 to 1.3 frames) at 11 of them, up to 9.4 levels (2.3 frames, at an idle loop seam) at the worst; the largest step between samples elsewhere is 16 levels, so no cut stands out, where the old design stepped 109. No black sample, 3 loop seams in the idle from beat 20.5 to 31.5, Move starts at frame 0, switches 0.06 to 0.08 s after the bar line.
- Shadow Pass: while `LiveOn` is 0 the gate does not draw the Shadow layers, so they do not advance; they are in step again from the next Move start after the live layer appears.
- Decode cost (2026-11-16, `python3 robot/magic/decode_cost.py`; 1920x1080 30 fps, beauty ProRes 4444 with alpha, shadow ProRes 422, so 2 streams per Angle; 20 s per run, alternating 1, 2, 2, 1): **all numbers taken under load 28 to 49 (`load_1m`, `fps_trustworthy` false), not trustworthy; only the ratio counts.**
  - Magic Graphics FPS: 1 Angle 28.8 (28.5, 29.1), 2 Angles 16.6 (16.8, 16.5). Ratio 2/1: 0.58.
  - Magic process CPU (top): 1 Angle 314 %, 2 Angles 295 %. It is flat near 3 cores both times, so decode is CPU bound (software ProRes), not GPU bound.
  - GPU (whole-GPU Device Utilization): 5 % and 3 %, other apps included.
  - Per frame time: 1 Angle 35 ms, 2 Angles 60 ms, so about 25 ms per added Angle and 9 ms fixed. A straight line gives 3 Angles about 12 fps and 4 Angles about 9 fps at 30 fps Clips. That is a guess from two points under load; the 1 Angle run may sit at a 30 fps cap, which would make the per-Angle cost larger, not smaller. Two Angles already miss 30 fps here, so 3 to 4 Angles do not fit at 4444 1080p as it stands on this machine under this load. Re-run on a quiet machine before deciding; levers if it still misses: ProRes 422 or HQ for the beauty, a Hap or lower resolution shadow, or stopping the Angles that are off air (they are drawn only so the cuts land on the same frame).
  - Target machine (user, 2026-11-16): a dedicated MacBook like this one (Apple M1 Max, 10 cores, 64 GB) with Magic and the Robot's live Blender layer alone on it. The runs above held Magic near 3 of 10 cores under load, so they are pessimistic for the show; the Angle-count and codec decision waits for a quiet re-run.
  - Not measured: GPU load of Magic alone, a quiet machine, depth Pass, the Syphon Live World.

## Section drives the tier (2026-11-16)

- `Tier` latches the section on a bar line in the frame `BeatEv` is (`Beats > BeatsPrev and Beats % 4 == 0`), so the pick that reads it one frame later sees it: latency unchanged, Wrap and NxtMove at b+3. Reading the tier a frame later than the beat broke the idle exit (the pick changed after the check).
- Model and Globals agree (`test_globals_match_the_model`, sections 0, 2, 3, 4 mixed over 4 seeds and cut rates); `test_tier_changes_only_on_a_bar_boundary` (model) and `test_tier_changes_only_on_a_bar_line` (Globals).
- Idle live proof again with the section as the OSC-driven clock (`idle_check.py`): idle to Move 0.059 s after bar 16, Move to idle 0.091 s after bar 20, idle to Move 0.050 s after bar 32, no black sample, 2 idle loop seams, 14 cuts all within the largest step elsewhere.
- X-Ray itself live (`python3 robot/magic/xray_check.py`, synthetic 124 BPM track into Source 0, probe OSC on 19408): kick, sub-bass and pad bars come back as State drop (3), breakdown (4), buildup (2), drop (3) in order; Tier follows each on a bar line (beats 64, 76, 92, 112) and never off one; Bpm 122.2 after 46 s (starts at 120 and converges, +-3 of 124). Notes: the kick must reach 0.6 on KickRaw (a quiet synthetic kick never pulses, Bpm stayed 120); music that starts after silence reads as a drop at once (State 3 in the first second), a real set that starts on a song does the same; the buildup read came one bar after the pad and snare roll began.
- Not covered: a real song's section accuracy (X-Ray's own notes hold that), and the Globals count (87 for the fixture).
