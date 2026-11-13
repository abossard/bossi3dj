"""Numerical checks for the Flight, the blends and the LOD stream (docs/research/synthwave-flight.md).

Plain Python, no Blender: python3 verify_flight.py [--quick]. Exit code 1 on any FAIL.
The terrain is synthetic (a continent with a coast, a mountain massif with passes, a lake and a pyramid on the
skim ring), so clearance and framing are checked against exact heights.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "blender", "scenes"))
import flight as fl  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "blender", "scenes", "planet_proto"))
import lod_stream as ls  # noqa: E402
import director as dr  # noqa: E402
import energy as en  # noqa: E402

QUICK = "--quick" in sys.argv
LOD_ONLY = "--lod-only" in sys.argv     # sections 1, 2, 5 and 6 only
BLEND_ONLY = "--blend-only" in sys.argv     # sections 1, 2 and 6 only
ENERGY_ONLY = "--energy-only" in sys.argv   # sections 1, 2 and 7 only
FPS = 60.0
DT = 1.0 / FPS
fails = []


def check(name, value, tol, op="<="):
    if (LOD_ONLY or BLEND_ONLY) and name[0] in "347" or BLEND_ONLY and name[0] == "5" or ENERGY_ONLY and name[0] in "3456":
        return
    ok = value <= tol if op == "<=" else value >= tol
    print("%-64s %12.4g  (%s %g)  %s" % (name, value, op, tol, "ok" if ok else "FAIL"))
    if not ok:
        fails.append(name)


class Synth:
    """A continent round the pole with sea at 0 m, a massif with five passes near its east coast, a lake at 30 m
    and a 46 m pyramid standing on the skim ring."""

    def __init__(self):
        self.c = (0.0, 0.0, 1.0)
        e, n = fl.local_frame(self.c)
        self.e, self.n = e, n
        self.mtn = fl.offset(self.c, e, n, 6500.0, 0.0)
        self.lake = fl.offset(self.c, e, n, -2000.0, 1500.0)
        me, mn = fl.local_frame(self.mtn)
        self.me, self.mn = me, mn
        self.pyr = fl.offset(self.mtn, me, mn, 0.0, 1800.0)
        self.far = fl.norm((0.3, -0.95, -0.1))          # a second candidate across the Planet, for region choice

    def ground(self, u):
        d = fl.R * fl.angle(u, self.c)
        h = 420.0 * math.exp(-(d / 6500.0) ** 2) - 60.0
        dm = fl.R * fl.angle(u, self.mtn)
        if dm < 6000.0:
            t = fl.tangent(self.mtn, u)
            az = math.atan2(fl.dot(t, self.mn), fl.dot(t, self.me))
            h += 380.0 * math.exp(-(dm / 1300.0) ** 2) * (0.65 + 0.35 * math.cos(5.0 * az)) + 60.0 * math.exp(-((dm - 1800.0) / 500.0) ** 2) * math.cos(5.0 * az)
        dl = fl.R * fl.angle(u, self.lake)
        h -= 110.0 * math.exp(-(dl / 700.0) ** 2)
        dp = fl.R * fl.angle(u, self.pyr)
        if dp < 40.0:
            h = max(h, h + 46.0 * (1.0 - dp / 40.0))
        return h

    def water(self, u):
        dl = fl.R * fl.angle(u, self.lake)
        return 30.0 if dl < 900.0 else 0.0

    def surface(self, u):
        return max(self.ground(u), self.water(u))

    def candidates(self):
        return [self.mtn, self.far]


T = Synth()
SUN = fl.norm((0.0, 0.8, 0.6))
MOON = (fl.add(fl.CENTRE, fl.norm((0.5, -0.6, 0.62)), 50000.0), 11500.0)

# 1. damping: a step from 0 to 1
x = v = 0.0
xs = [0.0]
vs = [0.0]
for i in range(int(90.0 / fl.SUBSTEP)):
    x, v = fl.glide(x, v, 1.0, fl.FLIGHT_RATE, fl.FLIGHT_ACC, fl.SUBSTEP)
    xs.append(x)
    vs.append(v)
check("1a damping: overshoot", max(xs) - 1.0, 1e-3)
check("1b damping: monotone (largest step back)", max(0.0, max(xs[i] - xs[i + 1] for i in range(len(xs) - 1))), 0.0)
t99 = next(i for i, x in enumerate(xs) if x >= 0.99) * fl.SUBSTEP
check("1c damping: time to 0.99 (s)", t99, 75.0)
check("1d damping: a jump does not teleport (time to 0.5, s)", next(i for i, x in enumerate(xs) if x >= 0.5) * fl.SUBSTEP, 15.0, ">=")
check("1e damping: rate never exceeds FLIGHT_RATE (ratio)", max(abs(v) for v in vs) / fl.FLIGHT_RATE, 1.0 + 1e-6)
check("1f damping: acceleration never exceeds FLIGHT_ACC, short of the final snap (ratio)", max(abs(vs[i + 1] - vs[i]) for i in range(len(vs) - 1) if 1.0 - xs[i + 1] > 1e-5) / fl.SUBSTEP / fl.FLIGHT_ACC, 1.0 + 1e-6)

# 2. stage weights
fs = [i / 3000.0 for i in range(3001)]
W = [fl.weights(f) for f in fs]
check("2a weights: partition of unity", max(abs(sum(w) - 1.0) for w in W), 1e-12)
check("2b weights: each stage 1 on its key", max(abs(fl.weights(k)[i] - 1.0) for i, k in enumerate(fl.KEYS)), 1e-12)
h = 1e-7
check("2c weights: flat on both sides of every key (C1, the stage holds)",
      max(abs(fl.weights(min(max(k + s * h, 0.0), 1.0))[i] - fl.weights(k)[i]) / h for k in fl.KEYS for s in (-1, 1) for i in range(4)), 1e-4)


# 3-4. flight sims
def program(name, rng):
    """(time s, flight, boost) samples: piecewise-constant controls, as OSC sends them."""
    if name == "sweep":
        return [(0, 0, 0), (15, 1, 0), (110, 0, 0), (200, 0, 0)]
    if name == "steps":
        return [(0, 0, 0), (10, 1 / 3, 0), (60, 2 / 3, 0), (110, 1, 0), (160, 1 / 3, 0), (200, 0, 0), (240, 0, 0)]
    if name == "jumps":
        return [(5 * i, rng.random(), 0) for i in range(40)] + [(200, 0, 0)]
    if name == "ramp":
        return [(i, min(i, 200 - i) / 100.0, 0) for i in range(0, 201)]
    if name == "boost":
        return [(0, 1, 0)] + [(70 + 8 * i + d, 1, b) for i in range(12) for d, b in ((0, 1), (3, 0))] + [(170, 1, 0)]
    if name == "dither":
        return [(0, 0.66, 0)] + [(60 + 0.5 * i, 0.6 + 0.1 * (i % 2), 0) for i in range(120)] + [(130, 0.66, 0)]
    raise ValueError(name)


def control(prog, t):
    cur = prog[0]
    for p in prog:
        if p[0] <= t:
            cur = p
    return cur[1], cur[2]


def vfov_half(lens):
    return math.atan((fl.SENSOR / 2.0) / lens / fl.ASPECT)


PROGRAMS = ("sweep", "steps", "jumps", "ramp", "boost", "dither")
SEEDS = range(3) if QUICK else range(8)
worst = {"floor": 0.0, "clear": 1e9, "turn": 0.0, "turn_acc": 0.0, "acc_low": 0.0, "slow": 1e9, "orbit_fit": -1e9,
         "horizon": -1e9, "moon": 1e9, "arrive": 0.0, "hover_gap": 0.0}
regions = set()
where = {}
for seed in ([] if LOD_ONLY or BLEND_ONLY or ENERGY_ONLY else SEEDS):
    for name in PROGRAMS:
        rng = random.Random(seed * 101 + len(name))
        prog = program(name, rng)
        F = fl.Flight(T, seed=seed, sun=SUN)
        prev_f = prev_p = prev_dp = prev_w = None
        at_one = arrived = None                 # when f reached 1 and when the Hover took effect over the water
        stay = False                            # on its loop with f at 1 ever since
        steps = int(prog[-1][0] * FPS)
        for i in range(steps):
            f, b = control(prog, i * DT)
            p, fwd, up, lens, info = F.step(DT, f, b, sun=SUN, moon=MOON)
            if info["region"] is not None:
                regions.add((seed, info["region"]))
            worst["clear"] = min(worst["clear"], info["clear"] - fl.curve_log(info["f"], fl.H_MIN) + 1e-9)
            worst["moon"] = min(worst["moon"], fl.length(fl.sub(p, MOON[0])) - MOON[1])
            if prev_f is not None:
                om = fl.angle(prev_f, fwd) / DT
                if math.degrees(om) > worst["turn"]:
                    worst["turn"], where["turn"] = math.degrees(om), (seed, name, round(i * DT, 1), round(info["f"], 3), round(info["alt"]), round(info["speed"]))
                if prev_w is not None:
                    worst["turn_acc"] = max(worst["turn_acc"], math.degrees(abs(om - prev_w)) / DT)
                prev_w = om
                dp = fl.sub(p, prev_p)
                if prev_dp is not None and info["alt"] < 2000.0:
                    a_ = fl.length(fl.sub(dp, prev_dp)) / (DT * DT) / max(1.0, info["clear"] / 150.0)
                    if a_ > worst["acc_low"]:
                        worst["acc_low"], where["acc_low"] = a_, (seed, name, round(i * DT, 1), round(info["f"], 3), round(info["alt"]), round(info["speed"]))
                prev_dp = dp
            prev_f, prev_p = fwd, p
            if i > FPS * 5:
                worst["slow"] = min(worst["slow"], info["speed"])
            near = F.region is not None and fl.R * fl.angle(F.u, F.region[1]) < 1.15 * fl.SKIM_RING + 500.0
            if F.f < 0.999:
                at_one = arrived = None
            elif at_one is None and near:          # f at 1 with the camera at the region (the descent is not timed)
                at_one = i * DT
            if at_one is not None and arrived is None:      # a hold that never gets there counts its whole length
                worst["arrive"] = max(worst["arrive"], i * DT - at_one)
                arrived = i * DT if F.fe >= 0.999 else None
            stay = F.f >= 0.999 and (stay or F.gap <= 0.5 * fl.HOVER_SHORE)
            if stay and name != "boost":
                worst["hover_gap"] = max(worst["hover_gap"], F.gap)
            w = info["w"]
            hv = vfov_half(lens)
            up_r = fl.norm(fl.sub(p, fl.CENTRE))
            if w[fl.ORBIT] > 0.999 and info["alt"] > 0.9 * fl.ALT[fl.ORBIT]:
                need = 0.0
                for c, r in ((fl.CENTRE, fl.R), MOON):
                    dv = fl.sub(c, p)
                    need = max(need, fl.angle(fwd, fl.norm(dv)) + math.asin(r / fl.length(dv)))
                worst["orbit_fit"] = max(worst["orbit_fit"], math.degrees(need - hv * fl.ASPECT ** 0) if False else math.degrees(need - math.atan(math.tan(hv) * fl.ASPECT)))
            if w[fl.ORBIT] < 0.01 and i > FPS * 10:
                dip = math.acos(fl.R / (fl.R + max(info["alt"], 0.0)))
                el = math.asin(fl.clamp(fl.dot(fwd, up_r), -1.0, 1.0))
                e_ = math.degrees(abs(el + dip) - 0.9 * hv)
                if e_ > worst["horizon"]:
                    worst["horizon"], where["horizon"] = e_, (seed, name, round(i * DT, 1), round(info["f"], 3), round(info["alt"]), round(math.degrees(el), 1), round(math.degrees(dip), 1), round(math.degrees(hv), 1))
        if F.floor_hits / max(F.steps, 1) > worst["floor"]:
            worst["floor"], where["floor"] = F.floor_hits / max(F.steps, 1), (seed, name)
check("3a clearance: height over the surface minus the stage floor (m)", worst["clear"], 0.0, ">=")
check("3b clearance: share of substeps where the floor binds", worst["floor"], 0.005)
check("3c moon: distance off the moon's surface (m)", worst["moon"], fl.MOON_CLEAR - 1.0, ">=")
check("3d FL1: view angular speed (deg/s)", worst["turn"], 45.0)
check("3e FL1: view angular acceleration (deg/s2)", worst["turn_acc"], 400.0)
check("3f FL1: acceleration under 2 km, per 150 m of height over 150 m (m/s2)", worst["acc_low"], 4.0 * fl.G)
check("3g FL1: never stalls (ground speed, m/s)", worst["slow"], 5.0, ">=")
check("3h FL2/FL4: the Hover in effect, s after f reaches 1 at the region (the blend reaches the water)", worst["arrive"], 15.0)
check("3i FL2/FL4: once on its water loop the Hover stays on it, programs without a boost (m off the loop)", worst["hover_gap"], fl.HOVER_SHORE)


# 3j. the Hover from the Skim: start states over seeds, time on the Skim track and two regions
def hover_jump(region, seed, hold, dt=DT):
    """A jump of /vj/flight from the Skim (2/3, held hold s on the region's Skim track) to the Hover (1): seconds from
    f reaching 1 until the Hover is in effect (fe 1), and the water's distance at the jump (m). dt is the frame time."""
    T.candidates = lambda: [region]
    F = fl.Flight(T, seed=seed, sun=SUN)
    t, on = 0.0, None
    while on is None or t < on + hold:
        F.step(dt, KEYS_SKIM, 0, sun=SUN, moon=MOON)
        t += dt
        if on is None and F.f > KEYS_SKIM - 1e-3 and fl.R * fl.angle(F.u, F.region[1]) < 1.15 * fl.SKIM_RING + 500.0:
            on = t
    at_one = gap = None
    for _ in range(int(150.0 / dt)):
        F.step(dt, 1.0, 0, sun=SUN, moon=MOON)
        t += dt
        if gap is None and F.f > KEYS_SKIM + 1e-3:
            gap = F.gap
        if at_one is None and F.f >= 0.999:
            at_one = t
        if F.fe >= 0.999:
            return t - at_one, gap
    return math.inf, gap


KEYS_SKIM = fl.KEYS[fl.SKIM]
if not (LOD_ONLY or BLEND_ONLY or ENERGY_ONLY):
    regions_ = (("the sea", T.far), ("water on one side", T.mtn))
    for label, region in regions_:
        for dt in (DT, 0.054, 0.1):     # the live frame time is 50 to 100 ms under load: the arrival must not depend on it
            runs = [(seed, hold) + hover_jump(region, seed, hold, dt) for seed in SEEDS for hold in (0.0, 15.0, 30.0, 45.0)]
            worst_ = max(runs, key=lambda r: r[2])
            check("3j FL2: a jump from the Skim to the Hover, %s, frame %.0f ms: in effect s after f reaches 1, %d start states" % (label, 1000 * dt, len(runs)), worst_[2], 15.0)
            print("   worst (seed, s on the Skim before the jump, s, water m off at the jump):", tuple(round(x) for x in worst_))
    del T.candidates


check("4a FL4: orbit frames planet and moon (deg past the frame edge)", worst["orbit_fit"], 0.0)
check("4b FL4: horizon inside the frame below orbit (deg past 0.9 of the edge)", worst["horizon"], 0.0)
if not (LOD_ONLY or BLEND_ONLY or ENERGY_ONLY):
    print("   worst at", where)
    check("4c seeds: distinct regions visited", float(len(regions)), 1.0, ">=")


# 7. energy, hit and pulse (energy.py, the Flight's energy terms, the Director's accents)
def drive_run(program, seconds, dt=DT):
    """program(t) -> (energy, hit, beat); returns the Drive's state per frame."""
    D_ = en.Drive(program(0.0)[0])
    out = []
    for i in range(int(seconds / dt)):
        e_, h_, b_ = program(i * dt)
        D_.step(dt, e_, h_, b_)
        out.append((i * dt, D_.e, D_.kick, D_.beat, D_.speed, D_.phase, D_.fired))
    return out


# 7a easing: a step reaches 95% of its way after RISE up and FALL down, never overshoots, and starts without a jolt
for name, e_from, e_to, want in (("rise 0.3->1", 0.3, 1.0, en.RISE), ("rise 0->1", 0.0, 1.0, en.RISE),
                                 ("fall 1->0.3", 1.0, 0.3, en.FALL), ("fall 1->0", 1.0, 0.0, en.FALL)):
    D_ = en.Drive(e_from)
    es = []
    for i in range(int(8.0 / DT)):
        D_.step(DT, e_to, 0.0, 0.0)
        es.append(D_.e)
    t95 = next(i for i, x in enumerate(es) if abs(x - e_from) >= 0.95 * abs(e_to - e_from)) * DT
    check("7a ease %s: time to 95%% (s, off the spec)" % name, abs(t95 - want), 0.1)
    check("7a ease %s: overshoot" % name, max(0.0, max((x - e_to) * (1 if e_to > e_from else -1) for x in es)), 1e-9)
    check("7a ease %s: first frame's share of the step (no jolt)" % name, abs(es[0] - e_from) / abs(e_to - e_from), 0.01)

# 7b the hit: fires on a rising edge over 0.5 only, its kick starts on the frame it arrives, peaks at a lens of
# HIT_LENS and is gone after HIT_RECOVER
POSE0 = (fl.add(fl.CENTRE, (0.0, 0.0, 1.0), fl.R + 50.0), fl.norm((0.0, 1.0, -0.1)), (0.0, 0.0, 1.0), 30.0, {})
for name, hits, fires in (("one pulse", [(1.0, 1.1, 1.0)], 1), ("held high", [(1.0, 4.0, 1.0)], 1),
                          ("under 0.5", [(1.0, 1.1, 0.4)], 0), ("two close", [(1.0, 1.1, 1.0), (1.5, 1.6, 1.0)], 2),
                          ("strong", [(1.0, 1.1, 1.5)], 1)):
    run = drive_run(lambda t: (en.E0, max([v for a, b, v in hits if a <= t < b], default=0.0), 0.0), 6.0)
    check("7b hit %s: fires" % name, abs(sum(r[6] for r in run) - fires), 0.0)
    if fires:
        i0 = next(i for i, r in enumerate(run) if r[6])
        D_ = en.Drive()
        lens = []
        for r in run:
            D_.e, D_.kick, D_.beat, D_.phase = r[1], r[2], 0.0, r[5]
            lens.append(en.accent(POSE0, D_)[3] / POSE0[3])
        check("7b hit %s: lens on the frame it arrives (share of the kick, EN3)" % name, (1.0 - lens[i0]) / (1.0 - en.HIT_LENS), 0.15, ">=")
        check("7b hit %s: widest lens (times the shot's)" % name, abs(min(lens) - en.HIT_LENS), 0.03)
        last = max(i for i, r in enumerate(run) if r[6])
        check("7b hit %s: kick left after HIT_RECOVER" % name, max(r[2] for r in run[last + int(en.HIT_RECOVER / DT) + 1:]), 0.0)
        check("7b hit %s: lens step between frames (log)" % name, max(abs(math.log(lens[i + 1] / lens[i])) for i in range(len(lens) - 1)), 0.1)

# 7c the pulse: a push of BEAT_LENS at most, a dip and roll of BEAT_TILT at most, scaled by the energy
for e_ in (0.0, en.E0, 1.0):
    run = drive_run(lambda t: (e_, 0.0, 1.0 if (t % 0.5) < 0.05 else 0.0), 6.0)
    D_ = en.Drive(e_)
    push = tilt = 0.0
    for r in run:
        D_.e, D_.kick, D_.beat, D_.phase = r[1], 0.0, r[3], r[5]
        p_, f_, u_, l_, _ = en.accent(POSE0, D_)
        push = max(push, l_ / POSE0[3] - 1.0)
        tilt = max(tilt, math.degrees(math.acos(min(1.0, (fl.dot(f_, POSE0[1]) + fl.dot(u_, POSE0[2])) / 2.0))) * 2.0 ** 0.5)
    check("7c pulse at energy %.1f: lens push (share, EN5)" % e_, push, en.BEAT_LENS * e_ + 1e-9)
    check("7c pulse at energy %.1f: dip and roll (deg, EN5)" % e_, tilt, 1.0 * e_ + 1e-6)


# 7d-g every fixed shot's move: never static, faster and tighter with the energy, slower and wider without it,
# aim held on the subject, clear of the surface. Synthetic shots for each kind of fixed camera.
def shot(kind):
    """(pose, subject distance, clearance, tighten) for a kind of fixed shot."""
    u = fl.norm((0.02, 0.01, 1.0))
    up = u
    h = fl.tangent(u, (0.0, 1.0, 0.0))
    if kind == "sys":
        p = fl.add(fl.CENTRE, (1.0, 0.0, 0.0), 165000.0)
        f_ = fl.norm(fl.sub(fl.CENTRE, p))
        return (p, f_, fl.tangent(f_, (0.0, 0.0, 1.0)), 19.0, {}), 165000.0, 165000.0 - fl.R, False
    clear, subject, pitch = {"plaza": (3.0, 3000.0, -2.0), "river": (9.0, 150.0, -4.0), "hero": (20.0, 120.0, -8.0),
                             "moon": (6.0, 2500.0, 25.0), "far": (25.0, 380.0, -3.0)}[kind]
    p = fl.add(fl.CENTRE, u, fl.R + clear)
    f_ = fl.norm(fl.add(fl.scale(h, math.cos(math.radians(pitch))), up, math.sin(math.radians(pitch))))
    return (p, f_, fl.tangent(f_, up), 30.0, {}), subject, clear, True


def energy_program(name):
    return {"zero": lambda t: (0.0, 0.0, 0.0), "default": lambda t: (en.E0, 0.0, 0.0), "full": lambda t: (1.0, 0.0, 0.0),
            "show": lambda t: (min(t / 20.0, 1.0) if t < 30.0 else 0.1, 1.0 if 24.0 <= t < 24.1 else 0.0,
                               1.0 if (t % 0.48) < 0.05 else 0.0)}[name]


SHOTS = ("plaza", "river", "hero", "moon", "far", "sys")
stats = {}
for kind in SHOTS:
    base, subject, clear, tighten = shot(kind)
    aim = fl.add(base[0], base[1], subject)
    for prog in ("zero", "default", "full", "show"):
        run = drive_run(energy_program(prog), 40.0)
        D_ = en.Drive()
        poses = []
        for r in run:
            D_.e, D_.kick, D_.beat, D_.phase = r[1], r[2], r[3], r[5]
            poses.append(en.move(base, subject, clear, D_, 1.3, tighten))
        steps_ = [fl.length(fl.sub(poses[i + 1][0], poses[i][0])) for i in range(len(poses) - 1)]
        tag = "%s %s" % (kind, prog)
        rel = max(subject * en.ORBIT_ANG, en.AMP_MIN) if kind == "sys" else 1.0     # the space view moves in km
        check("7d EN1 %s: smallest move between frames (mm per m of half width)" % tag, min(steps_) * 1000.0 / rel, 0.2, ">=")
        check("7f framing %s: aim off the subject (deg)" % tag, max(math.degrees(fl.angle(q[1], fl.norm(fl.sub(aim, q[0])))) for q in poses), 0.01)
        u_ = fl.norm(fl.sub(base[0], fl.CENTRE))
        check("7g clearance %s: lowest under the shot's height, past FLOOR over the surface (m)" % tag,
              max(fl.dot(fl.sub(base[0], q[0]), u_) - (clear - en.FLOOR) for q in poses), 0.0)
        stats[tag] = (sum(steps_) / len(steps_) * FPS, sum(fl.length(fl.sub(aim, q[0])) for q in poses) / len(poses),
                      sum(q[3] for q in poses) / len(poses))
    for a_, b_ in (("full", "default"), ("default", "zero")):
        check("7e EN2/EN4 %s: speed at %s over %s" % (kind, a_, b_), stats["%s %s" % (kind, a_)][0] / stats["%s %s" % (kind, b_)][0], 1.5, ">=")
        check("7e EN2/EN4 %s: distance to the subject at %s under %s (m)" % (kind, a_, b_),
              stats["%s %s" % (kind, a_)][1] - stats["%s %s" % (kind, b_)][1], 0.0)
        if tighten:
            check("7e EN2/EN4 %s: lens at %s over %s" % (kind, a_, b_), stats["%s %s" % (kind, a_)][2] / stats["%s %s" % (kind, b_)][2], 1.05, ">=")

# path shots run their path at the Drive's rate: never stopped, and faster with the energy and on a hit
for e_ in (0.0, en.E0, 1.0):
    run = drive_run(lambda t: (e_, 1.0 if 3.0 <= t < 3.1 else 0.0, 0.0), 6.0)
    check("7d EN1 path rate at energy %.1f: slowest (times /vj/cam_speed)" % e_, min(r[4] for r in run), en.RATE_LO, ">=")
    check("7e EN3 path rate at energy %.1f: swoop on a hit (times the rate before)" % e_, max(r[4] for r in run) / run[int(2.9 / DT)][4], 2.0, ">=")

# 7h the Flight with the energy and hits: the section 3 limits hold, a hit surges the speed, the energy raises it
EPROGS = {
    "energy ramps at skim": [(0, 2 / 3, 0, 0.3, 0)] + [(40 + 10 * i, 2 / 3, 0, (0.0, 1.0, 0.3, 1.0, 0.0)[i % 5], 0) for i in range(8)] + [(130, 2 / 3, 0, 0.3, 0)],
    "hits at skim": [(0, 2 / 3, 0, 1.0, 0)] + [(50 + 4 * i + d, 2 / 3, 0, 1.0, h_) for i in range(15) for d, h_ in ((0, 1), (0.1, 0))] + [(120, 2 / 3, 0, 1.0, 0)],
    "hits at hover": [(0, 1, 0, 0.6, 0)] + [(70 + 3 * i + d, 1, (i // 5) % 2, 0.6, h_) for i in range(25) for d, h_ in ((0, 1), (0.1, 0))] + [(170, 1, 0, 0.6, 0)],
    "hits at orbit": [(0, 0, 0, 0.8, 0)] + [(10 + 5 * i + d, 0, 0, 0.8, h_) for i in range(8) for d, h_ in ((0, 1), (0.1, 0))] + [(60, 0, 0, 0.8, 0)],
    "sweep at full energy": [(0, 0, 0, 1.0, 0), (5, 1, 0, 1.0, 0), (100, 0, 0, 1.0, 0), (180, 0, 0, 1.0, 0)],
}
for seed in range(2 if QUICK else 4):
    for name, prog in EPROGS.items():
        F = fl.Flight(T, seed=seed, sun=SUN)
        D_ = en.Drive()
        w7 = {"clear": 1e9, "turn": 0.0, "acc_low": 0.0, "slow": 1e9, "surge": 0.0}
        prev_f = prev_p = prev_dp = None
        hit_v = None
        for i in range(int(prog[-1][0] * FPS)):
            cur = [c for c in prog if c[0] <= i * DT][-1]
            D_.step(DT, cur[3], cur[4], 0.0)
            if D_.fired:
                hit_v = (F.v if F.steps else 0.0, i)
            p, fwd, up, lens, info = F.step(DT, cur[1], cur[2], en.level(D_.e), D_.kick, sun=SUN, moon=MOON)
            if hit_v is not None and i - hit_v[1] < 2.0 * FPS:
                w7["surge"] = max(w7["surge"], info["speed"] - hit_v[0])
            w7["clear"] = min(w7["clear"], info["clear"] - fl.curve_log(info["f"], fl.H_MIN) + 1e-9)
            if prev_f is not None:
                w7["turn"] = max(w7["turn"], math.degrees(fl.angle(prev_f, fwd)) * FPS)
                dp = fl.sub(p, prev_p)
                if prev_dp is not None and info["alt"] < 2000.0:
                    w7["acc_low"] = max(w7["acc_low"], fl.length(fl.sub(dp, prev_dp)) / (DT * DT) / max(1.0, info["clear"] / 150.0))
                prev_dp = dp
            prev_f, prev_p = fwd, p
            if i > FPS * 5:
                w7["slow"] = min(w7["slow"], info["speed"])
        tag = "seed %d, %s" % (seed, name)
        check("7h %s: clearance over the stage floor (m)" % tag, w7["clear"], 0.0, ">=")
        check("7h %s: floor binds (share of substeps)" % tag, F.floor_hits / max(F.steps, 1), 0.005)
        check("7h %s: view angular speed (deg/s, FL1)" % tag, w7["turn"], 45.0)
        check("7h %s: acceleration under 2 km per 150 m (m/s2, FL1)" % tag, w7["acc_low"], 4.0 * fl.G)
        check("7h %s: never stalls (m/s, EN1)" % tag, w7["slow"], 5.0, ">=")
        if "hits" in name:
            check("7h %s: speed surge within 2 s of a hit (m/s over the speed before, EN3)" % tag, w7["surge"],
                  0.4 * fl.BOOST_SPEED if "orbit" not in name else fl.HIT_SWOOP * fl.SPEED[fl.ORBIT] * 0.3, ">=")

if "--flight-only" in sys.argv:
    print("FAILED: " + ", ".join(fails) if fails else "all checks passed")
    sys.exit(1 if fails else 0)


# 6. blends (the Director)
def shot_pose(name, t):
    """Synthetic shots on the Synth terrain: a ground shot on the plaza, one by the mountains, a moving low pass along
    the coast and an orbit shot."""
    if name == "orbit":
        u = fl.norm((math.cos(0.01 * t), 0.3, math.sin(0.01 * t) + 0.5))
        p = fl.add(fl.CENTRE, u, 85000.0)
        return p, fl.norm(fl.sub(fl.CENTRE, p)), fl.tangent(fl.norm(fl.sub(fl.CENTRE, p)), (0.0, 0.0, 1.0)), 35.0, {"fog_k": 1.0, "fog_clear": 180.0}
    if name == "pass":
        u = fl.offset(T.mtn, T.me, T.mn, 3000.0 + 40.0 * t, -2600.0)
        h = fl.tangent(u, T.me)
    else:
        u = T.c if name == "plaza" else fl.offset(T.mtn, T.me, T.mn, -1200.0, -900.0)
        h = fl.tangent(u, T.mtn if name == "plaza" else T.c)
    up = u
    p = fl.add(fl.CENTRE, u, fl.R + T.surface(u) + (60.0 if name == "pass" else 3.0))
    fwd = fl.norm(fl.add(h, up, -0.05))
    return p, fwd, fl.tangent(fwd, up), 24.0 if name == "pass" else 35.0, {"fog_k": 2.0 if name == "pass" else 1.0, "fog_clear": 300.0}


def run_blend(seq, scale=1.0, seconds=40.0):
    """seq: [(time, shot)]; returns the rig's poses at 60 fps and the transitions' durations."""
    D = dr.Director()
    out, durs, shot = [], [], seq[0][1]
    for i in range(int(seconds * FPS)):
        t = i * DT
        for ts, s_ in seq:
            if abs(t - ts) < DT / 2:
                shot = s_
        had = D.tr
        pose = D.step(DT, shot, shot_pose(shot, t), scale, T)
        if D.tr is not None and D.tr is not had:
            durs.append(D.tr.d)
        out.append((t, shot, pose, D.blending()))
    return out, durs


worst6 = {"jerk": 0.0, "flow": 0.0, "v_jump": 0.0, "end": 0.0, "clear": 1e9, "turn": 0.0, "dur_lo": 1e9, "dur_hi": 0.0, "lens": 0.0}
for seq in ([(0, "plaza"), (2, "mtn")], [(0, "plaza"), (2, "orbit")], [(0, "orbit"), (2, "plaza")],
            [(0, "plaza"), (2, "pass")], [(0, "pass"), (2, "plaza"), (5, "mtn"), (7, "orbit")], [(0, "mtn"), (2, "pass")]):
    poses, durs = run_blend(seq)
    for d in durs:
        worst6["dur_lo"], worst6["dur_hi"] = min(worst6["dur_lo"], d), max(worst6["dur_hi"], d)
    prev_acc = prev_acc2 = None
    for k in range(2, len(poses)):
        (t0, _, a, _), (t1, _, b, _), (t2, s2, c, bl) = poses[k - 2], poses[k - 1], poses[k]
        va, vb = fl.scale(fl.sub(b[0], a[0]), FPS), fl.scale(fl.sub(c[0], b[0]), FPS)
        acc = fl.scale(fl.sub(vb, va), FPS)
        u, h = dr.spherical(c[0])
        clear = h - T.surface(u)
        worst6["clear"] = min(worst6["clear"], clear)
        worst6["flow"] = max(worst6["flow"], fl.length(vb) / max(clear, dr.H0))
        if prev_acc2 is not None:        # an acceleration step shows as a spike in its second difference
            step = fl.length(fl.add(fl.add(acc, prev_acc, -2.0), prev_acc2))
            worst6["jerk"] = max(worst6["jerk"], step / max(1.0, clear / 150.0))
        prev_acc, prev_acc2 = acc, prev_acc
        worst6["turn"] = max(worst6["turn"], math.degrees(fl.angle(b[1], c[1])) * FPS)
        worst6["lens"] = max(worst6["lens"], abs(math.log(c[3] / b[3])) * FPS)
        if not bl and poses[k - 1][3]:          # the frame a blend ends: on the target
            worst6["end"] = max(worst6["end"], fl.length(fl.sub(c[0], shot_pose(s2, t2)[0])))
check("6a blends: flow, speed over clearance (over 30 m): rise and traverse each at FLOW, so at most 1.45 (rad/s)", worst6["flow"], 1.45 * dr.FLOW)
check("6a2 blends: acceleration step between frames, per 150 m of clearance (m/s2: no jolt at start, end or restart)", worst6["jerk"], 3.0)
check("6b blends: on the target when the blend ends (m)", worst6["end"], 1e-6)
check("6c blends: clear of the terrain (m)", worst6["clear"], 2.5, ">=")
check("6d blends: view angular speed (deg/s)", worst6["turn"], 60.0)
check("6e blends: lens change (log per s)", worst6["lens"], 1.5)
check("6f blends: shortest duration (s)", worst6["dur_lo"], dr.DUR_MIN - 1e-9, ">=")
check("6g blends: longest duration (s)", worst6["dur_hi"], dr.DUR_MAX + 1e-9)
cut, _ = run_blend([(0, "plaza"), (2, "orbit")], scale=0.0, seconds=3.0)
check("6h blends: /vj/blend 0 is a cut (m off the target the next frame)", fl.length(fl.sub(cut[int(2 * FPS)][2][0], shot_pose("orbit", 2.0)[0])), 1e-6)

# 7i the Director puts the accents on top: the blend runs on the plain poses and the rig shows the kick
for name, scale in (("cut", 0.0), ("blend", 1.0)):
    Dd, Dr = dr.Director(), en.Drive()
    worst_end = worst_kick = 0.0
    for i in range(int(30.0 * FPS)):
        t = i * DT
        Dr.step(DT, 1.0, 1.0 if 2.0 <= t < 2.1 else 0.0, 1.0 if (t % 0.5) < 0.05 else 0.0)
        s_ = "plaza" if t < 2.0 else "mtn"
        tgt = shot_pose(s_, t)
        out = Dd.step(DT, s_, tgt, scale, T, Dr)
        worst_kick = max(worst_kick, abs(out[3] / Dd.pose[3] - (1.0 - (1.0 - en.HIT_LENS) * Dr.kick) * (1.0 + en.BEAT_LENS * Dr.beat * Dr.e)))
        if not Dd.blending() and t > 2.0:
            worst_end = max(worst_end, fl.length(fl.sub(out[0], tgt[0])))
    check("7i director %s: rig lens is the plain pose's times the kick and the pulse" % name, worst_kick, 1e-9)
    check("7i director %s: on the target after the blend, accents on (m)" % name, worst_end, 1e-6)
if ENERGY_ONLY:
    print("FAILED: " + ", ".join(fails) if fails else "all checks passed")
    sys.exit(1 if fails else 0)


# 5. LOD stream
WAVES = [((0.83, 0.31, 0.46), 2000.0, 200.0), ((-0.27, 0.91, 0.31), 600.0, 80.0), ((0.52, -0.44, 0.73), 150.0, 25.0),
         ((-0.61, -0.25, 0.75), 40.0, 6.0)]


def hfield(u):
    return 120.0 + sum(a * math.sin(fl.dot(fl.norm(w), u) * fl.R * 2.0 * math.pi / lam) for w, lam, a in WAVES)


GRIDS, HGRIDS = {}, {}


def grid(key, p):
    g = GRIDS.get(key)
    if g is None:
        g = GRIDS[key] = ls.node_grid(key, hfield, p)
    return g


TARGETS = {}


def drawn(key, cam, p):
    """The node as the vertex shader draws it for a camera at cam."""
    t = TARGETS.get(key)
    if t is None:
        t = TARGETS[key] = ls.morph_targets(key, hfield, p)
    return ls.morphed(key, grid(key, p), t, cam, p)


def hgrid(key, p):
    """The node's heights over R (what the runtime learns when it evaluates a node)."""
    g = HGRIDS.get(key)
    if g is None:
        g = HGRIDS[key] = [[fl.length(fl.sub(q, fl.CENTRE)) - fl.R for q in row] for row in grid(key, p)]
    return g


def make_hr(p):
    def hr(key):
        if key[1] == 0:
            return None
        par = (key[0], key[1] - 1, key[2] // 2, key[3] // 2)
        return ls.child_range(hgrid(par, p), key, p.n, 2.0 + 0.1 * p.size(key[1]))
    return hr


def lod_path(kind, seconds):
    """Camera positions at 60 fps: skim (85 m/s, 50 m over the field), descend (3 km to 50 m in 20 s, 150 m/s), hover
    (6 m/s at 8 m)."""
    u = fl.norm((0.1, 0.05, 1.0))
    h = fl.tangent(u, (1.0, 0.0, 0.0))
    out = []
    for i in range(int(seconds * FPS)):
        t = i * DT
        if kind == "skim":
            v, alt = 85.0, 50.0
        elif kind == "boost":
            v, alt = 85.0 + fl.BOOST_SPEED, 45.0
        elif kind == "descend":
            v, alt = 150.0, 3000.0 * (50.0 / 3000.0) ** min(t / 20.0, 1.0)
        else:
            v, alt = 6.0, 8.0
        h = fl.rot(u, 0.05 * math.sin(0.3 * t) * DT, h)
        u, h = fl.move(u, h, v * DT)
        out.append((fl.add(fl.CENTRE, u, fl.R + max(hfield(u), 0.0) + alt), v))
    return out


def neighbours(key, leaves_set, p):
    """(edge, neighbour leaf) for each of the 4 edges: the leaf just across each edge midpoint."""
    out = []
    for ex, ey, side in ((0.5, -0.02, "s"), (0.5, 1.02, "n"), (-0.02, 0.5, "w"), (1.02, 0.5, "e")):
        q = ls.node_dir(key, ex * p.n, ey * p.n, p.n)
        for d in range(min(key[1] + 3, p.d_max), -1, -1):
            k = ls.key_at(q, d)
            if k in leaves_set:
                out.append((side, k))
                break
    return out


def edge_points(key, side, p, cam):
    gm = drawn(key, cam, p)
    n = p.n
    idx = {"s": [(x, 0) for x in range(n + 1)], "n": [(x, n) for x in range(n + 1)],
           "w": [(0, y) for y in range(n + 1)], "e": [(n, y) for y in range(n + 1)]}[side]
    return [gm[y][x] for x, y in idx]


def polyline_gap(pts, line):
    """Largest distance from pts to the polyline line."""
    worst = 0.0
    for q in pts:
        best = 1e18
        for a, b in zip(line, line[1:]):
            ab = fl.sub(b, a)
            t = min(max(fl.dot(fl.sub(q, a), ab) / max(fl.dot(ab, ab), 1e-12), 0.0), 1.0)
            best = min(best, fl.length(fl.sub(q, fl.add(a, ab, t))))
        worst = max(worst, best)
    return worst


def change_gap(parent, kids, cam, p):
    """The surface jump when parent and its four children swap, for a camera at cam: every child vertex against the
    parent's drawn triangles, and every parent vertex against the children's."""
    n = p.n
    gp = drawn(parent, cam, p)
    worst = 0.0
    for kid in kids:
        ox, oy = kid[2] - 2 * parent[2], kid[3] - 2 * parent[3]
        gk = drawn(kid, cam, p)
        for y in range(n + 1):
            for x in range(n + 1):
                px, py = (ox * n + x) / 2.0, (oy * n + y) / 2.0
                worst = max(worst, fl.length(fl.sub(gk[y][x], ls.on_mesh(gp, px, py))))
    return worst


def run_lod(kind, seconds, p, lag):
    path = lod_path(kind, seconds)
    hr = make_hr(p)
    hist, prev, sel_cam = [], None, None
    st = {"balance": 0, "crack": 0.0, "pop": 0.0, "multi": 0, "multi_hidden": 0, "coarse": 0, "blocks_s": 0.0, "verts_s": 0.0,
          "leaves": 0, "verts": 0, "live_blocks": 0}
    changed_blocks = verts_eval = 0
    for i, (cam, v) in enumerate(path):
        hist.append(cam)
        cand = hist[max(0, len(hist) - 1 - lag)]
        p.margin = SEL_STEP + 1.0           # the runtime's: SEL_STEP, and the travel as the look-ahead segment
        if prev is None or fl.length(fl.sub(cand, sel_cam)) >= SEL_STEP:   # selects again after SEL_STEP metres
            sel_cam = cand
            step = fl.sub(cand, hist[max(0, len(hist) - 2 - lag)])     # the last frame's travel
            leaves = set(ls.select(sel_cam, p, hr, fl.add(cand, step, lag + 1.0)))
        else:
            leaves = prev
        if prev is not None:
            added, removed = leaves - prev, prev - leaves
            blocks = {ls.block_of(k, p) for k in added | removed}
            changed_blocks += len(blocks)
            for b in blocks:
                verts_eval += sum(1 for k in leaves if ls.block_of(k, p) == b) * (p.n + 1) ** 2
            for k in added:
                par = (k[0], k[1] - 1, k[2] // 2, k[3] // 2)
                top = par if par in removed else k if ls.children(k)[0] in removed else None
                if top is None:
                    # the cull lets a face jump depths where it crosses the horizon (the look-ahead camera bobs with
                    # the terrain); a node past the horizon for both cameras is not seen
                    hidden = ls.past_horizon(k, sel_cam) and ls.past_horizon(k, prev_cam)
                    st["multi_hidden" if hidden else "multi"] += 1
                elif not (ls.past_horizon(top, sel_cam) or ls.past_horizon(top, prev_cam)):   # a cull change is past the horizon
                    gap = change_gap(top, ls.children(top), cam, p)
                    if gap > st["pop"]:
                        st["pop"], st["pop_at"] = gap, (top[1], round(ls.dist_to(top, cam, hr)), "split" if top in removed else "merge")
        prev, prev_cam = leaves, sel_cam
        if i % 60 == 30:
            near = [k for k in leaves if ls.dist_to(k, cam, hr) < 2500.0]
            for k in near:
                for side, nb in neighbours(k, leaves, p):
                    st["balance"] = max(st["balance"], abs(nb[1] - k[1]))
                    if nb[1] < k[1]:            # coarser neighbour: our edge must lie on its edge
                        opp = {"s": "n", "n": "s", "w": "e", "e": "w"}[side]
                        if nb[0] == k[0]:
                            gap = polyline_gap(edge_points(k, side, p, cam), edge_points(nb, opp, p, cam))
                            if gap > st["crack"]:
                                st["crack"], st["crack_at"] = gap, (k[1], round(ls.dist_to(k, cam, hr)), round(ls.dist_to(nb, cam, hr)))
            want = set(ls.select(cam, Params0(p), hr))
            for k in near:
                c = ls.bounds(k)[2]
                if ls.key_at(c, k[1]) == k and any(ls.key_at(c, k[1] + 1) == w[:2] + w[2:] for w in want if w[1] > k[1]):
                    st["coarse"] += 1
    st["blocks_s"] = changed_blocks / seconds
    st["verts_s"] = verts_eval / seconds
    st["leaves"] = len(prev)
    st["verts"] = len(prev) * (p.n + 1) ** 2
    st["live_blocks"] = len({ls.block_of(k, p) for k in prev})
    return st


def Params0(p):
    return ls.Params(p.n, p.k, p.m0, p.d_max, 0.0, p.block_up, p.cull)


LAG = 3                                   # frames between the camera's move and the drawn selection
SEL_STEP = 8.0                            # m between selections, as lod_scene.SEL_STEP
for kind, secs, speed in () if BLEND_ONLY else (("skim", 6.0 if QUICK else 15.0, 85.0), ("boost", 4.0 if QUICK else 10.0, 85.0 + fl.BOOST_SPEED),
                          ("descend", 8.0 if QUICK else 20.0, 150.0), ("hover", 4.0, 6.0)):
    P = ls.Params(margin=speed * (LAG + 1) * DT + 1.0)
    st = run_lod(kind, secs, P, LAG)
    print("5  %-8s leaves %d, vertices %d, live blocks %d, changed blocks %.1f/s, vertices re-evaluated %.0f/s"
          % (kind, st["leaves"], st["verts"], st["live_blocks"], st["blocks_s"], st["verts_s"]))
    check("5a %s: restricted quadtree (largest depth step across an edge)" % kind, float(st["balance"]), 1.0)
    check("5b %s: cracks against a coarser neighbour (m)" % kind, st["crack"], 0.01)
    print("   worst crack (depth, distance m, neighbour distance m):", st.get("crack_at"))
    check("5c %s: pop at a split or merge in view (m)" % kind, st["pop"], 0.01)
    print("   worst pop (depth, distance m, kind):", st.get("pop_at"))
    check("5d %s: changes of more than one depth in a frame, in front of the horizon" % kind, float(st["multi"]), 0.0)
    print("   past the horizon for both cameras (not seen):", st["multi_hidden"])
    check("5e %s: nodes coarser than the camera asks, within 2.5 km" % kind, float(st["coarse"]), 0.0)



def fold_ratio(key, p, rng):
    """Smallest triangle area of a node over its unshifted area, at morph 0, 1 and random per-vertex morphs, on the
    tangent plane at its centre (the irregular net must not fold a triangle at any morph)."""
    n, g, tg = p.n, grid(key, p), ls.morph_targets(key, hfield, p)
    c = ls.node_dir(key, n / 2.0, n / 2.0, n)
    e1 = fl.norm(fl.tangent(c, (0.0, 0.0, 1.0) if abs(c[2]) < 0.9 else (1.0, 0.0, 0.0)))
    e2 = fl.cross(c, e1)
    flat = [[ls.node_dir(key, x, y, n) for x in range(n + 1)] for y in range(n + 1)]

    def area(q, a, b, cc):
        pa, pb, pc_ = ((fl.dot(q[v][u], e1), fl.dot(q[v][u], e2)) for u, v in (a, b, cc))
        return 0.5 * ((pb[0] - pa[0]) * (pc_[1] - pa[1]) - (pb[1] - pa[1]) * (pc_[0] - pa[0]))
    tris = [t_ for y in range(n) for x in range(n) for t_ in (((x, y), (x + 1, y), (x, y + 1)), ((x + 1, y), (x + 1, y + 1), (x, y + 1)))]
    ref = min(abs(area(flat, *t_)) for t_ in tris)
    sign = 1.0 if area(flat, *tris[0]) > 0 else -1.0
    worst = 1e9
    for trial in range(6):
        ms = [[(0.0 if trial == 0 else 1.0 if trial == 1 else rng.random()) for x in range(n + 1)] for y in range(n + 1)]
        q = [[fl.add(g[y][x], fl.sub(tg[y][x], g[y][x]), ms[y][x]) for x in range(n + 1)] for y in range(n + 1)]
        q = [[fl.norm(fl.sub(v, fl.CENTRE)) for v in row] for row in q]
        worst = min(worst, min(sign * area(q, *t_) for t_ in tris) / ref)
    return worst


rng5 = random.Random(5)
P5 = ls.Params()
fold = min(fold_ratio((f_, d_, rng5.randrange(1 << d_), rng5.randrange(1 << d_)), P5, rng5)
           for f_ in range(6) for d_ in (1, 3, 5, 7, 9) for _ in range(4))
check("5f irregular net: smallest triangle over its lattice share, any morph (over 0: no fold)", fold, 1e-6, ">=")

print("FAILED: " + ", ".join(fails) if fails else "all checks passed")
sys.exit(1 if fails else 0)
