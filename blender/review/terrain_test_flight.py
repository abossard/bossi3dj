"""The terrain test flight (docs/handover/terrain-test.md): 90 s along one script, a pure function of time, flown by the
Flight shot's rig over its streamed terrain, with a per-frame log. In the live planet Blender with flight_rt started:
    DN["tt_job"] = {"out": "/abs/run.json", "flag": "/abs/go.flag"}; exec this file; wait for DN["tt_done"].
The job resets the controls to their wire defaults, cuts hard to the Flight shot, hands flight_rt the script
(driver_namespace["vj_flight_script"]: the Flight's own integrator is off while it is set), waits until the stream shows
its first view, writes `flag` (a recorder started with --flag begins there) and flies:
  skim        0-14 s   10 m over the river of CAM_1, downstream at 40 m/s
  climb      14-38 s   on along the river, up to 64 km (log height), the view turning down to the planet
  orbit      38-44 s   held at 64 km, the whole planet in frame
  cross      44-54 s   at 64 km to above the valley
  descent    54-70 s   down to 450 m over the ground beside the pyramids, the view turning onto them
  circle450  70-80 s   round the pyramids at 450 m radius, 450 m up, looking at them
  circle60   80-90 s   the same circle, down to 60 m within 4 s
Clocks run, nothing is held. Then the hook is removed and CAM_0 is cut back. Per drawn frame the log holds: t, draw
interval ms, stage, height over the ground and over the sea, rt_space, shown nodes, their depth range, near nodes still
missing, the stream holding a cut, the stream's lag (metres from the camera to where its selection was made), and
every swap of the shown set with the nearest changed node's distance and depth (a level change in the near field).
Every 10th frame: the depth of the shown node on the ground under the lower third of the view and the on-screen length
of one of its cells (px of 1920). Writes the log and a summary per stage to `out`."""
import json
import math
import os
import statistics
import time

import bpy

DN = bpy.app.driver_namespace
S = bpy.context.scene
JOB = DN["tt_job"]
BR = DN["vj_osc_bridge"]
FRAME = next(h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "frame" and h.__module__ == "flight_rt")
G = FRAME.__globals__
FS, LOD, fl = G["_state"], G["lod_scene"], G["fl"]
ls = LOD.ls
FC = next(o for o in S.objects if o.type == "CAMERA" and o.get("vj_flight_cam"))
KEY = G["SCRIPT_KEY"]
STAGES = (("skim", 0.0, 14.0), ("climb", 14.0, 38.0), ("orbit", 38.0, 44.0), ("cross", 44.0, 54.0),
          ("descent", 54.0, 70.0), ("circle450", 70.0, 80.0), ("circle60", 80.0, 90.0))
DURATION = 90.0
SKIM_SPEED, SKIM_AGL = 40.0, 10.0
CLIMB_RUN = 2400.0          # m flown on along the river while climbing
ORBIT_ALT = 64000.0
RADIUS, HIGH, LOW = 450.0, 450.0, 60.0
CIRCLE_RATE = 40.0 / RADIUS  # rad/s: 40 m/s round the circle
LENS = 24.0
FOCAL_PX = LENS / 36.0 * 1920.0
DN["tt_done"] = False


def stage_of(t):
    return next((n for n, a, b in STAGES if t < b), STAGES[-1][0])


class Path:
    """The flight as a pure function of time over the clearance map (ground: unit direction -> m over the sea)."""

    def __init__(self, ground, c1_pos, c1_fwd, target):
        self.g = ground
        self.u1 = fl.norm(fl.sub(c1_pos, fl.CENTRE))
        self.h1 = fl.tangent(self.u1, c1_fwd)
        self.uT = fl.norm(fl.sub(target, fl.CENTRE))
        self.look = fl.add(fl.CENTRE, self.uT, fl.R + ground(self.uT) + 20.0)    # the pyramids' middle
        self.uB, self.hB = fl.move(self.u1, self.h1, SKIM_SPEED * 14.0 + CLIMB_RUN)
        self.e0 = fl.tangent(self.uT, fl.sub(self.uB, self.uT))     # the circle starts on the side we come from
        self.uS = self.circle_u(0.0)

    def gs(self, fn, x, span):
        """The ground under fn(x), averaged over x - span .. x + span: no jitter from the map's texels."""
        return sum(self.g(fn(x + k * span / 2.0)) for k in (-2, -1, 0, 1, 2)) / 5.0

    def river(self, d):
        return fl.move(self.u1, self.h1, d)

    def circle_u(self, th):
        return fl.move(self.uT, fl.rot(self.uT, th, self.e0), RADIUS)[0]

    @staticmethod
    def frame(f, u, hint):
        """The camera's up: the local up, or the heading hint where the view looks straight down."""
        w = max(0.0, -fl.dot(f, u)) ** 4
        h2 = fl.norm(fl.add(fl.scale(u, 1.0 - w), hint, w))
        return fl.norm(fl.sub(h2, fl.scale(f, fl.dot(h2, f))))

    @staticmethod
    def pitched(h, u, deg):
        p = math.radians(deg)
        return fl.norm(fl.add(fl.scale(h, math.cos(p)), u, math.sin(p)))

    def pose(self, t):
        t = min(max(t, 0.0), DURATION)
        ss = fl.smootherstep
        if t < 14.0:
            u, h = self.river(SKIM_SPEED * t)
            a = self.gs(lambda x: self.river(x)[0], SKIM_SPEED * t, 40.0) + SKIM_AGL
            f = self.pitched(h, u, -2.0)
            hint = h
        elif t < 38.0:
            e = ss((t - 14.0) / 24.0)
            d = SKIM_SPEED * 14.0 + CLIMB_RUN * e
            u, h = self.river(d)
            g = self.gs(lambda x: self.river(x)[0], d, 40.0)
            a = g * (1.0 - e) + SKIM_AGL * (ORBIT_ALT / SKIM_AGL) ** e
            f = self.pitched(h, u, -2.0 - 88.0 * e ** 1.3)
            hint = h
        elif t < 44.0:
            u, a, f, hint = self.uB, ORBIT_ALT, fl.scale(self.uB, -1.0), self.hB
        elif t < 54.0:
            s = (t - 44.0) / 10.0
            u = fl.slerp(self.uB, self.uS, ss(s))
            a, f = ORBIT_ALT, fl.scale(u, -1.0)
            chord = fl.sub(self.uS, self.uB)
            hint = fl.tangent(u, fl.add(fl.scale(self.hB, 1.0 - ss(2.0 * s)), fl.norm(chord), ss(2.0 * s)))
        elif t < 70.0:
            s = (t - 54.0) / 16.0
            e = ss(s)
            u = self.uS
            g = self.gs(self.circle_u, 0.0, 0.1)
            a = g * e + HIGH * (ORBIT_ALT / HIGH) ** (1.0 - e)
            p = fl.add(fl.CENTRE, u, fl.R + a)
            f = fl.slerp(fl.scale(u, -1.0), fl.norm(fl.sub(self.look, p)), ss(e))
            chord = fl.norm(fl.sub(self.uS, self.uB))
            hint = fl.tangent(u, fl.add(fl.scale(chord, 1.0 - ss(2.0 * s)), fl.sub(self.uT, self.uS), ss(2.0 * s)))
        else:
            th = CIRCLE_RATE * (t - 70.0)
            u = self.circle_u(th)
            agl = HIGH if t < 80.0 else LOW + (HIGH - LOW) * (1.0 - ss((t - 80.0) / 4.0))
            a = self.gs(self.circle_u, th, 0.1) + agl
            p = fl.add(fl.CENTRE, u, fl.R + a)
            f = fl.norm(fl.sub(self.look, p))
            hint = fl.tangent(u, fl.sub(self.uT, u))
        p = fl.add(fl.CENTRE, u, fl.R + a)
        agl = a - self.g(u)
        props = {"fog_k": 1.0, "fog_clear": 180.0, "fog_dip": math.sqrt(2.0 * max(agl, 5.0) / fl.R)}
        return p, f, self.frame(f, u, hint), LENS, props


cam1, cam1_m = S.objects["CAM_1"], S.objects["CAM_1"].matrix_world
pyr = [o.matrix_world.translation for o in S.objects if o.name.startswith("Pyramid_") and len(o.name) == 9]
target = tuple(sum(v[k] for v in pyr) / len(pyr) for k in range(3))
PATH = Path(FS["map"].surface, tuple(cam1_m.translation), tuple(-cam1_m.to_3x3().col[2]), target)
st = {"t0": None, "rows": [], "swaps": [], "probe": [], "last": None, "nodes": None, "keys": set(), "handle": None, "n": 0}
DN["tt_state"] = st


def script():
    t = 0.0 if st["t0"] is None else time.perf_counter() - st["t0"]
    return PATH.pose(t)


def ground_ray(p, f, up):
    """The ground point under the lower third of the view (2/3 of the way down from the centre), by marching the map."""
    half = math.atan(20.25 / 2.0 / LENS)
    d = fl.norm(fl.add(f, up, -(2.0 / 3.0) * math.tan(half)))
    prev, s = 0.0, 2.0
    while s < 250000.0:
        q = fl.add(p, d, s)
        uq = fl.norm(fl.sub(q, fl.CENTRE))
        if fl.length(fl.sub(q, fl.CENTRE)) - fl.R <= FS["map"].surface(uq):
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


def on_draw():
    rd = bpy.context.region_data
    if rd is None or rd.view_perspective != "CAMERA" or st["t0"] is None:
        return
    now = time.perf_counter()
    t = now - st["t0"]
    if st["last"] is None or t > DURATION:
        st["last"] = now
        return
    ms = (now - st["last"]) * 1000.0
    st["last"] = now
    st["n"] += 1
    pose = FS.get("flight_pose")
    cam = pose[0] if pose else (0.0, 0.0, 0.0)
    u = fl.norm(fl.sub(cam, fl.CENTRE))
    alt = fl.length(fl.sub(cam, fl.CENTRE)) - fl.R
    L = LOD._state
    nodes = L.get("nodes") or {}
    if nodes is not st["nodes"]:            # a swap or a staged flip: which nodes changed, how near the nearest
        old = st["keys"]
        new = {k for v in nodes.values() for k in v}
        ch = old ^ new
        if old and ch:
            hr = L.get("hr")
            near = min(ch, key=lambda k: ls.dist_to(k, cam, hr))
            st["swaps"].append((round(t, 3), len(ch), round(ls.dist_to(near, cam, hr), 1), near[1]))
        st["nodes"], st["keys"] = nodes, new
    depths = [k[1] for k in st["keys"]]
    sel = L.get("sel_cam")
    st["rows"].append((round(t, 3), round(ms, 2), stage_of(t), round(alt - FS["map"].surface(u), 1), round(alt, 1),
                       round(S.get("rt_space", 0.0), 3), len(st["keys"]), min(depths, default=-1), max(depths, default=-1),
                       len(L.get("near_missing") or ()), bool(LOD.holding()), round(math.dist(cam, sel), 1) if sel else None))
    if st["n"] % 10 == 0 and pose:
        q, dist = ground_ray(pose[0], pose[1], pose[2])
        if q is not None:
            uq = fl.norm(fl.sub(q, fl.CENTRE))
            depth = next((d for d in range(ls.Params().d_max, -1, -1) if ls.key_at(uq, d) in st["keys"]), None)
            if depth is not None:
                cell = ls.FACE_ARC / (1 << depth) / LOD._state["params"].n
                st["probe"].append((round(t, 3), stage_of(t), depth, round(dist, 1), round(cell, 1), round(cell / dist * FOCAL_PX, 2)))


def defaults():
    for k in list(S.keys()):
        if k.startswith("vj_") and k != "vj_cam" and isinstance(S[k], (int, float)):
            d = S.id_properties_ui(k).as_dict().get("default")
            if d is not None:
                S[k] = d


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else None


def summary():
    out = {}
    for name, a, b in STAGES:
        rows = [r for r in st["rows"] if r[2] == name]
        ms = [r[1] for r in rows]
        sw = [s for s in st["swaps"] if a <= s[0] < b]
        pr = [p for p in st["probe"] if p[1] == name]
        lag = [r[11] for r in rows if r[11] is not None]
        out[name] = {"frames": len(rows), "median_ms": round(statistics.median(ms), 1) if ms else None,
                     "p95_ms": round(pct(ms, 0.95), 1) if ms else None, "worst_ms": round(max(ms), 1) if ms else None,
                     "over_33ms": round(sum(1 for x in ms if x > 33.3) / len(ms), 3) if ms else None,
                     "swaps": len(sw), "near_level_changes_1500m": sum(1 for s in sw if s[2] < 1500.0),
                     "near_level_changes_300m": sum(1 for s in sw if s[2] < 300.0),
                     "edge_px_lower_third_median": round(statistics.median([p[5] for p in pr]), 2) if pr else None,
                     "lower_third_depth_median": statistics.median([p[2] for p in pr]) if pr else None,
                     "lower_third_dist_median_m": round(statistics.median([p[3] for p in pr])) if pr else None,
                     "lag_m_median": round(statistics.median(lag), 1) if lag else None, "lag_m_max": round(max(lag), 1) if lag else None,
                     "near_missing_frames": round(sum(1 for r in rows if r[9] > 0) / len(rows), 3) if rows else None,
                     "holding_frames": sum(1 for r in rows if r[10]),
                     "alt_m": [round(min(r[4] for r in rows)), round(max(r[4] for r in rows))] if rows else None,
                     "agl_min_m": round(min(r[3] for r in rows), 1) if rows else None,
                     "nodes_median": statistics.median([r[6] for r in rows]) if rows else None,
                     "max_depth_median": statistics.median([r[8] for r in rows]) if rows else None}
    band = [r for r in st["rows"] if 8000.0 <= r[4] <= 12000.0]       # build_planet GLOBE_BAND: the globe takes over
    out["globe_band_8_12km"] = {"frames": len(band), "t": [[r[0] for r in band][:1], [r[0] for r in band][-1:]],
                                "median_ms": round(statistics.median([r[1] for r in band]), 1) if band else None,
                                "worst_ms": round(max(r[1] for r in band), 1) if band else None,
                                "nodes": [min((r[6] for r in band), default=None), max((r[6] for r in band), default=None)],
                                "max_depth": [min((r[8] for r in band), default=None), max((r[8] for r in band), default=None)],
                                "swaps": sum(1 for s in st["swaps"] if any(abs(s[0] - r[0]) < 1e-6 for r in band))}
    return out


def run():
    load0 = os.getloadavg()[0]
    BR.hold = set()
    defaults()
    DN[KEY] = script
    BR.apply({"/vj/blend": [0.0], "/vj/flight": [0.0], "/vj/cam": [float(FC.name[4:])]}, "terrain_test")
    t = time.perf_counter()
    while time.perf_counter() - t < 60.0 and not (FS.get("stream") and LOD.live() and not LOD.holding()):
        yield 0.2
    yield 3.0
    if JOB.get("flag"):
        open(JOB["flag"], "w").write("go\n")
    st["t0"] = time.perf_counter()
    while time.perf_counter() - st["t0"] < DURATION + 0.2:
        yield 0.25
    DN.pop(KEY, None)
    BR.apply({"/vj/cam": [0.0]}, "terrain_test")
    defaults()
    bpy.types.SpaceView3D.draw_handler_remove(st["handle"], "WINDOW")
    st["handle"] = None
    json.dump({"load_start": round(load0, 1), "load_end": round(os.getloadavg()[0], 1), "stages": [list(s) for s in STAGES],
               "summary": summary(),
               "columns": ["t", "ms", "stage", "agl", "alt", "rt_space", "nodes", "min_depth", "max_depth", "near_missing",
                           "holding", "lag_m"],
               "rows": st["rows"], "swaps_columns": ["t", "changed_nodes", "nearest_changed_m", "its_depth"],
               "swaps": st["swaps"], "probe_columns": ["t", "stage", "depth", "dist_m", "cell_m", "cell_px"], "probe": st["probe"]},
              open(JOB["out"], "w"))
    DN["tt_done"] = True


gen = run()


def tick():
    try:
        return next(gen)
    except StopIteration:
        return None
    except Exception:
        import traceback
        DN["tt_err"] = traceback.format_exc()
        DN.pop(KEY, None)
        DN["tt_done"] = True
        return None


st["handle"] = bpy.types.SpaceView3D.draw_handler_add(on_draw, (), "WINDOW", "POST_PIXEL")
bpy.app.timers.register(tick, first_interval=0.1)
