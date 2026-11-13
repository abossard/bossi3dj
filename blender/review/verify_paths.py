"""Numerical checks for the Path Camera (blender/scenes/path_camera.py, docs/handover/path-camera.md).

Plain Python, no Blender: python3 verify_paths.py [--quick]. Exit code 1 on any FAIL.
The terrain is synthetic: a continent round the pole with sea at 0 m, a massif, a lake at 30 m, a river channel and
a pyramid hill on the plaza, so clearance and framing are checked against exact heights.

1. Live paths: every path with every target at five heights, 60 s each (speed 1 and the top speed): clearance,
   ground flow, view turn, lens change, the target in frame, the hand-over band.
2. Changes: every path change at every target and every target change on every path: clearance, flow, turn, lens,
   on the new path when the blend ends, no turn back inside the hand-over band.
3. The same program at four frame times ends on the same pose. A fade time of 0 cuts.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scenes"))
import director as dr  # noqa: E402
import flight as fl  # noqa: E402
import path_camera as pc  # noqa: E402

QUICK = "--quick" in sys.argv
FPS = 30.0
DT = 1.0 / FPS
fails = []


def check(name, value, tol, op="<="):
    ok = value <= tol if op == "<=" else value >= tol
    print("%-72s %12.4g  (%s %g)  %s" % (name, value, op, tol, "ok" if ok else "FAIL"))
    if not ok:
        fails.append(name)


class Synth:
    def __init__(self):
        self.c = (0.0, 0.0, 1.0)
        self.e, self.n = fl.local_frame(self.c)
        self.mtn = fl.offset(self.c, self.e, self.n, 6500.0, 0.0)
        self.lake = fl.offset(self.c, self.e, self.n, -2000.0, 1500.0)
        self.river = [fl.offset(self.c, self.e, self.n, x, -2500.0 + 200.0 * math.sin(x / 900.0)) for x in range(-4000, 2001, 250)]
        self.coast = fl.offset(self.c, self.e, self.n, -6500.0 * math.sqrt(math.log(7.0)), 0.0)

    def ground(self, u):
        d = fl.R * fl.angle(u, self.c)
        h = 420.0 * math.exp(-(d / 6500.0) ** 2) - 60.0
        dm = fl.R * fl.angle(u, self.mtn)
        if dm < 6000.0:
            h += 380.0 * math.exp(-(dm / 1300.0) ** 2)
        dl = fl.R * fl.angle(u, self.lake)
        h -= 110.0 * math.exp(-(dl / 700.0) ** 2)
        dr_ = min(fl.R * fl.angle(u, q) for q in self.river) if abs(fl.R * fl.angle(u, self.river[len(self.river) // 2])) < 4500.0 else 1e9
        h -= 25.0 * math.exp(-(dr_ / 60.0) ** 2)
        dp = fl.R * fl.angle(u, self.c)
        if dp < 40.0:
            h += 46.0 * (1.0 - dp / 40.0)
        return h

    def water(self, u):
        return 30.0 if fl.R * fl.angle(u, self.lake) < 900.0 else 0.0

    def surface(self, u):
        return max(self.ground(u), self.water(u))


T = Synth()
SUN = fl.norm((0.0, 0.8, 0.6))
TARGETS = {
    "pyramids": pc.ground_target("pyramids", T.c, T, 60.0, 20.0),
    "lake": pc.ground_target("lake", T.lake, T, 600.0),
    "river": pc.ground_target("river", T.river[len(T.river) // 2], T, 150.0),
    "coast": pc.ground_target("coast", T.coast, T, 800.0),
    "moon": pc.Target("moon", "sky", fl.add(fl.CENTRE, fl.norm((0.5, -0.6, 0.62)), 50000.0), 11500.0),
    "sun": pc.Target("sun", "sky", fl.add(fl.CENTRE, SUN, 2.0e6), 60000.0),
    "planet": pc.Target("planet", "planet", fl.CENTRE, fl.R),
}
HEIGHTS = (0.0, 0.25, 0.5, 0.78, 1.0)
FADE = 30.0         # s, /vj/blend's default
PACE = dr.DUR_MAX / FADE
VFOV_FIT = 1.05     # the target's look point within this share of the half vertical field


def clearance(p):
    u, h = dr.spherical(p)
    return h - T.surface(u), u, h


def half_v(lens):
    return math.atan(fl.SENSOR / 2.0 / fl.ASPECT / lens)


def frames(poses, worst, path=None, target=None, inside=None):
    """Per-frame numbers over a list of (pose, blending): worst clearance, flow, turn, lens change, band."""
    for k in range(1, len(poses)):
        a, b = poses[k - 1], poses[k]
        if b is None or a is None:
            continue
        clear, u, h = clearance(b[0])
        worst["clear"] = min(worst["clear"], clear)
        v = fl.length(fl.sub(b[0], a[0])) / DT
        worst["flow"] = max(worst["flow"], v / (max(clear, 0.0) + dr.H0))
        worst["turn"] = max(worst["turn"], math.degrees(fl.angle(a[1], b[1])) / DT)
        worst["lens"] = max(worst["lens"], abs(math.log(b[3] / a[3])) / DT)
        worst["band"] = max(worst["band"], abs(pc.band_weight(clearance(b[0])[2]) - pc.band_weight(clearance(a[0])[2])) / DT)
        if inside is not None:
            look = pc.look_point(TARGETS[target], b[0], fl.tangent(u, b[1]))
            off = fl.angle(b[1], fl.norm(fl.sub(look, b[0]))) / half_v(b[3])
            worst["frame"] = max(worst["frame"], off)


def fresh():
    return {"clear": 1e9, "flow": 0.0, "turn": 0.0, "lens": 0.0, "band": 0.0, "frame": 0.0, "end": 0.0, "back": 0}


# 1. live paths
secs = 20.0 if QUICK else 60.0
for speed, tag in ((1.0, "speed 1"), (4.0, "top speed")):
    worst = fresh()
    for path in pc.PATHS:
        for target in pc.TARGETS:
            for w in HEIGHTS:
                C = pc.PathCamera(TARGETS, T)
                poses = [C.step(DT, path, target, w, speed) for _ in range(int(secs * FPS))]
                framed = path != "follow" and TARGETS[target].kind == "ground"
                frames(poses, worst, path, target, framed or None)
    check("1a live %s: least clearance over the ground under the camera (m)" % tag, worst["clear"], pc.H_MIN - 1e-6, ">=")
    check("1b live %s: ground flow, speed over clearance + H0 (rad/s)" % tag, worst["flow"], pc.FLOW_MAX * 1.05)
    check("1c live %s: view turn (deg/s)" % tag, worst["turn"], 60.0)
    check("1d live %s: lens change (log per s)" % tag, worst["lens"], 1.5)
    check("1e live %s: ground target in frame (share of the half field)" % tag, worst["frame"], VFOV_FIT)
    check("1f live %s: hand-over band weight change (per s): a crossing takes 1 s at least" % tag, worst["band"], 1.875)

# 2. changes
worst = fresh()
seqs = []
for target in pc.TARGETS:
    for a in pc.PATHS:
        for b in pc.PATHS:
            if a != b:
                seqs += [((a, target), (b, target), w) for w in ((0.3,) if QUICK else (0.0, 0.3, 1.0))]
for path in pc.PATHS:
    for a in pc.TARGETS:
        for b in pc.TARGETS:
            if a != b:
                seqs.append(((path, a), (path, b), 0.3))
if QUICK:
    seqs = seqs[::4]
durs = []
for (pa, ta), (pb, tb), w in seqs:
    C = pc.PathCamera(TARGETS, T)
    for _ in range(int(3 * FPS)):
        last = C.step(DT, pa, ta, w, 1.0, FADE)
    poses, prev_dir, inside_dir = [last], 0.0, None
    C.step(DT, pb, tb, w, 1.0, FADE)
    durs.append(C.D.tr.d if C.D.tr is not None else 0.0)
    was = True
    for _ in range(int((dr.DUR_MAX + 2.0) * FPS)):
        out = C.step(DT, pb, tb, w, 1.0, FADE)
        poses.append(out)
        _, _, h = clearance(out[0])
        if pc.BAND[0] < h < pc.BAND[1] and C.blending():
            dh = h - clearance(poses[-2][0])[2]
            d_ = 1.0 if dh > 1e-6 else -1.0 if dh < -1e-6 else 0.0
            if d_ and inside_dir and d_ != inside_dir:
                worst["back"] += 1
            inside_dir = d_ or inside_dir
        else:
            inside_dir = None
        if was and not C.blending():
            live = C.live(pb, tb, math.exp(C.lh))
            worst["end"] = max(worst["end"], fl.length(fl.sub(out[0], live[0])))
        was = C.blending()
    frames(poses, worst)
print("2  changes: %d, durations %.1f to %.1f s" % (len(seqs), min(durs), max(durs)))
check("2a changes: least clearance over the ground under the camera (m)", worst["clear"], pc.H_MIN - 1e-6, ">=")
# At fade time f the Director's durations (tuned for DUR_MAX) are scaled by f / DUR_MAX: its pace runs PACE times
# faster at the default fade; the new path's own motion (FLOW) adds at the end.
check("2b changes: ground flow (rad/s): the Director's 1.45 FLOW times PACE, plus the path's FLOW", worst["flow"], 1.45 * dr.FLOW * PACE + pc.FLOW)
check("2c changes: view turn (deg/s): 60 times PACE", worst["turn"], 60.0 * PACE)
check("2d changes: lens change (log per s)", worst["lens"], 1.5)
check("2e changes: on the new live path when the blend ends (m)", worst["end"], 1e-6)
check("2f changes: turns back inside the hand-over band", float(worst["back"]), 0.0)
check("2g changes: longest blend at the default fade time (s)", max(durs), FADE + 1e-9)


# 3. frame time and cut
def program(dt, seconds=60.0):
    C = pc.PathCamera(TARGETS, T)
    t, out = 0.0, None
    steps = int(round(seconds / dt))
    for i in range(steps):
        t = i * dt
        path = "orbit" if t < 20 else "rise" if t < 35 else "vantage"
        target = "pyramids" if t < 25 else "lake"
        w = 0.3 if t < 5 else 0.6 if t < 40 else 0.2
        out = C.step(dt, path, target, w)
    return out


ref = program(1.0 / 60.0)
worst_dt = max(fl.length(fl.sub(program(dt)[0], ref[0])) for dt in (1.0 / 30.0, 1.0 / 20.0, 0.1))
check("3a the same program at 60, 30, 20 and 10 fps: end pose apart (m)", worst_dt, 1.0)
C = pc.PathCamera(TARGETS, T)
for _ in range(30):
    C.step(DT, "orbit", "pyramids", 0.3, 1.0, 0.0)
cut = C.step(DT, "vantage", "coast", 0.3, 1.0, 0.0)
check("3b fade time 0 cuts (m off the new live pose)", fl.length(fl.sub(cut[0], C.live("vantage", "coast", math.exp(C.lh))[0])), 1e-6)

print("FAILED: " + ", ".join(fails) if fails else "all checks passed")
sys.exit(1 if fails else 0)
