# Magic Music Visuals projects

Generators and tooling for `.magic` files. The skill `.claude/skills/magic-projects` says when to use which command.

## Synthwave project

`projects/synthwave_pyramids.magic` plays `blender/scenes/synthwave_pyramids.blend` and `synthwave_planet.blend`. It is generated: edit `synthwave_magic.py` and run `python3 magic/synthwave_magic.py` (`--port 9200` to go through the optional lab relay, `--syphon "<sender> - Blender"` for another Syphon name, `--synthetic --out FILE` for a test build that replaces audio and controls with a scripted EDM loop and timers, `--audio FILE` to play and analyse an audio file in a loop instead of BlackHole). Defaults: OSC to the bridge on 127.0.0.1:9201, Syphon server `CAM_OUT - Blender`, audio from BlackHole 2ch, OSC in on 11111. Every address, its wire range (0..1 for a continuous control) and its wire default come from `osc/contract.json`; the generator sends wire units and each scene scales them.

## Show project

`projects/show.magic` (`show_magic.py`, `python3 magic/show_magic.py`) is the synthwave project with two Syphon sources, `CAM_OUT - Blender` and `COLOSSUS_OUT - Godot`, in the Program scene. A `Mix` module crossfades them with the Global `SceneMix` (0 Blender only, 1 Godot only) and the effects run on the mix. Its senders go straight to the scene on udp 9201, which Blender's bridge and the Godot Colossus Scene both listen on (one runs at a time). `--syphon-godot` sets another server name. `Cam` and `CamAuto` are for Godot only (`/vj/cam`, `/vj/cam_auto`); Blender's Path Camera takes `Path`, `Target` and `Height`. Magic publishes its own mixed picture as Syphon `MAGIC_OUT - Magic` (1920x1080, `--syphon-out` renames it), which `magicproj.py grab --server MAGIC_OUT` reads and another app can take. The handbook's table of what Magic sends and why is made from this project: `python3 magic/magic_manual.py sync`.

Scenes:
- **Master**: Program behind Blackout, the Monitor overlay, and OSC Out.
- **Program**: SyphonClient → Bloom → Chroma Zoom → RadialBlur → Kaleidoscope → Shake. Each effect is bypassed while its amount is 0. `--trails` adds `effects/Synthwave Trails.fs` before the Kaleidoscope (each pixel is the brighter of the live frame and its fading history, so nothing goes dark); Magic finds it once `effects/` is listed under Help > Additional Module Folders. Magic's own Trails module draws behind its input through alpha, which the opaque Syphon frame hides, and the usual feedback shaders key dark pixels to their black history.
- **OSC Out**: one OSCSender per `/vj/*` address. OSCSender only sends on change, so every value jitters by 0.001 for the first 2 s and the scenes are reset to the project's values at load. Each value is clamped to the row's wire range (0..1, an index up to 10, a trigger up to 1.5), so a Global dragged past 1 in Magic cannot overdrive a scene.
- **Monitor**: a bar per analysis Global, for tuning.
- **Readout**: every `/vj/*` address with the value being sent, yellow while it differs from the scene default. Text cannot print numbers, so each row lists every displayable value and `Line #` picks one.

Controls are unlinked Globals in 0..1, ready for MIDI or OSC learn. Every `/vj/*` address has one named like it (`/vj/fog_height` is `FogHeight`), holding the contract's default. Where the music drives an address, the control is its value while no music plays and the base the music moves. `Live` is 1 while the input carries sound (it fades over 3 s after it stops), `Follow` is `Live` x `React`: with no sound, or `React` 0, every address holds its control and the cutter stands still.

| Global | Does |
|---|---|
| `Gain` | input sensitivity (0.5 = ×2) |
| `Master`, `Blackout` | overall brightness (scales `Intensity` and `Strobe`); black |
| `React` | the music mapping on or off: 0 = the controls alone, 1 = music drives the addresses it can |
| `Level` `Bass` `Beat` `Intensity` | `/vj/level` `/vj/bass` `/vj/beat` `/vj/intensity` |
| `Auto` | automatic build, drop and breakdown direction |
| `Strobe` | flash on every beat; the music adds flashes in drops and builds |
| `Buildup` | manual build fader, added to the detector |
| `Drop` | momentary pad, fires a drop |
| `Shock`, `ShockKick` | momentary pad, fires a shockwave; shockwaves on heavy kicks |
| `Meteor` | momentary pad, fires a shooting star |
| `Hue`, `HueDrift` | hue offset; hue walk per bar and per drop |
| `Path`, `Target`, `Height`, `CamSpeed` | the Path Camera: path 0..1 over 4 paths, target 0..1 over 7 targets, height (0.5 about 800 m); with music path and target step on at every drop and every 16 bars (`Moves`), height sinks on builds and rises in breakdowns; speed along the path |
| `Takeover` | how long a touched control stays yours before the music steers it again, 0..1 = 0..60 s; per steered control `<Name>Touch` keeps the clock of its last change and `<Name>Follow` is 0 meanwhile |
| `CamAuto`, `Cam` | Godot only: its director on or off; the shot 0..1 over shots 0..11 |
| `GridSpeed` | grid scroll speed (`/vj/grid_speed`) |
| `Sun` `Moon` `Pyramids` `Grid` `Stars` `Water` | scene elements, faded |
| `MoonPhase`, `Eclipse`, `StarSpeed` | moon on its orbit (0 new, next to the sun; 1 full, opposite); eclipse alignment (lunar at full, solar at new moon); star drift against the sun (×10, 1° per second at 0.1) |
| `Night`, `Nebula` | sun height (0 +20°, 0.5 half set, 1 -18° night; lowering it runs time backwards); nebula strength at night |
| `Flamingos` | flock size |
| `Fog` `FogHeight` `FogGlow` `FogHue` `FogNoise` `FogScale` `FogSpeed` `FogBeat` | fog, scaled to the scene's units (height ×60 m, glow ×2, scale ×520 m, speed ×40 m/s) |
| `Haze` | distance haze; 0 with `Fog` 0 is a fog-free view |
| `FxGlow` `FxTrails` `FxBlur` `FxChroma` `FxShake` `FxKaleido` | Magic effect amounts, all 0 by default and never raised by Auto, so Magic passes Blender's frame through untouched (Bloom also lays a milky veil over the sun) |
| `Monitor`, `Readout` | meter overlay; OSC value overlay |

Analysis, all in Globals:
- Bands are Magic's five 2-octave ranges, scaled by `Gain`.
- `Kick`, `Snare`, `Hat` are onsets: a ~10 ms follower above 1.25–1.4× a ~0.3 s follower plus a floor scaled to the track's recent peak, with a refractory time (0.22, 0.12, 0.06 s) and an exponential decay in seconds. The kick reads sub plus half the 80–320 Hz band; once the beat clock is locked only onsets within ±0.15 beat of it count, so off-beat bass notes neither flash nor pull the clock.
- A beat clock follows the kicks: `Period` comes from the kick intervals (folded into 100–200 BPM, shown as `BPM`), `Phase` runs 0..1 per beat and each kick pulls it toward 0, and `Lock` says how well kicks land on it (it fades over ~6 s without kicks). `Pulse` is the clock's own beat envelope, so `Beat` (`Kick`, `Lock`×`Pulse` or Synesthesia's `/audio/beat/onbeat` on OSC in) stays on the grid through a missed kick. `Beats` and `Bars` count clock beats, so camera cuts land on bar lines.
- `OutLevel` and `OutBass` are relative to the track's own averages, so any input level works.
- `Live` (sound on the input) times `React` is `Follow`; an Out Global is its control plus `Follow` times what the music adds to it.
- Structure is keyed on the kick: `NoKick` ramps up over 1.5–4 s without one. `Build` is that while the highs rise (riser, snare roll), `Breakdown` is that with quiet highs, and `DropEvt` is the first kick after 6 s or more without one.
- The slow trackers run in seconds (`Dt` from an Increase clock), so they hold at any evaluation rate.

OSC out (latest value of each Global; ranges and meaning per scene are in [osc/CONTROLS.md](../osc/CONTROLS.md)):

| Address | Global |
|---|---|
| `/vj/level` `/vj/bass` `/vj/beat` | `OutLevel` `OutBass` `OutBeat` |
| `/vj/hue` `/vj/intensity` `/vj/strobe` | `OutHue` `OutIntensity` `OutStrobe` |
| `/vj/grid_speed` `/vj/cam` `/vj/cam_auto` `/vj/cam_speed` | `OutGridSpeed` `OutCam` `OutCamAuto` `OutCamSpeed`; `OutCam` is a whole number from `Cam`, for Godot |
| `/vj/path` `/vj/target` `/vj/height` `/vj/takeover` | `OutPath` `OutTarget` (whole numbers) `OutHeight` `OutTakeover` |
| `/vj/sun` `/vj/moon` `/vj/pyramids` `/vj/grid` `/vj/stars` `/vj/water` | `OutSun` … `OutWater` |
| `/vj/night` `/vj/nebula` `/vj/shock` | `OutNight` `OutNebula` `OutShock`: a 50 ms pulse at the wave's strength on heavy kicks (at most every 0.9 s, every 0.35 s while a drop is fresh; 0.6 rising to 1.5), on each drop (1.5) and on the pad |
| `/vj/fog` … `/vj/fog_beat` | `OutFog` … `OutFogBeat`; fog thickens in breakdowns and glows on drops while `Auto` is on |
| `/vj/meteor` `/vj/flamingos` `/vj/haze` `/vj/moon_phase` | `OutMeteor` (1 while the pad is held) `OutFlamingos` `OutHaze` `OutMoonPhase` |
| `/vj/eclipse` `/vj/star_speed` | `OutEclipse` `OutStarSpeed` |
| `/vj/blend` `/vj/energy` `/vj/hit` | `OutBlend` (Fade Time) `OutEnergy` (faders `Blend` `Energy`, passed on as they are) and `OutHit` (1 while the `Hit` pad is held) |


## Magic projects (`magicproj.py`)

Read, check, diff, edit, build and live-check `.magic` files. `magic_modules_v3.json` is every bundled module's params as Magic 3.0b6 saves them; `catalog` and `check` use it. Standard library only; `grab` also needs syphon-python. The skill `.claude/skills/magic-projects` says when to use which command; the evidence is in [docs/magic-tooling-report.md](../docs/magic-tooling-report.md).

- `python3 magic/magicproj.py info|globals|nodes|osc|check FILE`
- `python3 magic/magicproj.py diff A B`
- `python3 magic/magicproj.py set FILE -o OUT --value Gain 0.7 --syphon on --osc-target 127.0.0.1:9200`
- `python3 magic/magicproj.py load FILE`, then `grab --out frame.png`
- Tests: `python3 -m unittest discover magic/tests`. The live test replaces Magic's project: `MAGICPROJ_LIVE=1 MAGICPROJ_RESTORE=<project> python3 magic/tests/test_magicproj.py LiveMagicTests`.

## EDM analysis (`edm_analysis_magic.py`)

Generates `projects/edm_analysis.magic`: live EDM analysis of Source 0/1 (BlackHole 2ch) as Globals with on-screen meters. Scenes: `Compare` (all variants side by side), `A`, `B`, `C` (one meter per signal), `OSC Tap` (off). Magic opens on B, the variant rated best.

- Build: `python3 magic/edm_analysis_magic.py` (checks itself, 0 errors).
- Read live values: build with `--tap -o X.magic`, `load` it, `edm_analysis_magic.py record 9311 60 rec.jsonl`. Raw inputs go to `/raw/<Global>`, the `TapVar` variant (0 a, 1 b, 2 c) to `/o/<signal>`.
- Replay offline: `edm_analysis_magic.py sim rec.jsonl [--series aBPM,bBuild]` runs the Global expressions on the recorded inputs, double-buffered like Magic (live vs sim correlation: BPM 0.99, phase 0.90, energy 0.96).
- Tests: `python3 -m unittest magic/tests/test_edm_analysis.py`.

Signals (`<v>` = `a`, `b` or `c`; 0..1 unless noted):

- `<v>Sub`: 20-80 Hz level, 0.5 = typical for the track (8 s mean).
- `<v>Bass`: 80-320 Hz level, same scale.
- `<v>Hard`: hard (distorted) bass: bass body vs sub, 0.4 = the track's typical ratio (averaged only while sub is present), 0 without sub or in the first 6 s of music.
- `<v>Vol`: overall volume, 0.5 = typical.
- `<v>VolNB`: volume without bass (320 Hz-20 kHz), 0.5 = typical.
- `<v>HatLvl`: 5-20 kHz level, 0.5 = typical.
- `<v>Vocal`: singing presence: 300-3400 Hz band above its 30 s mean and above its neighbouring bands.
- `<v>Width`: stereo width: L/R level difference of the mid/high bands minus that of the sub, x3.
- `<v>Energy`: energy against the track's own average (A, C: weighted bands vs 30 s; B: volume vs 45 s), 0.5 = average.
- `<v>Bright`: brightness (Magic's Tone).
- `<v>Kick`, `<v>Snare`, `<v>Hat`: onset envelopes (1 on the hit, decaying); `<v>KickOn` etc. are the one-frame events.
  - Kick: low-band log flux, on the beat (±0.1 beat), at least half the strongest of the last 4 s, at most one per 0.6 beat.
  - Snare/clap: 320-1.2k and 1.2-5k rising together, at least 70 % of the strongest of the last 4 s.
  - Hat: 5-20 kHz rising without a low hit, at least 70 % of the strongest of the last 2 s.
- `<v>BPM`: tempo, 90-180.
- `<v>Phase`: beat phase 0..1, `Lead` s ahead of the analysis (default 0.04) to cover Magic's latency; `<v>Beat`: pulse on each beat; `<v>Tick`: one-frame beat event.
- `<v>Conf`: beat-clock lock (coherence of onsets with the beat).
- `<v>BarPos`: beat in the bar 0..3, counted from the last drop.
- `<v>Build`, `<v>Break`: buildup and breakdown, 0..1.
- `<v>Drop`: 1 on a drop, falling to 0 over 4 s; `<v>DropEv`: one-frame event; drops are at least 15 s apart.

Shared by all variants:

- Beat clock: 24 leaky resonators (90-180 BPM) on low-band onset strength give the tempo (`TPer`) and a phase (`TPh`); an adaptive oscillator (`aPh`, `aPer`) locks to the onsets near the beat and is re-seeded from the bank when it loses lock.
- Measured on two techno tracks against the audio: tempo within 0.5 %, phase error about 30 ms (one track) to 80 ms (the other, a constant offset that `Lead` corrects), kicks 85-98 % on the beat.

Variants differ only in song structure:

- A: buildup from rising brightness, treble and snare rate; drop = first strong kick after 3.5 s without one; breakdown = no strong kick for 4 beats with the low end down.
- B (rated best): buildup while sub presence is under 35 % of typical and brightness or hit density rise, full after 24 beats; drop = low end jumping to 1.6x its 8 s mean within 2 s of a gap or during a buildup; breakdown = sub presence under 20 % for 4 beats.
- C: B's buildup, full after 16 beats; A's drop.
