"""The Flight shot by numbers, in the live planet Blender with flight_rt started (clocks running, nothing frozen):
    DN["flight_job"] = {"out": "/abs/flight.json", "seed": 1, "dwell": 10}; exec this file; wait for DN["flight_done"].
Sequence: CAM_0 for `dwell` s (the fixed shot of the same run); a hard cut (/vj/blend 0) into the Flight shot, its
Flight reset on `seed`; /vj/flight 0, 1/3, 2/3, 1 (Orbit, Approach, Skim, Hover), each held until that stage is in
effect for 3 s (the Hover: fe at 1, the camera on its water loop), then `dwell` s recorded; a hard cut out to CAM_0,
then CAM_0 again for `dwell` s. Every drawn frame logs:
  t, ms (draw interval), label, stage, f, fe, height over the ground (m), stream live, holding a cut,
  near blocks still missing, blocks wanted but not shown (near ones: a hole), blocks shown.
Summary per label: median and 95th percentile of ms, the worst frame, frames with a hole, the cut stalls."""
import json
import statistics
import time

import bpy

DN = bpy.app.driver_namespace
S = bpy.context.scene
JOB = DN["flight_job"]
BRIDGE = DN["vj_osc_bridge"]
FRAME = next(h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "frame" and h.__module__ == "flight_rt")
G = FRAME.__globals__
FS, fl, dr, LOD = G["_state"], G["fl"], G["dr"], G["lod_scene"]
FC = next(o for o in S.objects if o.type == "CAMERA" and o.get("vj_flight_cam"))
DWELL, TIMEOUT, HOLD = JOB.get("dwell", 10.0), JOB.get("timeout", 150.0), 3.0
KEYS = (0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0)
NAMES = ("orbit", "approach", "skim", "hover")

old = DN.get("flight_numbers")
if old and old.get("handle"):
    try:
        bpy.types.SpaceView3D.draw_handler_remove(old["handle"], "WINDOW")
    except Exception:
        pass
st = {"rows": [], "events": {}, "last": None, "label": "start", "handle": None, "cuts": []}
DN["flight_numbers"] = st
DN["flight_done"] = False


def send(**values):
    BRIDGE.apply({"/" + k.replace("_", "/", 1): [float(v)] for k, v in values.items()}, "flight_numbers")


def holes():
    L = LOD._state
    want, far, shown = L.get("want") or L.get("nodes") or {}, L.get("far") or set(), L.get("shown") or {}
    near = [b for b in want if b not in far]
    return sum(1 for b in near if b not in shown), len(shown), len(L.get("near_missing") or ())


def on_draw():
    rd = bpy.context.region_data
    if rd is None or rd.view_perspective != "CAMERA":
        return
    now = time.perf_counter()
    if st["last"] is not None:
        F = FS.get("flight")
        on_flight = FS.get("on_air") == FC
        hole, shown, nmiss = holes() if FS.get("stream") else (0, 0, 0)
        agl = None
        if on_flight and F is not None and FS.get("flight_pose") is not None:
            u, h = dr.spherical(FS["flight_pose"][0])
            agl = round(h - FS["map"].surface(u), 1)
        st["rows"].append((round(now - st["t0"], 3), round((now - st["last"]) * 1000.0, 2), st["label"],
                           int(S.get("rt_flight_stage", -1)) if on_flight else -1,
                           round(F.f, 4) if F else None, round(F.fe, 4) if F else None, agl,
                           bool(FS.get("stream") and LOD.live()), bool(LOD.holding()), nmiss, hole, shown))
    st["last"] = now


def defaults():
    """Every /vj/* control back to its wire default (a grab run leaves its last state, /vj/boost 1 after the boost pair)."""
    for k in list(S.keys()):
        if k.startswith("vj_") and k != "vj_cam" and isinstance(S[k], (int, float)):
            d = S.id_properties_ui(k).as_dict().get("default")
            if d is not None:
                S[k] = d


def run():
    st["t0"] = t0 = time.perf_counter()
    now = lambda: time.perf_counter() - t0
    defaults()
    send(vj_blend=0.0, vj_flight=0.0, vj_cam=0.0)
    st["label"] = "settle_cam0"
    while now() < 4.0:
        yield 0.1
    st["label"], t = "cam0_before", now()
    while now() < t + DWELL:
        yield 0.1
    G["quiesce"](JOB.get("seed", 1))
    st["label"], t = "cut_in", now()
    st["events"]["cut_in"] = round(t, 3)
    send(vj_cam=float(FC.name[4:]))
    while now() < t + 1.5:
        yield 0.05
    for k, (key, name) in enumerate(zip(KEYS, NAMES)):
        send(vj_flight=key)
        st["label"], t, since = "to_" + name, now(), None
        while now() < t + TIMEOUT:
            F = FS.get("flight")
            ok = F is not None and abs(F.f - key) < 2e-3 and int(S.get("rt_flight_stage", -1)) == k
            if name == "hover":
                ok = ok and F.fe >= 0.999
            since = (since or now()) if ok else None
            if since is not None and now() - since >= HOLD:
                break
            yield 0.1
        st["events"]["reached_" + name] = round(now() - t, 2) if since is not None else None
        st["label"], t = name, now()
        while now() < t + DWELL:
            yield 0.1
    st["events"]["hover_gap"] = round(FS["flight"].gap, 1)
    st["events"]["seed"] = FS["flight"].seed
    st["label"], t = "cut_out", now()
    st["events"]["cut_out"] = round(t, 3)
    send(vj_cam=0.0)
    while now() < t + 3.0:
        yield 0.05
    st["label"], t = "cam0_after", now()
    while now() < t + DWELL:
        yield 0.1
    send(vj_flight=0.0, vj_blend=1.0)
    bpy.types.SpaceView3D.draw_handler_remove(st["handle"], "WINDOW")
    st["handle"] = None
    summary = {}
    for label in dict.fromkeys(r[2] for r in st["rows"]):
        ms = sorted(r[1] for r in st["rows"] if r[2] == label)
        rs = [r for r in st["rows"] if r[2] == label]
        summary[label] = {"frames": len(ms), "median_ms": round(statistics.median(ms), 1),
                          "p95_ms": round(ms[min(len(ms) - 1, int(0.95 * len(ms)))], 1), "worst_ms": ms[-1],
                          "frames_with_hole": sum(1 for r in rs if r[7] and r[10] > 0),
                          "max_hole": max((r[10] for r in rs if r[7]), default=0),
                          "agl_min": min((r[6] for r in rs if r[6] is not None), default=None)}
    json.dump({"events": st["events"], "summary": summary, "load": __import__("os").getloadavg()[0],
               "columns": ["t", "ms", "label", "stage", "f", "fe", "agl", "live", "holding", "near_missing", "hole", "shown"],
               "rows": st["rows"]}, open(JOB["out"], "w"))
    DN["flight_done"] = True


gen = run()


def tick():
    try:
        return next(gen)
    except StopIteration:
        return None
    except Exception:
        import traceback
        st["err"] = traceback.format_exc()
        DN["flight_done"] = True
        return None


st["handle"] = bpy.types.SpaceView3D.draw_handler_add(on_draw, (), "WINDOW", "POST_PIXEL")
bpy.app.timers.register(tick, first_interval=0.1)
