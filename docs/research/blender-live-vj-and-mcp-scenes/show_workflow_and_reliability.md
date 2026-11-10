# Blender as a live VJ engine: show workflow and reliability

Scope: Blender 5.2.3 LTS on macOS Apple Silicon (M1 Max), output via Syphon into SwiftVJ, control via OSC. Research date 2026-11-03. Source quality is uneven: official docs and the Blender tracker are solid, practitioner reports are thin and mostly 2022 to 2026 forum posts. Inferences are marked as such.

## 1. Switching visual "scenes" live without stutter (scenes vs view layers vs collections, linking, shader warm-up, memory)

### Takeaway
The dominant stutter source is EEVEE material shader compilation, which happens the first time a material/pipeline is drawn. On macOS the compile path is Metal-only, the Subprocess/parallel compile preferences do not apply, and there is no documented EEVEE disk shader cache beyond the OS Metal cache. The practical pattern is: keep everything in one .blend, pre-draw every scene/material once before doors open, keep GPU textures/VBOs resident, and switch by changing what is drawn rather than by appending/linking on the fly.

### Cited Findings
- First enable of EEVEE-Next took about 13 s for shader compilation; later switches took a fraction of a second, because compiled shaders are reused ([devtalk EEVEE-Next feedback p.19](https://devtalk.blender.org/t/blender-4-2-eevee-next-feedback/31813?page=19)).
- Material shaders (from node trees) are the per-scene cost and must be compiled for most materials you author; a tester measured general shaders at 27 s in EEVEE-Next vs 2 s in legacy EEVEE on a clean cache ([devtalk EEVEE-Next feedback](https://devtalk.blender.org/t/blender-4-2-eevee-next-feedback/31813?page=21)).
- Developers attribute slow compiles to EEVEE's complexity and its source dependency system; most shaders are about 10k lines ([devtalk EEVEE-Next feedback](https://devtalk.blender.org/t/blender-4-2-eevee-next-feedback/31813/416)).
- Editing a Mix node value in EEVEE-Next caused 2 to 4 s recompile pauses that grow with shader complexity ([Issue #120586](https://projects.blender.org/blender/blender/issues/120586)). Relevant because driving some node inputs live can trigger recompiles rather than uniform updates.
- Tracking task for long compile times notes OpenGL limits multithreaded compilation and that Vulkan would address it ([Issue #120100](https://projects.blender.org/blender/blender/issues/120100)).
- Blender 5.0: simple materials compile about 4x faster on NVIDIA OpenGL, with improvement "on all backends"; benchmarks ran with shader caches disabled ([5.0 EEVEE release notes](https://developer.blender.org/docs/release_notes/5.0/eevee/)). The 5.0 notes do not mention Metal or any precompilation feature (same source).
- A late-2025 commit "Precompile World Material Pipelines" appears in weekly dev notes ([24 November 2025 notes](https://devtalk.blender.org/t/24-november-2025/43379)); May 2025 module notes said work was underway to avoid compiling unused shaders at startup and that EEVEE default shaders were still blocking ([2025-05-26 module meeting](https://devtalk.blender.org/t/2025-05-26-viewport-eevee-module-meeting/40798)).
- Parallel compilation of EEVEE specialization constants was merged for 4.2 ([PR #122798](https://projects.blender.org/blender/blender/pulls/122798)); a WIP to compile all static shaders in parallel warned it could slow startup on backends without parallel compile support, with uncertainty about Metal ([PR #121542](https://projects.blender.org/blender/blender/pulls/121542)).
- Preferences > System: "Shader Compilation Method" (Thread vs Subprocess) and the thread/subprocess count are "not available on macOS" and require the OpenGL backend ([Manual 5.2, System prefs](https://docs.blender.org/manual/en/latest/editors/preferences/system.html)).
- On macOS, viewport shaders (EEVEE, UI, Workbench) rely on the system Metal shader cache; only Cycles uses its own Metal binary archive cache (Blender developer comment surfaced in Metal shader-compilation issues, e.g. [Issue #116414](https://projects.blender.org/blender/blender/issues/116414) / [Issue #106304](https://projects.blender.org/blender/blender/issues/106304); exact issue holding the comment not re-verified).
- A maintainer treated a few seconds of freezing after switching to EEVEE shading on Mac as normal shader compilation ([Issue #106551](https://projects.blender.org/blender/blender/issues/106551)).
- Preferences > System: "Texture Time Out" and "VBO Time Out" set seconds before unused GPU textures/VBOs are freed; 0 keeps them allocated. "Undo Memory Limit" 0 means unlimited ([Manual 5.2, System prefs](https://docs.blender.org/manual/en/latest/editors/preferences/system.html)).
- Each scene has its own depsgraph; depsgraphs are passed explicitly since the 2018 removal of the single global evaluation context ([Blender archive commit](https://projects.blender.org/archive/blender-archive/src/commit/73dc8c24e44ba8b462f88c1c629a84c98979ef41)).

### Inferences
- One .blend, multiple Scenes, switched by setting `window.scene` (or the share add-on's scene/layer selector) is the cleanest "cue = scene" model. Already-compiled materials should not recompile on return, but a scene's depsgraph is (re)evaluated when it becomes active, so first activation of each scene should happen in a pre-show warm-up pass.
- Collections toggled within one scene avoid depsgraph switches but every hidden object still costs memory; toggling `hide_viewport` triggers depsgraph rebuilds, while `hide_render`/visibility flags differ in cost. Measure on the target scene. Not verified by a source.
- Append/link on the fly is the worst option live: file I/O, datablock creation, new materials compiled on first draw. Treat it as pre-show only.
- Warm-up procedure: open file, cycle every scene through the Rendered viewport (or the Syphon camera) for a few seconds each, at show resolution, before going live. Set Texture/VBO Time Out to 0 so assets stay resident during the show. On an M1 Max (unified memory, up to 64 GB) memory headroom is usually fine for a handful of scenes, but watch total RAM since GPU and CPU share it.
- Avoid driving shader node inputs that change shader topology or specialization live (the Mix-node recompile report). Prefer driving values via attributes, drivers on object custom properties, or Value nodes, and test each controlled parameter for hitches during rehearsal.

### Gaps
- No source confirms whether EEVEE on Metal in 5.x persists compiled pipelines across launches beyond the OS cache, or how long a cold start takes on M1 Max.
- No measured cost for `window.scene` switches in 5.x; no official guidance comparing scenes vs view layers vs collections for live switching.
- Blender 5.1/5.2 EEVEE release notes were not checked for further compile/precompile changes.

## 2. Running modes: visible UI viewport vs headless, multiple instances, frame pacing, redraw without playback, handlers vs timers

### Takeaway
The Syphon path that exists today (TextureSharing add-on) renders from a camera and only sends a frame when the viewport redraws, so a visible Blender UI instance is the practical mode; true background (`-b`) mode has no viewport to drive real-time EEVEE output. Keep redraws going with timeline playback (Frame Dropping sync) or a repeating `bpy.app.timers` callback that tags areas for redraw. Python threads touching `bpy` are unsupported.

### Cited Findings
- TextureSharing (maybites) shares a camera's output via Syphon/Spout/NDI/OMT from a "Share texture" panel in Camera properties; you choose resolution, a workspace for render/shading prefs, and a scene and layer to render ([TextureSharing README](https://github.com/maybites/TextureSharing)).
- "A frame is only sent when the viewport redraws"; the steady-stream option (resend last frame at scene fps while idle) exists only for NDI and OMT, not Syphon ([TextureSharing README](https://github.com/maybites/TextureSharing)).
- macOS status: Syphon Metal server and OpenGL server working; Syphon Metal client partial; transparency only works in Solid display mode ([TextureSharing README](https://github.com/maybites/TextureSharing)).
- V9.0.0 targets Blender 5.x; VDMX forum users in March and May 2026 report it working and "very simple" ([VIDVOX forum, V9.0.0 thread](https://discourse.vidvox.net/t/texture-sharing-add-on-v9-0-0-for-blender-5-x-upwards/8924)).
- Changing transfer settings (e.g. dimensions) does not apply while sharing is active: deactivate, change, reactivate, and recreate the receiver in the host app ([VIDVOX forum, 2024 thread](https://discourse.vidvox.net/t/blender-texture-sharing-syphon-spout-and-ndi/2397)).
- `bpy.app.timers.register(fn, first_interval=0, persistent=False)`: return a float to reschedule, `None` to stop; `persistent=True` survives file loads ([API: bpy.app.timers](https://docs.blender.org/api/current/bpy.app.timers.html)).
- Python threads are not supported: while threads run, no code (including main thread) may use bpy; long-running threads (e.g. repeating Timer) can cause random crashes in drawing code; use join() or `multiprocessing` ([API: Python Threads are Not Supported](https://docs.blender.org/api/current/info_gotchas_threading.html)).
- Playback sync: "No Sync" can run slow at 60 fps while "Frame Dropping" keeps timing correct (user report) ([Steam forum](https://steamcommunity.com/app/365670/discussions/0/1744520920051402432)); an old 2.80 report said Frame Dropping did not work, later marked resolved ([Issue #65940](https://projects.blender.org/blender/blender/issues/65940)).
- Turning vertical sync off was suggested as a workaround where the monitor refresh caps viewport playback ([Issue #88219](https://developer.blender.org/T88219)).
- Backend preference: changing GPU backend requires restart ([Manual 5.2, System prefs](https://docs.blender.org/manual/en/latest/editors/preferences/system.html)). On macOS the backend is Metal (Metal viewport introduced 3.5, works on Apple Silicon) ([CG Channel](https://www.cgchannel.com/?p=143434); [Blender Metal Viewport blog](https://code.blender.org/?p=10640)).

### Inferences
- Recommended mode: one visible Blender instance, a dedicated window or workspace showing the show camera in Rendered mode (or the add-on's offscreen camera render), UI overlays off, on a secondary display or hidden behind SwiftVJ. Frame rate is then bounded by Blender's main-loop redraw rate.
- Two ways to keep frames flowing: (a) timeline playback with Frame Dropping, which also gives frame-change handlers for time-based animation; (b) a timer returning e.g. 1/60 that calls `area.tag_redraw()` on the 3D view, decoupled from the timeline. (a) ties animation to scene fps; (b) is better for purely parameter-driven/generative content. Mixing both risks double work per frame.
- Frame-change handlers (`frame_change_pre/post`) run inside playback and add per-frame cost; keep them minimal and do OSC parsing outside them.
- OSC from SwiftVJ should be received on a non-bpy thread or socket polled from a timer, queuing values and applying them on the main thread in the timer callback (pattern implied by the threading doc; the timers page fetch did not show a queue example).
- Multiple Blender instances (one per scene, each its own Syphon server) would give instant switching at the host level (SwiftVJ crossfades between Syphon sources) at the cost of GPU contention and double memory. On M1 Max this is plausible for 2 light scenes; heavy EEVEE scenes would compete for the same GPU. Not verified by a source.
- Headless `blender -b` is suited to pre-rendering clips (offline renders to ProRes/HAP for SwiftVJ playback), not live output.

### Gaps
- No source on how Blender's macOS window/display vsync behaves with Metal or whether vsync can be disabled there.
- No benchmark of TextureSharing Syphon overhead (offscreen render + copy) on Apple Silicon, nor confirmation whether Syphon Metal server is zero-copy.
- No documentation found for exact redraw cadence of a timer-tagged viewport when the app is not frontmost (macOS App Nap/occlusion behavior).

## 3. Reliability: crash recovery, autosave/undo during a show, hitch-causing features, Python add-on stability

### Takeaway
Blender has no show-mode. Reliability comes from preferences (disable autosave, reduce undo, keep resources resident), a locked show file, a tested add-on set, and an external watchdog/relaunch path. Auto Run Python Scripts is off by default and must be explicitly allowed for the show file if drivers or scripts are used.

### Cited Findings
- Auto Save writes a temporary backup to the Temporary Directory every "Timer (Minutes)"; intended for crash recovery ([Manual 5.2, Save & Load](https://docs.blender.org/manual/en/latest/editors/preferences/save_load.html)).
- Save Versions default 2 (`.blend1`, `.blend2`) ([Manual 5.2, Save & Load](https://docs.blender.org/manual/en/latest/editors/preferences/save_load.html)).
- Python scripts, including driver expressions, do not auto-run by default for security; "Excluded Paths" exists ([Manual 5.2, Save & Load](https://docs.blender.org/manual/en/latest/editors/preferences/save_load.html)).
- Undo Steps and Global Undo are configurable; disabling Global Undo saves memory but breaks Adjust Last Operation, and the manual recommends keeping it on for editing. Undo Memory Limit 0 is unlimited ([Manual 5.2, System prefs](https://docs.blender.org/manual/en/latest/editors/preferences/system.html)).
- Threads that outlive the script can crash Blender's drawing code ([API threading gotchas](https://docs.blender.org/api/current/info_gotchas_threading.html)).
- After a package uninstall, Blender must restart for TextureSharing UI to update; an earlier 4.2.2 change removed the add-on's install button, requiring manual install ([TextureSharing README](https://github.com/maybites/TextureSharing); [VIDVOX forum 2024](https://discourse.vidvox.net/t/blender-texture-sharing-syphon-spout-and-ndi/2397)).
- Metal-specific failures exist: shaders failing to compile on Metal but fine on OpenGL, magenta world shaders with Attribute node on M1/M2, PSO creation failures ([Issue #106304](https://projects.blender.org/blender/blender/issues/106304); [Issue #112952](https://projects.blender.org/blender/blender/issues/112952); [Issue #116414](https://projects.blender.org/blender/blender/issues/116414)).
- Engine identifier changed from `BLENDER_EEVEE_NEXT` to `BLENDER_EEVEE` in 5.0, breaking scripts that set the engine by name ([5.0 EEVEE release notes](https://developer.blender.org/docs/release_notes/5.0/eevee/)).
- Curves now respect the `resolution` attribute in 5.0; default hair renders 15x more geometry than 4.5, a hidden performance trap for files migrated from older versions ([5.0 EEVEE release notes](https://developer.blender.org/docs/release_notes/5.0/eevee/)).

### Inferences
- Show preferences profile (use a separate `BLENDER_USER_CONFIG`/portable config so the show machine does not share prefs with editing work): Auto Save off (the periodic write is a likely hitch source), Undo Steps low (e.g. 0 to 4) since OSC-driven property changes during a show should not accumulate undo memory, Texture/VBO Time Out 0, Save Versions irrelevant (never save during show).
- Note: property changes made by Python/OSC typically do not push undo steps unless operators are called; prefer direct property writes over `bpy.ops` in the OSC handler. Not verified by a source.
- Allow auto-run only for the show folder (trusted path) rather than globally, if drivers are required.
- Crash plan: SwiftVJ should treat the Blender Syphon source as optional. On source disappearance, fall back to a local clip layer, then relaunch Blender with the show file via a launcher script (`blender show.blend --python warmup.py`) that re-runs warm-up and re-announces the Syphon server. Cold start includes shader compilation, so budget tens of seconds before the layer is usable.
- Pin Blender and add-on versions for the tour; freeze the add-on set to what was rehearsed. Validate the file in 5.2.3 specifically (identifier and curve-resolution changes above show 5.x breaks old assumptions).
- Keep a pre-rendered clip of each Blender scene in SwiftVJ as a hot backup.

### Gaps
- No primary source on whether Auto Save causes measurable viewport hitches (strong practitioner folklore, not found documented).
- No data on Blender 5.2.3 crash rates on Metal in long-running sessions (hours of continuous Rendered viewport).
- Default values for Undo Steps, Auto Save timer and Texture Time Out were not stated on the fetched manual pages.

## 4. Integration with VJ hosts and lighting consoles: Syphon/NDI source layer, tempo sync, cueing from external triggers

### Takeaway
The established pattern is Blender as a camera-driven Syphon (macOS) or Spout/NDI source layer inside a host (Resolume, VDMX, here SwiftVJ), with OSC into Blender for parameters and scene cues. No native Blender tempo/BPM sync exists; tempo must arrive over OSC (or be derived in the host) and be mapped to properties or frame rate.

### Cited Findings
- TextureSharing shares camera output "as a live-performing media and instrument"; Resolume Arena receives it under Sources; "Flip texture" needed for Spout to Resolume ([VIDVOX forum 2024](https://discourse.vidvox.net/t/blender-texture-sharing-syphon-spout-and-ndi/2397)).
- VDMX users confirm V9 Syphon works with Blender 5+ ([VIDVOX forum V9](https://discourse.vidvox.net/t/texture-sharing-add-on-v9-0-0-for-blender-5-x-upwards/8924)).
- VDMX ingests Syphon sources as live feeds, a common route for external renders into a show ([VIDVOX VVEDU Module 6](https://vidvox.github.io/vvedu/teaching_module_6.html)).
- OSC Controller add-on (commercial, Blender 4.0+) maps UDP OSC to shape keys, cameras, lights, shader params and Geometry Nodes, from TouchDesigner, Pure Data, Max or MIDI-to-OSC bridges, and can record performance into the timeline via Auto Key ([Superhive OSC Controller](https://superhivemarket.com/products/osc-controller)).
- Precedent pattern (non-Blender): Ableton to MIDI to Processing to Syphon to Resolume, with 6 scenes switched by OSC messages that change scenes, clear screen, move camera ([Processing forum](https://forum.processing.org/two/discussion/comment/60193/)).
- Older precedent: a 2012 generative set used Jitter plus Syphon mixers with OSC control from performers' laptops ([CDM](https://cdm.link/live-set-of-the-week-generative-set-telematique-u-matic-sascha-funke-audionite-in-nantes-jitter-syphon/)).

### Inferences
- For SwiftVJ: treat Blender as one Syphon layer per instance. SwiftVJ owns the clock and sends OSC: `/scene <name>` (cue), `/param/<name> <float>` (continuous), `/beat` or `/bpm <float>` + `/phase <0..1>` (tempo). Blender maps beat phase to a custom property that drivers/geometry nodes read; this avoids depending on Blender's timeline fps for tempo.
- Cue latency budget: OSC receive (timer-polled) + depsgraph update + next redraw + Syphon publish, roughly 1 to 3 frames if the timer runs at frame rate. Scene cues that hit an un-warmed scene will instead stall for shader compile.
- Lighting consoles: consoles typically speak sACN/Art-Net or OSC; route them through SwiftVJ (or a bridge) rather than having Blender listen to DMX, keeping Blender's input surface to one OSC port.
- If a scene crossfade is needed, do it in SwiftVJ between two Syphon sources (two Blender instances, or Blender + clip), since an in-Blender cut via `window.scene` is a hard cut.

### Gaps
- No source on Ableton Link or MIDI clock directly in Blender 5.x.
- No source on MadMapper specifically ingesting Blender Syphon (expected to work as a generic Syphon client, unverified).
- No measured end-to-end latency figures for OSC-to-Syphon round trip in Blender.

## 5. Real-world performer reports: what broke, what worked, hardware/settings (Apple Silicon)

### Takeaway
Public reports of Blender used as a live real-time VJ engine are scarce. Most working VJs use Blender to pre-render clips and play them in a host; those who tried real-time EEVEE hit FPS limits and moved to TouchDesigner or similar. The 2026 TextureSharing V9 reports are the first positive "it works" signals for Blender 5, but no Apple Silicon FPS numbers were found.

### Cited Findings
- 2022 forum thread: the OP tested EEVEE for real-time audio-synced loops (GTX 750 Ti, Audvis add-on), hit low FPS with subdivided geometry despite GPU Subdivision, and moved to TouchDesigner ([BlenderArtists thread](https://blenderartists.org/t/is-anyone-using-blender-as-a-vj-tool/1387361)).
- Same thread: Armature and Subdivision modifiers and particle systems are FPS costs; suggestion to use displacement-based planes and Geometry Nodes instancing; claim EEVEE is not truly real-time in practice ([BlenderArtists thread](https://blenderartists.org/t/is-anyone-using-blender-as-a-vj-tool/1387361)).
- Same thread: a working video DJ renders MP4s in Blender and performs them in Serato/MixEmergency, "static but reliable" ([BlenderArtists thread](https://blenderartists.org/t/is-anyone-using-blender-as-a-vj-tool/1387361)).
- TextureSharing tips: keep viewport render samples low (about 24 to 56), avoid complex lighting and particles; author expected an RTX 3080-class GPU for real-time; no Apple measurements ([VIDVOX forum 2024](https://discourse.vidvox.net/t/blender-texture-sharing-syphon-spout-and-ndi/2397)).
- A VJ YouTube channel describes using Blender with Resolume for live show visuals (content creation, not real-time output) ([Conrad Hellman YouTube](https://m.youtube.com/@ConradHellman)).
- 5.0 optimized Workbench and Overlay mesh instancing for up to 3x higher fps with many instances ([5.0 EEVEE release notes](https://developer.blender.org/docs/release_notes/5.0/eevee/)).
- Workbench/Solid mode is also the only mode where TextureSharing transparency works ([TextureSharing README](https://github.com/maybites/TextureSharing)).

### Inferences
- Design content for real-time: low EEVEE sample counts (viewport samples 1 to 16 for live, accept noise or use Workbench/Solid for stylized looks), no volumetrics/raytracing unless tested, baked lighting, Geometry Nodes instancing over particles, avoid modifier stacks evaluated per frame.
- Render at a reduced Syphon resolution (e.g. 1280x720) and let SwiftVJ upscale; resolution is set in the share panel.
- Keep a hybrid workflow: real-time Blender for a few hero interactive scenes, pre-rendered HAP/ProRes clips for the rest.
- M1 Max specifics (unverified by sources): Metal-only backend, no shader subprocess option, unified memory. Expect cold-start compile delays and test thermal behavior over a full set length.

### Gaps
- No Apple Silicon (M1 Max or later) FPS benchmarks for EEVEE in Blender 5.x found.
- No Blender Conference talk specifically on live VJ use found (searched; only adjacent real-time talks).
- No VJ Union or Resolume forum threads with detailed Blender live-show postmortems found.
