"""The Director: every shot change is a flight from the rig's current view to the new shot's live view.

Pure Python (no bpy), checked by docs/research/synthwave-flight/verify_flight.py (check 6). The design is in
docs/research/synthwave-flight.md, "Blended shots".

A Pose is (position, forward, up, lens, props): props are the per-shot numbers the scene reads (fog_k, fog_clear,
fog_dip), blended linearly. The runtime samples every shot's live pose each frame (fixed cameras from their
evaluated matrix, the Flight from flight.Flight) and gives the target's pose to step().

- The path runs in planet-centric coordinates and three overlapping phases: the clearance rises on a log curve, the
  ground point traverses by slerp while the camera is high, and the clearance descends onto the target. The peak
  grows with the ground distance and clears the terrain (a crane move nearby, a pull-out toward space across the
  Planet). The duration keeps the ground's flow and the rise under FLOW and the view's turn under TURN.
- Ease: quintic smootherstep, so the blend starts and ends without a jolt. The rig's velocity at the start is carried
  by a Hermite term that fades out, so a change of mind mid-blend never kinks; the end follows the target's own
  motion, so a moving shot is met at its speed.
- The view slerps from the old forward to the new one and, on long hops, bends toward the travel direction
  mid-way. The lens is log-lerped and widened mid-way on long hops. Up is the radial up with the roll blended, so
  the horizon stays level.
- The hit's wide-angle kick and the pulse's accent (energy.accent) go on the rig's pose last, on every shot and
  through blends. The next blend starts from the pose without them, so an accent never carries into a path.
- streamed(): which terrain is on. The Flight's streamed terrain only while the Flight shot is asked for or a running
  blend has it as one side; a fixed shot shows the planet as built.
"""
import math

import energy as en
import flight as fl

DUR_MIN, DUR_MAX = 2.0, 36.0        # s at /vj/blend 1 (a pull-out from the ground to orbit takes the longest)
CARRY = 0.3                         # the start velocity and acceleration are carried over this share of the blend
H0 = 30.0                           # m: heights are blended as log(h + H0)
HUMP_K, HUMP_MAX = 0.5, 30000.0     # hump height per metre of ground distance, and its cap
RISE, TRAVERSE = 0.4, 0.5           # shares of the blend: rising (and descending) at each end, traversing in the middle
FLOW = 1.0                          # rad/s: the ground's flow past the camera (speed over clearance), and e-folds/s of rise
TURN = math.radians(40.0)           # rad/s: the view's turn at the peak
LOOK_TRAVEL, TRAVEL_FROM = 0.4, 2000.0   # how far the view bends toward the travel direction, from this distance on
WIDEN = 0.3                         # the lens widens by up to this share mid-way on long hops
BEND_FLOW = 0.3                     # rad/s of ground flow at which the bend toward travel is full
CLEAR = 20.0                        # m the path keeps over the terrain between its ends
PATH_SAMPLES = 32


def spherical(p):
    rel = fl.sub(p, fl.CENTRE)
    r = fl.length(rel)
    return fl.scale(rel, 1.0 / r), r - fl.R


def ends(pa, pb, terrain):
    """Ground points, surface heights under them and clearances over them, for both ends."""
    ua, ha = spherical(pa)
    ub, hb = spherical(pb)
    sa, sb = (terrain.surface(ua), terrain.surface(ub)) if terrain is not None else (0.0, 0.0)
    return ua, ub, sa, sb, max(ha - sa, 0.0), max(hb - sb, 0.0)


def peak_for(ua, ub, sa, sb, ca, cb, ground, terrain):
    """The log clearance the path rises to: the hump (half the ground distance), clear of the terrain under the
    path (over the straight line between the ends' surfaces), and never below either end."""
    hump = min(HUMP_K * ground, HUMP_MAX)
    if terrain is not None:
        for i in range(1, PATH_SAMPLES):
            e = i / PATH_SAMPLES
            hump = max(hump, terrain.surface(fl.slerp(ua, ub, e)) - (sa + (sb - sa) * e) + CLEAR)
    return max(math.log(hump + H0), math.log(ca + H0), math.log(cb + H0)), hump


def duration(a, b, scale, terrain=None):
    """Blend time for a change from pose a to pose b at /vj/blend scale (0 is a cut): long enough that the ground
    flows past at FLOW at most while traversing, the clearance changes by at most FLOW e-folds a second while rising
    and descending, and the view turns at TURN at most."""
    ua, ub, sa, sb, ca, cb = ends(a[0], b[0], terrain)
    ground = fl.R * fl.angle(ua, ub)
    peak, hump = peak_for(ua, ub, sa, sb, ca, cb, ground, terrain)
    high = math.exp(peak) - H0
    climb = max(peak - math.log(ca + H0), peak - math.log(cb + H0))
    over = 1.875 * ground / (TRAVERSE * FLOW * max(high, H0))
    rise = 1.875 * climb / (RISE * FLOW)
    turn = 1.875 * fl.angle(a[1], b[1]) / TURN
    return scale * fl.clamp(max(over, rise, turn), DUR_MIN, DUR_MAX)


def streamed(flight, shot, sides, blending):
    """True while the Flight's streamed terrain is wanted: flight is the Flight shot's id, shot the one asked for,
    sides the shots of the running blend (Director.sides) and blending whether one runs."""
    return shot == flight or (blending and flight in sides)


def ease(s):
    return fl.smootherstep(s)


def hermite_fade(s):
    """h(0) = 0, h'(0) = 1, h''(0) = 0, and h, h', h'' all 0 at 1 (quintic Hermite): carries the start velocity
    without an acceleration step, then fades out."""
    return s - 6.0 * s ** 3 + 8.0 * s ** 4 - 3.0 * s ** 5


def hermite_fade2(s):
    """h(0) = h'(0) = 0, h''(0) = 1, and h, h', h'' all 0 at 1: carries the start acceleration, so a change of mind
    mid-blend has no acceleration step either."""
    return 0.5 * s * s - 1.5 * s ** 3 + 1.5 * s ** 4 - 0.5 * s ** 5


class Transition:
    def __init__(self, start, v0, target, scale, terrain=None, a0=(0.0, 0.0, 0.0)):
        self.a, self.v0, self.a0 = start, v0, a0
        self.d = duration(start, target, scale, terrain)
        self.t = 0.0
        self.terrain = terrain
        ua, ub, sa, sb, ca, cb = ends(start[0], target[0], terrain)
        self.ground = fl.R * fl.angle(ua, ub)
        self.ra, self.rb = self.roll(start), self.roll(target)
        self.peak = peak_for(ua, ub, sa, sb, ca, cb, self.ground, terrain)[0]

    @staticmethod
    def roll(pose):
        p, fwd, up = pose[0], pose[1], pose[2]
        level = fl.tangent(fwd, fl.norm(fl.sub(p, fl.CENTRE)))
        return math.atan2(fl.dot(fl.cross(level, up), fwd), fl.dot(level, up))

    def done(self):
        return self.t >= self.d

    def path(self, s, target):
        """The base path at time share s (no carried velocity): position and ease. Three overlapping phases: the
        clearance rises (log curve) over the first RISE of the blend, the ground point traverses over the middle
        TRAVERSE while high, the clearance descends over the last RISE. The height is the straight blend of the ends'
        surfaces plus the clearance."""
        e = ease(s)
        eg = ease((s - 0.5 * (1.0 - TRAVERSE)) / TRAVERSE)
        ua, ub, sa, sb, ca, cb = ends(self.a[0], target[0], self.terrain)
        la, lb = math.log(ca + H0), math.log(cb + H0)
        if s < 0.5:
            lc = la + (self.peak - la) * ease(s / RISE)
        else:
            lc = lb + (self.peak - lb) * ease((1.0 - s) / RISE)
        h = sa + (sb - sa) * eg + math.exp(lc) - H0
        return fl.add(fl.CENTRE, fl.slerp(ua, ub, eg), fl.R + h), e

    def pose(self, target):
        """The rig's pose now, for the target's live pose."""
        if self.d <= 0.0 or self.t >= self.d:
            return target
        s = self.t / self.d
        base, e = self.path(s, target)
        sc, dc = min(s / CARRY, 1.0), CARRY * self.d        # carried while the camera is still near its start
        p = fl.add(fl.add(base, self.v0, dc * hermite_fade(sc)), self.a0, dc * dc * hermite_fade2(sc))
        fwd = fl.slerp(self.a[1], target[1], e)
        bend = 4.0 * e * (1.0 - e) * min(1.0, self.ground / TRAVEL_FROM)
        if bend > 1e-4:
            travel = fl.sub(self.path(min(s + 0.01, 1.0), target)[0], base)
            radial0 = fl.norm(fl.sub(base, fl.CENTRE))
            travel = fl.sub(travel, fl.scale(radial0, fl.dot(travel, radial0)))     # its level part: it doesn't tip over the apex
            clear = spherical(base)[1] - (self.terrain.surface(spherical(base)[0]) if self.terrain is not None else 0.0)
            flow = fl.length(travel) / (0.01 * self.d) / max(clear, H0)
            bend *= fl.smootherstep(flow / BEND_FLOW)        # only while the ground really flows by: no flip when it stops
            if fl.length(travel) > 1e-6 and bend > 1e-4:
                travel = fl.norm(travel)
                ahead = fl.clamp((fl.dot(fwd, travel) + 0.2) / 0.7, 0.0, 1.0)     # only toward travel that is ahead
                fwd = fl.slerp(fwd, travel, LOOK_TRAVEL * bend * ahead * ahead)
        radial = fl.norm(fl.sub(p, fl.CENTRE))
        level = fl.tangent(fwd, fl.add(radial, fl.slerp(self.a[2], target[2], e), 0.05))   # a nudge keeps it defined looking straight down
        up = fl.rot(fwd, self.ra + (self.rb - self.ra) * e, level)
        lens = math.exp(math.log(self.a[3]) + (math.log(target[3]) - math.log(self.a[3])) * e) / (1.0 + WIDEN * bend)
        props = {k: self.a[4].get(k, v) + (v - self.a[4].get(k, v)) * e for k, v in target[4].items()}
        return p, fwd, up, lens, props


class Director:
    """The On-Air rig: holds the current pose, starts a Transition on a shot change and steps it."""

    def __init__(self):
        self.shot = None
        self.pose = None                # without the accents
        self.vel = self.acc = (0.0, 0.0, 0.0)
        self.tr = None
        self.sides = frozenset()        # the shots a running blend goes between (a change of mind adds one)

    def step(self, dt, shot, target, scale=1.0, terrain=None, drive=None):
        """shot: the selected shot's id; target: its live pose; drive: an energy.Drive (stepped by the caller) whose
        kick and pulse go on the result. Returns the rig's pose."""
        if self.pose is None:
            self.shot, self.pose = shot, target
            return en.accent(target, drive) if drive is not None else target
        if shot != self.shot:
            self.sides = (self.sides if self.tr is not None else frozenset((self.shot,))) | {shot}
            self.shot = shot
            v0 = fl.add(self.vel, self.acc, 0.5 * dt)     # the backward difference is half a frame old
            self.tr = Transition(self.pose, v0, target, scale, terrain, self.acc) if scale > 0.0 else None
        if self.tr is not None:
            self.tr.t += dt
            new = self.tr.pose(target)
            if self.tr.done():
                self.tr = None
        else:
            new = target
        if dt > 0.0:
            vel = fl.scale(fl.sub(new[0], self.pose[0]), 1.0 / dt)
            self.acc, self.vel = fl.scale(fl.sub(vel, self.vel), 1.0 / dt), vel
        self.pose = new
        return en.accent(new, drive) if drive is not None else new

    def blending(self):
        return self.tr is not None
