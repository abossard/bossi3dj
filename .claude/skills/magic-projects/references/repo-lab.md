# This repo's Magic → Blender lab (optional)

Only for work on this repository's `magic/`, `osc/` and `blender/` folders. Nothing here applies to Magic in general.

- `magic/synthwave_magic.py` generates `magic/projects/synthwave_pyramids.magic`. Edit the generator and regenerate; a `set` on its output is lost on the next build. Its note "Order matters" about Globals is wrong: evaluation is double-buffered (format.md).
- Its OSCSenders send `/vj/*` to 127.0.0.1:9201, the Blender bridge (`blender_osc_bridge.py`). Never bind or send there; `magicproj listen` refuses 9201 by default.
- `lab.py` (`make lab`) listens on 9200 and relays to 9201. It pings its Blender port once a second even with `--no-relay`; point `--blender-port` at an unused port when observing a copy.
- To observe the project's OSC: `set --osc-target 127.0.0.1:9300 --osc-prefix /vj/` on a copy, `load` it, `listen 9300`, then load the original back (`magic/projects/synthwave_pyramids.magic`).
- Do not open or modify `.blend` files from this workflow.

- `magic/show_magic.py` generates `magic/projects/show.magic`: the same project with a second Syphon source (`COLOSSUS_OUT - Godot`), a `Mix` between the two and OSC to the relay on 9200. Every address, range and default is a row of `osc/contract.json`; Magic sends 0..1 and each scene scales.
