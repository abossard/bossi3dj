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

## Live results so far (2026-11-12, Magic only; Blender was held by planet-finish, so nothing was written to it)

Magic ran with a copy of the project that sends to udp 9300 (`magicproj.py set --osc-target`), read with `magicproj.py listen 9300`:
- all 38 addresses arrive (n=63 in 14 s each, `/vj/fog` more while it eases to 0.35). With no sound every value sat on its contract default (level 0.5, intensity 0.5, grid_speed 0.15, cam_speed 0.25, cam 0, cam_auto 1, fog 0.35 ...).
- `Fog` 0.9 in the project file, loaded: `/vj/fog` ends at 0.89999; the original loaded back: 0.34999.
- `show_magic.py --synthetic` (synthetic music): twelve music addresses move (fog 0.67, hue, level, strobe, shock 12 sends, cam changed), the rest hold. So `Live` and `Follow` work; the 0.004 threshold passed the silence case on the real input and the synthetic case, not tried with a real track.
- Found and fixed: `show.magic` drew a black program whenever Godot's server was missing (the `Mix` draws black without its second source, even at Amount 0), so Magic's picture was black with Godot parked. The Mix is bypassed while `SceneMix` is 0 now; the picture is Blender's (mean RGB 134, 147.6, 200 as in the `CAM_OUT` grab).
- Magic's Syphon server is `MAGIC_OUT - Magic` (`magicproj.py grab --server MAGIC_OUT` works with the default app name).
- Orientation: `tools/magic_show_proof.py picture --no-hold`: the 16x9 luma grid of Magic's frame correlates 0.999 with the `CAM_OUT` grab with its rows reversed (-0.73 upright). The `shot-reviewer` judged Magic's frame upright (sky on top) and the `CAM_OUT` grab flipped. That matches the known state: `grab` delivers Blender's Syphon rows as Syphon stores them (flipped) and flips only Magic's. So Magic shows Blender's picture upright. Judged on sky and ground only (CAM_0 here had no pyramids in view).
- Magic was not running before; it is closed again.

## Live results against Blender (2026-11-12, planet scene opened by `make blender-open`, kept open for the next session)

- `python3 tools/blender_page_test.py`: 22 of 22 ok (37 of 37 controls with sentences in manual order, 12 named cameras, 415 and 403 refusals, set, hold, camera, presets, Hold all, Release all). The start check of that open said NOT ready on one row only: `health.py` (embedded `planet_runtime.py` differs from its file, the planet session's edit).
- Phone width (375 px, built-in browser) on the live page: no horizontal scroll, 12 camera buttons (7 gave "7 Flamingo Lake" on air), Hold all held 37, Release all cleared them, Check all started from the page and showed its progress chip. Check all was aborted from the page after 26 of 37 rows (25 effect, 1 no effect: `vj_grid_speed`, "no shader or driver reads it", island only by design), defaults restored, no holds, `off_default` empty. The full 37 rows were proven earlier (STATE).
- Magic loaded with `show.magic`, sending to udp 9201: `magic_show_proof.py osc`: 38 of 38 addresses reached the bridge (it took Magic about 20 s after `open -a` to start sending).
- `magic_show_proof.py global Fog 0.9`: scene `vj_fog` 0.35 to 0.878 (still easing to 0.9) and back to 0.342 after the project was loaded back, not held.
- `magic_show_proof.py picture`: Magic's `MAGIC_OUT - Magic` frame against `CAM_OUT - Blender` on CAM_0: correlation 0.997, mean luma difference 2.5 of 255 once the rows are reversed (as grabbed: -0.44, 71.8). `grab` flips only Magic's frames, so Blender's raw grab is the flipped one; the shot-reviewer judged Magic's frame upright and the raw grab flipped (earlier pair, same convention).
- Magic quit again; Blender left open on the planet with no holds.

## Open

- `Live` threshold (0.004 on `EnergyNow`) not tried with a real track.
- Not proven: Magic's live behaviour with real music through BlackHole; the page opened from an actual phone over the network (LAN mode is built, tested only through its settings file and Host rule); the page's Check all beyond row 26 from the phone-size page (the full run was proven earlier from the older page).
- `.claude/skills/magic-projects/evals/grade.py` lists the old Global names (`HueBase`, `CamSel`); not mine, not changed.
- Art-Net on the page: the bridge has it (another session); the page shows its source as the badge text and nothing else.

## Path Camera (2026-11-13)

Magic, page and handbook follow the contract of 2c370ae ([path-camera.md](path-camera.md), the user's "Yes, all five").

- Magic: the auto cutter, `CamCount`, `Flight`, `Boost` are gone. New controls `Path`, `Target` (0..1 faders over the stops, like `Cam`), `Height` (0.3), `Takeover` (0.33 = 20 s), `Blend` is the Fade Time. With music: `Moves` = 16-bar blocks plus drops; path = `Moves % 4`, target = `Moves*3 % 7` (every target in turn); height sinks on builds and drops, rises in breakdowns (smoothed). `Cam` and `CamAuto` stay for Godot, manual only.
- Takeover in Magic for every steered control (`STEERED` in `synthwave_magic.py`, 13 controls): `<Name>Prev`, `<Name>Touch` (clock of the last change by hand or MIDI, 0 = never, changes in the first second ignored), `<Name>Follow` = `Follow` or 0 while the touch is younger than `Takeover` x 60 s. The return to the music is a step in Magic; the scene's flight (fade time) and height glide smooth it. `/vj/shock` keeps its pads, no takeover.
- Page: the Camera card first (`page_model.CAMERA`): Path and Target as buttons with the contract's stop names, Height and Fade Time as faders; the header chip shows path and target by name; labels from the contract. `/api/state` has `path_camera` (the keys). Checked at 375 px against `tools/blender_page_mock.py`: no horizontal scroll, buttons set the values.
- Handbook: "The Path Camera" replaces "Cameras and the Flight" (stops generated from the contract, `magic_manual.py sync`); the hold rule became Takeover plus hold. README: Blender intro, the Flight cell and the gallery note.

Unverified (needs the Blender build and a Magic load):
- Magic's steering live: path and target stepping on drops and every 16 bars, height on builds and breakdowns, the takeover pause after a touch in Magic or by MIDI. Only the expressions are tested.
- The page against the new bridge: `tools/blender_page_test.py` (new rows: Path Camera first, named stops, a path and target set reaching the scene). Run against the mock it fails only where the mock has no bridge (Art-Net, 415, 403).
- The handbook's takeover for the page and the desk describes B9's bridge work, not yet seen.

Pictures for B10 (need Blender; the README gallery still shows the fixed shots, marked as the build before the Path Camera):
- Gallery: a handful of path and target pairs by day and at sunset (for example Orbit / Pyramids, Follow the land / River, Vantage / Coast, Rise and descend / Planet at height 1), replacing the `CAM_N` captions.
- OSC manual pictures (`docs/images/readme/osc/<name>-blender.jpg`, low | high): `path`, `target`, `height` (0 and 1), `blend` (a cut against a flight; the current picture shows the old shot change), `takeover` has none (a time).
- Remove from the manual folder once replaced: `cam-planet-*.jpg`, `cam-island-*.jpg` if the island goes too, `flight-blender.jpg`; `cam-blender.jpg` is unused since `/vj/cam` is Godot only.
