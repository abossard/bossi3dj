"""Flicker numbers of the live planet output: how much consecutive Syphon frames change, and how many pixels strobe.
In the live planet Blender:
    DN["fl_job"] = {"out": "/abs/flicker.json", "cases": [...], "frames": 90, "settle": 4.0}; exec this file;
    wait for DN["fl_done"].
A case: {"name": str, "set": {vj_key: value}, "pulse": bool, "hold": bool}. Every case starts from the show defaults
(the runtime's DEFAULTS) with the clocks running; "set" overrides them. "hold" (default true) holds every vj_ control
against OSC and Art-Net (Magic, QLC+), false leaves them to Magic. "pulse" false keeps the runtime's idle pulse at 0
(rt_beat from vj_beat only) by resetting its idle timer before each frame. After "settle" s, "frames" consecutive new
Syphon frames are read (luminance, 1920x1080).
Per case: per pair of frames the mean absolute luminance difference (0..255), its mean and 95th percentile over the
case; the toggle share: pixels that move by more than TOGGLE one way and then back the other way over three frames
(a strobe, not a motion), mean over the case; the draw interval. Load and fps_trustworthy are the
caller's (make status).
"""
import json
import os
import time

import bpy
import numpy as np

DN = bpy.app.driver_namespace
S = bpy.context.scene
JOB = DN["fl_job"]
BR = DN["vj_osc_bridge"]
TOGGLE = 16                 # of 255: a pixel's step up or down that counts toward a toggle
TICK = next(h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "synthwave_tick")
RT_G = TICK.__globals__
DN["fl_done"] = False
st = {"want": False, "got": [], "n": 0, "last": -1, "pulse": True, "t": []}


def no_pulse(scene, depsgraph=None):
    if not st["pulse"]:
        RT_G["_state"]["changed"] = time.perf_counter()
        RT_G["_state"]["idle"] = 0.0


def draw():
    s = DN.get("syphon_out")
    if not st["want"] or s is None or s.offscreen is None or s.frames == st["last"]:
        return
    st["last"] = s.frames
    a = np.asarray(s.offscreen.texture_color.read())
    if a.dtype != np.uint8:
        a = np.clip(a * 255.0, 0, 255).astype(np.uint8)
    lum = (a[..., 0].astype(np.uint16) * 54 + a[..., 1].astype(np.uint16) * 183 + a[..., 2].astype(np.uint16) * 19) >> 8
    st["got"].append(lum.astype(np.uint8))
    st["t"].append(time.perf_counter())


def numbers(frames, ts):
    f = [x.astype(np.int16) for x in frames]
    d = [f[i + 1] - f[i] for i in range(len(f) - 1)]
    mad = [float(np.abs(x).mean()) for x in d]
    tog = [float(((d[i] > TOGGLE) & (d[i + 1] < -TOGGLE) | (d[i] < -TOGGLE) & (d[i + 1] > TOGGLE)).mean())
           for i in range(len(d) - 1)]
    iv = [(ts[i + 1] - ts[i]) * 1000.0 for i in range(len(ts) - 1)]
    return {"pairs": len(d), "mad_mean": round(float(np.mean(mad)), 3), "mad_p95": round(float(np.percentile(mad, 95)), 3),
            "toggle_share": round(float(np.mean(tog)), 5), "toggle_p95": round(float(np.percentile(tog, 95)), 5),
            "draw_ms_median": round(float(np.median(iv)), 1)}


def apply(values):
    BR.apply({"/" + k.replace("_", "/", 1): [float(v)] for k, v in values.items()}, "flicker")


def run():
    hold0 = set(BR.hold)
    defaults = {k: v for k, v in RT_G["DEFAULTS"].items() if k in S}
    rows = []
    try:
        for case in JOB["cases"]:
            BR.hold = {k for k in S.keys() if k.startswith("vj_")} if case.get("hold", True) else set()
            st["pulse"] = case.get("pulse", True)
            if case.get("hold", True):
                vals = dict(defaults)
                vals.update(case.get("set", {}))
                apply(vals)
            t = time.perf_counter()
            while time.perf_counter() - t < JOB.get("settle", 4.0):
                yield 0.1
            st["got"], st["t"], st["want"] = [], [], True
            while len(st["got"]) < JOB.get("frames", 90):
                yield 0.005
            st["want"] = False
            row = {"case": case, "load": round(os.getloadavg()[0], 1)}
            row.update(numbers(st["got"], st["t"]))
            rows.append(row)
            st["got"] = []
    finally:
        st["want"], st["pulse"] = False, True
        BR.hold = set()
        apply(defaults)
        BR.hold = hold0
        bpy.types.SpaceView3D.draw_handler_remove(st["handle"], "WINDOW")
        if no_pulse in bpy.app.handlers.frame_change_pre:
            bpy.app.handlers.frame_change_pre.remove(no_pulse)
        json.dump(rows, open(JOB["out"], "w"), indent=1)
        DN["fl_done"] = True


gen = run()


def tick():
    try:
        return next(gen)
    except StopIteration:
        return None
    except Exception:
        import traceback
        DN["fl_err"] = traceback.format_exc()
        DN["fl_done"] = True
        return None


bpy.app.handlers.frame_change_pre.insert(0, no_pulse)
st["handle"] = bpy.types.SpaceView3D.draw_handler_add(draw, (), "WINDOW", "POST_PIXEL")
bpy.app.timers.register(tick, first_interval=0.1)
