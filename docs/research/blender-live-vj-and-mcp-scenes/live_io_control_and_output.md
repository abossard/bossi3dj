# Live control input and video output for Blender as a VJ engine

Scope: driving a running Blender 5.2.3 LTS scene from external show software, and getting frames out live, on macOS Apple Silicon. Researched 2026-11-03. Builds on three earlier project notes (cited below as "project note"), which contain local measurements on an M1 Max with Blender 5.2.3:
- Live control: `swift-vj-worktrees/research-blender-live-control/docs/research/blender-live-control.md`
- Syphon output: `swift-vj-worktrees/research-blender-syphon-output/docs/research/blender-syphon-output.md`
- Beat sources: `swift-vj-worktrees/research-live-beat-sources/docs/research/live-beat-sources.md`

Nothing was installed. Add-on code was read through `gh api` and the Blender Extensions API (`extensions.blender.org/api/v1/extensions/`, 1608 entries on 2026-11-03).

## Control input: OSC, MIDI, DMX/Art-Net/sACN, Ableton Link, custom sockets (which are maintained for Blender 5.x?)

### Takeaway
Every ready-made input add-on works by running a Python receive thread and draining it on the main thread. Blender's docs say such threads are unsupported. None of the OSC add-ons is on the official Extensions platform with 5.x support stated. BlenderDMX (Art-Net/sACN) and the two MIDI extensions are the actively maintained 5.x options. For show use, a small custom extension that polls a non-blocking UDP socket from one `bpy.app.timers` callback is still the most robust OSC path. Ableton Link can be read inside Blender with aalink by polling `link.beat`/`link.phase`, but it needs an asyncio loop object handed to it.

### Cited Findings

OSC
- NodeOSC (maybites): latest release v2.4.4 on 2026-06-05, GPL-3.0, 158 stars, not archived — [GitHub API, maybites/NodeOSC](https://github.com/maybites/NodeOSC)
- NodeOSC is a legacy `bl_info` add-on (`blender: (2, 80, 0)`) with no extension manifest and no stated 5.x support. It receives on an oscpy `OSCThreadServer` or python-osc thread, puts messages in a LIFO queue and drains it in `bpy.app.timers`. It uses `eval`/`exec` on data paths and does not call `update_tag` after writing custom properties — [project note, live control](https://github.com/maybites/NodeOSC)
- NodeOSC is not listed on extensions.blender.org (no OSC add-on of its name in the Extensions API dump of 1608 entries) — [Extensions API](https://extensions.blender.org/api/v1/extensions/)
- AddRoutes: upstream JPfeP/AddRoutes last pushed 2022-03-14 (115 stars, "Blender 2.8"). The slashv fork released v0.33.0 "Blender 4.2 support" on 2024-12-07 and has not been pushed since. It has an extension manifest with `blender_version_min = "4.2.0"` and handles OSC, MIDI and an Android app — [JPfeP/AddRoutes](https://github.com/JPfeP/AddRoutes), [slashv/AddRoutes](https://github.com/slashv/AddRoutes)
- AddRoutes receives with an oscpy server, drains a list queue in `bpy.app.timers` (`refresh` default 1 ms, `overflow` 200 events per cycle) — [project note, live control](https://github.com/slashv/AddRoutes)
- VMC Link 0.4.0 (maintainer "Internet-Addict") is on the Extensions platform as an OSC/VMC receiver for armatures and shape keys, with `network = "Receive OSC / VMC motion data over UDP"`, `blender_version_min 4.2.0`. It is motion-capture specific, not general OSC mapping — [Extensions API](https://extensions.blender.org/add-ons/vmc-link/)
- A paid "OSC Controller for Blender" on Superhive claims Blender 4.0+ support, an extension manifest for 4.2+, and a fix for "Geometry Nodes inputs on Blender 5.x". Not verified against code — [Superhive listing](https://superhivemarket.com/products/osc-controller), [versions](https://superhivemarket.com/products/osc-controller/versions)

MIDI
- MidiController (maintainer Eldin-Zenderink) 0.1.7 on the Extensions platform, `blender_version_min 4.2.0`, per-platform builds for macos-arm64, macos-x64, linux-x64 and windows-x64. The 0.1.7 release (2026-04-09) added Blender 5.1 support. It maps MIDI controls to object properties including geometry nodes inputs, and can insert keyframes — [Extensions API](https://extensions.blender.org/add-ons/midicontroller/), [versions](https://extensions.blender.org/add-ons/midicontroller/versions/)
- SimpleMIDI (maintainer yadu) 0.1.14 on the Extensions platform, `blender_version_min 4.2.0`, builds for linux-x64, macos-arm64, macos-x64, windows-x64. 0.1.14 (2026-06-12) added wheels "so it should now work on 5.1" — [Extensions API](https://extensions.blender.org/add-ons/simplemidi/), [versions](https://extensions.blender.org/add-ons/simplemidi/versions/)
- KeyCraft MIDI 1.4.0 (live MIDI keyboard animation) and MIDI-file tools (M2V, NLA Midi Copier, MIDIAnimator) exist, but they animate from MIDI notes or files, not general parameter control — [Extensions API](https://extensions.blender.org/api/v1/extensions/), [MIDIAnimator](https://github.com/jamesa08/MIDIAnimator)

DMX / Art-Net / sACN input (BlenderDMX)
- BlenderDMX (open-stage): GitHub release v2.3.1 on 2026-10-04, v2.3.0 on 2026-07-03, last push 2026-11-03, GPL-3.0-or-later, 290 stars. The Extensions platform still lists 2.2.4 (maintainer "Sunova") — [GitHub API, open-stage/blender-dmx](https://github.com/open-stage/blender-dmx), [Extensions page](https://extensions.blender.org/add-ons/open-stage-blender-dmx/)
- Manifest: `blender_version_min = "4.2.0"`, tagline "Visualization & programming with GDTF&MVR, OSC, PSN, Networking", network permission "For GDTF Share, sACN, Sinette, Art-Net, OSC, PSN, MVR-xchange". Bundled wheels include pygdtf 1.4.5, pymvr 1.0.7, sacn 1.9.1, oscpy 0.6.0, pypsn 0.2.3 — [blender_manifest.toml](https://github.com/open-stage/blender-dmx/blob/main/blender_manifest.toml)
- README: "4.2 or higher installed, latest tested is 5.0" — [README](https://github.com/open-stage/blender-dmx/blob/main/README.md)
- Art-Net input is a `threading.Thread` bound to UDP 6454 with `SO_BROADCAST`, `SO_REUSEADDR` and (since 2.3.1) `SO_REUSEPORT` "so a console on the same machine can share port 6454". It answers ArtPoll with ArtPollReply. It does not check universe subscription ("we are not checking if we are actually subscribed to the universe") — [artnet.py](https://github.com/open-stage/blender-dmx/blob/main/artnet.py), [v2.3.1 release notes](https://github.com/open-stage/blender-dmx/releases/tag/v2.3.1)
- sACN input uses the `sacn` library's `sACNreceiver` (its own receive thread, "start the receiving thread"), joins one multicast group per universe set to input "sACN", and skips universe 0 — [acn.py](https://github.com/open-stage/blender-dmx/blob/main/acn.py)
- BlenderDMX OSC is output only: it starts an oscpy `OSCThreadServer` on 0.0.0.0:8000 with the comment "If we have for OSC input in the future, we should make port and root path configurable" — [osc.py](https://github.com/open-stage/blender-dmx/blob/main/osc.py)
- Received DMX goes into `DMX_Data` bytearrays. The scene is updated from a `bpy.app.timers` callback `run_render` that returns `1.0 / 24`, so fixtures are applied at 24 Hz regardless of input rate. The timer stays registered while Art-Net, sACN, Sinette or PSN is enabled — [dmx.py](https://github.com/open-stage/blender-dmx/blob/main/dmx.py)
- 2.3.1 also "cap strobe to fps/2" and added "Initial support for Sinette protocol - a very simple plain data receiver" — [v2.3.1 release notes](https://github.com/open-stage/blender-dmx/releases/tag/v2.3.1)
- `data.py` comments that `tag_redraw()` from another thread "doesn't work", and that an empty `update=` callback on the DMX value property makes the UI refresh — [data.py](https://github.com/open-stage/blender-dmx/blob/main/data.py)

Ableton Link (aalink)
- aalink 0.2.3 (PyPI, 2026-07-03), GPL-3.0, repo last pushed 2026-10-04. PyPI ships `cp313-cp313-macosx_11_0_arm64` wheels, matching Blender 5.2's bundled Python 3.13 — [PyPI JSON](https://pypi.org/pypi/aalink/json), [artfwo/aalink](https://github.com/artfwo/aalink)
- README: "a Python wrapper for Ableton Link built for interactive applications using asyncio event loops"; `await link.sync(n)` resolves at the next n-th beat; timing "not 100% accurate due to the processing delay in the internal scheduler" (example: returned at beat 1.00190) — [README](https://github.com/artfwo/aalink/blob/master/README.rst)
- Bindings expose read-only `beat`, `phase`, `time`, `num_peers` and read/write `tempo`, `quantum`, `enabled`, `playing`, `start_stop_sync_enabled`. `Link(bpm, loop=None)` calls `asyncio.get_running_loop()` when no loop is given; passing `loop` is deprecated. A C++ scheduler thread polls every 1 ms and calls `loop.call_soon_threadsafe` — [src/aalink.cpp](https://github.com/artfwo/aalink/blob/master/src/aalink.cpp)
- No Blender add-on wrapping aalink or Link was found in search or in the Extensions API — [web search results](https://pypi.org/project/aalink/), [Extensions API](https://extensions.blender.org/api/v1/extensions/)

Custom socket on `bpy.app.timers` (from project note, measured on 5.2.3)
- Blender docs: Python threads "cause Blender to crash in hard to diagnose ways" unless the main thread is blocked joining them — [info_gotchas_threading](https://docs.blender.org/api/current/info_gotchas_threading.html)
- A timer returning `0.0` ran about 170 to 175 ticks/s idle, and 94 to 118 ticks/s when each tick requested a redraw. A non-blocking UDP socket drained in that timer received 1352 of 1360 datagrams at about 750 msg/s on localhost — [project note, live control](https://docs.blender.org/api/current/bpy.app.timers.html)
- Blender Lab's official MCP add-on uses a non-blocking TCP server polled from `bpy.app.timers` at 0.05 s active, 1.0 s idle — [mcp_to_blender_server.py](https://projects.blender.org/lab/blender_mcp/src/branch/main/addon/blender_mcp_addon/mcp_to_blender_server.py)

### Inferences
- Maintained for 5.x: BlenderDMX (active, tested to 5.0 per README, code current), MidiController and SimpleMIDI (5.1 support stated), aalink (library, 3.13 wheels). Not maintained for 5.x: AddRoutes (both repos idle since 2024 or earlier). NodeOSC is maintained (2026-06 release) but ships no manifest and states no 5.x support.
- Because aalink's `beat`/`phase` are plain properties, a Blender timer can read them each tick without running the asyncio loop. A loop object must still be supplied (for example `asyncio.new_event_loop()`), which triggers a DeprecationWarning. Calls to `sync()` would never resolve unless that loop is stepped. Not tested.
- aalink and BlenderDMX both run native or Python threads. aalink's threads are C++ and only touch Python through `call_soon_threadsafe` (needs the GIL). BlenderDMX's Art-Net and sACN threads only write bytearrays, and all `bpy` writes happen in the 24 Hz timer. This is the "thread plus main-thread drain" pattern Blender calls unsupported, but it keeps `bpy` access on the main thread.
- GPL: aalink is GPL-3.0 and BlenderDMX, NodeOSC are GPL. Inside Blender (itself GPL) this is fine; it matters only if code is copied into SwiftVJ.

### Gaps
- MidiController and SimpleMIDI source was not read (their repos were not found on GitHub; downloading the zips was out of scope). Their MIDI backend (likely python-rtmidi), threading model and 5.2 status are unverified.
- No add-on states verified support for Blender 5.2 specifically. Whether NodeOSC and AddRoutes still load on 5.2.3 was not tested (no install allowed).
- aalink inside Blender is untested; whether the C++ scheduler thread interacts badly with Blender's GIL handling is unknown.
- The paid Superhive OSC Controller was not inspected.

## Blender as a "virtual fixture" driven by a lighting console such as QLC+

### Takeaway
Two working routes exist. Art-Net or sACN from QLC+ into BlenderDMX gives GDTF-defined fixtures with 16-bit channel support, but BlenderDMX applies values at 24 Hz. QLC+ OSC output goes to `/<universe-1>/dmx/<channel-1>` as one float datagram per changed channel, only on change, 8-bit resolution (`value/255`). That works with NodeOSC or a custom receiver, but 16-bit channels arrive as two separate, non-atomic messages.

### Cited Findings
- QLC+ OSC output path: "/QLC+ universe - 1/dmx/DMX channel - 1", e.g. channel 12 of universe 4 is `/3/dmx/11`. "All the values transmitted by the OSC plugin use the float type." Output ports start at 9000 plus universe minus one; input ports at 7700 plus universe minus one — [QLC+ OSC plugin docs](https://docs.qlcplus.org/v4/plugins/osc)
- QLC+ source: `setupOSCDmx` builds `/%1/dmx/%2` with type tag `,f` and value `(float)value / 255.f`. `sendDmx` compares each channel with a cached copy and sends one datagram per channel only when it changed — [oscpacketizer.cpp](https://github.com/mcallegari/qlcplus/blob/master/plugins/osc/oscpacketizer.cpp), [osccontroller.cpp](https://github.com/mcallegari/qlcplus/blob/master/plugins/osc/osccontroller.cpp)
- QLC+ Art-Net modes: Standard sends "only when at least one DMX channel changes or every 2 seconds"; Full sends all 512 channels "at the speed rate of the QLC+ internal clock (50Hz)"; Partial sends only channels in use. Port 6454, broadcast by default, unicast when the address is 1 to 254 — [QLC+ Art-Net plugin docs](https://docs.qlcplus.org/v4/plugins/art-net)
- QLC+ latest release QLC+_5.3.0 on 2026-10-05 (5.2.2 on 2026-06-13). QLC+ plugins include E1.31 (sACN), artnet, osc, os2l, midi, loopback — [GitHub API, mcallegari/qlcplus](https://github.com/mcallegari/qlcplus/releases)
- BlenderDMX fixture definitions come from GDTF (GDTF Share library) via pygdtf, plus MVR scene import/export via pymvr — [README](https://github.com/open-stage/blender-dmx/blob/main/README.md)
- BlenderDMX reads multi-byte channels: `offsets_bytes` per channel, coarse plus fine for "classic 16-bit", and 24/32-bit channels trimmed to 16-bit ("TODO: fix this properly, here we trim to 16bit, to prevent crash with 24/32bit channels") — [fixture.py](https://github.com/open-stage/blender-dmx/blob/main/fixture.py)
- BlenderDMX 2.3.1 added `SO_REUSEPORT` on the Art-Net socket because "a console already bound to 6454 on the same machine (QLC+, Qt sets it) makes this bind fail with EADDRINUSE" — [artnet.py](https://github.com/open-stage/blender-dmx/blob/main/artnet.py)
- BlenderDMX applies received DMX in a 24 Hz timer (`return 1.0 / 24`) — [dmx.py](https://github.com/open-stage/blender-dmx/blob/main/dmx.py)
- BlenderDMX also receives PSN (PosiStageNet) tracking and Sinette, and speaks MVR-xchange — [blender_manifest.toml](https://github.com/open-stage/blender-dmx/blob/main/blender_manifest.toml)

### Inferences
- Running QLC+ and BlenderDMX on the same Mac needs BlenderDMX 2.3.1 or later (GitHub), not the 2.2.4 on the Extensions platform, because of the port 6454 fix. Unicast to 127.0.0.1 or loopback broadcast behaviour on macOS was not checked.
- For a "Blender as fixture" approach, the simplest fixture definition is a custom GDTF (or a QLC+ fixture definition on the console side) whose channels are abstract parameters (e.g. "Hue", "Speed", "Scene select") rather than real lamp attributes. BlenderDMX maps GDTF attributes to its own fixture models, so arbitrary scene parameters would still need a custom mapping layer. No published example of Blender as an abstract VJ fixture was found.
- QLC+ Full mode at 50 Hz against BlenderDMX's 24 Hz apply rate means every other frame is dropped; motion faster than 24 Hz steps is not visible. A custom receiver could apply at the timer rate (about 94 to 118 Hz measured with redraws).
- With QLC+ OSC, a 16-bit pan arrives as two independent datagrams (coarse, then fine) per change. A receiver that applies each immediately will briefly show a wrong combined value (tearing). Art-Net and sACN deliver all 512 bytes in one packet, so 16-bit values are atomic there.
- QLC+ OSC is 8-bit only per message (value/255 float), so OSC gives no resolution advantage over DMX. Fine control needs coarse plus fine channels.

### Gaps
- No QLC+ doc page states the OSC send rate. From the source it follows the QLC+ output tick (50 Hz per the Art-Net page) and only for changed channels, but this was not measured.
- sACN (E1.31) plugin rate and priority behaviour in QLC+ were not read.
- No real-world "QLC+ drives Blender VJ scene" project or tutorial was found beyond BlenderDMX as a visualiser.
- BlenderDMX docs site (blenderdmx.eu) was not fetched; mapping of arbitrary GDTF attributes to non-light properties is unverified.

## Video output: Syphon, Spout, NDI/OMT, offscreen capture, headless `gpu.init()`

### Takeaway
On macOS all live paths are "draw into `GPUOffScreen`, read to CPU, upload/encode". TextureSharing v9.1.1 (maybites) is the one maintained add-on, covering Syphon (macOS), Spout (Windows) and NDI/OMT (all platforms). Measured headless Eevee offscreen plus readback on an M1 Max gives about 80 fps upper bound at 720p, 40 at 1080p and 22 at 4K for the default cube, before the Syphon upload. 1080p30 is the safe planning target for real scenes.

### Cited Findings
- TextureSharing latest release v9.1.1 (2026-10-07), v9.1.0 (2026-09-23); README title "Texture sharing addon for Blender 5.x upwards"; v9.0.3 (2026-08-25) fixed "Blender 5.2 texture readback corruption". No license declared on GitHub — [GitHub API, maybites/TextureSharing](https://github.com/maybites/TextureSharing/releases), [README](https://github.com/maybites/TextureSharing/blob/master/README.md)
- Platform matrix: Windows Spout sender and discovery working, Spout receiver ⚠️; macOS Syphon Metal server working, Metal client ⚠️; NDI and OMT sender and discovery working on Linux, Windows, macOS, receivers ⚠️ — [README](https://github.com/maybites/TextureSharing/blob/master/README.md)
- Libraries installed by button via pip: syphon-python, SpoutGL, cyndilib (NDI), cyomtlib (OMT). OMT on Linux needs Avahi for discovery, otherwise receivers connect by `omt://host:port` — [README](https://github.com/maybites/TextureSharing/blob/master/README.md)
- "steady stream (NDI and OMT only): keep resending the last frame at the scene frame rate while the viewport is idle. Otherwise a frame is only sent when the viewport redraws." Transparent background "seems to work only for 'Display in solid mode'" — [README](https://github.com/maybites/TextureSharing/blob/master/README.md)
- Capture runs in a `SpaceView3D` POST_PIXEL draw handler and calls `GPUOffScreen.draw_view3d(...)` with the camera's matrices, so it renders the scene a second time at capture size. The Syphon Metal path does `texture_color.read()` then `MTLTexture.replaceRegion` into an `RGBA8Unorm` texture, then publishes — [project note, Syphon output](https://github.com/maybites/TextureSharing/blob/master/operators.py), [SyphonMetalServer.py](https://github.com/maybites/TextureSharing/blob/master/fbs/syphon/SyphonMetalServer.py)
- Blender 5.2 added "`gpu.init()` to initialize gpu backend when running Blender in background mode `--background`" — [5.2 Python API notes](https://developer.blender.org/docs/release_notes/5.2/python_api/)
- Measured (M1 Max, 5.2.3, headless after `gpu.init()`, default cube, Eevee Rendered, `draw_view3d` plus `texture_color.read()` including GPU wait): 1280x720 11.4 ms (~80 fps), 1920x1080 24.0 ms (~40 fps), 3840x2160 44.5 ms (~22 fps). Pure readback of a finished RGBA8 offscreen: 1.1 ms (720p), 1.6 ms (1080p), 5.4 ms (4K). Eevee shaders compile asynchronously and needed about 30 draws before the real image appeared. F12 `render.render()` at 720p 1 sample took about 135 ms — [project note, Syphon output](https://developer.blender.org/docs/release_notes/5.2/python_api/)
- `GPUTexture` in 5.2.3 exposes no native handle (no bindcode, no `MTLTexture` pointer), so zero-copy sharing is impossible from Python. macOS Blender is Metal-only since 4.0 — [project note, Syphon output](https://developer.blender.org/docs/release_notes/4.0/)
- The offscreen format is `RGBA8`, so all TextureSharing outputs are 8-bit SDR — [project note, Syphon output](https://github.com/cansik/syphon-python/blob/main/syphon/utils/raw.py)
- `syphon-python` 0.2.0 (2026-10-07) is a `py3-none-macosx_12_0_universal2` wheel on PyObjC 12.2; `cyndilib` 0.0.5 ships `cp313 macosx_11_0_arm64` wheels — [syphon-python PyPI](https://pypi.org/project/syphon-python/0.2.0/), [cyndilib PyPI](https://pypi.org/project/cyndilib/0.0.5/)
- Syphon discovery relies on `NSDistributedNotificationCenter` announce requests — [SyphonServerBase.m](https://github.com/Syphon/Syphon-Framework/blob/main/SyphonServerBase.m)

### Inferences
- In UI mode, Syphon frame rate equals viewport redraw rate. An idle scene sends nothing; driving properties with `tag_redraw()` (see next section) also drives the output.
- In headless mode, a script loop blocks the main thread, so Syphon discovery notifications may not be delivered unless the run loop is pumped. Unverified.
- NDI and OMT add CPU encode on top of the same readback and are only worth it across machines. Spout is irrelevant on macOS.
- Copy overhead itself is small on unified memory (1.6 ms at 1080p); scene GPU time dominates. In UI mode the visible viewport plus the capture double GPU cost.

### Gaps
- End-to-end latency into a Syphon client and the extra cost of `replaceRegion` upload were not measured.
- Behaviour when the Blender window is minimised or occluded (App Nap, occlusion throttling) is unknown.
- OMT performance on macOS and the cyomtlib version were not checked.
- No Blender-native (C++) Syphon/Spout/NDI output was found in the tracker.

## Threading and main-loop constraints affecting all of the above

### Takeaway
All `bpy` access must stay on the main thread. Inputs must be drained in a `bpy.app.timers` callback (or a modal operator), then the owning ID must be tagged with `update_tag()` and 3D views with `tag_redraw()`. Otherwise drivers stay stale and the viewport (and therefore Syphon output) does not redraw. Timer and redraw share one main loop, so input rate, scene evaluation and output fps compete.

### Cited Findings
- Python threads "cause Blender to crash in hard to diagnose ways"; a thread left running "may seem to work for a while" — [info_gotchas_threading](https://docs.blender.org/api/current/info_gotchas_threading.html)
- A timer callback returns its next delay in seconds or `None` to unregister; no minimum interval is documented — [bpy.app.timers](https://docs.blender.org/api/current/bpy.app.timers.html)
- `obj["prop"] = v` from Python sets no depsgraph tag; the RNA code says developers "will need to manually 'update_tag'". A `bpy.props` property without `update=` also tags nothing. `ID.update_tag()` adds no window-manager notifier — [rna_access.cc](https://projects.blender.org/blender/blender/src/branch/blender-v5.2-release/source/blender/makesrna/intern/rna_access.cc), [rna_ID.cc](https://projects.blender.org/blender/blender/src/branch/blender-v5.2-release/source/blender/makesrna/intern/rna_ID.cc)
- Measured on 5.2.3 GUI, EEVEE Rendered, no playback: custom property plus `update_tag()` re-evaluated drivers but gave 0 draws/s; adding `area.tag_redraw()` on VIEW_3D areas gave 94 draws/s; a plain RNA write like `ob.location.y = v` redrew by itself at 115 draws/s — [project note, live control](https://docs.blender.org/api/current/bpy.app.timers.html)
- Since 5.2, geometry nodes modifier inputs are RNA properties: `modifier.properties.inputs.Socket_1.value = 5.0` replaces `modifier["Socket_1"]`. They define no update callbacks, so they also need `obj.update_tag()` — [5.2 Python API notes](https://developer.blender.org/docs/release_notes/5.2/python_api/), [geometry_nodes_srna.cc](https://projects.blender.org/blender/blender/src/branch/blender-v5.2-release/source/blender/nodes/intern/geometry_nodes_srna.cc)
- Since 5.0, `bpy.props` properties are stored apart from custom properties and cannot be read with `obj["name"]` — [5.0 Python API notes](https://developer.blender.org/docs/release_notes/5.0/python_api/)
- Simple Expression drivers skip the Python interpreter and run even with script execution disabled — [Drivers panel manual](https://docs.blender.org/manual/en/latest/animation/drivers/drivers_panel.html)
- `bpy.app.driver_namespace` is reset on file load — [bpy.app](https://docs.blender.org/api/current/bpy.app.html)
- BlenderDMX works around redraw from threads with an empty `update=` callback on an `IntProperty`, noting `tag_redraw()` "doesn't work" from its context — [data.py](https://github.com/open-stage/blender-dmx/blob/main/data.py)
- NodeOSC only forces a GUI redraw when its message monitor is on — [NodeOSC server/_base.py](https://github.com/maybites/NodeOSC)
- Extensions must declare `network` in `[permissions]`; add-ons using the internet must check `bpy.app.online_access` — [Extensions getting started](https://docs.blender.org/manual/en/latest/advanced/extensions/getting_started.html)

### Inferences
- A single main-thread timer should do in order: drain sockets (latest value per address), write control properties, `update_tag()` the control ID, `tag_redraw()` the 3D views. The redraw then triggers the TextureSharing capture, so input and output stay in lockstep.
- Rough budget at 60 fps is 16.7 ms per frame shared by input drain, depsgraph evaluation, viewport draw and capture readback (about 24 ms at 1080p measured for the default cube capture alone). 60 fps at 1080p in UI mode is unlikely for non-trivial scenes; 30 fps is realistic.
- Eevee viewport restarts sampling on each change, so continuously driven scenes show 1-sample TAA frames. This affects the look of every output path.
- Under heavy scene evaluation, timer ticks slow down, so the add-on with the lowest fixed rate (BlenderDMX at 24 Hz) sets a ceiling, while queue-based OSC add-ons can build latency if they do not drop stale messages (NodeOSC uses LIFO; AddRoutes caps 200 events per cycle).

### Gaps
- Behaviour during timeline playback (frame-change handlers versus timers) was not tested.
- How much `tag_redraw()` at 60 Hz in heavy show scenes lowers the timer rate was not measured.
- Whether a localhost UDP listener counts as "internet" for `bpy.app.online_access` is not documented.
