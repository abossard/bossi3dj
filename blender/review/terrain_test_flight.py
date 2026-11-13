"""The terrain test flight (docs/handover/terrain-test.md, gpu-terrain.md): 90 s along one script, a pure function of
time, flown by the On-Air Camera (CAM_RIG) over the terrain, with a per-frame log. In the live planet Blender with
flight_rt started:
    DN["tt_job"] = {"out": "/abs/run.json", "flag": "/abs/go.flag", "terrain": "stream" | "gpu"}; exec this file;
    wait for DN["tt_done"].
The job holds every control at the runtime's defaults against OSC and Art-Net (Magic, QLC+), puts the terrain asked
for on air (gpu: gpu_terrain.switch, loaded in driver_namespace["gpu_terrain"]), replaces the Path Camera's step with
the script, waits until the terrain shows its first view, writes `flag` (a recorder started with --flag begins there)
and flies:
  skim        0-14 s   10 m over the ground from the river target (PathTarget.river) toward the pyramids at 40 m/s
  climb      14-38 s   on along the river, up to 64 km (log height), the view turning down to the planet
  orbit      38-44 s   held at 64 km, the whole planet in frame
  cross      44-54 s   at 64 km to above the valley
  descent    54-70 s   down to 450 m over the ground beside the pyramids, the view turning onto them
  circle450  70-80 s   round the pyramids at 450 m radius, 450 m up, looking at them
  circle60   80-90 s   the same circle, down to 60 m within 4 s
Clocks run. Then the Path Camera, the stream and the holds are put back. Per drawn frame the log holds: t, draw
interval ms, stage, height over the ground and over the sea, rt_space, shown nodes, their depth range, near nodes still
missing, the stream holding a cut, the stream's lag (metres from the camera to where its selection was made), and
every swap of the shown set with the nearest changed node's distance and depth (a level change in the near field).
Every 10th frame: the depth of the shown node on the ground under the lower third of the view and the on-screen length
of one of its cells (px of 1920; on the GPU grid, the ring's cell at that distance). Per drawn frame also the flicker:
the mean absolute luminance difference to the frame before (0..255, every 4th pixel of the Syphon output) and the share
of pixels that step over 16 and back over three frames. Writes the log and a summary per stage to `out`."""
import json
import math
import os
import statistics
import time

import bpy
import numpy as np

DN = bpy.app.driver_namespace
S = bpy.context.scene
JOB = DN["tt_job"]
BR = DN["vj_osc_bridge"]
FRAME = next(h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "frame" and h.__module__ == "flight_rt")
G = FRAME.__globals__
FS, LOD, fl = G["_state"], G["lod_scene"], G["fl"]
ls = LOD.ls
RIG = S.objects[G["RIG"]]
GT = DN.get("gpu_terrain")
GPU = JOB.get("terrain", "stream") == "gpu"
TOGGLE = 16
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

    def gs(self, fn, x, back, ahead, n=8):
        """The highest ground under fn over x - back .. x + ahead (x itself included): the height never dips under the
        ground below the camera, and rises before a slope ahead."""
        return max(self.g(fn(x + back * (k / n - 1.0) if k <= n else x + ahead * (k - n) / n)) for k in range(2 * n + 1))

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
            a = self.gs(lambda x: self.river(x)[0], SKIM_SPEED * t, 20.0, 80.0) + SKIM_AGL
            f = self.pitched(h, u, -2.0)
            hint = h
        elif t < 38.0:
            e = ss((t - 14.0) / 24.0)
            d = SKIM_SPEED * 14.0 + CLIMB_RUN * e
            u, h = self.river(d)
            g = self.gs(lambda x: self.river(x)[0], d, 20.0, 80.0)
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
            g = self.gs(self.circle_u, 0.0, 0.1, 0.1)
            a = g * e + HIGH * (ORBIT_ALT / HIGH) ** (1.0 - e)
            p = fl.add(fl.CENTRE, u, fl.R + a)
            f = fl.slerp(fl.scale(u, -1.0), fl.norm(fl.sub(self.look, p)), ss(e))
            chord = fl.norm(fl.sub(self.uS, self.uB))
            hint = fl.tangent(u, fl.add(fl.scale(chord, 1.0 - ss(2.0 * s)), fl.sub(self.uT, self.uS), ss(2.0 * s)))
        else:
            th = CIRCLE_RATE * (t - 70.0)
            u = self.circle_u(th)
            agl = HIGH if t < 80.0 else LOW + (HIGH - LOW) * (1.0 - ss((t - 80.0) / 4.0))
            a = self.gs(self.circle_u, th, 0.1, 0.2) + agl
            p = fl.add(fl.CENTRE, u, fl.R + a)
            f = fl.norm(fl.sub(self.look, p))
            hint = fl.tangent(u, fl.sub(self.uT, u))
        p = fl.add(fl.CENTRE, u, fl.R + a)
        agl = a - self.g(u)
        props = {"fog_k": 1.0, "fog_clear": 180.0, "fog_dip": math.sqrt(2.0 * max(agl, 5.0) / fl.R)}
        return p, f, self.frame(f, u, hint), LENS, props


pyr = [o.matrix_world.translation for o in S.objects if o.name.startswith("Pyramid_") and len(o.name) == 9]
target = tuple(sum(v[k] for v in pyr) / len(pyr) for k in range(3))
river = tuple(S.objects["PathTarget.river"].matrix_world.translation)
PATH = Path(FS["map"].surface, river, fl.sub(target, river), target)
st = {"t0": None, "rows": [], "swaps": [], "probe": [], "last": None, "nodes": None, "keys": set(), "handle": None, "n": 0,
      "lum": [], "flick": [], "sy": -1}
DN["tt_state"] = st


def script():
    if st.get("hold_t") is not None:
        return PATH.pose(st["hold_t"])
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


def pop(ch, cam):
    """How far from its parent's lattice the finer side of a level change is drawn when it changes: 1 - the morph
    factor of its vertex nearest the camera (0: the change is invisible, the vertices sit on the coarse surface).
    The finer side is a changed node whose parent changed too (a split adds it, a merge removes it); the four
    nearest by bounds are checked on their 9 x 9 lattice, heights from the clearance map."""
    p = LOD._state["params"]
    fine = [k for k in ch if k[1] and (k[0], k[1] - 1, k[2] >> 1, k[3] >> 1) in ch]
    hr = LOD._state.get("hr")
    worst = 0.0
    for k in sorted(fine, key=lambda k: ls.dist_to(k, cam, hr))[:4]:
        dmin = min(math.dist(cam, fl.add(fl.CENTRE, u, fl.R + FS["map"].ground(u)))
                   for u in (ls.node_dir(k, x, y, p.n) for x in range(p.n + 1) for y in range(p.n + 1)))
        worst = max(worst, 1.0 - ls.morph_factor(dmin, k[1], p))
    return worst


def flicker(t):
    """The Syphon output's change against the frame before (every 4th pixel), once per new Syphon frame."""
    s = DN.get("syphon_out")
    if s is None or s.offscreen is None or s.frames == st["sy"]:
        return
    st["sy"] = s.frames
    a = np.asarray(s.offscreen.texture_color.read())[::4, ::4, :3]
    if a.dtype != np.uint8:
        a = np.clip(a * 255.0, 0, 255).astype(np.uint8)
    lum = (a[..., 0].astype(np.int16) * 54 + a[..., 1].astype(np.int16) * 183 + a[..., 2].astype(np.int16) * 19) >> 8
    st["lum"] = (st["lum"] + [lum])[-3:]
    if len(st["lum"]) >= 2:
        d1 = st["lum"][-1] - st["lum"][-2]
        tog = None
        if len(st["lum"]) == 3:
            d0 = st["lum"][-2] - st["lum"][-3]
            tog = float(((d0 > TOGGLE) & (d1 < -TOGGLE) | (d0 < -TOGGLE) & (d1 > TOGGLE)).mean())
        st["flick"].append((round(t, 3), stage_of(t), round(float(np.abs(d1).mean()), 3), tog))


def gpu_cell(dist):
    """The GPU grid's cell (m) at a horizontal distance from the camera: the ring that holds it before its blend."""
    lv = 0
    while lv < GT.LEVELS - 1 and dist > GT.MORPH[0] * GT.N / 2.0 * GT.CELL_M * (1 << lv):
        lv += 1
    return GT.CELL_M * (1 << lv), lv


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
    M = RIG.matrix_world
    pose = (tuple(M.translation), tuple(-M.col[2].xyz), tuple(M.col[1].xyz))
    cam = pose[0]
    flicker(t)
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
            st["swaps"].append((round(t, 3), len(ch), round(ls.dist_to(near, cam, hr), 1), near[1], round(pop(ch, cam), 3)))
        st["nodes"], st["keys"] = nodes, new
    depths = [k[1] for k in st["keys"]]
    sel, shown = L.get("sel_cam"), L.get("shown_cam")
    st["rows"].append((round(t, 3), round(ms, 2), stage_of(t), round(alt - FS["map"].surface(u), 1), round(alt, 1),
                       round(S.get("rt_space", 0.0), 3), len(st["keys"]), min(depths, default=-1), max(depths, default=-1),
                       len(L.get("near_missing") or ()), bool(LOD.holding()), round(math.dist(cam, sel), 1) if sel else None,
                       round(math.dist(cam, shown), 1) if shown else None))
    if st["n"] % 10 == 0 and pose:
        q, dist = ground_ray(pose[0], pose[1], pose[2])
        if q is not None and GPU:
            cell, lv = gpu_cell(fl.R * fl.angle(fl.norm(fl.sub(q, fl.CENTRE)), u))
            st["probe"].append((round(t, 3), stage_of(t), lv, round(dist, 1), round(cell, 1), round(cell / dist * FOCAL_PX, 2)))
        elif q is not None:
            uq = fl.norm(fl.sub(q, fl.CENTRE))
            depth = next((d for d in range(LOD._state["params"].d_max, -1, -1) if ls.key_at(uq, d) in st["keys"]), None)
            if depth is not None:
                cell = ls.FACE_ARC / (1 << depth) / LOD._state["params"].n
                st["probe"].append((round(t, 3), stage_of(t), depth, round(dist, 1), round(cell, 1), round(cell / dist * FOCAL_PX, 2)))


TICK = next(h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "synthwave_tick")


def defaults():
    vals = {k: v for k, v in TICK.__globals__["DEFAULTS"].items() if k in S}
    BR.apply({"/" + k.replace("_", "/", 1): [float(v)] for k, v in vals.items()}, "terrain_test")


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
        slag = [r[12] for r in rows if r[12] is not None]
        pops = [s[4] for s in sw]
        fk = [f for f in st["flick"] if f[1] == name]
        fm = [f[2] for f in fk]
        ft = [f[3] for f in fk if f[3] is not None]
        out[name] = {"frames": len(rows), "median_ms": round(statistics.median(ms), 1) if ms else None,
                     "p95_ms": round(pct(ms, 0.95), 1) if ms else None, "worst_ms": round(max(ms), 1) if ms else None,
                     "over_33ms": round(sum(1 for x in ms if x > 33.3) / len(ms), 3) if ms else None,
                     "swaps": len(sw), "near_level_changes_1500m": sum(1 for s in sw if s[2] < 1500.0),
                     "near_level_changes_300m": sum(1 for s in sw if s[2] < 300.0),
                     "edge_px_lower_third_median": round(statistics.median([p[5] for p in pr]), 2) if pr else None,
                     "lower_third_depth_median": statistics.median([p[2] for p in pr]) if pr else None,
                     "lower_third_dist_median_m": round(statistics.median([p[3] for p in pr])) if pr else None,
                     "lag_m_median": round(statistics.median(lag), 1) if lag else None, "lag_m_max": round(max(lag), 1) if lag else None,
                     "shown_lag_m_median": round(statistics.median(slag), 1) if slag else None,
                     "shown_lag_m_p95": round(pct(slag, 0.95), 1) if slag else None,
                     "shown_lag_m_max": round(max(slag), 1) if slag else None,
                     "pops_over_0.05": sum(1 for x in pops if x > 0.05), "pop_max": max(pops, default=None),
                     "flicker_mean": round(statistics.mean(fm), 3) if fm else None,
                     "flicker_p95": round(pct(fm, 0.95), 3) if fm else None,
                     "flicker_spikes": sum(1 for x in fm if fm and x > 3.0 * statistics.median(fm) + 1.0),
                     "toggle_share": round(statistics.mean(ft), 5) if ft else None,
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


def overrides():
    """JOB "lod": lod_stream.Params fields, JOB "consts": lod_scene module constants; returns how to undo them."""
    p, undo = LOD._state["params"], []
    for k, v in (JOB.get("lod") or {}).items():
        undo.append((p, k, getattr(p, k)))
        setattr(p, k, v)
    for k, v in (JOB.get("consts") or {}).items():
        undo.append((LOD, k, getattr(LOD, k)))
        setattr(LOD, k, v)
    return undo


def settled():
    L = LOD._state
    return GPU or (LOD.live() and not LOD.holding() and L.get("want") is None and not L.get("near_missing"))


def holes(t):
    """The view at script time t held until its terrain is settled, then one OpenGL render of the camera view into a
    file with Sea_Underside (seen only through a hole in the land) as pure green emission; the green share counted.
    The render is off the Syphon output but the swapped material is drawn there for about one frame."""
    st["hold_t"] = t
    t1 = time.perf_counter()
    while time.perf_counter() - t1 < 30.0 and not settled():
        yield 0.2
    yield 1.5
    ob = S.objects["Sea_Underside"]
    mod = ob.modifiers[0]
    ident = next(it.identifier for it in mod.node_group.interface.items_tree
                 if getattr(it, "in_out", "") == "INPUT" and it.name == "Material")
    sock = getattr(mod.properties.inputs, ident)
    old = sock.value
    m = bpy.data.materials.get("_hole_green") or bpy.data.materials.new("_hole_green")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    em, out = nt.nodes.new("ShaderNodeEmission"), nt.nodes.new("ShaderNodeOutputMaterial")
    em.inputs["Color"].default_value = (0.0, 1.0, 0.0, 1.0)
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    path = os.path.join(os.path.dirname(JOB["out"]), "%s_holes_t%04.1f.png" % (JOB.get("name", "run"), t))
    fp, ff = S.render.filepath, S.render.image_settings.file_format
    S.render.filepath, S.render.image_settings.file_format = path, "PNG"
    try:
        sock.value = m
        ob.update_tag()
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                if area.type == "VIEW_3D":
                    with bpy.context.temp_override(window=win, area=area):
                        bpy.ops.render.opengl(write_still=True, view_context=True)
                    break
    finally:
        sock.value = old
        ob.update_tag()
        S.render.filepath, S.render.image_settings.file_format = fp, ff
    import numpy as np
    img = bpy.data.images.load(path)
    a = np.empty(len(img.pixels), np.float32)
    img.pixels.foreach_get(a)
    a = a.reshape(-1, 4)
    green = (a[:, 1] > 0.8) & (a[:, 0] < 0.25) & (a[:, 2] < 0.25)
    st.setdefault("holes", []).append({"t": t, "stage": stage_of(t), "green_px": int(green.sum()),
                                       "green_share": round(float(green.mean()), 6), "file": path,
                                       "settled": bool(settled())})
    bpy.data.images.remove(img)
    st["hold_t"] = None


def put_back():
    P = FS.get("path")
    if P is not None and "step" in P.__dict__:
        del P.step
    if GPU and GT is not None:
        GT.switch(False)
    BR.hold = st.get("hold0", set())


def run():
    load0 = os.getloadavg()[0]
    st["hold0"] = set(BR.hold)
    BR.hold = {k for k in S.keys() if k.startswith("vj_")}
    defaults()
    BR.apply({"/vj/blend": [0.0]}, "terrain_test")
    undo = st["undo"] = overrides()
    if GPU:
        GT.switch(True)
    FS["path"].step = lambda *a, **k: script()       # the Path Camera's pose is the script's
    t = time.perf_counter()
    while time.perf_counter() - t < 60.0 and not (GPU or (LOD.live() and not LOD.holding())):
        yield 0.2
    yield 3.0
    if JOB.get("flag"):
        open(JOB["flag"], "w").write("go\n")
    if JOB.get("fly", True):
        st["t0"] = time.perf_counter()
        while time.perf_counter() - st["t0"] < DURATION + 0.2:
            yield 0.25
    st["t0"] = None
    for t in JOB.get("holes_at", ()):
        yield from holes(t)
    for o, k, v in undo:
        setattr(o, k, v)
    put_back()
    bpy.types.SpaceView3D.draw_handler_remove(st["handle"], "WINDOW")
    st["handle"] = None
    json.dump({"load_start": round(load0, 1), "load_end": round(os.getloadavg()[0], 1), "stages": [list(s) for s in STAGES],
               "job": {k: v for k, v in JOB.items() if k not in ("out", "flag")},
               "summary": summary() if st["rows"] else None, "holes": st.get("holes"),
               "columns": ["t", "ms", "stage", "agl", "alt", "rt_space", "nodes", "min_depth", "max_depth", "near_missing",
                           "holding", "lag_m", "shown_lag_m"],
               "flicker_columns": ["t", "stage", "mean_diff", "toggle_share"], "flicker": st["flick"],
               "rows": st["rows"], "swaps_columns": ["t", "changed_nodes", "nearest_changed_m", "its_depth", "pop"],
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
        st["hold_t"] = None
        put_back()
        for o, k, v in st.get("undo") or ():
            setattr(o, k, v)
        DN["tt_done"] = True
        return None


st["handle"] = bpy.types.SpaceView3D.draw_handler_add(on_draw, (), "WINDOW", "POST_PIXEL")
bpy.app.timers.register(tick, first_interval=0.1)
