"""Do the pyramids pulse on one envelope (rubric-round17 N17-PULSE)? In the live planet Blender:
    DN["pu_job"] = {"out": "/abs/dir", "set": {vj_key: value}, "settle": 12.0, "frames": 90}; exec; wait for DN["pu_done"].
Every vj_ control held at the runtime's defaults plus "set"; the camera flies there for "settle" s and stops
(/vj/cam_speed 0). Then 10 Syphon frames each with rt_pulse forced to 0, to 1, and to 1 with the gain at 40 (round17_probes.py's node):
the pixels that the last brightens by over 40 of 255 are the pyramids' mask; their mean luminance at 1 over at 0 is the
swing. Then "frames" frames with the idle
pulse running free: per frame rt_pulse and the mask's mean luminance; the largest one-frame step as a share of the
swing. Out: pulse.json, rest.png, peak.png, mask.png.
"""
import json
import os
import time

import bpy
import numpy as np

DN = bpy.app.driver_namespace
S = bpy.context.scene
JOB = DN["pu_job"]
BR = DN["vj_osc_bridge"]
TICK = next(h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "synthwave_tick")
RT_G = TICK.__globals__
DN["pu_done"] = False
st = {"want": False, "got": [], "last": -1, "force": None, "pulse": []}
LUM = np.array([0.2126, 0.7152, 0.0722], np.float32)


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
    st["pulse"].append(float(S.get("rt_pulse", 0.0)))


def png(path, rgb):
    h, w = rgb.shape[:2]
    img = bpy.data.images.new("pu_tmp", w, h, alpha=True)
    px = np.ones((h, w, 4), np.float32)
    px[..., :3] = rgb.astype(np.float32) / 255.0
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw, img.file_format = path, "PNG"
    img.save()
    bpy.data.images.remove(img)


def capture(n):
    st["got"], st["pulse"], st["want"] = [], [], True
    while len(st["got"]) < n:
        yield 0.01
    st["want"] = False


def wait(s):
    t = time.perf_counter()
    while time.perf_counter() - t < s:
        yield 0.1


def run():
    hold0 = set(BR.hold)
    defaults = {k: v for k, v in RT_G["DEFAULTS"].items() if k in S}
    bpy.app.handlers.frame_change_pre.append(force)      # after flight_rt's frame, which writes rt_pulse
    try:
        BR.hold = {k for k in S.keys() if k.startswith("vj_")}
        vals = dict(defaults)
        vals.update(JOB.get("set", {}))
        BR.apply({"/" + k.replace("_", "/", 1): [float(v)] for k, v in vals.items()}, "pulse_check")
        yield from wait(JOB.get("settle", 12.0))
        BR.apply({"/vj/cam_speed": [0.0]}, "pulse_check")
        yield from wait(2.0)
        gains = DN["r17_nodes"]["gains"]          # round17_probes.py: every pyramid material's gain on rt_pulse
        g0 = gains[0].default_value
        lum = {}
        for f, g, tag in ((0.0, g0, "rest"), (1.0, g0, "peak"), (1.0, 40.0, "mask")):
            st["force"] = f
            for gi in gains:
                gi.default_value = g
            yield from wait(0.5)
            yield from capture(10)
            lum[tag] = np.mean([x.astype(np.float32) @ LUM for x in st["got"]], 0)
            if tag != "mask":
                png(os.path.join(JOB["out"], tag + ".png"), st["got"][0])
        for gi in gains:
            gi.default_value = g0
        mask = (lum["mask"] - lum["rest"]) > 40.0     # the pyramids alone, lit 41 x: the frame's own jitter and
        # the water, clouds and stars change by far less
        png(os.path.join(JOB["out"], "mask.png"), np.repeat(mask[:, :, None] * 255, 3, 2).astype(np.uint8))
        st["force"] = None
        RT_G["_state"]["changed"] = time.perf_counter() - 10.0       # the idle pulse runs from now
        yield from wait(3.0)
        yield from capture(JOB.get("frames", 90))
        series = [float((g.astype(np.float32) @ LUM)[mask].mean()) for g in st["got"]] if mask.any() else []
        rest, peak = float(lum["rest"][mask].mean()), float(lum["peak"][mask].mean())
        swing = max(series) - min(series) if series else 0.0
        steps = np.abs(np.diff(series)) if len(series) > 1 else np.zeros(1)
        res = {"mask_share": round(float(mask.mean()), 4), "rest": round(rest, 2), "peak": round(peak, 2),
               "swing_full": round(peak / max(rest, 1e-3) - 1.0, 3),
               "idle_swing": round(swing / max(min(series), 1e-3), 3) if series else None,
               "idle_step_max_of_swing": round(float(steps.max()) / max(swing, 1e-3), 3),
               "pulse": [round(p, 3) for p in st["pulse"]], "lum": [round(x, 2) for x in series],
               "load": round(os.getloadavg()[0], 1)}
        json.dump(res, open(os.path.join(JOB["out"], "pulse.json"), "w"), indent=1)
        DN["pu_result"] = {k: v for k, v in res.items() if k not in ("pulse", "lum")}
    finally:
        st["force"] = None
        if force in bpy.app.handlers.frame_change_pre:
            bpy.app.handlers.frame_change_pre.remove(force)
        BR.hold = set()
        BR.apply({"/" + k.replace("_", "/", 1): [float(v)] for k, v in defaults.items()}, "pulse_check")
        BR.hold = hold0
        bpy.types.SpaceView3D.draw_handler_remove(st["handle"], "WINDOW")
        DN["pu_done"] = True


gen = run()


def tick():
    try:
        return next(gen)
    except StopIteration:
        return None
    except Exception:
        import traceback
        DN["pu_err"] = traceback.format_exc()
        DN["pu_done"] = True
        return None


st["handle"] = bpy.types.SpaceView3D.draw_handler_add(draw, (), "WINDOW", "POST_PIXEL")
bpy.app.timers.register(tick, first_interval=0.1)
