# Perf pass on the island scene (synthwave_pyramids.blend), stopped early

Stopped on request (the planet replaces the island). Nothing kept or applied: build_world.py, scenes/*.py and the .blend are unchanged. Blender exited around 12:46 to 12:56 during the last run. There is no crash report and the cause is unknown.

Setup: M1 Max, Blender 5.2.3, drawn fps = Syphon sender frames/s. Beat sim on (`shock_every` 4), `vj_fog` 0.65, flamingos on, nebula on. OSC `vj_cam`/`vj_night`/`vj_fog`/`vj_hue` held during runs. Each cell: 1.2 s settle, 3 s measure; 8 to 30 s settle after a lever change.
Scripts: /private/tmp/claude-501/-Users-abossard-Desktop-projects-swift-vj/4908f8b8-1390-45f2-bfb5-48a373a9d58c/scratchpad/perf/ (harness.py = levers, matrix.py = states x cams runner, grab.py = full-res Syphon frame to PNG, *.json = raw results).

## Baseline, drawn fps per camera (CAM_0..CAM_6)

| state | 0 | 1 | 2 | 3 | 4 | 5 | 6 | mean |
|---|---|---|---|---|---|---|---|---|
| day (night 0) | 18.3 | 15.6 | 24.9 | 18.6 | 15.3 | 22.6 | 16.2 | 18.8 |
| twilight (0.5) | 19.4 | 15.0 | 25.3 | 19.6 | 22.5 | 24.6 | 15.3 | 20.2 |
| night (1) | 17.6 | 13.8 | 24.6 | 17.0 | 15.3 | 22.6 | 16.8 | 18.2 |

## Levers, mean fps of CAM_0/1/4/6, base measured in the same run

| lever | state | base | with lever | visual |
|---|---|---|---|---|
| Sea hidden (upper bound) | day | 15.8 | 47.5 | n/a. The sea is about 2/3 of the frame time |
| Sea `displacement_method` BUMP (no vertex displacement) | day | 15.4 | 24.3 | changes the look: no geometric waves or shock heave |
| `render.use_border` 0..1 (render only the camera frame, region is 2832x1830) | day | 15.8 | 20.7 | not checked side by side. Likely identical apart from bloom at the frame edge |
| same | night | 16.5 | 24.8 | same |
| `WATER_RES` 700 to 350 | day | 15.4 | 20.0 | not checked |
| Warped sea grid 350, 15 m at centre to 70 m at edge (x' = x(a+(1-a)\|x/H\|^4)) | day | 14.3* | 19.5* | not checked. *Run contaminated by a 2nd Blender |
| Sea Bump without the wave/shock height | day | 15.4 | 20.2 | changes the look (wave shading lost) |
| Viewport compositor off | day | 15.8 | 19.3 | loses bloom |
| World off (upper bound) | day | 15.8 | 19.2 | n/a. Sky shading per pixel (2 voronoi, noise detail 5-7) |
| Glare quality Low | day | 15.4 | 16.1 | within noise |
| Sun corona / sun / moon hidden | day | 15.8 | 17.2 / 16.9 / 16.4 | upper bounds, small |
| Nebula hidden | night | 16.5 | 17.3 | small |
| No gain: fog bypass (fog march is cheap; FOG_STEPS is not a lever), volumetric samples 32, tile 16, world probe 128, world sun extraction off, Land_Mirror hidden, flamingos hidden, runtime handler off, terrain DITHERED, terrain/sea DITHERED | | | | |

## Findings for the planet scene
- Vertex displacement of a dense, heavy-shader grid is the dominant cost: the sea's 490k vertices × wave + 8 shock evaluations per vertex. Keep displaced grids coarse, or use LOD around the cameras.
- A Bump node driven by heavy height math is evaluated about 3x per pixel. Feed it only cheap terms.
- Render only the camera frame (`render.use_border` 0..1 in camera view): +30% day, +50% night, no scene change.
- `preview_pixel_size` AUTO on this Retina screen equals pixel size 2 (AUTO 15.8, pixel 2: 16.9, pixel 1: 7.9 fps). The viewport renders at about 960x540, and Syphon gets that upscaled to 1920x1080.
- The second Blender of the planet session halves these numbers while it runs. Benchmark with only one Blender open.
