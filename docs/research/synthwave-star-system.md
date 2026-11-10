# A real star system for the synthwave planet

Question: how should the sun, moon and stars of `scenes/synthwave_planet.blend` move so that every camera sees one consistent sky, day and night come from real geometry, and the cameras know where the light is?

- Researched 2026-11-04 with the user. The decisions below come from their answers.
- The current scene was read from `planet_proto/build_planet.py`, `planet_runtime.py`, the island build, `synthwave_runtime.py` and `day_world.py` on `research/synthwave-planet`.
- Labels: **Fact** (read in code or a source), **Verified** (checked by [verify_star_system.py](synthwave-star-system/verify_star_system.py)), **Decision** (the user's), **Inference**, **Recommendation**.

## Answer

- **Decision:** the Planet stays fixed. The Star System (sun, moon, stars) turns around one spin axis, so every camera shares one sky.
- **Verified:** for every observer, turning the sky backwards gives the same sun height and direction as spinning the planet (check 3, error 5e-13°).
- **Decision:** `/vj/night` keeps control of the mood:
  - It maps to Sun Height for the On-Air Camera: 0 is +20°, 0.5 is the horizon, 1 is -18°.
  - The sky angle is solved in closed form for that camera, always on the setting side, so moving the knob back runs time backwards.
- **Decision:** the moon is on a real orbit, lit by the real sun:
  - `/vj/moon_phase` picks where it sits around its orbit.
  - The planet's shadow falls on it, and `/vj/eclipse` (0..1) lines the orbit up for lunar and solar eclipses.
- **Decision:** the stars drift slowly against the sun at `/vj/star_speed`. There are no seasons.
- **Decision:** sun and moon shots aim at their body on every cut. All other shots keep their framing.
- **Decision:** the look stays synthwave, and the output targets a steady 60 fps.
- **Verified:** every formula below passes its numeric check:
  - against NOAA's solar zenith and azimuth formulas
  - against Meeus's illuminated fraction
  - against NASA's period figures
  - by self-consistency (re-solving the inverse forward)

## Decisions

| # | Question | Answer |
|---|---|---|
| Q1 | How the star system works | The sky turns and the planet stays still |
| Q2 | Output frame rate | Steady 60 fps |
| Q3 | Look of the little earth | Synthwave look, real sky |
| Q4 | What sets the time of day | `/vj/night` stays in charge: the sky turns so the On-Air Camera sees the requested Sun Height |
| Q5 | Moon motion and phase | Real orbit, lit by the real sun; `/vj/moon_phase` picks the orbit position |
| Q6 | Seasons | None (fixed equinox) |
| Q7 | Night mapping | 0 → +20°, 0.5 → 0°, 1 → -18° |
| Q8 | Camera aim | Sun and moon shots track their body; other shots keep their framing |
| Q9 | Camera area latitude | On the equator of the spin axis |
| Q10 | Planet shadow on the moon | Real shadow and eclipses |
| Q11 | How eclipses happen | `/vj/eclipse` knob 0..1 |
| Q12 | Eclipse depth | Closer, smaller moon (50 km orbit, 11.5 km radius), shadow cast from a true-size sun |
| Q13 | Night back to day | The sky runs backwards |
| Q14 | Star drift | Slow drift against the sun, `/vj/star_speed` |

## Today

- **Fact:** the planet has radius `R = 16000` m and centre `C = (0, 0, -R)`. The camera area sits at the mesh pole (world origin), within about 9 km of arc of it. Nothing rotates.
- **Fact:** the sky is placed per shot by `Sky_Frame`:
  - The runtime's `place_sky` moves an empty to the ground point under the camera and writes `rt_up_*`.
  - The sun, moon, corona and nebula are parented to it, so each camera has its own sun.
- **Fact:** the sun always sits at the frame's local +y, at an elevation of -13.75° to +9.17° (`VJ_SunDir`: `el = maprange(vj_sun*(1-Dusk), 0..1 → -0.24..0.16 rad)`). It is drawn at `D_SUN = 150000` m with a radius of 0.18 to 0.30 rad.
- **Fact:** the moon rises on a fixed arc (`MOON_AZ = 30°`, elevation -18 to +22°) at `D_MOON = 120000` m with a radius of about 28 km.
  - Its phase comes from a virtual light set by `vj_moon_phase`, which ignores the sun.
  - The water's moon glint uses the fixed world vector `MOON_C`.
- **Fact:** every material is emission-only, and there are no Blender lights.
  - Shading uses hand-made `dot(N, sun.Dir)` terms.
  - A second fixed key light `SUN_KEY = (-0.72, -0.30, 0.62)` does not turn with the sky.
- **Fact:** the stars live in the world shader and turn with the frame. `rt_space` (camera above 2 km) switches to the space sky, and only CAM_6 (orbit, 54.4 km from the centre) gets there.

## Frames and symbols

- World frame: z up, metres. Planet centre `C = (0, 0, -R)`, `R = 16000`.
- Spin axis `A = +x`, through `C`.
  - **Decision (Q9):** that puts the camera area on the equator.
  - **Inference:** with this axis the sun sets toward +y, as it does today, so the current shot framings stay valid.
- Sun: a unit direction `s`, at infinity for lighting and shadows. Its disc is drawn along `s` from the On-Air Camera.
- Moon: a point `m` on the orbit sphere `|m - C| = a`, with `a = 50000` m and moon radius `r_m = 11500` m.
- Stars: directions, turned by the spin angle plus the drift.
- Surface frame at a point `p`: `up = (p - C)/|p - C|`, `east = normalize(A × up)`, `north = up × east`. On the equator this "north" points along the spin axis.
- Rotation: Rodrigues, `rot(k, φ, v) = v cos φ + (k × v) sin φ + k (k·v)(1 - cos φ)`. In shader nodes this is the Vector Rotate node (Axis Angle).

## Math

### 1. Sun height and direction

- `sin h = up · s`, and azimuth `az = atan2(s·east, s·north)`, measured clockwise from north.
- **Verified (1a, 1b):** these match NOAA's `cos z = sin lat sin decl + cos lat cos decl cos ha` to 7e-13°. They also match the standard azimuth `cos az = (sin decl - sin lat cos z)/(cos lat sin z)`, mirrored when `ha > 0`, to 1e-10°.
- **Verified (1c):** NOAA's PDF prints the azimuth as `cos(180 - θ) = -(sin lat cos z - sin decl)/(cos lat sin z)`. As extracted, that gives `180° - az`, a north-south mirror. Use the standard form.

### 2. Turning the sky instead of the planet

- Spinning the planet by `M` while keeping the sun at `s` is the same as keeping the planet still and turning the sun to `Mᵀ s`. The surface frame turns with `M`, so `up·s` and the azimuth are unchanged.
- **Verified (3):** to 5e-13° for random spins, tilts and surface points.
- **Inference:** this is why the planet can stay still. World-space shader noise (fog, waves), the LOD and the flocks keep their coordinates.

### 3. Night to Sun Height

- `h(n) = 20° - 40°·n` for `n < 0.5`, and `-36°·(n - 0.5)` for `n ≥ 0.5`.
- That's linear in each half: 0 is +20°, 0.5 is the horizon (the striped sun half set), 1 is -18°, the end of astronomical twilight.
- **Fact:** civil twilight is 0 to -6°, nautical -6 to -12°, astronomical -12 to -18° (Wikipedia, Twilight).
- **Recommendation:** drive the sky colour and the night layers from `h`, not from `n`. Then the night grid, stars and day-world swap follow the real light. The swap condition becomes "no night layer has weight at this `h`".

### 4. The sky angle for a Sun Height

- With no seasons the sun stays in the plane normal to `A`. Let `s(θ) = rot(A, -θ, ẑ)`, so `s(0)` is the zenith of the pole point and `θ` turns it toward +y.
- For the On-Air Camera with up `u`: `sin h = u·s(θ) = α cos θ + β sin θ`, where `α = u·s(0)` and `β = u·s(90°)`.
- So `θ = atan2(β, α) + arccos(sin h / hypot(α, β))`.
  - Taking the `+arccos` root keeps the sun past the camera's noon and going down. That's the setting branch, the same in both directions of the knob (Q13).
- `hypot(α, β) = cos(latitude)`. Every camera in the area is within 32° of the equator, so every `h` in -18..+20° can be reached.
- **Verified (10a-c):** 300 random area cameras and 201 night values:
  - the height is exact to 3e-14°
  - the sun is always on the setting side
  - the angle moves at most 0.24° per 1/200 of the knob
- **Verified (4):** with seasons (declination `δ`) the general form is `cos H = (sin h - sin φ sin δ)/(cos φ cos δ)`. 17% of random targets are then unreachable (polar day or night), which is one more reason for Q6.
- The runtime solves this every frame for the On-Air Camera. A cut changes the camera, so the sky jumps between shots, which is never on air (Q4).
  - For the orbit camera (`rt_space` 1, 12 km up), solve for the camera-area centre (the mesh pole). The orbit view then shows the terminator where the shots are.
  - Between 2 and 12 km up (`rt_space` 0 to 1) the up the Sun Height is measured from turns from the camera's own to the pole's along the great circle, over a smoothstep of `rt_space`, and the moon's parallax viewpoint moves the same way. Switched at `rt_space > 0`, the sun jumped as a camera rose through 2 km. At 0 and 1 the result is the same as the switch (checks 14j-l).

### 5. Sun disc and lighting

- Lighting uses `s` everywhere: terrain, pyramids, water glints, backdrop and atmosphere rim.
- **Recommendation:** the fixed `SUN_KEY` either goes or becomes a fill tied to `s`. A fixed key contradicts the real sun at night.
- The disc and corona sit at `cam + s·D_SUN` each frame (On-Air Camera).
  - A sun at a fixed world point would shift by up to `asin(R/D_SUN) = 6.1°` between cameras and then disagree with the lighting.
  - The stars are directions, so they need no placement.

### 6. Moon orbit and phase

- The orbit plane is tilted by `i` about its line of nodes `ν`, which lies in the sun's path plane (normal `A`):
  - `ν = rot(A, (1 - e)·90°, s)`
  - `n_orbit = rot(ν, i, A)`
  - `m = C + a · rot(n_orbit, E, ŝ_p)`
  - Here `ŝ_p` is `s` projected into the orbit plane, `E` is the elongation (0 new, 180° full, from `/vj/moon_phase`), and `e` is the eclipse knob.
- The phase is not computed. The moon's surface is lit by `s` (Lommel-Seeliger as today, with `L = s`), so the lit part is right by construction.
- **Verified (6):** a lit sphere's visible lit fraction equals Meeus 48.1, `k = (1 + cos i)/2`, to 3e-4.
- **Verified (11c):** to keep ordinary full moons out of the shadow, the tilt needs `sin i > (R + a tan α☉ + r_m)/a`. That's 33.7° at `a` = 50 km, so 25° is not enough. **Recommendation:** `i = 40°`.
- **Verified (11d):** at `e = 0` with a 40° tilt, seen from the pole point:
  - "full" is 93% lit
  - "new" shows a 21% crescent
  - quarter is 66% lit
  - **Inference:** knob 0 never shows a perfect full or new moon. Only knob 1 lines them up exactly.
- **Verified (12d):** the observer is on the surface, so the moon's distance and size change with its height:

| Moon height | Distance | Angular radius |
|---|---|---|
| 90° | 34.0 km | 18.7° |
| 30° | 40.0 km | 16.0° |
| 0° | 47.4 km | 13.6° |

  - Today's moon is 13°. `/vj/moon` keeps scaling `r_m`.
- **Verified (12c):** parallax is up to `asin(R/a) = 18.7°`, so far-apart cameras see the moon in quite different places. That's real, and it's why the moon shots track it (Q8).

### 7. Planet shadow on the moon (lunar eclipse)

- For a moon surface point `p`: `t = -(p - C)·s`, the depth behind the planet along the sun line. If `t > 0`, `d = |(p - C) + t s|`, the distance from the shadow axis.
- The umbra radius at that depth is `R - t tan α☉` and the penumbra radius `R + t tan α☉`, with `α☉ = 0.2667°`, the true-size sun (Q12) and not the drawn disc.
- The shadow is `clamp((r_pen - d)/(r_pen - r_um), 0, 1)`. That's 0 in full sun and 1 in the umbra, a linear ramp across the penumbra.
- **Verified (11a, 11b):**
  - at `e = 1`, full moon, every rim point is in the umbra (total eclipse)
  - at `e = 0` no point of the moon is shadowed
- **Fact:** the drawn sun disc (0.18 to 0.30 rad) would end the umbra 52 to 88 km behind the planet, before the moon, so only a partial dimming. With the true-size sun, the umbra is still 15.4 km wide at 50 km, wider than the moon (11.5 km).
- Colour: mix toward a deep red by the shadow, which is where Rayleigh-filtered light goes in a real eclipse. Earthshine stays.

### 8. Solar eclipse

- At new moon the alignment has to hold from the On-Air Camera, not from the planet centre. The 18.7° parallax would otherwise miss the sun.
- The aligned point is where the ray `cam + t s` meets the orbit sphere: `t = -b + sqrt(b² - (|o|² - a²))`, with `o = cam - C` and `b = o·s`.
- With `e > 0` near new moon, the moon blends from its orbit point to that point. Near full moon it blends toward the shadow axis `C - a s`.
- **Verified (12a, 12b):** the point lies on the sphere to 1e-11 m and on the sun line to 1e-14°.
- The moon (14 to 19°) and the drawn sun (10 to 17°) are about the same size on screen, so depth sorting does the eclipse. The moon is about 40 km away and the disc 150 km. Its dark side shows earthshine only.

### 9. Star drift

- Stars turn by `θ + β` about `A`, with `β += dt·star_speed`. The sun turns by `θ`, and the moon follows the sun through its elongation.
- **Verified (13):** the drift moves each star along its circle about the axis and leaves the Sun Height alone. With no seasons it never changes the sun's path.
- **Inference:** physically this is the sun moving along its yearly path against the stars.

### 10. Cameras

- Sun and moon shots (CAM_3 moon, CAM_9 sun, others marked so) aim on each cut. The track target goes to `cam + s·D` or to `m`. The horizon stays level through the existing `Planet_Centre` damped track.
- **Fact:** CAM_6's orbit ring (54.4 km from the centre, tilted 24°) crosses the new moon orbit sphere (50 km). Either it flies through the moon, or the moon fills its frame.
  - **Recommendation:** raise CAM_6 to about 80 km, or keep its path outside `a + r_m + margin`.
- Moving cameras (CAM_4, 5, 10 paths and the drift) get the solve every frame, so the Sun Height holds while they move.

### 11. Precision and cost

- **Verified (9):** float32 spacing is 2 mm at 20 km and 8 mm at 100 km. The moon (50 km) and the sun disc (150 km from the camera) are far inside safe precision.
- **Inference:** the runtime cost is a few vector operations per frame in Python. In the shaders, the stars need one Vector Rotate, and the moon about 10 nodes for the shadow. No new geometry.

## Interface changes

| Address | Today | New |
|---|---|---|
| `/vj/night` | Mood 0..1, sun -14..+9° on a fixed arc | Sun Height for the On-Air Camera, 0 → +20°, 0.5 → 0°, 1 → -18° |
| `/vj/moon_phase` | Angle of a virtual light | Elongation on the orbit (0 new, 1 full) |
| `/vj/moon` | Size | Size (unchanged) |
| `/vj/eclipse` | none | 0..1, lines up the orbit (lunar at full, solar at new) |
| `/vj/star_speed` | none | Drift rate of the stars against the sun |

- The Magic project needs the two new outputs, clamped to these ranges.
- The web page picks them up from the scene properties.

## Plan

1. Runtime (done, checks 14a-g): [`scenes/star_system.py`](../../blender/scenes/star_system.py), loaded by `synthwave_runtime.py` like `day_world.py`. It is inert in scenes without `Planet_Centre`.
   - Each frame it writes, for the On-Air Camera:
     - `rt_sun_x/y/z`, the world direction `s`
     - `rt_sun_h`, the Sun Height
     - `rt_moon_x/y/z`, the world moon centre
     - `rt_sky_ang` (`θ`) and `rt_star_ang` (`θ + β`)
   - It places the bodies:
     - `vj_body = "sun"` goes to `cam + s·vj_dist`, local Z level with the horizon.
     - `vj_body = "moon"` goes to the moon centre, with local -Y facing the planet.
     - Every camera with `vj_track = "sun"/"moon"`, on air or not, gets its TRACK_TO target moved onto the body each frame, so a cut or blend to a tracking shot starts on its aim. Off air its up is its own radial.
   - The planet radius comes from scene property `pl_radius` (default 16000).
   - New controls: `vj_eclipse` (0..1) and `vj_star_speed` (0..10, 1° per second at 1).
2. Build: replace `VJ_SunDir` with reads of `rt_sun_*` and `rt_sun_h`, turn the world-shader stars by `rt_star_ang` about `A`, remove `SUN_KEY` and `MOON_C`, and unparent sun, moon and corona from `Sky_Frame`.
3. Moon: orbit at 50 km, radius 11.5 km, lit by `s`, with the shadow term and the red eclipse tint. Move CAM_6 clear of the moon.
4. Sky colour from `h`: day, twilight and night ramps keyed to the twilight bands. The day-world swap keys on `h`.
5. Camera tracking for the sun and moon shots.
6. Magic: `/vj/eclipse` and `/vj/star_speed` outputs, `/vj/night` and `/vj/moon_phase` meanings updated.
7. Verify live: side-by-side Syphon grabs at night 0, 0.5 and 1 on CAM_0, CAM_3, CAM_6 and CAM_9; an eclipse sweep at full and new moon; drawn fps against the 60 fps target.

## Reproduce

- `verify_star_system.py` checks every formula above with numpy, with no Blender scene needed. Run it with Blender's bundled Python, which ships numpy:

```bash
/Applications/Blender.app/Contents/Resources/5.2/python/bin/python3.13 -I docs/research/synthwave-star-system/verify_star_system.py
```

- Its last line reads `all checks passed`.

## Sources

- NOAA Global Monitoring Laboratory, [General Solar Position Calculations](https://gml.noaa.gov/grad/solcalc/solareqns.PDF): solar zenith, azimuth, hour angle and declination series.
- NASA NSSDC, [Earth Fact Sheet](https://nssdc.gsfc.nasa.gov/planetary/factsheet/earthfact.html): obliquity 23.44°, sidereal rotation 23.9345 h.
- NASA NSSDC, [Moon Fact Sheet](https://nssdc.gsfc.nasa.gov/planetary/factsheet/moonfact.html): inclination 5.145°, revolution period 27.3217 d, synodic period 29.53 d.
- Meeus, *Astronomical Algorithms*, 2nd ed., ch. 48 (illuminated fraction `k = (1 + cos i)/2`), as cited by [siderust](https://docs.rs/crate/siderust/0.9.1/source/src/event/lunar/phase.rs).
- Wikipedia, [Twilight](https://en.wikipedia.org/wiki/Twilight): civil, nautical and astronomical bands.
