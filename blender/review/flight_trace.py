"""The Flight's state over time, in the live planet Blender with flight_rt started (clocks running):
    DN["ftrace_job"] = {"out": "/abs/trace.json", "seed": 1, "flight": [(0.0, 1.0)], "seconds": 150}; exec this file;
    wait for DN["ftrace_done"].
Resets the Flight on `seed`, cuts to the Flight shot (/vj/blend 0), then sets /vj/flight to each (time s, value) of
`flight` and logs every 0.5 s: t, f, fe, stage, gap to the water loop (m), speed (m/s), the pursuit's bearing alpha
(deg), cap, go, turn rate (deg/s), height over the clearance map, the region and how many water loops it has."""
import json
import math
import time

import bpy

DN = bpy.app.driver_namespace
S = bpy.context.scene
JOB = DN["ftrace_job"]
BRIDGE = DN["vj_osc_bridge"]
FRAME = next(h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "frame" and h.__module__ == "flight_rt")
G = FRAME.__globals__
FS = G["_state"]
FC = next(o for o in S.objects if o.type == "CAMERA" and o.get("vj_flight_cam"))
DN["ftrace_done"] = False


def send(**values):
    BRIDGE.apply({"/" + k.replace("_", "/", 1): [float(v)] for k, v in values.items()}, "flight_trace")


def r(x, n=1):
    return None if x is None or (isinstance(x, float) and math.isinf(x)) else round(x, n)


def defaults():
    """Every /vj/* control back to its wire default (a grab run leaves its last state, /vj/boost 1 after the boost pair)."""
    for k in list(S.keys()):
        if k.startswith("vj_") and k != "vj_cam" and isinstance(S[k], (int, float)):
            d = S.id_properties_ui(k).as_dict().get("default")
            if d is not None:
                S[k] = d


def run():
    t0 = time.perf_counter()
    now = lambda: time.perf_counter() - t0
    defaults()
    send(vj_blend=0.0, vj_flight=0.0)
    G["quiesce"](JOB.get("seed", 1))
    send(vj_cam=float(FC.name[4:]))
    plan, rows = sorted(JOB.get("flight", [(0.0, 1.0)])), []
    while now() < JOB.get("seconds", 150.0):
        while plan and now() >= plan[0][0]:
            send(vj_flight=plan.pop(0)[1])
        F = FS.get("flight")
        if F is not None:
            u, h = G["dr"].spherical(FS["flight_pose"][0]) if FS.get("flight_pose") else (None, None)
            rows.append((r(now()), r(F.f, 4), r(F.fe, 4), int(S.get("rt_flight_stage", -1)), r(F.gap), r(F.v), r(math.degrees(F.alpha)),
                         r(F.cap), r(F.go), r(math.degrees(F.rate), 2), r(h - FS["map"].surface(u)) if u else None,
                         F.region[0] if F.region else None, len(F.hovers)))
        yield 0.5
    send(vj_flight=0.0, vj_blend=1.0, vj_cam=0.0)
    json.dump({"seed": JOB.get("seed", 1), "load": __import__("os").getloadavg()[0],
               "columns": ["t", "f", "fe", "stage", "gap", "v", "alpha", "cap", "go", "rate", "agl", "region", "loops"], "rows": rows},
              open(JOB["out"], "w"))
    DN["ftrace_done"] = True


gen = run()


def tick():
    try:
        return next(gen)
    except StopIteration:
        return None
    except Exception:
        import traceback
        DN["ftrace_err"] = traceback.format_exc()
        DN["ftrace_done"] = True
        return None


bpy.app.timers.register(tick, first_interval=0.1)
