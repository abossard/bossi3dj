"""Issue #25 live: the Path Camera's blend fixes and the SKY_FRAME variant in the planet Blender. In it:
    DN["bl_job"] = {"out": "/abs/file.jsonl", "program": [[t, path, target, height, cam_speed, blend], ...],
                    "set": {"BLEND_LAND": 0.35, "BLEND_BY_HEIGHT": True, "SKY_FRAME": False}, "settle": 20.0,
                    "flag": "/abs/flag"?}; exec this file; wait for DN["bl_done"].
Holds the camera controls (vj_path, vj_target, vj_height, vj_cam_speed, vj_blend) against OSC and plays the program
(each row from its t, the first row held for "settle" s before t 0), with path_camera's switches set as given (restored
after). The other vj_ controls stay with Magic. Writes "flag" at t 0 (tools/syphon_record.py --flag starts there).
Every 0.25 s one line: t, the Syphon frame's luminance mean and spread (std over a 160 x 90 grid, 0..255; the demo's
fault map calls a frame flat under 15), rt_space, the Path Camera's blending and view.
"""
import json
import sys
import time

import bpy
import numpy as np

DN = bpy.app.driver_namespace
S = bpy.context.scene
JOB = DN["bl_job"]
BR = DN["vj_osc_bridge"]
PC = sys.modules["path_camera"]
KEYS = ("vj_path", "vj_target", "vj_height", "vj_cam_speed", "vj_blend")
LUM = np.array([0.2126, 0.7152, 0.0722], np.float32)
DN["bl_done"] = False
st = {"last": -1, "frame": None}


def draw():
    s = DN.get("syphon_out")
    if s is None or s.offscreen is None or s.frames == st["last"]:
        return
    st["last"] = s.frames
    a = np.asarray(s.offscreen.texture_color.read())
    a = a[:: max(a.shape[0] // 90, 1), :: max(a.shape[1] // 160, 1), :3].astype(np.float32)
    st["frame"] = a * (255.0 if a.max() <= 1.0 else 1.0)


def control(path, target, height, speed, blend):
    vals = {"vj_path": float(PC.PATHS.index(path)), "vj_target": float(PC.TARGETS.index(target)), "vj_height": height,
            "vj_cam_speed": speed, "vj_blend": blend}
    BR.apply({"/" + k.replace("_", "/", 1): [float(v)] for k, v in vals.items()}, "blend_live")


def run():
    hold0, old = set(BR.hold), {k: getattr(PC, k) for k in JOB.get("set", {})}
    prog = JOB["program"]
    rows = []
    try:
        for k, v in JOB.get("set", {}).items():
            setattr(PC, k, v)
        BR.hold = set(hold0) | set(KEYS)
        control(*prog[0][1:])
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < JOB.get("settle", 20.0):
            yield 0.1
        if JOB.get("flag"):
            open(JOB["flag"], "w").close()
        t0, i, nxt = time.perf_counter(), 0, 0.0
        while True:
            t = time.perf_counter() - t0
            if t > prog[-1][0]:
                break
            while i + 1 < len(prog) and prog[i + 1][0] <= t:
                i += 1
                control(*prog[i][1:])
            if t >= nxt and st["frame"] is not None:
                lum = st["frame"] @ LUM
                rows.append({"t": round(t, 2), "mean": round(float(lum.mean()), 1), "spread": round(float(lum.std()), 1),
                             "rt_space": round(float(S.get("rt_space", 0.0)), 3),
                             "blending": float(S.get("rt_blending", 0.0)), "view": " ".join(prog[i][1:3])})
                nxt = t + 0.25
            yield 0.05
    finally:
        for k, v in old.items():
            setattr(PC, k, v)
        BR.hold = hold0
        bpy.types.SpaceView3D.draw_handler_remove(st["handle"], "WINDOW")
        with open(JOB["out"], "w") as f:
            f.writelines(json.dumps(r) + "\n" for r in rows)
        DN["bl_done"] = True


gen = run()


def tick():
    try:
        return next(gen)
    except StopIteration:
        return None
    except Exception:
        import traceback
        DN["bl_err"] = traceback.format_exc()
        DN["bl_done"] = True
        return None


st["handle"] = bpy.types.SpaceView3D.draw_handler_add(draw, (), "WINDOW", "POST_PIXEL")
bpy.app.timers.register(tick, first_interval=0.1)
