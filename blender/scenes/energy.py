"""Energy, hit and pulse: how hard every camera moves (docs/research/synthwave-flight.md, "Energy controls").

Pure Python (no bpy), checked by docs/research/synthwave-flight/verify_flight.py (section 7). The scene knows
nothing about music: it eases the incoming controls and turns them into motion. Magic does the mapping.

- Drive eases /vj/energy (rises over RISE, falls over FALL, two first-order stages so a step starts without a
  jolt), fires on a rising edge of /vj/hit over 0.5 and keeps the hit's kick envelope (on the frame it arrives,
  recovering over HIT_RECOVER), and filters the pulse. Its rate is the speed of every camera move: never zero.
- move() gives a fixed shot its continuous move: an ellipse around its own pose in the view plane, aim held on the
  subject (so the framing holds), a dolly in or out with the energy, the lens tightened with it.
- accent() puts the hit's wide-angle kick and the pulse's push, dip and roll on the On-Air pose (the Director).
"""
import math

import flight as fl

E0 = 0.3                                   # the default energy: today's speeds
RISE, FALL = 1.5, 4.0                      # s to about 95% of a step, up and down
STAGES = 4.74                              # a two-stage follower reaches 95% after 4.74 time constants
RATE_LO, RATE_HI = 0.35, 2.5               # speed of the moves at energy 0 and 1 (about 1 at E0)
HIT_ATTACK, HIT_RECOVER = 0.04, 2.0        # s
HIT_LENS = 0.7                             # the lens at the kick's peak, times the shot's
HIT_SURGE = 3.0                            # extra rate at the kick's peak: a swoop along the move or the path
HIT_KEEP = 4                               # hits whose kicks overlap
BEAT_ATTACK, BEAT_RELEASE = 0.06, 0.25     # s
BEAT_LENS = 0.02                           # lens push at a full pulse and full energy
BEAT_TILT = math.radians(1.0)              # the dip and roll together at a full pulse and full energy
PERIOD = 20.0                              # s per ellipse at rate 1
ORBIT_ANG = math.radians(1.5)              # the ellipse's half width as an angle round the subject
CLEAR_SHARE = 0.15                         # and at most this share of the camera's height over the surface
AMP_MIN = 1.0                              # m, the smallest half width
FLOOR = 2.0                                # m over the surface the move keeps
PUSH = 0.08                                # dolly at energy 1 (and back at 0), share of the subject distance
PUSH_CLEAR = 4.0                           # and at most this many half widths
TIGHT = 0.25                               # log lens change per unit of energy over E0


def level(e):
    """The energy as -1..1 around E0: 0 at the default, 1 at full, -1 at none."""
    return (e - E0) / (1.0 - E0) if e >= E0 else (e - E0) / E0


def rate(e):
    return RATE_LO + (RATE_HI - RATE_LO) * fl.clamp(e, 0.0, 1.0)


def kick_env(age):
    """The kick of one hit, age s after it: rises within HIT_ATTACK, back to 0 at HIT_RECOVER."""
    if age < 0.0 or age >= HIT_RECOVER:
        return 0.0
    return (1.0 - math.exp(-age / HIT_ATTACK)) * (1.0 - fl.smootherstep(age / HIT_RECOVER))


class Drive:
    def __init__(self, energy=E0):
        self.e = self.e1 = energy
        self.prev_hit = 0.0
        self.hits = []                     # ages of the last HIT_KEEP hits
        self.kick = 0.0
        self.beat = 0.0
        self.phase = 0.0                   # the moves' clock: integrates rate and the hit's surge
        self.speed = rate(energy)
        self.fired = False

    def step(self, dt, energy, hit=0.0, beat=0.0):
        tau = (RISE if energy > self.e else FALL) / STAGES
        k = 1.0 - math.exp(-dt / tau) if dt > 0.0 else 0.0
        self.e1 += (fl.clamp(energy, 0.0, 1.0) - self.e1) * k
        self.e += (self.e1 - self.e) * k
        self.fired = hit >= 0.5 > self.prev_hit
        self.prev_hit = hit
        self.hits = [a + dt for a in self.hits if a + dt < HIT_RECOVER]
        if self.fired:
            self.hits = (self.hits + [dt * 0.5])[-HIT_KEEP:]     # half a frame old when it is drawn: starts this frame
        self.kick = max((kick_env(a) for a in self.hits), default=0.0)
        tb = BEAT_ATTACK if beat > self.beat else BEAT_RELEASE
        self.beat += (fl.clamp(beat, 0.0, 1.0) - self.beat) * (1.0 - math.exp(-dt / tb) if dt > 0.0 else 0.0)
        self.speed = rate(self.e) + HIT_SURGE * self.kick
        self.phase += self.speed * dt
        return self


def move(pose, subject, clear, drive, seed=0.0, tighten=True):
    """The shot's pose moved: an ellipse in the view plane round its own position (half widths from the subject
    distance and the height over the surface), aimed back at the subject point `subject` metres down the view, so the
    frame keeps its subject. The dolly and the lens follow the energy. clear: the camera's height over the surface;
    the move stays FLOOR over it."""
    p, fwd, up, lens, props = pose
    right = fl.norm(fl.cross(fwd, up))
    vup = fl.cross(right, fwd)
    aim = fl.add(p, fwd, subject)
    ax = max(min(subject * ORBIT_ANG, CLEAR_SHARE * clear), AMP_MIN)
    ay = min(0.5 * ax, max(clear - FLOOR, 0.1))      # never down to the surface, and never flat (EN1)
    a = 2.0 * math.pi * drive.phase / PERIOD + seed
    x, y = ax * math.cos(a), ay * math.sin(a)
    push = level(drive.e) * min(PUSH * subject, PUSH_CLEAR * ax)
    q = fl.add(fl.add(fl.add(p, right, x), vup, y), fwd, push)
    f2 = fl.norm(fl.sub(aim, q), fwd)
    u2 = fl.tangent(f2, up)
    lens2 = lens * math.exp(TIGHT * (drive.e - E0)) if tighten else lens
    return q, f2, u2, lens2, props


def accent(pose, drive):
    """The pose with the hit's kick and the pulse on it: the lens widens toward HIT_LENS at the kick's peak and pushes
    in by up to BEAT_LENS on a pulse; the view dips and rolls by up to BEAT_TILT. The pulse scales with the energy."""
    p, fwd, up, lens, props = pose
    a = drive.beat * fl.clamp(drive.e, 0.0, 1.0)
    lens2 = lens * (1.0 - (1.0 - HIT_LENS) * drive.kick) * (1.0 + BEAT_LENS * a)
    if a <= 1e-6:
        return p, fwd, up, lens2, props
    right = fl.norm(fl.cross(fwd, up))
    t = BEAT_TILT * a / math.sqrt(2.0)
    roll = t * math.cos(2.0 * math.pi * drive.phase / PERIOD)       # leans with the move
    f2 = fl.rot(right, -t, fwd)
    u2 = fl.rot(f2, roll, fl.rot(right, -t, up))
    return p, f2, u2, lens2, props
