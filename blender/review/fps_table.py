"""The planet's frame-time table, in the live planet Blender (clocks running, as in the show):
    DN["fps_job"] = {"out": "/abs/fps.json", "measure": 10.0, "settle": 3.0}; exec this file; wait for DN["fps_done"].
From the wire defaults, per fixed camera (CAM_0 to the last fixed one) by day (/vj/night 0) and at night (1): a hard cut
(/vj/blend 0), `settle` s, then every drawn frame of the camera view for `measure` s. Writes per cell: frames, median,
95th percentile and worst draw interval in ms, fps from the median, and the load average at the start and the end.
The Flight per stage comes from flight_numbers.py (same draw intervals)."""
import json
import os
import statistics
import time

import bpy

DN = bpy.app.driver_namespace
S = bpy.context.scene
JOB = DN["fps_job"]
BR = DN["vj_osc_bridge"]
MEASURE, SETTLE = JOB.get("measure", 10.0), JOB.get("settle", 3.0)
CAMS = [int(o.name[4:]) for o in S.objects if o.type == "CAMERA" and o.name[4:].isdigit() and not o.get("vj_flight_cam")]
DN["fps_done"] = False

old = DN.get("fps_state")
if old and old.get("handle"):
    try:
        bpy.types.SpaceView3D.draw_handler_remove(old["handle"], "WINDOW")
    except Exception:
        pass
st = {"draws": [], "rows": [], "handle": None}
DN["fps_state"] = st


def on_draw():
    rd = bpy.context.region_data
    if rd is not None and rd.view_perspective == "CAMERA":
        st["draws"].append(time.perf_counter())


def defaults():
    for k in list(S.keys()):
        if k.startswith("vj_") and k != "vj_cam" and isinstance(S[k], (int, float)):
            d = S.id_properties_ui(k).as_dict().get("default")
            if d is not None:
                S[k] = d


def run():
    load0 = os.getloadavg()[0]
    defaults()
    for night in (0.0, 1.0):
        for c in sorted(CAMS):
            BR.apply({"/vj/blend": [0.0], "/vj/night": [night], "/vj/cam": [float(c)]}, "fps_table")
            yield SETTLE
            t0 = time.perf_counter()
            yield MEASURE
            ds = [t for t in st["draws"] if t >= t0]
            iv = sorted(1000.0 * (b - a) for a, b in zip(ds, ds[1:]))
            med = statistics.median(iv) if iv else None
            st["rows"].append({"cam": c, "night": night, "frames": len(iv), "median_ms": round(med, 1) if med else None,
                               "p95_ms": round(iv[min(len(iv) - 1, int(0.95 * len(iv)))], 1) if iv else None,
                               "worst_ms": round(iv[-1], 1) if iv else None, "fps": round(1000.0 / med, 1) if med else None})
            st["draws"] = []
    defaults()
    BR.apply({"/vj/blend": [S["vj_blend"]], "/vj/night": [0.0], "/vj/cam": [0.0]}, "fps_table")
    bpy.types.SpaceView3D.draw_handler_remove(st["handle"], "WINDOW")
    st["handle"] = None
    json.dump({"load_start": round(load0, 1), "load_end": round(os.getloadavg()[0], 1), "measure_s": MEASURE, "rows": st["rows"]},
              open(JOB["out"], "w"), indent=1)
    DN["fps_done"] = True


gen = run()


def tick():
    try:
        return next(gen)
    except StopIteration:
        return None


st["handle"] = bpy.types.SpaceView3D.draw_handler_add(on_draw, (), "WINDOW", "POST_PIXEL")
bpy.app.timers.register(tick, first_interval=0.1)
