"""Issue #25: how much land a Path Camera blend keeps in frame, without Blender.
    python3 blender/review/blend_horizon.py [state.jsonl] [--base <commit>]
On verify_paths.py's synthetic terrain, replays the demo check's program (blender/review/out/demo-check-2026-11-16/
state.jsonl: per sample the shot, /vj/height, /vj/cam_speed and /vj/blend, held until the next sample) through the
Path Camera as committed at --base (default ea44a0b, before the #25 fix) and as in the working tree. Per second: the
eye's height over the sea, the share of the frame's centre column that sees the planet (land, from the view's pitch,
the horizon's dip and the vertical field) and the fog's clear distance the pose carries. Then per version: blend
seconds with land under 0.1, the least land in a blend, the largest view turn (deg/s).
The synthetic map's targets lie closer together than the planet's, so its humps stay lower than the demo's 12 km.
"""
import json
import math
import os
import subprocess
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
G = {"__name__": "blend_horizon", "__file__": os.path.join(HERE, "verify_paths.py")}
exec(open(G["__file__"]).read().split("# 1. live paths")[0], G)     # its imports, Synth terrain and TARGETS, no checks
dr, fl, pc, T, TARGETS, DT, half_v = (G[k] for k in ("dr", "fl", "pc", "T", "TARGETS", "DT", "half_v"))

args = [a for a in sys.argv[1:] if not a.startswith("--")]
BASE = sys.argv[sys.argv.index("--base") + 1] if "--base" in sys.argv else "ea44a0b"
STATE = args[0] if args and args[0] != BASE else os.path.join(HERE, "out", "demo-check-2026-11-16", "state.jsonl")


def old_module():
    src = subprocess.run(["git", "-C", ROOT, "show", "%s:blender/scenes/path_camera.py" % BASE], capture_output=True,
                         text=True, check=True).stdout
    m = types.ModuleType("path_camera_base")
    exec(compile(src, "path_camera@" + BASE, "exec"), m.__dict__)
    return m


def program():
    rows = [json.loads(line) for line in open(STATE)]
    return [(r["t"], *r["camera"].split(" ", 1), r["values"]["vj_height"], r["values"]["vj_cam_speed"],
             r["values"]["vj_blend"]) for r in rows]


def land_share(p, fwd, lens):
    u, h = dr.spherical(p)
    pitch = math.asin(fl.clamp(fl.dot(fwd, u), -1.0, 1.0))
    dip = math.acos(fl.clamp(fl.R / (fl.R + max(h, 0.0)), -1.0, 1.0))
    hv = half_v(lens)
    return fl.clamp((-dip - (pitch - hv)) / (2.0 * hv), 0.0, 1.0)


def run(mod, prog, tag):
    C = mod.PathCamera(TARGETS, T)
    _, path, target, w, speed, blend = prog[0]
    for _ in range(int(20.0 / DT)):            # settled on the first shot, as the recording began
        C.step(DT, path, target, w, speed, blend)
    t, i, prev, rows = prog[0][0], 0, None, {"dark": 0.0, "least": 1.0, "turn": 0.0}
    print("== %s" % tag)
    while t < prog[-1][0]:
        while i + 1 < len(prog) and prog[i + 1][0] <= t:
            i += 1
        _, path, target, w, speed, blend = prog[i]
        pose = C.step(DT, path, target, w, speed, blend)
        land = land_share(pose[0], pose[1], pose[3])
        if C.blending():
            rows["dark"] += DT * (land < 0.1)
            rows["least"] = min(rows["least"], land)
        if prev is not None:
            rows["turn"] = max(rows["turn"], math.degrees(fl.angle(prev[1], pose[1])) / DT)
        prev = pose
        if abs(t - round(t)) < DT / 2:
            print("t %4.0f  %-15s eye %7.0f m  land %4.2f  fog_clear %5.0f  blending %d" % (
                t, path + " " + target, dr.spherical(pose[0])[1], land, pose[4].get("fog_clear", 0.0), C.blending()))
        t += DT
    return rows


prog = program()
res = {"base " + BASE: run(old_module(), prog, "base " + BASE), "working tree": run(pc, prog, "working tree")}
for k, r in res.items():
    print("%-16s blend s with land < 0.1: %5.1f   least land in a blend: %4.2f   largest view turn: %5.1f deg/s" % (
        k, r["dark"], r["least"], r["turn"]))
