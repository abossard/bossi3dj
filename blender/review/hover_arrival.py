"""Hover arrival live, with the frame times per stage. In the live planet Blender with flight_rt started:
    DN["hover_job"] = {"out": "/abs/result.json"}; exec this file.
Through the bridge: the Flight shot at /vj/flight 0 for 5 s, then 0.66 until the camera flies on the Skim track
(f settled, within SKIM_GAP of the Skim loop for SKIM_HOLD s), then 1. Times as verify_flight 3h: from f at 1 with
the camera at the region to the Hover in effect (fe 1). Every drawn frame logs its interval and the Flight's stage.
Ends with /vj/flight 0 and /vj/cam 0; DN["hover_done"] turns True."""
import json
import time

import bpy

DN = bpy.app.driver_namespace
S = bpy.context.scene
JOB = DN["hover_job"]
BRIDGE = DN["vj_osc_bridge"]
FRAME = next(h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "frame" and h.__module__ == "flight_rt")
FS = FRAME.__globals__["_state"]
fl = FRAME.__globals__["fl"]
FC = next(o for o in S.objects if o.type == "CAMERA" and o.get("vj_flight_cam"))
SKIM_GAP, SKIM_HOLD, TIMEOUT = 100.0, 3.0, JOB.get("timeout", 300.0)

old = DN.get("hover_state")
if old and old.get("handle"):
    try:
        bpy.types.SpaceView3D.draw_handler_remove(old["handle"], "WINDOW")
    except Exception:
        pass
st = {"draws": [], "events": {}, "last": None, "phase": "orbit", "handle": None}
DN["hover_state"] = st
DN["hover_done"] = False


def send(**values):
    BRIDGE.apply({"/" + k.replace("_", "/", 1): [float(v)] for k, v in values.items()}, "hover_arrival")


def on_draw():
    rd = bpy.context.region_data
    if rd is None or rd.view_perspective != "CAMERA":
        return
    now = time.perf_counter()
    F = FS.get("flight")
    if st["last"] is not None and F is not None and FS.get("on_air") == FC:
        st["draws"].append((round(now - st["t0"], 3), round((now - st["last"]) * 1000.0, 2), int(S.get("rt_flight_stage", -1)),
                            round(F.f, 4), round(F.fe, 4), round(F.v, 1), st["phase"]))
    st["last"] = now


def skim_gap(F):
    if F.region is None:
        return float("inf")
    tr = F.region[2][fl.SKIM]
    return tr.gap(F.u, tr.nearest(F.u))


def run():
    st["t0"] = t0 = time.perf_counter()
    now = lambda: time.perf_counter() - t0
    send(vj_cam=float(FC.name[4:]), vj_flight=0.0)
    while now() < 5.0:
        yield 0.1
    send(vj_flight=0.66)
    st["phase"], st["events"]["approach"], on_skim = "approach", round(now(), 2), None
    while now() < TIMEOUT:
        F = FS.get("flight")
        ok = F is not None and abs(F.f - 0.66) < 2e-3 and skim_gap(F) < SKIM_GAP
        on_skim = (on_skim or now()) if ok else None
        if on_skim is not None and now() - on_skim >= SKIM_HOLD:
            break
        yield 0.1
    st["events"]["on_skim"] = round(now(), 2)
    send(vj_flight=1.0)
    st["phase"] = "hover"
    at_one = arrived = None
    while now() < 2.0 * TIMEOUT and (arrived is None or now() - arrived < 5.0):
        F = FS["flight"]
        near = F.region is not None and fl.R * fl.angle(F.u, F.region[1]) < 1.15 * fl.SKIM_RING + 500.0
        if at_one is None and F.f >= 0.999 and near:
            at_one = now()
        if at_one is not None and arrived is None and F.fe >= 0.999:
            arrived = now()
        yield 0.1
    st["events"].update(f_one=at_one and round(at_one, 2), hover=arrived and round(arrived, 2),
                        arrive_s=round(arrived - at_one, 2) if at_one and arrived else None,
                        hover_gap=round(FS["flight"].gap, 1), seed=FS["flight"].seed)
    send(vj_flight=0.0, vj_cam=0.0)
    bpy.types.SpaceView3D.draw_handler_remove(st["handle"], "WINDOW")
    st["handle"] = None
    json.dump({"events": st["events"], "draws": st["draws"]}, open(JOB["out"], "w"))
    DN["hover_done"] = True


gen = run()


def tick():
    try:
        return next(gen)
    except StopIteration:
        return None


st["handle"] = bpy.types.SpaceView3D.draw_handler_add(on_draw, (), "WINDOW", "POST_PIXEL")
bpy.app.timers.register(tick, first_interval=0.1)
