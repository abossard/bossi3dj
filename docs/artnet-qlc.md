# Art-Net and QLC+ for the Blender scene

A lighting desk or QLC+ can drive the Blender scene over Art-Net, next to Magic and the scene page. The bridge ([blender/blender_osc_bridge.py](../blender/blender_osc_bridge.py), Art-Net part in [blender/artnet_input.py](../blender/artnet_input.py)) listens for ArtDmx frames on udp 6454. One QLC+ fixture, [qlc/bossi3dj-Synthwave-Planet.qxf](../qlc/bossi3dj-Synthwave-Planet.qxf), has one DMX channel per address the Blender scene reacts to. Status: built, unit tested, and tried live with the sender (below); not yet tried with a running QLC+.

## What the bridge does with a frame

- **Settings** (`bridge.configure_artnet(enabled, universe, address)`): Art-Net on, universe 0, DMX start address 1. The scene page can show them later. A failed bind of udp 6454 is not fatal: the bridge reports it in `bridge.artnet_state()` (`bound`, `error`) and goes on with OSC.
- **One channel per address**, 37 in all, in contract order (the order of `SCALES` in the bridge): channel 1 is `/vj/level`. The table is below. `make qlc-fixture` rewrites the fixture and the table from [osc/contract.json](../osc/contract.json).
- **A value is a DMX value 0 to 255** mapped linearly onto the row's wire range (0 to 1 for a float), then it takes the same way as an OSC message: scaled to scene units, kept inside the property's limits, skipped when the page holds the control. In the bridge state the source is `artnet`.
- **Only changes are applied.** A desk sends every channel in every frame, Magic only on change. A channel is applied only when its DMX value differs from the last frame, so a resting fader never fights Magic or the page. The first frame after the start, and the first one after the universe or address changes, is the baseline and applies nothing. So after a start the desk's faders do nothing until you move them.
- **Triggers** (`/vj/shock`, `/vj/meteor`, `/vj/hit`): a rise through 128 fires once. The strength is 0.5 at 128 and grows to the row's wire maximum at 255 (`/vj/shock` 1.5, the others 1). When the channel falls below 128 the trigger gets 0 again, so the next rise is a new edge.
- **`/vj/cam`**: 0 to 255 is split into equal ranges, one per shot of the scene that runs: 12 on the planet (`CAM_0` to `CAM_10` and the Flight), 7 on the island. The fixture names the planet's 12 ranges; the island's ranges are in the second table below.
- **Who wins:** Art-Net, OSC from Magic and the scene page all write the same scene properties; the last change wins, and the page's hold (the H button, or a running check) stays above both. Within one tick OSC is applied first, then Art-Net.

## Channel table

<!-- artnet-channels:begin -->
| DMX channel | Address | What you see | DMX to wire value |
|---|---|---|---|
| 1 | `/vj/level` | The sun and its glow get stronger the louder the music is. | 0..255 = 0..1 |
| 2 | `/vj/bass` | Bass makes things hit harder: the glowing ground net and waterline in Blender, the shake and dust of each footfall in Godot. | 0..255 = 0..1 |
| 3 | `/vj/beat` | Pulses on every beat: pyramid edges, stars and water glints in Blender, footfalls and dust puffs in Godot. | 0..255 = 0..1 |
| 4 | `/vj/hue` | Turns all colours around the colour wheel. | 0..255 = 0..1 |
| 5 | `/vj/intensity` | Makes the whole picture brighter or darker. | 0..255 = 0..1 |
| 6 | `/vj/strobe` | Flashes the picture to white; higher means a stronger flash. | 0..255 = 0..1 |
| 7 | `/vj/grid_speed` | Makes the glowing grid on the ground scroll faster. | 0..255 = 0..1 |
| 8 | `/vj/cam` | Cuts to camera number N; 0 is the first shot. | split into equal ranges, one per shot (below) |
| 9 | `/vj/cam_speed` | Makes the camera drift and fly faster or slower. | 0..255 = 0..1 |
| 10 | `/vj/sun` | Lifts the sun up the sky and makes it bigger; 0 sinks it below the horizon. | 0..255 = 0..1 |
| 11 | `/vj/moon` | Makes the moon bigger or smaller. | 0..255 = 0..1 |
| 12 | `/vj/moon_phase` | Changes the shape of the moon from new through half to full. | 0..255 = 0..1 |
| 13 | `/vj/pyramids` | Makes the pyramids rise out of the ground. | 0..255 = 0..1 |
| 14 | `/vj/grid` | Shows the real triangle edges of the ground as a glowing net at night; by day there is none. | 0..255 = 0..1 |
| 15 | `/vj/stars` | Fades the stars in or out. | 0..255 = 0..1 |
| 16 | `/vj/water` | Turns the reflections on the water up or down. | 0..255 = 0..1 |
| 17 | `/vj/night` | Turns day into night: 0 is day, a quarter is sunset, half is twilight, 1 is night. | 0..255 = 0..1 |
| 18 | `/vj/nebula` | Fades in the coloured cloud in the night sky. | 0..255 = 0..1 |
| 19 | `/vj/shock` | A shock wave runs over the land once; in Godot the giant shakes while the Wanderer is on it. | below 128 off; from 128 fires once, strength 0.5 at 128 up to 1.5 at 255, back below 128 re-arms |
| 20 | `/vj/meteor` | A shooting star crosses the sky. | below 128 off; from 128 fires once, strength 0.5 at 128 up to 1 at 255, back below 128 re-arms |
| 21 | `/vj/flamingos` | Makes the flock of flamingos bigger; 0 hides it. | 0..255 = 0..1 |
| 22 | `/vj/fog` | More fog near the ground; at 1 it is dense autumn fog. | 0..255 = 0..1 |
| 23 | `/vj/fog_height` | Makes the fog bank taller or lower. | 0..255 = 0..1 |
| 24 | `/vj/fog_glow` | Makes the fog glow by itself. | 0..255 = 0..1 |
| 25 | `/vj/fog_hue` | Tints the fog pink, violet or cyan. | 0..255 = 0..1 |
| 26 | `/vj/fog_noise` | Makes the fog patchier. | 0..255 = 0..1 |
| 27 | `/vj/fog_scale` | Makes the fog clouds bigger or smaller. | 0..255 = 0..1 |
| 28 | `/vj/fog_speed` | Makes the wind push the fog along faster. | 0..255 = 0..1 |
| 29 | `/vj/fog_beat` | Makes the fog pump with the beat. | 0..255 = 0..1 |
| 30 | `/vj/haze` | Adds or removes the soft haze toward the horizon. | 0..255 = 0..1 |
| 31 | `/vj/eclipse` | Lines the moon up with the sun and the planet for an eclipse. | 0..255 = 0..1 |
| 32 | `/vj/star_speed` | Makes the stars drift across the sky. | 0..255 = 0..1 |
| 33 | `/vj/flight` | Steers the flying camera: 0 high orbit, then a landing approach, a skim over the mountains, and at 1 a hover over the water. | 0..255 = 0..1 |
| 34 | `/vj/boost` | Gives the flying camera a burst of speed with a wider view. | 0..255 = 0..1 |
| 35 | `/vj/blend` | Makes a camera change fly smoothly to the new shot; 0 cuts at once. | 0..255 = 0..1 |
| 36 | `/vj/energy` | Makes the camera move harder, from a slow wide glide to faster, tighter moves. | 0..255 = 0..1 |
| 37 | `/vj/hit` | A quick surge of speed with a wide-angle kick on the camera. | below 128 off; from 128 fires once, strength 0.5 at 128 up to 1 at 255, back below 128 re-arms |

`/vj/cam` ranges (channel 8), one per shot of the scene that runs:

| Scene | DMX value | Shot |
|---|---|---|
| Planet | 0 to 21 | 0 Plaza View |
| Planet | 22 to 42 | 1 River Skim |
| Planet | 43 to 63 | 2 Pyramid Hero |
| Planet | 64 to 85 | 3 Moon Watch |
| Planet | 86 to 106 | 4 Pole Flyover |
| Planet | 107 to 127 | 5 Pyramid Orbit |
| Planet | 128 to 149 | 6 Planet Orbit |
| Planet | 150 to 170 | 7 Flamingo Lake |
| Planet | 171 to 191 | 8 River Mouth |
| Planet | 192 to 213 | 9 Far Pyramids |
| Planet | 214 to 234 | 10 Coast Pass |
| Planet | 235 to 255 | 11 Flight |
| Island | 0 to 36 | 0 Plaza View |
| Island | 37 to 73 | 1 Valley Low |
| Island | 74 to 109 | 2 Pyramid Hero |
| Island | 110 to 146 | 3 Moon Watch |
| Island | 147 to 182 | 4 Flyover |
| Island | 183 to 219 | 5 Pyramid Orbit |
| Island | 220 to 255 | 6 Wide Orbit |
<!-- artnet-channels:end -->

## Install the fixture in QLC+

QLC+ reads user fixtures from `~/Library/Application Support/QLC+/Fixtures` (the folder exists once QLC+ has run). From the repository folder:

```bash
mkdir -p ~/Library/Application\ Support/QLC+/Fixtures && cp qlc/bossi3dj-Synthwave-Planet.qxf ~/Library/Application\ Support/QLC+/Fixtures/
```

Restart QLC+. Then in the Fixtures tab: Add fixture, manufacturer `bossi3dj`, model `Synthwave Planet`, mode `Synthwave`, universe 1, address 1. The 37 channels appear in Simple Desk and in a fixture console.

## Set QLC+'s Art-Net output

In QLC+'s Inputs/Outputs tab pick the universe, choose the Art-Net plugin as its output and open its configuration. Choose the network interface and the Art-Net universe (QLC+ counts universes from 1 in its own list; the Art-Net universe the plugin sends is a separate setting, 0 by default, which is what the bridge listens to). The address the frames go to is the open question below.

## First check without QLC+

```bash
python3 osc/artnet_send.py /vj/fog=0.9 /vj/night=0.5
python3 osc/artnet_send.py /vj/shock=1
python3 osc/artnet_send.py 127.0.0.1:6454 --universe 0 --start 1 /vj/cam=3 --dry-run
```

The sender sends one frame of defaults first (the bridge's baseline), then five frames with your values on top, like a desk, and for a trigger a last frame with it back at 0. `--broadcast` sends to a broadcast address. Without Blender running, nothing listens and nothing happens.

## Live test with the sender, 2026-11-12

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
3. The baseline, a trigger (`/vj/shock` rise through 128), `/vj/cam` ranges and the start address offset on the real scene.
4. Magic or the page moving the same control while QLC+'s fader rests: the page wins, nothing flickers.

If it cannot work on one machine, the fallback is QLC+'s OSC output plugin (`PlugIns/libosc.dylib`) into the existing OSC path (udp 9201): QLC+ would send each channel as an OSC message to the bridge, with the address per channel set in the plugin's configuration. That is not built, and how QLC+ scales the value (0 to 255 or 0 to 1) would need to be checked first.

## Tests

`python3 -m unittest discover blender/tests` (packet parse, channel map, change-only, baseline, triggers, camera ranges, start address, the bridge's wiring on ephemeral ports) and `python3 -m unittest discover osc/tests` (the fixture file and this table equal what the generator makes from the contract, the .qxf has what QLC+ needs, the sender and the decoder agree). None binds udp 6454 or 9201.
