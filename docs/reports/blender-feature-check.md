# Blender feature check, 2026-11-10

Node B1. Planet scene (`synthwave_planet.blend`, rebuilt on this branch), Blender 5.2.3, M1 Max, load average 15 to 70 from foreign jobs (no fps numbers were taken). Rerun: `make blender-open`, then `make blender-check` (about 25 min for 37 controls; `ARGS="--only vj_fog,vj_hue --no-fallback"` for a part). The same code runs from the "Check all" button on http://127.0.0.1:9210; the page shows the table of the last check. Raw data: [planet JSON](blender-feature-check-planet.json), [island JSON](blender-feature-check-island.json).

## Verdict

- Planet: 30 of 37 controls have an effect, 7 do not: `/vj/blend`, `/vj/boost`, `/vj/flight`, `/vj/hit`, `/vj/grid_speed`, `/vj/hue`, `/vj/nebula`. No control errored.
- Contract: 5 mismatches with `osc/CONTROLS.md`, all in range text. Every address is on the page and every page control has a row. 37 of 37 addresses sent over udp 9201 were received and applied.
- After the check `/api/state` equals the defaults, no hold is left, the simulator is as before. An aborted check restores the same way (tested from the page).

## How a control is judged

- State per control: defaults, clocks frozen by the runtime (`freeze`, `advance`, `quiesce` in `synthwave_runtime.py`), the preconditions of the one table `PRECONDITIONS` in `blender/scenes/synthwave_check.py` (night, fog, camera, clock time to step).
- Cells: min, default, middle and max (a trigger fires at 0.5, 1 and its max). The middle matters: `vj_hue` 0 and 1 are the same colour.
- Frame: the 640x360 Syphon preview (same composite as the Syphon texture), mean of 8 frames per cell.
- Numbers per cell against a baseline: mean absolute difference (mad, 0..255), share of pixels moved by more than 8, mean signed difference (bias). Noise floor: the largest difference among 3 untouched baselines per camera and state, and the default cell. An effect clears twice the floor and a minimum (mad 0.05, share 5e-4, bias 0.02). A cell far above the floor (10x) or two cells above it make an effect; a lone marginal cell does not. A weak effect is measured again on fresh baselines.
- A control with no effect on its cameras is tried on `CAM_0` to `CAM_10`, so a wrong camera does not read as dead. Triggers are fired with the clocks stepped (shock 1 s, meteor 0.4 s), and the runtime's own state (`rt_shock*_a`, `rt_met*_a`) is read to tell "not taken" from "not visible".
- The applied value is read back from the scene property (the camera name for `/vj/cam`). No readback failed.
- Noise: the viewport is not static. Untouched renders differ by 0.05 to 1.1 mad depending on the camera (grid wires, dither). A paused viewport was tried and is worse: frames are identical within a cell but differ by 1 to 1.9 mad between cells. Effects below about 0.1 mad cannot be seen by this check. Large "x floor" values come from cameras with a floor near 0.005.

## Planet table

| control | range | default | verdict | cam | mad (floor) | bias (floor) | x floor | readers | note |
|---|---|---|---|---|---|---|---|---|---|
| `/vj/bass` | 0..1 | 0 | effect | 0 | 2.019 (0.082) | 3.127 (0.064) | 1384.8 | 1n 0d |  |
| `/vj/beat` | 0..1 | 0 | effect | 0 | 4.781 (0.099) | 6.548 (0.062) | 3308.8 | 0n 0d |  |
| `/vj/blend` | 0..2 | 1 | no effect | 0 | 0.040 (0.043) | 0.006 (0.004) | 1.6 | 0n 0d py | read only in Python by flight_rt.frame |
| `/vj/boost` | 0..1 | 0 | no effect | 0 | 0.109 (0.105) | 0.040 (0.018) | 2.3 | 0n 0d py | read only in Python by flight_rt.frame |
| `/vj/cam` | 0..10 | 0 | effect | 0 | 103.681 (0.263) | 107.151 (0.255) | 420 | 0n 26d |  |
| `/vj/cam_speed` | 0..4 | 1 | effect | 4 | 12.635 (0.040) | 7.099 (0.004) | 4330.5 | 0n 27d |  |
| `/vj/eclipse` | 0..1 | 0 | effect | 3 | 11.060 (0.100) | 8.385 (0.049) | 566.6 | 4n 4d py |  |
| `/vj/energy` | 0..1 | 0.3 | effect | 3 | 0.801 (0.063) | 0.089 (0.003) | 111.4 | 0n 0d py |  |
| `/vj/flamingos` | 0..1 | 1 | effect | 7 | 4.870 (0.117) | 5.803 (0.008) | 766.8 | 1n 2d |  |
| `/vj/flight` | 0..1 | 0 | no effect | 0 | 0.102 (0.066) | 0.040 (0.032) | 1.6 | 0n 0d py | read only in Python by flight_rt.frame |
| `/vj/fog` | 0..1 | 0.35 | effect | 0 | 13.395 (0.119) | 16.975 (0.062) | 4186.9 | 3n 2d |  |
| `/vj/fog_beat` | 0..1 | 0.5 | effect | 0 | 2.791 (0.249) | 3.382 (0.059) | 354.9 | 2n 0d |  |
| `/vj/fog_glow` | 0..2 | 0.6 | effect | 0 | 9.078 (0.365) | 11.653 (0.249) | 150.8 | 3n 0d |  |
| `/vj/fog_height` | 1..200 | 25 | effect | 0 | 49.105 (0.242) | 61.410 (0.140) | 673.1 | 3n 0d |  |
| `/vj/fog_hue` | 0..1 | 0 | effect | 0 | 4.457 (0.334) | 6.755 (0.163) | 81.6 | 3n 0d |  |
| `/vj/fog_noise` | 0..1 | 0.6 | effect | 0 | 0.947 (0.239) | 0.643 (0.140) | 29.4 | 2n 0d |  |
| `/vj/fog_scale` | 10..1000 | 260 | effect | 0 | 3.152 (0.226) | 2.354 (0.140) | 91.6 | 2n 0d |  |
| `/vj/fog_speed` | 0..40 | 10 | effect | 0 | 1.323 (0.160) | 0.100 (0.081) | 99.2 | 2n 0d |  |
| `/vj/grid` | 0..1 | 1 | effect | 0 | 3.693 (0.221) | 6.278 (0.322) | 132 | 2n 0d |  |
| `/vj/grid_speed` | 0..4 | 0.6 | no effect | 4 | 0.108 (0.060) | 0.025 (0.027) | 3 | 0n 0d | no shader or driver reads it |
| `/vj/haze` | 0..1 | 1 | effect | 0 | 3.268 (0.143) | 4.707 (0.118) | 1473.5 | 2n 0d |  |
| `/vj/hit` | 0..1 | 0 | no effect | 9 | 0.316 (0.108) | 0.045 (0.022) | 5 | 0n 0d py | read only in Python by flight_rt.frame |
| `/vj/hue` | 0..1 | 0 | no effect | 3 | 0.083 (0.103) | 0.023 (0.012) | 2 | 1n 0d |  |
| `/vj/intensity` | 0..2 | 1 | effect | 0 | 124.733 (0.265) | 141.759 (0.300) | 662.3 | 1n 0d |  |
| `/vj/level` | 0..1 | 0.5 | effect | 0 | 2.721 (0.133) | 3.373 (0.062) | 2063.1 | 6n 0d |  |
| `/vj/meteor` | 0..1 | 0 | effect | 2 | 0.631 (0.146) | 0.663 (0.182) | 12.9 | 0n 0d py |  |
| `/vj/moon` | 0..1 | 1 | effect | 4 | 19.488 (0.148) | 19.404 (0.045) | 431.8 | 3n 4d |  |
| `/vj/moon_phase` | 0..1 | 1 | effect | 3 | 29.175 (0.438) | 21.817 (0.040) | 540.6 | 1n 0d py |  |
| `/vj/nebula` | 0..1 | 1 | no effect | 1 | 0.084 (0.092) | 0.034 (0.018) | 1.9 | 1n 0d |  |
| `/vj/night` | 0..1 | 0 | effect | 0 | 117.593 (0.256) | 136.571 (0.272) | 1097.7 | 1n 28d |  |
| `/vj/pyramids` | 0..1 | 1 | effect | 0 | 1.065 (0.094) | 0.594 (0.108) | 495 | 1n 4d |  |
| `/vj/shock` | 0..1.5 | 0 | effect | 2 | 47.072 (0.094) | 39.185 (0.027) | 1839.7 | 0n 0d py |  |
| `/vj/star_speed` | 0..10 | 0 | effect | 0 | 0.284 (0.121) | 0.109 (0.019) | 13.6 | 0n 0d py |  |
| `/vj/stars` | 0..1 | 1 | effect | 1 | 1.149 (0.092) | 1.355 (0.018) | 74.6 | 11n 0d |  |
| `/vj/strobe` | 0..1 | 0 | effect | 0 | 121.537 (0.141) | 152.317 (0.096) | 10000 | 1n 0d |  |
| `/vj/sun` | 0..1 | 1 | effect | 0 | 14.588 (0.119) | 17.633 (0.062) | 1640.9 | 3n 1d |  |
| `/vj/water` | 0..1 | 1 | effect | 1 | 14.074 (0.071) | 18.440 (0.014) | 3237.7 | 1n 0d |  |

counts: {'effect': 30, 'no effect': 7}; noise floor {'mad': 1.1238, 'frac': 0.045317, 'bias': 0.3952}; defaults restored: True; state equals defaults: True; holds released: True

Columns: `cam` is the camera that showed the best effect (or the first tried, when none did). mad and bias are the largest cell value, the floor in brackets. `readers` are Attribute nodes (n) and drivers (d) found in the scene data, `py` marks a reader in Python. Frames of the controls without an effect are in `blender/review/out/feature_check_planet_frames/<control>-cam<N>-{base,min,max}.png` (git-ignored, written by the check; upright, 640x360).

## Bugs found

1. **Flight and Energy controls have no reader.** `/vj/flight`, `/vj/boost`, `/vj/blend`, `/vj/hit` show nothing on any camera and `/vj/energy` only on `CAM_3` at 1.0 (0.8 mad, no reader found, unexplained, treat as unconfirmed). Cause: `synthwave_runtime.main()` never loads or starts `flight_rt` (the hook is listed as "not written yet" in `docs/research/synthwave-flight.md`); nothing else reads these properties. `STATE.md` lists the Flight camera and Energy as working. Owner: B2 (Flight behaviour, not touched here).
2. **`/vj/hue` is wired into a dead end.** In the node group `VJ_Color` (used by 18 materials and worlds) `Attribute(vj_hue)` goes to `Math` (ADD 0.5) and `Math.001` (FRACT), and `Math.001` has no outgoing link. The input `Hue` of `Hue/Saturation/Value` stays at 0.5. Fix: link `Math.001.Value` to `Hue/Saturation/Value.Hue` in `VJ_Color`. The island file has no builder, so the fix is made in `synthwave_pyramids.blend` and the planet rebuilt. Found with `blender/review/attribute_readers.py`. Not fixed here (scene data, a look change).
3. **`/vj/grid_speed` is read by nothing.** No Attribute node or driver reads `vj_grid_speed` or `rt_grid_phase` in the planet file, so the ground grid never scrolls. The contract still says "grid scroll". Owner: planet build (`build_planet.py`) or drop the control.
4. **`/vj/nebula` shows on no camera.** Night 1, `CAM_0` to `CAM_10`, 0.08 mad against a floor of 0.04. One Attribute node reads it (material `Nebula`). Not decided whether the volume is out of every camera's view or not drawn. Look issue, B3.
5. **The shipped `.blend` ran a stale runtime.** Blender runs the text block's stored copy on load, not the file it points to. `synthwave_planet.blend` and `synthwave_pyramids.blend` embedded a runtime without `vj_flight`, `vj_boost`, `vj_blend`, `vj_energy`, `vj_hit`: the page showed 32 controls and `make blender-check` could not have run. Fixed: the planet is rebuilt (`make blender-rebuild` re-embeds the texts) and the island refreshed with `blender/review/refresh_texts.py`. Rule: after any runtime edit run `make blender-rebuild`; `synthwave_web.py`, `synthwave_check.py`, `syphon_out.py` and the page are read from files.
6. **Preconditions that are not bugs but are traps.** `/vj/fog_hue` and `/vj/fog_glow` showed nothing in earlier runs of this session at fog 0.35 and 0.7 by day on any of the 11 cameras, and show with dense fog at dusk (fog 1, night 0.5: 81x and 151x floor in the final run). `/vj/nebula`, `/vj/stars`, `/vj/moon`, `/vj/moon_phase`, `/vj/eclipse`, `/vj/meteor` need night; `/vj/meteor` is faint in the 640x360 preview (12.9x floor on `CAM_2`). All are rows of `PRECONDITIONS`.

Fixed inside the runtime and page: none of the above bugs; the check itself needed `freeze`/`advance`/`quiesce` and a preview counter (`syphon_out.previews`), added for it.

## Contract cross-check

| address | kind | detail |
|---|---|---|
| `/vj/cam` | range | contract 0..6, page 0..10 |
| `/vj/fog_height` | range not numeric | contract 'm', page 1..200 |
| `/vj/fog_scale` | range not numeric | contract 'm', page 10..1000 |
| `/vj/fog_speed` | range not numeric | contract 'm/s', page 0..40 |
| `/vj/grid_speed` | range not numeric | contract 'grid cells/s', page 0..4 |

udp 9201: sent 37, received 37, applied 37, errors 0, not seen []

The four unit rows (`fog_height`, `fog_scale`, `fog_speed`, `grid_speed`) have no numeric range in `osc/CONTROLS.md`, so the page's ranges (1..200, 10..1000, 0..40, 0..4) cannot be compared. `/vj/cam` is 0..6 on the island and 0..10 on the planet; the contract text gives both. `/vj/fog_height` says "capped at 60 m" while the page allows 200.

## Syphon frame orientation (evidence only)

`python3 blender/review/syphon_orientation.py` (scene held still): the scene's own preview, flipped to top-down, has row luminance 177.9, 119.2, 62.2 from top to bottom (sky above, ground below). `magic/magicproj.py grab --app Blender --server CAM_OUT` returns the rows 68.5, 122.0, 178.5: reversed. Error against the preview 228.5 in the delivered order, 9.7 reversed. So the frame Blender publishes has row 0 at the bottom (the GL-origin texture, `FLIPPED = False` in `syphon_out.py`, commented there as what GL receivers such as Magic need). `grab()` reverses the rows only for `app == "Magic"` (`magicproj.py` line 1209, "Magic's frames arrive bottom-up"), so for Blender it prints the delivered bottom-up order. Which side flips: the grab tool's reading of Blender's frame, not a change in the sender. Whether Magic shows Blender's frame upright is not observed (Magic is the user's app and was not driven). That is B4's check.

## Island scene

Not usable, and not a verdict on the scene. The run completed (8 effect, 29 no effect, defaults restored) but the noise floor is exactly 0.000 and `vj_intensity`, `vj_level`, `vj_bass`, `vj_strobe`, `vj_fog` and `vj_water`, which have Attribute-node readers, show 0.000 on every camera, while the controls that move objects (`vj_night`, `vj_sun`, `vj_moon`, `vj_cam`, `vj_cam_speed`, `vj_shock`, `vj_pyramids`) show. The original `synthwave_pyramids.blend` from `HEAD` behaves the same (intensity 1 vs 0 differs by 1.2, the same as two renders of one state, 1.9). The island ran at 60 fps against 22 on the planet. Suspected cause, not verified: the island's viewport is in Solid shading (its Layout screen saves `SOLID`; the planet builder sets `RENDERED`, the island has no builder), so no shader reads the properties in the frame. B4 owns the island's start state; rerun `make blender-check` on it after the viewport is rendered. Data: [island JSON](blender-feature-check-island.json).

## Not done

- Pixel differences in 640x360 cannot see effects below about 0.1 mad; the check says "no effect" for them.
- Fallback cameras are limited to `vj_cam` values; free views and the `CAM_SYS_*` cameras are not tried.
- No fps was recorded.
