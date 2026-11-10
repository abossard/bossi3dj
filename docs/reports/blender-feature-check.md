# Blender feature check, 2026-11-10

Nodes B1 and B4. Planet (`synthwave_planet.blend`, rebuilt on this branch) and island (`synthwave_pyramids.blend`), Blender 5.2.3, M1 Max, load average 40 and more from foreign jobs: no fps numbers were taken. Rerun: `make blender-open SCENE=planet|island` (waits for the start state), then `make blender-check` (about 25 min per scene with the camera fallback; `ARGS="--only vj_fog,vj_hue --no-fallback"` for a quick pass). Tables below come from `docs/reports/blender-feature-check-planet.json` and `-island.json` through `blender/review/feature_check_table.py`.

## Verdict

- Planet: 33 of 37 controls have an effect, 4 do not: `/vj/blend`, `/vj/boost`, `/vj/flight` (Flight, B2) and `/vj/nebula` (look issue, B3). `/vj/energy` and `/vj/hit` now show an effect with no reader found (91x and 83x floor on one camera each): unexplained, unconfirmed, B2 to look at. No control errored.
- Island: 30 of 37, 7 do not: the five Flight and Energy controls (`/vj/blend`, `/vj/boost`, `/vj/flight`, `/vj/hit`, `/vj/energy`, B2), and `/vj/eclipse` and `/vj/star_speed`, which only the planet's `star_system.py` reads. Island nebula has an effect.
- Contract cross-check against `osc/contract.json` (range, default, trigger, existence, all failures): 0 mismatches on both scenes. udp 9201: 37 of 37 addresses applied. The six messages of `docs/handover/osc-contract.md`: 6 of 6 on both scenes.
- Start state: cold `make blender-open` of each scene reaches camera view in Rendered shading, runtime playing, bridge on 9201, Syphon drawing real pixels (preview luminance variance 2300 to 2700, grabbed frame lit 1.0), page on 9210, defaults, `health.py` clean.
- After each check `/api/state` equals the defaults and no hold is left.

## Changes of B4

- Stale embedded code: both files embed one text block, `vj_loader.py` (`blender/scenes/vj_loader.py`, put there by `make blender-prepare`). It runs `synthwave_runtime.py` from disk, which loads the bridge (`blender_osc_bridge.py`), Syphon sender and page from their files. `health.py` lists any embedded text that differs from its file. The earlier note that the `.blend` ran an older runtime is gone with this.
- Viewport: Blender opens 3D views in Solid shading whatever the file stores (set and saved headless, read back as Solid). The runtime sets camera view and Rendered when the window exists. That was the island's "invalid" run of B1: Solid shading drew no shader attributes.
- `/vj/hue`: the island's `VJ_Color` had the link; `build_planet.py` removed it on purpose (`no_hue`). The call and the function are removed, the planet rebuilt: effect 63 mad on `CAM_0`.
- `/vj/grid_speed`: the planet's wire lattice scrolls along the meridians by `fract(rt_grid_phase)` cells in `build_planet.py` (`la`). Effect 6.6 mad at 20x floor on `CAM_0`.
- Ranges: `vj_fog_height` 1..60 (runtime and contract; wire default 0.41), `vj_fog_scale` contract min 10 (wire default 0.25), `vj_cam` ends at the scene's last camera (0..10 planet, 0..6 island, set in `ensure_props`); the bridge now clamps an index to its property range as well as a float. Magic generator and `show.magic` follow (`make magic-build`).
- `/api/health` on the page runs `health.py` on the main thread; `/api/state` carries the bridge's `ignored` count.

## Planet table

| control | range | default | verdict | cam | mad (floor) | bias (floor) | x floor | readers | note |
|---|---|---|---|---|---|---|---|---|---|
| `/vj/bass` | 0..1 | 0 | effect | 0 | 2.100 (0.128) | 3.266 (0.074) | 1437 | 1n 0d |  |
| `/vj/beat` | 0..1 | 0 | effect | 0 | 4.851 (0.164) | 6.658 (0.109) | 3379.1 | 0n 0d |  |
| `/vj/blend` | 0..2 | 1 | no effect | 3 | 0.066 (0.049) | 0.007 (0.004) | 1.8 | 0n 0d py | read only in Python by flight_rt.frame |
| `/vj/boost` | 0..1 | 0 | no effect | 10 | 0.051 (0.041) | 0.001 (0.003) | 3.4 | 0n 0d py | read only in Python by flight_rt.frame |
| `/vj/cam` | 0..10 | 0 | effect | 0 | 103.334 (0.365) | 105.421 (0.330) | 319.1 | 0n 26d |  |
| `/vj/cam_speed` | 0..4 | 1 | effect | 4 | 12.914 (0.039) | 8.155 (0.008) | 4416.9 | 0n 27d |  |
| `/vj/eclipse` | 0..1 | 0 | effect | 3 | 11.064 (1.063) | 8.419 (0.038) | 221.5 | 4n 4d py |  |
| `/vj/energy` | 0..1 | 0.3 | effect | 9 | 0.895 (0.068) | 0.090 (0.021) | 91.3 | 0n 0d py |  |
| `/vj/flamingos` | 0..1 | 1 | effect | 0 | 0.316 (0.148) | 0.404 (0.074) | 103 | 1n 2d |  |
| `/vj/flight` | 0..1 | 0 | no effect | 8 | 0.039 (0.061) | 0.007 (0.001) | 3.5 | 0n 0d py | read only in Python by flight_rt.frame |
| `/vj/fog` | 0..1 | 0.35 | effect | 0 | 13.540 (0.167) | 17.227 (0.094) | 4229.2 | 3n 2d |  |
| `/vj/fog_beat` | 0..1 | 0.5 | effect | 0 | 2.893 (0.212) | 3.497 (0.114) | 213.3 | 2n 0d |  |
| `/vj/fog_glow` | 0..2 | 0.6 | effect | 0 | 9.048 (0.338) | 11.695 (0.202) | 249.1 | 3n 0d |  |
| `/vj/fog_height` | 1..60 | 25 | effect | 0 | 14.768 (0.178) | 18.471 (0.108) | 1202.4 | 3n 0d |  |
| `/vj/fog_hue` | 0..1 | 0 | effect | 0 | 4.379 (0.284) | 6.837 (0.155) | 153.1 | 3n 0d |  |
| `/vj/fog_noise` | 0..1 | 0.6 | effect | 0 | 0.975 (0.179) | 0.579 (0.108) | 63.3 | 2n 0d |  |
| `/vj/fog_scale` | 10..1000 | 260 | effect | 0 | 3.242 (0.171) | 2.394 (0.108) | 317.1 | 2n 0d |  |
| `/vj/fog_speed` | 0..40 | 10 | effect | 0 | 1.311 (0.148) | 0.071 (0.066) | 258.5 | 2n 0d |  |
| `/vj/grid` | 0..1 | 1 | effect | 0 | 3.639 (0.223) | 6.149 (0.224) | 372.9 | 2n 0d |  |
| `/vj/grid_speed` | 0..4 | 0.6 | effect | 0 | 6.575 (0.377) | 0.160 (0.304) | 20.2 | 1n 0d |  |
| `/vj/haze` | 0..1 | 1 | effect | 0 | 3.212 (0.192) | 4.622 (0.074) | 1468.8 | 2n 0d |  |
| `/vj/hit` | 0..1 | 0 | effect | 3 | 0.832 (0.078) | 0.112 (0.007) | 82.5 | 0n 0d py |  |
| `/vj/hue` | 0..1 | 0 | effect | 0 | 63.336 (0.191) | 60.503 (0.076) | 10000 | 1n 0d |  |
| `/vj/intensity` | 0..2 | 1 | effect | 0 | 124.683 (0.207) | 141.704 (0.112) | 3906.2 | 1n 0d |  |
| `/vj/level` | 0..1 | 0.5 | effect | 0 | 2.774 (0.161) | 3.447 (0.074) | 2064.8 | 6n 0d |  |
| `/vj/meteor` | 0..1 | 0 | effect | 2 | 0.559 (0.098) | 0.545 (0.058) | 29.2 | 0n 0d py |  |
| `/vj/moon` | 0..1 | 1 | effect | 4 | 19.428 (0.115) | 19.366 (0.030) | 647.7 | 3n 4d |  |
| `/vj/moon_phase` | 0..1 | 1 | effect | 3 | 29.140 (1.064) | 21.816 (0.032) | 678 | 1n 0d py |  |
| `/vj/nebula` | 0..1 | 1 | no effect | 3 | 0.604 (1.062) | 0.121 (0.032) | 3.8 | 1n 0d |  |
| `/vj/night` | 0..1 | 0 | effect | 0 | 117.549 (0.305) | 136.543 (0.155) | 881.5 | 1n 28d |  |
| `/vj/pyramids` | 0..1 | 1 | effect | 0 | 0.472 (0.155) | 0.128 (0.074) | 31.2 | 1n 4d |  |
| `/vj/shock` | 0..1.5 | 0 | effect | 2 | 46.685 (0.084) | 39.047 (0.017) | 2247.8 | 0n 0d py |  |
| `/vj/star_speed` | 0..10 | 0 | effect | 1 | 1.149 (0.080) | 1.268 (0.005) | 276.5 | 0n 0d py |  |
| `/vj/stars` | 0..1 | 1 | effect | 1 | 1.127 (0.062) | 1.365 (0.031) | 46.2 | 11n 0d |  |
| `/vj/strobe` | 0..1 | 0 | effect | 0 | 121.609 (0.156) | 152.417 (0.074) | 6578.9 | 1n 0d |  |
| `/vj/sun` | 0..1 | 1 | effect | 0 | 14.635 (0.128) | 17.593 (0.074) | 987.4 | 3n 1d |  |
| `/vj/water` | 0..1 | 1 | effect | 1 | 14.835 (0.069) | 19.394 (0.012) | 2058.5 | 1n 0d |  |

counts: {'effect': 33, 'no effect': 4}; noise floor {'mad': 1.0616, 'frac': 0.041536, 'bias': 0.3042}; defaults restored: True; state equals defaults: True; holds released: True

Columns: `cam` is the camera that showed the best effect (or the first tried, when none did). mad and bias are the largest cell value, the floor in brackets. `readers` are Attribute nodes (n) and drivers (d) found in the scene data; `py` marks a reader in Python.

## Island table

| control | range | default | verdict | cam | mad (floor) | bias (floor) | x floor | readers | note |
|---|---|---|---|---|---|---|---|---|---|
| `/vj/bass` | 0..1 | 0 | effect | 0 | 2.392 (0.304) | 3.186 (0.021) | 153.9 | 3n 0d |  |
| `/vj/beat` | 0..1 | 0 | effect | 0 | 15.867 (0.319) | 17.602 (0.135) | 130.4 | 0n 0d |  |
| `/vj/blend` | 0..2 | 1 | no effect | 3 | 0.237 (0.189) | 0.012 (0.004) | 2.9 | 0n 0d py | read only in Python by flight_rt.frame |
| `/vj/boost` | 0..1 | 0 | no effect | 6 | 0.593 (0.490) | 0.011 (0.015) | 1.5 | 0n 0d py | read only in Python by flight_rt.frame |
| `/vj/cam` | 0..6 | 0 | effect | 0 | 68.605 (0.350) | 49.579 (0.086) | 574.5 | 0n 0d |  |
| `/vj/cam_speed` | 0..4 | 1 | effect | 4 | 5.325 (0.204) | 1.855 (0.016) | 211.5 | 0n 16d |  |
| `/vj/eclipse` | 0..1 | 0 | no effect | 1 | 0.458 (0.529) | 0.033 (0.015) | 2.2 | 0n 0d py | read only in Python by star_system.sync |
| `/vj/energy` | 0..1 | 0.3 | no effect | 6 | 0.625 (0.446) | 0.014 (0.019) | 2.5 | 0n 0d py | a weak first effect did not repeat; read only in Python by flight_rt.frame |
| `/vj/flamingos` | 0..1 | 1 | effect | 1 | 0.364 (0.278) | 0.112 (0.036) | 3.1 | 0n 2d | weak, repeated |
| `/vj/flight` | 0..1 | 0 | no effect | 5 | 0.197 (0.266) | 0.013 (0.007) | 1.9 | 0n 0d py | read only in Python by flight_rt.frame |
| `/vj/fog` | 0..1 | 0.35 | effect | 0 | 35.269 (0.316) | 40.483 (0.074) | 544.1 | 1n 0d |  |
| `/vj/fog_beat` | 0..1 | 0.5 | effect | 0 | 12.033 (0.222) | 14.458 (0.089) | 162.1 | 1n 0d |  |
| `/vj/fog_glow` | 0..2 | 0.6 | effect | 0 | 22.248 (0.323) | 27.618 (0.171) | 161.9 | 1n 0d |  |
| `/vj/fog_height` | 1..60 | 25 | effect | 0 | 37.428 (0.286) | 41.470 (0.149) | 277.7 | 1n 0d |  |
| `/vj/fog_hue` | 0..1 | 0 | effect | 0 | 11.247 (0.323) | 17.068 (0.153) | 111.9 | 1n 0d |  |
| `/vj/fog_noise` | 0..1 | 0.6 | effect | 0 | 4.129 (0.336) | 3.162 (0.178) | 47.4 | 1n 0d |  |
| `/vj/fog_scale` | 10..1000 | 260 | effect | 0 | 6.201 (0.318) | 6.011 (0.183) | 63.8 | 1n 0d |  |
| `/vj/fog_speed` | 0..40 | 10 | effect | 0 | 1.065 (0.171) | 0.410 (0.020) | 22.9 | 1n 0d |  |
| `/vj/grid` | 0..1 | 1 | effect | 0 | 2.318 (0.381) | 3.029 (0.210) | 14.4 | 2n 0d |  |
| `/vj/grid_speed` | 0..4 | 0.6 | effect | 2 | 2.495 (0.309) | 0.029 (0.050) | 13.3 | 1n 0d |  |
| `/vj/haze` | 0..1 | 1 | effect | 0 | 2.977 (0.359) | 3.977 (0.095) | 42 | 1n 0d |  |
| `/vj/hit` | 0..1 | 0 | no effect | 5 | 0.238 (0.215) | 0.034 (0.048) | 1.4 | 0n 0d py | read only in Python by flight_rt.frame |
| `/vj/hue` | 0..1 | 0 | effect | 0 | 73.852 (0.410) | 79.893 (0.091) | 880.9 | 1n 0d |  |
| `/vj/intensity` | 0..2 | 1 | effect | 0 | 128.144 (0.402) | 164.669 (0.291) | 566.7 | 1n 0d |  |
| `/vj/level` | 0..1 | 0.5 | effect | 0 | 8.909 (0.317) | 10.318 (0.068) | 151.3 | 6n 0d |  |
| `/vj/meteor` | 0..1 | 0 | effect | 3 | 0.691 (0.339) | 0.516 (0.071) | 7.2 | 0n 0d py | weak, repeated |
| `/vj/moon` | 0..1 | 1 | effect | 0 | 13.612 (0.802) | 13.584 (0.207) | 65.6 | 1n 3d |  |
| `/vj/moon_phase` | 0..1 | 1 | effect | 3 | 14.500 (0.395) | 15.596 (0.093) | 167.9 | 1n 0d py |  |
| `/vj/nebula` | 0..1 | 1 | effect | 1 | 2.071 (0.735) | 1.817 (0.147) | 12.3 | 1n 0d |  |
| `/vj/night` | 0..1 | 0 | effect | 0 | 85.262 (0.378) | 104.821 (0.211) | 496.8 | 1n 3d |  |
| `/vj/pyramids` | 0..1 | 1 | effect | 2 | 3.861 (0.058) | 3.015 (0.009) | 705 | 0n 4d |  |
| `/vj/shock` | 0..1.5 | 0 | effect | 2 | 14.650 (0.057) | 5.553 (0.005) | 3059.8 | 0n 0d py |  |
| `/vj/star_speed` | 0..10 | 0 | no effect | 6 | 0.834 (1.029) | 0.070 (0.040) | 1.7 | 0n 0d py | read only in Python by star_system.sync |
| `/vj/stars` | 0..1 | 1 | effect | 0 | 5.548 (0.843) | 5.592 (0.259) | 21.6 | 3n 0d |  |
| `/vj/strobe` | 0..1 | 0 | effect | 0 | 126.692 (0.431) | 167.068 (0.210) | 795.9 | 1n 0d |  |
| `/vj/sun` | 0..1 | 1 | effect | 0 | 51.683 (0.378) | 64.703 (0.192) | 336.8 | 1n 1d |  |
| `/vj/water` | 0..1 | 1 | effect | 1 | 7.953 (0.289) | 3.573 (0.034) | 119.8 | 3n 0d |  |

counts: {'effect': 30, 'no effect': 7}; noise floor {'mad': 1.0293, 'frac': 0.038264, 'bias': 0.2335}; defaults restored: True; state equals defaults: True; holds released: True

The island's bridge row for `/vj/cam 12` in the full run read 10 (the bridge clamped floats only); it was fixed and rerun with `--only vj_cam` (6 of 6, `CAM_6`), and that result is the one in the JSON.

## Open bugs

1. **Flight and Energy controls have no reader** (`/vj/flight`, `/vj/boost`, `/vj/blend`; `/vj/hit` and `/vj/energy` on the island). `flight_rt` is never started by `synthwave_runtime.main()`. Owner: B2 (`blender/flight`).
2. **`/vj/nebula` shows on no camera of the planet** (night 1, `CAM_0` to `CAM_10`, 0.6 mad at 3.8x floor on the best). One Attribute node reads it (material `Nebula`). Look issue, B3.
3. **`/vj/hit` and `/vj/energy` on the planet show an effect on one camera each** (`CAM_3` 0.83 mad, `CAM_9` 0.90 mad) with no shader, driver or Python reader in the scene data. Treat as unconfirmed until B2 wires them.
4. **`/vj/eclipse` and `/vj/star_speed` do nothing on the island**: the island has no star system. The page still lists them. Not changed.
5. **Preconditions that are traps, not bugs**: `/vj/fog_hue` and `/vj/fog_glow` need dense fog at dusk to show; `/vj/nebula` and `/vj/moon` need night. They are in `PRECONDITIONS`.

## Contract cross-check

`feature_check.py` reads `osc/contract.json` (through `osc/contract.py`) and fails on every difference to the page's controls: a row without a control, a control without a row, a scene range, a default that is not the scene value of the wire default (half a percent of the range of slack), a trigger flag or trigger maximum that differs, an index that does not start at the wire minimum or ends above the wire maximum. Result on both scenes: 0 mismatches. Before the ranges were aligned (fog_height 0..60 against the property's 1..200, `vj_cam` 0..6 against the planet's 0..10, fog_scale minimum 0 against 10) it reported 5 in the planet run of B1.

Bridge, six messages of `docs/handover/osc-contract.md`, read back from the scene (expected = the contract's scene value of the wire value, kept inside the property's range):

Planet:

| message | property | expected | got | ok |
|---|---|---|---|---|
| `/vj/intensity 0.5` | vj_intensity | 1.0 | 1.0 | yes |
| `/vj/fog_height 0.42` | vj_fog_height | 25.78 | 25.78 | yes |
| `/vj/fog_scale 0.26` | vj_fog_scale | 267.4 | 267.4 | yes |
| `/vj/cam 12` | vj_cam | 10 | 10.0 | yes |
| `/vj/shock 1.4` | vj_shock | 1.4 | 1.4 | yes |
| `/vj/cam_auto 0` | none (ignored +1) | - | - | yes |

Island:

| message | property | expected | got | ok |
|---|---|---|---|---|
| `/vj/intensity 0.5` | vj_intensity | 1.0 | 1.0 | yes |
| `/vj/fog_height 0.42` | vj_fog_height | 25.78 | 25.78 | yes |
| `/vj/fog_scale 0.26` | vj_fog_scale | 267.4 | 267.4 | yes |
| `/vj/cam 12` | vj_cam | 6.0 | 6.0 | yes |
| `/vj/shock 1.4` | vj_shock | 1.4 | 1.4 | yes |
| `/vj/cam_auto 0` | none (ignored +1) | - | - | yes |

udp 9201 probe: 37 sent, 37 received, 37 applied, 0 errors on both scenes.

## How a control is judged

- State per control: defaults, clocks frozen by the runtime (`freeze`, `advance`, `quiesce` in `synthwave_runtime.py`), the preconditions of the one table `PRECONDITIONS` in `blender/scenes/synthwave_check.py` (night, fog, camera, clock time to step).
- Cells: min, default, middle and max (a trigger fires at 0.5, 1 and its max). The middle matters: `vj_hue` 0 and 1 are the same colour.
- Frame: the 640x360 Syphon preview (same composite as the Syphon texture), mean of 8 frames per cell.
- Numbers per cell against a baseline: mean absolute difference (mad, 0..255), share of pixels moved by more than 8, mean signed difference (bias). Noise floor: the largest difference among 3 untouched baselines per camera and state, and the default cell. An effect clears twice the floor and a minimum (mad 0.05, share 5e-4, bias 0.02). A cell far above the floor (10x) or two cells above it make an effect; a lone marginal cell does not. A weak effect is measured again on fresh baselines.
- A control with no effect on its cameras is tried on `CAM_0` to `CAM_10`, so a wrong camera does not read as dead. Triggers are fired with the clocks stepped (shock 1 s, meteor 0.4 s), and the runtime's own state (`rt_shock*_a`, `rt_met*_a`) is read to tell "not taken" from "not visible".
- The applied value is read back from the scene property (the camera name for `/vj/cam`). No readback failed.
- Noise: the viewport is not static. Untouched renders differ by 0.05 to 1.1 mad depending on the camera (grid wires, dither). A paused viewport was tried and is worse: frames are identical within a cell but differ by 1 to 1.9 mad between cells. Effects below about 0.1 mad cannot be seen by this check. Large "x floor" values come from cameras with a floor near 0.005.

## Syphon frame orientation (evidence only)

`python3 blender/review/syphon_orientation.py` (scene held still): the scene's own preview, flipped to top-down, has row luminance 177.9, 119.2, 62.2 from top to bottom (sky above, ground below). `magic/magicproj.py grab --app Blender --server CAM_OUT` returns the rows 68.5, 122.0, 178.5: reversed. Error against the preview 228.5 in the delivered order, 9.7 reversed. So the frame Blender publishes has row 0 at the bottom (the GL-origin texture, `FLIPPED = False` in `syphon_out.py`, commented there as what GL receivers such as Magic need). `grab()` reverses the rows only for `app == "Magic"` (`magicproj.py` line 1209, "Magic's frames arrive bottom-up"), so for Blender it prints the delivered bottom-up order. Which side flips: the grab tool's reading of Blender's frame, not a change in the sender. Whether Magic shows Blender's frame upright is not observed (Magic is the user's app and was not driven). That is B4's check.

## Not done

- Pixel differences in 640x360 cannot see effects below about 0.1 mad; the check says "no effect" for them.
- Fallback cameras are limited to `vj_cam` values; free views and the `CAM_SYS_*` cameras are not tried.
- No fps was recorded.
