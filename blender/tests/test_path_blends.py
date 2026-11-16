"""Path Camera blends keep land in frame without breaking the blend's limits (issue #25, the review of 158d3c1), on
verify_paths.py's synthetic terrain, without Blender. Run: python3 -m unittest discover blender/tests"""
import math
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
G = {"__name__": "test_path_blends", "__file__": os.path.join(HERE, "..", "review", "verify_paths.py")}
exec(open(G["__file__"]).read().split("# 1. live paths")[0], G)     # its imports, Synth terrain and TARGETS, no checks
dr, fl, pc, T, TARGETS, DT, half_v = (G[k] for k in ("dr", "fl", "pc", "T", "TARGETS", "DT", "half_v"))
FAR = dict(TARGETS, coast=pc.ground_target("coast", fl.offset(T.c, T.e, T.n, -20000.0, 14000.0), T, 800.0),
           lake=pc.ground_target("lake", fl.offset(T.c, T.e, T.n, 15000.0, -18000.0), T, 600.0))   # about 24 km apart


def land(p, fwd, lens):
    """The share of the frame's centre column under the horizon."""
    u, h = dr.spherical(p)
    pitch = math.asin(fl.clamp(fl.dot(fwd, u), -1.0, 1.0))
    dip = math.acos(fl.clamp(fl.R / (fl.R + max(h, 0.0)), -1.0, 1.0))
    return fl.clamp((-dip - (pitch - half_v(lens))) / (2.0 * half_v(lens)), 0.0, 1.0)


def run(targets, prog, seconds):
    """prog: [(t, path, target, height, blend)]; settled 3 s on the first. Returns the blend seconds with land under
    0.1, the largest view turn (deg/s, the cut frame left out), the largest angle (deg) off the live view at a blend's
    end and the angle off it on a cut's first frame."""
    C = pc.PathCamera(targets, T)
    for _ in range(int(3.0 / DT)):
        prev = C.step(DT, *prog[0][1:4], 1.0, prog[0][4])
    dark, turn, end, cut, i, was = 0.0, 0.0, 0.0, 0.0, 0, False
    for n in range(int(seconds / DT)):
        t = n * DT
        new = i + 1 < len(prog) and prog[i + 1][0] <= t
        i += new
        _, path, target, w, blend = prog[i]
        out = C.step(DT, path, target, w, 1.0, blend)
        live = C.live(path, target, math.exp(C.lh))
        if new and blend == 0.0:
            cut = max(cut, math.degrees(fl.angle(out[1], live[1])))
        else:
            turn = max(turn, math.degrees(fl.angle(prev[1], out[1])) / DT)
        if C.blending() and land(out[0], out[1], out[3]) < 0.1:
            dark += DT
        if was and not C.blending():
            end = max(end, math.degrees(fl.angle(out[1], live[1])))
        was, prev = C.blending(), out
    return dark, turn, end, cut


CASES = [  # name, targets, program, seconds, most dark blend s, most turn deg/s (60 x DUR_MAX / blend). Dark s before the
    # keep (ea44a0b): 14.2, 6.5, 7.2, 16.6, 15.2, 2.2, 1.4
    ("change mid-blend", TARGETS, [(0, "orbit", "coast", 0.3, 30.0), (5, "orbit", "sun", 0.3, 30.0),
                                   (13, "rise", "lake", 0.3, 30.0)], 45.0, 3.5, 72.0),
    ("fall from space", TARGETS, [(0, "vantage", "planet", 1.0, 30.0), (3, "orbit", "river", 0.3, 30.0)], 40.0, 2.0, 72.0),
    ("cut mid-blend", TARGETS, [(0, "orbit", "coast", 0.3, 30.0), (5, "follow", "sun", 0.3, 30.0),
                                (15, "vantage", "moon", 0.3, 0.0)], 20.0, 0.5, 72.0),
    ("far targets", FAR, [(0, "follow", "lake", 0.6, 30.0), (3, "follow", "coast", 0.6, 30.0),
                          (27, "follow", "sun", 0.6, 30.0)], 50.0, 8.0, 72.0),
    ("far change", FAR, [(0, "orbit", "moon", 0.6, 30.0), (3, "follow", "lake", 0.6, 30.0),
                         (22.4, "orbit", "sun", 0.6, 30.0)], 45.0, 13.0, 72.0),
    ("6 s blends", TARGETS, [(0, "vantage", "coast", 0.6, 6.0), (3, "follow", "lake", 0.6, 6.0)], 12.0, 2.0, 360.0),
    ("6 s blends far", FAR, [(0, "vantage", "coast", 0.6, 6.0), (3, "follow", "lake", 0.6, 6.0)], 12.0, 1.0, 360.0),
]


class BlendTests(unittest.TestCase):
    def test_blends(self):
        for name, targets, prog, seconds, dark_max, turn_max in CASES:
            with self.subTest(case=name):
                dark, turn, end, cut = run(targets, prog, seconds)
                self.assertLessEqual(dark, dark_max, "blend seconds with land under 0.1")
                self.assertLessEqual(turn, turn_max, "view turn (deg/s)")
                self.assertLessEqual(end, 0.5, "off the live view at a blend's end (deg)")
                self.assertLessEqual(cut, 1e-4, "off the live view on a cut (deg)")


if __name__ == "__main__":
    unittest.main()
