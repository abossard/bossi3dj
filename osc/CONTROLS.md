# The `/vj/*` control contract

One row per address. Magic sends them (generator `magic/synthwave_magic.py`, one float32 per datagram, only on change), `osc/lab.py` relays every packet to Blender (udp 9201) and Godot (udp 9202).

The source of the rows is [contract.json](contract.json). The table below, the bridge's `SCALES` block and the lab page are made from it (`python3 osc/contract.py sync`); `osc/tests/test_contract.py` fails when a copy drifts. Change the row first, then the Magic generator, then each scene. A scene that ignores an address says "not used".

## Rules

- A continuous control is 0..1 on the wire. Each scene scales it to its own range (the Blender and Godot columns), so one address means one thing and the wire default gives each scene its tuned look.
- An index (`/vj/cam`, `/vj/cam_auto`) is an integer on the wire, sent as a float32 holding a whole number. Scenes round it.
- A trigger fires on the rising edge above 0.5. The value is the strength and is not scaled (`/vj/shock` 0.5..1.5, 1.4 and above marks a drop in Godot).
- Wire values are clamped to the row's range before scaling. Out-of-range input never overdrives a scene.
- `/vj/cam N` picks the scene's Nth shot, 0-based. N above the last shot takes the last. Blender cuts to `CAM_N`, Godot pins the director's Nth shot.
- `/vj/cam_auto` is 0 or 1, default 1. 1 hands the cuts to the scene's own director (Godot follows it and ignores `/vj/cam`). 0 holds the shot `/vj/cam` picks. Blender ignores it and follows `/vj/cam` always, so Magic's own auto-cutter drives Blender.
- A scene ignores an address that is not a row, and keeps the last value of a row until the next packet. No address expires.
- Where the wire default does not map to a round scene value the row says so: `/vj/fog_height` carries 0.42 on the wire (25.2 m in Blender, 25 m is 0.4167).
- Without OSC each scene keeps moving: Blender fades in a 124 BPM idle pulse after 2 s, Godot runs an internal 90 BPM beat while `/vj/beat` is quiet.
- Neither scene sends OSC. Blender answers `/lab/ping` with `/lab/pong` for the relay page.

## Addresses

<!-- contract-table:begin -->
| Address | Wire | Blender (`blender/scenes`) | Godot (`godot/colossus`) |
|---|---|---|---|
| `/vj/level` | 0..1, default 0.5 | sun, horizon glow, moon rim | 1..2.6 light energy, default 1.8. sun glow through the cloud gap |
| `/vj/bass` | 0..1, default 0 | ground wireframe brightness, waterline rim | 0.5..1 weight, default 0.5. footfall weight: camera shake, dust size |
| `/vj/beat` | 0..1, default 0 | pyramid edges and capstones, stars, grid, water glints | footfalls, dust puffs, cut points; an internal 90 BPM beat runs while it is quiet |
| `/vj/hue` | 0..1, default 0 | rotates the whole palette | not used |
| `/vj/intensity` | 0..1, default 0.5 | 0..2, default 1. overall brightness | 0.2..1.8 exposure, default 1. overall exposure |
| `/vj/strobe` | 0..1, default 0 | flash to white | not used |
| `/vj/grid_speed` | 0..1, default 0.15 | 0..4 cells/s, default 0.6. island scene only: grid scroll; the planet has no scrolling lines and does not read it | not used |
| `/vj/cam` | integer 0..11, default 0 | cut to `CAM_N`; in the planet scene `CAM_11` is the Flight shot; N above the last camera of the scene takes the last | pin the director's Nth shot (0-based); N above the last shot takes the last; held only while `/vj/cam_auto` is 0 |
| `/vj/cam_auto` | integer 0..1, default 1 | not used | 1: the director cuts by itself; 0: it holds the shot `/vj/cam` picks |
| `/vj/cam_speed` | 0..1, default 0.25 | 0..4, default 1. camera drift and flyover speed | not used |
| `/vj/sun` | 0..1, default 1 | sun elevation, and size (largest at peak day): 0 sets it below the horizon (night lighting) | not used |
| `/vj/moon` | 0..1, default 1 | moon size. The Moon is not faded: it rises from below the sea as the sun goes down (`/vj/sun`, `/vj/night`) and sets again by day | not used |
| `/vj/moon_phase` | 0..1, default 1 | lunar phase: 1 full, 0.5 half, 0 new (crater shadows along the terminator). Planet scene (star system): where the moon sits on its orbit, 0 next to the sun, 1 opposite it, lit by the real sun | not used |
| `/vj/pyramids` | 0..1, default 1 | pyramids rise from the ground | not used |
| `/vj/grid` | 0..1, default 1 | planet: strength of the real edges of the drawn ground mesh (its triangles, never a lattice), fading in from sunset (/vj/night 0.25 to 0.5), full at night, none by day, pulsed by bass and beat; island: ground wireframe by day (the real low-poly mesh edges; the projected grid only remains on the night ground) | not used |
| `/vj/stars` | 0..1, default 1 | stars | not used |
| `/vj/water` | 0..1, default 1 | water reflection | not used |
| `/vj/night` | 0..1, default 0 | time of day: 0 day; 0.25 sunset; 0.5 twilight (blue hour, afterglow, land in silhouette, first stars); 1 night: black land (planet: with the real mesh edges at /vj/grid; island: its glowing low-poly wireframe), deep space sky with Milky Way, bright stars and a volumetric 3D nebula 2-5 km up. Fog darkens toward night. Flamingos take off above 0.18 and return below 0.08. Planet scene (star system): the sun's height for the camera on air, 0 +20°, 0.5 half set on the horizon, 1 -18°; the sky turns to fit, and moving it back runs time backwards | not used |
| `/vj/nebula` | 0..1, default 1 | night nebula strength | not used |
| `/vj/shock` | trigger 0..1.5, default 0 | rising edge above 0.5: shockwave from the next pyramid, a rolling ground wave (300 m/s, 170 m wavelength, up to 16 m heave) about 3.6 km out in 12 s; the sea heaves harder with chop and foam, pyramids lift and tilt, the grid warps, land and cameras shake. Up to four waves run at once. The trigger value sets the strength (0.5 to 1.5). Fires by itself every 16 s while idle | shake while the Wanderer is on the Colossus; 1.4 and above marks a drop for the next bar |
| `/vj/meteor` | trigger 0..1, default 0 | rising edge above 0.5: a shooting star (up to three at once), brightest at night. Without the trigger only rarely, every 1-3 min at night while idle | not used |
| `/vj/flamingos` | 0..1, default 1 | flamingo flock size; 0 hides them | not used |
| `/vj/fog` | 0..1, default 0.35 | fog bank density, about linear up to 0.6, then it climbs steeply to dense autumn fog at 1, where the ground barely shows. A bank of drifting 3D clouds that fills the valleys and hides what lies behind it, ray-marched per pixel on land, water and pyramids; sky, sun and moon never get it, their reflections in the water do | 0..0.0086 density, default 0.00301. volumetric fog density |
| `/vj/fog_height` | 0..1, default 0.41 | 1..60 m, default 25.19. top of the fog bank (soft over its upper half), 60 m at most so it always stays near the ground | 0..95 m, default 38.95. top of the volumetric fog |
| `/vj/fog_glow` | 0..1, default 0.3 | 0..2, default 0.6. self-glow | not used |
| `/vj/fog_hue` | 0..1, default 0 | colour: pink, violet, cyan, back to pink | not used |
| `/vj/fog_noise` | 0..1, default 0.6 | patchiness | not used |
| `/vj/fog_scale` | 0..1, default 0.25 | 10..1000 m, default 257.5. cloud size | not used |
| `/vj/fog_speed` | 0..1, default 0.25 | 0..40 m/s, default 10. wind drift | not used |
| `/vj/fog_beat` | 0..1, default 0.5 | beat pumping | not used |
| `/vj/haze` | 0..1, default 1 | distance haze toward the horizon; 0 with `/vj/fog` 0 gives a fog-free view | 0..0.00025 density, default 0.00025. distance haze |
| `/vj/eclipse` | 0..1, default 0 | planet scene (star system): turns the moon's tilted orbit into line with the sun, a lunar eclipse in the planet's shadow at full moon, a solar eclipse at new moon | not used |
| `/vj/star_speed` | 0..1, default 0 | 0..10 °/s, default 0. planet scene (star system): drift of the stars against the sun | not used |
| `/vj/flight` | 0..1, default 0 | planet scene, Flight camera ([plan](../docs/research/synthwave-flight.md)): 0 orbit framing the star system, 0.33 landing approach, 0.66 skim over the mountains, 1 hover over water. Damped: a jump flies, about a minute from end to end | not used |
| `/vj/boost` | 0..1, default 0 | planet scene, Flight camera: the accelerator while skimming or hovering, a surge forward with a wider view | not used |
| `/vj/blend` | 0..1, default 0.5 | 0..2, default 1. planet scene: duration scale of shot changes, which fly from the current view to the new shot; 0 cuts | not used |
| `/vj/energy` | 0..1, default 0.3 | planet scene: how hard every camera moves. Eased (up over 1.5 s, down over 4 s). Low: a slow, wide floating glide; high: faster, pushed in, tighter lens, bigger pulse accents. Every shot keeps moving even at 0 | not used |
| `/vj/hit` | trigger 0..1, default 0 | planet scene: rising edge above 0.5: a surge of speed with a wide-angle kick (lens to 0.7x, back over 2 s), a swoop along the path on moving shots | not used |
<!-- contract-table:end -->

## Driving a scene without Magic

- `make lab`, then http://127.0.0.1:8765: one slider per row in wire units at the wire default, generators (sine, beat pulse, ramp) on any row, all reach both scenes.
- `make osc-sweep` walks every row through its minimum, default and maximum (triggers fire once), to the relay or to one scene's port.
- Blender only: http://127.0.0.1:9210, one control per `vj_*` property in scene units, with holds and a beat simulator.
