# GPU terrain: displacement on a camera-centred grid (design and test, 2026-11-14)

The user (2026-11-13): "Displacement on the GPU and lets ditch the wireframe". The streamed terrain (`lod_scene`, CDLOD nodes baked on the CPU through PL_Surface) is replaced by one fixed mesh round the camera whose vertices the material puts on the Planet, from a height map, with no detail levels to switch. This note is the design, the prototype that tests it beside the stream, and the numbers. Nothing of the stream is removed yet.

## Design

**The grid: a geometry clipmap.** LEVELS square rings of N x N cells round the camera, the cell doubling per ring (prototype: 8 rings of 128 cells, 3 m to 384 m, the outer ring 24.6 km off). Each ring is snapped to two of its own cells, so every vertex sits on a fixed point of its ring's lattice: the ground does not swim as the camera moves, a vertex only appears or leaves at a ring's edge. Over a ring's outer band (70 to 92 % of its half side) its heights blend to the next ring's lattice (bilinear over its even vertices), so the rings meet with no crack and a vertex that leaves a ring was already where the coarser ring draws it: no pop, no level switch anywhere. The mesh never changes (about 120 k vertices, 230 k triangles); per frame only the camera's two map coordinates are written.

**Where the grid lives: the height map's own longitude and latitude.** The map is equirectangular, in a frame turned so the pyramids' valley lies on its equator (its poles 90 degrees from the show). Grid and map share the coordinates, so the vertex's map lookup is direct and a lattice point is a fixed texel position. Near the map's poles the cells narrow in longitude: fine within about 60 degrees (16 km) of the valley; a whole-planet show needs a cube-map version (the clearance map's cube faces, the grid on the camera's face: a jump when the camera crosses a face edge, or a ring per face).

**Displacement in EEVEE.** Material output Displacement, method Displacement Only, a Vector Displacement node in object space: vertex = Planet centre + direction(lon, lat) x (R + height). EEVEE moves the vertices in the vertex stage (image textures and view-layer attributes work there). Two things the stream did not need:
- Bounds: the mesh's own vertices sit at the origin; eight loose corner vertices give it bounds round the whole Planet, so it is never culled.
- Normals: displacement leaves the flat mesh's normals, and the Terrain shades itself from the Geometry node's Normal (emission only). The prototype uses True Normal, the displaced triangle's: correct relief, faceted per triangle. Smooth normals need the map's gradient in the shader (three more lookups).

**The height source.** PL_Surface itself, probed once into the map (land height R, water level G, m over R) as a float image (packed). Prototype: 8192 x 4096, 12.3 m per texel at the valley, baked in about 70 s (2 M points per chunk through the clearance map's probe group), cached under `~/Library/Caches/swiftvj-flight`, 188 MB compressed. Below the texel size the grid only interpolates: the 3 m cells near the camera show 12 m detail. Options for real near detail (open):
- a regional map round the show's places (8192^2 over 24 km: 3 m texels, about 4 minutes to bake);
- PL_Surface's fine octaves as shader noise on top of the map (the noise nodes exist as shader nodes; the hydro inputs stay in the map);
- half-float precision is enough for heights (0.25 to 0.5 m steps at 730 m); the prototype keeps float.

**Water, lakes, rivers.** A second grid with a copy of the Sea material, displaced to the map's water level where there is water and 2 m under the land elsewhere. Rivers narrower than about 2 texels (25 m) are lost at 12 m; the stream had them from PL_Surface at its cell size.

**Pyramids, sites, props.** Unchanged objects; they stand on PL_Surface's height, the grid's ground under them is the map's (within a texel's interpolation: up to a few metres off on slopes). The flock and the palms scatter round LOD_Anchor on their own; the capstone lamps read the clearance map: none of them read the stream.

**Far field and space.** The outer ring reaches 24.6 km; above about 10 km the globe (`Planet_Globe`, its band 8 to 12 km) carries the Planet as before. The stream fades into the globe in that band through the same Terrain material, which the GPU copy keeps.

**What breaks or goes.**
- The night edges (the Wireframe node is cut out of the GPU copy), `/vj/grid` and its pulse on the Planet, and the start check's `edge_guard` (it probes for those edges): to remove with the stream.
- Site lights (`pl_city`, a geometry attribute the stream's GN wrote): 0 in the copy; they need a map channel or a shader distance to the sites.
- Water flow (`pl_flow`): 0 in the copy: no flowing rivers.
- The mirror copy of the land (`mirror` attribute): 0.
- `lod_scene`, `lod_stream`, its verify checks (5a to 5f), the `LOD` objects and their caches, `path_edges.py`, `net_regularity.py`: obsolete once the GPU terrain carries the show.

**Cost.** GPU: about 120 k vertices with 6 map lookups each (the vertex, the 4 coarse-lattice corners, plus the surface's water lookup per pixel), against the stream's up to 351 slots of baked meshes. CPU: nothing per frame but two scene properties; the stream baked nodes and swapped blocks every frame (its build budget). Memory: the map, 512 MB as a float RGBA image in RAM and on the GPU (half float: 256 MB; R and G only would halve it again, Blender has no two-channel float image).

## The prototype

`blender/scenes/planet_proto/gpu_terrain.py`, loaded from disk into the live planet Blender (no rebuild):

    import importlib.util, sys; spec = importlib.util.spec_from_file_location("gpu_terrain", "<abs>/blender/scenes/planet_proto/gpu_terrain.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); sys.modules["gpu_terrain"] = mod
    bpy.app.driver_namespace["gpu_terrain"] = mod; mod.build(); mod.switch(True)     # switch(False): the stream back

`build()` bakes or loads the map, makes the image `GT_Map`, the grids `GT_Land` and `GT_Water` and their materials `Terrain GPU` and `Sea GPU`, and adds a frame handler that writes `rt_gt_lam`, `rt_gt_phi`. `switch(True)` pauses the stream and makes its update a no-op.

Two faults found on the way: the map image came out blank when its colour space was set after its pixels (a generated image is regenerated), and the land shaded as one flat slate until the normals came from True Normal.

## The test

`blender/review/terrain_test_flight.py` (restored from round 3's deletion, adapted to the Path Camera): the 90 s flight of the terrain test, now from the river target toward the pyramids (CAM_1 is gone), every control held against Magic at the runtime's defaults, the Path Camera's step replaced by the script. Per stage: frame time, the lower third's cell on screen, flicker (mean luminance change between consecutive Syphon frames, 0..255, and the share of pixels toggling), pops (stream level changes over 0.05 morph), holes (green test at 6 times). Outputs in `blender/review/out/gpu_terrain/` (git-ignored).

Load 76 to 122 (stream) and 117 to 70 (GPU), `fps_trustworthy` false: frame times compare only roughly.

| stage | frame ms median, stream / GPU | lower-third cell px, stream / GPU | flicker mean, stream / GPU | toggles, stream / GPU | flicker spikes, stream / GPU | pops, stream / GPU |
|---|---|---|---|---|---|---|
| skim 10 m | 78.5 / 55.0 | 198 / 97 | 1.85 / 1.12 | 0.0015 / 0.0009 | 6 / 5 | 0 / 0 |
| climb to 64 km | 48.8 / 40.7 | 25 / 23 | 3.45 / 3.73 | 0.0069 / 0.0063 | 30 / 44 | 8 / 0 |
| orbit | 33.0 / 34.6 | | 0.04 / 0.04 | | 0 / 0 | 0 / 0 |
| cross | 34.4 / 33.0 | | 1.01 / 1.00 | | 0 / 0 | 1 / 0 |
| descent to 450 m | 40.0 / 37.5 | 20 / 11 | 7.57 / 6.97 | 0.020 / 0.016 | 59 / 117 | 5 / 0 |
| circle 450 m | 78.2 / 41.8 | 28 / 15 | 1.68 / 0.99 | 0.0020 / 0.0013 | 0 / 0 | 1 / 0 |
| circle 60 m | 84.5 / 44.4 | 21 / 22 | 4.27 / 1.75 | 0.0113 / 0.0031 | 14 / 0 | 0 / 0 |

Holes (green share): stream 0, 0.0003, 0.0040, 0.0002, 0, 0 at 7, 26, 41, 62, 75, 85 s; GPU 0, 0, 0.0019, 0, 0, 0.

- The GPU terrain's ground: no pops by construction, less flicker on the ground stages (circle 60 m 4.27 to 1.75, toggles a quarter), frame times about half on the low stages (under unequal load).
- Its finer near cells (11 to 15 px against 20 to 28) are interpolation of the 12 m map, not detail.
- The descent has twice the flicker spikes of the stream (117 against 59): frames with a large change while the camera falls from 64 km, most likely the hand-over between the globe and the grid; not looked at.
- Supersampling (the camera frame fitted to the viewport, 1.47x, `planet_runtime.show_camera_view`): on the GPU terrain flicker unchanged (circle 60 m 1.75 to 1.83, descent 6.97 to 7.09), frame time +2 to +4 ms per stage (load 59 to 78). It mattered for the 1 px edges, which are gone; not built in (the call is in look-round-15.md).

What the frames show (`shot-reviewer`, 6 frames of the recording at 7, 26, 41, 58, 75, 87 s): ground everywhere, no holes, pyramids standing on the ground with their shadows, sea and coasts sane from orbit and in the descent. Faults:
- Blocky square cells in the near ground at 450 m and 60 m (lower left of the frame): the 12 m map's texels, bilinear, lit per triangle (True Normal). The first thing to fix: smooth normals from the map's gradient and finer near heights (question 1).
- Terrace-like banding on a foreground slope at the 10 m skim: most likely the map's precision on the GPU (a float image may go up as half float: 0.25 to 0.5 m steps) or the bilinear facets; not measured.
- A rectangular outline in the sea at the climb (26 s): a ring border of the water grid or the land grid under the sea.
- Stretched triangles down cliff faces at 60 m: one map texel spans the cliff.

Recording: `docs/video/gpu-terrain-test.mp4` (the GPU flight, supersampled, 1920x1080, 92 s; git-ignored).

## Built (2026-11-14)

The user's answers: near detail from noise in the shader, ground detail for the show's region and the globe for space, river flow rebuilt and site lights dropped, smooth shading, the stream removed in one change.

- The GPU terrain is the only terrain: `flight_rt` starts `gpu_terrain` (loaded from disk, map baked on the first open after a rebuild, about 80 s with the flow, then cached) and feeds it the camera every frame. Gone: `lod_scene`, `lod_stream`, the night edges in the Terrain material (the scene's only `/vj/grid` reader), `edge_guard` and its test, the stream's review tools (`path_edges`, `net_regularity`, `edge_probe`, `edge_stability`, `line_motion`, `cut_trace`) and `verify_flight`'s section 5. The page still reads `edge_guard`: the runtime reports `not_applicable` until the page's chip goes (B11). The start check has a terrain row instead of the night-edge row.
- Faults of the test, fixed and checked by `shot-reviewer` on the same flight seconds:
  - blocky cells and terraces: gone. Heights split into a 16 m coarse part and a fine rest (the half-float GPU texture kept 0.25 to 0.5 m steps), cubic map reads, two noise octaves (22 m / 1.4 m, 6 m / 0.45 m) within 120 m of the camera and off the water, smooth normals from the map's slope and the noise's;
  - stretched cliff triangles: reduced to smooth streaks (the map's 12 m remains the limit on cliffs);
  - the rectangle in the sea: gone. The see-through water drew the one-cell overlap of two rings twice; each ring now cuts away the pixels the finer ring draws (a transparent mix at the output). A first try that sank the overlapped ring added more outlines.
- The descent's flicker spikes are not the globe hand-over: per altitude band the GPU terrain flickers as much as or less than the stream (8 to 12 km: 17.5 against 21.7); the large changes come from falling at about 6 km/s, and the spike count is relative to a lower median.
- River flow: the probe stores PL_Surface's flow; image GT_Flow (half resolution) feeds the Sea's `pl_flow`. Rivers narrower than about two map texels (25 m) are not drawn: a finer regional water map would be the next step, not done.
- Found and left: the pyramids' own neon edges (a Wireframe node in the Pyramid material, 1.6 px, beat-pulsed) read as a dotted, glittery fringe; the user's call whether they go with the terrain's edges.

## Open questions for the user

1. Near detail: is the 12 m map's smooth near ground enough, or should the grid show real detail under 3 m (a regional map round the show's places, or PL_Surface's fine noise in the shader)?
2. Whole planet or the show's region: the prototype's map frame is good within about 16 km of the valley; flying anywhere needs a cube-map grid.
3. Site lights and flowing rivers: rebuild them for the GPU terrain (map channels), or let them go?
4. Faceted or smooth shading of the relief (True Normal per triangle against map-gradient normals)?
5. When the stream goes: everything listed under "What breaks or goes", in one change.
