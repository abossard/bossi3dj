"""Issue #25: how much land a Path Camera blend keeps in frame, without Blender.
    python3 blender/review/blend_horizon.py
On verify_paths.py's synthetic terrain, replays the demo check's shot changes (blender/review/out/demo-check-2026-11-16,
state.jsonl: vantage planet -> orbit river at /vj/height 0.3, follow sun -> rise lake, rise lake -> vantage moon) at
/vj/blend 30 s and prints per second: the eye's height over the sea, the view's pitch over level, the horizon's dip and
the share of the frame's centre column that sees the planet (land), from the pose's forward and vertical field.
"""
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
G = {"__name__": "blend_horizon", "__file__": os.path.join(HERE, "verify_paths.py")}
exec(open(G["__file__"]).read().split("# 1. live paths")[0], G)     # its imports, Synth terrain and TARGETS, no checks
dr, fl, pc, T, TARGETS, DT, half_v = (G[k] for k in ("dr", "fl", "pc", "T", "TARGETS", "DT", "half_v"))

PROGRAM = [  # (s, path, target) as Magic sent them in the demo check
    ((0.0, "vantage", "planet"), (3.0, "orbit", "river"), (40.0, None, None)),
    ((0.0, "follow", "sun"), (3.0, "rise", "lake"), (40.0, None, None)),
    ((0.0, "rise", "lake"), (3.0, "vantage", "moon"), (40.0, None, None)),
]
W, BLEND = 0.3, 30.0


def land_share(p, fwd, lens):
    """The share of the frame's centre column under the horizon, from the forward's pitch over level and the field."""
    u, h = dr.spherical(p)
    pitch = math.asin(fl.clamp(fl.dot(fwd, u), -1.0, 1.0))
    dip = math.acos(fl.clamp(fl.R / (fl.R + max(h, 0.0)), -1.0, 1.0))
    hv = half_v(lens)
    return pitch, dip, fl.clamp((-dip - (pitch - hv)) / (2.0 * hv), 0.0, 1.0)


for steps in PROGRAM:
    C = pc.PathCamera(TARGETS, T)
    t, k, path, target = 0.0, 0, steps[0][1], steps[0][2]
    print("== %s %s -> %s %s" % (steps[0][1], steps[0][2], steps[1][1], steps[1][2]))
    for _ in range(int(20.0 / DT)):            # settle on the first shot
        C.step(DT, path, target, W, 1.0, BLEND)
    while t < steps[-1][0]:
        if k + 1 < len(steps) and t >= steps[k + 1][0] and steps[k + 1][1]:
            k += 1
            path, target = steps[k][1], steps[k][2]
        pose = C.step(DT, path, target, W, 1.0, BLEND)
        if abs(t - round(t)) < DT / 2 and round(t) % 2 == 0:
            pitch, dip, land = land_share(pose[0], pose[1], pose[3])
            print("t %4.0f  eye %7.0f m  pitch %6.1f  dip %5.1f  land %4.2f  blending %d" % (
                t, dr.spherical(pose[0])[1], math.degrees(pitch), math.degrees(dip), land, C.blending()))
        t += DT
