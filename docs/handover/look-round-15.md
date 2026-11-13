# Look round 15: strobe and antialiasing (2026-11-13, stopped)

The user on the live Path Camera: "extremely strobey and glitchy, maybe lacks antialiasing a lot and the wireframe is too fine in general". Stopped in the middle by the user's change of direction (terrain as GPU displacement, no wireframe; [gpu-terrain.md](gpu-terrain.md)). The wireframe changes were dropped; the numbers and the antialiasing finding stay.

## The flicker number

`blender/review/flicker.py` (live Blender, `DN["fl_job"]`): per case, 90 consecutive Syphon frames (luminance, 1920x1080), clocks running, every control held at the show defaults unless the case says otherwise. Per pair of frames the mean absolute difference (0..255); its mean and 95th percentile; the toggle share: pixels that step more than 16 one way and then back over three frames (a strobe, not a motion); the mean difference on pairs with and without a block swap of the stream. "No pulse" keeps the runtime's idle pulse (rt_beat, which starts after 2 s without a change, so in every held run) at 0. Outputs in `blender/review/out/look15/` (git-ignored).

## Split by cause (before, round-3 build, held, load 57 to 84)

| case | day mean / p95 / toggles | night mean / p95 / toggles |
|---|---|---|
| camera still, no pulse | 0.05 / 0.06 / 0 | 0.45 / 0.52 / 0.00002 |
| still, no pulse, edges off (`/vj/grid` 0) | 0.05 / 0.07 / 0 | 0.01 / 0.02 / 0 |
| still, idle pulse | 1.12 / 1.87 / 0.0027 | 9.19 / 15.0 / 0.052 |
| slow path (`/vj/cam_speed` 0.25), no pulse | 1.37 / 1.86 / 0.0041 | 8.13 / 11.5 / 0.060 |
| slow path, edges off | 1.41 / 1.95 / 0.0044 | 0.28 / 0.48 / 0.0007 |
| show defaults (pulse, speed 1) | 2.30 / 3.18 / 0.0062 | 14.05 / 17.7 / 0.085 |
| unheld, Magic steering with music | | 15.4 / 25.9 / 0.076 (Magic set night) |

- Night: the 1 px edges are nearly all of it. With the camera still they shimmer (0.45 against 0.01 without them): the viewport's TAA jitter never settles, as the scene changes every frame. Moving, they crawl (8.1 against 0.28). The beat pulse makes them flash (9.2 with the camera still).
- Day: the beat accent (lens push, dip and roll, `energy.accent`) and the camera's own motion, about 1.1 and 1.4 each; no edges by day.
- LOD swaps: no measurable share (mean difference on swap pairs equal to the others, every case).
- Magic: about 10 % over the held show defaults.

## Antialiasing

- What runs: EEVEE, viewport TAA 4 samples with reprojection, render filter 1.5 px. The Syphon output is the viewport's camera frame copied 1:1 (1920x1079 of a 2832x1893 viewport region on this Mac). The scene's custom properties change every frame, so the viewport restarts its sampling every frame: the output is one jittered sample per frame, that is no antialiasing, and the jitter itself moves thin lines.
- Viewport TAA 1 (no jitter): no better (night show defaults 9.5 against 10.7 with the same edges).
- Supersampling by fitting the camera frame to the viewport (`view3d.view_center_camera`: 2828x1591 drawn, scaled to 1920x1080 on the way to Syphon, about 1.47x): night show defaults 10.7 to 2.6 with the same edge settings, slow path 7.3 to 1.2, day 2.0 to 1.6, toggles 7 % to 1.2 %. Cost: draw interval 55 to 73 ms at the same load (about 16), an untrustworthy load; on an idle machine it scales with the pixel count (2.2x the shaded pixels). The change is one call in `planet_runtime.show_camera_view` (embedded: needs a rebuild); kept for the GPU terrain rebuild.
- Variants of the edges tried live and dropped with the wireframe (fade from 12 to 24 px: the net vanishes, edge share 0.0001 to 0.024; fade 6 to 12 px with a quarter of the beat pulse: net visible, share 0.014 to 0.12, flicker 10.7).
- After set, on a build with the fitted view, fade 6 to 12, edges 1.5 px on the output and a quarter of the pulse (dropped since), under load 34 to 198: night show defaults 14.05 to 4.72 (toggles 0.085 to 0.035), night slow 8.13 to 2.18, day show defaults 2.30 to 1.65, Magic unheld 15.4 to 4.2.

## Left

- The day's beat accent: `energy.BEAT_LENS` 0.02 and `BEAT_TILT` 1 degree at a full pulse shake the whole frame on every beat (day still with pulse 1.12 against 0.05); not changed.
- The pyramids' edges flash with the beat (glow 2.6 + 7 x beat, capstone 2.2 + 4 x beat in `build_planet`); not changed.
