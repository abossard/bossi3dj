"""Does the river water move on the GPU terrain? In the live planet Blender:
    DN["rc_job"] = {"out": "/abs/dir", "shots": [{"name": str, "set": {vj_key: value}}], "frames": 40, "settle": 12.0};
    exec this file; wait for DN["rc_done"].
Per shot: every vj_ control held at the runtime's defaults plus the shot's set; the camera flies there for "settle" s,
then stops (/vj/cam_speed 0) with the idle pulse off, so only the water's own animation changes the picture. Then
"frames" consecutive Syphon frames twice: with the flow as built and with the Sea GPU's flow scaled to 0 (the
RIVER_SPEED scale node). Out per shot: <name>.png and <name>_last.png (the first and last frame with the flow), <name>_motion.png (per-pixel mean change with
the flow, x8, grey), <name>_flow.png (the change the flow adds: with minus without, x8, clipped at 0), and in rivers.json
the share of pixels the flow moves (adds over 1 of 255) and the mean changes with and without. The flow drifts the
ripples a tenth of a metre a frame, so also over the whole capture: span_share, the pixels whose first-to-last change
with the flow exceeds the change without by over SPAN of 255, and <name>_span.png (that excess, x4). draw_ms: the
median interval between new Syphon frames while the flow runs (a frame time only when make status says fps_trustworthy).
Same views across runs: each row records the camera it used ("pose": its world matrix and lens); a shot given a "pose"
holds the camera there (after flight_rt's frame, the GPU grid centred on it) instead of where the flight stopped.
"""
import json
import os
import sys
import time

import bpy
import numpy as np

DN = bpy.app.driver_namespace
S = bpy.context.scene
JOB = DN["rc_job"]
BR = DN["vj_osc_bridge"]
TICK = next(h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "synthwave_tick")
RT_G = TICK.__globals__
if "gpu_terrain" not in sys.modules:       # flight_rt's copy, for pin()
    sys.modules["gpu_terrain"] = next(h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "frame"
                                      and "gpu_terrain" in h.__globals__).__globals__["gpu_terrain"]
DN["rc_done"] = False
st = {"want": False, "got": [], "last": -1, "t": []}
SPAN = 4.0
LUM = np.array([0.2126, 0.7152, 0.0722], np.float32)


def flow_node():
    nt = bpy.data.materials["Sea GPU"].node_tree
    return next(n for n in nt.nodes if n.type == "VECT_MATH" and n.operation == "SCALE"
                and abs(n.inputs["Scale"].default_value - 2.6) < 1e-4)


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
    st["got"].append(a[..., :3].copy())
    st["t"].append(time.perf_counter())


def png(path, rgb):
    h, w = rgb.shape[:2]
    img = bpy.data.images.new("rc_tmp", w, h, alpha=True)
    px = np.ones((h, w, 4), np.float32)
    px[..., :3] = rgb.astype(np.float32) / 255.0
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw, img.file_format = path, "PNG"
    img.save()
    bpy.data.images.remove(img)


def capture():
    st["got"], st["t"], st["want"] = [], [], True
    while len(st["got"]) < JOB.get("frames", 40):
        yield 0.01
    st["want"] = False


def span(frames):
    return np.abs(frames[-1].astype(np.float32) @ LUM - frames[0].astype(np.float32) @ LUM)


def motion(frames):
    lum = [f.astype(np.float32) @ LUM for f in frames]
    return np.mean([np.abs(lum[i + 1] - lum[i]) for i in range(len(lum) - 1)], axis=0)


def run():
    hold0 = set(BR.hold)
    defaults = {k: v for k, v in RT_G["DEFAULTS"].items() if k in S}
    fn = flow_node()
    k0 = fn.inputs["Scale"].default_value
    rows = []
    try:
        BR.hold = {k for k in S.keys() if k.startswith("vj_")}
        for shot in JOB["shots"]:
            vals = dict(defaults)
            vals.update(shot["set"])
            BR.apply({"/" + k.replace("_", "/", 1): [float(v)] for k, v in vals.items()}, "river_check")
            t = time.perf_counter()
            while time.perf_counter() - t < shot.get("settle", JOB.get("settle", 12.0)):
                yield 0.1
            BR.apply({"/vj/cam_speed": [0.0]}, "river_check")
            bpy.app.handlers.frame_change_pre.insert(0, no_pulse)
            st["pose"] = shot.get("pose")
            if st["pose"] is not None:
                bpy.app.handlers.frame_change_pre.append(pin)     # after flight_rt's frame
            cam = S.camera
            t = time.perf_counter()
            while time.perf_counter() - t < 3.0:
                yield 0.1
            yield from capture()
            on = list(st["got"])
            draw_ms = float(np.median(np.diff(st["t"]))) * 1000.0
            fn.inputs["Scale"].default_value = 0.0
            t = time.perf_counter()
            while time.perf_counter() - t < 1.0:
                yield 0.1
            yield from capture()
            off = list(st["got"])
            fn.inputs["Scale"].default_value = k0
            bpy.app.handlers.frame_change_pre.remove(no_pulse)
            pose = {"matrix": [x for row in cam.matrix_world for x in row], "lens": cam.data.lens}
            if pin in bpy.app.handlers.frame_change_pre:
                bpy.app.handlers.frame_change_pre.remove(pin)
            m_on, m_off = motion(on), motion(off)
            add = np.clip(m_on - m_off, 0.0, None)
            base = os.path.join(JOB["out"], shot["name"])
            png(base + ".png", on[0])
            png(base + "_last.png", on[-1])
            png(base + "_motion.png", np.repeat(np.clip(m_on * 8.0, 0, 255)[:, :, None], 3, 2))
            png(base + "_flow.png", np.repeat(np.clip(add * 8.0, 0, 255)[:, :, None], 3, 2))
            ex = span(on) - span(off)
            png(base + "_span.png", np.repeat(np.clip(ex * 4.0, 0, 255)[:, :, None], 3, 2))
            rows.append({"shot": shot, "flow_share": round(float((add > 1.0).mean()), 5),
                         "span_share": round(float((ex > SPAN).mean()), 5), "draw_ms": round(draw_ms, 1), "pose": pose,
                         "mad_with_flow": round(float(m_on.mean()), 4), "mad_without": round(float(m_off.mean()), 4),
                         "load": round(os.getloadavg()[0], 1)})
    finally:
        fn.inputs["Scale"].default_value = k0
        for h in (no_pulse, pin):
            if h in bpy.app.handlers.frame_change_pre:
                bpy.app.handlers.frame_change_pre.remove(h)
        BR.hold = set()
        BR.apply({"/" + k.replace("_", "/", 1): [float(v)] for k, v in defaults.items()}, "river_check")
        BR.hold = hold0
        bpy.types.SpaceView3D.draw_handler_remove(st["handle"], "WINDOW")
        json.dump(rows, open(os.path.join(JOB["out"], "rivers.json"), "w"), indent=1)
        DN["rc_done"] = True


gen = run()


def tick():
    try:
        return next(gen)
    except StopIteration:
        return None
    except Exception:
        import traceback
        DN["rc_err"] = traceback.format_exc()
        DN["rc_done"] = True
        return None


st["handle"] = bpy.types.SpaceView3D.draw_handler_add(draw, (), "WINDOW", "POST_PIXEL")
bpy.app.timers.register(tick, first_interval=0.1)
