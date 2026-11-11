"""Traces one cut as a self-check cell makes it: clocks frozen, quiesce, /vj/cam through the bridge, no advance.
DN["cut_trace"] = {"from": 0, "to": 1, "seconds": 12, "out": "/abs/result.json"}; exec this file.
Logs every 0.2 s: the shot asked for, the shot on air, the LOD hold, the Director's blend, the rig's distance to the
shot's own pose. A cell's frame shows the shot only once on_air is it and dist is 0."""
import json
import time

import bpy

DN = bpy.app.driver_namespace
S = bpy.context.scene
CFG = DN["cut_trace"]
RT = DN["vj_runtime"]
BRIDGE = DN["vj_osc_bridge"]
FRAME = next(h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "frame" and h.__module__ == "flight_rt")
FS = FRAME.__globals__["_state"]
LOD = FRAME.__globals__["lod_scene"]


def run():
    rows = []
    RT.freeze(True)
    BRIDGE.apply({"/vj/cam": [float(CFG["from"])]}, "cut_trace")
    for _ in range(30):
        RT.freeze(True)
        yield 0.1
    RT.quiesce()
    BRIDGE.apply({"/vj/cam": [float(CFG["to"])]}, "cut_trace")
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < CFG.get("seconds", 12.0):
        RT.freeze(True)
        dg = bpy.context.evaluated_depsgraph_get()
        cam = S.objects["CAM_%d" % CFG["to"]].evaluated_get(dg).matrix_world.translation
        D = FS.get("director")
        rows.append({"t": round(time.perf_counter() - t0, 2), "frame": S.frame_current, "shot": FS["shot"].name,
                     "on_air": FS["on_air"].name if FS.get("on_air") else None, "holding": bool(LOD.holding()),
                     "blend": D is not None and D.tr is not None,
                     "dist": round((S.objects["CAM_RIG"].matrix_world.translation - cam).length, 1)})
        yield 0.2
    RT.freeze(False)
    json.dump(rows, open(CFG["out"], "w"))


gen = run()


def tick():
    try:
        return next(gen)
    except StopIteration:
        return None


bpy.app.timers.register(tick, first_interval=0.1)
