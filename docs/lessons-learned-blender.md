# Lessons learned: Blender scenes, review and automation (2026-11-04 to 2026-11-15)

From the Synthwave Planet, the island and the parked Godot Colossus: 218 commits, 17 look rounds, about 40 sessions. Written for the Robot Scene (pre-rendered clips in Magic, live Blender layers on top). Evidence lives in `docs/handover/`, `docs/retrospective-2026-11.md` and `blender/review/`; "hv/" below is `docs/handover/`.

## The ten that matter most

1. **The user judges the moving picture.** Two days of passed rubrics on frozen still frames ended with "the cameras are all pretty glitchy and unpredictable" (2026-11-12); Godot got "too ugly to be honest" after 27 of 27 passes. Done means a 60 to 90 s recording of the live output with show defaults (blends, music, Magic steering), plus per-stage flicker numbers.
2. **Settle the look with the user before any build.** Rubrics measure readability, not quality. Many rounds of line work were thrown away when the user banned wireframe ("no wireframe at all", 2026-11-13). Get references, must-have shots and the visual language (lines or shading) rated first. That is what the concept site is for.
3. **Physical realism and coherence over effects.** Things on the ground need real contact (shadow, contact shade, no float, no cut through). Light, fog and haze apply to every object alike. Beat reactions go through brightness or emission on one smooth envelope, never through lens, FOV or geometry jitter (hv/gpu-terrain.md, round 16: the beat lens push alone was most of the steady flicker).
4. **Fewer moving parts.** Removed after costing days: 12 fixed shots with per-camera terrain sets, the auto cutter, Flight, Boost, Hover, the CDLOD terrain stream, wireframe, the violet grid. One path camera with a few parameters replaced them. Ask "is this needed?" before any LOD, stream or effect system.
5. **Numbers before images.** Flicker (mean frame diff, p95, toggle share), A/B on the same seconds with an A/A control, frame stats, ground-gap scans. Look at images only for what numbers can't tell you. Sanity-check a new measuring tool against known cases first (the round 17 ground scan reported 143 m gaps that weren't real).
6. **The build script is the source of truth.** The `.blend` is generated. A live MCP patch is an experiment until it is in the builder and the rebuilt file passes. A reboot wiped the scratchpad and took the island builder (patched 56 times by string replace), the grab tools and 237 grabs with it.
7. **Magic decides the music, the scene takes controls.** No music logic in scenes. One OSC contract (`osc/contract.json`) feeds the docs, the bridge scales and the Magic generator. Takeover (the user's touch wins, the music returns after a pause) is arbitrated in the bridge.
8. **Magic is file-based.** Generate `.magic` with `magicproj.py` and check its output with a Syphon grab. Never drive Magic by computer use (54 calls and 54 images for what a generator does in one).
9. **One Blender, one GPU, one owner.** The lock hook (`tools/blender_lock.py`) replaced slot negotiation by message. Two Blenders halve fps and collide on udp 9201.
10. **Reuse sessions and cap review cost.** Review subagents spent 15.5M of 22.3M output tokens; one reviewer read the same files 1,805 times. One reviewer, contact sheets, at most 36 images, a frozen rubric per round.

## Look and visual coherence

- **Lines:** 1 px lines never antialias in a live EEVEE viewport. Props change every frame, so TAA restarts and you get one jittered sample: shimmer and crawl. Use thick, soft or glow edges, or supersample (fitting the camera frame to the viewport, about 1.47x, cut night flicker 10.7 to 2.6). Wireframe-node edges read as a dotted fringe at grazing angles.
- **Regular lattices** (even parallel lines, global grids) read as a dummy grid and make moiré near the poles. If lines are needed, they follow the shape (contours), never a global lattice.
- **Contact:** objects lifted by half their depth floated. Emission-only objects cast no shadow and look pasted on. Add a sun shadow and a contact term. Bright emitters washed out the haze (300 kW lamps; 120 kW gave a tight halo): calibrate each emitter against fog at its intended distance.
- **Seams:** patch borders with their own smooth normals made straight light and shade lines along hillsides. Use one connected mesh, or weld borders and take normals from the shared height field. Per-triangle lighting of a bilinear height map reads as blocky cells.
- **Two surfaces at one distance trade pixels:** the globe-to-ground hand-over band flickered and gave ragged edges. Bake the area from one consistent mesh.
- **Water:** set the material to no transparency overlap with backface culling. Give it its own base colour and an explicit horizon or star reflection; keep ripple normals out of the colour mix. Derive water and land from one height source.
- **Fog:** keep froxel tile size at its tested value and keep a clear zone of 150 m or more around the camera. Fog floors must be interpolated, not taken per nearest vertex. Sky, stars and fog volumes follow the camera every frame.
- **Framing:** many "render" fails were framing (one ridge filling 55 % of the frame, 60 % blank sea, a moon cut by the frame edge). Set per-shot targets for ground, sky and subject share before polishing.
- **Precision:** a 100 km camera with corners projected 0.5 m ahead in single precision gave a dark 3 to 8 px border. Use camera-relative maths at large scales and check output borders on every path.
- **Stars:** match texture resolution to output (8k for 1080p; 16k put stars between pixels and looked emptier). Add nebulae linearly, not squared.
- **Don't let a fix undo an earlier user rule** (round 9 made day wires brighter, round 10 had "no lines by day").
- Not defects, so don't chase them: the moon's dark limb is its night side; palm crowns from above look like flamingos; dark water seen through the sea is the reflection backdrop.

## Motion, flicker and cameras

- What "strobey" turned out to be: edges and beat accents, not LOD swaps. Measure it: `blender/review/flicker.py` (cases still, moving, pulse on and off, overlays on and off).
- A/B on the same seconds: switch a probe every 8 frames on the same flight and run an A/A control (floor about 5 %). Freeze clocks to find the replicate noise floor per camera before acting on any difference.
- Cross representation swaps slowly: a blend crossed the globe band in 3 to 4 frames (jumps of 45 per frame). Capping the rate inside the band gave a mean of 3.15 over 37 frames.
- Camera logic as a pure, bpy-free module: a blend is a function of start pose, velocity, start time and t (quintic ease); a change mid-blend starts from the current pose. An offline checker (`verify_paths.py`) covers all pairs, heights, clearance and turn rate in `make verify`.
- Grabs landed mid-blend because `/vj/blend` defaulted to a fly-over, and the reviewer passed them. Before a still grab, set transitions to hard cut and hold every control.
- Cold first cuts take 90 to 260 ms (world swap, buffer upload). Pre-warm every shot's data before the show.
- Log camera pose per frame and per cut; an aim jump of 0 across cuts is a cheap, useful assertion.

## Blender as the build framework

- Thin loader in the `.blend` (`vj_loader.py`); runtime, bridge, Syphon sender and page load from disk on every open. An embedded runtime turned one-line fixes into rebuilds. Relative `//` paths (`make blender-paths`).
- Headless rebuilds take 5 to 11 s on an idle machine (46 rebuilds, 5 tracebacks). One rebuild per batch of changes, not per idea.
- Never save live OSC values into the `.blend`; `health.py` lists values that differ from their defaults (`off_default`).
- Pitfalls, each cost hours:
  - Timers die silently when their function raises: wrap ticks in try/except. `is_registered` on a bound method is always False.
  - Draw handlers survive file reloads (six rebuilds gave six handlers): replace the previous one through `driver_namespace` on start.
  - Driver expressions over 256 characters are cut silently.
  - Relinking nodes before capturing the old targets makes cycles.
  - A float image whose colorspace is set after the pixels are written comes out blank: set `is_data=True`, then pixels, `update()`, `pack()`. Float TIFF or EXR loaded as sRGB looks washed out.
  - Displacement keeps the mesh normals; supply a slope normal in the shader.
  - Blender opens 3D views in Solid: the runtime sets camera view and Rendered. EEVEE draws flat frames while compiling shaders (about 1 min cold): wait for luminance variance before grabbing.
  - Scripts exec'd inside a timer break closures; run them at top level.
  - Look objects up by collection or custom property, never by name prefix (`Pyramid_*` caught a helper and re-ran a scatter every frame, halving fps).
  - Per-frame `update_tag` costs about 8 µs per object; never mass-toggle visibility in a frame handler. `ID.copy()` of an evaluated mesh is 70x faster than `new_from_object`.
- Blender MCP: assign a dict to `result` or the call returns nothing. Release every OSC hold and restore props after a live session. A hold on `/vj/cam` made the camera jump back later.

## Blender as the live layer

- Ground shots are bound by per-pixel cost, not triangles (8x fewer triangles: 24.6 to 25.9 fps). Fog volumes near the camera and blended transparent layers (each runs the full shader including fog) are the heavy parts. Pre-render heavy work; keep the live layer to cheap passes.
- Cheap exact wins (18.8 to 59.2 fps): `render.use_border` on the camera frame, one Attribute node per shader tree (`shader_dedupe.py`), a light world for the common state. No measurable gain from: bloom quality, world probe, volume tile and samples, fog steps, glare quality, backface culling, dithered blend. Don't retest them.
- `preview_pixel_size` AUTO on Retina is 2: the viewport renders about 960x540 and Syphon upscales. Set the real resolution explicitly.
- Fps counts only with one Blender, `fps_trustworthy`, frozen clocks and held inputs, measured as Syphon frames per second. Load reached 50 to 280 from other work; say "skipped" rather than report loaded numbers.
- Features first, one tuning pass after (fps fell from 60 to 16 during feature work before anyone measured, and the first tuning pass was thrown away with the island). A cheap fps check per batch still helps.
- Syphon: a POST_PIXEL draw handler with no CPU copy (`syphon_out.py`). A black frame has the right size and rate: always check pixel mean and variance. Check orientation in Magic, not in a Metal read-back (a flip passed there and was upside down in Magic, an 8 min recording wasted). Leaving camera view stops Syphon, so health checks it.
- OSC bridge: a `bpy.app.timers` callback, no threads, `/vj/<name>` into `scene["vj_<name>"]`, latest wins. Latch triggers over a frame change (pulses were lost below 10 fps). Clamp in sender and runtime (an unclamped fog of 5.75 overdrove the scene). Test with 5 known messages and count them: that found a parser padding bug in 3 min.
- Art-Net (`artnet_input.py`): only changed channels apply, the first frame is a baseline so a resting fader never fights Magic, triggers fire on a rising edge through 128. The bridge is the one place that merges sources.
- Boot order: Blender, then Magic (it sends on change only, plus 2 s after load), then the page.

## Magic integration

- Generators reproduce Magic projects with 0 differences; `magicproj.py check/set --osc-target/listen/grab`. Test through a copy sending to a spare port (9300).
- Always set the OSCSender port (its default is 9201, Blender's). Allow about 20 s after Magic opens before it sends.
- Global evaluation is double-buffered: each Global-to-Global hop costs a frame (the kick chain lagged about 4 frames). Keep chains short; one control Global per address, named like it.
- Proof is Magic's output pixels: `magic_show_proof.py picture` compared MAGIC_OUT with CAM_OUT (correlation 0.997). Test the missing-source case (`show.magic` drew black when Godot's server was absent).
- The user: "Magic should not add additional filter and blooms now". Don't stack Magic effects on a scene that already has them.

## Orchestration and cost

- One session per area, one narrow brief; each writes `docs/handover/<topic>.md`. A 50 h do-everything session re-read about 560k tokens per turn.
- Reuse sessions; measure with `get_usage`, hand over only above about 350k of 1M. A restart costs 10 to 15 min.
- Models per node in the plan: Opus 5.5 high for design and root causes, Sonnet 5.5 medium for specified code and tests, Haiku 5.5 for reading helpers. Say when plan usage gets high (work paused 2026-11-12 to 2026-11-17 for the weekly limit).
- "The timing on how you check it is on you" (2026-11-11): slow checks came from our rebuilds, reproduction marathons and restarts, not machine load.
- Pure model first, scene second: logic in bpy-free modules with tests (Godot had 52 green tests 3 min after the first code). The live part comes last.
- Rubrics: frozen before the first grab, IDs per line, a counterexample, "name where in the frame". A new wish starts the next round. Review at full size for judgment calls; sheets are for triage. Mark shots that can't show a feature "not judged" (vacuous passes happened). Revert a fix the reviewer still fails even when its number improved (hole pixels 22,120 to 387, still a fail).
- Orchestrator re-runs the tests and reads the note before reporting a session's claim; lists unverified items explicitly.
- Shared machine: never put an app name in your own long-running shell command (the guards use `pgrep -f`). Wait for long runs with `until [ -f DONE ]`, never sleep chains. Recordings 1 min unless asked. Timing asserts report, they don't fail.
- Assets: one asset worker with a "needs the user's login" exit before any criterion depends on an asset (Mixamo and Sketchfab picks never got downloaded). Don't install a tool without a first use in the brief (godot-mcp went unused for 43 h).
- Ask design questions in one batch with defaults; the user answered 12 in one go (2026-11-12) and five as "Yes, all five" (2026-11-14).

## What changes for the Robot Scene

- **Pre-render removes most live failure modes:** LOD, streaming, TAA crawl, fog cost and fps all move to offline renders with real samples and motion blur. Spend render time on quality; check clips with the same flicker and coherence numbers before they ship.
- **New risks to plan for:**
  - continuity between clips (pose and camera match at cut points)
  - live layers aligned with pre-rendered camera moves (export the camera per frame alongside each clip)
  - matte and depth passes for compositing
  - decode load and file size in Magic (test the codec and the clip count on the show Mac early)
  - beat-aligned clip lengths
- **Keep the live layer small:** sparks, light, HUD and particles placed with the clip's mattes, beat reactions by brightness, thick soft edges, no wireframe.
- **Contract first:** Robot rows in `osc/contract.json` (group, plain sentence, scenes field) before any generator or scene code; its own Syphon name and test ports.
