# Godot Colossus Scene: frame-time table (context only)

One run of `make godot-fps` on 2026-11-11, Metal, Apple M1 Max, the real scene with both models, 1080p output with MetalFX temporal at 0.75. **Load 55 at the start, 20 at the end; `fps_trustworthy` false throughout. Read the table as context, not as fps.** The orchestrator reruns the target on an idle machine. The session was parked before a second run finished; the probe in the tree has two fixes this run did not have (listed under "What this run got wrong").

## What the table shows

Metal keeps the display link with vsync off and has no GPU timer (`viewport_get_measured_render_time_gpu` reads 0, the CPU side of the render 0.25 ms). A frame that fits in about 8.3 ms reads 8.3 ms whatever it costs, so the production rows only say that **the frame fits**. Two numbers go below the floor:

- the median again with the internal resolution at 2.0 times the output (4 times the pixels, bilinear), where the GPU is the limit and the time grows with the work: the "at 2x" column;
- a resolution sweep (`sweep`): far view, scale wide: 1.0x 8.25 ms, 1.25x 10.47, 1.5x 13.80; near view, close grip: 8.48, 9.41, 12.29. A quadratic in the scale through the 1.25x and 1.5x points puts the GPU time at the show's 0.75 scale at about **5 to 6 ms** (far 5.6, near 5.2), and 7.8 / 7.4 ms at 1.0x. This is an extrapolation of two points, not a measurement.

## Per director shot (20 s each, vsync off)

"far": the Wanderer at the Shrine, the long walk. "near": he hangs on the Colossus in a Climb. Draw calls and triangles are the colour and shadow passes together, median of one sample a second.

| Situation, shot | median ms | p95 ms | worst ms | draws | triangles | median at 2x pixels ms |
|---|---|---|---|---|---|---|
| far, scale wide | 8.25 | 9.11 | 40.69 | 71 | 321,600 | 22.90 |
| far, low hero | 8.37 | 8.74 | 11.89 | 111 | 523,368 | 29.64 |
| far, over-shoulder | 8.28 | 9.19 | 18.48 | 127 | 666,692 | 21.31 |
| far, close grip | 8.37 | 9.09 | 11.47 | 118 | 619,300 | 21.07 |
| far, aerial | 8.48 | 11.25 | 16.02 | 134 | 603,280 | 38.85 |
| near, scale wide | 8.16 | 9.27 | 10.68 | 159 | 950,228 | 12.69 |
| near, low hero | 8.16 | 9.30 | 10.12 | 142 | 968,076 | 10.61 |
| near, over-shoulder | 8.20 | 11.51 | 39.37 | 126 | 852,604 | 15.94 |
| near, close grip | 8.47 | 11.65 | 46.78 | 140 | 987,350 | 31.62 |
| near, aerial | 8.39 | 17.66 | 1004.19 | 150 | 891,152 | 35.60 |

## One Arc (vsync off) and the same Arc with vsync on

Approach with the Wanderer 60 m from the Colossus, Climb, Fall, Reset. Phase rows are a Phase's first 20 s.

| Phase | vsync off median / p95 / worst ms | vsync on median / p95 / worst ms | vsync on: frames over 16.7 ms (over 33.3 ms) of frames |
|---|---|---|---|
| Approach | 8.51 / 12.06 / 685.54 | 16.65 / 19.48 / 48.37 | 563 (17) of 1200 |
| Climb | 8.23 / 13.62 / 294.73 | 16.66 / 18.48 / 43.48 | 591 (10) of 1200 |
| Fall | 8.61 / 13.53 / 1004.66 | 16.65 / 18.59 / 52.04 | 271 (8) of 576 |
| Reset | 8.14 / 19.05 / 274.36 | 16.66 / 18.13 / 331.77 | 113 (3) of 231 |
| whole Arc | 8.44 / 13.40 / **1004.66** | 16.66 / 18.55 / **331.77** | 1626 (38) of 3388 |

With vsync on, half the frames land a little over 16.7 ms (p95 18.5 ms): the display tick, not work; frames over 33.3 ms are 1 %. `make godot-hitch` (the same Arc without the probe's extra work) reads worst 24 ms, all medians 16.7 ms, so the large worst values above are probe or load effects, see below.

## The three most expensive things in the frame

Each switched off once, alternating with the scene as it is (3 rounds, 150 frames), in two views. At the show's setting every difference is under 0.1 ms (hidden by the floor). At 2x pixels (4 times the work, so pixel-bound passes cost about 7 times what they do at the show's 0.75 scale):

| Feature off | far, scale wide | near, close grip | mean |
|---|---|---|---|
| SSIL | -5.25 ms | -5.47 | **-5.4** |
| SDFGI | -3.16 | -5.00 | **-4.1** |
| glow | -2.70 | -2.09 | **-2.4** |
| sun shadow | -2.58 | -1.61 | -2.1 |
| SSAO | -2.55 | -1.39 | -2.0 |
| fill light | -1.75 | -0.86 | -1.3 |
| distance fog | -1.76 | -0.29 | -1.0 |
| volumetric fog | -1.70 | -0.22 | -1.0 |

As is: 24.49 and 24.63 ms. The three most expensive: SSIL, SDFGI, glow (sun shadow and SSAO close behind). Volumetric fog, which the guidelines name first, is cheap here.

## What this run got wrong

- The 2.0x stress made the GPU time out three times ("timeout waiting for fence") and the stress left the output's upscaler on bilinear at 0.75 instead of MetalFX (scale and mode were set in the wrong order). The worst frames of 685, 1004 and 274 ms in the Arc and in `near, aerial` come from there. The probe in the tree sets the order right and stresses at 1.5x with a sweep to 2x; that version did not finish a run.
- Median at 2x pixels for the far and aerial rows swings (21 to 39 ms) with load; the ranking of the shots by it is not reliable.
- One run, at load 20 to 55.

Reproduce: `make godot-fps FPS_OUT=<json>` (about 10 minutes, refuses while Blender runs; `ARGS=shots|arc|vsync|sweep|features` for one part).
