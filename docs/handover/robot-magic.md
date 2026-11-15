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
- `robot_magic.py`: Robot scene (SyphonClient `ROBOT_LIVE - Blender` into Blend Multiply with the Shadow InputSelector, Mask on the beauty InputSelector, Transparency with the Android in front) and `OSC Out` scene (3 OSCSenders to 127.0.0.1:9201). 8 VideoFiles per selector, ordered move-major, Angle minor. Speed linked to `SpeedRatio` = BPM / manifest bpm. `Goto Start` linked to `StartPulse` (2 frames at each Move change). OSC rows live in one table, `OSC_ROWS`.
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

## Needs the user's Magic

1. Does VideoFile play ProRes 4444 and keep the alpha? (Fallback: Hap Alpha, needs another encoder.)
2. Does a VideoFile that the InputSelector is not drawing keep playing? If not, an Angle cut mid-Clip shows the other Angle's old frame. Fallback: draw all 8 behind Transparency Amount 0/1, or restart on every Angle cut with a Start Time per beat.
3. `Goto Start` linked to a 2-frame pulse: does it restart the video once, and does `Looping 0` hold the last frame (the Key Pose) instead of going black?
4. Blend `Mode 3` multiplies the Shadow Pass onto the Live World as meant (shadow dark on white). Mask with one source on both pins.
5. Duplicate `Child` id in Mask (`20,20`): accepted by `check`, not tried in Magic.
6. Relative `File` paths (`beauty/idle__front.mov` next to the `.magic`) resolve; `absoluteFilename` is also written.
7. `ROBOT_LIVE - Blender` is the Syphon server name once the live scene exists (R7); tests use `ROBOT_TEST`.
8. OSCSender sends floats; the live scene should accept them as integers.

## Open for the `osc/` owner

The addresses are only in `robot_magic.OSC_ROWS` until `osc/contract.json` has the rows (R2).
