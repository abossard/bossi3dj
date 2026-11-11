"""Splits the worst low-altitude acceleration of single verify_flight cases into tangential, vertical and lateral.

python3 probe_acc.py 3:6:boost 7:1:"sweep at full energy"
Section 3 cases are (seed, program name), section 7 cases (seed, EPROGS name), run as verify_flight runs them.
"""
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "verify_flight.py")).read()
argv, sys.argv = sys.argv, [sys.argv[0], "--energy-only"]
ns = {"__file__": os.path.join(HERE, "verify_flight.py"), "__name__": "verify_head"}
exec(compile(SRC.split("\nPROGRAMS = ")[0], "verify_flight_head", "exec"), ns)
e0 = SRC.index("EPROGS = {")
exec(SRC[e0:SRC.index("\n}\n", e0) + 3], ns)
fl, en, T, SUN, MOON, DT, FPS = (ns[k] for k in ("fl", "en", "T", "SUN", "MOON", "DT", "FPS"))


def run(sec, seed, name):
    F = fl.Flight(T, seed=seed, sun=SUN)
    if sec == "3":
        prog = ns["program"](name, random.Random(seed * 101 + len(name)))
        drive, steps = None, int(prog[-1][0] * FPS)
    else:
        prog = ns["EPROGS"][name]
        drive, steps = en.Drive(), int(prog[-1][0] * FPS)
    prev_p = prev_dp = None
    worst = (0.0,)
    for i in range(steps):
        if drive is None:
            f, b = ns["control"](prog, i * DT)
            p, fwd, up, lens, info = F.step(DT, f, b, sun=SUN, moon=MOON)
        else:
            cur = [c for c in prog if c[0] <= i * DT][-1]
            drive.step(DT, cur[3], cur[4], 0.0)
            p, fwd, up, lens, info = F.step(DT, cur[1], cur[2], en.level(drive.e), drive.kick, sun=SUN, moon=MOON)
        if prev_p is not None:
            dp = fl.sub(p, prev_p)
            if prev_dp is not None and info["alt"] < 2000.0:
                a = fl.scale(fl.sub(dp, prev_dp), 1.0 / (DT * DT))
                k = max(1.0, info["clear"] / 150.0)
                if fl.length(a) / k > worst[0]:
                    vel = fl.norm(dp)
                    rad = fl.norm(fl.sub(p, fl.CENTRE))
                    at, ar = fl.dot(a, vel), fl.dot(a, rad)
                    lat = math.sqrt(max(fl.dot(a, a) - at * at - ar * ar, 0.0))
                    worst = (fl.length(a) / k, round(i * DT, 1), round(info["clear"]), round(info["speed"]),
                             "tan %.1f vert %.1f lat %.1f" % (at / k, ar / k, lat / k),
                             "fe %.3f go %.1f cap %s vb %s en %.2f b %.2f" % (F.fe, F.go, F.cap and round(F.cap, 1),
                                                                             F.vb and round(F.vb, 1), F.en, F.b))
            prev_dp = dp
        prev_p = p
    return worst


for case in argv[1:]:
    sec, seed, name = case.split(":", 2)
    w = run(sec, int(seed), name)
    print("%s  %.1f m/s2 (limit %.2f)  at %s s, clear %s m, %s m/s  %s  %s" % ((case, w[0], 4.0 * fl.G) + w[1:]))
