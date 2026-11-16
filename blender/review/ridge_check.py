"""Issue #10, holes and a pale ring on mountain ridges: the land's zw fix (gpu_terrain.material, node "gt_zw_fix") A/B
on the same frames. In the live planet Blender:
    DN["rg_job"] = {"out": "/abs/dir", "shots": [{"name": str, "set": {vj_key: value}, "pose": {...}?}], "settle": 12.0,
                    "frames": 10}; exec this file; wait for DN["rg_done"].
Per shot: every vj_ control held at the runtime's defaults plus the shot's set; the camera flies there for "settle" s,
stops (/vj/cam_speed 0) and is held at its pose (or the shot's "pose"), the idle pulse off. Then "frames" Syphon frames
with the fix (factor 1, after) and without (0, before). Out per shot: <name>_after.png, <name>_before.png (mean frames),
<name>_diff.png (per-pixel luminance change, x4, grey) and in ridges.json the share of pixels the fix changes by over
CHANGE of 255, the same between two halves of the after frames (the A/A noise), and the pose.
"""
import json
import os
import sys
import time

import bpy
import numpy as np

DN = bpy.app.driver_namespace
S = bpy.context.scene
JOB = DN["rg_job"]
BR = DN["vj_osc_bridge"]
TICK = next(h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "synthwave_tick")
RT_G = TICK.__globals__
if "gpu_terrain" not in sys.modules:       # flight_rt's copy, for pin()
    sys.modules["gpu_terrain"] = next(h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "frame"
                                      and "gpu_terrain" in h.__globals__).__globals__["gpu_terrain"]
DN["rg_done"] = False
st = {"want": False, "got": [], "last": -1}
CHANGE = 8.0
LUM = np.array([0.2126, 0.7152, 0.0722], np.float32)
FIX = [n for m in bpy.data.materials if m.node_tree for n in m.node_tree.nodes if n.label == "gt_zw_fix"]


def set_fix(k):
    for n in FIX:
        n.inputs[1].default_value = k


def pin(scene, depsgraph=None):
    p = st.get("pose")
    if p is None or scene.camera is None:
        return
    from mathutils import Matrix
    scene.camera.matrix_world = Matrix([p["matrix"][i * 4:i * 4 + 4] for i in range(4)])
    scene.camera.data.lens = p["lens"]
    sys.modules["gpu_terrain"].follow(scene, scene.camera.matrix_world.translation)


def no_pulse(scene, depsgraph=None):
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
    st["got"].append(a[..., :3].astype(np.float32))


def png(path, rgb):
    h, w = rgb.shape[:2]
    img = bpy.data.images.new("rg_tmp", w, h, alpha=True)
    px = np.ones((h, w, 4), np.float32)
    px[..., :3] = np.clip(rgb, 0, 255) / 255.0
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw, img.file_format = path, "PNG"
    img.save()
    bpy.data.images.remove(img)


def wait(s):
    t = time.perf_counter()
    while time.perf_counter() - t < s:
        yield 0.1


def capture(n):
    st["got"], st["want"] = [], True
    while len(st["got"]) < n:
        yield 0.01
    st["want"] = False
    return list(st["got"])


def run():
    hold0 = set(BR.hold)
    defaults = {k: v for k, v in RT_G["DEFAULTS"].items() if k in S}
    n = JOB.get("frames", 10)
    rows = []
    try:
        if not FIX:
            raise RuntimeError("no gt_zw_fix node: gpu_terrain without the issue #10 fix")
        BR.hold = {k for k in S.keys() if k.startswith("vj_")}
        for shot in JOB["shots"]:
            set_fix(1.0)
            vals = dict(defaults)
            vals.update(shot["set"])
            BR.apply({"/" + k.replace("_", "/", 1): [float(v)] for k, v in vals.items()}, "ridge_check")
            yield from wait(shot.get("settle", JOB.get("settle", 12.0)))
            BR.apply({"/vj/cam_speed": [0.0]}, "ridge_check")
            cam = S.camera
            st["pose"] = shot.get("pose") or {"matrix": [x for row in cam.matrix_world for x in row], "lens": cam.data.lens}
            bpy.app.handlers.frame_change_pre.insert(0, no_pulse)
            bpy.app.handlers.frame_change_pre.append(pin)     # after flight_rt's frame
            yield from wait(3.0)
            after = yield from capture(n)
            set_fix(0.0)
            yield from wait(1.0)
            before = yield from capture(n)
            set_fix(1.0)
            for h in (no_pulse, pin):
                bpy.app.handlers.frame_change_pre.remove(h)
            a, b = np.mean(after, 0), np.mean(before, 0)
            d = np.abs((a - b) @ LUM)
            aa = np.abs((np.mean(after[: n // 2], 0) - np.mean(after[n // 2:], 0)) @ LUM)
            base = os.path.join(JOB["out"], shot["name"])
            png(base + "_after.png", a)
            png(base + "_before.png", b)
            png(base + "_diff.png", np.repeat(np.clip(d * 4.0, 0, 255)[:, :, None], 3, 2))
            rows.append({"shot": shot["name"], "set": shot["set"], "changed_share": round(float((d > CHANGE).mean()), 5),
                         "aa_share": round(float((aa > CHANGE).mean()), 5), "pose": st["pose"],
                         "load": round(os.getloadavg()[0], 1)})
            st["pose"] = None
    finally:
        set_fix(1.0)
        for h in (no_pulse, pin):
            if h in bpy.app.handlers.frame_change_pre:
                bpy.app.handlers.frame_change_pre.remove(h)
        BR.hold = set()
        BR.apply({"/" + k.replace("_", "/", 1): [float(v)] for k, v in defaults.items()}, "ridge_check")
        BR.hold = hold0
        bpy.types.SpaceView3D.draw_handler_remove(st["handle"], "WINDOW")
        json.dump(rows, open(os.path.join(JOB["out"], "ridges.json"), "w"), indent=1)
        DN["rg_done"] = True


gen = run()


def tick():
    try:
        return next(gen)
    except StopIteration:
        return None
    except Exception:
        import traceback
        DN["rg_err"] = traceback.format_exc()
        DN["rg_done"] = True
        return None


st["handle"] = bpy.types.SpaceView3D.draw_handler_add(draw, (), "WINDOW", "POST_PIXEL")
bpy.app.timers.register(tick, first_interval=0.1)
