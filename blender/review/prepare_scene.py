"""Puts a scene file into its start state, headless. Idempotent; the same for the island and (through the builder) the planet.

    blender -b --disable-autoexec blender/scenes/synthwave_pyramids.blend --python blender/review/prepare_scene.py
    (or: make blender-prepare)

- the only registered runtime text is `vj_loader.py` (a copy of blender/scenes/vj_loader.py): it runs the
  runtime, bridge, Syphon sender and page from their files, so no embedded copy of them can go stale;
  the old embedded `synthwave_runtime.py` and `blender_osc_bridge.py` blocks are removed;
Camera view and Rendered shading are not stored here: Blender opens every 3D view in Solid shading whatever the file
says, so the runtime sets them once the window exists (`_play` in synthwave_runtime.py).
Saves the file when something changed.
"""
import os

import bpy

HERE = os.path.dirname(bpy.data.filepath)
LOADER = "vj_loader.py"
STALE = ("synthwave_runtime.py", "blender_osc_bridge.py")
changed = []

with open(os.path.join(HERE, LOADER)) as f:
    source = f.read()
loader = bpy.data.texts.get(LOADER)
if loader is None:
    loader = bpy.data.texts.new(LOADER)
if loader.as_string() != source or not loader.use_module or loader.filepath:
    loader.filepath = ""
    loader.from_string(source)
    loader.use_module = True
    changed.append("loader")
for name in STALE:
    tx = bpy.data.texts.get(name)
    if tx is not None:
        bpy.data.texts.remove(tx)
        changed.append("removed " + name)

print("PREPARE", bpy.data.filepath, changed or "nothing to do")
if changed:
    bpy.ops.wm.save_mainfile()
