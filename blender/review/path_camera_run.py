"""The Path Camera run (docs/handover/path-camera.md, gpu-terrain.md): 3 minutes of control changes at show defaults over
every path and every target, then optionally a stretch left to Magic. In the live planet Blender with flight_rt started:
    DN["pc_job"] = {"out": "/abs/run.json", "flag": "/abs/go.flag", "passes": [...], "holes_at": [s, ...]}; exec this
    file; wait for DN["pc_done"].
A pass: {"name": str, "set": {vj_key: value}, "hold": true, "seconds": 180}. A held pass (the default) holds every
control against OSC and Art-Net (Magic, QLC+), starts from the runtime's defaults plus its set and sends the STEPS
through the bridge as a desk would: path, target and height at the listed second, /vj/blend at its default, so most
changes fly. An unheld pass ("hold": false) releases the holds and lets Magic steer for its seconds. Default: one held
"day" pass. The job writes `flag` when the first pass starts (a recorder started with --flag begins there).
Per drawn frame the log holds: t, draw interval ms, step, height over the ground (clearance map) and over the sea,
rt_space, whether a blend runs, and the flicker: the mean absolute luminance change to the Syphon frame before (0..255,
every 4th pixel) and the share of pixels that step over 16 and back over three frames. A flicker spike (a frame over
3x its step's median + 1) stands in for a pop: the GPU terrain has no detail levels to switch. Every 10th frame the
lower third's ground cell on screen (px of 1920, the GPU grid's ring cell at that distance) and the capstone lamps
that shine (energy times colour over 1 W) within LAMP_NEAR with land between (clearance map). At each of "holes_at"
(run seconds) one OpenGL render of the view with Sea_Underside pure green: the green share (holes in the land).
Writes the log and a summary per step and per pass."""
import json
import math
import os
import statistics
import time

import bpy
import numpy as np

DN = bpy.app.driver_namespace
S = bpy.context.scene
JOB = DN["pc_job"]
BR = DN["vj_osc_bridge"]
FRAME = next(h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "frame" and h.__module__ == "flight_rt")
G = FRAME.__globals__
FS, GT, fl, pc = G["_state"], G["gpu_terrain"], G["fl"], G["pc"]
RIG = S.objects[G["RIG"]]
TICK = next(h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "synthwave_tick")
# (second, path, target, height wire): every path and every target, path and target changes, height from ground to space
STEPS = ((0, "orbit", "pyramids", 0.3), (12, "orbit", "lake", 0.3), (24, "follow", "lake", 0.3), (36, "follow", "river", 0.3),
         (48, "rise", "river", 0.5), (60, "rise", "coast", 0.5), (72, "vantage", "coast", 0.5), (84, "vantage", "moon", 0.5),
         (96, "orbit", "moon", 0.7), (108, "orbit", "planet", 1.0), (120, "vantage", "planet", 1.0), (132, "vantage", "sun", 0.5),
         (144, "follow", "sun", 0.2), (156, "follow", "pyramids", 0.0), (168, "rise", "pyramids", 0.3))
PASSES = [dict({"set": {}, "hold": True, "seconds": 180.0}, **p) for p in (JOB.get("passes") or [{"name": "day"}])]
STARTS = [sum(p["seconds"] for p in PASSES[:k]) for k in range(len(PASSES))]
TOTAL = sum(p["seconds"] for p in PASSES)
LAMP_NEAR = 3000.0
LAMPS = [o for o in S.objects if o.name.startswith("Lamp_Capstone.")]
TOGGLE = 16
DN["pc_done"] = False
st = {"t0": None, "rows": [], "probe": [], "lamps": [], "flick": [], "holes": [], "last": None, "handle": None, "n": 0,
      "lum": [], "sy": -1}
DN["pc_state"] = st


def pass_of(t):
    return max(k for k in range(len(PASSES)) if STARTS[k] <= max(t, 0.0))


def step_of(t):
    k = pass_of(t)
    if not PASSES[k]["hold"]:
        return "%s" % PASSES[k]["name"]
    tt = t - STARTS[k]
    i = max(j for j, s in enumerate(STEPS) if s[0] <= max(tt, 0.0))
    return "%s %02d %s %s %.1f" % ((PASSES[k]["name"], i) + STEPS[i][1:])


def land_between(a, b, n=32):
    for k in range(1, n):
        rq = fl.sub(fl.add(a, fl.sub(b, a), k / n), fl.CENTRE)
        if fl.length(rq) - fl.R < FS["map"].ground(fl.norm(rq)):
            return True
    return False


def hidden_lamps(cam):
    return sum(1 for o in LAMPS if o.data.energy * max(o.data.color) > 1.0 and math.dist(cam, o.location) < LAMP_NEAR
               and land_between(cam, tuple(o.location)))


def ground_ray(p, f, up, lens):
    """The ground point under the lower third of the view, by marching the clearance map."""
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


def gpu_cell(dist):
    """The GPU grid's cell (m) at a horizontal distance from the camera: the ring that holds it before its blend."""
    lv = 0
    while lv < GT.LEVELS - 1 and dist > GT.MORPH[0] * GT.N / 2.0 * GT.CELL_M * (1 << lv):
        lv += 1
    return GT.CELL_M * (1 << lv)


def flicker(t):
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
        st["flick"].append((round(t, 3), step_of(t), round(float(np.abs(d1).mean()), 3), tog))


def on_draw():
    rd = bpy.context.region_data
    if rd is None or rd.view_perspective != "CAMERA" or st["t0"] is None:
        return
    now = time.perf_counter()
    t = now - st["t0"]
    if st["last"] is None or t > TOTAL:
        st["last"] = now
        return
    ms = (now - st["last"]) * 1000.0
    st["last"] = now
    st["n"] += 1
    m = RIG.matrix_world
    cam = tuple(m.translation)
    u = fl.norm(fl.sub(cam, fl.CENTRE))
    alt = fl.length(fl.sub(cam, fl.CENTRE)) - fl.R
    flicker(t)
    st["rows"].append((round(t, 3), round(ms, 2), step_of(t), round(alt - FS["map"].surface(u), 1), round(alt, 1),
                       round(S.get("rt_space", 0.0), 3), bool(S.get("rt_blending", 0.0))))
    if st["n"] % 10 == 0:
        st["lamps"].append((round(t, 3), step_of(t), hidden_lamps(cam)))
        r = m.to_3x3().normalized()
        lens = RIG.data.lens
        q, dist = ground_ray(cam, tuple(-r.col[2]), tuple(r.col[1]), lens)
        if q is not None:
            cell = gpu_cell(fl.R * fl.angle(fl.norm(fl.sub(q, fl.CENTRE)), u))
            st["probe"].append((round(t, 3), step_of(t), round(dist, 1), cell, round(cell / dist * lens / 36.0 * 1920.0, 2)))


def holes(t):
    """One OpenGL render of the view with Sea_Underside (seen only through a hole in the land) pure green."""
    ob = S.objects["Sea_Underside"]
    mod = ob.modifiers[0]
    ident = next(it.identifier for it in mod.node_group.interface.items_tree
                 if getattr(it, "in_out", "") == "INPUT" and it.name == "Material")
    sock = getattr(mod.properties.inputs, ident)
    old = sock.value
    m = bpy.data.materials.get("_hole_green") or bpy.data.materials.new("_hole_green")
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    em, out = nt.nodes.new("ShaderNodeEmission"), nt.nodes.new("ShaderNodeOutputMaterial")
    em.inputs["Color"].default_value = (0.0, 1.0, 0.0, 1.0)
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    path = os.path.join(os.path.dirname(JOB["out"]), "%s_holes_t%05.1f.png" % (os.path.splitext(os.path.basename(JOB["out"]))[0], t))
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
    st["holes"].append({"t": round(t, 1), "step": step_of(t), "green_share": round(float(green.mean()), 6), "file": path})


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else None


def stats(rows, fk, pr, lm):
    ms = [r[1] for r in rows]
    fm = [f[2] for f in fk]
    ft = [f[3] for f in fk if f[3] is not None]
    med = statistics.median(fm) if fm else 0.0
    return {"frames": len(rows), "median_ms": round(statistics.median(ms), 1) if ms else None,
            "p95_ms": round(pct(ms, 0.95), 1) if ms else None, "worst_ms": round(max(ms), 1) if ms else None,
            "flicker_mean": round(statistics.mean(fm), 3) if fm else None, "flicker_p95": round(pct(fm, 0.95), 3) if fm else None,
            "toggle_share": round(statistics.mean(ft), 5) if ft else None,
            "flicker_spikes": sum(1 for x in fm if x > 3.0 * med + 1.0),
            "blending_frames": round(sum(1 for r in rows if r[6]) / len(rows), 3) if rows else None,
            "agl_min_m": round(min(r[3] for r in rows), 1) if rows else None,
            "alt_m": [round(min(r[4] for r in rows)), round(max(r[4] for r in rows))] if rows else None,
            "cell_px_lower_third_median": round(statistics.median([p[4] for p in pr]), 2) if pr else None,
            "lamp_hidden_lit_share": round(sum(1 for x in lm if x) / len(lm), 3) if lm else None}


def summary():
    out = {}
    for name in dict.fromkeys(r[2] for r in st["rows"]):
        out[name] = stats([r for r in st["rows"] if r[2] == name], [f for f in st["flick"] if f[1] == name],
                          [p for p in st["probe"] if p[1] == name], [x[2] for x in st["lamps"] if x[1] == name])
    for ps in PASSES:
        pre = ps["name"]

        def sel(n):
            return n == pre or n.startswith(pre + " ")

        out["pass " + pre] = stats([r for r in st["rows"] if sel(r[2])], [f for f in st["flick"] if sel(f[1])],
                                   [p for p in st["probe"] if sel(p[1])], [x[2] for x in st["lamps"] if sel(x[1])])
    band = [r for r in st["rows"] if pc.BAND[0] <= r[4] <= pc.BAND[1]]
    out["band_8_12km"] = {"frames": len(band), "median_ms": round(statistics.median([r[1] for r in band]), 1) if band else None}
    return out


def defaults(extra=None):
    vals = {k: v for k, v in TICK.__globals__["DEFAULTS"].items() if k in S}
    vals.update(extra or {})
    BR.apply({"/" + k.replace("_", "/", 1): [float(v)] for k, v in vals.items()}, "path_camera_run")


def send(path, target, w):
    BR.apply({"/vj/path": [float(pc.PATHS.index(path))], "/vj/target": [float(pc.TARGETS.index(target))],
              "/vj/height": [w]}, "path_camera_run")


def start_pass(k):
    ps = PASSES[k]
    if ps["hold"]:
        BR.hold = {k_ for k_ in S.keys() if k_.startswith("vj_")}
        defaults(ps["set"])
        send(*STEPS[0][1:])
    else:
        BR.hold = set()


def run():
    load0 = os.getloadavg()[0]
    hold0 = set(BR.hold)
    try:
        start_pass(0)
        yield 5.0
        if JOB.get("flag"):
            open(JOB["flag"], "w").write("go\n")
        st["t0"] = time.perf_counter()
        k, nxt = 0, 1
        holes_at = sorted(JOB.get("holes_at", ()))
        while time.perf_counter() - st["t0"] < TOTAL + 0.2:
            el = time.perf_counter() - st["t0"]
            if k + 1 < len(PASSES) and el >= STARTS[k + 1]:
                k, nxt = k + 1, 1
                start_pass(k)
            if PASSES[k]["hold"] and nxt < len(STEPS) and el - STARTS[k] >= STEPS[nxt][0]:
                send(*STEPS[nxt][1:])
                nxt += 1
            if holes_at and el >= holes_at[0]:
                holes(holes_at.pop(0))
            yield 0.05
    finally:
        st["t0"] = None
        BR.hold = set()
        defaults()
        BR.hold = hold0
        bpy.types.SpaceView3D.draw_handler_remove(st["handle"], "WINDOW")
        st["handle"] = None
        json.dump({"load_start": round(load0, 1), "load_end": round(os.getloadavg()[0], 1), "steps": [list(s) for s in STEPS],
                   "passes": PASSES, "summary": summary() if st["rows"] else None, "holes": st["holes"],
                   "columns": ["t", "ms", "step", "agl", "alt", "rt_space", "blending"], "rows": st["rows"],
                   "flicker_columns": ["t", "step", "mean_diff", "toggle_share"], "flicker": st["flick"],
                   "probe_columns": ["t", "step", "dist_m", "cell_m", "cell_px"], "probe": st["probe"],
                   "lamp_columns": ["t", "step", "hidden_lit"], "lamp_probe": st["lamps"]}, open(JOB["out"], "w"))
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
        return None


st["handle"] = bpy.types.SpaceView3D.draw_handler_add(on_draw, (), "WINDOW", "POST_PIXEL")
bpy.app.timers.register(tick, first_interval=0.1)
