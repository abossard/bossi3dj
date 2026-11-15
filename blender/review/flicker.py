"""Flicker numbers of the live planet output: how much consecutive Syphon frames change, and how many pixels strobe.
In the live planet Blender:
    DN["fl_job"] = {"out": "/abs/flicker.json", "cases": [...], "frames": 90, "settle": 4.0}; exec this file;
    wait for DN["fl_done"].
A case: {"name": str, "set": {vj_key: value}, "pulse": bool, "hold": bool, "noise": float, "normal": "true"}.
"noise" scales the GPU terrain's near detail (1 as built, 0 none); "normal": "true" shades the land with the displaced
triangles' own normals instead of the map's slope; "energy": {NAME: value} overrides energy.py's constants (the beat
accent); all are undone after the case.
A case with "log": true also returns one row per pair of frames: t (s from the case's first frame), the camera's
altitude (m), the mean difference over the whole frame and over its top, middle and bottom thirds, the toggle share
and the A/B side.
An A/B case adds "alt": {"every": frames, "a": probe, "b": probe}; a probe is {"noise": float, "pulse": bool,
"edges": pyramid_edges variant, "r17": round17_probes flags (exec that file first), "energy": {NAME: value}, "scene": {prop: value} written straight to the scene, back to the case's after}. The case's frames switch between a and b every "every" frames on the same flight, so
both see the same seconds; the first 2 frames after a switch are not counted. Its row has the numbers per side. Every case starts from the show defaults
(the runtime's DEFAULTS) with the clocks running; "set" overrides them. "hold" (default true) holds every vj_ control
against OSC and Art-Net (Magic, QLC+), false leaves them to Magic. "pulse" false keeps the runtime's idle pulse at 0
(rt_beat from vj_beat only) by resetting its idle timer before each frame. After "settle" s, "frames" consecutive new
Syphon frames are read (luminance, 1920x1080).
Per case: per pair of frames the mean absolute luminance difference (0..255), its mean and 95th percentile over the
case; the toggle share: pixels that move by more than TOGGLE one way and then back the other way over three frames
(a strobe, not a motion), mean over the case; the draw interval. Load and fps_trustworthy are the
caller's (make status).
"""
import json
import os
import sys
import time

import bpy
import numpy as np

DN = bpy.app.driver_namespace
S = bpy.context.scene
JOB = DN["fl_job"]
BR = DN["vj_osc_bridge"]
TOGGLE = 16                 # of 255: a pixel's step up or down that counts toward a toggle
TICK = next(h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "synthwave_tick")
RT_G = TICK.__globals__
FR = next((h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "frame"), None)
FL = FR.__globals__.get("fl") if FR else None
DN["fl_done"] = False
st = {"want": False, "got": [], "n": 0, "last": -1, "pulse": True, "t": [], "alt": None, "scene0": {}, "energy0": {}, "log": None,
      "prev": None, "t0": 0.0}
SKIP = 2                    # frames after an A/B switch that are not counted
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else DN.get("pe_here", "")


def no_pulse(scene, depsgraph=None):
    if not st["pulse"]:
        RT_G["_state"]["changed"] = time.perf_counter()
        RT_G["_state"]["idle"] = 0.0


def probe(p):
    """Applies an A/B side: near-detail scale, idle pulse, pyramid edges."""
    for n, v in st["amps"]:
        n.inputs[1].default_value = v * p.get("noise", 1.0)
    st["pulse"] = p.get("pulse", True)
    E = sys.modules["energy"]
    for k, v in p.get("energy", {}).items():
        st["energy0"].setdefault(k, getattr(E, k))
        setattr(E, k, v)
    for k in [k for k in st["energy0"] if k not in p.get("energy", {})]:
        setattr(E, k, st["energy0"].pop(k))
    for k, v in p.get("scene", {}).items():
        st["scene0"].setdefault(k, S[k])
        S[k] = v
    for k in [k for k in st["scene0"] if k not in p.get("scene", {})]:
        S[k] = st["scene0"].pop(k)
    if "r17" in p or st.get("r17_used"):      # round17_probes.py
        st["r17_used"] = True
        DN["r17_apply"](p.get("r17", {}))
    if "edges" in p or st.get("pe_used"):
        st["pe_used"] = True
        st["pe"](p.get("edges", {}))


def alt_switch(scene, depsgraph=None):
    A = st["alt"]
    if A is None or not st["want"]:
        return
    A["k"] += 1
    if A["k"] % A["every"] == 0:
        A["tag"] = "b" if A["tag"] == "a" else "a"
        A["since"] = 0
        probe(A[A["tag"]])


def altitude():
    if FL is None or S.camera is None:
        return None
    return round(FL.length(FL.sub(tuple(S.camera.matrix_world.translation), FL.CENTRE)) - FL.R, 1)


def log_row(d, prev_d, tag):
    h = d.shape[0] // 3
    a = np.abs(d)
    tog = None if prev_d is None else float(((prev_d > TOGGLE) & (d < -TOGGLE) | (prev_d < -TOGGLE) & (d > TOGGLE)).mean())
    st["log"].append([round(time.perf_counter() - st["t0"], 3), altitude(), round(float(a.mean()), 3),
                      round(float(a[:h].mean()), 3), round(float(a[h:2 * h].mean()), 3), round(float(a[2 * h:].mean()), 3),
                      None if tog is None else round(tog, 5), tag])


def alt_frame(lum):
    A = st["alt"]
    A["since"] += 1
    if A["since"] <= SKIP:
        A["prev"] = None
        return
    f, acc, p = lum.astype(np.int16), A["acc"][A["tag"]], A["prev"]
    d = None
    if p is not None:
        d = f - p[0]
        acc["mad"].append(float(np.abs(d).mean()))
        if st["log"] is not None:
            log_row(d, p[1], A["tag"])
        if p[1] is not None:
            acc["tog"].append(float(((p[1] > TOGGLE) & (d < -TOGGLE) | (p[1] < -TOGGLE) & (d > TOGGLE)).mean()))
    A["prev"] = (f, d)
    st["n"] += 1


def draw():
    s = DN.get("syphon_out")
    if not st["want"] or s is None or s.offscreen is None or s.frames == st["last"]:
        return
    st["last"] = s.frames
    a = np.asarray(s.offscreen.texture_color.read())
    if a.dtype != np.uint8:
        a = np.clip(a * 255.0, 0, 255).astype(np.uint8)
    lum = (a[..., 0].astype(np.uint16) * 54 + a[..., 1].astype(np.uint16) * 183 + a[..., 2].astype(np.uint16) * 19) >> 8
    if st["alt"] is not None:
        alt_frame(lum)
        return
    if st["log"] is not None:
        f = lum.astype(np.int16)
        if st["prev"] is not None:
            d = f - st["prev"][0]
            log_row(d, st["prev"][1], None)
            st["prev"] = (f, d)
        else:
            st["prev"] = (f, None)
        st["n"] += 1
        return
    st["got"].append(lum.astype(np.uint8))
    st["t"].append(time.perf_counter())


def numbers(frames, ts):
    f = [x.astype(np.int16) for x in frames]
    d = [f[i + 1] - f[i] for i in range(len(f) - 1)]
    mad = [float(np.abs(x).mean()) for x in d]
    tog = [float(((d[i] > TOGGLE) & (d[i + 1] < -TOGGLE) | (d[i] < -TOGGLE) & (d[i + 1] > TOGGLE)).mean())
           for i in range(len(d) - 1)]
    iv = [(ts[i + 1] - ts[i]) * 1000.0 for i in range(len(ts) - 1)]
    return {"pairs": len(d), "mad_mean": round(float(np.mean(mad)), 3), "mad_p95": round(float(np.percentile(mad, 95)), 3),
            "toggle_share": round(float(np.mean(tog)), 5), "toggle_p95": round(float(np.percentile(tog, 95)), 5),
            "draw_ms_median": round(float(np.median(iv)), 1)}


def apply(values):
    BR.apply({"/" + k.replace("_", "/", 1): [float(v)] for k, v in values.items()}, "flicker")


def terrain(case):
    """Applies the case's terrain probes; returns the undo."""
    nt = bpy.data.materials["Terrain GPU"].node_tree
    amps = [(n, n.inputs[1].default_value) for n in nt.nodes if n.label == "gt_noise_amp"]
    for n, v in amps:
        n.inputs[1].default_value = v * case.get("noise", 1.0)
    moved = []
    if case.get("normal") == "true":
        geo = next(n for n in nt.nodes if n.type == "NEW_GEOMETRY")
        for lk in list(nt.links):
            if lk.to_socket.name == "Normal" and lk.from_node.type == "VECT_MATH":
                moved.append((lk.from_socket, lk.to_socket))
                nt.links.remove(lk)
                nt.links.new(geo.outputs["True Normal"], moved[-1][1])

    E = sys.modules["energy"]
    e0 = {k: getattr(E, k) for k in case.get("energy", {})}
    for k, v in case.get("energy", {}).items():
        setattr(E, k, v)

    def undo():
        for k, v in e0.items():
            setattr(E, k, v)
        for n, v in amps:
            n.inputs[1].default_value = v
        for src, to in moved:
            for lk in list(to.links):
                nt.links.remove(lk)
            nt.links.new(src, to)
    return undo


def run():
    hold0 = set(BR.hold)
    defaults = {k: v for k, v in RT_G["DEFAULTS"].items() if k in S}
    rows = []
    try:
        for case in JOB["cases"]:
            BR.hold = {k for k in S.keys() if k.startswith("vj_")} if case.get("hold", True) else set()
            st["pulse"] = case.get("pulse", True)
            if case.get("hold", True):
                vals = dict(defaults)
                vals.update(case.get("set", {}))
                apply(vals)
            undo = terrain(case)
            t = time.perf_counter()
            while time.perf_counter() - t < JOB.get("settle", 4.0):
                yield 0.1
            st["log"] = [] if case.get("log") else None
            st["prev"], st["t0"] = None, time.perf_counter()
            if case.get("log") and "alt" not in case:
                st["n"], st["want"] = 0, True
                while st["n"] < JOB.get("frames", 90):
                    yield 0.005
                st["want"] = False
                undo()
                L = st["log"]
                st["log"] = None
                m = [r[2] for r in L]
                rows.append({"case": case, "load": round(os.getloadavg()[0], 1), "mad_mean": round(float(np.mean(m)), 3),
                             "mad_p95": round(float(np.percentile(m, 95)), 3),
                             "log_columns": ["t", "alt", "mad", "top", "mid", "bottom", "toggle", "side"], "log": L})
                continue
            if "alt" in case:
                al = case["alt"]
                st["alt"] = {"every": al.get("every", 8), "a": al.get("a", {}), "b": al.get("b", {}), "k": 0, "tag": "a",
                             "since": 0, "prev": None, "acc": {"a": {"mad": [], "tog": []}, "b": {"mad": [], "tog": []}}}
                st["n"] = 0
                probe(st["alt"]["a"])
                st["want"] = True
                while st["n"] < JOB.get("frames", 90):
                    yield 0.005
                st["want"] = False
                probe({})
                acc = st["alt"]["acc"]
                st["alt"] = None
                undo()
                row = {"case": case, "load": round(os.getloadavg()[0], 1)}
                if st["log"] is not None:
                    row["log_columns"] = ["t", "alt", "mad", "top", "mid", "bottom", "toggle", "side"]
                    row["log"], st["log"] = st["log"], None
                for k in "ab":
                    row[k] = {"pairs": len(acc[k]["mad"]), "mad_mean": round(float(np.mean(acc[k]["mad"])), 3),
                              "toggle_share": round(float(np.mean(acc[k]["tog"])), 5)}
                rows.append(row)
                continue
            st["got"], st["t"], st["want"] = [], [], True
            while len(st["got"]) < JOB.get("frames", 90):
                yield 0.005
            st["want"] = False
            undo()
            row = {"case": case, "load": round(os.getloadavg()[0], 1)}
            row.update(numbers(st["got"], st["t"]))
            rows.append(row)
            st["got"] = []
    finally:
        st["want"], st["pulse"] = False, True
        BR.hold = set()
        apply(defaults)
        BR.hold = hold0
        bpy.types.SpaceView3D.draw_handler_remove(st["handle"], "WINDOW")
        for h in (no_pulse, alt_switch):
            if h in bpy.app.handlers.frame_change_pre:
                bpy.app.handlers.frame_change_pre.remove(h)
        json.dump(rows, open(JOB["out"], "w"), indent=1)
        DN["fl_done"] = True


gen = run()


def tick():
    try:
        return next(gen)
    except StopIteration:
        return None
    except Exception:
        import traceback
        DN["fl_err"] = traceback.format_exc()
        DN["fl_done"] = True
        return None


st["amps"] = [(n, n.inputs[1].default_value) for n in bpy.data.materials["Terrain GPU"].node_tree.nodes
              if n.label == "gt_noise_amp"]
if any("alt" in c for c in JOB["cases"]):
    _pe = {"__name__": "pe", "__file__": os.path.join(HERE, "pyramid_edges.py")}
    DN["pe_variant"] = {}
    exec(compile(open(_pe["__file__"]).read(), _pe["__file__"], "exec"), _pe)
    st["pe"] = _pe["apply"]
bpy.app.handlers.frame_change_pre.insert(0, no_pulse)
bpy.app.handlers.frame_change_pre.insert(0, alt_switch)
st["handle"] = bpy.types.SpaceView3D.draw_handler_add(draw, (), "WINDOW", "POST_PIXEL")
bpy.app.timers.register(tick, first_interval=0.1)
