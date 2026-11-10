# The `/vj/*` control contract

One row per address. Magic sends them (generator `magic/synthwave_magic.py`, one float32 per datagram, only on change), `osc/lab.py` relays every packet to Blender (udp 9201) and Godot (udp 9202). Range and default are what Magic sends and what the Blender runtime's `RANGES` and `DEFAULTS` hold.

Change a row first, then the generator, then each scene. A scene that ignores an address says "not used".

## Open mismatches

Both scenes hear the same packets, so one address must mean one thing. Read from the code on 2026-11-10, not yet observed live:

- `/vj/fog_height`: Magic sends metres (0..60, default 25). Godot reads 0..1 and maps it to 10..90 m without a clamp, so 25 becomes about 2 km of fog height.
- `/vj/cam`: Blender cuts to `CAM_N` (0..6 island, 0..10 planet, 0 is a camera). Godot takes 1..5 as director shots and 0 as "auto". One fader moves both.
- Staleness: Magic sends a value only when it changes. Godot drops an address 2 s after its last packet and returns to its rest value; Blender keeps the last value. A fader that stands still loses its effect in Godot after 2 s.
- Defaults differ per scene (`/vj/fog` 0.35 against 0.1, `/vj/haze` 1 against 0.05), so the same Magic default gives Godot far more fog than its tuned look.

Deciding these (0..1 everywhere with per-scene scaling, per-scene address prefixes, or per-scene Magic Globals) is open in [STATE.md](../STATE.md).

## Addresses

| Address | Range | Default | Blender (`blender/scenes`) | Godot (`godot/colossus`) |
|---|---|---|---|---|
| `/vj/level` | 0..1 | 0.5 | sun, horizon glow, moon rim | sun glow through the cloud gap (rest 0.33) |
| `/vj/bass` | 0..1 | 0 | ground wireframe brightness, waterline rim | footfall weight: camera shake, dust size (rest 0.5) |
| `/vj/beat` | 0..1 | 0 | pyramid edges and capstones, stars, grid, water glints | footfalls, dust puffs, cut points; internal 90 BPM beat while quiet |
| `/vj/hue` | 0..1 | 0 | rotates the whole palette | not used |
| `/vj/intensity` | 0..2 | 1 | overall brightness | overall exposure, 0.2..2 (rest 1) |
| `/vj/strobe` | 0..1 | 0 | flash to white | not used |
| `/vj/grid_speed` | grid cells/s | 0.6 | grid scroll | not used |
| `/vj/cam` | 0..6 | 0 | cut to `CAM_N` | **1..5 pins that director shot, 0 hands cuts back to the director** |
| `/vj/cam_speed` | 0..4 | 1 | camera drift and flyover speed | not used |
| `/vj/sun` | 0..1 | 1 | sun elevation, and size (largest at peak day): 0 sets it below the horizon (night lighting) | not used |
| `/vj/moon` | 0..1 | 1 | moon size. The Moon is not faded: it rises from below the sea as the sun goes down (`/vj/sun`, `/vj/night`) and sets again by day | not used |
| `/vj/moon_phase` | 0..1 | 1 | lunar phase: 1 full, 0.5 half, 0 new (crater shadows along the terminator). Planet scene (star system): where the moon sits on its orbit, 0 next to the sun, 1 opposite it, lit by the real sun | not used |
| `/vj/pyramids` | 0..1 | 1 | pyramids rise from the ground | not used |
| `/vj/grid`, `/vj/stars`, `/vj/water` | 0..1 | 1 | ground wireframe by day (the real low-poly mesh edges; the projected grid only remains on the night ground), stars, water reflection | not used |
| `/vj/night` | 0..1 | 0 | time of day: 0 day; 0.25 sunset; 0.5 twilight (blue hour, afterglow, land in silhouette, first stars); 1 night: black land with glowing low-poly wireframe, deep space sky with Milky Way, bright stars and a volumetric 3D nebula 2–5 km up. Fog darkens toward night. Flamingos take off above 0.18 and return below 0.08. Planet scene (star system): the sun's height for the camera on air, 0 +20°, 0.5 half set on the horizon, 1 -18°; the sky turns to fit, and moving it back runs time backwards | not used |
| `/vj/nebula` | 0..1 | 1 | night nebula strength | not used |
| `/vj/shock` | trigger | 0 | rising edge above 0.5: shockwave from the next pyramid. No colour: a rolling ground wave (300 m/s, 170 m wavelength, up to 16 m heave, up to 5× that on the mountains) runs about 3.6 km out over land, mountains and water in 12 s (GPU displacement); the sea heaves harder, with a train of short chop behind the swell and whitewater foam on the high crests (faded within ~200 m of the camera so low shots stay clear), pyramids lift and tilt with it, the grid warps, land and cameras shake. Up to four waves run at once, so one per heavy kick overlaps (they saturate rather than stack). The trigger value sets the strength (0.5..1.5). Fires by itself every 16 s while idle | Shake while the Wanderer is on the Colossus; 1.4 and above marks a drop for the next bar |
| `/vj/meteor` | trigger | 0 | rising edge above 0.5: a shooting star (up to three at once), brightest at night. Without the trigger only rarely, every 1–3 min at night while idle | not used |
| `/vj/flamingos` | 0..1 | 1 | flamingo flock size; 0 hides them | not used |
| `/vj/fog` | 0..1 | 0.35 | fog bank density, about linear up to 0.6, then it climbs steeply to dense autumn fog at 1, where the ground barely shows. A bank of drifting 3D clouds that fills the valleys and hides what lies behind it, ray-marched per pixel on land, water and pyramids (6 cloud samples along the view ray, no EEVEE volume), so it does not crawl, flicker or show blocks; sky, sun and moon never get it, their reflections in the water do | volumetric fog density (rest 0.1) |
| `/vj/fog_height` | m | 25 | top of the fog bank (soft over its upper half), capped at 60 m so it always stays near the ground | **expects 0..1** (10 to 90 m, rest 0.375) |
| `/vj/fog_glow` | 0..2 | 0.6 | self-glow | not used |
| `/vj/fog_hue` | 0..1 | 0 | colour: pink, violet, cyan, back to pink | not used |
| `/vj/fog_noise` | 0..1 | 0.6 | patchiness | not used |
| `/vj/fog_scale` | m | 260 | cloud size | not used |
| `/vj/fog_speed` | m/s | 10 | wind drift | not used |
| `/vj/fog_beat` | 0..1 | 0.5 | beat pumping | not used |
| `/vj/haze` | 0..1 | 1 | distance haze toward the horizon; 0 with `/vj/fog 0` gives a fog-free view | distance haze (rest 0.05) |
| `/vj/eclipse` | 0..1 | 0 | planet scene (star system): turns the moon's tilted orbit into line with the sun, a lunar eclipse in the planet's shadow at full moon, a solar eclipse at new moon | not used |
| `/vj/star_speed` | 0..10 | 0 | planet scene (star system): drift of the stars against the sun, 1° per second at 1 | not used |
| `/vj/flight` | 0..1 | 0 | planet scene, Flight camera (being built, [plan](../docs/research/synthwave-flight.md)): 0 orbit framing the star system, 0.33 landing approach, 0.66 skim over the mountains, 1 hover over water. Damped: a jump flies, about a minute from end to end | not used |
| `/vj/boost` | 0..1 | 0 | planet scene, Flight camera (being built): the accelerator while skimming or hovering, a surge forward with a wider view | not used |
| `/vj/blend` | 0..2 | 1 | planet scene (being built): duration scale of shot changes, which fly from the current view to the new shot; 0 cuts | not used |
| `/vj/energy` | 0..1 | 0.3 | planet scene (being built): how hard every camera moves. Eased (up over 1.5 s, down over 4 s). Low: a slow, wide floating glide; high: faster, pushed in, tighter lens, bigger pulse accents. Every shot keeps moving even at 0 | not used |
| `/vj/hit` | trigger | 0 | planet scene (being built): rising edge above 0.5: a surge of speed with a wide-angle kick (lens to 0.7x, back over 2 s), a swoop along the path on moving shots | not used |

## Behaviour both scenes share

- A trigger fires on the rising edge above 0.5. The value at the edge is the strength.
- Without OSC each scene keeps moving: Blender fades in a 124 BPM idle pulse after 2 s, Godot runs an internal 90 BPM beat while `/vj/beat` is quiet.
- Neither scene sends OSC. Blender answers `/lab/ping` with `/lab/pong` for the relay page.

## Driving a scene without Magic

- `make lab`, then http://127.0.0.1:8765: sliders and generators (sine, beat pulse, ramp) reach both scenes.
- Blender only: http://127.0.0.1:9210, one control per `vj_*` property, with holds and a beat simulator.
