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

## The run (2026-11-14)

`blender/review/path_camera_run.py`, one held day pass (3 min, every path and target, show defaults, every control held), recorded to `docs/video/gpu-terrain-run.mp4` (1920x1080, 3936 new frames in 183 s, git-ignored). Load 226 to 228 (others' dotnet and clang builds): frame times untrusted.

- Median 41.3 ms, p95 66.2 ms; flicker mean 6.5 (0..255), toggles 0.015; lower-third cell about 38 px; least height over the ground 10 m.
- Holes: none at any of the 15 steps (a second held run with a green test mid-step, `run_holes.json`).
- The 60 s with Magic and music: skipped (the user, 2026-11-14; Magic sent nothing to 9201).

## Round 16 (2026-11-14): the open items, measured

Tools (live planet Blender, every control held at the show defaults unless said): `blender/review/flicker.py` (cases; new: `noise` and `normal` terrain probes, `energy` constants, `log` per frame with altitude and frame thirds, A/B cases that switch a probe every 8 frames on the same flight so both sides see the same seconds), `blender/review/pyramid_edges.py` (edge variants, flicker runs per variant, frame grabs), `blender/review/river_check.py` (still camera, pulse off, water change with and without flow). Rubric `blender/review/rubric-round16.md`. Outputs in `blender/review/out/round16/` (git-ignored). Load 20 to 350 throughout (others' builds): frame times untrusted, flicker numbers are per frame and hold.

**1. Steady flicker split** (mean luminance change per frame, 0..255; toggles = share of pixels that step up and back):
- Camera motion is the largest share: still against moving at the show defaults 0.96 against 1.6 to 1.9 (follow pyramids), 0.28 against 2.0 to 2.7 (follow sun). It is the shot itself, not a fault.
- Beat pulse: on a still camera it is nearly all that is left (0.70 against 0.02 at the lake, 0.43 against 0.04, 0.15 against 0.005). Of it the lens push (`energy.BEAT_LENS` 0.02) is 55 % (lens 0: 0.32) and 74 % of its toggles; the dip and roll 20 % (tilt 0: 0.56); the rest the brightness flashes. A slower attack (0.15 s) and both at half changed nothing much.
- Terrain: near noise off, A/B on the same seconds: the lowest pyramid shot 1.01 to 0.60, the others 5 to 7 % (A/A control within 5 %), no toggles either way: the relief's own texture passing by, not a strobe. Smooth against flat normals: within the noise.
- Pyramids (lowered with `/vj/pyramids` 0, A/B): orbit pyramids 0.3: 1.59 to 1.30, toggles 0.0039 to 0.0027. Their edges, stripes, the edges' beat and 2.5 px edges each: no difference over the A/A control, moving or held.
- The run's steady 9.2 at "follow sun" was the tail of the fall from 64 km (blend flag off, the height still gliding), not a steady shot.
- Fix: `BEAT_LENS` 0 (`energy.py`): the lens no longer pushes on the beat (the hit's lens, the dip and roll and the flashes stay). A/B on the same seconds, moving: follow lake 1.27 to 0.52 (toggles 0.00085 to 0.00018), follow pyramids 0.0 2.88 to 2.27 (toggles 0.0033 to 0.0020), orbit pyramids no change (1.60 to 1.56). 0.005 instead of 0: only part of it.

**2. Descent spikes** (vantage planet 1.0 to follow sun 0.2, logged per frame):
- Fault: the globe hand-over band (8 to 12 km) was crossed in 3 to 4 frames by a blend (only the rise path kept `BAND_RATE`); the far skin took the pixels over at once: 45 and 29 in two frames, evenly over the whole frame. Fix in `path_camera.py`: `banded` holds the eye's height to `BAND_RATE` (0.3 e-folds/s) inside the band during a blend, and lets it catch up at `BAND_CATCH` (3 e-folds/s) outside it; cuts and live shots pass. After: 8 to 12 km mean 3.15 over 37 frames, max 11.8 (before 26.4 over 4 frames, max 45.6). `make test`, `make verify` green.
- Not a fault: 800 to 250 m: 12 to 17 a frame with toggles 5 to 12 %, top third first; the blend falls about 1 e-fold of height per second there over detailed ground. Held at that height the picture is clean (0.15 with the pulse, 0.005 without, fog on or off). Fog A/B in the fall: 2.50 against 2.09 below 800 m, no toggle difference.

**3. Rivers** (`river_check.py`, shots follow river 0.0 and 0.15, orbit river 0.3; reviewer set R):
- The orbit shot shows a river, 60 to 200 px wide, one continuous band (R16-RIVER-WHOLE holds). The follow shots show only a lake shore or no water.
- The flow does not show: it moves 0.002 % of the pixels (R16-FLOW fails). Two causes: GT_Flow has flow only on one-texel lines (2.5 % of texels within 1 km of the river target), while the drawn river is several texels wide; and the ripples barely show at these heights (water change 0.04 to 0.06 on a still camera with or without flow).
- Rivers under 25 m: the three shots show none missing, but they cannot show what the 12 m map never had; no number for it.
- A regional water map (4096^2 over 16 km round the valley, about 4 m a texel): bake about 40 s more on the first open (the 8192x4096 map takes about 80 s), cached; 64 MB more as RGBA float, about 16 MB of flow; in the shaders a second lookup with a switch at its edge (land: 5 lookups for height and slope, water: 1), estimated 1 to 2 ms on the GPU, unmeasured. Not built.

**4. Pyramid neon edges**: share of the flicker not measurable apart from the pyramids as a whole (above). Built: steady (no `rt_beat` term) and 2.5 px (`build_planet.pyr_build`, rebuilt). Reviewer (set P): orbit 0.3 clean in both; orbit 0.15 the far ridge dashed in both, the new edge marginally cleaner; follow 0.0 too small to judge.

**5. Idle frame times**: skipped, `make status` said load 68 to 129, `fps_trustworthy` false. For the user, on an idle machine with nothing else on the GPU: `make status` (fps_trustworthy true), `make blender-open SCENE=planet`, then in a session through the Blender MCP: `DN["fl_job"] = {"out": "<abs>/blender/review/out/idle.json", "frames": 300, "cases": [{"name": "defaults"}]}; exec(open("<abs>/blender/review/flicker.py").read())`; the row's `draw_ms_median` is the frame time.

**6. Recording**: `docs/video/gpu-terrain-round16.mp4` (90 s, unheld, Magic steering, 1920x1080, 1709 new frames, git-ignored), with the new lens and the band fix live, the new edges set live before the rebuild. Flicker 2.63 mean, p95 5.25, toggles 0.0043, 26 spikes; by 15 s stage 1.71, 3.26, 4.01 (one frame of 32), 2.05, 1.46, 3.37. Magic held one shot (148 to 340 m, no blends). Draw interval median 52 ms at load 82 to 113 (untrusted).

## Open items (for a fresh session)

1. **River flow**: spread the flow from its one-texel lines over the drawn water in the bake (dilate within the water mask), and make the ripples readable at 100 m to 1 km; then `river_check.py` again. The regional water map: the user's call (cost above).
2. **The pyramids' far ridge** reads dashed at orbit 0.15 (grazing faces under the Wireframe node); a silhouette-aware edge or a geometric edge would be next.
3. **The fall's lower part** (800 to 250 m, about 1 e-fold/s): if the user sees it as a strobe, slow the blend's height near the ground like the band.
4. **Idle frame times**: the command under 5.
5. The page and its test still read `edge_guard` (`not_applicable`) and the contract still has `/vj/grid`: B9 and B11.
6. Reviewer note: a hole-like opening at a mountain peak in the follow pyramids 0.0 frame (about x 1060, y 212); unchecked.

The five questions of the GPU terrain test were answered "Yes, all five" (2026-11-14) and built in 25322af.

## Round 17 (2026-11-15): pulse, ground contact, edges

The user (2026-11-15): "during a pulse, the pyramids need to pulse with it, and their connection to the ground needs to be realistic. edges are better, but still glitchy. frame rate is not an issue, but physical realism and good visual coherence." Rubric `blender/review/rubric-round17.md`, frozen before the build (7af25a7).

**The near pyramids are the island's.** Every pyramid shot is framed on Pyramid_A to D (materials Pyramid Body and Pyramid Edge, wireframe-modifier tubes), not on the site pyramids (Planet_Sites). Their edges still flashed at 7 x rt_beat and the capstone at 4 x: the "still glitchy" edges. Round 16 had changed only the site pyramids.

### Built

- **Pulse** (`energy.py`, `flight_rt.py`, `build_planet.py`): `rt_pulse`, the Drive's glow, follows the beat's held peak (released over PULSE_RELEASE 0.25 s) at PULSE_ATTACK 0.08 s. It drives the emission strength of all three pyramid materials, 1 + PYR_PULSE (3) x rt_pulse, after the haze. A gain before the haze was diluted by the fog round the pyramids (+7 % at 1.7 x). The island's beat terms (edges 7 x, capstone 4 x rt_beat) are 0.
- **Ground** (`gpu_terrain.pads`): a level pad in the map under every site pyramid (base + 1 m, level to 20 m past the base, blended into the land by 160 m, applied to the cached map at start, no rebake). A foundation under each site pyramid (`unit_pyramid`: the faces continue 0.6 x the depth into the ground), for the coarse rings that cannot hold a pad. The near noise is off over the pads.
- **Contact**: the land's shade round a site pyramid's foot (GT_Flow's alpha, 1 at the base to 0 at 0.6 x the half side, the land at 0.6 there, under the haze); the site pyramid's foot in shade over its lowest 6 % (PYR_FOOT).
- **Edges**: the site pyramids' Wireframe node in world units, its width grown with the distance to 2.5 px from the live lens (`rt_px_angle`, written by flight_rt); the same line in the island pyramids' body under their tubes.

### Numbers

**N17-GAP** (`blender/review/pyramid_ground.py`, 1355 site pyramids). The first run's 143 m was a stale map frame in the scan (fixed: it computes the frame when the live one is missing; the map then agrees with PL_Surface within 0.3 m). Rows: floating at the base / floating past the foundation / buried p50 / buried p95 (share of height) / faces cut by the land.

| ring (cell) | before | after |
|---|---|---|
| 0 (3 m) | 1262 / – / 19.6 % / 57 % / 1333 | 14 / 0 / 2.4 % / 4.1 % / 21 |
| 2 (12 m) | 1262 / – / 19.5 % / 57 % / 1332 | 22 / 0 / 2.4 % / 4.1 % / 23 |
| 3 (24 m) | | 48 / 0 / 2.6 % / 4.3 % / 34 |
| 4 (48 m) | 1239 / – / 19.1 % / 55 % / 1314 | 153 / 0 / 3.0 % / 8.3 % / 120 |
| 5 (96 m) | 1194 / – / 18.7 % / 58 % / 1277 | 443 / 6 / 4.0 % / 21.5 % / 447 |

Pads 6/60 m left 705 floating on the 48 m cells; 20/160 m: 165 (before the foundation). Pass on rings 0 to 3 (none floats, p95 under 6 %); ring 4 p95 8.3 %, ring 5 21.5 % and 6 past the foundation: fail.

**N17-PULSE** (`blender/review/pulse_check.py`, orbit pyramids 0.15 held still; the pyramids' mask from a 40 x gain, 17.5 % of the frame): luminance 100 at rest, 143 at rt_pulse 1 (+43 %, bar 25 %: pass). The idle pulse (no `/vj/beat` from Magic) swings it 108 to 118 (about 10 %) twice a second; its largest one-frame step is 74 % of the swing (bar 40 %: fail). At 124 BPM an attack fast enough to show needs more than 40 % in a frame; visibility won. The outline does not change (the pulse touches only emission).

**N17-FLICKER** (`flicker.py` A/B on the same seconds, the round-17 site-pyramid switches of `round17_probes.py` on / off): orbit pyramids 0.15 2.82 / 2.91, orbit 0.3 3.22 / 3.18, follow 0.0 1.08 / 1.18: within 5 %, pass. The recording against round 16's: mean 1.79 / 2.63, p95 5.36 / 5.25, toggles 0.0023 / 0.0043, frames over 30: 0 / 1.

**N17-EDGE**: whole-frame toggles at orbit 0.15, world edges / round 16's pixel edges: 0.00734 / 0.00774 (5 % less, bar half: fail as measured; not measured inside the pyramid masks).

### Shot-reviewer

Final stills (`out/round17/final/`, five shots, rest and peak): R17-PULSE pass 5 of 5 (faces, edges and capstone together, outline unchanged); R17-GROUND pass; R17-CONTACT pass (cast shadows, shade at the foot); R17-COHERENT pass. R17-EDGE fail on two small far base edges (orbit 0.3, vantage 0.5); the dotted island ridges of the earlier set are now continuous lines. R17-HOLE fail: ragged see-through patches, a pale ring and dark pits on mountain ridges (orbit 0.3, rise 0.3). An A/B without the land's ring-overlap cut left every hole in place: not the cut.

Set M (the recording): R17-MOTION pass, no jump, jitter, strobe or loss of contact in 36 tiles. The pulse is not visible at 480 px tiles ("a smooth swell of a few percent at most"): the idle pulse's 10 %.

### Recording

`docs/video/gpu-terrain-round17.mp4` (90 s, 1920x1080, 1554 new frames, git-ignored): 70 s held at show defaults (orbit pyramids 0.15, rise to 0.6, descent to 0.2, follow 0.1), 20 s Magic steering (it held one shot, no beats). Recorded without `--vflip` and flipped upright afterwards (`ffmpeg -vf vflip`); `syphon_record.py` needs `--vflip` for Blender. Stages by 15 s: 1.59, 3.12, 2.98, 1.73, 0.67, 0.93 (`blender/review/video_flicker.py`).

### Open items and questions

1. **The idle pulse's strength**: decided by the user (2026-11-15, "Stronger idle pulse"), built in round 18.
2. **Holes on mountain ridges**: fixed (2026-11-16, issue #10, below).
3. **Far small base edges** read dashed (two in the final set): the base edge lies along the ground at a grazing angle.
4. **Ring 5** (96 m cells, 6 to 12 km): 6 pyramids float past the foundation, buried p95 21.5 %.
5. **Idle frame times**: not measured, `make status` load 40 to 87, `fps_trustworthy` false; the command under round 16's point 5.
6. Others' items unchanged: river flow (1), the fall below 800 m (3), B9 and B11's page and contract leftovers (5).

## Round 18 (2026-11-15): the stronger idle pulse

The user: "Stronger idle pulse" (replaces "10% is fine"). Rubric `blender/review/rubric-round18-idle-pulse.md`.

**Built.** A pyramid-only gain while the idle pulse runs: `flight_rt.py` writes rt_pulse = glow x PULSE_IDLE_GAIN - PULSE_IDLE_FLOOR, clamped to 0..1, weighted by the runtime's idle (`vj_runtime.idle()`, 0 while `/vj/*` changes, 1 after IDLE_AFTER). `energy.py` PULSE_IDLE_GAIN 3.0, PULSE_IDLE_FLOOR 0.2: the idle rt_pulse runs 0 to 0.74 (was 0.08 to 0.28). IDLE_DEPTH (stars) and PYR_PULSE are unchanged; a Magic beat has gain 1 and floor 0, as in round 17.

**Numbers** (`pulse_check.py`, orbit pyramids 0.15, `blender/review/out/round18/`):

| Run | gain, floor | full beat (rt_pulse 1) | idle swing | idle rt_pulse |
|---|---|---|---|---|
| day | 3.0, 0 | +40 % | 21 % | 0.20 to 0.91 |
| day | 3.6, 0.22 | +39 % | 33 % | 0 to 0.94 |
| day | 3.2, 0.2 | +52 % (other pose) | 39 % | 0 to 0.81 |
| day (built) | 3.0, 0.2 | +40 % | 27 % | 0 to 0.74 |
| night (built) | 3.0, 0.2 | +148 % (8.8 to 21.9) | 80 % (peak 15.9) | 0 to 0.68 |

The pose differs per run (the orbit flies on during the settle), so compare the idle swing with the full beat of the same run. N18-IDLE pass (27 %). N18-CAP pass: rt_pulse stays at most 1, so a full beat is as bright as in round 17; at night the idle peak (15.9) stays under the full beat's (21.9). The largest one-frame step stays about 70 % of the swing (round 17's N17-PULSE smoothness fail, unchanged).

**Recording.** `docs/video/gpu-terrain-idle-pulse.mp4` (30 s, 1920x1080, upright, git-ignored): orbit pyramids 0.15, every control held, idle. 513 new frames (load 30 to 38). Flicker mean 1.97, p95 4.74, toggles 0.0016, no frame over 30. The bright bodies in the frame's middle band beat at 2.07 Hz (124 BPM), 466 x the median spectral power.


## Regional water map and river flow (2026-11-15)

The user: "yes regional water map". Rubric `blender/review/rubric-water-map.md`.

**Built** (`gpu_terrain.py`):
- The bake runs per grid (`grid()`, `bake(region=)`); caches are now `gt2-*` (the old `gt-*` hold unspread flow).
- **Flow spread**: GT_Flow's flow sits on the river's centre line. `spread()` hands it ring by ring to the wet texels round it, up to FLOW_SPREAD (150 m). Wet texels carrying flow: 73 % of the inland water in the region's box (round 16: one-texel lines).
- **River ripple bands** (`build_planet.water_shader`, RIVER_BANDS 0.45): on flowing water the ripple bands reach down to 0.45 of the reflection (sea: 0.85 to 1). Rebuilt.
- **Regional map**: GT_Region and GT_RegionFlow, 4 m texels over REGION. That is the box of the four camera targets plus 2 km (14.8 x 24 km, 3700 x 6000; the river target lies 14 km from the pyramids, outside a 16 km square). Pads on it too, and the shaders blend to it over REGION_EDGE. **Off** (`REGION_ON = False`): it neither bakes nor draws.

**Why off** (numbers first):
- Rivers: the planet's rivers are 50 to 100 m wide. Inland water over the box is 0.229 km² at 4 m against 0.225 km² at 12 m. The 12 m map misses 0.006 km², none of it in channels under 25 m (`blender/review/water_map_check.py`, width histograms in `blender/review/out/water/water_map*.json`).
- Cost under load (load 22 to 30, `fps_trustworthy` false), median frame interval on the same five pinned poses: 71.4 ms off, 78.9 ms on (+7.5 ms, about 10 %).
- Bake about 45 s on the first open; cache 126 MB. CPU images 444 MB as float32 (22.2 M + 5.5 M texels); on the GPU about 220 MB at half floats (estimated).
- Reviewer: C (region on) drew ripple bands and bright stripes on the land at two of five poses (RW-SEAM and RW-COHERENT fail).

**Cold open** with the new caches (12 m map rebaked with the spread, region off): 91 s to the start state ready; Blender RSS 4.0 GB just after (a warm open: 1.8 GB).

**river_check.py** now holds a shot's camera at a recorded pose (`"pose"`, after flight_rt's frame), saves the last frame and the span over the capture, and logs the draw interval.
- Its flow numbers are not repeatable: one pose gave 0.004 % and 37 % in two runs of the same build. The span counted sky and land as well.
- The first capture after a `start()` caught EEVEE still compiling (100 % change): wait for a warm frame.
- Use the reviewer's frames, not these numbers, for the flow.

**Reviewer** (5 pinned poses x A before / B spread and bands / C plus region, first and last frame 3.5 s apart, `blender/review/out/water/rev_*`):
- Two of the poses (follow river 0.0 and 0.15) show no river, only a lake at the edge.
- On the three river poses B reads best: the river gains a ripple grain that matches the sea (A's river is flat). RW-RIVER passes on orbit 0.15.
- B also shows a checker dither on banks and shores in some frames that A lacks. It may come from the day cycle: one pose went from dusk to day within the capture, since the day cycle isn't frozen.
- RW-RIPPLE fails in every build: the flow's motion is not readable within 3.5 s.

### Open items
1. River flow readable in motion (RW-RIPPLE): at 2.6 m/s the ripples drift 9 m in 3.5 s, but the grain is faint. Next: a river-only ripple scale and contrast, judged on a recording, not on stills.
2. B's checker dither on banks and shores: check it with the day cycle frozen.
3. `river_check.py` poses that see the river (the follow poses don't), and freezing the day cycle during a capture.
4. The swiftvj-flight cache keeps every old bake (1.7 GB+); nothing prunes it.

## Holes on mountain ridges (2026-11-16, issue #10)

- Not the cubic lookup: EEVEE's Cubic is a B-spline (weights all >= 0, `textureLod` 0), it never overshoots its 4 x 4 texels. Not the slope normal.
- Cause: Terrain hides land under its water by `zw = alt - pl_w < -SHALLOW` (1 m). On the GPU land `alt` was the drawn triangle's height and `pl_w` the map's water read per pixel, which the bake puts 15 m under dry land. A coarse ring's triangles cut under a peak by more than 16 m: hidden (holes), or drawn as wet bed and fringe just above that (the pale rim).
- Offline on the cached map (`blender/review/ridge_holes.py`, no Blender), dry land in the targets' box hidden per ring cell: 24 m 0.005 %, 48 m 0.51 %, 96 m 4.4 %, 192 m 12.5 %; worst peaks 1.7 to 3 km from the pyramids, cut up to 110 m on 96 m cells.
- Fix (`gpu_terrain.material`, land only): `pl_w` shifted by the triangle's own error (`alt - h`), so `zw` is the map's land over its water at the pixel. Node `gt_zw_fix` (factor 1) switches it for the A/B.
- Live A/B on the same frames (`blender/review/ridge_check.py`, controls held, pose pinned, `out/issue10/live/`): changed share / A/A noise: orbit pyramids 0.3 0.42 % / 0.22 %, rise pyramids 0.3 0.41 % / 0.38 %, orbit pyramids 0.15 0.20 % / 0.06 %, orbit lake 0.3 0.86 % / 0.13 %. The first toggle recompiles the shader: the first shot's first pass caught it (82 %) and was rerun at its pose.
- Reviewer (`rubric-issue10.md`): all four pass I10-HOLE, I10-RING, I10-SAME, I10-COAST. Orbit lake 0.3 had see-through holes with a pale rim on four summits before, solid summits after; the other three shots have no peak in frame.
