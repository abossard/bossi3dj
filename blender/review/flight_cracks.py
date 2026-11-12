"""Numbers of the stream's border cracks at the Flight's pose, off the Syphon output: the drawn border of every shown node
(its vertices as the vertex shader moves them, lod_stream's morph with the real rt_cam) against the coarser neighbour's
border polyline, in m, grouped by depth step and by the morph at the fine side's border vertices.
    DN["crack_job"] = {"out": "/abs/cracks.json", "flight": 0.3333}; exec this file; wait for DN["crack_done"].
Flies the Flight (seed 1) to the stage, holds it for 4 s, reads the shown blocks (their meshes hold the unmorphed grids in
node order), then returns to CAM_0."""
import json
import math
import time

import bpy
import numpy as np

DN = bpy.app.driver_namespace
S = bpy.context.scene
JOB = DN["crack_job"]
BR = DN["vj_osc_bridge"]
FRAME = next(h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "frame" and h.__module__ == "flight_rt")
G = FRAME.__globals__
FS, LOD = G["_state"], G["lod_scene"]
ls = LOD.ls
FC = next(o for o in S.objects if o.type == "CAMERA" and o.get("vj_flight_cam"))
DN["crack_done"] = False


def send(**values):
    BR.apply({"/" + k.replace("_", "/", 1): [float(v)] for k, v in values.items()}, "flight_cracks")


def node_grids():
    """Per shown node, its (n+1)^2 grid of unmorphed positions: the block mesh holds its nodes' grids one after the other
    (lod_scene.assemble concatenates the nodes' arrays in the order of the block's key tuple)."""
    p = LOD._state["params"]
    nv = (p.n + 1) ** 2
    out = {}
    for b, (ob, keys) in LOD._state["shown"].items():
        me = ob.data
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", co)
        v = co.reshape(-1, 3).astype(np.float64)
        # land and water share the nodes' vertex arrays: only the land part (the first nv vertices of a node) is needed,
        # and the mirror copy adds more. Each node's arrays start at its own offset in "POINT" order of the cache.
        off = 0
        for k in keys:
            nd = LOD._state["cache"].get(k)
            if nd is None:
                continue
            cnt = nd["n"][0]
            out[k] = v[off:off + nv]
            off += cnt
    return out


def morph_pos(key, g, cam, p):
    """g: (nv, 3) unmorphed positions in lattice order (the Mesh Grid is x-major: index = x * (n + 1) + y)."""
    n = p.n
    d = key[1]
    res = np.array(g, dtype=np.float64).reshape(n + 1, n + 1, 3)       # [x][y]
    mm = np.zeros((n + 1, n + 1))
    out = res.copy()
    camv = np.array(cam)
    for x in range(n + 1):
        for y in range(n + 1):
            q = res[x, y]
            m = ls.morph_factor(float(np.linalg.norm(q - camv)), d, p)
            if m > 0.0 and (x % 2 or y % 2):
                if x % 2 and not y % 2:
                    t = 0.5 * (res[x - 1, y] + res[x + 1, y])
                elif y % 2 and not x % 2:
                    t = 0.5 * (res[x, y - 1] + res[x, y + 1])
                else:
                    t = 0.5 * (res[x + 1, y - 1] + res[x - 1, y + 1])
                out[x, y] = q + (t - q) * m
            mm[x, y] = m
    return out, mm


def analyse():
    p = LOD._state["params"]
    n = p.n
    cam = (S["rt_cam_x"], S["rt_cam_y"], S["rt_cam_z"])
    grids = node_grids()
    drawn = {k: morph_pos(k, g, cam, p) for k, g in grids.items()}
    res = {"nodes": len(grids), "pairs": {}, "worst": []}
    near_all = []
    # how far the morph lowers the drawn land under its unmorphed height (radial, per vertex), by depth: the margin a
    # water face needs under the land so that a morphed land cannot dip below it
    C_ = np.array(ls.CENTRE)
    drop = {}
    for k, (gm, mm) in drawn.items():
        g0 = np.array(grids[k]).reshape(n + 1, n + 1, 3)
        r0 = np.linalg.norm(g0 - C_, axis=2)
        r1 = np.linalg.norm(gm - C_, axis=2)
        dd = float((r0 - r1).max())
        a_ = drop.setdefault(k[1], [])
        a_.append(dd)
    res["morph_drop_by_depth"] = {str(d): {"n": len(v), "max_m": round(max(v), 1), "p95_m": round(float(np.percentile(v, 95)), 1)} for d, v in sorted(drop.items())}
    edges = {"s": lambda a: a[:, 0], "n": lambda a: a[:, n], "w": lambda a: a[0, :], "e": lambda a: a[n, :]}
    for k, (gm, mm) in drawn.items():
        f, d, i, j = k
        for side, (di, dj, opp) in {"w": (-1, 0, "e"), "e": (1, 0, "w"), "s": (0, -1, "n"), "n": (0, 1, "s")}.items():
            ni, nj = i + di, j + dj
            if not (0 <= ni < (1 << d) and 0 <= nj < (1 << d)) or (f, d, ni, nj) in drawn:
                continue
            for dd in range(1, d + 1):
                a = (f, d - dd, ni >> dd, nj >> dd)
                if a in drawn:
                    break
            else:
                continue
            pts = edges[side](gm)
            line = edges[opp](drawn[a][0]) if dd == 1 else None
            if line is None:
                key = "step%d" % dd
                res["pairs"][key] = res["pairs"].get(key, {"n": 0})
                res["pairs"][key]["n"] += 1
                continue
            worst = 0.0
            for q in pts:
                best = 1e18
                for u, v in zip(line, line[1:]):
                    uv = v - u
                    t = min(max(float(np.dot(q - u, uv)) / max(float(np.dot(uv, uv)), 1e-12), 0.0), 1.0)
                    best = min(best, float(np.linalg.norm(q - (u + uv * t))))
                worst = max(worst, best)
            mfine = float(edges[side](mm).mean())
            dcam = float(np.linalg.norm(pts[n // 2] - np.array(cam)))
            bucket = res["pairs"].setdefault("step1", {"n": 0, "gaps": []})
            bucket["n"] += 1
            bucket["gaps"].append(worst)
            near_all.append(dcam < 9000.0)
            if worst > 0.05:
                res["worst"].append({"fine": list(k), "coarse": list(a), "gap_m": round(worst, 2), "dist_m": round(dcam), "morph_fine": round(mfine, 2)})
    g = res["pairs"].get("step1", {}).get("gaps", [])
    if g:
        res["pairs"]["step1"]["gaps"] = {"max": round(max(g), 3), "over_1m": sum(1 for x in g if x > 1.0), "over_0.05": sum(1 for x in g if x > 0.05)}
    res["near_borders"] = sum(1 for r in near_all if r)
    allworst = list(res["worst"])
    res["worst_within_9km"] = sorted([r for r in allworst if r["dist_m"] < 9000], key=lambda r: -r["gap_m"])[:12]
    res["worst"] = sorted(allworst, key=lambda r: -r["gap_m"])[:12]
    res["cam"] = [round(c) for c in cam]
    return res


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
    f = JOB.get("flight", 1.0 / 3.0)
    send(vj_flight=f)
    t0, since = time.perf_counter(), None
    while time.perf_counter() - t0 < 120.0:
        F = FS.get("flight")
        ok = F is not None and abs(F.f - f) < 2e-3
        since = (since or time.perf_counter()) if ok else None
        if since is not None and time.perf_counter() - since > 4.0:
            break
        yield 0.2
    res = analyse()
    send(vj_flight=0.0, vj_cam=0.0, vj_blend=1.0)
    json.dump(res, open(JOB["out"], "w"), indent=1)
    DN["crack_done"] = True


gen = run()


def tick():
    try:
        return next(gen)
    except StopIteration:
        return None
    except Exception:
        import traceback
        DN["crack_err"] = traceback.format_exc()
        DN["crack_done"] = True
        return None


bpy.app.timers.register(tick, first_interval=0.1)
