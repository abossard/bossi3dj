"""In-Blender grab and cut sequencer for the visual check.
DN["grab_jobs"] = [job, ...] before exec; progress and results in DN["grabber"].
job kinds:
  {"kind": "grab", "set": {"vj_cam": 2, ...}, "phase": 0.0|None, "settle": 3.0, "out": "/abs/x.ppm"}
      applies the controls like the web page does, waits, then writes the Syphon frame (1920x1080) halved to 960x540
  {"kind": "cut", "set": {...}, "cam": 3, "watch": 1.5, "tag": "..."}
      applies the controls, then cuts to CAM_<cam> and records draw intervals for `watch` s (M1) and, for CAM_3,
      the aim error at the first drawn frame (M2)."""
import math
import time

import bpy
import numpy as np
from mathutils import Vector

DN = bpy.app.driver_namespace
S = bpy.context.scene
HOLD = {"vj_cam", "vj_night", "vj_shock", "vj_fog", "vj_eclipse", "vj_moon_phase", "vj_cam_speed"}

old = DN.get("grabber")
if old and old.get("handle"):
    try:
        bpy.types.SpaceView3D.draw_handler_remove(old["handle"], "WINDOW")
    except Exception:
        pass
st = {"i": -1, "jobs": list(DN.get("grab_jobs", [])), "log": [], "done": False, "draws": [], "want": None,
      "cut": None, "handle": None, "err": None}
DN["grabber"] = st


def star_mod():
    for h in bpy.app.handlers.frame_change_pre:
        if getattr(h, "__name__", "") == "synthwave_tick":
            return h.__globals__["_state"].get("star_system")
    return None


def aim_error(rv3d, cam):
    ss = star_mod()
    if ss is None or cam.get("vj_track") not in ("sun", "moon"):
        return None
    fwd = rv3d.view_matrix.inverted().to_3x3() @ Vector((0.0, 0.0, -1.0))
    centre = tuple(S.objects["Planet_Centre"].matrix_world.translation)
    cam_p = tuple(rv3d.view_matrix.inverted().translation)
    r = ss.solve(centre, S.get("pl_radius", 16000.0), cam_p, S.get("rt_space", 0.0), S.get("vj_night", 0.0),
                 S.get("vj_moon_phase", 1.0), S.get("vj_eclipse", 0.0), ss._state["beta"])
    body = r["moon"] if cam["vj_track"] == "moon" else tuple(Vector(cam_p) + Vector(r["sun"]) * 150000.0)
    p = ss.aim_point(cam_p, r["up"], body)
    want = (Vector(p) - Vector(cam_p)).normalized()
    return math.degrees(fwd.angle(want))


def on_draw():
    now = time.perf_counter()
    ctx = bpy.context
    if ctx.region_data is None or ctx.region_data.view_perspective != "CAMERA":
        return
    st["draws"].append(now)
    if len(st["draws"]) > 4000:
        del st["draws"][:2000]
    cut = st["cut"]
    if cut is not None and cut.get("first") is None and S.camera is not None and S.camera.name == cut.get("to"):
        cut["first"] = now
        cut["fwd_first"] = ctx.region_data.view_matrix.inverted().to_3x3() @ Vector((0.0, 0.0, -1.0))
        try:
            cut["aim_first"] = aim_error(ctx.region_data, S.camera)
        except Exception as e:
            cut["aim_first"] = "err %s" % e
    if cut is not None and cut.get("first") is not None and cut.get("aim_late") is None and now - cut["first"] > 1.0:
        fwd = ctx.region_data.view_matrix.inverted().to_3x3() @ Vector((0.0, 0.0, -1.0))
        cut["aim_jump"] = math.degrees(fwd.angle(cut["fwd_first"]))
        try:
            cut["aim_late"] = aim_error(ctx.region_data, S.camera)
        except Exception as e:
            cut["aim_late"] = "err %s" % e
    w = st["want"]
    if w is not None and now >= w["due"]:
        st["want"] = None
        try:
            sender = DN["syphon_out"]
            a = np.asarray(sender.offscreen.texture_color.read())
            if w.get("full"):        # the Syphon frame as sent, 1920x1080
                h_, w_ = a.shape[0], a.shape[1]
                a = np.ascontiguousarray(a[:, :, :3][::-1])
            else:
                h_, w_ = a.shape[0] // 2, a.shape[1] // 2
                a = a[:h_ * 2, :w_ * 2, :3].astype(np.uint16).reshape(h_, 2, w_, 2, 3).sum(axis=(1, 3)) // 4
                a = a.astype(np.uint8)[::-1]
            with open(w["out"], "wb") as f:
                f.write(b"P6\n%d %d\n255\n" % (w_, h_) + a.tobytes())
            w["ok"] = True
        except Exception as e:
            w["ok"] = "err %s" % e
        w["t"] = now


st["handle"] = bpy.types.SpaceView3D.draw_handler_add(on_draw, (), "WINDOW", "POST_PIXEL")


def apply(values):
    bridge = DN.get("vj_osc_bridge")
    bridge.hold = bridge.hold | HOLD
    bridge.apply({"/" + k.replace("_", "/", 1): [float(v)] for k, v in values.items()}, "web")


def step():
    try:
        return _step()
    except Exception as e:
        import traceback
        st["err"] = traceback.format_exc()
        st["done"] = True
        return None


def _step():
    now = time.perf_counter()
    i = st["i"]
    if i >= 0:
        job = st["jobs"][i]
        if job["kind"] == "grab":
            w = job["_w"]
            if "ok" not in w:
                return 0.05                     # the frame has not been drawn yet
            ds = [t for t in st["draws"] if job["_t0"] + job["settle"] - 1.5 <= t <= w["t"]]
            fps = round((len(ds) - 1) / (ds[-1] - ds[0]), 1) if len(ds) > 2 else 0.0
            st["log"].append({"out": job["out"], "ok": w["ok"], "fps": fps, "cam": S.camera.name})
        else:
            cut = st["cut"]
            if now < cut["t"] + job.get("watch", 1.5):
                return 0.05
            ds = [cut["before"]] + [t for t in st["draws"] if cut["t"] <= t <= cut["t"] + job.get("watch", 1.5)]
            iv = [round(1000 * (b - a), 1) for a, b in zip(ds, ds[1:])]
            st["log"].append({"tag": job.get("tag"), "from": cut["from"], "to": cut["to"], "worst_ms": max(iv) if iv else None,
                              "first_ms": iv[0] if iv else None, "iv": iv[:12], "aim_first": cut.get("aim_first"),
                              "aim_late": cut.get("aim_late"), "aim_jump": cut.get("aim_jump")})
            st["cut"] = None
    i += 1
    st["i"] = i
    if i >= len(st["jobs"]):
        st["done"] = True
        return None
    job = st["jobs"][i]
    if job.get("exec"):
        exec(job["exec"], {"bpy": bpy, "S": S, "DN": DN})
    if job.get("set"):
        apply(job["set"])
    if job.get("camera"):            # a camera outside /vj/cam's range (CAM_SYS and the system views)
        S.camera = S.objects[job["camera"]]
    if job.get("phase") is not None:
        S["rt_cam_phase"] = float(job["phase"])
        S.update_tag()
    if job["kind"] == "grab":
        job["_t0"] = now
        job["_w"] = {"due": now + job["settle"], "out": job["out"], "full": job.get("full", False)}
        st["want"] = job["_w"]
        return job["settle"] + 0.05
    # cut: let the set controls settle, then cut
    bpy.app.timers.register(lambda: do_cut(job), first_interval=job.get("pre", 1.0))
    st["cut"] = {"t": 1e18, "from": S.camera.name}
    return job.get("pre", 1.0) + 0.1


def do_cut(job):
    st["cut"]["before"] = st["draws"][-1] if st["draws"] else time.perf_counter()
    st["cut"]["from"] = S.camera.name
    st["cut"]["to"] = "CAM_%d" % job["cam"]
    st["cut"]["t"] = time.perf_counter()
    apply({"vj_cam": job["cam"]})
    return None


bpy.app.timers.register(step, first_interval=0.2)
