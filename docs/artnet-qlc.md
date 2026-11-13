# Art-Net and QLC+ for the Blender scene

A lighting desk or QLC+ can drive the Blender scene over Art-Net, next to Magic and the scene page. The bridge ([blender/blender_osc_bridge.py](../blender/blender_osc_bridge.py), Art-Net part in [blender/artnet_input.py](../blender/artnet_input.py)) listens for ArtDmx frames on udp 6454. One QLC+ fixture, [qlc/bossi3dj-Synthwave-Planet.qxf](../qlc/bossi3dj-Synthwave-Planet.qxf), has one DMX channel per address the Blender scene reacts to. Status: built, unit tested, and tried live with the sender (below); not yet tried with a running QLC+.

## Test with QLC+

1. `make qlc-install`. Pass: it prints `installed: ~/Library/Application Support/QLC+/Fixtures/bossi3dj-Synthwave-Planet.qxf`.
2. `make blender-open` (planet), wait for `start state: ready`. Pass: `make status` lists Blender under `artnet_listeners` (udp 6454).
3. Start QLC+ (quit and start it again if it ran) and open the workspace `qlc/bossi3dj-Synthwave-Planet.qxw`. Pass: no load error, the Fixtures tab shows `Synthwave Planet` at universe 1, address 1, the Virtual Console shows a frame per manual group.
4. Inputs/Outputs tab, Universe 1: the output must be the Art-Net plugin; if it shows none, pick `ArtNet`. Open its configuration: IP address `255.255.255.255` (the broadcast), universe `0`, mode `Full`. Pass: the universe's Output box is ticked.
5. Virtual Console in operate mode. Move the `fog` slider (group Fog). Pass: the fog in the Blender window changes within a second, and `make status` shows `blender_scene.osc_received` rising.
6. Press `shock` (group Triggers). Pass: one shock wave per press. Click a button of `Target`, for example `Moon`. Pass: the Path Camera flies to the moon within the fade time (`/vj/blend`).
7. Check the port: `make status` with QLC+ running should list both `QLC+` and `Blender` under `artnet_listeners`, or tell in its notes what is wrong. Pass: no note about Art-Net.
8. Set the IP address in the plugin configuration to `127.0.0.1` and repeat step 5. Pass or fail is the answer to "does a unicast frame reach Blender next to QLC+".
9. Tell what failed and what `make status` said. Move faders only after Blender has started: the first frame it sees is the baseline.

What is verified in the workspace file: its structure (Creator, Engine with fixture, scene functions, Virtual Console with frames, sliders in Level mode and buttons) follows a workspace written by QLC+ 5.3.0 GIT on this machine, read for its element names only. The Art-Net plugin's parameter names (`outputIP`, `outputUni`, `transmitMode`, `UniverseChannels`) are read from the strings of `PlugIns/libartnet.dylib`. From memory and not verified: the `Output` element's `Name` and `Line` for the Art-Net plugin (QLC+ may leave the output unset: step 4 fixes that in two clicks), that a Flash button on a scene releases its channel to 0, and what releasing a Toggle camera button does (it may cut back to shot 0; the `/vj/cam` slider has no such effect).

## What the bridge does with a frame

- **Settings** (`bridge.configure_artnet(enabled, universe, address)`): Art-Net on, universe 0, DMX start address 1. The scene page can show them later. A failed bind of udp 6454 is not fatal: the bridge reports it in `bridge.artnet_state()` (`bound`, `error`) and goes on with OSC.
- **One channel per address**, 37 in all, in contract order (the order of `SCALES` in the bridge): channel 1 is `/vj/level`. The table is below. `make qlc-fixture` rewrites the fixture and the table from [osc/contract.json](../osc/contract.json).
- **A value is a DMX value 0 to 255** mapped linearly onto the row's wire range (0 to 1 for a float), then it takes the same way as an OSC message: scaled to scene units, kept inside the property's limits, skipped when the page holds the control. In the bridge state the source is `artnet`.
- **Only changes are applied.** A desk sends every channel in every frame, Magic only on change. A channel is applied only when its DMX value differs from the last frame, so a resting fader never fights Magic or the page. The first frame after the start, and the first one after the universe or address changes, is the baseline and applies nothing. So after a start the desk's faders do nothing until you move them.
- **Triggers** (`/vj/shock`, `/vj/meteor`, `/vj/hit`): a rise through 128 fires once. The strength is 0.5 at 128 and grows to the row's wire maximum at 255 (`/vj/shock` 1.5, the others 1). When the channel falls below 128 the trigger gets 0 again, so the next rise is a new edge.
- **Index channels (`/vj/path`, `/vj/target`)**: 0 to 255 is split into equal ranges, one per index (4 paths, 7 targets), named in the fixture by the row's `stops`.
- **Takeover**: a changed Art-Net channel is a touch: the address is the user's, Magic's OSC value for it is kept and applied only after `/vj/takeover` (20 s by default) with no touch. The scene page's touches count the same; triggers always pass.
- **Who wins:** Art-Net, OSC from Magic and the scene page all write the same scene properties; the last change wins, and the page's hold (the H button, or a running check) stays above both. Within one tick OSC is applied first, then Art-Net.

## Channel table

<!-- artnet-channels:begin -->
| DMX channel | Name in QLC+ | What you see | DMX to wire value |
|---|---|---|---|
| 1 | Light Level (`/vj/level`) | The sun and its glow get stronger the louder the music is. | 0..255 = 0..1 |
| 2 | Bass (`/vj/bass`) | Bass makes things hit harder: the glowing ground net and waterline in Blender, the shake and dust of each footfall in Godot. | 0..255 = 0..1 |
| 3 | Beat (`/vj/beat`) | Pulses on every beat: pyramid edges, stars and water glints in Blender, footfalls and dust puffs in Godot. | 0..255 = 0..1 |
| 4 | Palette Hue (`/vj/hue`) | Turns all colours around the colour wheel. | 0..255 = 0..1 |
| 5 | Brightness (`/vj/intensity`) | Makes the whole picture brighter or darker. | 0..255 = 0..1 |
| 6 | Strobe (`/vj/strobe`) | Flashes the picture to white; higher means a stronger flash. | 0..255 = 0..1 |
| 7 | Grid Speed (`/vj/grid_speed`) | Makes the glowing grid on the ground scroll faster. | 0..255 = 0..1 |
| 8 | Camera Speed (`/vj/cam_speed`) | Makes the camera drift and fly faster or slower. | 0..255 = 0..1 |
| 9 | Path (`/vj/path`) | Picks how the camera moves: 0 orbit the target, 1 follow the land, 2 rise and descend, 3 vantage with a slow push. | split into 4 equal ranges, one per index; ranges: Orbit 0 to 63, Follow the land 64 to 127, Rise and descend 128 to 191, Vantage 192 to 255 |
| 10 | Target (`/vj/target`) | Picks what the camera looks at: 0 pyramids, 1 lake, 2 river, 3 coast, 4 moon, 5 sun, 6 planet. | split into 7 equal ranges, one per index; ranges: Pyramids 0 to 36, Lake 37 to 73, River 74 to 109, Coast 110 to 146, Moon 147 to 182, Sun 183 to 219, Planet 220 to 255 |
| 11 | Height (`/vj/height`) | Lifts the camera from just over the ground (0) to space with the whole Planet in frame (1). | 0..255 = 0..1; ranges: Ground 0 to 64, 800 m 65 to 191, Space 192 to 255 |
| 12 | Sun Height (`/vj/sun`) | Lifts the sun up the sky and makes it bigger; 0 sinks it below the horizon. | 0..255 = 0..1 |
| 13 | Moon Size (`/vj/moon`) | Makes the moon bigger or smaller. | 0..255 = 0..1 |
| 14 | Moon Phase (`/vj/moon_phase`) | Changes the shape of the moon from new through half to full. | 0..255 = 0..1; ranges: New 0 to 64, Half 65 to 191, Full 192 to 255 |
| 15 | Pyramids (`/vj/pyramids`) | Makes the pyramids rise out of the ground. | 0..255 = 0..1 |
| 16 | Mesh Edges (`/vj/grid`) | Island scene only: shows the real edges of the low-poly ground as a glowing wireframe; the planet has none. | 0..255 = 0..1 |
| 17 | Stars (`/vj/stars`) | Fades the stars in or out. | 0..255 = 0..1 |
| 18 | Water Reflection (`/vj/water`) | Turns the reflections on the water up or down. | 0..255 = 0..1 |
| 19 | Night (`/vj/night`) | Turns day into night: 0 is day, a quarter is sunset, half is twilight, 1 is night. | 0..255 = 0..1; ranges: Day 0 to 32, Sunset 33 to 96, Twilight 97 to 191, Night 192 to 255 |
| 20 | Nebula (`/vj/nebula`) | Fades in the coloured cloud in the night sky. | 0..255 = 0..1 |
| 21 | Shock (`/vj/shock`) | A shock wave runs over the land once; in Godot the giant shakes while the Wanderer is on it. | below 128 off; from 128 fires once, strength 0.5 at 128 up to 1.5 at 255, back below 128 re-arms |
| 22 | Meteor (`/vj/meteor`) | A shooting star crosses the sky. | below 128 off; from 128 fires once, strength 0.5 at 128 up to 1 at 255, back below 128 re-arms |
| 23 | Flamingos (`/vj/flamingos`) | Makes the flock of flamingos bigger; 0 hides it. | 0..255 = 0..1 |
| 24 | Fog (`/vj/fog`) | More fog near the ground; at 1 it is dense autumn fog. | 0..255 = 0..1 |
| 25 | Fog Height (`/vj/fog_height`) | Makes the fog bank taller or lower. | 0..255 = 0..1 |
| 26 | Fog Glow (`/vj/fog_glow`) | Makes the fog glow by itself. | 0..255 = 0..1 |
| 27 | Fog Hue (`/vj/fog_hue`) | Tints the fog pink, violet or cyan. | 0..255 = 0..1; ranges: Pink 0 to 42, Violet 43 to 126, Cyan 127 to 211, Pink again 212 to 255 |
| 28 | Fog Patches (`/vj/fog_noise`) | Makes the fog patchier. | 0..255 = 0..1 |
| 29 | Fog Size (`/vj/fog_scale`) | Makes the fog clouds bigger or smaller. | 0..255 = 0..1 |
| 30 | Fog Wind (`/vj/fog_speed`) | Makes the wind push the fog along faster. | 0..255 = 0..1 |
| 31 | Fog Pump (`/vj/fog_beat`) | Makes the fog pump with the beat. | 0..255 = 0..1 |
| 32 | Haze (`/vj/haze`) | Adds or removes the soft haze toward the horizon. | 0..255 = 0..1 |
| 33 | Eclipse (`/vj/eclipse`) | Lines the moon up with the sun and the planet for an eclipse. | 0..255 = 0..1 |
| 34 | Star Drift (`/vj/star_speed`) | Makes the stars drift across the sky. | 0..255 = 0..1 |
| 35 | Fade Time (`/vj/blend`) | How long a change of path or target flies; 0 cuts at once. | 0..255 = 0..1 |
| 36 | Takeover Pause (`/vj/takeover`) | How long a control you touched stays yours before the music steers it again. | 0..255 = 0..1 |
| 37 | Camera Energy (`/vj/energy`) | Makes the camera move harder, from a slow wide glide to faster, tighter moves. | 0..255 = 0..1 |
| 38 | Hit (`/vj/hit`) | A quick surge of speed with a wide-angle kick on the camera. | below 128 off; from 128 fires once, strength 0.5 at 128 up to 1 at 255, back below 128 re-arms |
<!-- artnet-channels:end -->

## What QLC+ offers and what we use

"Verified" means seen in a file that ships in `/Applications/QLC+.app` (5.3.0 GIT: 144 fixture folders in `Resources/Fixtures`, `Resources/Gobos`, `Resources/Sample.qxw`, a workspace QLC+ 5.3.0 wrote on this machine, strings of `PlugIns/libartnet.dylib`). The app ships no schema or fixture documentation. "Memory" means QLC+ knowledge that no shipped file shows.

| QLC+ feature | Evidence | Used here |
|---|---|---|
| Fixture type (14 seen: Color Changer, Moving Head, Scanner, Flower, LED Bar, Strobe, Laser, Smoke, Effect, Dimmer, Other, Hazer, Fan) | verified | `Other`: no type fits a video scene. |
| Channel groups (Effect, Colour, Shutter, Speed, Gobo, Intensity, Maintenance, Beam, Prism, Pan, Tilt, Nothing) | verified | Intensity only for `/vj/intensity` (QLC+'s grand master scales Intensity channels, memory: right for overall brightness, wrong for level, bass or beat), Colour for the two hues, Shutter for `/vj/strobe`, Speed for the four speeds, Gobo for `/vj/cam`, Effect for the rest. |
| Channel `Preset` attribute (`IntensityMasterDimmer`, `ShutterStrobeSlowFast`, `SpeedPanTiltSlowFast`, `IntensityHue`, ...) | verified (a self-closing channel, no capability text under it in any shipped file) | Not used: a preset channel cannot carry the plain sentence, and these presets mean a master dimmer, a strobe frequency or an HSV hue channel, which the scene does not mean. |
| Capability `Preset="ColorMacro"` with `Res1="#rrggbb"` (a colour swatch) | verified (13482 uses) | Yes, for the four ranges of `/vj/fog_hue`: the build script's `FOG_RAMP` (pink, violet, cyan, pink) converted from scene-linear to sRGB. `/vj/hue` rotates the whole palette, so it has no single colour and no swatch. |
| Capability `Preset="GoboMacro"` with `Res1="Folder/name.png"` (a picture) | verified (4113 uses; every `Res1` is a path relative to the Gobos folder, none is absolute; shipped pictures are 64x64 PNG or SVG) | Not used since the Path Camera (2026-11-13): the 12 shots and their pictures left the Planet; the targets are names only. That QLC+ finds a user fixture's pictures in `~/Library/Application Support/QLC+/Gobos` stays unverified. |
| Capability `Preset="SlowToFast"` | verified (208 uses) | Yes, for the speed channels. |
| Strobe, rotation, pulse, ramp, lamp and reset capability presets | verified | Not used: they describe a lamp or a motor; `/vj/strobe` flashes to white, it is not a frequency. |
| Capability text | verified | Yes. QLC+ has no description field per channel (only `Name`, `Group`, `Colour`, `Capability` under a channel), so the plain sentence is the capability text, with the stop's name before it where a channel has labelled stops. |
| Channel `Default` attribute | verified (358 uses) | Yes, the contract default as a DMX value. |
| Aliases (`Preset="Alias"` with `<Alias Mode= Channel= With=>`), fine channels (`...Fine` presets, `Group Byte="1"`), channel `Colour` element | verified | Not used: one mode, 8 bit channels, no colour channels. |
| Several modes | verified | One mode. A short "Essentials" mode (a dozen channels for a desk with few faders) is not built: the decoder takes its channel list from `SCALES`, so it needs a channel list per mode in `DmxDecoder`, a generated `ESSENTIALS` block next to `SCALES` (a `contract.py` change), a `mode` setting and state field in the bridge, a line in the scene page and in `make status` that says which mode is expected, and a rerun of `osc/artnet_live_test.py`. |
| `Physical` block | verified | Zeros: a video scene has no bulb, lens or weight. |
| Workspace: virtual console frames, level sliders, buttons, solo frames | verified (in the 5.3.0 workspace) | Yes: a frame per manual group, a slider per slider channel captioned with the short name, Flash buttons for the triggers, a solo frame of toggle buttons for the labelled stops of each channel that has them (path and target among them). |
| Workspace `ChannelsGroup` (a group of channels as one control) | memory, no shipped file has one | Written, one per manual group; QLC+ ignores an element it does not know. |
| Slider marks at stops | not found in any shipped workspace | Not available: the stops are buttons instead. |

## Install the fixture in QLC+

QLC+ 5.3 reads user fixtures from `~/Library/Application Support/QLC+/Fixtures` (the folder exists on this machine, empty). `make qlc-install` copies the fixture there and prints what it did; it never starts QLC+. `make qlc-fixture` is the generator (fixture, workspace and the table above, all from the contract). Restart QLC+. The workspace patches it for you; by hand it is the Fixtures tab, Add fixture, manufacturer `bossi3dj`, model `Synthwave Planet`, mode `Synthwave`, universe 1, address 1. The 37 channels appear in Simple Desk and in a fixture console.

## Set QLC+'s Art-Net output

In QLC+'s Inputs/Outputs tab pick the universe, choose the Art-Net plugin as its output and open its configuration. Choose the network interface and the Art-Net universe (QLC+ counts universes from 1 in its own list; the Art-Net universe the plugin sends is a separate setting, 0 by default, which is what the bridge listens to). The address the frames go to is the open question below.

## First check without QLC+

```bash
python3 osc/artnet_send.py /vj/fog=0.9 /vj/night=0.5
python3 osc/artnet_send.py /vj/shock=1
python3 osc/artnet_send.py 127.0.0.1:6454 --universe 0 --start 1 /vj/target=4 --dry-run
```

The sender sends one frame of defaults first (the bridge's baseline), then five frames with your values on top, like a desk, and for a trigger a last frame with it back at 0. `--broadcast` sends to a broadcast address. Without Blender running, nothing listens and nothing happens.

## Live test with the sender, 2026-11-12

History: this run was on the 12-shot contract, before the Path Camera and Takeover. `osc/artnet_live_test.py` now checks `/vj/target` ranges in row e and the Takeover pause in row c; it has not run live since.

`python3 osc/artnet_live_test.py` against the planet scene (`make blender-open`, committed round 13 build), frames to 127.0.0.1:6454 universe 0 from `osc/artnet_send.py`'s frame builder, one OSC packet to udp 9201, every result read back from the page's API (`/api/state`: values, `osc.source`, `osc.log`, camera). At the start the bridge reported `bound: true` on udp 6454, universe 0, address 1, 37 channels, 12 shots.

| Row | Result | What was read back |
|---|---|---|
| Baseline and equal frames change nothing | ok | first run after the start: four frames, values equal, `applied` 3 to 3 |
| A changed channel sets its control, source `artnet` | ok | `/vj/fog_glow` wire 0.25 gave scene 0.502 (range 0 to 2), source `artnet` |
| A resting channel does not override OSC | ok | OSC 0.75 gave 1.500 (source `osc`); four equal frames after it left 1.500 and source `osc` |
| A trigger fires once on the rise through 128 | ok | `/vj/shock` in the log: 1.50, then 0.00 (one rise at full strength, one fall) |
| The camera channel picks the shots by range | ok | DMX 0 and 21 gave `CAM_0`, 22 gave `CAM_1`, 64 `CAM_3`, 128 `CAM_6`, 234 `CAM_10`, 235 and 255 `CAM_11` (the Flight): the 12 ranges of the table below |
| A held control ignores Art-Net | ok | `vj_fog_glow` unchanged at 0.596 with the hold on, `held` counter rose |
| Another universe is ignored | ok | frames to universe 1 changed nothing; the bridge counted them (`other_universe` 10) |
| Restore | ok | the baseline frame again, then `vj_fog_glow`, `vj_cam`, `vj_shock` and the holds set back; every value and the camera as at the start |

Bridge counters at the end: 94 ArtDmx packets, 84 frames of universe 0, 32 changed channels applied, 0 malformed.

Notes from the run:

- The sender's own baseline frame holds the fixture defaults. The bridge treats only the first frame after the start (or after a settings change) as the baseline, so a later run of the sender whose first frame differs from the last one of the previous run changes those channels. That is a desk moving its faders, not a fault.
- The page's status line does not show the Art-Net state yet: `/api/state` has no Art-Net entry, so this test read the listener from the bridge (`artnet_state()` through the Blender MCP). Showing it needs a change in `blender/scenes/synthwave_web.py` (session B11's file): `snap["osc"]["artnet"] = bridge.artnet_state()` in `publish()` and a chip in `synthwave_control.html`.
- QLC+ was not running, so whether udp 6454 can be shared with it is still untested.

## The one open risk: sharing udp 6454 with QLC+

QLC+ opens udp 6454 itself (its Art-Net plugin listens as well as sends), and so does the bridge. On one machine both must be able to use the port.

What is known without having run it:

- The bridge sets `SO_REUSEADDR` and `SO_REUSEPORT` on a non-blocking socket bound to every interface, which is what lets two listeners share a port on macOS.
- On macOS, a broadcast datagram is delivered to every socket bound to the port, but a unicast datagram (for example to 127.0.0.1:6454) goes to only one of them. So if both bind, QLC+ should send to a broadcast address, not to 127.0.0.1.
- If QLC+ binds without the reuse options, the second one to bind fails: if the bridge is first, QLC+'s Art-Net plugin may not start; if QLC+ is first, the bridge reports `bound: false` with the error.
- I could not read from the QLC+ binary (5.3.0, GIT build, `PlugIns/libartnet.dylib`) how it binds or which address it sends to by default; the shipped fixtures are in the 4.12 definition format, which the generated file follows. From memory, the plugin binds with Qt's address sharing and sends to the interface's broadcast address unless a unicast IP is set per output in its configuration. That is not verified.

What the live test must show (with the user's QLC+, Blender running with the planet):

1. `make blender-open`, then in the bridge state `artnet_state()["bound"]` is true. Start QLC+: is the bridge still bound, does QLC+'s Art-Net plugin start (no bind error in its log)?
2. QLC+ output to the interface's broadcast address: move the `/vj/fog` fader, `packets` and `changes` in `artnet_state()` rise and the fog changes. Repeat with output to 127.0.0.1: does the bridge still get the frames?
3. The baseline, a trigger (`/vj/shock` rise through 128), `/vj/target` ranges, the Takeover pause and the start address offset on the real scene.
4. Magic or the page moving the same control while QLC+'s fader rests: the page wins, nothing flickers.

If it cannot work on one machine, the fallback is QLC+'s OSC output plugin (`PlugIns/libosc.dylib`) into the existing OSC path (udp 9201): QLC+ would send each channel as an OSC message to the bridge, with the address per channel set in the plugin's configuration. That is not built, and how QLC+ scales the value (0 to 255 or 0 to 1) would need to be checked first.

## Tests

`python3 -m unittest discover blender/tests` (packet parse, channel map, change-only, baseline, triggers, camera ranges, start address, the bridge's wiring on ephemeral ports) and `python3 -m unittest discover osc/tests` (the fixture file and this table equal what the generator makes from the contract, the .qxf has what QLC+ needs, the sender and the decoder agree). None binds udp 6454 or 9201.
