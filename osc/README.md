# OSC relay and debug page

`lab.py` is an optional debug tool, not part of the show: Magic sends straight to the scene on udp 9201 (the Blender bridge and the Godot Colossus Scene both listen there, only one runs at a time). The lab listens on 9200, relays to the scene and shows every message, with wire-unit sliders, generators and the sweep. The address contract is [CONTROLS.md](CONTROLS.md), made from [contract.json](contract.json) (`python3 osc/contract.py sync`, `make osc-sync`). `osc/sweep.py` (`make osc-sweep`) walks every row through min, default and max.

```
Magic OSCSender ──udp 9201──> Blender (blender/blender_osc_bridge.py) or Godot (godot/colossus/io/vj_signals.gd)

debug only:
Magic or a slider ──udp 9200──> lab.py ──relay udp 9201──> the running scene
                                  │  http 8765                 │
                                  └── /lab/ping ──> ... <── /lab/pong ┘
```

Standard-library Python only, no install.

## Run

```bash
make lab
```

or `python3 osc/lab.py --log capture.jsonl`. Open http://127.0.0.1:8765.

Options: `--listen 9200` (port Magic sends to), `--blender-port 9201`, `--blender-host`, `--godot-port N` (second relay target, default 0 = off: both scenes share 9201), `--no-relay`, `--log FILE` (append every message as JSON lines), `--http 8765`.

## What the page gives you

- **Incoming OSC**: one row per address with type tags, last value, min/max, send rate (Hz), count, bundle flag and a trend line. This is where the Magic format and rate get read off.
- **Relay**: every packet from Magic is forwarded unchanged to the Blender target (Magic can only send to one destination per project).
- **Blender bridge**: round-trip time, Blender/Python version, scene, timer ticks per second, messages received and applied. The bridge answers `/lab/ping` once a second.
- **Send / sliders / generators**: drive Blender and Godot without Magic. The sliders are one per contract row, in wire units, starting at the wire default; a generator's range follows the row you pick. A generator sends a sine, beat pulse, square, ramp or noise at a chosen rate, so the scene side can be built before the Magic side exists.
- **Packet log**: last 1000 messages with source, size and bundle marker; downloadable as JSONL.
- **Checklist**: the manual steps for Blender, Magic and Syphon.

## Blender side

Run `blender_osc_bridge.py` in Blender's Text Editor (or `blender --python blender/blender_osc_bridge.py`).

- Listens on UDP 127.0.0.1:9201 from a `bpy.app.timers` callback; no threads.
- The first numeric argument of each address lands in a scene custom property: `/vj/level` → `scene["vj_level"]`, scaled from the wire value to the property's scene units (`SCALES`, from `contract.json`); an address that is not a row Blender uses is ignored. Drivers read it with the Simple Expression path `["vj_level"]`.
- `MAPPING` at the top of the script optionally routes an address to an object attribute, e.g. `"/vj/level": ("Cube", "scale", 2)`.
- `/vj/cam N` also makes the camera object `CAM_N` the scene camera, or the last camera below N when the scene has fewer (drivers cannot set `scene.camera`).
- After each batch it calls `scene.update_tag()` and redraws 3D views, which plain custom-property writes skip.
- Re-running the script replaces the previous instance.

Verified on Blender 5.2.3 LTS: headless (`-b`, driver follows the property) and GUI (timer at about 118 ticks/s with redraw, values applied, RTT about 2 ms on localhost).

## Magic side

Only the Performer edition has `OSCSender`. One IP and port per project. Set IP Addr `127.0.0.1`, Port `9201` (`9200` to go through the lab), Message e.g. `/vj/level`, and link Value to an audio feature.
