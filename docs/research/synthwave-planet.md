# A procedural planet for the synthwave VJ scene

Question: can a whole procedural planet, built in Geometry Nodes, replace the flat island of the synthwave pyramids scene (`blender/scenes/synthwave_pyramids.blend`) at real-time VJ frame rates, with all of the scene's features kept?

- Researched 2026-11-04, with the scene-perf session (performance levers) and the live show setup (Magic over OSC, Syphon out).
- Host: Apple M1 Max, Blender 5.2.3 LTS, Metal, EEVEE.
- Labels: **Fact** (read in Blender or a file), **Measured** (local run, see [Reproduce](#reproduce)), **Inference**, **Recommendation**.

## Answer

- **Recommendation:** run the show on `scenes/synthwave_planet.blend`. It is the island scene with its ground replaced by a 16 km Geometry Nodes planet. It keeps every island feature:
  - OSC bridge, web page and Syphon sender;
  - ray-marched fog bank, shockwaves and meteors;
  - flamingo flight, sun, moon and nebula.
- **Fact:** it adds the following:
  - pyramid groups across the whole planet;
  - flamingo flocks wherever shallows lie next to pyramids, all flying off at dusk;
  - reflections of every instance in the sea;
  - a sky that turns with each shot;
  - four shots across the planet (CAM_7..CAM_10);
  - a fixed, balanced seed.
- **Measured:** live, same conditions as the island baseline (rendered, viewport region 2832x1893, Syphon on, day), see [Live](#live-the-official-scene-with-the-planet) for the full table.
  - Island: 15.3 to 24.9 fps per camera.
  - First planet graft: 17.5 to 55 fps.
  - With the scene-perf levers (render border, shader dedupe): mean 47.7 fps by day.
  - Feature-complete graft: 25 to 34 fps on most cameras, about 20 on the river mouth (CAM_8).
  - Triangles: 1.24 M on the island, 0.3 M on the planet.
- **Recommendation:** keep the LOD anchor on camera cuts. A cut rebuilds the LOD in 0.1 to 0.3 s once. Rebuilding it every frame drops playback to 7 to 9 fps.
- **Recommendation:** the next performance work is per pixel and per cut, listed under [Next steps](#next-steps).

## What was built

All in `blender/scenes/planet_proto/`:

- `build_planet.py` builds the planet. It runs in two modes:
  - **Standalone:** writes `planet_proto.blend`, a self-contained prototype with its own ported shaders and a volume fog box.
  - **Graft (`--graft`):** opens the island scene, replaces its ground with the planet and saves `synthwave_planet.blend` next to it. That file is generated and, like the island `.blend`, not tracked. The island file is opened read-only, and its hash is unchanged after a graft.
- `planet_runtime.py` is a text block embedded in the generated scenes. It:
  - moves the LOD anchor and turns the sky frame on camera cuts;
  - writes `rt_space` (camera altitude);
  - raises the web page's camera range to every `CAM_N`;
  - sets the 3D view to rendered camera view on load;
  - runs the clocks only when the island runtime is absent.
- `bench_fps.py` measures playback fps in a GUI Blender: camera view, full-area 3D view, viewport redraws counted by a draw handler.

### Planet, all Geometry Nodes

- **Fact:** radius 16 km, north pole at the island's origin. The island's valley sits at the pole, with the same meander (`valley_x`). Its floor lies near sea level and runs north into a bay about 1.7 km away. Mountains flank it, and sun, pyramids and sea keep the island's composition.
- **Fact:** one seed (`Seed` on `Planet_Hydro`, default 6) moves every noise, so the planet is always the same. Seed 6 scored best for balance over seeds 0..80:
  - 5 separate seas, the largest holding half the water;
  - land spread evenly (octant balance 0.76);
  - lakes 4.7%, mountains 13% of the land, 119 rivers and 742 pyramid groups, scored with the earlier lake fill. With the exact fill below, lakes cover 1.8% of the sphere and there are 135 rivers;
  - 440 m mountains framing the valley.
- **Fact:** elevation is one GN group (`PL_Elevation`): continents (fBm, 7 km), ridged mountains (1.25 km) masked inland, and hills. Land, water, props and hydrology all sample it, so they agree.
- **Fact:** water is tunable and connected (`PL_Hydrology` on the hidden object `Planet_Hydro`, evaluated once on load):
  - Sea level is the `Water` quantile of the elevation (Sort Elements plus Sample Index on a 40,962-vertex icosphere). `Water` 0.40 gives **Measured:** 40.0% ocean.
  - Shortest Edge Paths drains every land vertex to the ocean along low ground, with edge cost = length x (1 + (height / 45 m)^2).
  - Pointer jumping along that drainage tree (10 rounds in a Repeat Zone) gives each vertex the highest ground on its way to the sea. That is an upper bound only: one path's highest point overfills where another way out is lower. **Measured:** 933 of 1,942 lake vertices were false, up to 205 m above their real spill point, and showed as flat water plateaus in the mountains.
  - An exact depression fill (Planchon-Darboux) follows: each vertex relaxes to the highest of its own height and its lowest neighbour's fill, 24 rounds in a Repeat Zone. **Measured:** it matches a priority-flood fill exactly after 16 rounds. Lakes form where the fill holds water (`Lake Depth` 4 m minimum).
  - No lakes form in the mountain ranges (`Mountain` mask 0.1 or more). Their ridges are finer than the 300 m hydrology grid, so a pit in the grid drains through a valley the grid cannot see. Those lakes stood up to 120 m above the fine terrain.
  - Water levels are flat per hydrology triangle: the level of its water corners, carried across the whole triangle. Where two water bodies at different levels share a triangle, the lower one wins, because interpolating between them tilted water over dry land.
  - Edge Paths to Selection from sparse springs gives a river network. Rivers merge where they meet and run through lakes into the ocean. They are resampled every 30 m, smoothed and meandered by noise.
  - River surfaces sit 0.8 m or more under the fine terrain on dry land and keep the lake level across lakes. Water shows only where a river cuts a channel. The bed is carved 1.2 m plus 6% of the river's width deep. Banks rise at most 0.3 m per metre, so rivers cut V-shaped valleys instead of cliffs.
  - Rivers are a 1 m wide ribbon mesh, sampled with Sample Nearest Surface, so level, width and flow interpolate along the river. A nearest-point lookup stepped the level every 30 m into terraces with sawtooth edges.
- **Fact:** level of detail uses cube-sphere patches (6 faces x 32 x 32 patches):
  - Each patch is a grid of 2^level cells, instanced per patch point and realized. The level falls by one each time the distance from the `LOD_Anchor` to the patch's nearest point doubles. Near the camera the cells are about 6 m (`Max Level` 7, within about 200 m), then 12 m within about 400 m.
  - Patches past the anchor's horizon (plus 650 m mountains) are deleted before instancing.
  - Border vertices snap onto the lattice of their edge's level, using a Sample Index of the same grid. Both patches along an edge then trace one polyline at any level difference. **Measured:** no cracks in any still.
- **Fact:** one patch tree builds land and water:
  - The water surface sits at the local water level: sea, lake or river.
  - Water faces with no wet corner are deleted.
  - Along coasts the ocean's first hydrology ring keeps the sea flat, so the coastline is where the terrain meets it.
  - A thin surf line glows where the water runs out, pulsing with the beat.
  - The land within 6 km of the anchor is mirrored radially about sea level (radius R - h) for reflections.
- **Fact:** props are scattered on a fixed icosphere, so they never move with the LOD:
  - `Planet_Sites`: pyramid groups on dry flat lowland across the whole planet. Static, evaluated once.
  - `Props`: palm groves near water, within 5 km of the anchor.
  - `Flock_Birds` (graft): flock spots in shallows within 1.5 km of any pyramid, within 5 km of the anchor. After each cut the runtime copies them into the island's `Flamingos` mesh. Its own `Flamingo Flock` flight, whose climb and turns now follow each bird's local up, animates them, so every flock takes off into the sunset.
  - `PL_Reflect` mirrors every instance (pyramids, palms, flamingos, flying ones too) about the sea surface under it, with one matrix per instance.
  - `/vj/pyramids` and `/vj/flamingos` act in the shader through GPU displacement, so a VJ control never re-evaluates geometry.
- **Fact:** a sphere 700 m under the sea draws the sky gradient mirrored about the local surface, plus the striped sun's and the moon's reflections. Water shows a reflection where the mirrored land ends, and the planet never looks hollow.
- **Fact:** an additive shell 2.5 km above the sea glows at the limb when the camera is high (`rt_space`).

### Graft into the official scene

- **Fact:** `--graft` keeps from `synthwave_pyramids.blend`:
  - the runtime and OSC bridge text blocks, which start the web page, the Syphon sender, shockwaves, meteors and the flamingo flight clock;
  - the shared shader groups (`VJ_Sky`, `VJ_SkyBase`, `VJ_SunDir`, `VJ_Fog`, `VJ_Color`, `VJ_Phase`, `VJ_Meteor`);
  - sun, corona, moon, nebula, the four pyramids and the flamingos;
  - render settings, bloom compositor and all `vj_*` values.
  The planet's materials call those groups, so a later change to fog, sky or colour in the island scene shows up on the planet after a rebuild.
- **Fact:** look changes requested for the planet show:
  - **Real sky:** `VJ_SkyBase` is rebuilt. By day it is an even pastel blue, paler toward the horizon, with a tight warm glow around the sun. The synthwave sunset gradient appears only at twilight (`vj_night` around 0.25 to 0.75), and the night is near black. `VJ_Sky` draws stars only in the dark. The pink ground now stands clear of the sky.
  - **No hue rotation:** `VJ_Color` no longer rotates the hue (`vj_hue` has no effect), because colour effects live in Magic. Intensity and strobe stay.
- **Fact:** the graft adapts the island's groups to the sphere instead of copying them:
  - **Fog:** `VJ_Fog` takes surface and camera heights as altitude over the sea sphere. It used world z, so the fog bank vanished past about 1 km.
  - **Sky:** `VJ_SunDir`, `VJ_SkyBase`, `VJ_Sky` and the haze colour turn with the shot's local up (`VJ_Frame`, written on every cut). Sun, corona, moon and nebula ride on `Sky_Frame`, so horizons are right anywhere on the planet.
  - **Sun and moon:** they set at the shot's horizon plane, not at world z = 0.
  - **From space:** `VJ_Sky` folds its lower half up, so no sea horizon shows behind the planet.
- **Fact:** it removes `Terrain`, `Sea` and `Sea_Far`. It also:
  - keeps `Land_Mirror` for the island's own pyramids only;
  - drops the pyramids onto the plaza;
  - pushes sun and corona to 150 km and the moon to 120 km at the same angular size, so the orbit shot keeps them far and in scale;
  - adds render border (0..1) and runs the scene-perf session's `shader_dedupe.dedupe_all()`.
- **Fact:** it rebuilds CAM_0..CAM_6 with the island's roles (wide valley, river, pyramid hero, moon tilt, flyover loop, pyramid orbit, orbit of the whole planet). It adds CAM_7..CAM_10 3.5 to 9 km from the pole: a flock on a lake, a river mouth, a far pyramid group and a coast pass. Every camera target tracks the planet centre, so horizons stay level.
- **Measured:** live, the grafted file starts its OSC bridge (udp 9201, Magic connected), web page (9210, 30 controls, cameras 0..10) and Syphon sender (`failed: false`).

## Measurements

### A/B at 1920x1080, one Blender only

`bench_fps.py`, GUI Blender `--factory-startup -Y`, built-in 120 Hz display, 3D view full area, region 1920x1080 px, rendered, compositor on, 10 s per case after shader compilation. Scene `preview_pixel_size` is AUTO in both files. On this Retina screen that renders at pixel size 2. The prototype here is the standalone layout before the graft work.

| View | Island copy (12:13 save): camera, fps, tris | Planet prototype: camera, fps, tris |
|---|---|---|
| Ground, wide toward the sun | CAM_0, 24.6, 1,235,404 | CAM_0, 41.8, 82,368 |
| Pyramid hero | | CAM_2, 47.5, 125,234 |
| Flyover | CAM_4, 23.1, 1,235,404 | CAM_4, 47.5, 131,810 |
| Orbit (island: high 360 orbit; planet: whole planet) | CAM_6, 22.6, 1,235,404 | CAM_6, 42.5, 91,804 |
| Flyover, LOD anchor on the camera every frame | | CAM_4, 9.2, 158,016 |

- **Measured:** a second Blender halves the live instance's fps (15-23 to 4-12 fps). Benchmark with one Blender only.

### Live, the official scene with the planet

Drawn fps reported by the scene's own web page (Syphon frames per second). Viewport region 2832x1893, rendered, day, `vj_cam` held against OSC. The island rows are the scene-perf session's (beat sim with a shockwave every 4 beats, `vj_fog` 0.65); the planet rows are mine with Magic driving the rest.

| Version | 0 | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|---|
| Island | 18.3 | 15.6 | 24.9 | 18.6 | 15.3 | 22.6 | 16.2 |
| Planet, first graft | 17.5 | 40 | 53 | 55 | 27 | 44 | 28.5 |

- **Measured (scene-perf session, first graft plus my water fixes):**
  - Render border plus shader dedupe raised the mean of CAM_0..6 from 30.3 to 47.7 fps by day, 34.2 to 50.7 at twilight and 33.2 to 41.9 at night.
  - CAM_0 went 17.2 → 45.4. Both changes are pixel-identical in full-resolution Syphon grabs.
- **Measured:** the two water shader changes gave rough gains of CAM_4 27 → 40, CAM_6 28.5 → 33 and CAM_0 17.5 → 21, read through a harness collision. The changes: the water's Bump gets only the ripples, and the backdrop uses `VJ_SkyBase` instead of `VJ_Sky`.
- **Measured:** feature-complete graft (all features in this document, seed 6), same setup with Magic driving: settled readings per camera after a cut. The first reading after each cut is lower (18 to 25 fps), because of the cut rebuild.

| Camera | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fps | 31 | 30 | 32 | 30 | 29 | 29 | 34 | 25 | 20 | 23-32 | 27 |

  - Before the flock-link fix the same scene ran 13 to 24 fps.
  - **Inference:** compared with the first graft plus the perf levers (mean 47.7), these features cost the most: the finer LOD near the camera (6 m cells), the fog bank active over the whole planet, and the per-instance reflections. The next perf pass measures each one.

### Geometry Nodes cost

- **Measured:** with the anchor fixed, a frame costs 0.1 to 0.3 ms on the CPU. Nothing re-evaluates, including the runtime's `scene.update_tag()` every frame.
- **Measured:** a camera cut rebuilds land, water, props and flock spots in 0.1 to 0.3 s, once.
- **Measured:** with the anchor on the camera every frame: 50 to 80 ms per frame headless, 6.7 to 9.2 fps in the GUI.
- **Fact:** the hydrology and the planet-wide pyramid sites have no anchor input, so they evaluate on load only.
- **Measured:** the flock spot scatter (`Flock_Birds`, 22 to 36 ms) re-evaluated on every frame. The scene dropped to 13 to 24 fps, and to about 60 with the flamingos hidden. Two changes:
  - the flock rule reads a static copy of the island pyramids' positions, since the runtime moves the live pyramids with every shockwave;
  - the runtime copies the spots into the flamingo mesh after each cut, so the per-frame flight does not depend on the scatter.
- **Measured (scene-perf session):** the remaining per-frame cost was a name clash. The island runtime treats every object named `Pyramid_*` as a pyramid and moves it each frame with the shockwave. The spots copy was named `Pyramid_Spots`, so the flock scatter that reads it re-evaluated every frame. Renamed to `Spots_Pyramids`, drawn fps went day CAM_0 26 → 45, CAM_3 30 → 57 and CAM_8 19 → 26, and night CAM_0 26 → 43.
  - **Recommendation:** the runtime should select its pyramids by the Pyramids collection rather than by name prefix.

## Limits

### Horizon curvature vs the camera cuts

- **Fact:** at R = 16 km the horizon is 0.5 km away from 8 m (CAM_2), 1.0 km from 32 m, 1.5 km from 70 m and 2.1 km from 140 m. The sphere drops 31 m at 1 km, 125 m at 2 km and 281 m at 3 km.
- **Inference:** ground shots look like a small planet, with a curved sea horizon 2 to 5 degrees below eye level. That suits the stylized look, but the far views differ from the island's.
- **Fact:** a cut used to cost a 0.24 to 0.41 s freeze while land and water rebuilt under the moved anchor. Each camera now has its own land and water set, built on load (three along each flight path, the nearest is used). A cut switches sets with `visible_camera` plus `hide_set`.
  - **Measured:** a cut's worst frame is 45 to 118 ms (typically 50 to 70 ms; props and flock spots still follow the anchor).
  - **Measured:** sets hidden only from the camera still cost about a third of the frame (CAM_8 35 vs 48 fps); `hide_viewport` would re-evaluate them on a cut, `hide_set` does not.
- **Fact:** the flyover loop is 22 km long, with the anchor fixed where the cut happened. The far side of the loop runs on coarser patches.

### Water reflections via the mirrored land

- **Fact:** the flat island mirrors land, sun and moon about z = 0 with a collection instance scaled -1 in z. That transform does not exist for a sphere.
- **Fact:** the planet mirrors each land vertex radially about sea level (R - h) inside its GN tree, and each instance about the sea surface under it.
- **Inference:** each point reflects about the sea surface right under it. That matches a flat mirror locally and drifts at grazing angles over curvature, which is not visible at show distances.
- **Fact:** there is one mirror level, sea level. Water up to 3 m above it behaves like the sea. Higher lakes and rivers are opaque and reflect the sky gradient in their own shader, with no land reflection. Ocean beyond 6 km of the anchor reflects the sky through the backdrop sphere.
- **Fact:** the waterline, reworked after close-ups showed teeth and stepped cuts:
  - **Cause:** water that dropped under the ground at the next vertex left a sloped sliver in every shore cell, and lakes were cut along hydrology triangle edges.
  - **Flat water:** surfaces now stay flat past their shore (sea and lakes across their whole hydrology triangles, rivers for 30 m past the bank) under the rising ground.
  - **Neon line:** the terrain draws a thin line exactly where it meets its water, from its exact height above the water per pixel. It laps up and down with the swell and pulses with beat and bass, pink by day and cyan at night.
  - **Shallow bed:** the bed shows, wet and darkening, through the first metre of water, and waves and shock heave fade out in shallow water.
  - **Continuous level:** the water level is the highest of lake level, sea level and 15 m under the ground, with the river level blended over its channel. Nothing interpolated across a triangle switches between them, so neither the water surface nor the land's water cut zigzags.
- **Fact:** a second rework, after the user found the waterline still not good:
  - **River bed 0 m deep:** the bank term was clamped at the water level, so the carved bed never won and the river bed lay exactly at the water surface. The water z-fought the land, and the lapping neon line showed as blobs across the whole channel.
  - **Flat patches on rivers:** the water is BLENDED with transparency overlap, so its faces did not depth-test each other. Water diving under a bank, seen from below through the cut-away river bed, was drawn over the river. Turning overlap off and culling back faces removes the patches. **Measured** later, live at CAM_8 by day: the front water stays, only its look changes (the sea shows the shore's mirrored land instead of a second ripple-ring layer), and drawn fps rises 29.9 → 39.2. Both settings ship with the quality pass.
- **Fact:** with water flat past its shore under the rising ground, the waterline is therefore where the water plane meets the terrain triangles: about 6 m within 200 m of the camera, 12 m within 400 m, coarser further out. Rivers narrower than a cell vanish in the distance.

### Fog layer on a sphere

- **Fact:** the graft's fog bank measures altitude over the sphere along each view ray, so it fills valleys anywhere. The ray between two samples is straight, while the sphere curves under it, which underestimates fog by up to 31 m of depth at 2 km.
- **Fact:** the fog does not show from orbit (the bank is thin, and from 38 km up the view rays cross it almost vertically). The atmosphere shell carries the look from space.
- **Fact:** a real EEVEE volume was tried live instead of the shader bank (CAM_2, M1 Max, drawn fps), and is not shipped:
  - A ball around the whole planet does not work: with Fast intersection EEVEE showed no fog, and with Accurate it veiled the whole frame, sky included, even with density forced to 0.
  - A 12 km box under the camera works as a domain. With the island's volume settings (64 slices, 1..8000 m) it costs 59 -> 38 to 46 fps, and 32 slices cost almost nothing (57 to 60). The 8 km range must stay: the night nebula is an 18 x 18 x 3 km volume about 3.7 km up.
  - With the bank dropped, the volume is barely visible at `vj_fog` 0.5, and at 1.0 it veils the sky. A mask that gives fog only to view rays ending on the ground (slope against the camera's own up and its horizon dip) did not hold in the froxel pass: in cold single tests, the camera-relative position read as if the froxels near the camera faced the opposite way. Fading density out within 30 to 80 m of the camera helped but left streaks in the sky.
  - **Inference:** a clean sky with real volume fog needs that mask working. The attempt is kept as a patch outside the repo.
- **Fact:** the grey band on the horizon was the island sky's painted sea. VJ_Sky draws a sea below its level horizon, and the planet's real horizon dips 2 to 5 degrees lower from shot heights, so a band of it showed between them. VJ_Sky now folds its lower half up at all times, not only from space. The real sea and the backdrop cover everything below the real horizon.

### Jitter (measured with a viewport draw recorder)

- **Measured:** frame pacing within a shot is steady (sd about 1 ms). The jitter came from:
  - shockwave camera shake: about ±1 m at 7 to 10 Hz on every fresh wave, at every camera (a global term in the island runtime, now removed). The planet cameras now shake 0.1 m at 3 to 4 Hz while a front passes;
  - the cut freeze above.
- Wires get a soft edge (three widths averaged) and fade toward their average where the ground is seen edge-on.

### Star system and look (quality pass)

- The star system (docs/research/synthwave-star-system.md) runs in the graft: the island's `VJ_SunDir` and `VJ_Phase` read the runtime's sun, the stars turn about +x, the moon sits on its 50 km orbit lit by the real sun with the planet's umbra in red, CAM_3 and CAM_9 track their body, CAM_6 orbits at 80 km.
- **Fact:** the first star rotation rewired the island sky's shared view-direction node, so `VJ_SkyBase` saw the rotated star vector and every sunset was one flat colour. Only the star layers turn now.
- Sunset: a poster gradient from the visible (dipped) horizon, hot orange under the sun through pink and magenta to navy; the setting sun keeps its stripes above the horizon. Night: the neon grid on a black sky with a faint violet horizon glow. Orbit: latitude and longitude lines every 10° on land and sea.
- Water: the ripple normal comes from the ripple noise's own colour instead of a Bump (three noise evaluations fewer per pixel), and the water hazes toward the horizon sky instead of running the fog group.

### Less flat terrain (user request: "the flat areas are much much too wide")

- Ranges cover about half the land (was 30%), narrower and more numerous, ringed by ridged foothills. All land away from the coast rolls with 70 m hills 1 km across and 12 m knolls 220 m across, and the camera valley's floor is 640 m wide instead of 1.1 km, with knolls that only rise from it.
- **Measured** (dry land within 2.5 km of each ground camera with a slope under 5°): CAM_0 30% → 12%, CAM_1 44% → 13%, CAM_2/3/5 29% → 14%, CAM_7 36% → 12%, CAM_9 25% → 13%.
- **Fact:** the 300 m hydrology grid must resolve every dip. With 140 m knolls able to dip, its flat lake levels stood as slabs and walls on the slopes, so hills are 1 km across and the knolls only rise. Lakes form only up to 40 m (`LAKE_MAX_H`): 0.3% of the planet, 44 rivers.
- **Fact:** a pyramid group's three pyramids spread up to 240 m but stood at the group's single height, so on rolling ground the far ones floated. Each pyramid now stands on its own ground and only where that ground is dry.

### Visual check, round 1 (docs/research/synthwave-visual-check.md)

- Volume fog in the graft: a box under the shot (on `Sky_Frame`), hidden at `vj_fog` 0, replacing the island's shader fog bank.
- **Fact:** the fog's checker pattern in thick fog was EEVEE's 8 px froxels. With 4 px froxels and a 4.5 km volume range (the fog box's reach), the pattern is gone at about 1 fps. The night nebula looks the same at that range.
- **Fact:** the volume's `Incoming` carries no view direction, so the old sky mask did nothing and thick fog veiled the whole sky. The mask now uses the ray from the camera position (`rt_cam_*`) and fades the fog out between 1° and 6° above level, so it hugs the horizon. The fog also opens around the camera out to the shot's subject (camera property `fog_clear`, written to `rt_fog_clear`), so at `vj_fog` 1 the subject still reads and the fog stands behind it.
- **Fact:** CAM_10's "surf blotches" were the land's neon waterline, which lit every flat within 0.3 m of its water level. The line's width is now measured across the slope (and stays within 1.5 m of the water), so a flat gets a line along its edge.
- **Fact:** a view ray dipping less than about 17° crosses the transparent sea without reaching the deep reflection backdrop (700 m down) and leaves the sea sphere again 1 to 7 km out. It met the far water's underside (pale patches on near water). Water faces all point outward, so the water now culls back faces. The backdrop moved from 700 m down (facing out) to just under the sea (facing in): a ray leaves the sea sphere at the same angle to its surface as it went in, so the backdrop where it leaves shows the reflection for that angle, for every ray. Two backdrops showed a curved seam across the near water.
- **Fact:** the cyan blotches on night water (pink by day) were the wave crests: the four wave trains add up to tens-of-metres patches above the old crest threshold. Crests now light only the tips.
- **Fact:** the "glassy bowls" (CAM_1, CAM_8) were rivers above sea level, which are opaque and reflect the sky themselves: at half strength even seen from above, a raised pool read as bright glass. Their reflection now follows Fresnel (dark from above, bright at grazing angles).
- The sea's shallow tint is gone (a broad tint over every sandbank).
- Sun and moon set on the visible horizon (dipped from the camera height) instead of the level plane, so a setting body no longer hangs a few degrees above the ground. The sky folds at the visible horizon too: folded at the level plane, its horizon glow stood as a band 7 to 17° over the ground from 130 to 750 m up.
- **Fact:** the site pyramids floated 15 to 29 m over the ground in every shot (user screenshot). Their instance points sat exactly on the drawn ground, but the Cone node already puts its base at z = 0, and `unit_pyramid` lifted it by half its depth again, as if it were centred. That also put the glowing capstone over the upper half. The shockwave hop and the LOD were not the cause: the island's own pyramids sit within 0.6 m of the drawn ground, and CAM_9's nearest site pyramids had their instance points within 0.1 m of it.
- Distant grid lines and wires fade to a dim, even glow where they would fall closer than a few pixels (by distance, slant and LOD cell), which removes the moire. Palm groves keep 90 m from a fixed camera. The fog's top rolls with its noise instead of ending on one height or one view angle.
- Terrain facets are shaded per face and gentler; a noise snapped to 40 m cubes shaded square blocks across the faces on near mountains.
- Cameras:
  - CAM_1 skims 9 m over its river's water instead of standing on a bank 52 m above a pool;
  - CAM_8 aims at sea level past the river mouth (its aim had landed on a hill), from 40 m upstream: rivers here meet the sea from 15 to 75 m up, and from 240 m upstream a raised pool filled the foreground;
  - CAM_10 runs 300 m out over open water past a shore (the hydrology's coast is too ragged for a straight pass along it);
  - CAM_4 flies high enough that every hill 3 km ahead sits below the frame centre, with 8 land sets along its 22 km loop instead of 3;
  - CAM_9 slides its frame down (lens shift) while the sun is high, so its pyramids stay in frame.
- Cuts: land, water, props and the flamingo flock exist per camera set (the flock baked into a mesh), and the cut runs before the new shot's first frame is evaluated (`depsgraph_update_pre`). Flights switch to the nearest set as they fly.
- **Measured** (cut frame, 44 cuts, Godot running): worst 90 ms → 66 ms; CAM_3 and CAM_9 aim error on the first frame after a cut 1.7° and 15.7° → 0°.

### Visual check, rounds 2 and 3

- Fog (round 2 review: a slab with a ruler-straight top over the horizon, hot pink at every time):
  - Density follows the height above the local valley floor, not the altitude. A 768 x 384 map of the lowest ground around each point (the hydrology's heights, a 3-step minimum, then smoothed) is baked at build time and read by direction in the volume shader. The scale height rolls with a 1.8 km noise and the top billows with the fog noise, so ridges stand out of it as islands.
  - The fog is lit and has almost no light of its own: white by day, the sky's colours at sunset (warm toward the sun, violet in the shade), dark navy at night. Sun and moon lights that only reach the volume give the halos and a cool sheen on its top. Each pyramid capstone within 1.5 km of a ground camera carries a point light, so at night the fog glows warm round the tops. At night the grid adds a faint violet glow at the fog's foot.
  - **Fact:** EEVEE's froxels within about 150 m of the camera do not hold the sky fade, which drew a woven dither over CAM_1's water and sky. Each shot keeps its fog out of that zone (`fog_clear`). The water draws the same fog itself, since EEVEE draws no volume over blended surfaces.
- Water has no light of its own at night (the neon ripple lines and wave crests are gone). Shockwaves move the ground and water but add no glow. The sun's glint is soft and shows on a low sun only, and the moon's glint is soft.
- **Fact:** the sea bed's mirror copy (the land mirrored about sea level for the reflections) stands over the sea as hills as high as the sea is deep. Every build-time ground probe hit it: CAM_7 found no water behind its flock and stood on the shore (the round 2 "bowl lip"), and CAM_4 took the sea for hills. The probes now skip mirror faces and stop 3 km under the sea: a probe that found nothing went on through the planet and once put CAM_7 on its far side.
- **Fact:** the "white specks" on CAM_10's sea were mirrored pyramid groups. Like the land, a view ray dipping under the near sea travels on underground and met their reflections kilometres away. Mirrored pyramids now show only within 1.8 km of the camera, like the land's copy.
- CAM_7 stands in open water 75 m behind a flock, with water all the way to it and little wet flat in view (a flat just above the water reflects the sky but not the mirrored hills, so it reads as a glassy sheet). It looks toward the sunset sun's real bearing within 70° (local north missed it by up to 90° away from the pole). The flocks on offer have open water behind them only 50° off that bearing, so the sun stays out of frame.
- CAM_4 aims where the ground fills 40% of the frame: the skyline per bearing across the frame, from where the camera is when it looks at that point. CAM_3 holds the sky over the skyline toward the pyramids (ground 40%). Its spot, at the pyramids' level, has the lowest horizon across the sunset sun's disc (with eclipse 1 it holds the moon over the sun, which sits on the horizon, and a near slope half-hid it), then across the night moon's.
- **Fact:** CAM_3's night moon centre is 6° under the horizon from the pyramids' valley (its top edge 1° over it), and the valley walls stand 10° and more toward it. From the pyramids' level no spot sees it clear: only from 360 m up is the horizon low enough, and from there CAM_3 looks down. At night with eclipse 0 it holds the sky over the pyramids, the moon behind the ridge.
- A capstone lamp sits at the top centre of its pyramid's bounding box, and only where every ground shot within 3 km sees it (17 of 23). At its highest corner, or behind a ridge, its halo hung in the night fog as an orb.
- **Measured** (cut frame, 84 cuts, Godot not running): on the final build at most 58.6 ms. On the build before the lamp fix, one sweep had four day cuts over 70 ms (75 to 213 ms) and a re-run one (161 ms, into CAM_4's set after 4 minutes unseen). Sunset and night stayed under 55 ms in every sweep.
- Grid lines and wires keep the light of their world width: drawn at least a pixel wide, a line dims as it widens. Where they fade into their average glow, the floor matches the lines over it. A fixed dim average drew a dark band with a hard edge in front of CAM_0's horizon.
- **Fact:** the dark 3 to 8 px border on system-view grabs comes from the Syphon sender (`scenes/syphon_out.py`, outside the repo). It projects the camera frame's corners half a metre in front of a camera 100 km out, in single precision, and its crop misses by a few pixels. Projected 10 km out along the same rays, the border is gone (tested live in memory, the file is unchanged).

### Visual check, round 4

- Fog (round 3 review: a smooth vertical wash with no top, which swallowed the pyramids):
  - A layer with a billowing top, not an exponential. It is full up to half its top and thins to the top, with a thin haze over it. The top is `vj_fog_height` (25 m) at `/vj/fog` 1, 0.7 of that at 0.5. It rolls between 0.4 and 1.6 of that over 1 to 2 km and billows by a fifth of it, so ridges and pyramid tops stand out as islands. The water's analytic fog uses the same profile.
  - **Fact:** the valley floor took the minimum over 3 rings of the 300 m hydrology grid. A river 20 m up a narrow valley then got the lowland's floor 900 m off and stood over the fog (CAM_1 f1). It is now 1 ring, smoothed over 2.
  - At night the grid's glow on the fog stays over land within 1.5 km, at a third of its strength. Over the sea and summed toward the horizon it was a self-lit violet band. The fog's own colour is darker (albedo 0.06), and the lamps are twice as bright.
- Night ground: a grid line or wire dims with the square of its crowding (wires from 16 px cells down), and night wires are at 60%. Seen edge-on on a near bank, wires 12 px apart filled the land with teal (CAM_7, CAM_8). The pole's flat grid shows on flat ground only: on sloped banks it drew stray magenta streaks.
- Night water reflects the violet horizon glow in its ripple bands and the real stars, so it reads as dark water instead of a black slab.
- An eclipse shrinks the sun to its sunset size (0.18 rad, the corona with it). By day its 0.30 rad disc showed round the 0.23 rad moon as a thick striped ring. Both parts sit in two drivers: in one the expression passed Blender's 256-character limit and the driver went invalid.
- CAM_3 releases its hold on the moon only once the moon clears the real skyline toward it (14° from its spot), not the level horizon. Halfway, it framed a wire hillside with the moon behind it. In an eclipse the moon has no magenta rim.
- CAM_7 searches every flock cluster near the far pyramid groups. It takes the first spot in open water with the sunset sun in frame and water all the way to the flock. Its sunset was 80% plain sky and water with the sun 51° off, after the flock had flown. Wet flats just above the water reflect at half strength, since the water beside them also mirrors the dark hills.
- Capstone lamps light the fog only in the shots that see them (a bit per `/vj/cam` in an energy driver), and are off in space.
- At sunset a pink band lies low in the sky all round, most away from the sun: there CAM_1's sky was flat violet.
- From space the moon's earthshine is a quarter as bright: it lit its night side as an even grey disc.
- **Fact:** the CAM_6 lighting agrees. Seen from CAM_6, the planet's phase angle is 97° (half lit from the right) and the moon's 60° (gibbous, lit from the right): the moon sits 55 km off to the side.
- Stars (user request: "100% realistic from NASA pictures"): NASA SVS Deep Star Maps 2020 (svs.gsfc.nasa.gov/4851, public domain, NASA/Goddard Space Flight Center Scientific Visualization Studio) in place of every procedural star layer:
  - **Fact:** a 3D voronoi cut by the unit sphere showed its lattice as rings of stars, the island's star layer was mirrored below the horizon, and it pulsed with the beat.
  - The map's north celestial pole lies on the spin axis +x, so the sky turns about it with `rt_star_ang`. The camera area sits on the equator, both celestial poles on its horizon. A black point (0.0012, the map's median is 0.0016) and a gain of 2.5 make a dark-site photo: the empty sky black, the Milky Way visible, bright stars blooming. Linear filtering: stars stay put as the camera drifts.
  - **Measured** (8k against 16k, same shots): with the 8k map Blender's physical footprint was 4.8 GB (2.5 GB of it graphics), with the 16k 7.1 GB (3.4 GB). At 1920 x 1080 a 16k map pixel is smaller than a screen pixel, so most of its stars fell between the samples: the sky looked emptier and dimmer. Drawn fps could not be told apart: the machine ran a load average of 50 to 75 after a reboot.
  - The maps are not in the repo (`starmaps/`, ignored): `--stars 16k` builds with the larger one.
- **Fact:** M1 outliers. In this round's sweeps, cuts into space were the slowest every time (55 to 65 ms, one at 87). Two night cuts stalled for 811 and 488 ms, the 488 ms one in the middle of a shot, not on its cut. Ten more cuts at the same setting stayed under 37 ms. During the sweeps other processes ran: Microsoft Defender and FSEvents (scanning the 450 grab files just written, 70 to 120% CPU), and an unrelated Python job (80%). A sweep taken while they ran had 10 cuts over 70 ms, with whole stretches of 70 to 140 ms frames.

### Visual check, round 5

- **The same planet near and far (S8):**
  - From orbit, land and sea keep the ground's palette: magenta and violet land, violet sea, lit by the real sun with a soft terminator and dark violet on the night side. Grey-tan rock and a navy ocean read as another planet.
  - The land draws the sea itself from orbit, per pixel from its height over its water level. The water mesh drops dry faces whole, which drew the coasts stair-stepped, so past halfway to space it steps aside.
  - Pyramids from orbit are dim violet stone. Black, they read as holes from 10 km.
  - Proof cameras pull out over the pyramids, 60° down along CAM_0's view, at 1 km and 10 km (CAM_0's land set) and at 50 km and 165 km (CAM_6's whole planet).
- **Star map (S6):**
  - Two lookups of the same texels. A plate carree map's `u` jumps from 1 to 0 at its edge, and the texture filter took that jump for a huge footprint: a line of smeared stars. The second lookup runs on past 1 there (the map repeats) and jumps in the map's middle, where the first one is used.
  - Within 14 to 18° of each celestial pole, caps in an orthographic azimuthal projection (made once from the map, `starmaps/*_caps.exr`). The plate carree pinch drew a radial starburst of streaked stars around the pole (CAM_4 at night).
- **Wires (G2, LOD seams):** a triangle lattice of fixed spacing (24 m) along the equator and meridians of the spin axis, not the LOD mesh's edges. The mesh's cells halved at every LOD ring as square patch borders, and its long thin faces drew needle streaks (CAM_4 p75).
- **Fog:**
  - The billows on the layer's top are as deep as the layer, with 500 m swells, and the fog lies in banks about 700 m across with clear gaps. At a quarter of that depth, the top read as a ruler-straight band from low shots.
  - At night the moon's light on it is at 0.25 (from 0.8), and the grid's glow at 0.03. Brighter, they read as self-lit violet bands.
  - Shots standing in the layer by the sea (CAM_7, CAM_8, CAM_10) take half the fog; CAM_4, 650 m over it, takes 2.5 times.
- **Night:**
  - Palm crowns go dark: only the grid, the wires and the capstones glow (T-night).
  - The neon waterline shows by day and at dusk only. At night it read as a dashed jagged cyan shore.
  - The pole's flat grid draws only on ground flatter than 4°.
- **Sun, moon and eclipse:**
  - The striped sun shows its stripes only toward sunset. By day it is a disc: striped with sky in the gaps, it read as a salmon card. Its reflection follows.
  - In an eclipse the corona grows 0.10 rad past the sun. At 1.12 times the sun it hid behind the 0.23 rad moon, leaving a bare black disc at sunset.
  - The moon has no magenta rim at night.
- **Water:**
  - Flats just above the water are wet sand, the ground darkened with a faint sky sheen. With the full sky in them they read as a pale raised ledge.
  - The sun's glitter shows only within a few degrees of the horizon, and its mirrored image only down to 5° under it. Nearer, both stood as a lone golden blob on the near water at sunset.
- **Syphon sender:** `syphon_out.py` (now in the repo) projects the camera frame's corners 10 km out along their rays. At the view frame's own half metre, single precision far from the origin put the crop a few pixels off: dark strips along the frame's edges.
- **Flamingo flight in the visual check:** sunset and night grabs are taken about 3 s into the flock's take-off. It leaves as the sun sets and is gone within 30 s, which left CAM_7 empty in every settled sunset and night grab.

### The planet from far away (S9, user: "planet doesn't look so good from distance")

- From about 9 km up a smooth globe draws the planet: an icosphere at sea level (655 k vertices, smooth normals) that evaluates the ground's own surface (PL_Surface) at every vertex. It carries height, water level, rivers (300 m wide, like a map), the pyramid sites, and a relief normal from the height exaggerated 3 times. The ground's LOD patches step aside there; near the ground the globe scales to nothing. From orbit the patches, the far side at the lowest level, drew a ragged, faceted limb and blotchy colours.
- The globe's look: land magenta to violet by height with lighter pink peaks, a deep teal-indigo sea with teal shallows, coasts per pixel from the height against the water level, a soft sun glint. The night side is dark, with the neon lattice as a faint fine pattern and the pyramid sites as city lights.
- Atmosphere: a 500 m shell with the sphere's own normal and a sharp rim, lavender by day with a pink-orange band along the terminator. A 1.2 km shell and a soft rim over flat faces stood off the limb as crescents and laid a sheen over the day side.
- The moon's maps are pre-filtered once (a 2k colour map, the height map blurred), next to the star map. The 8k map and the relief's height samples aliased into moire craters at a few hundred pixels.
- **Measured:** the planet file loads and plays in 24 s with the globe (655 k vertices evaluated at load); the file stays at 1.8 MB.
- Later, from the user's review: the globe's rivers draw as cyan threads (in the shallow-sea teal they did not stand out), its shallows are a crisp cyan fringe over the first 8 m, and the flat lowlands (a fifth of the land) get a fine violet mottling. The moon's maps blend into their polar cap's mean from 65 deg (its texture poles drew radial streaks), and its relief and crater self-shadow are softer (hard black blotches when it filled the frame).
- **The handover to the globe** (Flight rule FL2): across 8 to 12 km the ground's patches and the globe trade pixels by a fixed noise per screen pixel against the viewer's progress through the band, a dissolve with no flicker. Both draw one shared orbit look there (land palette by height, sea by depth, the real sun), and the globe's own extras (300 m rivers, exaggerated relief, the night lattice and the city lights) grow in over 12 to 20 km. Switched at one height, the planet jumped from the sunlit patches to the night-side globe with its lights. **Measured** (altitude sweep 6 to 13 km in 125 m steps, mean frame-to-frame difference): the largest step was 2.5 times the median at night before; after, 1.2 times at night, 1.4 by day, 1.6 at sunset, where the sky darkening into space adds to it.
  - The night lattice (900 m) and the pyramid sites' lights belong to that shared look, so both sides draw them: on the globe alone they vanished across the band and came back above it. The ground's patches carry the sites' lights as a vertex value (`pl_city`, the same 140 m radius as the globe's). Re-swept: the largest step is 1.2 times the median at night, 1.4 by day, 1.5 at sunset.
  - The pale water from 6 to 8 km up is the distance haze, not a second water colour: with `/vj/haze` 0 it is the same deep teal as from 10 km.
- **Atmosphere** (user: "the atmosphere is too weird"): no lit shell. The shell is only a canvas past the limb, and the glow comes from each view ray's closest approach to the planet's centre: brightest where the ray grazes the limb, fading over about two pixels outward and one inward at any distance, so it is concentric by construction. Pale pink-lavender on the sun side, none at night, a warm band only where the terminator meets the limb.
- **Star contrast** (user: "a bit too bright, it needs more contrast"): a black point of 0.002 over the faint-star field and a square curve on luminance (colours kept). **Measured** (darkest 100 px sky patch, 1920 x 1080): CAM_SYS night 15/255 to 3/255, CAM_6 8 to 3, CAM_9 and the orbit view 3 to 3; the sky's median over the top 40% of the frame 33 to 5 (CAM_SYS) and 20 to 3 (CAM_9). The Milky Way is subtle (user's choice).

### Wireframe only (user: "the violet lines and the wireframe are overkill / ONLY the wireframe please")

- One line layer on the ground: the 24 m triangle wireframe. The pole's planar 22 m square grid is gone (night, flat ground, warped by the shock rings): over the wires it read as a second layer of violet lines.
- The wires are cyan at every time of day, bluer on the peaks. They were magenta to violet by day, and cyan to violet to magenta with height at night.
- The wires cover all ground, flats, hills and mountains, at every distance, in one style (user: "Wireframe can cover everything", "In the same style"): one cyan, about a pixel wide, a slight glow. They drew on ground flatter than 14° and within 3.5 km only, bluer on the peaks. The lattice is projected along the local up, so on a slope its cells stretch along the fall line by 1/cos(slope) (15% at 30°). Every line is about a pixel wide on screen whatever its direction and slope: each of the three line families takes its width from its coordinate's gradient along the surface over that gradient's foreshortening from the camera. At one width in lattice units, the lines across the view thinned away on a low view of flat ground, and the plaza's triangles read as a coarse square grid beside the hills' fine triangles (CAM_5, round 7). By day the wires are drawn over the ground in their cyan, not added to it: added, they washed out to pale pink on sunlit hills. They stay lines while a cell is over about 3 px on screen; past that by day they fade into their mean glow, at night they fade out, so the far floor stays a dark silhouette.
- The pink neon waterline is gone too. It was one of the magenta lines, and it traced the land's triangles at the water as a zigzag (CAM_1).
- From orbit the night side's faint 900 m lattice is the wireframe's cyan, over land and sea (S8, S9). On land only, the night side broke into lattice patches with holes where the seas are (CAM_6). The fog's glow from below at night is cyan too.
- Unchanged: the pyramid outlines. Shock waves still lift the ground and the sea, and no longer warp any lines.

### Visual check, round 5 review

- **Night water** (T-night: water only reflects): the water's own deep violet (0.022 blue) and a violet "horizon glow" with a 30% floor lit every river and the sea as a flat glowing slab. At night the deep colour is near black, and the glow shows only where the water mirrors the horizon. **Measured** (near water, 960 x 540 at (480,520)): CAM_1 night sRGB (36,15,63) to (3,1,11), CAM_8 (39,17,67) to (2,0,11); the far water keeps the horizon's violet in its ripples. Stars reflect at 0.7 (from 0.5), and the mirrored moon sits at the real moon (the island scene's own moon path put a pale disc in the water where the sky had none).
- **Eclipsed moon:** in the planet's umbra no sunlight reaches it, so it is an even copper glow on its rock colour over the whole disc. The sunlit shading tinted copper left the far half black from the side (CAM_SYS night e1).
- **CAM_SYS:** 300 km out at 40 mm, 25° off the line behind the planet from the sun. At 125 km the moon's orbit needed 16 to 19 mm, which stretched the moon at the frame edge into an oval. CAM_SYS_MOON sits on the moon's side toward the sun, so the moon shows its lit limb.
- **Fact:** in space the solar eclipse is aligned for the camera area (the pole), as the star system's parallax viewpoint moves from the camera to the pole over `rt_space`. From CAM_SYS the moon then sits beside the planet in the sun's direction, not over the sun.
- **Coasts:** sea level reaches 3 hydrology rings (about 800 m) past the last sea vertex. It ended one ring out, and where the fine terrain dips under 0 beyond that, the coast ran along 260 m hydrology triangle edges, stair-stepped from orbit (CAM_6, S8).
- **Orbit look:** the night lattice is 600 m cells at 0.07 over land and sea (900 m at 0.12 on land only read as bold patches with holes); the sites' lights are small points (cubed); shaded slopes keep 30% (12% went grey-brown); relief exaggerated 2 times (from 3); the sun glint at 0.15 (0.35 burnt white). Inside the handover band the relief shading flattens to 40%: the patches and the globe shade from normals of different resolution, and the per-pixel dissolve showed that as speckle at 10 km.
- **Atmosphere:** the warm band where the terminator meets the limb is dimmer and fades twice as fast past the limb. As bright as the day side, its tail stood out over the dark night limb as "ears".
- **Pyramids' shadows** (G5): the island's four pyramids cast a sun shadow on the terrain, the hull of the base and the apex cast along the sun, with a 2 m soft edge. Every surface is emission only, so from 1 km up they stood on an even plane and read as floating.
- **Fog:** gaps between the banks at 40% (25% left f1 shots in a gap looking like f0). CAM_1 takes 3.5 times the fog (at 2 its f1 showed only on the far water), CAM_7 0.8 (from 0.5). CAM_9 f1 now shows the layer round the pyramids.
- **Sun:** the island sun's large spots darken its disc by 8% (from 30%). They read as a dark blotch on the sun (CAM_0 at sunset). Grabbed with the flock landed and in flight, the blotch was the same, so it was not the flamingos.
- **Sea by day** (CAM_10): it reflects at least 30% of the sky (from 50%), and its own colour by day is a deep teal-indigo, the sea's colour from orbit. Half the pastel sky over every metre of sea read as a washed-out grey. CAM_10 aims 60 m off the shore and 45 m down (from 150 m and 20 m), where over 60% of the frame was blank sky and open sea.
- **Fog by day** takes the sky's light as a faint emission: the sun is the only light reaching the volume, so away from it the fog went a muddy mauve-grey over the sea (CAM_10 f1). CAM_7 takes 1.2 times the fog.
- **The fog's top:** the fade that keeps rays steeper than about 11° clear (the stars stay sharp) applies to the haze over the layer only. On the whole density it cut a camera's own layer off at its eye level, a ruler-straight fog top (CAM_5 f1).
- **Moon poles:** each moon map has two polar caps in an azimuthal projection, drawn from 62° latitude, like the star map's. The cap is blurred the same in every direction, 1.5 cap pixels (about 0.1°) from 16° off the pole and 10 at the pole: the maps' polar data vary along longitude far more than along latitude, which the caps drew as spokes converging on the pole. Its magenta rim shows by day only (at sunset too it read as a rim, CAM_4).
- **Capstone lamps** at 120 kW (from 300 kW): their light spread through the night haze as a warm wash over half the frame, which read as the fog glowing on its own (CAM_5, CAM_2 at night f1).
- **An eclipsed moon's image on the water** is dim copper, with no glitter: pale, it lay on the night sea as a bright band (CAM_10 night e1).
- **Round 6 review:**
  - The globe's rivers draw by day only, about 200 m wide at 70% over the land: mixed in with their unlit colour at night they cut the night lattice as black strokes, and solid they read as cyan capsules.
  - Inside the handover band the globe is displaced to the ground's true height (by the viewer's altitude, a smooth sphere again from 20 km): the patches' mountains stood over the sea-level sphere, and their per-pixel dissolve drew a ragged limb and land edge at 10 km.
  - The fog floor is weighted over the 4 nearest hydrology vertices: the nearest one alone made the fog's top step in 260 m terraces (CAM_4 f1). The sky's light in the day fog is 0.3 (0.5 burnt thick near fog into a white slab, CAM_2), the moon's 0.12 (0.25 smeared the night haze purple over the far sky from CAM_4).
  - At night the water's violet horizon reflection is at 0.04 blue (0.07 read as cloud-like blotches, CAM_1). The moon's caps blur strongly out to 27° from the pole, and its crater self-shadow is at 10 (from 20). CAM_4 aims for 48% ground (42% left 65% blank sky).
  - **Fact:** the bright magenta line along CAM_10's waterline at sunset is drawn by the land itself: it stays with the water, the mirror object, the land's rim light or its dusk glow hidden. Not found yet.
- **Fact:** the fix for CAM_0's faint fog stipple, volume tiles of 2 px instead of 4, costs 7.9 ms per frame (20.4 to 28.3 ms at f1, CAM_0 by day, a 2832 x 1893 viewport), so it is not applied.
- **CAM_4** clears every hill in its view by 170 m (from 120 m) and aims for 42% ground (from 45%): one near ridge filled 55% of the frame (p25, p50).
- **Not defects:** no dark rectangle in the night sky on fresh grabs (CAM_3, CAM_4 night): the sky's median is 2/255 across x 0 to 780 above y 170, rising smoothly to 3 to 6 toward the right edge. The dark limb beside CAM_4's night moon is its night side: a full moon here stays at least 34° from opposition so it passes beside the planet's shadow (star system check 11c), which leaves 8 to 12% of its disc dark. The "flamingos on dry ground" over the plaza are palm groves seen from above. No seam in the star map from space (column medians 4/255 over x 820 to 860, the largest step between columns 1/255 in the whole frame); the smudge near the south celestial pole is where the Magellanic Clouds are. In CAM_7 and CAM_8 at night e1 the moon is not in frame; the white point is a star, at the same place at e0.

### System view (user request: "make it look like a serious star/universe simulation when zoomed out")

- **Fact:** zoomed out in a free view the scene broke apart:
  - one modelled cap on a black ball: LOD sets dropped every patch past their anchor's horizon;
  - a moon cut into a dome: its visible-horizon cut;
  - an elliptical sun: the striped sun is a card that faces the On-Air Camera;
  - an offset ring: a 2.5 km atmosphere shell;
  - a purple smear: the night nebula volume and the island sky's purple milky way.
- Planet: no horizon culling. Patch points past the anchor's horizon (centres and edge midpoints, so neighbours agree) take the lowest level, so every set is a whole sphere.
  - **Measured** on CAM_1's set: the far side adds about 5 k one-quad patches (21 k of its 297 k vertices).
  - Kept at their distance levels instead, the far side made cuts into the shot about 50 ms slower.
- **Fact:** the island sky has no notion of space: from far out, its horizon glow ringed the planet's limb as a purple halo. In space, it is fed the zenith everywhere.
- Shading follows the viewer's own altitude: shading point + incoming × view distance, so any view works, including a free viewport. The runtime also takes a free view's position for `rt_cam_*` and `rt_space`.
  - From space, land and sea turn into a simulation: rock and dust, and a deep-blue ocean with the sun's glint. Both are lit by the real sun with a soft terminator.
  - The neon grid and the distance haze fade out, and the globe lines turn faint.
- The moon keeps no horizon cut: the whole planet occludes it. Its magenta rim fades out in space.
- The atmosphere is a 1.2 km limb shell: blue on the day side, warm along the terminator.
- The striped sun card hides above 0.5 `rt_space`. VJ_Sky draws the real sun from space: a small round disc with glare.
- The sky has stars of varied brightness and colour, a dense faint field and a faint white milky way, all turning with `rt_star_ang`. The island's purple layers and the nebula volume are gone.
- CAM_SYS sits 165 km out on the spin axis, so the terminator always faces it side-on and the moon's orbit stays in frame. It and four system views (front, back, above, behind the moon) share CAM_6's whole-planet set.

## Next steps

- **Recommendation:** a full perf pass on the feature-complete scene with the scene-perf harness. First items:
  - an upper bound with `Water` hidden: the water at 12 m cells carries wave and shock displacement;
  - the cut rebuild time (0.1 to 0.3 s);
  - `Detail` and `Max Level` for land and water;
  - the 1.4 k pyramid instances, which double with their reflections.
- **Recommendation:** a day-only world, switched by the runtime, adds about 11% by day (scene-perf, pixel-identical at `vj_night` 0).

## Reproduce

Run Blender only when no other Blender is running.

- Standalone prototype: `blender -b --factory-startup --python blender/scenes/planet_proto/build_planet.py [-- --seed N]`
- Graft: `blender -b --factory-startup -Y blender/scenes/synthwave_pyramids.blend --python blender/scenes/planet_proto/build_planet.py -- --graft`. It writes `scenes/synthwave_planet.blend` and leaves the island file untouched.
- Show: open `scenes/synthwave_planet.blend` with Auto Run allowed, as the island before.
- fps in a GUI Blender: `blender --factory-startup -Y --window-geometry 0 0 960 540 FILE.blend --python blender/scenes/planet_proto/bench_fps.py -- --out result.json --cases CAM_0,CAM_4,CAM_4:follow,CAM_6`. A case `CAM:MODE` sets the camera's LOD mode: `surface`, `follow` or `orbit`.
- fps live: hold `vj_cam` (`POST /api/hold {"keys":["vj_cam"],"on":true}`), set it (`POST /api/set {"vj_cam": N}`) and read `fps` from `GET /api/state`.
