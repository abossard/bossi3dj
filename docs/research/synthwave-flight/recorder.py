"""In-Blender recorder for the Flight proofs (docs/research/synthwave-flight.md, "Test plan").

Run inside the live planet Blender (with flight_rt started):
    DN["flight_rec_job"] = {"out": "/abs/dir", "program": [(t, {"vj_flight": 1.0, ...}), ...], "seconds": 120}
    exec(open(".../recorder.py").read())
It plays the program through the OSC bridge (as the web page does), logs every drawn frame's interval, grabs the
Syphon frame (halved to 960x540) at GRAB_HZ as PPM, and logs the frame difference between grabs and the rig's
state. Each drawn frame also logs how far the On-Air Camera moved and turned since the last one, its lens, and
whether its matrix and lens are exactly the last frame's (the motion trace, EN1). trace.json in the out dir holds it all; DN["flight_rec"]["done"] turns True at the end.
"""
import json
import math
import os
import time

import bpy
import numpy as np

DN = bpy.app.driver_namespace
S = bpy.context.scene
GRAB_HZ = 15.0
job = DN["flight_rec_job"]          # {"out", "program", "seconds", optional "grab_hz"}
os.makedirs(job["out"], exist_ok=True)

old = DN.get("flight_rec")
if old and old.get("handle"):
    try:
        bpy.types.SpaceView3D.draw_handler_remove(old["handle"], "WINDOW")
    except Exception:
        pass
st = {"t0": time.perf_counter(), "last": None, "draws": [], "grabs": [], "prev": None, "next_grab": 0.0, "pi": 0,
      "done": False, "handle": None, "n": 0, "cam": None}
DN["flight_rec"] = st


def apply(values):
    bridge = DN.get("vj_osc_bridge")
    if bridge is None:
        for k, v in values.items():
            S[k] = float(v)
        return
    bridge.hold = bridge.hold | set(values)
    bridge.apply({"/" + k.replace("_", "/", 1): [float(v)] for k, v in values.items()}, "web")


def rig_state():
    import flight_rt as frt
    c = S.camera.matrix_world.translation
    alt = math.sqrt(c.x ** 2 + c.y ** 2 + (c.z + 16000.0) ** 2) - 16000.0
    F = frt._state.get("flight")
    return {"alt": round(alt, 2), "lens": round(S.camera.data.lens, 2), "blend": S.get("rt_blending", 0.0),
            "stage": S.get("rt_flight_stage", -1.0), "f": round(F.f, 4) if F else None, "boost": round(F.b, 3) if F else None,
            "fe": round(F.fe, 4) if F else None, "v": round(F.v, 2) if F else None, "seed": F.seed if F else None,
            "space": round(S.get("rt_space", 0.0), 3), "shot": frt._state["shot"].name if frt._state["shot"] else None,
            "energy": round(S.get("rt_energy", 0.0), 3), "kick": round(S.get("rt_kick", 0.0), 3),
            "pos": [round(c.x, 1), round(c.y, 1), round(c.z, 1)]}


def on_draw():
    now = time.perf_counter() - st["t0"]
    if st["done"]:
        return
    m = S.camera.matrix_world.copy()
    lens = S.camera.data.lens
    if st["last"] is not None:             # time, frame ms, mm moved, millidegrees turned, lens, 1 if the view is the same
        c0, l0 = st["cam"]
        r = c0.to_3x3().normalized().transposed() @ m.to_3x3().normalized()
        turn = math.degrees(math.acos(max(-1.0, min(1.0, (r[0][0] + r[1][1] + r[2][2] - 1.0) / 2.0))))
        st["draws"].append((round(now, 4), round((now - st["last"]) * 1000.0, 2),
                            round((m.translation - c0.translation).length * 1000.0, 2), round(turn * 1000.0, 2),
                            round(lens, 3), int(m == c0 and lens == l0)))
    st["last"], st["cam"] = now, (m, lens)
    prog = job["program"]
    while st["pi"] < len(prog) and prog[st["pi"]][0] <= now:
        apply(prog[st["pi"]][1])
        st["pi"] += 1
    hz = job.get("grab_hz", GRAB_HZ)        # 0: no grabs, for an undisturbed fps trace
    if hz > 0.0 and now >= st["next_grab"]:
        st["next_grab"] = now + 1.0 / hz
        try:
            a = np.asarray(DN["syphon_out"].offscreen.texture_color.read())
            h_, w_ = a.shape[0] // 2, a.shape[1] // 2
            a = (a[:h_ * 2, :w_ * 2, :3].astype(np.uint16).reshape(h_, 2, w_, 2, 3).sum(axis=(1, 3)) // 4).astype(np.uint8)[::-1]
            small = a[::4, ::4].astype(np.float32)
            diff = float(np.abs(small - st["prev"]).mean()) if st["prev"] is not None else 0.0
            st["prev"] = small
            path = os.path.join(job["out"], "f%05d.ppm" % st["n"])
            with open(path, "wb") as f:
                f.write(b"P6\n%d %d\n255\n" % (w_, h_) + np.ascontiguousarray(a).tobytes())
            st["grabs"].append(dict(t=round(now, 4), i=st["n"], diff=round(diff, 3), **rig_state()))
            st["n"] += 1
        except Exception as e:
            st["grabs"].append({"t": now, "err": str(e)})
    if now >= job["seconds"]:
        st["done"] = True
        with open(os.path.join(job["out"], "trace.json"), "w") as f:
            json.dump({"program": job["program"], "draws": st["draws"], "grabs": st["grabs"]}, f)
        bpy.app.timers.register(lambda: bpy.types.SpaceView3D.draw_handler_remove(st["handle"], "WINDOW"), first_interval=0.01)


st["handle"] = bpy.types.SpaceView3D.draw_handler_add(on_draw, (), "WINDOW", "POST_PIXEL")
