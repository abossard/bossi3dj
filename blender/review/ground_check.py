"""G5 check: every pyramid in a camera's view against the ground that camera draws.
For each camera (path cameras at DN["gc_phases"] of their loop), takes the land set the runtime shows for it and,
for every pyramid instance (Planet_Sites, and the island's Pyramids collection) in the camera frame within MAX_D,
casts rays straight down onto that land mesh through the base centre and the four base corners. Gap = base height
over the drawn ground there: > 0 floats, < 0 is sunk. A miss means no drawn ground under it (culled patch).
Results: DN["ground_check"] = {cam@phase: {"n": pyramids, "float": [...], "miss": [...], "max_gap": m}}."""
import math

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

DN = bpy.app.driver_namespace
S = bpy.context.scene
R = 16000.0
C = Vector((0.0, 0.0, -R))
MAX_D = 6000.0
rt = next(h for h in bpy.app.handlers.depsgraph_update_pre
          if h.__name__ == "on_cut" and "nearest_set" in h.__globals__).__globals__    # the Flight runtime has an on_cut too


def bases(dg):
    """(name, base corners in world space, centre) for every pyramid above the sea."""
    out = []
    for inst in dg.object_instances:
        if not inst.is_instance or inst.parent is None:
            continue
        par = inst.parent.original.name
        if not (par == "Planet_Sites" or par.startswith("Planet_Sites.")):
            continue
        M = inst.matrix_world.copy()
        c = M.translation
        if (c - C).length < R - 5.0:          # reflections
            continue
        up = (c - C).normalized()
        bb = sorted((M @ Vector(v) for v in inst.object.bound_box), key=lambda p: (p - C).dot(up))
        corners = bb[:4]
        c = sum(corners, Vector()) / 4.0
        out.append(("site", corners, c))
    coll = bpy.data.collections.get("Pyramids")
    for ob in (coll.objects if coll else ()):
        e = ob.evaluated_get(dg)
        bb = [e.matrix_world @ Vector(v) for v in e.bound_box]
        up = (e.matrix_world.translation - C).normalized()
        bb.sort(key=lambda p: (p - C).dot(up))
        corners = bb[:4]
        out.append((ob.name, corners, sum(corners, Vector()) / 4.0))
    return out


def check(cam, dg, label):
    near = rt["nearest_set"](S, cam)
    land = S.objects.get("Planet." + near[0]) if near else None
    if land is None:
        return {"set": None}
    le = land.evaluated_get(dg)
    cp = cam.evaluated_get(dg).matrix_world.translation
    res = {"set": near[0], "n": 0, "float": [], "miss": [], "max_gap": -1e9, "min_gap": 1e9, "max_px": 0.0}
    px_rad = 2.0 * math.atan(18.0 / cam.data.lens) / 960.0       # one pixel of the 960 px grab
    for name, corners, centre in bases(dg):
        if (centre - cp).length > MAX_D:
            continue
        v = world_to_camera_view(S, cam.evaluated_get(dg), centre)
        if not (v.z > 0 and -0.05 <= v.x <= 1.05 and -0.05 <= v.y <= 1.05):
            continue
        res["n"] += 1
        gaps = []
        for p in corners + [centre]:
            up = (p - C).normalized()
            hit = le.ray_cast(p + up * 150.0, -up, distance=400.0)
            if hit[0]:
                gaps.append((p - C).length - (hit[1] - C).length)
        if not gaps:
            res["miss"].append((name, round((centre - cp).length)))
            continue
        g = min(gaps)                  # the lowest corner's gap: > 0 means no corner touches the ground
        res["max_gap"] = max(res["max_gap"], g)
        res["max_px"] = max(res["max_px"], round(g / (centre - cp).length / px_rad, 2))
        res["min_gap"] = min(res["min_gap"], min(gaps))
        if g > 0.5:
            res["float"].append((name, round(g, 1), round((centre - cp).length), round(g / (centre - cp).length / px_rad, 2)))
    res["max_gap"] = round(res["max_gap"], 2)
    res["min_gap"] = round(res["min_gap"], 2)
    res["float"] = sorted(res["float"], key=lambda f: -f[1])[:8]
    return res


out = {}
phases = DN.get("gc_phases", (0.0, 0.25, 0.5, 0.75))
for cam in sorted((o for o in S.objects if o.type == "CAMERA" and o.name.startswith("CAM_") and o.name[4:].isdigit()),
                  key=lambda o: int(o.name[4:])):
    for ph in (phases if "path_period" in cam else (0.0,)):
        S["rt_cam_phase"] = cam.get("path_period", 0.0) * ph
        S.update_tag()
        dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
        out["%s@%g" % (cam.name, ph)] = check(cam, dg, ph)
S["rt_cam_phase"] = 0.0
DN["ground_check"] = out
