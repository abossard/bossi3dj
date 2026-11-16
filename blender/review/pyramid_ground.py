"""Ground-gap scan of the site pyramids against the GPU terrain (rubric-round17 N17-GAP). In the live planet Blender:
    DN["pg_job"] = {"out": "/abs/file.json", "rings": [0, 1, 2, 3, 4, 5]}; exec this file; read the JSON.
Per site pyramid (Planet_Sites' instances, mirrored copies skipped): its base square and apex from the instance's
mesh. The terrain the GPU grid draws at ring l: the map's land height (bilinear, as GT_Map's texels) at the ring's
lattice points (3 m x 2^l, fixed in map longitude and latitude), linear over the grid's two triangles per cell. The near
noise is left out (it only acts within 120 m of the camera; see gpu_terrain.NOISE).
A foundation under the base (build_planet.PYR_FOUND) shows where the land dips under the base: float_found_n counts the
pyramids whose base edge has the land lower than the foundation's depth (they float even so). Per ring: along the base edges, gap = base plane - terrain (> 0: the pyramid floats there) and buried = terrain - base
plane (as a share of the pyramid's height); inside the footprint, cut = terrain - the pyramid's face (> 0: the ground
slices through a face). With the pads of gpu_terrain.pads the map is the padded one.
Variants (issue #12), without a rebuild: DN["pg_job"]["variants"] = [{"name": str, "pad_edge": [level, blend] m,
"found_k": x}]: each scans the raw map padded with gpu_terrain.pads at that PAD_EDGE (default the built one), the
foundation's depth scaled by found_k (default 1); out then {"variants": {name: scan}}.
"""
import json
import math
import sys

import bpy
import numpy as np

import flight as fl

DN = bpy.app.driver_namespace
JOB = DN["pg_job"]
gt = sys.modules["gpu_terrain"]
S = bpy.context.scene
A = gt._state["axes"] if gt._state.get("axes") is not None else gt.axes(S)
H = gt._state.get("h_padded")
if H is None:
    H = gt.bake(S, None)[0]
ROWS, W = H.shape
C = np.array(fl.CENTRE, float)


def pyramids():
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for inst in dg.object_instances:
        if not (inst.is_instance and inst.parent and inst.parent.name == "Planet_Sites"):
            continue
        m = np.array(inst.matrix_world.copy())
        if np.linalg.det(m[:3, :3]) <= 0.0:
            continue
        v = np.array([tuple(x.co) for x in inst.object.data.vertices], float)
        out.append((m[:3, :3] @ v.T).T + m[:3, 3])
    return out


def map_height(lam, phi):
    x = (lam + math.pi) / (2.0 * math.pi) * W - 0.5
    y = (phi + math.pi / 2.0) / math.pi * ROWS - 0.5
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = x - x0, y - y0
    x0m, x1m = x0 % W, (x0 + 1) % W
    y0c, y1c = np.clip(y0, 0, ROWS - 1), np.clip(y0 + 1, 0, ROWS - 1)
    a = H[y0c, x0m] * (1 - fx) + H[y0c, x1m] * fx
    b = H[y1c, x0m] * (1 - fx) + H[y1c, x1m] * fx
    return a * (1 - fy) + b * fy


def coords(p):
    d = p - C
    d = d / np.linalg.norm(d, axis=-1, keepdims=True)
    c = d @ A.T
    return np.arctan2(c[..., 1], c[..., 0]), np.arcsin(np.clip(c[..., 2], -1.0, 1.0))


def ring_height(lam, phi, l):
    s = gt.CELL_M * 2.0 ** l / fl.R
    i, j = lam / s, phi / s
    i0, j0 = np.floor(i), np.floor(j)
    fx, fy = i - i0, j - j0
    h = lambda a, b: map_height((i0 + a) * s, (j0 + b) * s)
    h00, h10, h11, h01 = h(0, 0), h(1, 0), h(1, 1), h(0, 1)
    lower = fx >= fy          # triangle (a, b, c) of the grid: (0,0) (1,0) (1,1); else (0,0) (1,1) (0,1)
    return np.where(lower, h00 + fx * (h10 - h00) + fy * (h11 - h10), h00 + fy * (h01 - h00) + fx * (h11 - h01))


def scan(rings, found_k=1.0):
    pyr = pyramids()
    rows = {l: {"float_n": 0, "float_found_n": 0, "gap_max": 0.0, "buried_share": [], "cut_n": 0, "cut_max": 0.0} for l in rings}
    worst = []
    t = np.linspace(0.0, 1.0, 17)
    g = np.linspace(-0.95, 0.95, 9)
    for vs in pyr:
        centre = vs.mean(0)
        up = (centre - C) / np.linalg.norm(centre - C)
        ht = vs @ up
        apex = vs[np.argmax(ht)]
        base = gt.site_base(vs, up)
        bc = base.mean(0)
        hgt = float((apex - bc) @ up)
        found = float((bc - vs[np.argmin(ht)]) @ up) * found_k     # the foundation's depth under the base (0 without one)
        ang = np.arctan2((base - bc) @ np.cross(up, base[0] - bc), (base - bc) @ (base[0] - bc))
        base = base[np.argsort(ang)]
        edge = np.concatenate([base[k] + np.outer(t, base[(k + 1) % 4] - base[k]) for k in range(4)])
        e_base = np.linalg.norm(edge - C, axis=1) - fl.R
        u, v = np.meshgrid(g, g)
        u, v = u.ravel(), v.ravel()
        a1, a2 = (base[0] - base[2]) / 2.0, (base[1] - base[3]) / 2.0     # half diagonals
        inner = bc + np.outer((u + v) / 2.0, a1) + np.outer((u - v) / 2.0, a2)
        frac = 1.0 - np.maximum(np.abs(u), np.abs(v))
        face = np.linalg.norm(inner + np.outer(frac * hgt, up) - C, axis=1) - fl.R
        el, ep = coords(edge)
        il, ip = coords(inner)
        for l in rings:
            ter = ring_height(el, ep, l)
            gap = e_base - ter
            r = rows[l]
            r["float_n"] += int(gap.max() > 0.3)
            r["float_found_n"] += int(gap.max() > found + 0.3)
            r["gap_max"] = max(r["gap_max"], float(gap.max()))
            r["buried_share"].append(max(0.0, float((-gap).max())) / hgt)
            cut = ring_height(il, ip, l) - face
            r["cut_n"] += int(cut.max() > 0.3)
            r["cut_max"] = max(r["cut_max"], float(cut.max()))
            if l == rings[0]:
                worst.append((float(gap.max()), float((-gap).max()), round(hgt, 1), [round(x) for x in bc]))
    out = {"pyramids": len(pyr), "rings": {}}
    for l, r in rows.items():
        b = np.array(r.pop("buried_share"))
        r.update(buried_p50=round(float(np.median(b)), 4), buried_p95=round(float(np.percentile(b, 95)), 4),
                 buried_over_6pct=int((b > 0.06).sum()), gap_max=round(r["gap_max"], 2), cut_max=round(r["cut_max"], 2),
                 cell_m=gt.CELL_M * 2 ** l)
        out["rings"][str(l)] = r
    worst.sort(reverse=True)
    out["worst_float_ring0"] = worst[:5]
    return out


RINGS = JOB.get("rings", [0, 1, 2, 3, 4, 5])
if "variants" in JOB:
    raw, pe0 = gt.bake(S, None)[0], gt.PAD_EDGE
    res = {"variants": {}}
    try:
        for v in JOB["variants"]:
            gt.PAD_EDGE = tuple(v.get("pad_edge", pe0))
            H = gt.pads(S, raw, A)[0]
            res["variants"][v["name"]] = dict(scan(RINGS, v.get("found_k", 1.0)), variant=v)
    finally:
        gt.PAD_EDGE = pe0
        H = gt._state.get("h_padded")
else:
    res = scan(RINGS)
json.dump(res, open(JOB["out"], "w"), indent=1)
DN["pg_result"] = res
