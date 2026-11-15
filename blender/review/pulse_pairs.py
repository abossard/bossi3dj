"""Rest and peak frames of the pyramids' pulse per shot (rubric-round17 R17-*). In the live planet Blender:
    DN["pp_job"] = {"out": "/abs/dir", "shots": [{"name": str, "set": {vj_key: value}}], "settle": 14.0}; exec;
    wait for DN["pp_done"].
Per shot: every vj_ control held at the runtime's defaults plus the shot's set; the camera flies there for "settle" s
and stops (/vj/cam_speed 0). Then one Syphon frame with rt_pulse forced to 0 (<name>_rest.png) and one with it forced
to 1 (<name>_peak.png), full size.
"""
import os
import time

import bpy
import numpy as np

DN = bpy.app.driver_namespace
S = bpy.context.scene
JOB = DN["pp_job"]
BR = DN["vj_osc_bridge"]
TICK = next(h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "synthwave_tick")
RT_G = TICK.__globals__
DN["pp_done"] = False
st = {"want": False, "got": [], "last": -1, "force": None}


def force(scene, depsgraph=None):
    if st["force"] is not None:
        scene["rt_pulse"] = st["force"]


def draw():
    s = DN.get("syphon_out")
    if not st["want"] or s is None or s.offscreen is None or s.frames == st["last"]:
        return
    st["last"] = s.frames
    a = np.asarray(s.offscreen.texture_color.read())
    if a.dtype != np.uint8:
        a = np.clip(a * 255.0, 0, 255).astype(np.uint8)
    st["got"].append(a[..., :3].copy())


def png(path, rgb):
    h, w = rgb.shape[:2]
    img = bpy.data.images.new("pp_tmp", w, h, alpha=True)
    px = np.ones((h, w, 4), np.float32)
    px[..., :3] = rgb.astype(np.float32) / 255.0
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw, img.file_format = path, "PNG"
    img.save()
    bpy.data.images.remove(img)


def wait(s):
    t = time.perf_counter()
    while time.perf_counter() - t < s:
        yield 0.1


def grab(path):
    st["got"], st["want"] = [], True
    while len(st["got"]) < 3:          # the third new frame: the forced value is drawn
        yield 0.01
    st["want"] = False
    png(path, st["got"][-1])


def run():
    hold0 = set(BR.hold)
    defaults = {k: v for k, v in RT_G["DEFAULTS"].items() if k in S}
    bpy.app.handlers.frame_change_pre.append(force)      # after flight_rt's frame, which writes rt_pulse
    try:
        BR.hold = {k for k in S.keys() if k.startswith("vj_")}
        for shot in JOB["shots"]:
            vals = dict(defaults)
            vals.update(shot["set"])
            BR.apply({"/" + k.replace("_", "/", 1): [float(v)] for k, v in vals.items()}, "pulse_pairs")
            yield from wait(shot.get("settle", JOB.get("settle", 14.0)))
            BR.apply({"/vj/cam_speed": [0.0]}, "pulse_pairs")
            yield from wait(1.5)
            for f, tag in ((0.0, "rest"), (1.0, "peak")):
                st["force"] = f
                yield from wait(0.4)
                yield from grab(os.path.join(JOB["out"], "%s_%s.png" % (shot["name"], tag)))
            st["force"] = None
    finally:
        st["force"] = None
        if force in bpy.app.handlers.frame_change_pre:
            bpy.app.handlers.frame_change_pre.remove(force)
        BR.hold = set()
        BR.apply({"/" + k.replace("_", "/", 1): [float(v)] for k, v in defaults.items()}, "pulse_pairs")
        BR.hold = hold0
        bpy.types.SpaceView3D.draw_handler_remove(st["handle"], "WINDOW")
        DN["pp_done"] = True


gen = run()


def tick():
    try:
        return next(gen)
    except StopIteration:
        return None
    except Exception:
        import traceback
        DN["pp_err"] = traceback.format_exc()
        DN["pp_done"] = True
        return None


st["handle"] = bpy.types.SpaceView3D.draw_handler_add(draw, (), "WINDOW", "POST_PIXEL")
bpy.app.timers.register(tick, first_interval=0.1)
