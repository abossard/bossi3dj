"""Night edges of the Path Camera: a /vj/grid 1 and 0 pair at night for each pose, for net_regularity.py.
In the live planet Blender with flight_rt started:
    DN["pe_job"] = {"out": "/abs/dir", "poses": [[path, target, height wire], ...]}; exec this file; wait for DN["pe_done"].
Per pose: a cut there (/vj/blend 0), wait until the stream shows the whole view and 3 s more, freeze the clocks, hold
night 1 and grid 1, read a Syphon frame, grid 0, read again; writes <i>_<path>_<target>_g1.ppm and _g0.ppm (960x540)
and pe.json (the poses, the shown depth range, the camera's height over the ground). Holds every control against OSC and Art-Net while it runs; puts every control and hold back.
With JOB "holes": true, per pose also <i>_<path>_<target>_holes.png: an OpenGL render of the camera view with
Sea_Underside (seen only through a hole in the land) as pure green, its green share in pe.json. The render is off the
Syphon output, but the swapped material shows there for about one frame.
Then:  .venv/bin/python blender/review/net_regularity.py DIR 00_orbit_pyramids_g1:00_orbit_pyramids_g0 ...
"""
import json
import math
import os
import time

import bpy
import numpy as np

DN = bpy.app.driver_namespace
S = bpy.context.scene
JOB = DN["pe_job"]
BR = DN["vj_osc_bridge"]
RT = DN.get("vj_runtime")
FRAME = next(h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "frame" and h.__module__ == "flight_rt")
G = FRAME.__globals__
FS, LOD, fl, pc = G["_state"], G["lod_scene"], G["fl"], G["pc"]
RIG = S.objects[G["RIG"]]
SETTLE = 4                  # Syphon frames after a change before a frame is read
DN["pe_done"] = False
st = {"want": False, "got": None, "handle": None}


def draw():
    if not st["want"]:
        return
    s = DN.get("syphon_out")
    if s is None or s.offscreen is None or bpy.context.region_data is None or bpy.context.region_data.view_perspective != "CAMERA":
        return
    st["want"] = False
    a = np.asarray(s.offscreen.texture_color.read())
    if a.dtype != np.uint8:
        a = np.clip(a * 255.0, 0, 255).astype(np.uint8)
    st["got"] = a


def write_ppm(a, path):
    """Flipped to top-down, every second pixel (960x540 of 1920x1080)."""
    a = a[::-1, :, :3][::2, ::2]
    with open(path, "wb") as f:
        f.write(b"P6 %d %d 255\n" % (a.shape[1], a.shape[0]))
        f.write(np.ascontiguousarray(a).tobytes())


def frames():
    return DN["syphon_out"].frames


def apply(values):
    BR.apply({"/" + k.replace("_", "/", 1): [float(v)] for k, v in values.items()}, "web")


def holes(name):
    """Green share of the camera view with the sea's underside pure green (the hole test)."""
    ob = S.objects["Sea_Underside"]
    mod = ob.modifiers[0]
    ident = next(it.identifier for it in mod.node_group.interface.items_tree
                 if getattr(it, "in_out", "") == "INPUT" and it.name == "Material")
    sock = getattr(mod.properties.inputs, ident)
    old = sock.value
    m = bpy.data.materials.get("_hole_green") or bpy.data.materials.new("_hole_green")
    if m.node_tree is None:
        m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    em, out = nt.nodes.new("ShaderNodeEmission"), nt.nodes.new("ShaderNodeOutputMaterial")
    em.inputs["Color"].default_value = (0.0, 1.0, 0.0, 1.0)
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    path = os.path.join(JOB["out"], name + "_holes.png")
    fp, ff = S.render.filepath, S.render.image_settings.file_format
    S.render.filepath, S.render.image_settings.file_format = path, "PNG"
    try:
        sock.value = m
        ob.update_tag()
        for win in bpy.context.window_manager.windows:
            area = next((a for a in win.screen.areas if a.type == "VIEW_3D"), None)
            if area is not None:
                with bpy.context.temp_override(window=win, area=area):
                    bpy.ops.render.opengl(write_still=True, view_context=True)
                break
    finally:
        sock.value = old
        ob.update_tag()
        S.render.filepath, S.render.image_settings.file_format = fp, ff
    img = bpy.data.images.load(path)
    a = np.empty(len(img.pixels), np.float32)
    img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    a = a.reshape(-1, 4)
    green = (a[:, 1] > 0.8) & (a[:, 0] < 0.25) & (a[:, 2] < 0.25)
    return {"green_px": int(green.sum()), "green_share": round(float(green.mean()), 6)}


def run():
    os.makedirs(JOB["out"], exist_ok=True)
    saved = {"values": {k: S.get(k) for k in ("vj_night", "vj_grid", "vj_blend", "vj_path", "vj_target", "vj_height")},
             "hold": set(BR.hold)}
    meta = []
    BR.hold = {k for k in S.keys() if k.startswith("vj_")}     # OSC and Art-Net (Magic, QLC+) cannot move a pose
    try:
        for i, (path, target, w) in enumerate(JOB["poses"]):
            apply({"vj_blend": 0.0, "vj_night": 1.0, "vj_grid": 1.0, "vj_path": pc.PATHS.index(path),
                   "vj_target": pc.TARGETS.index(target), "vj_height": w})
            t = time.perf_counter()
            yield 1.0
            while time.perf_counter() - t < 60.0 and not (LOD.live() and not LOD.holding() and not LOD._state.get("near_missing")):
                yield 0.2
            yield 3.0
            names = []
            for g in (1.0, 0.0):
                RT.freeze(True)
                apply({"vj_grid": g})
                f0 = frames()
                while frames() < f0 + SETTLE:
                    RT.freeze(True)
                    yield 0.05
                st["got"], st["want"] = None, True
                while st["got"] is None:
                    RT.freeze(True)
                    yield 0.05
                name = "%02d_%s_%s_g%d" % (i, path, target, int(g))
                write_ppm(st["got"], os.path.join(JOB["out"], name + ".ppm"))
                names.append(name)
            hole = holes("%02d_%s_%s" % (i, path, target)) if JOB.get("holes") else None
            RT.freeze(False)
            cam = tuple(RIG.matrix_world.translation)
            u = fl.norm(fl.sub(cam, fl.CENTRE))
            depths = [k[1] for v in (LOD._state.get("nodes") or {}).values() for k in v]
            meta.append({"pose": [path, target, w], "pair": ":".join(names),
                         "agl_m": round(fl.length(fl.sub(cam, fl.CENTRE)) - fl.R - FS["map"].surface(u), 1),
                         "depths": [min(depths, default=-1), max(depths, default=-1)], "lens": round(RIG.data.lens, 1), "holes": hole})
    finally:
        RT.freeze(False)
        for k, v in saved["values"].items():
            if v is not None:
                S[k] = v
        BR.hold = saved["hold"]
        json.dump(meta, open(os.path.join(JOB["out"], "pe.json"), "w"), indent=1)
        bpy.types.SpaceView3D.draw_handler_remove(st["handle"], "WINDOW")
        DN["pe_done"] = True


gen = run()


def tick():
    try:
        return next(gen)
    except StopIteration:
        return None
    except Exception:
        import traceback
        DN["pe_err"] = traceback.format_exc()
        DN["pe_done"] = True
        return None


st["handle"] = bpy.types.SpaceView3D.draw_handler_add(draw, (), "WINDOW", "POST_PIXEL")
bpy.app.timers.register(tick, first_interval=0.1)
