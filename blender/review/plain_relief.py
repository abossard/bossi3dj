"""Round 11 numbers of the plains, headless, on a built planet file:

    blender -b --disable-autoexec FILE.blend --python blender/review/plain_relief.py [-- CAM_0 CAM_3]

Per camera, the drawn land of that camera's LOD set (Planet.<cam>.0), dry vertices in its frame between NEAR and FAR m:
height spread (std of h, std after a plane fit), face slope (median, p90, share of faces under 1 deg; the same for the
plains alone, faces under 15 deg, per distance band), and inland water
of its Water set in frame (vertices under water above sea level). Planet-wide: lake vertices of the hydrology grid and
river length. Prints one line 'PLAIN_RELIEF {json}'."""
import json
import math
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

R = 16000.0
C = np.array((0.0, 0.0, -R))
NEAR, FAR = 30.0, 8000.0
CELL_M = 200.0
BANDS = ((30.0, 300.0), (300.0, 1000.0), (1000.0, 3000.0), (3000.0, 8000.0))
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
CAMS = ARGS or ["CAM_0", "CAM_3"]
S = bpy.context.scene


def show(ob):
    ob.hide_viewport = False
    ob.hide_set(False)
    for c in ob.users_collection:
        c.hide_viewport = False


def attr(me, name, n):
    a = np.empty(n)
    me.attributes[name].data.foreach_get("value", a)
    return a


def positions(me):
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def view_matrix(cam):
    """cam's world matrix; a camera with a hold rig (CAM_3) gets the rig's rotation, the pose the runtime shows while
    the moon is down (headless, without the runtime, it tracks the moon's default target)."""
    rig = bpy.data.objects.get(cam.name + "_hold_rig")
    if rig is None:
        return cam.matrix_world
    return Matrix.Translation(cam.matrix_world.translation) @ rig.matrix_world.to_quaternion().to_matrix().to_4x4()


def in_frame(cam, co):
    """Mask of points in cam's frame and their distance to it."""
    M = np.array(view_matrix(cam).inverted())
    loc = co @ M[:3, :3].T + M[:3, 3]
    z = -loc[:, 2]
    fx = cam.data.lens / cam.data.sensor_width * 2.0
    aspect = S.render.resolution_x / S.render.resolution_y
    with np.errstate(divide="ignore", invalid="ignore"):
        x = loc[:, 0] / z * fx
        y = loc[:, 1] / z * fx * aspect
    ok = (z > 0) & (np.abs(x) <= 1) & (np.abs(y) <= 1)
    return ok, np.linalg.norm(loc, axis=1)


def land_stats(cam, dg):
    ob = bpy.data.objects["Planet.%s.0" % cam.name]
    me = ob.evaluated_get(dg).to_mesh()
    co = positions(me)
    n = len(co)
    rel = co - C
    rad = np.linalg.norm(rel, axis=1)
    h = rad - R
    up = rel / rad[:, None]
    ok, dist = in_frame(cam, co)
    sel = ok & (dist > NEAR) & (dist < FAR) & (attr(me, "mirror", n) < 0.5) & (h > attr(me, "pl_w", n) + 0.05)
    out = {"vertices": int(sel.sum())}
    if sel.sum() < 10:
        ob.evaluated_get(dg).to_mesh_clear()
        return out
    # tangent frame at the camera's foot: plane fit of h over (u, v)
    u0 = Vector(up[sel].mean(axis=0)).normalized()
    t1 = u0.orthogonal().normalized()
    t2 = u0.cross(t1)
    P = co[sel]
    A = np.c_[P @ np.array(t1), P @ np.array(t2), np.ones(len(P))]
    coef, *_ = np.linalg.lstsq(A, h[sel], rcond=None)
    out["h_std"] = round(float(h[sel].std()), 2)
    out["h_resid_std"] = round(float((h[sel] - A @ coef).std()), 2)
    # face slope against the local up
    me.calc_loop_triangles()
    tri = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", tri)
    tri = tri.reshape(-1, 3)
    tri = tri[sel[tri].all(axis=1)]
    a, b, c = co[tri[:, 0]], co[tri[:, 1]], co[tri[:, 2]]
    nrm = np.cross(b - a, c - a)
    nrm /= np.linalg.norm(nrm, axis=1)[:, None] + 1e-12
    upf = up[tri].mean(axis=1)
    upf /= np.linalg.norm(upf, axis=1)[:, None]
    ang = np.degrees(np.arccos(np.clip(np.abs((nrm * upf).sum(axis=1)), 0, 1)))
    out["faces"] = int(len(ang))
    out["slope_med_deg"] = round(float(np.median(ang)), 2)
    out["slope_p90_deg"] = round(float(np.percentile(ang, 90)), 2)
    out["flat_share_1deg"] = round(float((ang < 1.0).mean()), 3)
    # the plains alone (faces under 15 deg) per distance band: where the lattice showed
    dface = dist[tri].mean(axis=1)
    # local relief of the near plain (faces under 15 deg, closer than 1 km): height std after a plane fit per
    # CELL_M square, median over the squares (one fit over the whole frame measured the hills, not the plain)
    pv = np.unique(tri[(ang < 15.0) & (dface < 1000.0)])
    uv = np.c_[co[pv] @ np.array(t1), co[pv] @ np.array(t2)]
    key = np.floor(uv / CELL_M).astype(np.int64)
    stds = []
    for k in np.unique(key, axis=0):
        m = (key == k).all(axis=1)
        if m.sum() >= 20:
            Ak = np.c_[uv[m], np.ones(m.sum())]
            ck, *_ = np.linalg.lstsq(Ak, h[pv][m], rcond=None)
            stds.append(float((h[pv][m] - Ak @ ck).std()))
    if stds:
        out["plain_local_std_m"] = round(float(np.median(stds)), 2)
        out["plain_cells"] = len(stds)
    for lo, hi in BANDS:
        m = (dface >= lo) & (dface < hi) & (ang < 15.0)
        if m.sum():
            out["plain_%d_%d" % (lo, hi)] = {"faces": int(m.sum()), "of_all": int(((dface >= lo) & (dface < hi)).sum()), "slope_med_deg": round(float(np.median(ang[m])), 2),
                                            "flat_share_1deg": round(float((ang[m] < 1.0).mean()), 3)}
    ob.evaluated_get(dg).to_mesh_clear()
    return out


def water_stats(cam, dg):
    ob = bpy.data.objects["Water.%s.0" % cam.name]
    me = ob.evaluated_get(dg).to_mesh()
    co = positions(me)
    lvl = np.linalg.norm(co - C, axis=1) - R
    ok, dist = in_frame(cam, co)
    wet = attr(me, "pl_depth", len(co)) > 0.05
    inland = ok & wet & (lvl > 0.5) & (dist < 3000.0)
    out = {"inland_wet_vertices": int(inland.sum())}
    ob.evaluated_get(dg).to_mesh_clear()
    return out


def hydro_stats(dg):
    gs = bpy.data.objects["Planet_Hydro"].evaluated_get(dg).evaluated_geometry()
    me = gs.mesh
    n = len(me.vertices)
    wet = attr(me, "wet", n) > 0.5
    lake = wet & (attr(me, "h", n) >= 0.0)
    cur = gs.curves
    length = 0.0
    if cur is not None:
        pos = np.empty(len(cur.points) * 3)
        cur.attributes["position"].data.foreach_get("vector", pos)
        pos = pos.reshape(-1, 3)
        for cv in cur.curves:
            p = pos[cv.first_point_index:cv.first_point_index + cv.points_length]
            length += float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum())
    return {"lake_vertices": int(lake.sum()), "rivers": len(cur.curves) if cur is not None else 0,
            "river_km": round(length / 1000.0, 2)}


S.frame_set(1)
res = {"file": bpy.data.filepath, "cameras": {}}
for name in CAMS:
    for prefix in ("Planet.", "Water."):
        show(bpy.data.objects[prefix + name + ".0"])
show(bpy.data.objects["Planet_Hydro"])
dg = bpy.context.evaluated_depsgraph_get()
dg.update()
for name in CAMS:
    cam = bpy.data.objects[name]
    p = np.array(cam.matrix_world.translation)
    res["cameras"][name] = {"eye_alt_m": round(float(np.linalg.norm(p - C) - R), 1),
                            "land": land_stats(cam, dg), "water": water_stats(cam, dg)}
res["hydrology"] = hydro_stats(dg)
print("PLAIN_RELIEF " + json.dumps(res))
