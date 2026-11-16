"""Path Camera blends keep land in frame without breaking the blend's limits (issue #25, the review of 158d3c1), on
verify_paths.py's synthetic terrain, without Blender. Run: python3 -m unittest discover blender/tests"""
import math
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
G = {"__name__": "test_path_blends", "__file__": os.path.join(HERE, "..", "review", "verify_paths.py")}
exec(open(G["__file__"]).read().split("# 1. live paths")[0], G)     # its imports, Synth terrain and TARGETS, no checks
import energy as en  # noqa: E402  (on the path verify_paths set)
dr, fl, pc, T, TARGETS, DT, half_v = (G[k] for k in ("dr", "fl", "pc", "T", "TARGETS", "DT", "half_v"))
FAR = dict(TARGETS, coast=pc.ground_target("coast", fl.offset(T.c, T.e, T.n, -20000.0, 14000.0), T, 800.0),
           lake=pc.ground_target("lake", fl.offset(T.c, T.e, T.n, 15000.0, -18000.0), T, 600.0))   # about 24 km apart


def land(p, fwd, lens):
    """The share of the frame's centre column under the horizon."""
    u, h = dr.spherical(p)
    pitch = math.asin(fl.clamp(fl.dot(fwd, u), -1.0, 1.0))
    dip = math.acos(fl.clamp(fl.R / (fl.R + max(h, 0.0)), -1.0, 1.0))
    return fl.clamp((-dip - (pitch - half_v(lens))) / (2.0 * half_v(lens)), 0.0, 1.0)


def run(targets, prog, seconds, drive=None):
    """prog: [(t, path, target, height, blend)]; settled 3 s on the first. Returns the blend seconds with land under
    0.1, the largest view turn (deg/s, a cut's frame left out), the keep left on a blend's last frame (deg between the
    Director's view and the one shown), the largest keep in a blend (deg), the angle off the live view on a cut's frame
    and the keep on the frame before it. With drive (energy.accent's beat, e, kick, phase) also the largest difference
    from the beat's full dip over a twin camera without it (deg)."""
    C, twin = pc.PathCamera(targets, T), pc.PathCamera(targets, T) if drive else None
    for _ in range(int(3.0 / DT)):
        prev = C.step(DT, *prog[0][1:4], 1.0, prog[0][4])
        if twin:
            twin.step(DT, *prog[0][1:4], 1.0, prog[0][4])
    r = {"dark": 0.0, "turn": 0.0, "end": 0.0, "kept": 0.0, "cut": 0.0, "cut_kept": 0.0, "accent": 0.0}
    i, gap = 0, 0.0
    for n in range(int(seconds / DT)):
        t = n * DT
        new = i + 1 < len(prog) and prog[i + 1][0] <= t
        i += new
        _, path, target, w, blend = prog[i]
        was = C.blending()
        out = C.step(DT, path, target, w, 1.0, blend, drive)
        if twin:
            bare = twin.step(DT, path, target, w, 1.0, blend)
            r["accent"] = max(r["accent"], abs(math.degrees(fl.angle(bare[1], out[1]) - en.BEAT_TILT / math.sqrt(2.0))))
        if new and blend == 0.0:
            r["cut"] = max(r["cut"], math.degrees(fl.angle(out[1], C.live(path, target, math.exp(C.lh))[1])))
            r["cut_kept"] = gap
        else:
            r["turn"] = max(r["turn"], math.degrees(fl.angle(prev[1], out[1])) / DT)
        if was and not C.blending() and not new:      # a blend that ended by itself, not by a cut
            r["end"] = max(r["end"], gap)
        gap = math.degrees(fl.angle(*C.views)) if C.blending() else 0.0
        r["kept"] = max(r["kept"], gap)
        if C.blending() and land(out[0], out[1], out[3]) < 0.1:
            r["dark"] += DT
        prev = out
    return r


class Beat:
    """A drive on a beat held at its peak (energy.accent reads beat, e, kick and phase)."""
    beat, e, kick, phase = 1.0, 1.0, 0.0, 0.0


CASES = [  # name, targets, program, seconds, most dark blend s, most turn deg/s (60 x DUR_MAX / blend). Dark s before the
    # keep (ea44a0b): 14.2, 6.5, 7.2, 16.6, 15.2, 2.2, 1.4
    ("change mid-blend", TARGETS, [(0, "orbit", "coast", 0.3, 30.0), (5, "orbit", "sun", 0.3, 30.0),
                                   (13, "rise", "lake", 0.3, 30.0)], 45.0, 0.5, 72.0),
    ("fall from space", TARGETS, [(0, "vantage", "planet", 1.0, 30.0), (3, "orbit", "river", 0.3, 30.0)], 40.0, 1.0, 72.0),
    ("cut mid-blend", TARGETS, [(0, "orbit", "coast", 0.3, 30.0), (5, "follow", "sun", 0.3, 30.0),
                                (11, "vantage", "moon", 0.3, 0.0)], 16.0, 0.5, 72.0),
    ("far targets", FAR, [(0, "follow", "lake", 0.6, 30.0), (3, "follow", "coast", 0.6, 30.0),
                          (27, "follow", "sun", 0.6, 30.0)], 50.0, 1.5, 72.0),
    ("far change", FAR, [(0, "orbit", "moon", 0.6, 30.0), (3, "follow", "lake", 0.6, 30.0),
                         (22.4, "orbit", "sun", 0.6, 30.0)], 45.0, 5.5, 72.0),
    ("far change, eye held", FAR, [(0, "follow", "lake", 0.6, 30.0), (3, "rise", "moon", 0.6, 30.0),
                                   (9.9, "vantage", "moon", 0.6, 30.0)], 30.0, 3.5, 72.0),
    ("far change, 15 s fade", FAR, [(0, "follow", "coast", 0.3, 15.0), (3, "follow", "moon", 0.3, 15.0),
                                    (9.5, "orbit", "moon", 0.3, 15.0)], 30.0, 1.0, 144.0),
    ("6 s blends", TARGETS, [(0, "vantage", "coast", 0.6, 6.0), (3, "follow", "lake", 0.6, 6.0)], 12.0, 2.5, 360.0),
    ("6 s blends far", FAR, [(0, "vantage", "coast", 0.6, 6.0), (3, "follow", "lake", 0.6, 6.0)], 12.0, 1.0, 360.0),
]


def kept_view(pitch_deg, clearance):
    """on_land's view for a pose over the plaza at clearance m looking pitch_deg over level, mid-blend (10 s to go):
    the share of land in it and its angle off the given view (deg)."""
    C = pc.PathCamera(TARGETS, T)
    u = T.c
    p = fl.add(fl.CENTRE, u, fl.R + T.surface(u) + clearance)
    head = fl.tangent(u, (1.0, 0.0, 0.0))
    fwd = fl.add(fl.scale(head, math.cos(math.radians(pitch_deg))), u, math.sin(math.radians(pitch_deg)))
    pose = (p, fwd, fl.tangent(fwd, u), 24.0, {})
    out = C.on_land(pose, fl.scale(fwd, 2.0), 10.0)
    return land(out[0], out[1], out[3]), math.degrees(fl.angle(fwd, out[1]))


class KeepTests(unittest.TestCase):
    def test_kept_view(self):
        cases = [  # pitch deg, clearance m, least land, most land, most deg off the view
            (0.0, 3000.0, pc.BLEND_LAND - 1e-6, 1.0, 90.0),         # level from height: tipped down to land
            (-89.0, 3000.0, 0.0, pc.BLEND_LAND_MAX + 1e-6, 90.0),    # straight down: lifted to keep the horizon
            (-5.0, 100.0, 0.0, 1.0, 5.0),                            # low over the plaza: a few degrees at most
        ]
        for pitch, clear, lo, hi, off in cases:
            with self.subTest(pitch=pitch, clearance=clear):
                share, d = kept_view(pitch, clear)
                self.assertGreaterEqual(share, lo)
                self.assertLessEqual(share, hi)
                self.assertLessEqual(d, off)


class BlendTests(unittest.TestCase):
    def test_blends(self):
        for name, targets, prog, seconds, dark_max, turn_max in CASES:
            with self.subTest(case=name):
                r = run(targets, prog, seconds)
                self.assertLessEqual(r["dark"], dark_max, "blend seconds with land under 0.1")
                self.assertLessEqual(r["turn"], turn_max, "view turn (deg/s)")
                self.assertGreater(r["kept"], 1.0, "the keep acts in this case (deg)")
                self.assertLessEqual(r["end"], math.degrees(pc.BLEND_LAND_TURN) * DT + 0.05,
                                     "keep left on a blend's last frame (deg): one frame of BLEND_LAND_TURN at most")

    def test_cut_mid_blend(self):
        r = run(*[c for c in CASES if c[0] == "cut mid-blend"][0][1:4])
        self.assertGreater(r["cut_kept"], 1.0, "the frame before the cut was kept (deg)")
        self.assertLessEqual(r["cut"], 1e-4, "a cut's frame is the live view (deg)")

    def test_accent_on_the_keep(self):
        r = run(*[c for c in CASES if c[0] == "fall from space"][0][1:4], drive=Beat())
        self.assertLessEqual(r["accent"], 1e-3, "the beat's dip over the kept view (deg off the full dip)")


if __name__ == "__main__":
    unittest.main()
