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

## Decode-cost fixes (2026-11-16, `decode_cost.py`, proposal for CONTRACTS.md and R5)

**Every number: taken under load 28 to 190 (`load_1m`, `fps_trustworthy` false), not trustworthy. Runs alternate across configs; the order of the configs is what counts. Target is the dedicated M1 Max.** Fixture Moves, 1920x1080 30 fps, a noisy disc on transparent black (a quarter of the frame lit), every Angle drawn all the time. Magic's Graphics FPS reads up to about 33 here, so 30 to 33 means "not limited by decode".

| config (beauty / shadow / matte) | 4 Angles fps (2 rounds) | Magic CPU | MB per Move and Angle |
|---|---|---|---|
| ProRes 4444 / ProRes 422 (today) | 20.5 | 159 % | 85 |
| ProRes 4444 low quality (qscale 20) / 422 | 21.9 | 149 % | 60 |
| ProRes 4444 / H.264 shadow | 21.8 | 162 % | 76 |
| ProRes 4444 / half resolution H.264 shadow | 21.7 | 166 % | 55 |
| QuickTime Animation (qtrle, 8-bit ARGB) / ProRes 422 | 28.3 | 67 % | 154 |
| raw ARGB / ProRes 422 | 28.5 | 66 % | 520 |
| raw ARGB / half resolution H.264 shadow | 29.1 | 61 % | 491 |
| H.264 intra 4:2:0 colour / H.264 shadow, own grey matte | 32.5 | 209 % | 47 |

Angle sweep, one round, same load (fps): ProRes 4444 / 422 1 Angle 33.9, 2 Angles 31.2, 3 Angles 21.0, 4 Angles 20.6. qtrle: 33.2, 29.5, 29.8 (4 Angles 28.3 above). H.264 with matte: 33.5, 32.2, 33.5 (4 Angles 32.5).

- Result: the beauty codec is the cost. ProRes 4444 is software decode at about 3 cores for 4 Angles and falls below 30 fps at 3 Angles. Every Shadow Pass change (lower quality, H.264, half resolution) moved the 4 Angle fps by 1 to 1.5 only, so step 2 is not worth a format change.
- Step 3 (play only the on-air Angle) is not needed and was not built, so cuts still land on the same frame. Nothing about cuts changed.
- The `h264` config has not been checked for the black level: limited range 4:2:0 lifted the mean of the output from 23 to 31 (lit share 0.15 to 0.22), so it must be encoded full range.
- Proposal, no Manifest or CONTRACTS.md change: **beauty Pass as QuickTime Animation (`qtrle`) in a .mov, 8-bit RGBA, 1920x1080**, Shadow and Depth stay as they are. It keeps the alpha in the beauty file (the generator's Mask is unchanged), decodes at about a third of the CPU of ProRes 4444 and 4 Angles hold 28 to 30 fps under load 100+. Cost: files are 1.8 times ProRes 4444 for this content (a real render with more lit area compresses less). Alpha stays straight or premultiplied as the ProRes path had it; I checked only that the Android shows up with the same lit share in Magic (0.164 against 0.152, mean grey 23.9 against 23.2). Check that Blender's FFmpeg output offers qtrle with RGBA (R5).
- Alternative if more headroom is wanted: H.264 intra 4:2:0 colour (full range) plus a grey matte file as its own Pass (`passes.matte`, generator `matte_pass=True`, Mask `Use Alpha 0`). Fastest here (32.5 fps at 4 Angles, 47 MB) but it needs `matte` in the Manifest and CONTRACTS.md, 8-bit 4:2:0 colour, and Magic's CPU was about 2 cores (209 %), more than qtrle. Not recommended before the qtrle result is seen on a quiet machine.
- Hap Alpha (GPU decode, probably the best): this ffmpeg has no Hap encoder (`-buildconf` has no libsnappy). It would need ffmpeg built with libsnappy (`brew install snappy` and an ffmpeg with `--enable-libsnappy`, for example the homebrew-ffmpeg tap) or Vidvox's hap-encoder tool. Nothing is installed; ask first.
- Not measured: a quiet machine (rerun `python3 robot/magic/decode_cost.py --configs prores,qtrle,h264_matte --angles 1,2,3,4` when `make status` says `fps_trustworthy`), a real render, Hap, raw at 3 Angles. `python3 robot/magic/decode_cost.py --list` shows the configs.

### Re-measurement with confirmed loads (2026-11-16)

Every run now verifies the load (window title `<config>_<angles>.magic - Editor`, no `Error!` window) and stops otherwise. **All numbers under load 45 to 75, `fps_trustworthy` false, not trustworthy; ratios only.** Work files: `robot/magic/decode/` (git-ignored).

| config | 1 Angle fps (2 rounds) | Magic CPU | 4 Angles fps (2 rounds) | Magic CPU |
|---|---|---|---|---|
| ProRes 4444 / 422 | 33.1 | 74 % | 21.1 | 138 % |
| qtrle / 422 | 31.4 | 36 % | 29.3 | 61 % |
| raw ARGB / 422 | 31.1 | 36 % | 28.6 | 64 % |
| H.264 + grey matte | (not rerun) | | 27.0 (34.0 and 19.9: a noisy pair) | 191 % |

- Confirmed: the qtrle and raw loads work and the numbers above are of those projects. The ratio 4 to 1 Angle: ProRes 0.64, qtrle 0.93, raw 0.92. The earlier table's qtrle, raw and H.264 rows are superseded by this one; the ProRes row is consistent with it.
- Load failures (the "Project loading failed" and `Error!` dialog): not a /tmp path (repo paths failed the same), not the codec (`qtrle_1`, `raw_1` and `prores_1` all load from the repo). An open `Error!` dialog makes every later `magicproj load` fail ("NOT confirmed"). The dialog came back on the 26th or so load of the session, on the fixture `robot.magic` that loaded fine before, so the likeliest cause is Magic degrading after many loads of 48-VideoFile projects (a leak or a limit); a Magic restart is the untested remedy. Not proven.
- A bug in `decode_cost.py` hung a run: the drain loop read the probe until quiet, and the probe sends every frame. Fixed (drain for 1 s).
- Proposal unchanged and now supported by confirmed loads: beauty Pass as `qtrle` (RGBA .mov). H.264 plus matte is noisy under this load and needs a Manifest change; not recommended.

## R8 live test (prepared 2026-11-16, not yet run)

- `python3 robot/magic/live_test.py prepare robot/package/v1/manifest.json`: writes the 48 bar, 92.9 s, 124 BPM track (intro, drop, breakdown, buildup, drop, breakdown, buildup, drop) and `robot/magic/live/robot_live_test.magic`. The project is the generator's show project (defaults: auto cuts, every Angle playing, OSC Out to 9201, Live World off through the heartbeat fallback, 9202 in) plus a Probe scene that sends Beats, Bpm, State, Section, Tier, Move, Angle, OutClip, OutFrame, IsIdle, MoveStart, Volume and Fps to 127.0.0.1:19420.
- `python3 robot/magic/live_test.py run`: the user has loaded `robot_live_test.magic` (one load; the script never loads). It checks the probe answers, plays the track once with `afplay` to the default output (BlackHole 2ch, as B11) and needs peak Volume above 0.1 in Magic, waits for silence, then plays it again while `tools/syphon_record.py` records `Main Server` (Magic) for 90 s to `docs/video/robot-live-test.mp4` and the probe log goes to `robot/magic/live/events.txt`. Magic's audio input is the user's setting and may need picking again after a restart (B11).
- `python3 robot/magic/live_test.py analyze robot/package/v1/manifest.json`: the numbers (`robot/magic/live/numbers.json`) and the 6x6 contact sheet `robot/magic/live/sheet.png` for the shot-reviewer against `robot/build/review/rubric-live.md` (frozen before the run: bar N1 to N9 for numbers, L1 to L6 for tiles).
- Restore (lead's rule): Magic holds `show.magic` for B11's planet run. Run `python3 robot/magic/live_test.py note` while Magic still holds it, before the user's load (read-only: window title resolved to `magic/projects/show.magic`, stored in `robot/magic/live/held_project.txt`; `run` refuses without it). After the run and analysis, `python3 robot/magic/live_test.py restore` loads it back with `magicproj load` and confirms the editor title and no Error window. The outcome goes in this section.
- The show's `robot.magic` itself is generated with `python3 robot/magic/robot_magic.py robot/package/v1/manifest.json` once the package is final; the test project differs from it only by the Probe scene.

### R8 live test, run of 2026-11-16 (package v1, `robot_live_test.magic`, 90 s)

**Under load 45 to 90 (`fps_trustworthy` false). fps is context only.** Test track (124 BPM, 48 bars) played straight into BlackHole 2ch (ffmpeg audiotoolbox, default output untouched), Spotify paused, the silence check passed before the run. Video `docs/video/robot-live-test.mp4` (960x540, recorded upside down by `syphon_record.py`, flipped afterwards; `run` now records with `--vflip`). Numbers: `python3 robot/magic/live_test.py analyze robot/package/v1/manifest.json` (`robot/magic/live/numbers.json`). Rubric `robot/build/review/rubric-live.md`, frozen before the run.

| Bar | Result |
|---|---|
| N1 fps | median 202.6, p5 99.8, min 93.9 (context only, load) |
| N2 black / stale | 0 black frames; 324 of 2,700 repeated frames (12 %), over the 1 % bar. Cause not separated: Magic runs a free 100 to 200 fps against 30 fps Clips and a 30 fps recorder (OutFrame steps +1 every 33 ms, p95 42 ms). A viewer's own sampling would see the same kind of repeats |
| N3 Move changes on bar lines | 20 of 20; shown 0.7 frames (median), 1.1 (max) after the Beats event. Pass |
| N4 cuts on cut points | 44 cuts, 0 off a cut point. Pass |
| N5 Tier against Section | 0 changes off a bar line; 50 bar lines; literal reading (Section 2 frames before) 6 mismatches, all State changes landing on that same bar line; with 3 frames before to 2 after allowed, 0. Pass on the windowed reading |
| N6 intensity | Move value changes per bar: calm 0.4 (5 bars), build 1.0 (10), drop 0.11 (28.2); cuts per bar 0.6, 1.0, 0.92. Literal fail: the drop is lower. Cause is in the package: the drop pool is one Move (`front_kick`), so the Clip restarts every bar without a Move change; only Angle cuts vary it |
| N7 Idle seams | 10 seams, frame-difference peak 2.36 max against 1.99 p95 of normal frames; 10.7 times the median of the changed frames (0.22), over the 3 times bar. The median is of a mostly black frame; the seam is not above ordinary motion |
| N8 spikes | the 5 times median test does not fit a frame 3.5 % lit (318 "spikes"). Largest difference 3.1, 1.6 times p95; flicker (15 s stages) mean 0.38 to 0.79, over30 0, toggles 0.002 |
| N9 bar lines against the track | median 48 ms (37 ms after 30 s); max 340 ms (also after 30 s). Median passes, max fails the 100 ms bar |

- X-Ray sections in order drop, breakdown, buildup, drop, breakdown, buildup, drop (State 3, 4, 2, 3, 4, 2, 3 at 8.7, 26.2, 28.1, 39.7, 56.9, 64.7, 70.7 s). Drops read about 1 s after the track's, breakdowns 2.7 to 3 s late, and the buildup read starts with the pad's tone rise inside the breakdown (3 s before the track's snare roll). Tempo 124.3 first, 122.9 at the end.
- Found: `/vj/clip_frame` (OutFrame) falls back one beat (14 frames) for about 15 ms after almost every beat (375 jumps, 1.9 per beat; sizes 13 to 15), then recovers: `BeatFrac` wraps before `Beats` increments. It reaches only the OSC values the scenes get, not Magic's picture. Not fixed (a fix: hold BeatFrac until Beats has stepped, or derive the pair from one Global).
- Picture review (shot-reviewer, one 6x6 sheet of 480 px tiles, gamma lifted 2.2 because the Android is dark on black; the first plain sheet judged only L1 to L3): L1, L2, L3, L5, L6 pass; L4 (edge fringe) needs a 1:1 frame and is not judged. The black level of the recording is about 10 of 255 (limited-range H.264).
- Restore: one `magicproj load magic/projects/show.magic` opened an `Error!` window and Magic still held `robot_live_test.magic`; later Magic was no longer running. Not restored, see the report to the leads.

## Issue #19, more Moves: the Clip Graph is ready (2026-11-16)

- No repeat: `ClipGraph.candidates` already left the current Move out whenever another Move fits (same tier, `key_in` equal to the current `key_out`); the Magic pick tables are written from the same `pool`. New parametrized tests over seeds, pools and walks (`NoRepeatTests`); a pool of one repeats itself (the fixture's drop). The live test's drop showed 0.11 Move changes per bar for that reason, not a graph fault.
- Several Key Poses: picks follow `key_out` to `key_in`; `ClipGraph.exits()` and `dead_ends()` list the (Key Pose, tier) pairs with no Move to leave the pose in that tier. With a way out in every tier an Idle Clip is left at the first bar line (tested over seeds and random sections); without one the walk waits in the pose's Idle Clip and leaves on a bar line when a pick appears. R5's package should keep `dead_ends()` empty, including calm, or the Android idles through that tier.
- Mixed lengths 4, 8 and 16: Magic Globals equal the model on a walk over all three (the pick happens at the Clip's end, which is always on a bar line); cut points per Clip come from the Manifest.
- `robot/package/many`: 3 Key Poses (guard, crouch, stance), 21 Moves (6 per tier plus an Idle Clip per pose) of 4, 8 and 16 beats, 2 Angles, 42 Clips. `python3 robot/magic/fixture.py --many [--media]`, then `python3 robot/magic/robot_magic.py robot/package/many/manifest.json`. Manifest, Clip Data and Camera Tracks are committed; the media and `robot.magic` are not. The generated project checks clean but has not been loaded in Magic: it holds 84 VideoFiles and nested-if tables of 63 entries (ExprTk's limit for those is unknown).
- OutFrame fix: Beats stepped 3 frames after Phase wrapped and BeatFrac 1 frame after, so `/vj/clip_frame` dipped by a beat for 2 frames at each beat. BeatFrac now reads Phase through two lag Globals (`PhaseLag1`, `PhaseLag2`) and wraps in the frame Beats steps. `tests/test_xray.py` simulates the Globals at 30, 100 and 200 fps and with bar grid shifts: it fails on the old BeatFrac and passes now. Not seen in Magic yet; a rerun of `live_test.py` shows `out_frame_jumps` going to 0 besides the Move and Idle seams.

## MMV effects in the generator (#21, 2026-11-17)

- `robot_magic.build(..., effects=True, fx=None)` puts four modules after the composite: Chroma Zoom (chromatic split on Hits), Color Controls (grade per tier), Bloom (glow on drops), Bright (flash on Hits, strobe on Angle cuts). Driven by `effect_globals`: `HitEnv` from the Clip Data Hits (`clip_hits`, a missing or unreadable Clip Data file gives no Hits), `StrobeEnv` on an Angle change, `DropAmt` easing to 1 while X-Ray says drop (times 0.5 + 0.5 Kick), `GradeSat` and `GradeCon` easing to the tier's grade (calm 0.75 / 0.95, build 1.05 / 1.08, drop 1.3 / 1.2). Switches: manual Globals `FxHit`, `FxDrop`, `FxStrobe`, `FxGrade` (1 on); at 0 each module sits at its identity value. No module reads a Pass, so no Pass can black the frame.
- Depth fog or tint: not built. It needs the depth Pass as a third VideoFile per Clip and Angle (42 more on `package/many`); not cheap.
- Live check (Magic 3 beta, under load about 74, no music so the tier is calm): `package/many/robot.magic` (99 Globals, 104 modules, 84 VideoFiles, 63-entry nested-if tables) loaded first time, editor title confirmed, no Error window. 4 Syphon grabs 3 s apart, 480x270, mean RGB 45.7/43.8/44.7, 30.6/40.0/36.1, 36.6/29.0/28.8, 43.5/41.1/42.9 (frames move). Shot-reviewer (round 1, `robot/build/review/rubric-fx.md`): X1 to X4 pass. Not seen live: a Hit flash, a cut strobe, the drop glow (needs music). `show.magic` loaded back and confirmed.

### R8 live test, run of 2026-11-17 (package v1: 21 Moves, low-quality Eevee, effects on)

**Under load 58 to 130 (`fps_trustworthy` false); fps is context only.** Magic freshly started (Untitled), one load of `robot_live_test.magic`, test track straight into BlackHole (Spotify not playing), recorded upright (`--vflip`) to `docs/video/robot-live-test.mp4`; `show.magic` loaded back, title confirmed, no Error window. Numbers: `robot/magic/live/numbers.json`. Review: `robot/build/review/rubric-live-r2.md`, round 2.

| | Result |
|---|---|
| fps | median 127, p5 97, min 93 (context) |
| picture | 0 black frames; 287 of 2,700 repeated (11 %); largest frame difference 11.6; flicker mean 0.94, p95 3.0, over30 0 |
| Move changes | 31, all on bar lines, shown 1.0 frames (median), 1.7 (max) after the Beats event |
| Angle changes | 32: the drop Moves have cut point 0 only, so the Angle changes with each Move; 1 cut inside a Move (`guard_shuffle`, flagged off its cut points by the analysis, which takes the offset modulo the Move's beats) |
| tier | drop 75 s (38.8 bars, 0.67 Move changes per bar), calm 7.7 s (0.5), build 6.3 s (0.61); 0 tier changes off a bar line, 0 mismatches with the jitter window (2 literal) |
| `/vj/clip_frame` | no one-beat dips any more (jump sizes 1 to 3 frames from frame pacing, and 114 at a Move that restarts itself); the BeatFrac fix holds in Magic |
| beat pulse (luma by beat phase, (max - min) / mean) | drop 0.68, calm 0.43, build 0.36: a stronger pulse in the drop, where the glow follows the kick; the calm figure is the Clips' own motion, only 4 bars of it |
| X-Ray | State 3 at 1.4 s (the music after silence read as a drop), then 4 at 57.3, 2 at 64.9, 3 at 71.2: the first breakdown and buildup (23 to 39 s) were missed and the bar grid was set by that first false drop, so Magic's bar lines sat 381 ms (median), up to 966 ms, off the track's (the 2026-11-16 run: 48 ms, all sections read). An X-Ray start-up issue, not the graph's |

- Review (shot-reviewer on Opus, plain and gamma-lifted sheets): L1, L2, L3, L4, L6 pass; E2 glow and E3 effects pass (a soft bloom on drop tiles, none on calm tile 1; the colour split shows as a thin fringe on Hit tiles 3, 9, 10, 16, 30, nothing washed out). Need a full-size frame: L5 (dark side-view tiles 2, 15, 18, 24, 32, 36: dark lighting or a black part) and E1 (the calm grade is only slightly duller than the drop's at tile size). Note: brightness swings hard between drop tiles (silver against near black).
- Effects in motion: the colour split and the glow are visible in the recording's stills; the beat pulse is stronger in the drop; the cut strobe and the Hit flash are not measured on their own (no probe for HitEnv or StrobeEnv).

## X-Ray start-up misread (#29, 2026-11-17)

- Cause: `SubOut` counted every bar with low sub, silent bars too, so after the 15 s of silence before a run it already stood at 2 or more; the first kick then made `SubFast` jump (the bass relative to `BassPeak`, which after silence or a short audio check knows only the kick), and `DropPulse` fired 0.7 s after the music began. That false drop set `DownSlot`, and since `DropPulse` needed State not 3, no later drop could re-anchor the grid while State stayed 3: the bar lines stayed 0.4 to 1 s off.
- Fix (`xray.py`): `SubOut` counts only bars with music (a silent bar resets it) and is cleared by a drop; new `MusicBars` (bars of music since the last silent bar), and State moves away from where it is (except to silence, and except a drop) only after 2 bars of music; `DropPulse` no longer needs State not 3, so the sub returning after 2 bars without it re-anchors the bar grid inside a drop too.
- Tests (`tests/test_xray.py`): a replay of the start of the 2026-11-17 run (`tests/data/live-2026-11-17-start.txt`, Magic's Volume and bar lines as logged after the 15 s silence; the bass bands, not in the log, follow the cause): the old rules fire State 3 within 1 s of the logged 1.39 s, the new ones stay at 0 for the 14 s replayed. Rule cases: a drop straight after silence is not read (no evidence), 2 intro bars then the sub is read at the bar the sub enters, 1 intro bar is too little, a drop after a missed breakdown re-anchors (2 drop pulses, the old rules 1).
- Cost: a set that starts on a drop is read as one only at its first sub return after 2 bars without sub. Not run in Magic yet. `live_test.py` now probes `SubBar`, `SubFast`, `SubOut`, `MusicBars`, `DropPulse`, `DownSlot`, `KickRate` and `VolSlow`, so the next run's log can replay a start-up in full. `robot/package/v1/robot.magic` regenerated with the fix.

## Solo and duel Angles, the giant machine (#23, 2026-11-17)

- Validator (contract 2a943fa): an Angle may be a duel Angle (`opponent`, a bool); a Move has a Clip on exactly the Angles of its kind (Exchanges on the duel Angles, solo Moves on the solo ones); on every Angle each Key Pose its Clips start or end in has exactly one Idle Clip (a solo Angle: every Key Pose); the giant's points include `g_knee_l` and `g_knee_r`. fixture, many, v1 and the new `package/duel` validate.
- Rule (proposal, simple): the duel while the tier is drop, solo otherwise (`ClipGraph(..., duel_tiers=("drop",))`, also a `graph_globals` argument). The kind changes only through the Idle Clips: when the tier wants the other kind, a Move that ends goes to its own kind's Idle Clip of its `key_out`, that Idle Clip hands over on the next bar line to the Idle Clip of the same Key Pose of the other kind (on that kind's first Angle), and that one is left on the bar after as usual. So a switch takes up to 3 bars after the tier changes. A Key Pose with no Idle Clip of the wanted kind stays in its kind. Picks stay within the kind of the Move on air, cuts within the Angles of its kind. It is all in the pick tables (`pool`), so the Magic Globals change only in `Angle` (the kind switch, cuts within a group) and two new selector inputs `MoveInSolo` and `MoveInDuel` (a Move's place among the Moves of its kind; a solo-only Manifest keeps `Move`).
- `package/duel` (`python3 robot/magic/fixture.py --duel [--media]`): Key Poses guard and crouch; 14 solo Moves on front and side (an Idle Clip per pose, 4 Moves per tier), 6 Exchanges on duel_wide and duel_low (a duel Idle Clip per pose, 4 drop Exchanges of 4 and 8 beats, Hits that alternate Android to `g_core` and `g_hammer` to `head`), 40 Clips. Its `robot.magic` checks clean (104 Globals). Not loaded in Magic.
- Tests: model (`DuelTests`: one kind per Move and Angle, switches only Idle to Idle on a bar line in one Key Pose onto the kind's first Angle, duel in a settled drop and solo otherwise, cuts within the kind, pools, a pose without a duel Idle Clip stays solo); Globals against the model on package/duel over calm, build, drop, breakdown and back (Move, Angle, MoveStart, OutClip, the selector inputs); the duel project's selectors; validator cases for the coverage, the Idle rule per Angle and the knees.

## Variation: variants, Idle chains, Flavor (#32, 2026-11-17)

- Manifest: a Clip may carry `variant_of` (a base Move's name). The variant is its own Move in its base's family and shares key_in, key_out, tier, idle and opponent with the base; beats, frames and Cut Points may differ. The Idle rule counts an Idle Clip's variants as their base, so an Idle family may have several Clips per Angle. Old Manifests: every Move is a family of one. The contract text (`robot/CONTRACTS.md`) is R5's to write.
- Pick (`ClipGraph.score`, `next_move`): the pools are unchanged; the pick takes the best score in the pool. Fresh: the family not picked for `FAMILY_WINDOW` (32 beats) and the Move not for `VARIANT_WINDOW` (128 beats, about a minute at 124 BPM). Fresh before stale; among fresh families a hash per family (each family as likely, whatever its variants), then a hash per variant; among stale ones the oldest. `State.used` holds (Move, beat last picked).
- Idle chains: an Idle Clip with no Move to leave into plays its whole length, then goes to another variant of its Idle family, never itself (`pool`, `chain`). It still leaves into a Move on the next bar line; the solo and duel switch is unchanged. A Key Pose with one Idle variant loops as before.
- Flavor: a hash of the pick's start beat. The Move's cut chance is `cut_rate x (0.4 + 1.2 x Flavor)` (0.85 on average at 1), and `HitEnv` and `StrobeEnv` start at `0.6 + 0.8 x Flavor`.
- Globals: `Score<i>` and `Used<i>` per Move, `Chain`, `Flavor`; `PickH` is gone. Same pipeline timing. Every table is now a binary tree of ifs (`tree`), so nesting stays log2(n) deep: a linear chain of 228 entries broke the tests' interpreter, and ExprTk limits nesting too. v1's `robot.magic` regenerated (167 Globals, checks clean).
- `package/variants` (`python3 robot/magic/fixture.py --variants [--media]`): package/duel with 4 variants of every Move and 3 of every Idle Clip, 76 Moves, 152 Clips; its `robot.magic` checks clean (257 Globals). Not loaded in Magic.
- Tests: a 3-minute model walk (calm, build, drop, breakdown, build, drop, calm; 5 seeds) never picks the same Move variant within 124 beats; families equally likely; fresh, stale and oldest cases; an Idle chain walks all its variants at their length, never one after itself, and leaves into a Move on the bar; each pick's cut chance; the Globals equal the model on package/variants with and without an Idle chain over 200 beats (Move, Angle, MoveStart, OutClip, Used); validator cases for `variant_of`.

## Backdrops (2026-11-17)

- Contract and validator: optional top-level `backdrops`, each `{id, frames, angles: {<angle id>: path}}` with exactly the Manifest's Angles; missing or empty means none. Plates are opaque H.264, full range, 1920x1080, 30 fps, looping on their own clock (the format is in the text, not checked).
- Rule (`ClipGraph.backdrops`, Globals `BdSec`, `BdSecLag`, `BdSince`, `BdDue`, `BdAngleLag`, `BeatEv4`, `BdTrig`, `Backdrop`): the first backdrop at the start; a change is due when the Section at a bar line differs from the last bar line's, and is taken at the next Angle change (a cut or the solo/duel switch, so the cut hides it), or `BACKDROP_WAIT` (8) beats on at a bar line if none comes; the next is a hash pick among the others, never the same twice in a row.
- Layer: per Angle an InputSelector (`Backdrop`) over the backdrops' plates of that Angle, hidden off air by `HideAngle<a>` like the Clips, so the plate cuts on the same frame; every Angle drawn all the time so they run in step; no Goto Start or Speed link. Plate, Shadow multiplied onto it, beauty over it with its Matte. The gate reads `Ground` (0 the Android alone, 1 the Live World, which wins while its heartbeat is on, 2 the backdrop while `BackdropOn` is 1). A Manifest without backdrops builds as before (the snapshot test).
- Not measured: the decode cost of 4 opaque 1080p H.264 plates on top of the Clips in Magic.
- `package/variants` holds 4 backdrops (arclink_city_1, chipset_04, greeble_01, greeble_03) with placeholder plates of 60 frames (`fixture.py --variants --media`, git-ignored); its `robot.magic` checks clean (267 Globals). Tests: validator cases and plate files, the model (changes only after a Section change, at an Angle change or the wait, never the same twice, all come, none or one stays), the Globals against the model, the layer and gate.

### R8 live test, run of 2026-11-18 (package v1 of 0f2d645: 31 Moves with 10 Exchanges, duel Angles, effects on; generator with variation)

- Audio: Source 0 "BlackHole 2ch 0"; peak Volume 1.00 (clamped; the drop's median 0.53). Fps median 115.8, p5 108.2 (R5 rendered in Blender meanwhile: context only). The analysis uses the Manifest the project was built from (`git show 0f2d645:robot/package/v1/manifest.json`); v1 has changed since (variants, backdrops). show.magic restored on the second try (the first opened Magic's Error window).
- #29 not passed. Bar-line offset median 111 ms, max 812 ms (after 30 s: 95, 812), against 381 / 966 ms before and 48 ms on 2026-11-16. Two causes in the log:
  1. The run starts with X-Ray primed by the audio check: the silence wait ends on Volume < 0.01 while VolSlow is still 0.17, so no silent bar resets MusicBars (8) and SubOut (3), and DropPulse fires at 1.26 s inside the intro (State 3, DownSlot 1): the bar offset is +680 ms until the real drop at 8.5 s. The harness should wait for VolSlow below Quiet; in the show, a pause shorter than VolSlow's decay keeps the evidence too.
  2. The beat clock does not lock in the drops: KickRate is 0.02 in the first drop (2.8 in the intro), so no KickPulse pulls the phase and the bar offset drifts about 40 ms a bar (214 to 812 ms over 8.5-38 s), re-anchored only by the DropPulses at 39.5 and 70.5 s; Bpm ends at 122.5. The kick band (80-320 Hz, x Gain x 4) likely stays above the gate's 0.6 with the hotter input, so the gate never re-arms. Not seen before at the lower input level.
- Sections read: 4 at 0.3 s (carried from the audio check), 3 at 1.3 (misread), 4 at 26.3, 2 at 28.3, 3 at 39.5, 4 at 56.8, 2 at 64.6, 3 at 70.5; the track's sections are intro 0, drop 7.7, breakdown 23.2, buildup 31.0, drop 38.7, breakdown 54.2, buildup 61.9, drop 69.7 s. Tier changes all on bar lines, none off.
- Solo and duel: 5 switches, each Idle to Idle in its Key Pose onto duel_wide in a drop and onto front out of it (5.1 s, 28.4, 43.2, 58.8, 74.3); duel 48 % of the time. 29 Move changes, all on bar lines; 22 cuts, none off a Cut Point.
- Repeats: 34 picks of 14 Moves; v1 of 0f2d645 had no variants. quake_stomp played 4 times running in the first drop (the only Exchange out of the low pose back into it), hammer_hit and core_strike came back within 25 s. More Exchanges per Key Pose or variants fix this, not the rule.
- Picture: 0 black frames, flicker mean 0.7 and p95 2.25 with no frame over 30.
- Review round 3 (`robot/build/review/rubric-live-r3.md`, shot-reviewer): fail. D1 tile 19 (giant and Android merged in a bright smear) and E3 tiles 19 and 20 (red/cyan colour split doubling the fighters, thick fringe): one burst of Hits with strong bloom in a duel; Exchanges alternate Hits, and the Flavor lets HitEnv reach 1.4, so the split is up to 1.4 x 0.025. L6 at low confidence: the Android is red-orange on the duel Angles and pale on the solo ones (light or material, to check at full size). L1-L5, D2, E1 and E2 pass.
