"""Frame-time A/B in the live scene: clocks frozen, inputs held, cells interleaved.
DN["ab"] = {"cells": [{"name": "A", "set": {vj_*: value}, "exec": "python run before the cell"}, ...],
            "rounds": 3, "settle": 3.0, "measure": 10.0, "out": "/abs/result.json"}
Runs one warm-up cell (not counted), then rounds x cells; the cell order flips every round (A B, B A, A B).
Each cell: exec, apply the controls with a hold, wait `settle` s, then record the drawn frames of the camera view for
`measure` s. Writes per cell and round: frames, mean and p95 frame ms, fps; then per cell the mean of the rounds."""
import json
import statistics
import time

import bpy

DN = bpy.app.driver_namespace
S = bpy.context.scene
CFG = DN["ab"]
RT = DN["vj_runtime"]
HOLD = {"vj_cam", "vj_night", "vj_shock", "vj_fog", "vj_eclipse", "vj_moon_phase", "vj_cam_speed", "vj_nebula"}

old = DN.get("ab_state")
if old and old.get("handle"):
    try:
        bpy.types.SpaceView3D.draw_handler_remove(old["handle"], "WINDOW")
    except Exception:
        pass
cells = CFG["cells"]
order = [cells[0]]
for r in range(CFG.get("rounds", 3)):
    order += [(r, c) for c in (cells if r % 2 == 0 else cells[::-1])]
order[0] = (-1, order[0])
st = {"order": order, "i": -1, "draws": [], "t0": None, "rows": [], "done": False, "err": None, "handle": None}
DN["ab_state"] = st


def on_draw():
    rd = bpy.context.region_data
    if rd is not None and rd.view_perspective == "CAMERA":
        st["draws"].append(time.perf_counter())


st["handle"] = bpy.types.SpaceView3D.draw_handler_add(on_draw, (), "WINDOW", "POST_PIXEL")


def apply(values):
    bridge = DN.get("vj_osc_bridge")
    bridge.hold = bridge.hold | HOLD
    bridge.apply({"/" + k.replace("_", "/", 1): [float(v)] for k, v in values.items()}, "web")


def finish():
    bpy.types.SpaceView3D.draw_handler_remove(st["handle"], "WINDOW")
    st["handle"] = None
    RT.freeze(False)
    summary = {}
    for c in cells:
        rows = [x for x in st["rows"] if x["cell"] == c["name"] and x["round"] >= 0]
        if rows:
            summary[c["name"]] = {"mean_ms": round(statistics.mean(x["mean_ms"] for x in rows), 2),
                                  "fps": round(statistics.mean(x["fps"] for x in rows), 1),
                                  "per_round_ms": [x["mean_ms"] for x in rows]}
    with open(CFG["out"], "w") as f:
        json.dump({"rows": st["rows"], "summary": summary, "err": st["err"]}, f, indent=1)
    st["done"] = True


def step():
    try:
        RT.freeze(True)
        now = time.perf_counter()
        i = st["i"]
        if i >= 0:
            if now < st["t0"] + CFG.get("settle", 3.0) + CFG.get("measure", 10.0):
                return 0.5
            r, c = st["order"][i]
            ds = [t for t in st["draws"] if t >= st["t0"] + CFG.get("settle", 3.0)]
            iv = sorted(1000.0 * (b - a) for a, b in zip(ds, ds[1:]))
            if iv:
                st["rows"].append({"cell": c["name"], "round": r, "frames": len(ds), "mean_ms": round(statistics.mean(iv), 2),
                                   "p95_ms": round(iv[int(0.95 * (len(iv) - 1))], 2),
                                   "fps": round((len(ds) - 1) / (ds[-1] - ds[0]), 1)})
        i += 1
        st["i"] = i
        if i >= len(st["order"]):
            finish()
            return None
        r, c = st["order"][i]
        RT.quiesce()
        if c.get("exec"):
            exec(c["exec"], {"bpy": bpy, "S": S, "DN": DN})
        apply(c.get("set", {}))
        st["draws"].clear()
        st["t0"] = time.perf_counter()
        return 0.5
    except Exception:
        import traceback
        st["err"] = traceback.format_exc()
        finish()
        return None


bpy.app.timers.register(step, first_interval=0.2)
