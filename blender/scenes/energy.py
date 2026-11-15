"""Energy, hit and pulse: how hard every camera moves (docs/research/synthwave-flight.md, "Energy controls").

Pure Python (no bpy), checked by docs/research/synthwave-flight/verify_flight.py (section 7). The scene knows
nothing about music: it eases the incoming controls and turns them into motion. Magic does the mapping.

- Drive eases /vj/energy (rises over RISE, falls over FALL, two first-order stages so a step starts without a
  jolt), fires on a rising edge of /vj/hit over 0.5 and keeps the hit's kick envelope (on the frame it arrives,
  recovering over HIT_RECOVER), and filters the pulse. Its rate is the speed of every camera move: never zero.
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
PULSE_ATTACK, PULSE_RELEASE = 0.08, 0.25   # s: the pyramids' glow (rt_pulse) follows the beat's held peak (released
#                                            over PULSE_RELEASE) at PULSE_ATTACK: a third of the step per frame at 30 fps.
#                                            Following the beat itself, the idle pulse's short spike lifted it to 0.2 and
#                                            the recording showed a 1 % swing. The idle pulse now swings 0.08 to 0.28,
#                                            a full beat reaches 0.62 (review/pulse_check.py)
PULSE_IDLE_GAIN, PULSE_IDLE_FLOOR = 3.0, 0.2    # while the idle pulse runs (no /vj/* for IDLE_AFTER s): rt_pulse =
#                                            glow x GAIN - FLOOR, in 0..1 (0 to 0.74). The idle glow of 0.08 to 0.28 read
#                                            as a 10 % swing on the pyramids, not seen in motion; x 3 alone lifted the
#                                            trough too (21 %), now 27 % by day. Pyramids only: IDLE_DEPTH also drives
#                                            the stars. A Magic beat keeps gain 1 and floor 0, so it gets no whiter
#                                            (review/pulse_check.py, round 18)
BEAT_LENS = 0.0                            # lens push at a full pulse and full energy. Was 0.02: the push moved every
# pixel on every beat, 55 % of the pulse's frame change on a held camera and 59 % of a moving one's at the lake
# (round 16, review/flicker.py A/B); the dip and roll and the flashes stay
BEAT_TILT = math.radians(1.0)              # the dip and roll together at a full pulse and full energy
PERIOD = 20.0                              # s per roll cycle at rate 1


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
        self.glow = 0.0                    # the pyramids' pulse envelope (rt_pulse)
        self.held = 0.0                    # the beat's peak, released over PULSE_RELEASE
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
        self.held = max(self.held * math.exp(-dt / PULSE_RELEASE) if dt > 0.0 else self.held, fl.clamp(beat, 0.0, 1.0))
        self.glow += (self.held - self.glow) * (1.0 - math.exp(-dt / PULSE_ATTACK) if dt > 0.0 else 0.0)
        self.speed = rate(self.e) + HIT_SURGE * self.kick
        self.phase += self.speed * dt
        return self


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
