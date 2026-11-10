# OSC relay and debug page

`lab.py` sits between Magic Music Visuals and the scenes: it relays Magic's OSC to Blender and Godot and shows every message. The address contract is [CONTROLS.md](CONTROLS.md).

```
Magic OSCSender ──udp 9200──> lab.py ──relay udp 9201──> Blender (blender/blender_osc_bridge.py)
                                 ├──────relay udp 9202──> Godot (godot/colossus/io/vj_signals.gd)
                                 │  http 8765                       │
                                 └── /lab/ping ──> ... <── /lab/pong ┘
```

Standard-library Python only, no install.

## Run

```bash
make lab
```

or `python3 osc/lab.py --log capture.jsonl`. Open http://127.0.0.1:8765.

Options: `--listen 9200` (port Magic sends to), `--blender-port 9201`, `--blender-host`, `--godot-port 9202` (second relay target for the Godot Colossus Scene, 0 = off), `--no-relay`, `--log FILE` (append every message as JSON lines), `--http 8765`.

## What the page gives you

- **Incoming OSC**: one row per address with type tags, last value, min/max, send rate (Hz), count, bundle flag and a trend line. This is where the Magic format and rate get read off.
- **Relay**: every packet from Magic is forwarded unchanged to the Blender target (Magic can only send to one destination per project).
- **Blender bridge**: round-trip time, Blender/Python version, scene, timer ticks per second, messages received and applied. The bridge answers `/lab/ping` once a second.
- **Send / sliders / generators**: drive Blender without Magic. A generator sends a sine, beat pulse, square, ramp or noise at a chosen rate, so the scene side can be built before the Magic side exists.
- **Packet log**: last 1000 messages with source, size and bundle marker; downloadable as JSONL.
- **Checklist**: the manual steps for Blender, Magic and Syphon.

## Blender side

Run `blender_osc_bridge.py` in Blender's Text Editor (or `blender --python blender/blender_osc_bridge.py`).

- Listens on UDP 127.0.0.1:9201 from a `bpy.app.timers` callback; no threads.
- The first numeric argument of each address lands in a scene custom property: `/vj/level` → `scene["vj_level"]`. Drivers read it with the Simple Expression path `["vj_level"]`.
- `MAPPING` at the top of the script optionally routes an address to an object attribute, e.g. `"/vj/level": ("Cube", "scale", 2)`.
- `/vj/cam N` also makes the camera object `CAM_N` the scene camera (drivers cannot set `scene.camera`).
- After each batch it calls `scene.update_tag()` and redraws 3D views, which plain custom-property writes skip.
- Re-running the script replaces the previous instance.

Verified on Blender 5.2.3 LTS: headless (`-b`, driver follows the property) and GUI (timer at about 118 ticks/s with redraw, values applied, RTT about 2 ms on localhost).

## Magic side

Only the Performer edition has `OSCSender`. One IP and port per project. Set IP Addr `127.0.0.1`, Port `9200`, Message e.g. `/vj/level`, and link Value to an audio feature.
