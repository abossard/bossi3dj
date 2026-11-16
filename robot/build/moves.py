"""The Android's Key Poses and Moves as key tables on a beat grid. Pure, no bpy.

A Pose maps a channel to a tuple. Channels ending in `_rot` are Euler XYZ degrees in the bone's own frame;
every rotated bone points up at rest, so x bends forward, y twists counter-clockwise seen from above and z
leans to the Android's right (for a foot: x points the toe down, y turns the toe counter-clockwise). The other
channels are absolute positions in metres in the rig's root space: Z up, the Android faces -Y, its left is +X.
`hips` is the hips joint, `hand_*` the wrist and `foot_*` the ankle (IK targets). A planted ankle sits at 0.10.

A Move lasts 4, 8 or 16 beats (1, 2 or 4 bars). Keys sit on beats; the frame of beat b is b x 60 / bpm x fps.
The last key is pulled onto the last frame, so a Clip's first and last frame show its Key Poses. Between keys
every channel eases with smoothstep. A foot moves only off the ground: two keys in a row with the same foot at
0.10 hold it in place.

    python3 -m unittest discover robot/build/tests
"""
import math
from collections import namedtuple

BPM = 124
FPS = 30
BEATS = 4
ANKLE_Z = 0.10

Move = namedtuple("Move", "name tier beats key_in key_out keys hits idle waves", defaults=(False, ()))
Wave = namedtuple("Wave", "channel axis amplitude harmonic")
Key = namedtuple("Key", "beat pose")
Hit = namedtuple("Hit", "beat limb strength")

GUARD = {
    "hips": (0.0, 0.02, 0.91),
    "hips_rot": (0.0, -25.0, 0.0),
    "spine_rot": (6.0, -5.0, 0.0),
    "chest_rot": (6.0, 0.0, 0.0),
    "head_rot": (-8.0, 22.0, 0.0),
    "hand_l": (0.15, -0.42, 1.50),
    "hand_r": (-0.10, -0.20, 1.52),
    "foot_l": (0.15, -0.24, ANKLE_Z),
    "foot_l_rot": (0.0, -15.0, 0.0),
    "foot_r": (-0.15, 0.30, ANKLE_Z),
    "foot_r_rot": (0.0, -45.0, 0.0),
}
CHANNELS = tuple(GUARD)


def pose(base, **changes):
    """A full Pose: `base` with some channels replaced. Unknown channels raise."""
    unknown = set(changes) - set(CHANNELS)
    if unknown:
        raise KeyError("unknown channels: %s" % ", ".join(sorted(unknown)))
    out = dict(base)
    out.update({k: tuple(float(x) for x in v) for k, v in changes.items()})
    return out


def shifted(base, dy):
    """`base` moved dy metres along Y (toward the back for dy > 0): hips, hands and feet."""
    return pose(base, **{c: (base[c][0], base[c][1] + dy, base[c][2])
                         for c in ("hips", "hand_l", "hand_r", "foot_l", "foot_r")})


def is_rotation(channel):
    return channel.endswith("_rot")


# wide power stance, squared to the front, fists low and wide
LOW = pose(GUARD, hips=(0.0, 0.0, 0.76), hips_rot=(0.0, 0.0, 0.0), spine_rot=(10.0, 0.0, 0.0),
           chest_rot=(4.0, 0.0, 0.0), head_rot=(-12.0, 0.0, 0.0),
           hand_l=(0.30, -0.30, 1.05), hand_r=(-0.30, -0.30, 1.05),
           foot_l=(0.36, -0.05, ANKLE_Z), foot_l_rot=(0.0, 20.0, 0.0),
           foot_r=(-0.36, -0.05, ANKLE_Z), foot_r_rot=(0.0, -20.0, 0.0))
# landing crouch: deep, staggered feet, rear fist down by the floor, lead arm back
CROUCH = pose(GUARD, hips=(0.0, 0.10, 0.50), hips_rot=(25.0, -10.0, 0.0), spine_rot=(25.0, -5.0, 0.0),
              chest_rot=(10.0, 0.0, 0.0), head_rot=(-35.0, 10.0, 0.0),
              hand_l=(0.40, 0.05, 0.95), hand_r=(-0.16, -0.36, 0.32),
              foot_l=(0.22, -0.22, ANKLE_Z), foot_l_rot=(0.0, -10.0, 0.0),
              foot_r=(-0.24, 0.28, ANKLE_Z), foot_r_rot=(0.0, -30.0, 0.0))
KEY_POSES = {"guard": GUARD, "low": LOW, "crouch": CROUCH}

# the bob: weight settles a little between beats, so a held guard never freezes
BOB = pose(GUARD, hips=(0.0, 0.02, 0.895), hand_l=(0.15, -0.42, 1.49), hand_r=(-0.10, -0.20, 1.51))

# punches from the guard, shared by the guard's striking Moves
JAB = pose(GUARD, hips=(0.0, 0.0, 0.90), hips_rot=(0.0, -32.0, 0.0), spine_rot=(8.0, -8.0, 0.0),
           chest_rot=(6.0, -6.0, 0.0), head_rot=(-8.0, 30.0, 0.0),
           hand_l=(0.10, -0.86, 1.52), hand_r=(-0.08, -0.22, 1.54))
JAB_BACK = pose(GUARD, hips=(0.0, 0.01, 0.90), hand_l=(0.15, -0.44, 1.51))
CROSS_LOAD = pose(GUARD, hips=(0.0, 0.0, 0.90), hips_rot=(0.0, -28.0, 0.0), spine_rot=(7.0, -7.0, 0.0),
                  hand_l=(0.14, -0.40, 1.52), hand_r=(-0.10, -0.18, 1.52))
CROSS = pose(GUARD, hips=(0.0, -0.04, 0.89), hips_rot=(0.0, 10.0, 0.0), spine_rot=(10.0, 12.0, 0.0),
             chest_rot=(6.0, 8.0, 0.0), head_rot=(-8.0, -10.0, 0.0),
             hand_l=(0.12, -0.36, 1.52), hand_r=(-0.02, -0.88, 1.52),
             foot_r=(-0.15, 0.30, 0.14), foot_r_rot=(12.0, -5.0, 0.0))
CROSS_BACK = pose(GUARD, hips=(0.0, -0.01, 0.90), hips_rot=(0.0, -12.0, 0.0), spine_rot=(7.0, 2.0, 0.0),
                  head_rot=(-8.0, 8.0, 0.0), hand_r=(-0.06, -0.40, 1.50),
                  foot_r=(-0.15, 0.30, 0.12), foot_r_rot=(6.0, -25.0, 0.0))
HOOK_LOAD = pose(GUARD, hips=(0.0, 0.01, 0.90), hips_rot=(0.0, -12.0, 0.0), spine_rot=(7.0, 0.0, 0.0),
                 hand_l=(0.24, -0.36, 1.48))
HOOK = pose(GUARD, hips=(0.0, 0.0, 0.89), hips_rot=(0.0, -45.0, 0.0), spine_rot=(8.0, -15.0, 0.0),
            chest_rot=(6.0, -10.0, 0.0), head_rot=(-8.0, 35.0, 0.0), hand_l=(-0.15, -0.55, 1.50))
HOOK_BACK = pose(GUARD, hips=(0.0, 0.01, 0.90), hips_rot=(0.0, -30.0, 0.0), hand_l=(0.10, -0.45, 1.50))
# a fist raised overhead for the two-handed slams
FLEX = dict(hand_l=(0.42, -0.05, 1.42), hand_r=(-0.42, -0.05, 1.42), chest_rot=(-6.0, 0.0, 0.0))


def _idle(name, key, waves):
    """An Idle Clip: each wave is a (1 - cos) term over the whole Clip, so it starts and ends at the Key Pose with
    zero speed and the identical first and last frames loop without a seam."""
    return Move(name, "calm", BEATS, key, key, [Key(0, KEY_POSES[key]), Key(BEATS, KEY_POSES[key])], [], True,
                tuple(Wave(*w) for w in waves))


def _idles():
    return [
        _idle("idle_guard", "guard", (("hips", 2, -0.02, 2), ("chest_rot", 0, 2.5, 2),       # breathing
                                      ("hand_l", 2, -0.015, 2), ("hand_r", 2, -0.012, 2),
                                      ("hips", 0, 0.015, 1), ("hips_rot", 1, 2.0, 1),        # weight shift
                                      ("head_rot", 1, 6.0, 1), ("head_rot", 0, -2.0, 3),     # servo glances
                                      ("hand_l", 1, 0.015, 1), ("hand_r", 0, 0.01, 3))),
        _idle("idle_low", "low", (("hips", 2, -0.025, 2), ("chest_rot", 0, 3.0, 2),
                                  ("hand_l", 2, -0.02, 2), ("hand_r", 2, -0.02, 2),
                                  ("head_rot", 1, 15.0, 1), ("head_rot", 0, -3.0, 3),        # slow scan
                                  ("hips_rot", 1, 3.0, 1), ("hand_l", 0, 0.02, 1), ("hand_r", 0, -0.02, 1))),
        _idle("idle_crouch", "crouch", (("hips", 2, -0.015, 2), ("chest_rot", 0, 2.0, 2),
                                        ("head_rot", 1, 12.0, 1), ("head_rot", 0, -3.0, 2),
                                        ("hand_l", 1, 0.03, 1), ("hand_l", 2, -0.02, 2))),
    ]


# ---------- calm ----------

def _guard_shuffle():
    fwd = shifted(GUARD, -0.16)
    keys = [Key(0, GUARD), Key(1, BOB),
            Key(1.5, pose(GUARD, hips=(0.0, -0.02, 0.91), foot_l=(0.15, -0.32, 0.18))),
            Key(2, pose(GUARD, hips=(0.0, -0.06, 0.90), foot_l=(0.15, -0.40, ANKLE_Z))),
            Key(2.5, pose(fwd, foot_r=(-0.15, 0.22, 0.17))),
            Key(3, fwd), Key(3.75, pose(fwd, head_rot=(-8.0, 40.0, 0.0))),
            Key(4.5, pose(fwd, head_rot=(-8.0, 0.0, 0.0))), Key(5, fwd),
            Key(5.5, pose(fwd, hips=(0.0, -0.10, 0.91), foot_r=(-0.15, 0.22, 0.17))),
            Key(6, pose(fwd, hips=(0.0, -0.06, 0.90), foot_r=(-0.15, 0.30, ANKLE_Z), foot_r_rot=(0.0, -45.0, 0.0))),
            Key(6.5, pose(GUARD, hips=(0.0, -0.02, 0.91), foot_l=(0.15, -0.32, 0.18))),
            Key(7, GUARD), Key(7.5, BOB), Key(8, GUARD)]
    return Move("guard_shuffle", "calm", 8, "guard", "guard", keys, [])


def _settle_low():
    r_down = pose(GUARD, hips=(0.0, 0.0, 0.84), hips_rot=(0.0, -10.0, 0.0),
                  hand_l=(0.22, -0.35, 1.30), hand_r=(-0.20, -0.30, 1.30),
                  foot_r=LOW["foot_r"], foot_r_rot=LOW["foot_r_rot"])
    keys = [Key(0, GUARD), Key(1, BOB),
            Key(2, pose(GUARD, hips=(0.0, 0.0, 0.90), head_rot=(-8.0, 10.0, 0.0),
                        foot_r=(-0.22, 0.18, 0.22), foot_r_rot=(0.0, -30.0, 0.0))),
            Key(2.75, r_down),
            Key(3.5, pose(r_down, hips=(-0.03, 0.0, 0.84), foot_l=(0.28, -0.12, 0.20), foot_l_rot=(0.0, 5.0, 0.0))),
            Key(4.25, pose(LOW, hips=(0.0, 0.0, 0.80), hips_rot=(0.0, -5.0, 0.0), spine_rot=(8.0, 0.0, 0.0),
                           hand_l=(0.25, -0.33, 1.20), hand_r=(-0.25, -0.30, 1.20))),
            Key(5, pose(LOW, hips=(0.0, 0.0, 0.74), hand_l=(0.38, -0.20, 1.10), hand_r=(-0.38, -0.20, 1.10))),
            Key(6, pose(LOW, head_rot=(-12.0, 25.0, 0.0))), Key(7, pose(LOW, head_rot=(-12.0, -20.0, 0.0))),
            Key(8, LOW)]
    return Move("settle_low", "calm", 8, "guard", "low", keys, [])


def _rise_guard():
    keys = [Key(0, LOW),
            Key(0.75, pose(LOW, hips=(0.03, 0.0, 0.80), hand_l=(0.22, -0.38, 1.30), hand_r=(-0.20, -0.28, 1.30),
                           foot_l=(0.28, -0.15, 0.20), foot_l_rot=(0.0, 0.0, 0.0))),
            Key(1.5, pose(LOW, hips=(0.02, 0.0, 0.84), hips_rot=(0.0, -15.0, 0.0),
                          hand_l=(0.17, -0.40, 1.42), hand_r=(-0.12, -0.24, 1.42),
                          foot_l=GUARD["foot_l"], foot_l_rot=GUARD["foot_l_rot"])),
            Key(2, pose(GUARD, hips=(-0.02, 0.02, 0.86), foot_r=(-0.25, 0.15, 0.20), foot_r_rot=(0.0, -35.0, 0.0))),
            Key(2.75, pose(GUARD, hips=(0.0, 0.02, 0.89))), Key(3.5, BOB), Key(4, GUARD)]
    return Move("rise_guard", "calm", 4, "low", "guard", keys, [])


def _low_scan():
    twist_l = pose(LOW, hips_rot=(0.0, 12.0, 0.0), spine_rot=(10.0, 15.0, 0.0), head_rot=(-12.0, 30.0, 0.0),
                   hand_l=(0.20, -0.36, 1.05), hand_r=(-0.36, -0.18, 1.05))
    twist_r = pose(LOW, hips_rot=(0.0, -12.0, 0.0), spine_rot=(10.0, -15.0, 0.0), head_rot=(-12.0, -30.0, 0.0),
                   hand_l=(0.36, -0.18, 1.05), hand_r=(-0.20, -0.36, 1.05))
    flex = pose(LOW, spine_rot=(4.0, 0.0, 0.0), head_rot=(-18.0, 0.0, 0.0), **FLEX)
    keys = [Key(0, LOW), Key(2, twist_l), Key(4, LOW), Key(6, twist_r), Key(8, LOW), Key(9.5, flex),
            Key(11, pose(flex, head_rot=(-22.0, 10.0, 0.0))), Key(12.5, LOW),
            Key(13.5, pose(LOW, hips=(0.0, 0.0, 0.72))), Key(14.5, pose(LOW, hips=(0.0, 0.0, 0.78))), Key(16, LOW)]
    return Move("low_scan", "calm", 16, "low", "low", keys, [])


def _stand_up():
    rise = pose(CROUCH, hips=(0.0, 0.04, 0.86), hips_rot=(5.0, -20.0, 0.0), spine_rot=(8.0, -5.0, 0.0),
                chest_rot=(6.0, 0.0, 0.0), head_rot=(-10.0, 20.0, 0.0),
                hand_l=(0.20, -0.36, 1.38), hand_r=(-0.12, -0.20, 1.40))
    keys = [Key(0, CROUCH), Key(1, pose(CROUCH, head_rot=(-40.0, 20.0, 0.0), hand_r=(-0.18, -0.30, 0.55))),
            Key(2.5, pose(CROUCH, hips=(0.0, 0.06, 0.70), hips_rot=(12.0, -15.0, 0.0), spine_rot=(15.0, -5.0, 0.0),
                          head_rot=(-20.0, 15.0, 0.0), hand_l=(0.25, -0.30, 1.00), hand_r=(-0.20, -0.25, 1.00))),
            Key(4, rise),
            Key(4.75, pose(rise, foot_l=(0.18, -0.24, 0.18), foot_l_rot=(0.0, -12.0, 0.0))),
            Key(5.25, pose(rise, foot_l=GUARD["foot_l"], foot_l_rot=GUARD["foot_l_rot"])),
            Key(5.75, pose(rise, hips=(0.0, 0.03, 0.88), foot_l=GUARD["foot_l"], foot_l_rot=GUARD["foot_l_rot"],
                           foot_r=(-0.20, 0.30, 0.18), foot_r_rot=(0.0, -38.0, 0.0))),
            Key(6.25, pose(GUARD, hips=(0.0, 0.02, 0.90))), Key(7, pose(GUARD, chest_rot=(6.0, 0.0, 6.0))),
            Key(7.5, BOB), Key(8, GUARD)]
    return Move("stand_up", "calm", 8, "crouch", "guard", keys, [])


# ---------- build ----------

def _jab_cross():
    keys = [Key(0, GUARD), Key(0.7, BOB), Key(1.0, JAB), Key(1.3, JAB_BACK), Key(1.7, CROSS_LOAD),
            Key(2.0, CROSS), Key(2.5, CROSS_BACK), Key(3.0, GUARD), Key(3.5, BOB), Key(4, GUARD)]
    return Move("jab_cross", "build", 4, "guard", "guard", keys, [Hit(1.0, "hand_l", 0.6), Hit(2.0, "hand_r", 1.0)])


def _take_hit():
    impact = pose(GUARD, hips=(0.0, 0.08, 0.90), spine_rot=(-6.0, -5.0, 0.0), chest_rot=(-12.0, 0.0, 4.0),
                  head_rot=(-30.0, 35.0, 8.0), hand_l=(0.22, -0.30, 1.46), hand_r=(-0.16, -0.10, 1.44))
    stagger = pose(GUARD, hips=(0.0, 0.20, 0.86), hips_rot=(-8.0, -20.0, 0.0), spine_rot=(-10.0, -5.0, 0.0),
                   chest_rot=(-8.0, 0.0, 6.0), head_rot=(-20.0, 30.0, 10.0),
                   hand_l=(0.30, -0.10, 1.25), hand_r=(-0.30, 0.10, 1.22))
    recover = pose(GUARD, hips=(0.0, 0.06, 0.88), spine_rot=(12.0, -5.0, 0.0), chest_rot=(8.0, 0.0, 0.0),
                   head_rot=(0.0, 22.0, -6.0), hand_l=(0.18, -0.36, 1.40), hand_r=(-0.12, -0.18, 1.42))
    keys = [Key(0, GUARD), Key(0.8, BOB), Key(1.0, impact), Key(1.4, stagger), Key(2.25, recover),
            Key(3.0, GUARD), Key(3.5, BOB), Key(4, GUARD)]
    return Move("take_hit", "build", 4, "guard", "guard", keys, [Hit(1.0, "head", 1.0)])


def _jab_jab_hook():
    keys = [Key(0, GUARD), Key(0.6, BOB), Key(1.0, JAB), Key(1.25, JAB_BACK), Key(1.5, JAB), Key(1.8, JAB_BACK),
            Key(2.25, HOOK_LOAD), Key(2.5, HOOK), Key(2.9, HOOK_BACK), Key(3.5, CROSS_LOAD), Key(4.0, CROSS),
            Key(4.5, CROSS_BACK), Key(5.0, GUARD), Key(5.5, BOB), Key(6.0, GUARD),
            Key(6.5, pose(GUARD, head_rot=(-8.0, 35.0, 0.0))), Key(7.0, GUARD), Key(7.5, BOB), Key(8, GUARD)]
    hits = [Hit(1.0, "hand_l", 0.6), Hit(1.5, "hand_l", 0.6), Hit(2.5, "hand_l", 0.8), Hit(4.0, "hand_r", 1.0)]
    return Move("jab_jab_hook", "build", 8, "guard", "guard", keys, hits)


def _palm_strike():
    load = pose(LOW, hips=(0.0, 0.02, 0.74), spine_rot=(4.0, 0.0, 0.0),
                hand_l=(0.30, 0.05, 1.00), hand_r=(-0.30, 0.05, 1.00))
    strike = pose(LOW, hips=(0.0, -0.06, 0.76), spine_rot=(18.0, 0.0, 0.0), head_rot=(-16.0, 0.0, 0.0),
                  hand_l=(0.18, -0.80, 1.20), hand_r=(-0.18, -0.80, 1.20))
    keys = [Key(0, LOW), Key(0.6, load), Key(1.0, strike),
            Key(1.4, pose(strike, hand_l=(0.25, -0.50, 1.15), hand_r=(-0.25, -0.50, 1.15))), Key(2.0, load),
            Key(2.5, pose(strike, hand_l=(0.18, -0.80, 1.35), hand_r=(-0.18, -0.80, 1.35))),
            Key(3.0, LOW), Key(3.5, pose(LOW, hips=(0.0, 0.0, 0.74))), Key(4, LOW)]
    return Move("palm_strike", "build", 4, "low", "low", keys, [Hit(1.0, "hand_l", 0.8), Hit(2.5, "hand_r", 0.8)])


def _elbow_rush():
    step_in = pose(GUARD, hips=(0.0, -0.05, 0.84), hips_rot=(0.0, -20.0, 0.0), foot_r=LOW["foot_r"],
                   foot_r_rot=LOW["foot_r_rot"], hand_l=(0.18, -0.40, 1.45), hand_r=(-0.14, -0.22, 1.45))
    elbow = pose(step_in, hips=(0.0, -0.08, 0.86), hips_rot=(0.0, 20.0, 0.0), spine_rot=(10.0, 15.0, 0.0),
                 chest_rot=(6.0, 10.0, 0.0), head_rot=(-8.0, -5.0, 0.0), hand_r=(0.05, -0.35, 1.55))
    keys = [Key(0, LOW), Key(1, pose(LOW, hips=(-0.05, 0.0, 0.76))),
            Key(1.5, pose(LOW, hips=(-0.05, -0.02, 0.80), foot_l=(0.30, -0.25, 0.22), foot_l_rot=(0.0, 0.0, 0.0),
                          hand_l=(0.20, -0.36, 1.30), hand_r=(-0.20, -0.25, 1.30))),
            Key(2.0, step_in), Key(2.5, elbow), Key(3.25, step_in),
            Key(4.0, pose(step_in, foot_r=(-0.25, 0.10, 0.20), foot_r_rot=(0.0, -35.0, 0.0))),
            Key(4.75, pose(GUARD, hips=(0.0, 0.0, 0.89))), Key(5.5, pose(GUARD, head_rot=(-8.0, 35.0, 0.0))),
            Key(6, BOB), Key(7, GUARD), Key(7.5, BOB), Key(8, GUARD)]
    return Move("elbow_rush", "build", 8, "low", "guard", keys, [Hit(2.5, "hand_r", 0.9)])


def _crouch_strike():
    keys = [Key(0, CROUCH), Key(0.6, pose(CROUCH, hand_l=(0.30, -0.05, 0.85))),
            Key(1.0, pose(CROUCH, hips=(0.0, 0.06, 0.52), hand_l=(0.10, -0.75, 0.55), head_rot=(-30.0, 0.0, 0.0))),
            Key(1.3, pose(CROUCH, hand_l=(0.30, -0.20, 0.80))),
            Key(2.0, pose(CROUCH, hips=(0.0, 0.06, 0.52), hand_l=(0.15, -0.78, 0.65), head_rot=(-30.0, 0.0, 0.0))),
            Key(2.4, pose(CROUCH, hand_l=(0.32, -0.10, 0.85))), Key(3.0, CROUCH),
            Key(3.5, pose(CROUCH, hips=(0.0, 0.10, 0.48))), Key(4, CROUCH)]
    return Move("crouch_strike", "build", 4, "crouch", "crouch", keys,
                [Hit(1.0, "hand_l", 0.7), Hit(2.0, "hand_l", 0.8)])


# ---------- drop ----------

def _front_kick():
    dip = pose(GUARD, hips=(0.0, 0.02, 0.89))
    shift = pose(GUARD, hips=(0.0, 0.12, 0.93), hips_rot=(-4.0, -15.0, 0.0), spine_rot=(-6.0, -5.0, 0.0),
                 chest_rot=(0.0, 0.0, 0.0), head_rot=(4.0, 15.0, 0.0),
                 hand_l=(0.17, -0.34, 1.54), hand_r=(-0.10, -0.14, 1.56))
    chamber = pose(shift, hips=(0.0, 0.14, 0.94), foot_l=(0.12, -0.30, 0.62), foot_l_rot=(-30.0, -5.0, 0.0))
    extend = pose(shift, hips=(0.0, 0.16, 0.95), hips_rot=(-12.0, -15.0, 0.0), spine_rot=(-10.0, -5.0, 0.0),
                  head_rot=(10.0, 15.0, 0.0), hand_l=(0.20, -0.30, 1.50), hand_r=(-0.14, -0.06, 1.54),
                  foot_l=(0.12, -0.78, 0.95), foot_l_rot=(-40.0, -5.0, 0.0))
    rechamber = pose(chamber, foot_l=(0.12, -0.34, 0.60))
    planted = pose(GUARD, hips=(0.0, 0.0, 0.90), spine_rot=(8.0, -5.0, 0.0))
    keys = [Key(0, GUARD), Key(0.75, dip), Key(1.5, shift), Key(1.75, chamber), Key(2.0, extend),
            Key(2.3, rechamber), Key(2.75, pose(GUARD, hips=(0.0, 0.04, 0.90))), Key(3.25, planted),
            Key(3.6, BOB), Key(4, GUARD)]
    return Move("front_kick", "drop", 4, "guard", "guard", keys, [Hit(2.0, "foot_l", 1.0)])


def _uppercut_combo():
    dip = pose(GUARD, hips=(0.0, 0.02, 0.84), spine_rot=(14.0, -5.0, 0.0), hand_r=(-0.12, -0.25, 1.25))
    upper_r = pose(GUARD, hips=(0.0, -0.03, 0.95), hips_rot=(0.0, 8.0, 0.0), spine_rot=(-4.0, 10.0, 0.0),
                   head_rot=(-14.0, -5.0, 0.0), hand_r=(-0.02, -0.55, 1.85),
                   foot_r=(-0.15, 0.30, 0.14), foot_r_rot=(12.0, -10.0, 0.0))
    upper_r_back = pose(GUARD, hips=(0.0, 0.0, 0.91), hand_r=(-0.08, -0.28, 1.55),
                        foot_r=(-0.15, 0.30, 0.12), foot_r_rot=(6.0, -30.0, 0.0))
    dip_l = pose(GUARD, hips=(0.0, 0.02, 0.84), spine_rot=(14.0, -12.0, 0.0), hand_l=(0.16, -0.38, 1.25))
    upper_l = pose(GUARD, hips=(0.0, -0.02, 0.95), hips_rot=(0.0, -40.0, 0.0), spine_rot=(-4.0, -10.0, 0.0),
                   head_rot=(-14.0, 30.0, 0.0), hand_l=(0.05, -0.55, 1.85))
    keys = [Key(0, GUARD), Key(0.5, dip), Key(1.0, upper_r), Key(1.4, upper_r_back), Key(1.75, HOOK_LOAD),
            Key(2.0, HOOK), Key(2.4, HOOK_BACK), Key(2.75, dip_l), Key(3.0, upper_l), Key(3.4, JAB_BACK),
            Key(3.75, BOB), Key(4, GUARD)]
    return Move("uppercut_combo", "drop", 4, "guard", "guard", keys,
                [Hit(1.0, "hand_r", 1.0), Hit(2.0, "hand_l", 0.8), Hit(3.0, "hand_l", 1.0)])


def _leap_slam():
    wind = pose(GUARD, hips=(0.0, 0.05, 0.64), hips_rot=(15.0, -10.0, 0.0), spine_rot=(20.0, -5.0, 0.0),
                head_rot=(-20.0, 10.0, 0.0), hand_l=(0.35, 0.25, 1.00), hand_r=(-0.35, 0.25, 1.00))
    takeoff = pose(GUARD, hips=(0.0, 0.0, 1.05), hips_rot=(0.0, -10.0, 0.0), spine_rot=(-8.0, 0.0, 0.0),
                   head_rot=(-15.0, 10.0, 0.0), hand_l=(0.30, -0.20, 1.95), hand_r=(-0.30, -0.20, 1.95),
                   foot_l=(0.15, -0.24, 0.16), foot_l_rot=(25.0, -15.0, 0.0),
                   foot_r=(-0.15, 0.30, 0.16), foot_r_rot=(25.0, -40.0, 0.0))
    apex = pose(takeoff, hips=(0.0, 0.05, 1.55), hips_rot=(-10.0, -10.0, 0.0), spine_rot=(-10.0, 0.0, 0.0),
                hand_l=(0.25, -0.25, 2.30), hand_r=(-0.25, -0.25, 2.30),
                foot_l=(0.18, -0.30, 1.00), foot_l_rot=(-30.0, -10.0, 0.0),
                foot_r=(-0.18, 0.15, 0.95), foot_r_rot=(-20.0, -25.0, 0.0))
    fall = pose(apex, hips=(0.0, 0.08, 1.25), spine_rot=(10.0, 0.0, 0.0),
                hand_l=(0.22, -0.40, 1.45), hand_r=(-0.22, -0.40, 1.45),
                foot_l=(0.22, -0.22, 0.60), foot_l_rot=(0.0, -10.0, 0.0),
                foot_r=(-0.24, 0.28, 0.60), foot_r_rot=(0.0, -30.0, 0.0))
    reach = pose(fall, hips=(0.0, 0.10, 0.95), spine_rot=(20.0, -5.0, 0.0), hand_l=(0.20, -0.45, 0.75),
                 hand_r=(-0.20, -0.45, 0.75), foot_l=(0.22, -0.22, 0.25), foot_r=(-0.24, 0.28, 0.25))
    slam = pose(CROUCH, hips=(0.0, 0.10, 0.44), spine_rot=(32.0, -5.0, 0.0), head_rot=(-30.0, 0.0, 0.0),
                hand_l=(0.16, -0.38, 0.30))
    keys = [Key(0, GUARD), Key(1, BOB), Key(2, wind), Key(2.6, takeoff), Key(3.0, apex), Key(3.4, fall),
            Key(3.7, reach), Key(4.0, slam), Key(4.4, pose(CROUCH, hips=(0.0, 0.10, 0.52), hand_l=(0.24, -0.20, 0.60))),
            Key(5, pose(CROUCH, head_rot=(-40.0, 0.0, 0.0))), Key(6, pose(CROUCH, head_rot=(-35.0, 30.0, 0.0))),
            Key(7, pose(CROUCH, hips=(0.0, 0.10, 0.48))), Key(8, CROUCH)]
    return Move("leap_slam", "drop", 8, "guard", "crouch", keys, [Hit(4.0, "hand_r", 1.0), Hit(4.0, "foot_l", 0.8)])


def _ground_pound():
    up = pose(CROUCH, hips=(0.0, 0.08, 0.55), hips_rot=(10.0, -10.0, 0.0), spine_rot=(0.0, 0.0, 0.0),
              chest_rot=(-10.0, 0.0, 0.0), head_rot=(-20.0, 10.0, 0.0),
              hand_l=(0.25, -0.10, 1.40), hand_r=(-0.25, -0.10, 1.40))
    down = pose(CROUCH, hips=(0.0, 0.10, 0.46), spine_rot=(35.0, 0.0, 0.0), head_rot=(-30.0, 0.0, 0.0),
                hand_l=(0.16, -0.40, 0.28), hand_r=(-0.16, -0.38, 0.28))
    keys = [Key(0, CROUCH), Key(0.5, up), Key(1.0, down), Key(1.5, up), Key(2.0, down), Key(2.5, up),
            Key(3.0, down), Key(3.5, pose(CROUCH, hips=(0.0, 0.10, 0.52))), Key(4, CROUCH)]
    return Move("ground_pound", "drop", 4, "crouch", "crouch", keys,
                [Hit(1.0, "hand_l", 1.0), Hit(2.0, "hand_r", 1.0), Hit(3.0, "hand_l", 1.0)])


def _burst_rise():
    coil = pose(CROUCH, hips=(0.0, 0.10, 0.45), head_rot=(-10.0, 0.0, 0.0),
                hand_l=(0.30, -0.15, 0.70), hand_r=(-0.30, -0.25, 0.60))
    burst = pose(LOW, hips=(0.0, 0.05, 1.00), spine_rot=(-12.0, 0.0, 0.0), chest_rot=(-10.0, 0.0, 0.0),
                 head_rot=(-25.0, 0.0, 0.0), hand_l=(0.62, -0.05, 1.60), hand_r=(-0.62, -0.05, 1.60),
                 foot_l=(0.30, -0.15, 0.25), foot_l_rot=(0.0, 10.0, 0.0),
                 foot_r=(-0.30, 0.10, 0.25), foot_r_rot=(0.0, -20.0, 0.0))
    land = pose(LOW, hips=(0.0, 0.0, 0.70), hand_l=(0.55, -0.10, 1.35), hand_r=(-0.55, -0.10, 1.35))
    punch_r = pose(LOW, hips_rot=(0.0, 15.0, 0.0), spine_rot=(12.0, 12.0, 0.0),
                   hand_l=(0.25, -0.30, 1.20), hand_r=(-0.10, -0.82, 1.25))
    punch_l = pose(LOW, hips_rot=(0.0, -15.0, 0.0), spine_rot=(12.0, -12.0, 0.0),
                   hand_l=(0.10, -0.82, 1.25), hand_r=(-0.25, -0.30, 1.20))
    back = pose(LOW, hand_l=(0.25, -0.40, 1.20), hand_r=(-0.25, -0.40, 1.20))
    keys = [Key(0, CROUCH), Key(0.5, coil), Key(1.0, burst), Key(1.5, land), Key(2.0, back),
            Key(2.5, punch_r), Key(2.75, back), Key(3.0, punch_l), Key(3.25, back), Key(3.5, punch_r),
            Key(3.75, back), Key(4.0, punch_l), Key(4.5, back), Key(5.25, pose(LOW, spine_rot=(4.0, 0.0, 0.0), **FLEX)),
            Key(6, pose(LOW, spine_rot=(0.0, 0.0, 0.0), head_rot=(-30.0, 0.0, 0.0), **FLEX)), Key(7, LOW), Key(8, LOW)]
    hits = [Hit(1.0, "head", 1.0), Hit(1.5, "foot_l", 0.8), Hit(2.5, "hand_r", 0.7), Hit(3.0, "hand_l", 0.7),
            Hit(3.5, "hand_r", 0.8), Hit(4.0, "hand_l", 1.0)]
    return Move("burst_rise", "drop", 8, "crouch", "low", keys, hits)


def _power_stomp():
    def knee(side):
        foot, x = ("foot_r", -0.30) if side == "r" else ("foot_l", 0.30)
        return pose(LOW, hips=(0.08 if side == "r" else -0.08, 0.0, 0.80), spine_rot=(4.0, 0.0, 0.0),
                    **{foot: (x, -0.10, 0.55), foot + "_rot": (-20.0, 0.0, 0.0)}, **FLEX)
    stomp = pose(LOW, hips=(0.0, 0.0, 0.70), spine_rot=(16.0, 0.0, 0.0),
                 hand_l=(0.30, -0.28, 0.95), hand_r=(-0.30, -0.28, 0.95))
    keys = [Key(0, LOW), Key(0.5, knee("r")), Key(1.0, stomp), Key(1.5, knee("l")), Key(2.0, stomp),
            Key(2.5, knee("r")), Key(3.0, stomp), Key(3.5, pose(LOW, hips=(0.0, 0.0, 0.74))), Key(4, LOW)]
    return Move("power_stomp", "drop", 4, "low", "low", keys,
                [Hit(1.0, "foot_r", 1.0), Hit(2.0, "foot_l", 1.0), Hit(3.0, "foot_r", 0.9)])


def _low_charge():
    tuck = pose(LOW, hips=(0.0, 0.05, 0.70), spine_rot=(25.0, -10.0, 0.0), head_rot=(-25.0, 0.0, 0.0),
                hand_l=(0.10, -0.35, 1.15), hand_r=(-0.20, -0.25, 1.15))
    ram = pose(tuck, hips=(0.0, -0.35, 0.80), hips_rot=(0.0, -35.0, 0.0), spine_rot=(30.0, -15.0, 0.0),
               hand_l=(0.10, -0.62, 1.15), hand_r=(-0.10, -0.50, 1.15),
               foot_l=(0.15, -0.55, ANKLE_Z), foot_l_rot=(0.0, -15.0, 0.0))
    fwd = shifted(GUARD, -0.31)
    planted = dict(foot_l=fwd["foot_l"], foot_l_rot=fwd["foot_l_rot"])
    keys = [Key(0, LOW), Key(1, tuck),
            Key(1.5, pose(tuck, hips=(-0.04, -0.10, 0.74), foot_l=(0.25, -0.35, 0.25), foot_l_rot=(0.0, 0.0, 0.0))),
            Key(2.0, ram), Key(2.4, pose(ram, hips=(0.0, -0.25, 0.84), spine_rot=(15.0, -10.0, 0.0))),
            Key(2.75, pose(ram, hips=(0.0, -0.28, 0.86), spine_rot=(10.0, -8.0, 0.0),
                           foot_r=(-0.25, -0.20, 0.22), foot_r_rot=(0.0, -35.0, 0.0))),
            Key(3.25, fwd),
            Key(4.0, pose(fwd, hips=(0.0, -0.27, 0.95), spine_rot=(-6.0, 0.0, 0.0), head_rot=(-15.0, 5.0, 0.0),
                          hand_l=(0.15, -0.40, 1.95), hand_r=(-0.15, -0.40, 1.95))),
            Key(4.5, pose(fwd, hips=(0.0, -0.33, 0.84), spine_rot=(22.0, 0.0, 0.0), head_rot=(-15.0, 5.0, 0.0),
                          hand_l=(0.10, -0.80, 1.10), hand_r=(-0.10, -0.75, 1.10))),
            Key(5.0, fwd),
            Key(5.5, pose(fwd, hips=(0.0, -0.20, 0.91), foot_r=(-0.18, 0.15, 0.20))),
            Key(6.0, pose(GUARD, hips=(0.0, -0.10, 0.90), hand_l=fwd["hand_l"], **planted)),
            Key(6.5, pose(GUARD, hips=(0.0, -0.02, 0.91), foot_l=(0.15, -0.40, 0.20))),
            Key(7.0, GUARD), Key(7.5, BOB), Key(8, GUARD)]
    return Move("low_charge", "drop", 8, "low", "guard", keys, [Hit(2.0, "head", 1.0), Hit(4.5, "hand_r", 1.0)])


MOVES = {m.name: m for m in _idles() + [
    _guard_shuffle(), _settle_low(), _rise_guard(), _low_scan(), _stand_up(),
    _jab_cross(), _take_hit(), _jab_jab_hook(), _palm_strike(), _elbow_rush(), _crouch_strike(),
    _front_kick(), _uppercut_combo(), _leap_slam(), _ground_pound(), _burst_rise(), _power_stomp(), _low_charge()]}


def frames_per_beat(bpm=BPM, fps=FPS):
    return 60.0 / bpm * fps


def clip_frames(beats=BEATS, bpm=BPM, fps=FPS):
    """Frames of a Clip: beats x 60 / bpm x fps, rounded half up (robot/CONTRACTS.md)."""
    return int(beats * frames_per_beat(bpm, fps) + 0.5)


def move_frames(move, bpm=BPM, fps=FPS):
    return clip_frames(move.beats, bpm, fps)


def beat_frame(beat, bpm=BPM, fps=FPS):
    """The frame a beat lands on."""
    return int(beat * frames_per_beat(bpm, fps) + 0.5)


def _smoothstep(t):
    return t * t * (3.0 - 2.0 * t)


def _key_frames(move, bpm, fps):
    last = move_frames(move, bpm, fps) - 1
    return [min(k.beat * frames_per_beat(bpm, fps), last) for k in move.keys]


def sample(move, frame, bpm=BPM, fps=FPS):
    """The Pose of `move` at `frame` (0-based)."""
    pose = _sample_keys(move, frame, bpm, fps)
    if move.waves:
        t = frame / (move_frames(move, bpm, fps) - 1)
        for w in move.waves:
            v = list(pose[w.channel])
            v[w.axis] += w.amplitude * 0.5 * (1.0 - math.cos(2.0 * math.pi * w.harmonic * t))
            pose[w.channel] = tuple(v)
    return pose


def _sample_keys(move, frame, bpm, fps):
    kf = _key_frames(move, bpm, fps)
    if frame <= kf[0]:
        return dict(move.keys[0].pose)
    for i in range(1, len(kf)):
        if frame <= kf[i]:
            t = _smoothstep((frame - kf[i - 1]) / (kf[i] - kf[i - 1]))
            a, b = move.keys[i - 1].pose, move.keys[i].pose
            return {c: tuple(x + (y - x) * t for x, y in zip(a[c], b[c])) for c in CHANNELS}
    return dict(move.keys[-1].pose)


def frames(move, bpm=BPM, fps=FPS):
    """One Pose per frame of the Clip."""
    return [sample(move, f, bpm, fps) for f in range(move_frames(move, bpm, fps))]


def hit_frames(move, bpm=BPM, fps=FPS):
    """Hits for Clip Data, without the point (that comes from the render): [{f, limb, strength}]."""
    return [{"f": beat_frame(h.beat, bpm, fps), "limb": h.limb, "strength": h.strength} for h in move.hits]


def pose_distance(a, b):
    """(largest rotation difference in degrees, largest position difference in metres)."""
    rot = max(abs(x - y) for c in CHANNELS if is_rotation(c) for x, y in zip(a[c], b[c]))
    pos = max(abs(x - y) for c in CHANNELS if not is_rotation(c) for x, y in zip(a[c], b[c]))
    return rot, pos


def cut_points(move, bpm=BPM, fps=FPS, tol_deg=0.5, tol_m=0.005):
    """Beats inside the Clip whose frame shows the Clip's Key Pose, so Magic may switch there."""
    key = KEY_POSES[move.key_in]
    out = []
    for beat in range(move.beats):
        rot, pos = pose_distance(sample(move, beat_frame(beat, bpm, fps), bpm, fps), key)
        if rot <= tol_deg and pos <= tol_m:
            out.append(beat)
    return out


# the leg as rigged in build_robot.py: thigh (0.11, 0, 0.96) to (0.11, -0.03, 0.53), shin on to (0.11, 0, 0.10)
LEG_M = 2 * math.hypot(0.03, 0.43)
HIP_OFFSET = (0.11, 0.0, -0.04)   # thigh head relative to the hips joint at rest, left side


def hip_joint(p, side):
    """Root-space position of the thigh head of `side` ('l' or 'r') in Pose `p`: the rest offset turned by
    hips_rot (Euler XYZ in the hips bone's frame, whose axes are root X, Z and -Y)."""
    ox, oy, oz = HIP_OFFSET[0] * (1 if side == "l" else -1), HIP_OFFSET[1], HIP_OFFSET[2]
    v = (ox, oz, -oy)                                   # root to bone frame
    a, b, c = (math.radians(x) for x in p["hips_rot"])
    v = (v[0], v[1] * math.cos(a) - v[2] * math.sin(a), v[1] * math.sin(a) + v[2] * math.cos(a))
    v = (v[0] * math.cos(b) + v[2] * math.sin(b), v[1], -v[0] * math.sin(b) + v[2] * math.cos(b))
    v = (v[0] * math.cos(c) - v[1] * math.sin(c), v[0] * math.sin(c) + v[1] * math.cos(c), v[2])
    hx, hy, hz = p["hips"]
    return (hx + v[0], hy - v[2], hz + v[1])            # bone frame back to root
