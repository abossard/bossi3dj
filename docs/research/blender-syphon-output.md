# Sending Eevee frames out of Blender over Syphon

Research for issue #2. Question: how live Eevee output leaves Blender as a Syphon texture on Apple Silicon so `SyphonReceiver` (`Sources/SyphonKit/SyphonReceiver.swift`, wraps `SyphonMetalClient`) can ingest it.

- Researched 2026-11-03.
- Host: Apple M1 Max, Blender 5.2.3 LTS (`/Applications/Blender.app`, build 2026-10-22, bundled Python 3.13).
- Labels: **Fact** (read in a primary source), **Measured** (local probe, see [Local probes](#local-probes)), **Inference**, **Recommendation**.

## Answer

- **Recommendation:** use the TextureSharing add-on (maybites/TextureSharing v9.1.1) for the first integration. It publishes a camera's Eevee view as a `SyphonMetalServer` that SwiftVJ's existing `SyphonReceiver` can discover by server name (the camera name). No SwiftVJ code change is needed.
- **Recommendation:** expect a CPU round trip, not zero copy. Every Python path reads the Blender GPU texture to CPU and uploads it into a new `MTLTexture`. Budget roughly 1080p at 30 fps for real scenes on Apple Silicon. 4K is feasible only for light scenes.
- **Recommendation:** if a windowless "render node" Blender is wanted later, a small custom script on Blender 5.2's new `gpu.init()` can render Eevee into a `GPUOffScreen` in `--background` mode (measured working). It must pump the main run loop for Syphon discovery (unverified).
- **Recommendation:** NDI/OMT is a fallback only. SwiftVJ has no NDI receiver today, and these paths add CPU encode on top of the same readback.

## Approaches

### A. TextureSharing add-on (Syphon, NDI, OMT)

- **Fact:** latest release v9.1.1 (2026-10-07), targets "Blender 5.x upwards"; v9.0.3 (2026-08-25) fixed "Blender 5.2 texture readback corruption". ([README](https://github.com/maybites/TextureSharing/blob/master/README.md), [releases](https://github.com/maybites/TextureSharing/releases))
- **Fact:** README status on macOS: Syphon Metal server and OpenGL server working, Metal client "⚠️", OpenGL client not implemented. ([README](https://github.com/maybites/TextureSharing/blob/master/README.md))
- **Fact:** not in Blender's extension repository. Install from the release zip via Preferences > Add-ons > Install from Disk. It installs `syphon-python==0.2.0` (plus optional PyOpenGL), `cyndilib==0.0.5`, `cyomtlib==0.1.2` into Blender's Python with pip from a button. ([`__init__.py`](https://github.com/maybites/TextureSharing/blob/master/__init__.py))
- **Fact:** sharing is configured per Camera object (Properties > Camera > "Share texture"): capture width/height, workspace, scene, view layer, color management, transparent background, vertical flip, preview. Server name defaults to the camera name. ([README](https://github.com/maybites/TextureSharing/blob/master/README.md), [`operators.py`](https://github.com/maybites/TextureSharing/blob/master/operators.py))
- **Fact:** mechanism ([`operators.py`](https://github.com/maybites/TextureSharing/blob/master/operators.py)):
  - registers `SpaceView3D.draw_handler_add(..., 'WINDOW', 'POST_PIXEL')`, so a frame is captured only when a 3D viewport redraws;
  - inside the handler it calls `GPUOffScreen.draw_view3d(scene, layer, space, region, view_matrix, projection_matrix, do_color_management=..., draw_background=...)` with the camera's matrices. The render engine and shading come from the chosen workspace's 3D view `space`, so Eevee output needs that viewport in Rendered shading;
  - README: without steady stream "a frame is only sent when the viewport redraws"; steady stream exists for NDI and OMT only.
- **Fact:** Metal backend send path ([`fbs/syphon/SyphonMetalServer.py`](https://github.com/maybites/TextureSharing/blob/master/fbs/syphon/SyphonMetalServer.py)):
  - `offscreen.texture_color.read()` (GPU to CPU);
  - `copy_bytes_to_mtl_texture` (`MTLTexture.replaceRegion`, CPU to GPU) into an `RGBA8Unorm` texture created by `syphon-python` on `MTLCreateSystemDefaultDevice()`;
  - `publish_frame_texture(...)`, which commits and waits until submitted. ([`syphon/utils/raw.py`](https://github.com/cansik/syphon-python/blob/main/syphon/utils/raw.py), [`syphon/server.py`](https://github.com/cansik/syphon-python/blob/main/syphon/server.py))
- **Fact:** backend selection: `gpu.platform.backend_type_get()` is `METAL` → `SyphonMetalServer`, `OPENGL` → `SyphonOpenGLServer` (direct GL texture publish, no readback). ([`fbs/FrameBufferSharingServer.py`](https://github.com/maybites/TextureSharing/blob/master/fbs/FrameBufferSharingServer.py))
- **Inference:** the capture renders the scene a second time at capture resolution, on top of the visible viewport's own draw. GPU cost is roughly doubled versus just viewing.
- **Inference:** Syphon frame rate is capped by viewport redraw rate. During animation playback that is the scene fps. When the scene is idle and nothing redraws, the receiver sees no new frames (SwiftVJ keeps the last one).

### B. Custom script: headless Eevee offscreen + syphon-python

- **Fact:** Blender 5.2 added "`gpu.init()` to initialize gpu backend when running Blender in background mode `--background`." ([5.2 Python API notes](https://developer.blender.org/docs/release_notes/5.2/python_api/))
- **Measured:** in `--background --factory-startup`, without `gpu.init()` any `GPUOffScreen` raises "GPU functions for drawing requires the gpu module to be initialized". After `gpu.init()` the backend reports `METAL / APPLE / Metal API 1.2`.
- **Measured:** `draw_view3d` requires a `SpaceView3D` (passing `None` raises TypeError). The SpaceView3D and WINDOW region stored in the file's `Layout` screen work headless. With `space.shading.type = 'RENDERED'`, Eevee output is correct (red world test colour appears in the frame).
- **Measured:** Eevee shaders compile asynchronously. The first headless draws showed a Workbench-like image. After about 30 draws with short sleeps, the real Eevee image appeared.
- **Fact:** the Syphon Metal server takes any `MTLTexture` and copies it ("The texture is copied and can be safely modified once this method has returned"), and is thread safe. ([SyphonMetalServer.h](https://github.com/Syphon/Syphon-Framework/blob/main/SyphonMetalServer.h))
- **Fact:** Syphon discovery uses `NSDistributedNotificationCenter`. Servers observe `SyphonServerAnnounceRequest` and answer with an announce. ([SyphonServerBase.m](https://github.com/Syphon/Syphon-Framework/blob/main/SyphonServerBase.m))
- **Inference:** in `--background` a Python frame loop blocks the main thread, so distributed notifications are not delivered. A client started after the server may not discover it. Pumping `NSRunLoop.currentRunLoop().runUntilDate_(...)` each frame should fix it. This was not verified because installing PyObjC into Blender's Python was out of scope.
- **Inference:** the loop drives time itself (`scene.frame_set` or property changes from OSC), so frame rate is set by the script, not by window redraws.

### C. Zero copy (Blender `MTLTexture` straight into Syphon)

- **Measured:** `gpu.types.GPUTexture` in 5.2.3 exposes only `anisotropic_filter, clear, extend_mode*, filter_mode, format, height, mipmap_mode, read, width`. It has no native handle (no `bindcode`, no `MTLTexture` pointer).
- **Fact:** the old OpenGL zero-copy route is gone on macOS: "On macOS only Metal is supported now, and the OpenGL backend has been removed" (Blender 4.0). ([4.0 release notes](https://developer.blender.org/docs/release_notes/4.0/))
- **Inference:** zero copy needs a C++ change to Blender, either exposing the Metal texture or adding a built-in Syphon output. No such work was found. The Blender tracker's issue search API returned no relevant hits for "syphon", and the web UI was not reachable (HTTP 403).

### D. NDI / OMT fallback

- **Fact:** TextureSharing NDI and OMT senders work on all platforms and support steady stream. NDI uses `cyndilib` and does the same `texture.read()`, then numpy flip and flatten on the CPU before sending. ([README](https://github.com/maybites/TextureSharing/blob/master/README.md), [`fbs/ndi/NDIServer.py`](https://github.com/maybites/TextureSharing/blob/master/fbs/ndi/NDIServer.py))
- **Fact:** `cyndilib==0.0.5` ships `cp313 macosx_11_0_arm64` wheels, which match Blender 5.2's Python 3.13. ([PyPI](https://pypi.org/project/cyndilib/0.0.5/))
- **Fact:** SwiftVJ has no NDI or OMT receiver (`grep` of `Sources/` finds none). Using NDI means new SwiftVJ code or an external NDI-to-Syphon bridge.
- **Inference:** NDI adds compression and network-stack latency over Syphon. Only worth it if Blender runs on another machine.

### E. Final render (F12) per frame

- **Measured:** `bpy.ops.render.render()` with Eevee at 720p and 1 sample, default cube: about 135 ms per frame (about 7 fps). This is not a live path.

## Performance

- **Measured** (M1 Max, default cube, Eevee Rendered, overlays off, headless `draw_view3d` then `texture_color.read()`; the read includes the GPU sync):

| Resolution | draw submit | read incl. GPU wait | Upper-bound fps before Syphon upload |
|---|---|---|---|
| 1280x720 | 1.0 ms | 11.4 ms | ~80 |
| 1920x1080 | 1.0 ms | 24.0 ms | ~40 |
| 3840x2160 | 1.3 ms | 44.5 ms | ~22 |

- **Measured:** pure readback of an already finished RGBA8 offscreen takes 1.1 ms (720p), 1.6 ms (1080p) and 5.4 ms (4K). So most of the cost above is Eevee GPU time, not the copy. Unified memory keeps the readback cheap.
- **Fact:** the offscreen format is `RGBA8` (8-bit, display-referred when `do_color_management=True`). TextureSharing therefore delivers 8-bit SDR, not float or HDR. (Measured `texture_color.format`; [`raw.py`](https://github.com/cansik/syphon-python/blob/main/syphon/utils/raw.py) creates `RGBA8Unorm`.)
- **Inference:** real scenes cost more GPU time than the default cube. In UI mode the viewport also renders the scene a second time. Plan on 1080p30 as the safe target and 1080p60 only for light scenes.
- **Inference:** latency is about 1 frame. Readback blocks until the GPU finishes, then the upload and Syphon blit go to a new command buffer. SwiftVJ receives the frame on its `newFrameHandler`, one display frame later at most. Not measured end to end.
- **Inference:** Eevee viewport renders one TAA sample per redraw while the scene changes, so moving content looks noisier or more aliased than a final render. Raising viewport samples does not help during motion.

## Blender version and backend

- **Fact:** macOS Blender is Metal-only since 4.0. Metal 2.2 GPU required. ([4.0 release notes](https://developer.blender.org/docs/release_notes/4.0/))
- **Fact:** TextureSharing `bl_info` claims Blender 3.0 minimum, but the README and release titles target 5.x. v4.0.0 (2023-12-20) first supported "4.x on OSX using Metal Backend". ([releases](https://github.com/maybites/TextureSharing/releases))
- **Fact:** `syphon-python` 0.2.0 (2026-10-07) is a pure `py3-none-macosx_12_0_universal2` wheel built on PyObjC 12.2, needs Python ≥3.10 and macOS 12 or later. ([README](https://github.com/cansik/syphon-python/blob/main/README.md), [PyPI](https://pypi.org/project/syphon-python/0.2.0/))
- **Measured:** installed Blender 5.2.3 runs Eevee (`BLENDER_EEVEE` is the only Eevee enum id) on Metal.
- **Implication:** the OpenGL server branch in TextureSharing is dead code on current macOS Blender. Every Mac path is Metal plus readback.

## Must Blender keep a visible window?

- **Fact (add-on, UI mode):** yes, effectively. Capture runs in a `SpaceView3D` draw handler, so a window containing a 3D viewport of the configured workspace must be open and redrawing. ([`operators.py`](https://github.com/maybites/TextureSharing/blob/master/operators.py))
- **Unknown:** whether a minimized, occluded or other-Space window keeps redrawing on macOS (App Nap, occlusion throttling). The README is silent. Test before relying on it in a show.
- **Measured (custom script, background):** no window is needed. `blender --background file.blend --python script.py` plus `gpu.init()` renders Eevee offscreen. This requires Blender 5.2 or later, because earlier versions have no `gpu.init()`.

## Open questions that could change the recommendation

- Does headless Syphon discovery work without pumping the run loop? If not, how often must it be pumped?
- Does a TextureSharing server keep streaming when its Blender window is minimized or behind SwiftVJ fullscreen output?
- Do real show scenes hold 1080p at 30 or 60 fps on the target Mac with double rendering in UI mode?
- Does SwiftVJ need alpha? TextureSharing transparency "seems to work only for 'Display in solid mode'" (README).
- Does SwiftVJ's `SyphonReceiver` need a flip? TextureSharing exposes a per-camera flip toggle.

## Local probes

- All probes ran `/Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup --python <probe>.py` from the session scratchpad. Nothing was installed, and user prefs and add-ons were not loaded.
- Probes covered:
  - `gpu.platform.*` before and after `gpu.init()`;
  - `dir()` of `GPUTexture` and `GPUOffScreen`;
  - `GPUOffScreen(w, h)` + `texture_color.read()` timing after `fb.clear`;
  - `draw_view3d` with the `Layout` screen's `SpaceView3D` and WINDOW region in SOLID, MATERIAL and RENDERED shading, with a red world colour to confirm Eevee;
  - `bpy.ops.render.render()` timing.
