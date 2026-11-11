"""Repeats one self-check cell on the Flight shot and records the Flight's state after each, to find what differs.
DN["flight_repeat"] = {"set": {"vj_flight": 0.66}, "advance": 2.0, "n": 3, "out": "/abs/result.json"}; exec this file.
Each cell, as synthwave_check.cell: quiesce, clocks back, set the state through the bridge, one frame, advance the frozen clocks, wait 3 s."""
import json
import time

import bpy

DN = bpy.app.driver_namespace
S = bpy.context.scene
CFG = DN["flight_repeat"]
RT = DN["vj_runtime"]
BRIDGE = DN["vj_osc_bridge"]
CLOCK0 = {k: S[k] for k in RT.CLOCKS if k in S}
FRAME = next(h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "frame" and h.__module__ == "flight_rt")
FS = FRAME.__globals__["_state"]
FC = next(o for o in S.objects if o.type == "CAMERA" and o.get("vj_flight_cam"))


def snap(i, t0):
    F = FS.get("flight")
    rig = S.objects["CAM_RIG"]
    lod = FRAME.__globals__["lod_scene"]
    return {"cell": i, "wall": round(time.time() - t0, 2), "camera": S.camera.name, "shot": FS["shot"].name,
            "on_air": FS["on_air"].name if FS.get("on_air") else None, "holding": bool(lod.holding()),
            "rig": [round(x, 2) for x in rig.matrix_world.translation], "fc": [round(x, 2) for x in FC.matrix_world.translation],
            "vj_cam": S.get("vj_cam"), "vj_flight": S.get("vj_flight"), "sun": [round(S.get(k, 0.0), 5) for k in ("rt_sun_x", "rt_sun_y", "rt_sun_z")],
            "flight": None if F is None else {"seed": F.seed, "f": round(F.f, 4), "fe": round(F.fe, 4), "t": round(F.t, 3),
                                              "steps": F.steps, "u": [round(x, 6) for x in F.u],
                                              "region": F.region[0] if F.region else None},
            "director_tr": FS["director"].tr is not None if FS.get("director") else None}


def run():
    t0, rows = time.time(), []
    RT.freeze(True)
    for i in range(CFG.get("n", 3)):
        RT.quiesce()
        for k, v in CLOCK0.items():
            S[k] = v
        state = dict(CFG["set"])
        state["vj_cam"] = float(FC.name[4:])
        BRIDGE.apply({"/" + k.replace("_", "/", 1): [float(v)] for k, v in state.items()}, "flight_repeat")
        n0 = S.frame_current
        while S.frame_current == n0:
            RT.freeze(True)
            yield 0.05
        rows.append(dict(snap(i, t0), phase="after one frame"))
        RT.advance(CFG.get("advance", 2.0))
        while RT.steps_left() > 0:
            RT.freeze(True)
            yield 0.05
        rows.append(dict(snap(i, t0), phase="clocks stepped"))
        for _ in range(30):
            RT.freeze(True)
            yield 0.1
        rows.append(dict(snap(i, t0), phase="3 s later"))
    RT.freeze(False)
    json.dump(rows, open(CFG["out"], "w"), indent=1)
    DN["flight_repeat_done"] = True


gen = run()
DN["flight_repeat_done"] = False


def tick():
    try:
        return next(gen)
    except StopIteration:
        return None


bpy.app.timers.register(tick, first_interval=0.1)
