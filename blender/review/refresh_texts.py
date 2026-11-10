"""Re-embeds the external text blocks of a .blend from their files and saves it (headless, nothing runs).

    blender -b --disable-autoexec FILE.blend --python blender/review/refresh_texts.py

Blender runs the text block's stored copy on load, not the file it points to, so a .blend whose runtime was
edited elsewhere runs the old one. The planet file gets this from `make blender-rebuild`; the island file
has no builder.
"""
import os

import bpy

for tx in bpy.data.texts:
    path = bpy.path.abspath(tx.filepath) if tx.filepath else ""
    if os.path.exists(path):
        with open(path) as f:
            tx.from_string(f.read())
        print("REFRESHED", tx.name, path)
bpy.ops.wm.save_mainfile()
