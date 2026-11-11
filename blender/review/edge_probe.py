"""Does the terrain draw its real triangle edges at night? One probe in the open planet scene, a second or two.

Through the Blender MCP:  exec(open(bpy.path.abspath("//../review/edge_probe.py")).read())
Optional before it: DN["edge_probe_args"] = {"repair": False, "force_blank": 1}  (default: repair on, no forced blank).
Starts blender/scenes/edge_guard.py's Guard (the same code the runtime runs once at the start) and returns at once; the
answer lands in driver_namespace["edge_guard"] when it is done: status "present", "repaired", "missing", "no_picture"
or "error", `shares` (line share of night /vj/grid 1 over 0, one per probe; present from MIN_SHARE 0.03), probe_ms.
The probe holds night 1 and grid 1/0 for about a second, freezes the clocks, then puts every control back.
Read it with:  DN.get("edge_guard")   (health.py lists status "missing" as a problem).
"""
import os
import sys

import bpy

DN = bpy.app.driver_namespace
scenes = bpy.path.abspath("//")
if scenes not in sys.path:
    sys.path.insert(0, scenes)
import importlib

import edge_guard

importlib.reload(edge_guard)
args = DN.pop("edge_probe_args", {})
DN["edge_guard_run"] = edge_guard.start(**args)
result = DN.get("edge_guard")
