# bossi3dj

Live visuals for music. A 3D scene reacts to the sound, and you mix its picture on a projector or screen.

How it works, in four steps:

1. Music goes into **Magic Music Visuals** (Magic), a VJ program.
2. Magic turns it into about 38 simple numbers, for example *louder*, *bass*, *beat*, *night*, *fog*, *which camera*. Every number is a row in [osc/contract.json](osc/contract.json) and goes out as an OSC message named `/vj/<name>` (OSC is a small network message format).
3. One 3D scene reads the numbers and moves, glows and changes. Two scenes exist: a **Blender** scene and a **Godot** scene. Only one runs at a time, so both listen on the same port, udp 9201.
4. The scene publishes its picture as a **Syphon** video stream (a way for Mac apps to share frames). Magic picks it up, adds effects and mixes the two scenes.

The scenes hold no music logic. Magic decides what the music means, the scenes only take the numbers.

```mermaid
flowchart LR
    A["Music<br/>(audio in)"] --> B["Magic Music Visuals<br/>analyses the music,<br/>makes 38 numbers"]
    B -->|"OSC /vj/*<br/>udp 9201"| C["The running scene"]
    C --- D["Blender<br/>Synthwave Planet"]
    C --- E["Godot<br/>Colossus"]
    D -->|"Syphon<br/>CAM_OUT - Blender"| B
    E -->|"Syphon<br/>COLOSSUS_OUT"| B
    B --> F["Projector or screen"]
```

| Scene | Engine | Folder | What you see |
|---|---|---|---|
| Synthwave Planet | Blender 5.3 (EEVEE), built by script | [blender/](blender/) | a retro planet with pink and lilac hills, pyramids, water, flamingos, stars and a moon |
| Colossus | Godot 4.7 (Forward+, Metal) | [godot/colossus/](godot/colossus/) | an overcast dusk plain, a giant, and a small figure that climbs it |

## The Blender scene: Synthwave Planet

A whole small planet with a sun, a moon and a star sky. Fixed cameras (`CAM_0` to `CAM_10`) show it from the ground, from a river, from a coast and from orbit. `CAM_11` is the Flight shot, a camera that flies over the planet. The music changes the light and the weather:

- `/vj/night` moves the time of day: 0 is day, 0.25 sunset, 0.5 twilight, 1 night.
- `/vj/fog` sets how dense the fog bank is. Fog has its own colour, glow, size and wind (`/vj/fog_*`).
- `/vj/cam` cuts to a camera, `/vj/blend` sets how smoothly the cut flies over, `/vj/energy` how hard the camera moves.
- `/vj/flight` runs the Flight shot from orbit down to a skim over the mountains and a hover over the water.
- `/vj/grid` shows the real triangle edges of the ground at night as a glowing cyan net. By day there are none.
- `/vj/level`, `/vj/bass` and `/vj/beat` pulse the sun, the net, the pyramid edges and the water glints with the music. `/vj/hue` turns the whole palette.

The full list with ranges is in [osc/CONTROLS.md](osc/CONTROLS.md).

<table>
<tr>
<td width="50%"><img src="docs/images/readme/planet-valley-palms-day.jpg" alt="A valley of purple hills with a large pink sun, palms and small pyramids on a magenta plain"><br><sub><b>Day, <code>CAM_0</code></b>: wide, up the plaza toward the pyramids and the sun (<code>/vj/night</code> 0).</sub></td>
<td width="50%"><img src="docs/images/readme/planet-night-mesh-edges.jpg" alt="Night valley with a glowing cyan triangle net on the hills and ground under a starry sky"><br><sub><b>Night with mesh edges, <code>CAM_0</code></b>: <code>/vj/night</code> 1 and <code>/vj/grid</code> 1 draw the ground's real triangles.</sub></td>
</tr>
<tr>
<td><img src="docs/images/readme/planet-valley-pyramids-day.jpg" alt="Day valley of lilac and pink hills with haze, small pyramids on the valley floor and a large pink sun"><br><sub><b>Pyramids, <code>CAM_2</code></b>: the pyramid hero shot by day, with haze between the hills.</sub></td>
<td><img src="docs/images/readme/planet-pyramids-day.jpg" alt="Five dark pyramids on a magenta ground with a water strip at the left and a pink sun in a pale blue sky"><br><sub><b>Far pyramids, <code>CAM_9</code></b>: a pyramid group far from the valley, the sun behind it.</sub></td>
</tr>
<tr>
<td><img src="docs/images/readme/planet-flamingos-day.jpg" alt="A large pink sun over a flat lake with many pink flamingos and their reflections, dark hills and palms on the horizon"><br><sub><b>Flamingos, <code>CAM_7</code></b>: a flock on the water next to the pyramids, low, looking toward the sun (<code>/vj/flamingos</code> sets the flock size).</sub></td>
<td><img src="docs/images/readme/planet-river-day.jpg" alt="A water channel between two magenta hills with small palms on the left bank under a pale blue sky"><br><sub><b>River, <code>CAM_8</code></b>: a river running into the sea, looking downstream.</sub></td>
</tr>
<tr>
<td><img src="docs/images/readme/planet-coast-day.jpg" alt="Calm blue water filling the lower right with a mirrored pink hill at the left under a pale sky"><br><sub><b>Coast, <code>CAM_10</code></b>: a low pass along a coast with the sea on one side.</sub></td>
<td><img src="docs/images/readme/planet-sun-hills-day.jpg" alt="A large orange-pink sun with a glow over low lilac hills at the bottom of a light blue sky"><br><sub><b>Sun over the hills, <code>CAM_3</code></b>: tilted up over the pyramids (at night this camera looks at the moon).</sub></td>
</tr>
<tr>
<td><img src="docs/images/readme/planet-orbit-moon.jpg" alt="Space with a starfield, a large grey cratered moon at the left and the planet as a dark globe with pink land and blue water"><br><sub><b>Orbit, <code>CAM_6</code></b>: the whole planet in frame, with the moon. Space is dark even when the planet's ground is in daylight.</sub></td>
<td><img src="docs/images/readme/planet-flight-night.jpg" alt="The planet as a globe with pink land, blue water and a lit horizon band, a half-lit moon above and stars"><br><sub><b>Flight shot, <code>CAM_11</code></b>: the camera flying over the planet, at night with <code>/vj/grid</code> 0.</sub></td>
</tr>
</table>

These are 960x540 review grabs from the planet's look rounds 11 and 12, not all from the same build, and they are not a promise of how every frame looks. The night shot has no matching frame with `/vj/grid` 0 of the same framing, and there is no sunset or fog frame yet.

## The Godot scene: Colossus

A giant (the Colossus) walks across an overcast plain at dusk. A small figure, the Wanderer, walks up to it and climbs it. The Colossus tries to shake it off, then falls, and a new Colossus appears. One round of this is called an Arc: Approach, Climb, Fall, Reset. The terms are in [GLOSSARY.md](GLOSSARY.md).

The music drives the weight of the scene: `/vj/bass` sets how heavy each footfall is (camera shake, size of the dust), `/vj/beat` times the footfalls, dust puffs and cut points, `/vj/level` is the sun glow through the clouds, `/vj/intensity` the exposure. `/vj/shock` makes the Colossus shake while the Wanderer is on it. Without any OSC the scene runs on its own 90 BPM beat.

<table>
<tr>
<td width="50%"><img src="docs/images/2026-11-11/godot-models-wanderer.jpg" alt="Sheet of the Wanderer model"></td>
<td width="50%"><img src="docs/images/2026-11-11/godot-models-colossus.jpg" alt="Sheet of the Colossus models"></td>
</tr>
<tr>
<td align="center"><sub>The Wanderer, the figure that climbs.</sub></td>
<td align="center"><sub>The Colossi, one appears at a time.</sub></td>
</tr>
</table>

Screenshots of the running scene will follow. The character models are not in the repository (they come from downloads with their own licences); without them the scene runs with stand-ins. See [godot/colossus/assets/MODELS.md](godot/colossus/assets/MODELS.md) for what is needed and how to rebuild them.

## Try it

```bash
make help
```

Lists every command.

```bash
make blender-open
```

Opens the planet in Blender and waits until the start state is ready (runtime, bridge, Syphon, picture, night edges). Then open http://127.0.0.1:9210 to drive it by hand without Magic. Use `SCENE=island` for the older island scene.

```bash
make godot-open
```

Runs the Colossus scene in a window. Control page: http://127.0.0.1:9211. It refuses to start while Blender runs, because both use the same GPU and port.

```bash
make test
```

Runs all tests without a window or a GPU: the OSC contract, the Magic project tools, the Blender bridge and the Godot logic with a headless self-check.

For music, open [magic/projects/show.magic](magic/projects/show.magic) in Magic Performer. It sends to 127.0.0.1:9201 and shows both Syphon sources with a fader between them (`SceneMix`). `make lab` starts an optional debug relay and test page on http://127.0.0.1:8765, not needed for a show.

## Needs

- macOS on Apple Silicon, Blender 5.3 with `syphon-python` and PyObjC in `~/.local/lib/python3.13/site-packages`, Godot 4.7 (mono build at `/Applications/Godot_mono.app`), Magic Music Visuals Performer, ImageMagick for contact sheets, gdtoolkit for `make godot-lint`, `make venv` for the verify scripts (numpy and Pillow).
- Star maps for the planet sky are not in git: NASA SVS Deep Star Maps 2020 into `blender/scenes/planet_proto/starmaps/`.

## Read next

- Agents and contributors: [AGENTS.md](AGENTS.md), then [STATE.md](STATE.md).
- The addresses: [osc/CONTROLS.md](osc/CONTROLS.md).
- Terms: [GLOSSARY.md](GLOSSARY.md).
- The scenes: [blender/README.md](blender/README.md), [godot/colossus/README.md](godot/colossus/README.md).
