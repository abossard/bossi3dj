"""Issue #25: whether a part of the keep still matters (the guard's change branch did not, in 0 of 120: removed): random programs (near and far targets, fades 15 and 30 s,
a change at 1 to 12 s) on the current path_camera against a copy without the part. Prints per part the largest view
turn (deg/s) with and without, and in how many programs removing it raises the turn by over 5 deg/s.
    python3 blender/review/issue25_review/redundant.py [programs]"""
import math
import os
import random
import sys
import types

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
G = {"__name__": "x", "__file__": os.path.join(ROOT, "blender", "tests", "test_path_blends.py")}
exec(open(G["__file__"]).read().split("def kept_view")[0], G)
dr, fl, pc, T, TARGETS, FAR, DT = (G[k] for k in ("dr", "fl", "pc", "T", "TARGETS", "FAR", "DT"))
SRC = open(os.path.join(ROOT, "blender", "scenes", "path_camera.py")).read()
PARTS = {"heading from the ends": ("head = fl.tangent(u, fl.add(fwd, ends, 0.25))", "head = fl.tangent(u, fwd)")}


def turn(mod, targets, shots, w, t2, b):
    C = mod.PathCamera(targets, T)
    for _ in range(90):
        prev = C.step(DT, *shots[0], w, 1.0, b)
    worst, t = 0.0, 0.0
    while t < 30.0:
        out = C.step(DT, *(shots[1] if t < t2 else shots[2]), w, 1.0, b)
        worst, prev, t = max(worst, math.degrees(fl.angle(prev[1], out[1])) / DT), out, t + DT
    return worst


n = int(sys.argv[1]) if len(sys.argv) > 1 else 120
for part, (a, b_) in PARTS.items():
    m = types.ModuleType("mut")
    exec(compile(SRC.replace(a, b_), "mut", "exec"), m.__dict__)
    rnd, worse, hi = random.Random(5), 0, [0.0, 0.0]
    for _ in range(n):
        shots = [(rnd.choice(pc.PATHS), rnd.choice(pc.TARGETS)) for _ in range(3)]
        args = (FAR if rnd.random() < 0.5 else TARGETS, shots, rnd.choice((0.0, 0.3, 0.6, 1.0)), rnd.uniform(1, 12),
                rnd.choice((15.0, 30.0)))
        x, y = turn(pc, *args), turn(m, *args)
        hi = [max(hi[0], x), max(hi[1], y)]
        worse += y > x + 5.0
    print("%-24s largest turn %.1f with, %.1f without; worse by over 5 deg/s in %d of %d" % (part, hi[0], hi[1], worse, n))
