# Getting live control data into Blender

Research for issue #3. Question: how a running Blender scene receives live control data (beat, BPM, phase, song changes, parameter values) from another app at show rates, and maps it onto drivers, custom properties and geometry node inputs.

- Date: 2026-11-03
- Installed Blender: `5.2.3 LTS` (build 2026-10-22), from `/Applications/Blender.app/Contents/MacOS/Blender --version`
- API docs read: docs.blender.org/api/current, which reports itself as "Blender 5.2 Python API"
- Source read: `blender-v5.2-release` branch on projects.blender.org
- Test host: Apple M1 Max, factory settings, isolated `BLENDER_USER_RESOURCES`, default scene, EEVEE, viewport in Rendered shading
- Labels: **Fact** (cited source or own measurement), **Inference** (reasoned, not measured), **Rec** (recommendation)

## Answer

- **Rec:** Write a small Blender extension of our own. It binds a non-blocking UDP socket and drains it from one `bpy.app.timers` callback on the main thread, with no Python threads. It keeps only the latest value per address, writes into a few scene-level properties, then calls `update_tag()` on the owning ID and `tag_redraw()` on the 3D views. Drivers and geometry node inputs read those properties through Simple Expressions. Blender Lab's official MCP add-on uses the same no-thread socket and timer pattern.
- **Rec:** SwiftVJ sends OSC to a dedicated Blender port. Continuous values (BPM, energy, parameters) go at up to 60 Hz. Track changes go as single events. For beat phase, send a BPM plus a beat-anchor timestamp, and let Blender work out the phase each tick, so network jitter does not show up as phase jitter (Inference).
- **Rec:** Use NodeOSC for quick prototypes without writing code. It works, but it runs a receive thread (which Blender says is unsupported), it uses `eval`/`exec` on data paths, and it does not tag custom property writes for update.
- **Rec:** Don't use MCP to stream data. It suits authoring the mapping (creating drivers and properties) through an LLM. It does not suit sending show-rate data: it polls every 50 ms when active, drops to 1 s when idle, and runs arbitrary code.

## Facts later decisions depend on

### Main thread and update rate

- **Fact:** Blender's docs say Python threads "cause Blender to crash in hard to diagnose ways" and are supported only while the main thread is blocked (joined). A thread left running "may seem to work for a while" but causes random crashes. ([info_gotchas_threading](https://docs.blender.org/api/current/info_gotchas_threading.html))
- **Fact:** A timer callback returns its next delay in seconds, or `None` to unregister. The docs give no minimum interval. ([bpy.app.timers](https://docs.blender.org/api/current/bpy.app.timers.html))
- **Fact (measured):** A timer that returns `0.0` ran about 170 to 175 times per second with nothing else happening. When every tick also requested a redraw, it fell to 94 to 118 ticks per second, because ticks and draws share the main loop. That is above 60 Hz for the default scene. Heavier scenes will slow it further (Inference).
- **Fact (measured):** A non-blocking UDP socket drained inside that timer received 1352 of 1360 small datagrams sent from another process at about 750 msg/s on localhost. The cause of the 8 missing datagrams was not established.
- **Fact:** Blender Lab's MCP add-on describes itself as a "Non-blocking TCP socket server" that never blocks the main thread. It polls through `bpy.app.timers` at `TIMER_INTERVAL_ACTIVE = 0.05`, and after 5 s without traffic it backs off to 1.0 s. ([mcp_to_blender_server.py](https://projects.blender.org/lab/blender_mcp/src/branch/main/addon/blender_mcp_addon/mcp_to_blender_server.py), [execute_interactive.py](https://projects.blender.org/lab/blender_mcp/src/branch/main/addon/blender_mcp_addon/execute_interactive.py))

### Property writes, depsgraph and redraw (no playback)

- **Fact (source):** `obj["prop"] = v` from Python only stores the value. It runs no RNA update and sets no depsgraph tag (`pyrna_struct_ass_subscript` calls `BPy_Wrap_SetMapItem`, in [bpy_rna.cc](https://projects.blender.org/blender/blender/src/branch/blender-v5.2-release/source/blender/python/intern/bpy_rna.cc)). The RNA code says outright that for ID properties edited from Python, developers "will need to manually 'update_tag', see: #74000" ([rna_access.cc](https://projects.blender.org/blender/blender/src/branch/blender-v5.2-release/source/blender/makesrna/intern/rna_access.cc), [#74000](https://developer.blender.org/T74000)).
- **Fact (source):** Setting an RNA attribute from Python runs the update only when `RNA_property_update_check` passes, meaning the property has an `update` function or a notifier flag. A `bpy.props` property without `update=` has neither, so setting it tags nothing ([rna_access.cc](https://projects.blender.org/blender/blender/src/branch/blender-v5.2-release/source/blender/makesrna/intern/rna_access.cc)).
- **Fact (source):** `ID.update_tag()` only calls `DEG_id_tag_update_ex`. It adds no window-manager notifier ([rna_ID.cc](https://projects.blender.org/blender/blender/src/branch/blender-v5.2-release/source/blender/makesrna/intern/rna_ID.cc)).
- **Fact (measured, headless 5.2.3):** A driver reading `obj["p"]` or `scene["beat"]` stayed stale until `update_tag()` was called on the ID that owns the property. Tagging the scene was enough for an object driver that reads a scene property. A driver reading a `bpy.props` `FloatProperty` on Scene, and a geometry nodes modifier input set through `.value`, also stayed stale until tagged.
- **Fact (measured, GUI, EEVEE Rendered, no playback):**
  - `obj["p"] = v` plus `update_tag()` re-evaluated the driver, but the viewport did not redraw (0 draws/s).
  - Adding `area.tag_redraw()` for VIEW_3D areas made redraws follow the updates (94 draws/s).
  - Plain `ob.location.y = v`, which goes through an RNA property with a notifier, redrew without help (115 draws/s).
- **Inference:** EEVEE's Rendered viewport starts sampling over on every change, so constantly changing values will show low-sample frames. This was not measured. Check it in Material Preview and Rendered before a show.
- **Fact:** NodeOSC adds a redraw "hack to refresh the GUI", and only when its message monitor is on (`server/_base.py` in [NodeOSC](https://github.com/maybites/NodeOSC)).

### Mapping targets in Blender 5.x

- **Fact:** Simple Expressions skip the Python interpreter, and they "are evaluated even when Python script execution is disabled". Anything outside that subset is flagged as a "Slow Python expression". Driver variables should read data through RNA paths such as `["prop_name"]` so dependencies are tracked. ([Drivers panel](https://docs.blender.org/manual/en/latest/animation/drivers/drivers_panel.html))
- **Fact:** Since 5.2, geometry nodes modifier inputs are RNA properties rather than custom properties. The old `modifier["Socket_1"] = 5.0` style is replaced by `modifier.properties.inputs.Socket_1.value = 5.0` ([5.2 Python API notes](https://developer.blender.org/docs/release_notes/5.2/python_api/)). The old style raised `TypeError: id properties not supported for this type` on 5.2.3 (measured). The generated RNA for these inputs defines no update callbacks ([geometry_nodes_srna.cc](https://projects.blender.org/blender/blender/src/branch/blender-v5.2-release/source/blender/nodes/intern/geometry_nodes_srna.cc)), which matches the measured need for `obj.update_tag()`.
- **Fact:** Since 5.0, properties defined with `bpy.props` are stored apart from user custom properties and can't be read with `obj["name"]` ([5.0 Python API notes](https://developer.blender.org/docs/release_notes/5.0/python_api/)). This affects add-ons that mix the two, which NodeOSC's data paths can do.
- **Inference:** The least fragile mapping is plain custom properties on one control ID, for example `scene["vj_bpm"]` or an Empty named `VJ`. Drivers then read those properties, and a geometry nodes input is driven by one of those drivers. The receiver then only needs to tag that one control ID, and no input socket identifier from the 5.2 API ends up in the receiver.
- **Fact:** `bpy.app.driver_namespace` is reset on file load ([bpy.app](https://docs.blender.org/api/current/bpy.app.html)). Python drivers also need Auto Run Python Scripts and are listed among the thread crash risks, so avoid reading a socket from a driver function (Inference).

### Packaging and permissions

- **Fact:** An extension declares `network` in `[permissions]`. Add-ons that use the internet must check `bpy.app.online_access`. ([Getting started](https://docs.blender.org/manual/en/latest/advanced/extensions/getting_started.html), [Add-ons](https://docs.blender.org/manual/en/latest/advanced/extensions/addons.html))
- **Inference:** The docs do not say whether a localhost UDP listener counts as internet use. Declaring `network` and binding only to `127.0.0.1` by default is the safe reading. Blender Lab's MCP add-on declares `network = "Runs a local TCP socket server for MCP client communication"` ([blender_manifest.toml](https://projects.blender.org/lab/blender_mcp/src/branch/main/addon/blender_mcp_addon/blender_manifest.toml)).

## Options compared

| Option | Receive model | Rate controls | Writes | Blender 5.2 status | Fit |
|---|---|---|---|---|---|
| NodeOSC v2.4.4 (2026-06-05) | oscpy `OSCThreadServer` or python-osc thread, then a LIFO queue drained in `bpy.app.timers` | `input_rate` ms (default 0, every loop), `output_rate` 40 ms, optional repeat-address filter | `setattr` for RNA paths, `data_path[prop] = v` for custom properties (no `update_tag`), `eval`/`exec` statements | Legacy `bl_info` add-on (`blender: (2, 80, 0)`), no extension manifest, no stated 5.x support | Prototyping |
| AddRoutes v0.33.0 fork (slashv, 2024-12-07) | oscpy server, list queue drained in `bpy.app.timers` | `refresh` ms (default 1), `overflow` 200 events per cycle | `setattr` on RNA paths, optional keyframe recording, plus MIDI and an Android app | Extension manifest, `blender_version_min = "4.2.0"`, `network` permission, bundled wheels. Upstream JPfeP repo last pushed 2022-03 | Prototyping, MIDI |
| Custom extension (recommended) | Non-blocking UDP socket polled in one timer, no threads | Own timer interval, latest-value-wins per address | Custom properties on one control ID, then `update_tag()` and `tag_redraw()` | Fits the documented threading rules | Show use |
| Blender Lab MCP 1.0.x | Non-blocking TCP on `localhost:9876`, null-delimited JSON carrying Python code | 50 ms active, 1 s idle after 5 s | Arbitrary `exec` | Needs Blender 5.1 or newer. Its page warns it runs LLM code "without any guards" ([page](https://www.blender.org/lab/mcp-server/)) | Authoring only |
| Community "MCP for Blender" (ahujasid) | Socket thread plus a queue drained in a timer, `localhost:9876` | Not designed for streaming | `exec(code, namespace)` | Says it is not affiliated with the official project ([repo](https://github.com/ahujasid/mcp-for-blender)) | Authoring only |

Sources: NodeOSC `server/_base.py`, `server/callbacks.py`, `server/server.py`, `preferences.py` ([repo](https://github.com/maybites/NodeOSC)); AddRoutes `osc.py`, `__init__.py`, `blender_manifest.toml` ([fork](https://github.com/slashv/AddRoutes), [upstream](https://github.com/JPfeP/AddRoutes)).

## SwiftVJ context (live source, main checkout)

- **Fact:** `OSCHub` listens only on UDP 9010 (VDJ responses) and sends to fixed localhost targets: VDJ 9009, Synesthesia 7777, Magic 11111. Every received message is forwarded to Magic (`forwardTargets`, `Sources/SwiftVJCore/Adapters/OSCClient.swift`, `Sources/SwiftVJCore/Infrastructure/Config.swift`). `docs/architecture/06-osc-messages.md` still says the receive port is 9999, which is out of date.
- **Fact:** `OSCHub.send(_:values:host:port:...)` already accepts any host and port. The store's `EffectEnvironment.sendOSC` handles only the targets `magic`, `synesthesia` and `vdj` (`Sources/SwiftVJApp/SwiftVJApp.swift`). A `blender` target needs a new branch there plus a port setting next to `OSCHub.PortKeys`.
- **Fact:** Track changes already go out as `/textler/track [active, source, artist, title, album, duration, has_lyrics]` and `/ai/analysis [mood, energy, valence]` to Magic (`Sources/SwiftVJCore/Modules/PipelineModule.swift`). BPM and `song_pos` come from VDJ, which is polled at 1 Hz (`Sources/SwiftVJCore/Adapters/VDJMonitor.swift`).
- **Fact:** SwiftVJ has no live beat or phase input today. `RenderEngine.updateCachedState` sets `audioLevels` to `nil` with the comment "No audio input". `AudioState.beatPhase` and `beat4` are fed only through `onAudioUpdate` (`Sources/SwiftVJApp/Rendering/RenderEngine.swift`, `AudioProcessor.swift`).
- **Inference:** BPM from a 1 Hz VDJ poll is enough for the BPM itself, but beat phase needs a beat anchor (a beat position or downbeat time) that SwiftVJ does not currently receive.

## Open questions that could change the recommendation

- Where beat phase comes from: VDJ beat position over OSC, Synesthesia `/audio/beat/*`, or Ableton Link. This was not researched here. It decides whether SwiftVJ sends a phase stream or a BPM plus anchor.
- How EEVEE Rendered and Material Preview look under constant 60 Hz updates in a real show scene (low-sample flicker), and how much heavy geometry nodes evaluation lowers the timer and draw rate.
- Whether to send to Blender on the same machine only, or also over the LAN. LAN use touches `online_access` and firewall prompts.
- Whether a frame-change handler during playback (for timeline-synced scenes) should replace the timer. This was not tested.

## Method

- Read Blender 5.2 API pages, the manual, and the 5.0 and 5.2 release notes. Read 5.2 release-branch source: `bpy_rna.cc`, `rna_access.cc`, `rna_ID.cc`, `geometry_nodes_srna.cc`, `wm_draw.cc`, `render_update.cc`.
- Read add-on source from GitHub and projects.blender.org through `gh api` and raw URLs. Nothing was installed.
- Ran two throwaway scripts against the installed Blender, outside the repo, with `--factory-startup` and `BLENDER_USER_RESOURCES` set to a scratch folder.
  - The headless (`-b`) script checked driver and geometry nodes evaluation after each kind of write.
  - The GUI script counted `SpaceView3D` POST_PIXEL draw callbacks and timer ticks over 2 s phases, with a `/usr/bin/python3` UDP sender running alongside.
