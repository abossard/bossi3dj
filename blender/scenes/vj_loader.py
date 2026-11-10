"""Starts the VJ runtime from the file on disk, so an embedded copy that went stale can never run.

Embedded in every scene as the registered text block `vj_loader.py` (blender/review/prepare_scene.py puts it
there). Blender runs a registered text block from its stored copy, never from the file it points to; this copy
is the only one, and it only opens synthwave_runtime.py next to the .blend and runs it. The runtime then loads
the bridge, the Syphon sender and the page from their files the same way.
"""
import os

import bpy

path = os.path.join(bpy.path.abspath("//"), "synthwave_runtime.py")
with open(path) as f:
    source = f.read()
exec(compile(source, path, "exec"), {"__name__": "synthwave_runtime", "__file__": path})
