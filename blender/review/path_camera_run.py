"""The Path Camera run (docs/handover/path-camera.md, step 4): 3 minutes of control changes at show defaults over every
path and every target, with the terrain test's per-frame log. In the live planet Blender with flight_rt started:
    DN["pc_job"] = {"out": "/abs/run.json", "flag": "/abs/go.flag"}; exec this file; wait for DN["pc_done"].
Optional JOB "passes": [{"name": "day", "set": {}}, {"name": "night", "set": {"vj_night": 1.0}}] flies the STEPS once per
pass, each pass from the wire defaults plus its set (default: one "day" pass).
The job resets the controls to their wire defaults, waits until the stream shows its first view, writes `flag` (a
recorder started with --flag begins there) and sends the STEPS through the bridge as a desk would (source
"path_camera_run"): path, target and height change at the listed second; /vj/blend stays at its default, so most
changes fly and a change can come while the last one still flies. Clocks run, nothing is held.
Per drawn frame the log holds: t, draw interval ms, step, height over the ground (clearance map) and over the sea,
rt_space, shown nodes, their depth range, near nodes still missing, the stream holding a cut, the selection's and the
shown view's lag (m from the camera), whether a blend runs; every swap with the nearest changed node's distance, depth
and pop. Every 10th frame the lower third's ground cell on screen (px of 1920) and the capstone lamps: how many shine
(energy times colour over 1 W: flight_rt fades a hidden lamp's colour) within LAMP_NEAR of the camera with land between (on the clearance map), the case the old per-shot
mask turned off. Holds every control against OSC and Art-Net while it runs. Writes the log and a summary per step."""
import json
import math
import os
import statistics
import time

import bpy

DN = bpy.app.driver_namespace
S = bpy.context.scene
JOB = DN["pc_job"]
BR = DN["vj_osc_bridge"]
FRAME = next(h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "frame" and h.__module__ == "flight_rt")
G = FRAME.__globals__
FS, LOD, fl, pc = G["_state"], G["lod_scene"], G["fl"], G["pc"]
ls = LOD.ls
RIG = S.objects[G["RIG"]]
# (second, path, target, height wire): every path and every target, path and target changes, height from ground to space
STEPS = ((0, "orbit", "pyramids", 0.3), (12, "orbit", "lake", 0.3), (24, "follow", "lake", 0.3), (36, "follow", "river", 0.3),
         (48, "rise", "river", 0.5), (60, "rise", "coast", 0.5), (72, "vantage", "coast", 0.5), (84, "vantage", "moon", 0.5),
         (96, "orbit", "moon", 0.7), (108, "orbit", "planet", 1.0), (120, "vantage", "planet", 1.0), (132, "vantage", "sun", 0.5),
         (144, "follow", "sun", 0.2), (156, "follow", "pyramids", 0.0), (168, "rise", "pyramids", 0.3))
DURATION = 180.0
PASSES = JOB.get("passes") or [{"name": "day", "set": {}}]
LAMP_NEAR = 3000.0          # m: the old mask's reach (build_planet.fog_lights)
LAMPS = [o for o in S.objects if o.name.startswith("Lamp_Capstone.")]
DN["pc_done"] = False


def step_of(t):
    k = min(int(max(t, 0.0) // DURATION), len(PASSES) - 1)
    t = t - k * DURATION
    i = max(j for j, s in enumerate(STEPS) if s[0] <= max(t, 0.0))
    return "%s %02d %s %s %.1f" % ((PASSES[k]["name"], i) + STEPS[i][1:])


def land_between(a, b, n=32):
    """Whether the clearance map's ground rises over the straight line a-b somewhere between them."""
    for k in range(1, n):
        q = fl.add(a, fl.sub(b, a), k / n)
        rq = fl.sub(q, fl.CENTRE)
        if fl.length(rq) - fl.R < FS["map"].ground(fl.norm(rq)):
            return True
    return False


def hidden_lamps(cam):
    return sum(1 for o in LAMPS if o.data.energy * max(o.data.color) > 1.0 and math.dist(cam, o.location) < LAMP_NEAR
               and land_between(cam, tuple(o.location)))


st = {"t0": None, "rows": [], "swaps": [], "probe": [], "lamps": [], "last": None, "nodes": None, "keys": set(), "handle": None, "n": 0}
DN["pc_state"] = st


def ground_ray(p, f, up, lens):
    """The ground point under the lower third of the view (2/3 of the way down from the centre), by marching the map."""
    half = math.atan(20.25 / 2.0 / lens)
    d = fl.norm(fl.add(f, up, -(2.0 / 3.0) * math.tan(half)))
    prev, s = 0.0, 2.0
    while s < 250000.0:
        q = fl.add(p, d, s)
        if fl.length(fl.sub(q, fl.CENTRE)) - fl.R <= FS["map"].surface(fl.norm(fl.sub(q, fl.CENTRE))):
            lo, hi = prev, s
            for _ in range(8):
                mid = 0.5 * (lo + hi)
                qm = fl.add(p, d, mid)
                if fl.length(fl.sub(qm, fl.CENTRE)) - fl.R <= FS["map"].surface(fl.norm(fl.sub(qm, fl.CENTRE))):
                    hi = mid
                else:
                    lo = mid
            return fl.add(p, d, hi), hi
        prev, s = s, s * 1.06
    return None, None


def pop(ch, cam):
    """1 - the morph factor of the finer side's vertex nearest the camera at a level change (0: invisible)."""
    p = LOD._state["params"]
    fine = [k for k in ch if k[1] and (k[0], k[1] - 1, k[2] >> 1, k[3] >> 1) in ch]
    hr = LOD._state.get("hr")
    worst = 0.0
    for k in sorted(fine, key=lambda k: ls.dist_to(k, cam, hr))[:4]:
        dmin = min(math.dist(cam, fl.add(fl.CENTRE, u, fl.R + FS["map"].ground(u)))
                   for u in (ls.node_dir(k, x, y, p.n) for x in range(p.n + 1) for y in range(p.n + 1)))
        worst = max(worst, 1.0 - ls.morph_factor(dmin, k[1], p))
    return worst


def on_draw():
    rd = bpy.context.region_data
    if rd is None or rd.view_perspective != "CAMERA" or st["t0"] is None:
        return
    now = time.perf_counter()
    t = now - st["t0"]
    if st["last"] is None or t > DURATION * len(PASSES):
        st["last"] = now
        return
    ms = (now - st["last"]) * 1000.0
    st["last"] = now
    st["n"] += 1
    m = RIG.matrix_world
    cam = tuple(m.translation)
    u = fl.norm(fl.sub(cam, fl.CENTRE))
    alt = fl.length(fl.sub(cam, fl.CENTRE)) - fl.R
    L = LOD._state
    nodes = L.get("nodes") or {}
    if nodes is not st["nodes"]:
        old = st["keys"]
        new = {k for v in nodes.values() for k in v}
        ch = old ^ new
        if old and ch:
            hr = L.get("hr")
            near = min(ch, key=lambda k: ls.dist_to(k, cam, hr))
            st["swaps"].append((round(t, 3), len(ch), round(ls.dist_to(near, cam, hr), 1), near[1], round(pop(ch, cam), 3)))
        st["nodes"], st["keys"] = nodes, new
    depths = [k[1] for k in st["keys"]]
    sel, shown = L.get("sel_cam"), L.get("shown_cam")
    st["rows"].append((round(t, 3), round(ms, 2), step_of(t), round(alt - FS["map"].surface(u), 1), round(alt, 1),
                       round(S.get("rt_space", 0.0), 3), len(st["keys"]), min(depths, default=-1), max(depths, default=-1),
                       len(L.get("near_missing") or ()), bool(LOD.holding()), round(math.dist(cam, sel), 1) if sel else None,
                       round(math.dist(cam, shown), 1) if shown else None, bool(S.get("rt_blending", 0.0))))
    if st["n"] % 10 == 0:
        st["lamps"].append((round(t, 3), step_of(t), hidden_lamps(cam)))
        r = m.to_3x3().normalized()
        lens = RIG.data.lens
        q, dist = ground_ray(cam, tuple(-r.col[2]), tuple(r.col[1]), lens)
        if q is not None:
            uq = fl.norm(fl.sub(q, fl.CENTRE))
            depth = next((d for d in range(LOD._state["params"].d_max, -1, -1) if ls.key_at(uq, d) in st["keys"]), None)
            if depth is not None:
                cell = ls.FACE_ARC / (1 << depth) / LOD._state["params"].n
                st["probe"].append((round(t, 3), step_of(t), depth, round(dist, 1), round(cell, 1),
                                    round(cell / dist * lens / 36.0 * 1920.0, 2)))


def defaults():
    for k in list(S.keys()):
        if k.startswith("vj_") and isinstance(S[k], (int, float)):
            d = S.id_properties_ui(k).as_dict().get("default")
            if d is not None:
                S[k] = d


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else None


def summary():
    out = {}
    for k_, i, (a, *_rest) in ((k_, i, (s_[0] + k_ * DURATION,) + tuple(s_[1:])) for k_ in range(len(PASSES)) for i, s_ in enumerate(STEPS)):
        b = (STEPS[i + 1][0] if i + 1 < len(STEPS) else DURATION) + k_ * DURATION
        name = step_of(a)
        rows = [r for r in st["rows"] if r[2] == name]
        ms = [r[1] for r in rows]
        sw = [s for s in st["swaps"] if a <= s[0] < b]
        pr = [p for p in st["probe"] if p[1] == name]
        slag = [r[12] for r in rows if r[12] is not None]
        pops = [s[4] for s in sw]
        lm = [x[2] for x in st["lamps"] if x[1] == name]
        out[name] = {"frames": len(rows), "median_ms": round(statistics.median(ms), 1) if ms else None,
                     "p95_ms": round(pct(ms, 0.95), 1) if ms else None, "worst_ms": round(max(ms), 1) if ms else None,
                     "over_33ms": round(sum(1 for x in ms if x > 33.3) / len(ms), 3) if ms else None,
                     "swaps": len(sw), "near_level_changes_300m": sum(1 for s in sw if s[2] < 300.0),
                     "pops_over_0.05": sum(1 for x in pops if x > 0.05), "pop_max": max(pops, default=None),
                     "shown_lag_m_median": round(statistics.median(slag), 1) if slag else None,
                     "shown_lag_m_max": round(max(slag), 1) if slag else None,
                     "near_missing_frames": round(sum(1 for r in rows if r[9] > 0) / len(rows), 3) if rows else None,
                     "holding_frames": sum(1 for r in rows if r[10]),
                     "blending_frames": round(sum(1 for r in rows if r[13]) / len(rows), 3) if rows else None,
                     "agl_min_m": round(min(r[3] for r in rows), 1) if rows else None,
                     "alt_m": [round(min(r[4] for r in rows)), round(max(r[4] for r in rows))] if rows else None,
                     "edge_px_lower_third_median": round(statistics.median([p[5] for p in pr]), 2) if pr else None,
                     "nodes_median": statistics.median([r[6] for r in rows]) if rows else None,
                     "lamp_hidden_lit_share": round(sum(1 for x in lm if x) / len(lm), 3) if lm else None,
                     "lamp_hidden_lit_max": max(lm, default=None),
                     "max_depth_median": statistics.median([r[8] for r in rows]) if rows else None}
    band = [r for r in st["rows"] if pc.BAND[0] <= r[4] <= pc.BAND[1]]
    out["band_8_12km"] = {"frames": len(band), "median_ms": round(statistics.median([r[1] for r in band]), 1) if band else None,
                          "worst_ms": round(max(r[1] for r in band), 1) if band else None}
    ms = [r[1] for r in st["rows"]]
    out["all"] = {"frames": len(ms), "median_ms": round(statistics.median(ms), 1) if ms else None,
                  "p95_ms": round(pct(ms, 0.95), 1) if ms else None, "agl_min_m": round(min(r[3] for r in st["rows"]), 1) if ms else None,
                  "pops_over_0.05": sum(1 for s in st["swaps"] if s[4] > 0.05)}
    for k_, ps in enumerate(PASSES):
        rows = [r for r in st["rows"] if r[2].startswith(ps["name"] + " ")]
        out["pass " + ps["name"]] = {"frames": len(rows), "median_ms": round(statistics.median([r[1] for r in rows]), 1) if rows else None,
                                     "pops_over_0.05": sum(1 for s in st["swaps"] if k_ * DURATION <= s[0] < (k_ + 1) * DURATION and s[4] > 0.05)}
    return out


def set_pass(ps):
    defaults()
    if ps["set"]:
        BR.apply({"/" + k.replace("_", "/", 1): [float(v)] for k, v in ps["set"].items()}, "path_camera_run")


def send(path, target, w):
    BR.apply({"/vj/path": [float(pc.PATHS.index(path))], "/vj/target": [float(pc.TARGETS.index(target))],
              "/vj/height": [w]}, "path_camera_run")


def run():
    load0 = os.getloadavg()[0]
    hold0 = set(BR.hold)
    BR.hold = {k for k in S.keys() if k.startswith("vj_")}     # OSC and Art-Net (Magic, QLC+) cannot move the run
    set_pass(PASSES[0])
    send(*STEPS[0][1:])
    t = time.perf_counter()
    while time.perf_counter() - t < 60.0 and not (LOD.live() and not LOD.holding()):
        yield 0.2
    yield 3.0
    if JOB.get("flag"):
        open(JOB["flag"], "w").write("go\n")
    st["t0"] = time.perf_counter()
    plan = [(s_[0] + k_ * DURATION, k_, s_) for k_ in range(len(PASSES)) for s_ in STEPS]
    nxt = 1
    while time.perf_counter() - st["t0"] < DURATION * len(PASSES) + 0.2:
        el = time.perf_counter() - st["t0"]
        if nxt < len(plan) and el >= plan[nxt][0]:
            if plan[nxt][1] != plan[nxt - 1][1]:
                set_pass(PASSES[plan[nxt][1]])
            send(*plan[nxt][2][1:])
            nxt += 1
        yield 0.05
    st["t0"] = None
    defaults()
    BR.hold = hold0
    bpy.types.SpaceView3D.draw_handler_remove(st["handle"], "WINDOW")
    st["handle"] = None
    json.dump({"load_start": round(load0, 1), "load_end": round(os.getloadavg()[0], 1), "steps": [list(s) for s in STEPS],
               "passes": PASSES, "lamps": len(LAMPS), "lamp_columns": ["t", "step", "hidden_lit"], "lamp_probe": st["lamps"],
               "summary": summary() if st["rows"] else None,
               "columns": ["t", "ms", "step", "agl", "alt", "rt_space", "nodes", "min_depth", "max_depth", "near_missing",
                           "holding", "lag_m", "shown_lag_m", "blending"],
               "rows": st["rows"], "swaps_columns": ["t", "changed_nodes", "nearest_changed_m", "its_depth", "pop"],
               "swaps": st["swaps"], "probe_columns": ["t", "step", "depth", "dist_m", "cell_m", "cell_px"], "probe": st["probe"]},
              open(JOB["out"], "w"))
    DN["pc_done"] = True


gen = run()


def tick():
    try:
        return next(gen)
    except StopIteration:
        return None
    except Exception:
        import traceback
        DN["pc_err"] = traceback.format_exc()
        DN["pc_done"] = True
        return None


st["handle"] = bpy.types.SpaceView3D.draw_handler_add(on_draw, (), "WINDOW", "POST_PIXEL")
bpy.app.timers.register(tick, first_interval=0.1)
