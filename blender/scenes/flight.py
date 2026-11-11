"""The Flight: one procedural camera that /vj/flight carries from an orbit of the Planet down to the water.

Pure Python (no bpy), so verify_flight.py runs it without Blender. The design and the numbers are in
docs/research/synthwave-flight.md. The runtime builds one Flight on a Terrain (the baked clearance map)
and calls step() every frame; step() returns the camera pose.

- The control f (vj_flight, damped) is one continuum: every value is a shot. Stage parameters are keyed at
  KEYS (Orbit, Approach, Skim, Hover) and blended with smootherstep weights.
- The ground point u (unit direction from the planet centre) moves along a heading at the stage speed. The
  heading steers by pure pursuit toward the weighted stage tracks, with a bounded turn rate: the position never
  jumps and the view never whips round, whatever the control does.
- Altitude follows the clearance envelope ahead (it climbs before a ridge) and is floored over the ground.
- A region (mountains next to water) is locked when f leaves the Orbit. Each return to the Orbit draws a new seed.

A Terrain gives: surface(u) and ground(u) (m over R, conservative), water(u) (m over R, or None on dry land)
and candidates() (unit directions of mountain spots that have water within REGION_WATER).
"""
import math
import random

R = 16000.0
CENTRE = (0.0, 0.0, -R)
G = 9.81
KEYS = (0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0)
ORBIT, APPROACH, SKIM, HOVER = range(4)
SUBSTEP = 1.0 / 120.0

FLIGHT_RATE, FLIGHT_ACC = 1.0 / 50.0, 0.004      # per s, per s2: a jump from 0 to 1 flies for about a minute
BOOST_ATTACK, BOOST_RELEASE = 0.7, 1.5          # s, per stage of the boost's two-stage follower
RESEED_BELOW, LOCK_ABOVE = 0.005, 0.01           # f under which the next visit gets a new seed, over which a region locks

# per stage: Orbit, Approach, Skim, Hover
ALT = (69000.0, 3000.0, 45.0, 4.0)        # m over the clearance envelope (over the water when hovering)
H_MIN = (2000.0, 300.0, 25.0, 2.5)        # m: the floor over the surface right under the camera
SPEED = (420.0, 150.0, 85.0, 6.0)         # m/s of the ground point
LENS = (35.0, 28.0, 20.0, 24.0)           # mm (the Orbit's lens is fitted to the bodies)
PITCH = (0.0, -18.0, -6.0, -2.0)          # deg over the local horizontal
SUBJECT = (1.0, 0.6, 0.0, 0.0)            # weight of the stage subject against the look-ahead
LAT_ACC = (50.0, 0.3 * G, 1.5 * G, 0.4 * G)   # m/s2, the turn limit
BANK_MAX = (0.0, 12.0, 35.0, 10.0)        # deg
BOOST_SPEED, BOOST_LENS, BOOST_PITCH = 70.0, 14.0, -3.0
LOOK_AHEAD = 1.2                          # s of turn the view anticipates
TURN_LAG, VIEW_LAG, ALT_SMOOTH = 0.35, 0.12, 0.8   # s
ENV_AHEAD = (2.0, 300.0)                  # s, m: the envelope looks this far ahead (the larger)
ENV_SAMPLES, CLIMB = 24, 0.35             # samples over it (and half as far behind); the climb gradient it plans with
GOAL_LAG = 0.3                            # s, the altitude goal's low-pass
HORIZON_KEEP = 0.8                        # below orbit the horizon stays within this share of the half frame
TRACK_AHEAD = (2.0, 60.0)                 # s, m: pure pursuit looks this far along a track
SWAY = (1.5, 0.7)                         # deg, rad/s: the hover's slow roll
ENERGY_SPEED = (0.25, 0.4)                # speed share taken off at energy level -1, added at +1
ENERGY_HOVER = 0.5                        # of BOOST_SPEED added at level +1 while hovering (half the boost)
ENERGY_DIP = 0.2                          # share of the stage height taken off at level +1, low stages only
ENERGY_RATE, ENERGY_ACC = 0.6, 1.5        # per s, per s2: the Flight's own follower on the eased energy (its inertia)
HIT_GAIN, HIT_ATTACK = 2.0, 0.8          # the hit's kick times HIT_GAIN (capped at 1) is a short boost's control,
                                          # with a softer attack than the boost's: it comes on top of a turn
HIT_SWOOP = 1.5                           # the Orbit's and Approach's speed share added at a hit's peak

ORBIT_TILT = 25.0                         # deg: the orbit plane's tilt off the sun's plane, by seed
ORBIT_TURN = 0.02                         # rad/s: how fast the orbit plane turns toward its seeded plane
REGION_AHEAD, REGION_REACH = 30.0, 60.0   # deg: regions within REACH of the point this far ahead on the orbit
REGION_WATER = 2500.0                     # m: water this close to a region's mountains
APPROACH_RING = 4000.0                    # m, the holding circle
SKIM_RING, SKIM_ACROSS = 1800.0, 400.0    # m, the skim loop's radius and how far across it looks for passes
HOVER_SHORE, HOVER_RING = 80.0, (120.0, 700.0)   # m from the shore; loop radius range
HOVER_LOOPS, HOVER_SPREAD = 4, 1500.0     # water loops planned round the Skim ring, at least this far apart; the one
                                          # nearest the camera when f passes the Skim's key is the Hover's
HOVER_ARRIVE = 400.0                      # m: the Skim-to-Hover blend completes only over the water. Further off the
                                          # loop than HOVER_SHORE / 2 + this, the stage in effect stays the Skim (its
                                          # height, lens, pitch) while the camera flies for the water at the Skim's
                                          # speed; it eases into the Hover over this last stretch. (At the 6 m/s drift
                                          # a loop 1.5 km away took 4 minutes, 4 m over dry hillsides.)
HOVER_RELEASE = 300.0                     # m: once on its loop the Hover holds until this much further off it
                                          # (a boost's surge leaves the loop: the 0.4 g turn can't follow it)
HOVER_DECEL = 11.0                         # m/s2: the braking onto the water loop (85 m/s to the drift in 10 s, 450 m)
HOVER_TRANSIT = 125.0                     # m/s: the transit's top speed to far water (the Skim's 85 and most of a boost)
HOVER_TURN = 30.0                         # m/s: the transit's speed with the water abeam or behind (a U-turn of
                                          # 120 m at the Skim's 1.5 g instead of 1 km at 85 m/s); full speed head-on
HOVER_STEER = 1.0 / 48.0                  # of f past the Skim's key over which the steering turns to the water
HOVER_LAND = (45.0, 600.0)                # m: the Hover's height over land: without a water loop, and off its loop
                                          # (a boost) rising to it over HOVER_LAND[1] m past HOVER_SHORE
MOON_CLEAR = 5000.0                       # m off the moon's surface
SENSOR, ASPECT = 36.0, 16.0 / 9.0


# ---------------------------------------------------------------- vectors (tuples, fast in plain Python)
def add(a, b, k=1.0):
    return (a[0] + k * b[0], a[1] + k * b[1], a[2] + k * b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def scale(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def length(a):
    return math.sqrt(dot(a, a))


def norm(a, fallback=(0.0, 0.0, 1.0)):
    n = length(a)
    return scale(a, 1.0 / n) if n > 1e-12 else fallback


def rot(axis, ang, v):
    """v turned by ang about the unit axis (Rodrigues)."""
    c, s = math.cos(ang), math.sin(ang)
    return add(add(scale(v, c), cross(axis, v), s), axis, dot(axis, v) * (1.0 - c))


def angle(a, b):
    return math.acos(min(max(dot(a, b), -1.0), 1.0))


def slerp(a, b, t):
    om = angle(a, b)
    if om < 1e-6:
        return norm(add(scale(a, 1.0 - t), b, t))
    if om > math.pi - 1e-4:            # opposite: turn through any perpendicular
        return rot(norm(cross(a, (1.0, 0.0, 0.0) if abs(a[0]) < 0.9 else (0.0, 1.0, 0.0))), om * t, a)
    s = math.sin(om)
    return add(scale(a, math.sin((1.0 - t) * om) / s), b, math.sin(t * om) / s)


def tangent(u, v):
    """v projected into the tangent plane at u, normalized."""
    return norm(sub(v, scale(u, dot(u, v))), fallback=norm(cross(u, (1.0, 0.0, 0.0))))


def move(u, h, dist):
    """The ground point u moved dist metres along the heading h; returns the new point and heading."""
    ax = cross(u, h)
    a = dist / R
    return norm(rot(ax, a, u)), norm(rot(ax, a, h))


def at_distance(u, h, dist):
    return move(u, h, dist)[0]


# ---------------------------------------------------------------- scalars
def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def smootherstep(t):
    t = clamp(t, 0.0, 1.0)
    return t * t * t * (t * (6.0 * t - 15.0) + 10.0)


def smooth_damp(x, v, target, smooth_time, dt, max_speed=math.inf):
    """Critically damped follower (Game Programming Gems 4, 1.10): C1, no overshoot, speed at most max_speed."""
    st = max(1e-4, smooth_time)
    om = 2.0 / st
    k = om * dt
    e = 1.0 / (1.0 + k + 0.48 * k * k + 0.235 * k * k * k)
    change = clamp(x - target, -max_speed * st, max_speed * st)
    goal = x - change
    tmp = (v + om * change) * dt
    v = (v - om * tmp) * e
    out = goal + (change + tmp) * e
    if (target - x > 0.0) == (out > target):
        out, v = target, 0.0
    return out, v


def glide(x, v, target, v_max, a_max, dt):
    """Follows target with speed at most v_max and acceleration at most a_max, braking in time to stop on it: a jump
    of the target never jumps the speed or the acceleration past the limits (SmoothDamp's acceleration jumps with
    its target)."""
    d = target - x
    want = math.copysign(min(v_max, math.sqrt(2.0 * a_max * max(abs(d) - abs(v) * dt, 0.0)), abs(d) / dt), d)
    v += clamp(want - v, -a_max * dt, a_max * dt)
    if abs(d) < 1e-6 and abs(v) < a_max * dt:
        return target, 0.0
    return x + v * dt, v


def spring(x, v, target, smooth_time, dt):
    """The same critically damped follower without the overshoot guard: for a moving target, where the guard
    would stop the motion dead in one step."""
    om = 2.0 / max(1e-4, smooth_time)
    k = om * dt
    e = 1.0 / (1.0 + k + 0.48 * k * k + 0.235 * k * k * k)
    change = x - target
    tmp = (v + om * change) * dt
    return target + (change + tmp) * e, (v - om * tmp) * e


def weights(f):
    """Stage weights at f: a partition of unity, each stage at 1 on its key, smootherstep between keys (C2)."""
    f = clamp(f, 0.0, 1.0)
    w = [0.0, 0.0, 0.0, 0.0]
    i = min(int(f * 3.0), 2)
    s = smootherstep((f - KEYS[i]) / (KEYS[i + 1] - KEYS[i]))
    w[i], w[i + 1] = 1.0 - s, s
    return w


def pchip(f, keys, vals):
    """Monotone cubic (Fritsch-Carlson) through (keys, vals): C1, no overshoot, and unlike the stage weights it keeps
    moving through a key, so the altitude falls at an even rate across stages instead of in bursts between them."""
    f = clamp(f, keys[0], keys[-1])
    n = len(keys)
    h = [keys[i + 1] - keys[i] for i in range(n - 1)]
    d = [(vals[i + 1] - vals[i]) / h[i] for i in range(n - 1)]
    m = [d[0]] + [0.0 if d[i - 1] * d[i] <= 0.0 else 3.0 * (h[i - 1] + h[i]) / ((2 * h[i] + h[i - 1]) / d[i - 1] + (h[i] + 2 * h[i - 1]) / d[i])
                  for i in range(1, n - 1)] + [d[-1]]
    i = min(int((f - keys[0]) / h[0]), n - 2) if all(abs(x - h[0]) < 1e-12 for x in h) else max(j for j in range(n - 1) if keys[j] <= f)
    t = (f - keys[i]) / h[i]
    t2, t3 = t * t, t * t * t
    return ((2 * t3 - 3 * t2 + 1) * vals[i] + (t3 - 2 * t2 + t) * h[i] * m[i] + (-2 * t3 + 3 * t2) * vals[i + 1]
            + (t3 - t2) * h[i] * m[i + 1])


def curve_log(f, vals):
    return math.exp(pchip(f, KEYS, [math.log(v) for v in vals]))


def mix(w, vals):
    return sum(wi * v for wi, v in zip(w, vals))


def mix_log(w, vals):
    return math.exp(sum(wi * math.log(v) for wi, v in zip(w, vals)))


# ---------------------------------------------------------------- tracks
class GreatCircle:
    """The orbit's ground track: the great circle normal to n."""

    def __init__(self, n, sign=1.0):
        self.n, self.sign = norm(n), sign

    def ahead(self, u, dist, hint=None):
        p = norm(sub(u, scale(self.n, dot(self.n, u))), fallback=norm(cross(self.n, (1.0, 0.0, 0.0))))
        return rot(self.n, self.sign * dist / R, p), None


class SmallCircle:
    """A circle of radius metres around the ground point c (the Approach's holding pattern)."""

    def __init__(self, c, radius, sign=1.0):
        self.c, self.a, self.sign = norm(c), radius / R, sign

    def ahead(self, u, dist, hint=None):
        t = tangent(self.c, u)
        p = add(scale(self.c, math.cos(self.a)), t, math.sin(self.a))
        return rot(self.c, self.sign * dist / (R * math.sin(self.a)), p), None


class Loop:
    """A closed ground track through the unit directions pts."""

    def __init__(self, pts, sign=1.0):
        self.pts = pts if sign > 0 else pts[::-1]
        self.cum = [0.0]
        for i in range(len(self.pts)):
            self.cum.append(self.cum[-1] + R * angle(self.pts[i], self.pts[(i + 1) % len(self.pts)]))
        self.total = self.cum[-1]

    def nearest(self, u, hint=None):
        n = len(self.pts)
        idx = range(n) if hint is None else ((hint + k) % n for k in range(-6, 12))
        return max(idx, key=lambda i: dot(self.pts[i], u))

    def gap(self, u, i):
        """Metres from u to the track near its point i (the two segments through it)."""
        n, a = len(self.pts), self.pts[i]
        best = math.inf
        for b in (self.pts[(i - 1) % n], self.pts[(i + 1) % n]):
            ab = sub(b, a)
            t = clamp(dot(sub(u, a), ab) / max(dot(ab, ab), 1e-18), 0.0, 1.0)
            best = min(best, R * length(sub(u, add(a, ab, t))))
        return best

    def at(self, s):
        s %= self.total
        lo, hi = 0, len(self.pts)
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if self.cum[mid] <= s:
                lo = mid
            else:
                hi = mid
        seg = self.cum[lo + 1] - self.cum[lo]
        t = (s - self.cum[lo]) / seg if seg > 0.0 else 0.0
        return norm(add(scale(self.pts[lo], 1.0 - t), self.pts[(lo + 1) % len(self.pts)], t))

    def ahead(self, u, dist, hint=None):
        i = self.nearest(u, hint)
        return self.at(self.cum[i] + dist), i


def local_frame(c):
    """East and north at the ground point c (any fixed pair works; north follows +y like the runtime's)."""
    e = norm(cross((0.0, 1.0, 0.0), c), fallback=norm(cross((1.0, 0.0, 0.0), c)))
    return e, cross(c, e)


def offset(c, e, n, x, y):
    """The ground point x metres east and y metres north of c (exponential map)."""
    d = math.hypot(x, y)
    if d < 1e-9:
        return c
    return at_distance(c, norm(add(scale(e, x / d), n, y / d)), d)


def periodic_smooth(vals, window, passes):
    n, h = len(vals), window // 2
    for _ in range(passes):
        vals = [sum(vals[(i + k) % n] for k in range(-h, h + 1)) / (2 * h + 1) for i in range(n)]
    return vals


def plan_skim(terrain, c, rng, count=64):
    """A closed loop around the mountains at c: per angle the lowest ground within SKIM_ACROSS across the ring (the
    passes and saddles), smoothed so the loop bends gently."""
    e, n = local_frame(c)
    ring = SKIM_RING * rng.uniform(0.85, 1.15)
    offs = []
    for k in range(count):
        a = 2.0 * math.pi * k / count
        best = min(range(-4, 5), key=lambda j: terrain.surface(offset(c, e, n, (ring + j * SKIM_ACROSS / 4) * math.cos(a),
                                                                        (ring + j * SKIM_ACROSS / 4) * math.sin(a))))
        offs.append(best * SKIM_ACROSS / 4)
    offs = periodic_smooth(offs, 7, 3)
    return [offset(c, e, n, (ring + o) * math.cos(2.0 * math.pi * k / count), (ring + o) * math.sin(2.0 * math.pi * k / count))
            for k, o in enumerate(offs)]


def wet(terrain, u, margin=1.0):
    w = terrain.water(u)
    return w is not None and w > terrain.ground(u) + margin


def plan_hovers(terrain, c, rng, count=48, reach=REGION_WATER, step=125.0, near=None, loops=HOVER_LOOPS):
    """Up to loops closed loops over water near c, at least HOVER_SHORE off any shore and HOVER_SPREAD apart. Each loop's
    centre is a wet point well off the shore (the first nearest the track near, else c, picked among the best few by
    seed; the others the next nearest far enough from those), and the loop is star-shaped round it, each ray stopping
    short of the first dry ground. Empty when there is no water within reach."""
    e, n = local_frame(c)
    m = int(reach / step)
    grid = {}
    for i in range(-m, m + 1):
        for j in range(-m, m + 1):
            grid[i, j] = wet(terrain, offset(c, e, n, i * step, j * step))
    far = {k: 0 if not v else 10 ** 6 for k, v in grid.items()}       # chamfer distance to dry, in cells
    order = sorted(grid)
    for keys in (order, order[::-1]):
        for (i, j) in keys:
            if far[i, j]:
                for di, dj in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
                    k = (i + di, j + dj)
                    if k in far:
                        far[i, j] = min(far[i, j], far[k] + (1.4 if di and dj else 1.0))
                    else:
                        far[i, j] = min(far[i, j], 1.0 + m - max(abs(i), abs(j)) + 1.0)   # past the grid: unknown
    good = [k for k, d in far.items() if d * step >= 2.0 * HOVER_RING[0]]
    if not good:
        return []
    if near:        # the track in c's tangent plane (cells), every fourth point: the Skim ends over the water
        xy = [(R * dot(q, e) / step, R * dot(q, n) / step) for q in near[::4]]
        good.sort(key=lambda k: min(math.hypot(k[0] - x, k[1] - y) for x, y in xy))
    else:
        good.sort(key=lambda k: math.hypot(*k))
    centres = [good[rng.randrange(min(3, len(good)))]]
    for g in good:
        if len(centres) >= loops:
            break
        if all(math.hypot(g[0] - a, g[1] - b) * step >= HOVER_SPREAD for a, b in centres):
            centres.append(g)
    return [hover_loop(terrain, offset(c, e, n, ci * step, cj * step), rng, count) for ci, cj in centres]


def hover_loop(terrain, cw, rng, count):
    ew, nw = local_frame(cw)
    raw = []
    for k in range(count):
        a = 2.0 * math.pi * k / count
        r = 0.0
        while r < HOVER_RING[1] + HOVER_SHORE and wet(terrain, offset(cw, ew, nw, (r + 20.0) * math.cos(a), (r + 20.0) * math.sin(a))):
            r += 20.0
        raw.append(clamp(r - HOVER_SHORE, HOVER_RING[0] * 0.5, HOVER_RING[1]))
    lim = HOVER_RING[1] * rng.uniform(0.6, 1.0)
    eroded = [min(min(raw[(i + k) % count] for k in range(-2, 3)), lim) for i in range(count)]
    rad = [sum(eroded[(i + k) % count] for k in range(-2, 3)) / 5.0 for i in range(count)]
    return [offset(cw, ew, nw, r * math.cos(2.0 * math.pi * k / count), r * math.sin(2.0 * math.pi * k / count))
            for k, r in enumerate(rad)]


# ---------------------------------------------------------------- orbit framing
def lens_for(half_v):
    """Focal length (mm, horizontal sensor fit) whose vertical half field of view is half_v."""
    return (SENSOR / 2.0) / (math.tan(half_v) * ASPECT)


def frame_bodies(cam, bodies):
    """Aim and lens that fit the bodies [(centre, radius)] with 10% margin, the first body first: the others are
    dropped smoothly when they can't fit within a 40 deg half field."""
    dirs = []
    for c, r in bodies:
        v = sub(c, cam)
        d = length(v)
        dirs.append((norm(v), math.asin(min(r / max(d, r + 1.0), 1.0))))

    def fit(ds):
        aim = norm(tuple(sum(d[0][k] * d[1] for d in ds) for k in range(3)))
        need = max(angle(aim, d[0]) + d[1] for d in ds)
        return aim, need

    aim, need = fit(dirs[:1])
    if len(dirs) > 1:
        aim2, need2 = fit(dirs)
        k = smootherstep((math.radians(40.0) - need2) / math.radians(10.0))
        aim, need = norm(add(scale(aim, 1.0 - k), aim2, k)), need + (need2 - need) * k
    return aim, clamp(lens_for(min(need * 1.1, math.radians(60.0))), 12.0, 60.0)


# ---------------------------------------------------------------- the flight
class Flight:
    def __init__(self, terrain, seed=0, sun=(0.0, 1.0, 0.0)):
        self.terrain, self.seed = terrain, seed
        self.f = self.fv = 0.0
        self.b = self.b1 = 0.0
        self.hk = self.hk1 = 0.0
        self.en = self.env_v = 0.0
        self.t = 0.0
        self.region = None            # (index, centre, tracks)
        self.hovers = []              # the region's water loops (Loop)
        self.rng = random.Random(seed)
        self.n_pref = self.orbit_normal(sun)
        self.n = self.n_pref
        self.u = norm(cross(self.n, (0.0, 0.0, 1.0)), fallback=norm(cross(self.n, (1.0, 0.0, 0.0))))
        self.h = norm(cross(self.n, self.u))
        self.rate = 0.0
        self.alt = ALT[ORBIT]
        self.goal = self.env = None
        self.ev = 0.0
        self.fwd = self.up = None
        self.hints = {}
        self.floor_hits = 0
        self.steps = 0
        self.gap = math.inf           # m from the Hover's water loop (inf without one)
        self.fe = 0.0                 # the stage in effect: f, held at the Skim until the camera is over the water
        self.held = False             # the Hover has taken effect over the water (HOVER_RELEASE)
        self.go = 0.0                 # the speed floor that flies to and brakes onto the water loop
        self.cap = None               # m/s, the transit's speed cap: slower while the water is not ahead
        self.alpha = 0.0              # rad, the target's bearing off the heading (last substep)
        self.a_st, self.a_v = None, 0.0  # the stage height, followed: holding the Skim stops its descent, so C1

    def orbit_normal(self, sun):
        """The seeded orbit plane: the plane holding the sun direction, tilted by up to ORBIT_TILT about it."""
        s = norm(sun)
        base = norm(cross(s, (1.0, 0.0, 0.0)), fallback=norm(cross(s, (0.0, 1.0, 0.0))))   # the spin axis +x lies in it
        return rot(s, math.radians(self.rng.uniform(-ORBIT_TILT, ORBIT_TILT)), base)

    # -- regions
    def lock_region(self):
        ahead = at_distance(self.u, self.h, R * math.radians(REGION_AHEAD))
        cands = [(i, c) for i, c in enumerate(self.terrain.candidates()) if math.degrees(angle(c, ahead)) <= REGION_REACH]
        if not cands:
            cands = [min(enumerate(self.terrain.candidates()), key=lambda ic: angle(ic[1], ahead))]
        cands.sort(key=lambda ic: angle(ic[1], ahead))
        idx, c = cands[self.rng.randrange(min(3, len(cands)))]
        sign = self.rng.choice((-1.0, 1.0))
        skim = plan_skim(self.terrain, c, self.rng)
        self.hovers = [Loop(h, sign) for h in plan_hovers(self.terrain, c, self.rng, near=skim)]
        tracks = [None, SmallCircle(c, APPROACH_RING, sign), Loop(skim, sign), None]
        self.region = (idx, c, tracks)
        self.hints = {}

    def reseed(self, sun):
        self.seed += 1
        self.rng = random.Random(self.seed)
        self.region = None
        self.n_pref = self.orbit_normal(sun)

    # -- one frame
    def step(self, dt, flight, boost=0.0, energy=0.0, hit=0.0, sun=(0.0, 1.0, 0.0), moon=None):
        """Advances the flight by dt (in SUBSTEP slices) and returns (position, forward, up, lens, info).
        energy: the eased energy as a level, -1 (none) .. 0 (default) .. 1 (full); hit: the hit's kick, 0..1. The
        hit's wide-angle kick and the pulse are the Director's (energy.accent); here a hit is a surge of speed."""
        n = max(1, int(math.ceil(dt / SUBSTEP)))
        for _ in range(n):
            self.substep(dt / n, flight, boost, energy, hit, sun)
        return self.pose(dt, sun, moon)

    def substep(self, dt, flight, boost, energy, hit, sun):
        self.t += dt
        self.steps += 1
        self.f, self.fv = glide(self.f, self.fv, clamp(flight, 0.0, 1.0), FLIGHT_RATE, FLIGHT_ACC, dt)
        tb = BOOST_ATTACK if boost > self.b1 else BOOST_RELEASE      # two stages: the surge starts without a jolt
        self.b1 += (clamp(boost, 0.0, 1.0) - self.b1) * (1.0 - math.exp(-dt / tb))
        self.b += (self.b1 - self.b) * (1.0 - math.exp(-dt / tb))
        hit = min(HIT_GAIN * hit, 1.0)
        th = HIT_ATTACK if hit > self.hk1 else BOOST_RELEASE
        self.hk1 += (hit - self.hk1) * (1.0 - math.exp(-dt / th))
        self.hk += (self.hk1 - self.hk) * (1.0 - math.exp(-dt / th))
        self.en, self.env_v = glide(self.en, self.env_v, clamp(energy, -1.0, 1.0), ENERGY_RATE, ENERGY_ACC, dt)
        if self.region is not None and self.f < RESEED_BELOW:
            self.reseed(sun)
        if self.region is None and self.f > LOCK_ABOVE:
            self.lock_region()
        wf = weights(self.f)
        tracks = self.region[2] if self.region else [None] * 4
        if self.region is not None:         # the Hover's loop: the water nearest the camera as f passes the Skim
            if self.f <= KEYS[SKIM]:
                tracks[HOVER], self.gap, self.held = None, math.inf, False
            elif tracks[HOVER] is None and self.hovers:
                tracks[HOVER] = min(self.hovers, key=lambda lp: angle(self.u, lp.pts[lp.nearest(self.u)]))
                self.hints.pop(HOVER, None)
        self.fe = self.f
        if self.f > KEYS[SKIM] and tracks[HOVER] is not None:
            self.held = self.held and self.gap < HOVER_RELEASE + HOVER_ARRIVE
            arrive = 1.0 - smootherstep((self.gap - 0.5 * HOVER_SHORE - (HOVER_RELEASE if self.held else 0.0)) / HOVER_ARRIVE)
            self.held = self.held or self.gap <= 0.5 * HOVER_SHORE
            self.fe = KEYS[SKIM] + (self.f - KEYS[SKIM]) * arrive
            # at least the speed that brakes onto the loop at HOVER_DECEL (and back onto it after a boost), at most
            # the transit's; on the loop the drift
            go = min(math.sqrt(SPEED[HOVER] ** 2 + 2.0 * HOVER_DECEL * max(self.gap - 0.5 * HOVER_SHORE, 0.0)), HOVER_TRANSIT)
            cap = HOVER_TURN + (HOVER_TRANSIT - HOVER_TURN) * max(math.cos(self.alpha), 0.0) ** 2
        else:
            go, cap = 0.0, None
        # rate-limited, and not rising during a surge: a boost carrying the camera off its loop must not feed back
        # into its own speed
        rise = 0.0 if max(self.b, self.hk) > 0.05 else 1.2 * HOVER_DECEL * dt
        self.go += clamp(go - self.go, -1.2 * HOVER_DECEL * dt, rise)
        w = self.w = weights(self.fe)
        base = max(mix_log(w, SPEED), self.go)      # the stage in effect's: the Skim's all the way to the water
        acc = 1.2 * HOVER_DECEL * dt                # the cap is followed, and released at that rate after the transit
        if cap is not None:     # not falling during a surge, as the floor does not rise (a boost or hit leaves the loop)
            self.cap = base if self.cap is None else self.cap + clamp(cap - self.cap, 0.0 if max(self.b, self.hk) > 0.05 else -acc, acc)
        elif self.cap is not None:
            self.cap = None if self.cap + acc >= base else self.cap + acc
        if self.cap is not None:
            base = min(base, self.cap)
        low = w[SKIM] + w[HOVER]
        ek = 1.0 + self.en * (ENERGY_SPEED[1] if self.en > 0.0 else ENERGY_SPEED[0])
        swoop = HIT_SWOOP * self.hk * (w[ORBIT] + w[APPROACH])
        v = (base * (ek + swoop) + max(self.b, self.hk) * BOOST_SPEED * low
             + ENERGY_HOVER * BOOST_SPEED * max(self.en, 0.0) * w[HOVER])
        self.v = v

        # the orbit plane turns slowly toward its seeded plane
        ax = cross(self.n, self.n_pref)
        if length(ax) > 1e-9:
            self.n = norm(rot(norm(ax), min(ORBIT_TURN * dt, angle(self.n, self.n_pref)), self.n))

        # pure pursuit toward the weighted stage targets
        look = max(TRACK_AHEAD[0] * v, TRACK_AHEAD[1])
        target = (0.0, 0.0, 0.0)
        wp = list(w)                # past the Skim (the control), it steers for the water
        if self.f > KEYS[SKIM] and tracks[HOVER] is not None:
            wp[HOVER] = smootherstep((self.f - KEYS[SKIM]) / HOVER_STEER)
            wp[SKIM] = 1.0 - wp[HOVER]
        for k, wk in enumerate(wp):
            if wk < 1e-5:
                continue
            tr = GreatCircle(self.n, 1.0 if dot(cross(self.n, self.u), self.h) >= 0.0 else -1.0) if k == ORBIT else tracks[k]
            if tr is None:
                tr = tracks[SKIM] if k == HOVER and tracks[SKIM] else GreatCircle(self.n)
            p, self.hints[k] = tr.ahead(self.u, look, self.hints.get(k))
            target = add(target, p, wk)
        hover = tracks[HOVER]
        if hover is not None:
            self.gap = hover.gap(self.u, hover.nearest(self.u, self.hints.get(HOVER)))
        else:
            self.gap = math.inf
        target = norm(target)
        t_dir = tangent(self.u, target)
        alpha = self.alpha = math.atan2(dot(self.u, cross(self.h, t_dir)), dot(self.h, t_dir))
        # a target further than the look-ahead (a track joined from afar, the water loop) is turned to first, then
        # flown at: pure pursuit's arc through it is dist / (2 sin alpha) wide, a 3 km half circle for a loop abeam
        dist = clamp(R * angle(self.u, target), 1.0, look)
        rmax = mix(w, LAT_ACC) / max(v, 1.0)
        want = math.copysign(rmax, alpha) if abs(alpha) > math.pi / 2.0 else clamp(2.0 * v * math.sin(alpha) / dist, -rmax, rmax)
        self.rate += (want - self.rate) * (1.0 - math.exp(-dt / TURN_LAG))
        self.h = norm(rot(self.u, self.rate * dt, self.h))
        self.u, self.h = move(self.u, self.h, v * dt)

        # altitude = the followed terrain envelope + the stage height A(f). The envelope is a cone hull of the surface
        # around the path (every peak, ahead or just passed, asks for its height less CLIMB per metre away, so it
        # rises and falls at CLIMB * v at most), shifted ahead by the followers' lag, low-passed, then followed.
        # A(f) moves only as smoothly as the damped control; the floor is the guard.
        here = self.terrain.surface(self.u)
        reach = max(ENV_AHEAD[0] * v, ENV_AHEAD[1])
        lead = v * (ALT_SMOOTH + GOAL_LAG)
        env = max(here, self.terrain.surface(at_distance(self.u, self.h, lead)))
        for i in range(ENV_SAMPLES):
            d = reach * (1.5 * i / (ENV_SAMPLES - 1) - 0.5)
            env = max(env, self.terrain.surface(at_distance(self.u, self.h, d + lead)) - CLIMB * abs(d))
        if self.goal is None:
            self.goal = self.env = env
        self.goal += (env - self.goal) * (1.0 - math.exp(-dt / GOAL_LAG))
        self.env, self.ev = spring(self.env, self.ev, self.goal, ALT_SMOOTH, dt)
        floor = here + curve_log(self.fe, H_MIN)
        dip = ENERGY_DIP * max(self.en, 0.0) ** 2 * low       # squared: no kink in the climb rate as it starts
        off = 1.0 if tracks[HOVER] is None else smootherstep((self.gap - HOVER_SHORE) / HOVER_LAND[1])
        land = w[HOVER] * off * (HOVER_LAND[0] - ALT[HOVER])
        a_goal = curve_log(self.fe, ALT) + land
        if self.a_st is None:
            self.a_st = a_goal
        self.a_st, self.a_v = spring(self.a_st, self.a_v, a_goal, ALT_SMOOTH, dt)
        self.alt = self.env + self.a_st * (1.0 - dip)
        if self.alt < floor:
            self.env, self.ev = self.env + floor - self.alt, max(self.ev, 0.0)
            self.alt = floor
            self.floor_hits += 1

    def position(self):
        return add(CENTRE, self.u, R + self.alt)

    def pose(self, dt, sun, moon):
        w = self.w
        p = self.position()
        if moon is not None:                     # keep clear of the moon
            d = sub(p, moon[0])
            need = moon[1] + MOON_CLEAR
            if length(d) < need:
                p = add(moon[0], norm(d), need)
        up_r = norm(sub(p, CENTRE))
        h_la = rot(self.u, self.rate * LOOK_AHEAD, self.h)
        pitch = math.radians(mix(w, PITCH) + BOOST_PITCH * self.b * (w[SKIM] + w[HOVER]))
        fwd = norm(add(scale(h_la, math.cos(pitch)), up_r, math.sin(pitch)))
        lens = mix_log(w, LENS)
        sw = w[ORBIT] * SUBJECT[ORBIT] + w[APPROACH] * SUBJECT[APPROACH]
        if sw > 1e-6:
            bodies = [(CENTRE, R)] + ([moon] if moon is not None else [])
            aim, lens0 = frame_bodies(p, bodies)
            subj = scale(aim, w[ORBIT] * SUBJECT[ORBIT])
            if self.region is not None and w[APPROACH] > 0.0:
                c = self.region[1]
                ground = add(CENTRE, c, R + self.terrain.surface(c))
                subj = add(subj, norm(sub(ground, p)), w[APPROACH] * SUBJECT[APPROACH])
            fwd = slerp(fwd, norm(subj), sw)
            lens = math.exp(math.log(lens) + w[ORBIT] * (math.log(lens0) - math.log(LENS[ORBIT])))
        if w[ORBIT] < 1.0:                       # FL4: the horizon stays in frame below orbit
            hv = math.atan((SENSOR / 2.0) / lens / ASPECT) * HORIZON_KEEP
            dip = -math.acos(min(R / length(sub(p, CENTRE)), 1.0))
            el = math.asin(clamp(dot(fwd, up_r), -1.0, 1.0))
            el2 = clamp(el, dip - hv, dip + hv)
            el = el + (el2 - el) * (1.0 - w[ORBIT])
            flat = tangent(up_r, fwd) if abs(dot(fwd, up_r)) < 0.9999 else self.h
            fwd = norm(add(scale(flat, math.cos(el)), up_r, math.sin(el)))
        low = w[SKIM] + w[HOVER]
        lens = math.exp(math.log(lens) + self.b * low * (math.log(BOOST_LENS) - math.log(lens)))
        bmax = math.radians(mix(w, BANK_MAX))
        bank = clamp(math.atan(self.v * self.rate / G), -bmax, bmax)
        bank += math.radians(SWAY[0]) * w[HOVER] * math.sin(SWAY[1] * self.t)
        up0 = tangent(fwd, up_r) if abs(dot(fwd, up_r)) < 0.999 else tangent(fwd, self.h)
        up = rot(fwd, -bank, up0)
        if self.fwd is None:
            self.fwd = self.fwd2 = fwd
            self.up = self.up2 = up
        k = 1.0 - math.exp(-max(dt, 1e-4) / VIEW_LAG)
        self.fwd2 = norm(add(scale(self.fwd2, 1.0 - k), fwd, k))
        self.fwd = norm(add(scale(self.fwd, 1.0 - k), self.fwd2, k))
        self.up2 = norm(add(scale(self.up2, 1.0 - k), up, k))
        self.up = tangent(self.fwd, add(scale(self.up, 1.0 - k), self.up2, k))
        info = {"f": self.fe, "w": tuple(w), "boost": self.b, "hit": self.hk, "energy": self.en, "speed": self.v, "alt": self.alt,
                "clear": self.alt - self.terrain.surface(self.u), "agl": self.alt - self.terrain.ground(self.u),
                "region": self.region[0] if self.region else None, "seed": self.seed, "floor_hits": self.floor_hits}
        return p, self.fwd, self.up, lens, info
