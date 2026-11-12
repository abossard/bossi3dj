"""The stream's seams at the Flight's pose, in the live planet Blender with flight_rt started, off the Syphon output
(nothing is drawn differently): DN["seam_job"] = {"out": "/abs/seams.json"}; exec this file; wait for DN["seam_done"].
Reads the shown blocks of lod_scene after the Flight has flown to its Approach (seed 1), then for every pair of
neighbouring shown nodes (same face) of different depth works out, with lod_stream's pure model:
  - the depth difference (the 2:1 balance the morph assumes: more than 1 leaves a gap along the border),
  - the largest gap between the two drawn border polylines (the morph at the camera the shader uses, rt_cam),
and the share of near blocks wholly or partly missing. Writes the numbers, never the images."""
import json
import math
import time

import bpy

DN = bpy.app.driver_namespace
S = bpy.context.scene
JOB = DN["seam_job"]
BR = DN["vj_osc_bridge"]
FRAME = next(h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "frame" and h.__module__ == "flight_rt")
G = FRAME.__globals__
FS, LOD, fl = G["_state"], G["lod_scene"], G["fl"]
ls = LOD.ls
FC = next(o for o in S.objects if o.type == "CAMERA" and o.get("vj_flight_cam"))
DN["seam_done"] = False


def send(**values):
    BR.apply({"/" + k.replace("_", "/", 1): [float(v)] for k, v in values.items()}, "flight_seams")


def analyse():
    p = LOD._state["params"]
    cam = (S["rt_cam_x"], S["rt_cam_y"], S["rt_cam_z"])
    nodes = {}
    for b, (ob, keys) in LOD._state["shown"].items():
        for k in keys:
            nodes[k] = b
    by_face = {}
    for k in nodes:
        by_face.setdefault(k[0], []).append(k)
    # edge-adjacent pairs of different depth: a node of depth d at (i, j) touches a node of depth d' where its
    # edge cells' parent-grid neighbours lie
    jumps = {}
    for k in nodes:
        f, d, i, j = k
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ni, nj = i + di, j + dj
            if not (0 <= ni < (1 << d) and 0 <= nj < (1 << d)):
                continue
            same = (f, d, ni, nj) in nodes
            if same:
                continue
            # the neighbour cell is covered by an ancestor (coarser) or by descendants (finer)
            gap = None
            a = (f, d, ni, nj)
            for dd in range(1, d + 1):
                a = (f, d - dd, ni >> dd, nj >> dd)
                if a in nodes:
                    gap = dd
                    break
            if gap is None:
                gap = 0       # finer, or not shown (counted from the finer side)
            jumps[gap] = jumps.get(gap, 0) + 1
    # the same census on the selection the model makes at this pose (no look-ahead, margin as the runtime's), and the
    # depth-2 and depth-3 borders of the shown set with their distance to the camera and their blocks' state
    hr = LOD._state["hr"]
    pp = ls.Params(p.n, p.k, p.m0, p.d_max, 0.0, p.block_up, p.cull)
    pp.margin = LOD.SEL_STEP + 1.0
    sel = set(ls.select(cam, pp, hr, None))

    def census(nodes):
        out, bad = {}, []
        for k in nodes:
            f, d, i, j = k
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ni, nj = i + di, j + dj
                if not (0 <= ni < (1 << d) and 0 <= nj < (1 << d)) or (f, d, ni, nj) in nodes:
                    continue
                for dd in range(1, d + 1):
                    a = (f, d - dd, ni >> dd, nj >> dd)
                    if a in nodes:
                        out[dd] = out.get(dd, 0) + 1
                        if dd >= 2:
                            bad.append({"fine": list(k), "coarse": list(a), "dist_fine": round(ls.dist_to(k, cam, hr)),
                                        "dist_coarse": round(ls.dist_to(a, cam, hr))})
                        break
        return out, bad
    sel_c, sel_bad = census(sel)
    shown_c, shown_bad = census(set(nodes))
    near_missing = len(LOD._state.get("near_missing") or ())
    # the node bounds' heights (hr, from the clearance map) against the drawn surface: the morph's balance assumes the
    # true distances; a node whose drawn heights leave its bounds sits nearer than the model thinks
    import numpy as np
    hr_, C = LOD._state["hr"], np.array(ls.CENTRE)
    outside, worst, by_depth, ex = 0, 0.0, {}, []
    for b, (ob, keys) in LOD._state["shown"].items():
        me = ob.data
        if not len(me.vertices):
            continue
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", co)
        r = np.linalg.norm(co.reshape(-1, 3).astype(np.float64) - C, axis=1) - ls.R
        bs = [hr_(k) or (ls.H_LO, ls.H_HI) for k in keys]
        lo, hi = min(x[0] for x in bs), max(x[1] for x in bs)
        exc = max(float(r.max() - hi), float(lo - r.min()), 0.0)
        if exc > 0:
            outside += 1
            worst = max(worst, exc)
            by_depth[b[1]] = by_depth.get(b[1], 0) + 1
            if len(ex) < 5:
                ex.append((list(b), round(float(r.min()), 1), round(float(r.max()), 1), round(lo, 1), round(hi, 1)))
    # land faces by how far they stand above the water level there (pl_depth = water - ground per vertex): the stream's
    # wet test keeps a water face only up to 1 m of land over the water; a morph that lowers the land past that leaves
    # a hole (the underside shows)
    bands = {1: 0, 10: 0, 25: 0, 40: 0, 80: 0}
    land_faces = water_faces = 0
    for b_, (ob_, keys_) in LOD._state["shown"].items():
        me_ = ob_.data
        at = me_.attributes.get("pl_depth")
        if at is None or not len(me_.polygons):
            continue
        d_ = np.empty(len(me_.vertices), np.float32)
        at.data.foreach_get("value", d_)
        mat = np.empty(len(me_.polygons), np.int32)
        me_.attributes["material_index"].data.foreach_get("value", mat)
        lc = np.empty(len(me_.loops), np.int32)
        me_.loops.foreach_get("vertex_index", lc)
        fd = d_[lc].reshape(-1, 3).mean(axis=1)
        land = mat == 0
        land_faces += int(land.sum())
        water_faces += int((mat == 1).sum())
        for m in bands:
            bands[m] += int((land & (fd > -m) & (fd <= -1.0)).sum())
    bounds_check = {"land_faces": land_faces, "water_faces": water_faces, "land_within_m_above_water": bands,"blocks": len(LOD._state["shown"]), "outside_hr": outside, "worst_m": round(worst, 2), "by_depth": by_depth, "examples": ex}
    holes = {"bounds": bounds_check, "shown_nodes": len(nodes), "model_selection_nodes": len(sel), "model_jumps": sel_c, "shown_jumps": shown_c,
             "model_bad": sel_bad[:10], "shown_bad": shown_bad[:10], "in_model_not_shown": len(sel - set(nodes)),
             "in_shown_not_model": len(set(nodes) - sel), "depth_jump_counts": jumps, "near_missing": near_missing,
             "depths": {str(d): sum(1 for k in nodes if k[1] == d) for d in sorted({k[1] for k in nodes})},
             "cam": [round(c) for c in cam], "m0": p.m0, "k": p.k}
    return holes


def run():
    send(vj_blend=0.0, vj_flight=0.0, vj_night=0.0)
    for k in list(S.keys()):
        if k.startswith("vj_") and k != "vj_cam" and isinstance(S[k], (int, float)):
            d = S.id_properties_ui(k).as_dict().get("default")
            if d is not None:
                S[k] = d
    G["quiesce"](JOB.get("seed", 1))
    send(vj_cam=float(FC.name[4:]))
    yield 2.0
    send(vj_flight=1.0 / 3.0)
    t0 = time.perf_counter()
    since = None
    while time.perf_counter() - t0 < 120.0:
        F = FS.get("flight")
        ok = F is not None and abs(F.f - 1.0 / 3.0) < 2e-3
        since = (since or time.perf_counter()) if ok else None
        if since is not None and time.perf_counter() - since > 4.0:
            break
        yield 0.2
    res = {"approach": analyse()}
    send(vj_flight=0.0, vj_cam=0.0, vj_blend=1.0)
    json.dump(res, open(JOB["out"], "w"), indent=1)
    DN["seam_done"] = True


gen = run()


def tick():
    try:
        return next(gen)
    except StopIteration:
        return None
    except Exception:
        import traceback
        DN["seam_err"] = traceback.format_exc()
        DN["seam_done"] = True
        return None


bpy.app.timers.register(tick, first_interval=0.1)
