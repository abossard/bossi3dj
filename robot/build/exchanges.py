"""Exchanges: Moves with both fighters, the Android and the giant machine, on one beat grid. Pure, no bpy.

An Exchange holds two Moves (moves.py) of the same length and tier: the Android's, which starts and ends in its Key
Poses, and the giant's, which starts and ends in LOOM. The giant's channels are named control points that an
imported rig maps to (robot/build/GIANT.md): `g_hips` (pelvis), `g_hammer` and `g_claw` (the striking heads at the
ends of the arms, the arm IK targets), `g_foot_l` and `g_foot_r` (ankles), and rotations `g_hips_rot`, `g_chest_rot`,
`g_head_rot` in the bones' own frames. Positions are in the Android's root space: the giant stands at y = -2.5 facing
+Y, so its right is +X.

Hits name a striking point and the point it strikes on the other fighter (or "floor"); dodges name a striking point
that must miss the Android. Contact is judged between point spheres (RADIUS).

    python3 -m unittest discover robot/build/tests
"""
import math
from collections import namedtuple

import moves
from moves import BEATS, CROUCH, GUARD, LOW, Hit, Key, Move, Wave, pose, shifted

Exchange = namedtuple("Exchange", "name tier beats android giant hits dodges idle", defaults=(False,))
Strike = namedtuple("Strike", "beat point strength target")
Dodge = namedtuple("Dodge", "beat point")

# the giant's proportions as planned for the imported model (GIANT.md): about 6 m tall
G_ANKLE_Z = 0.30
G_THIGH = G_SHIN = 1.25
G_HIP = (0.40, -0.15)          # thigh head: sideways and down from g_hips
G_CORE_UP, G_HEAD_UP = 1.38, 2.2
G_CORE_CHEST = 0.1             # the chest core sits near the chest's pivot: it leans by a tenth of g_chest_rot (rig, X1)
A_CHEST_UP, A_HEAD_UP = 0.50, 0.93
# g_knee: the shin shell's front lies at the model knee point, not 0.35 m ahead of it (review/giant_contact.py, X1)
RADIUS = {"g_hammer": 0.50, "g_claw": 0.30, "g_foot_l": 0.30, "g_foot_r": 0.30, "g_core": 0.50, "g_head": 0.40,
          "g_knee_l": 0.10, "g_knee_r": 0.10, "hand_l": 0.08, "hand_r": 0.08, "foot_l": 0.12, "foot_r": 0.12,
          "head": 0.15, "chest": 0.25, "hips": 0.20}
ANDROID_BODY = ("head", "chest", "hips", "hand_l", "hand_r", "foot_l", "foot_r")

LOOM = {
    "g_hips": (0.0, -2.5, 2.6),
    "g_hips_rot": (0.0, 0.0, 0.0),
    "g_chest_rot": (18.0, 0.0, 0.0),
    "g_head_rot": (-12.0, 0.0, 0.0),
    "g_hammer": (0.95, -1.9, 3.3),
    "g_claw": (-0.90, -1.8, 2.6),
    "g_foot_l": (-0.55, -2.75, G_ANKLE_Z),
    "g_foot_r": (0.55, -2.2, G_ANKLE_Z),
}


def gpose(base, **changes):
    unknown = set(changes) - set(LOOM)
    if unknown:
        raise KeyError("unknown giant channels: %s" % ", ".join(sorted(unknown)))
    out = dict(base)
    out.update({k: tuple(float(x) for x in v) for k, v in changes.items()})
    return out


def _add(p, d):
    return tuple(a + b for a, b in zip(p, d))


def _up(base, lean_deg, length, forward_y):
    r = math.radians(lean_deg)
    return _add(base, (0.0, forward_y * length * math.sin(r), length * math.cos(r)))


def g_hip_joint(g, side):
    """Thigh head of the giant, `side` 'l' (toward -X) or 'r', turned by the hips' twist."""
    s = 1.0 if side == "r" else -1.0
    t = math.radians(g["g_hips_rot"][1])
    x, z = s * G_HIP[0], G_HIP[1]
    return _add(g["g_hips"], (x * math.cos(t), x * math.sin(t), z))


def g_knee(g, side):
    """Knee of a 2-bone leg from hip to ankle, bent toward the giant's front (+Y)."""
    h, a = g_hip_joint(g, side), g["g_foot_" + side]
    d = math.dist(h, a)
    u = tuple((y - x) / d for x, y in zip(h, a))
    mid = tuple((x + y) / 2 for x, y in zip(h, a))
    bend = math.sqrt(max(G_THIGH * G_THIGH - (d / 2) ** 2, 0.0))
    f = (0.0, 1.0, 0.0)
    p = tuple(fc - u_c * sum(fi * ui for fi, ui in zip(f, u)) for fc, u_c in zip(f, u))
    n = math.sqrt(sum(c * c for c in p))
    return tuple(m + bend * c / n for m, c in zip(mid, p))


def points(a, g):
    """Every named point of both fighters in one frame: the Android's from its Pose `a`, the giant's from `g`."""
    lean_a = a["hips_rot"][0] + a["spine_rot"][0] + a["chest_rot"][0]
    lean_g = g["g_hips_rot"][0] + g["g_chest_rot"][0]
    out = {k: a[k] for k in ("hips", "hand_l", "hand_r", "foot_l", "foot_r")}
    out["chest"] = _up(a["hips"], lean_a, A_CHEST_UP, -1.0)
    out["head"] = _up(a["hips"], lean_a, A_HEAD_UP, -1.0)
    out.update({k: g[k] for k in ("g_hammer", "g_claw", "g_foot_l", "g_foot_r")})
    out["g_core"] = _up(g["g_hips"], g["g_hips_rot"][0] + G_CORE_CHEST * g["g_chest_rot"][0], G_CORE_UP, 1.0)
    out["g_head"] = _up(g["g_hips"], lean_g, G_HEAD_UP, 1.0)
    out["g_knee_l"], out["g_knee_r"] = g_knee(g, "l"), g_knee(g, "r")
    return out


def _giant(name, tier, beats, keys, waves=(), idle=False):
    return Move(name, tier, beats, "loom", "loom", keys, [], idle, tuple(Wave(*w) for w in waves))


def shifted_x(base, dx):
    return pose(base, **{c: (base[c][0] + dx, base[c][1], base[c][2])
                         for c in ("hips", "hand_l", "hand_r", "foot_l", "foot_r")})


# ---------- calm ----------

def _duel_idle(name, android_idle):
    """The duel Angles' Idle Clip of one Key Pose: the Android's Idle Clip of it, the giant breathing in LOOM."""
    giant = _giant(name, "calm", BEATS, [Key(0, LOOM), Key(BEATS, LOOM)],
                   (("g_hips", 2, -0.05, 2), ("g_chest_rot", 0, 3.0, 2), ("g_hammer", 2, -0.08, 2),
                    ("g_claw", 2, -0.06, 2), ("g_head_rot", 1, 10.0, 1), ("g_hips", 0, 0.04, 1)), idle=True)
    return Exchange(name, "calm", BEATS, moves.MOVES[android_idle], giant, [], [], True)


def _circle():
    lean_r = gpose(LOOM, g_hips=(0.15, -2.5, 2.55), g_hips_rot=(0.0, 8.0, 0.0), g_head_rot=(-12.0, -10.0, 0.0),
                   g_hammer=(1.05, -2.0, 3.6))
    lean_l = gpose(LOOM, g_hips=(-0.15, -2.5, 2.55), g_hips_rot=(0.0, -8.0, 0.0), g_head_rot=(-12.0, 10.0, 0.0),
                   g_claw=(-1.0, -1.7, 2.9))
    giant = _giant("circle", "calm", 8, [Key(0, LOOM), Key(2, lean_r), Key(4, LOOM), Key(6, lean_l), Key(8, LOOM)])
    return Exchange("circle", "calm", 8, moves.MOVES["guard_shuffle"]._replace(name="circle"), giant, [], [])


# ---------- build ----------

def _hammer_dodge():
    side = shifted_x(GUARD, 1.15)
    android = Move("hammer_dodge", "build", BEATS, "guard", "low", [
        Key(0, GUARD), Key(0.8, BOB_UP),
        Key(1.2, pose(GUARD, hips=(0.25, 0.02, 0.86), foot_l=(0.45, -0.20, 0.25), foot_l_rot=(0.0, 0.0, 0.0))),
        Key(1.6, pose(side, hips=(1.15, 0.02, 0.84), foot_r=(0.70, 0.20, 0.22), foot_r_rot=(0.0, -30.0, 0.0),
                      hand_l=(1.30, -0.40, 1.45), hand_r=(1.05, -0.22, 1.45))),
        Key(2.0, pose(side, hips=(1.15, 0.02, 0.84), head_rot=(-8.0, -30.0, 0.0))),
        Key(2.6, pose(side, hips=(1.10, 0.02, 0.86), foot_l=(0.95, -0.15, 0.22), foot_l_rot=(0.0, 0.0, 0.0))),
        Key(3.2, pose(LOW, hips=(0.10, 0.0, 0.80), foot_r=(-0.10, 0.05, 0.22), foot_r_rot=(0.0, -20.0, 0.0))),
        Key(4, LOW)], [])
    wind = gpose(LOOM, g_hips=(0.0, -2.6, 2.7), g_chest_rot=(-8.0, 0.0, 0.0), g_head_rot=(-20.0, 0.0, 0.0),
                 g_hammer=(0.5, -2.4, 5.0))
    smash = gpose(LOOM, g_hips=(0.0, -2.3, 1.4), g_chest_rot=(75.0, 0.0, 0.0), g_head_rot=(10.0, 0.0, 0.0),
                  g_hammer=(0.15, -0.65, 0.42), g_claw=(-1.1, -1.6, 1.3))
    giant = _giant("hammer_dodge", "build", BEATS, [Key(0, LOOM), Key(0.8, wind), Key(2.0, smash, "in"),
                                                     Key(2.15, gpose(smash, g_hammer=(0.15, -0.67, 0.55)), "out"),
                                                     Key(3.2, gpose(LOOM, g_chest_rot=(25.0, 0.0, 0.0))), Key(4, LOOM)])
    return Exchange("hammer_dodge", "build", BEATS, android, giant,
                    [Strike(2.0, "g_hammer", 1.0, "floor")], [Dodge(2.0, "g_hammer")])


def _sweep_jump():
    dip = pose(LOW, hips=(0.0, 0.0, 0.66), spine_rot=(16.0, 0.0, 0.0), hand_l=(0.30, 0.10, 0.95),
               hand_r=(-0.30, 0.10, 0.95))
    air = pose(LOW, hips=(0.0, 0.0, 1.50), spine_rot=(10.0, 0.0, 0.0), head_rot=(10.0, 0.0, 0.0),
               hand_l=(0.40, -0.30, 1.75), hand_r=(-0.40, -0.30, 1.75),
               foot_l=(0.25, -0.15, 1.15), foot_l_rot=(-20.0, 10.0, 0.0),
               foot_r=(-0.25, 0.05, 1.10), foot_r_rot=(-20.0, -20.0, 0.0))
    fall = pose(CROUCH, hips=(0.0, 0.10, 1.00), hips_rot=(10.0, -10.0, 0.0), spine_rot=(10.0, -5.0, 0.0),
                hand_l=(0.40, -0.10, 1.30), hand_r=(-0.30, -0.30, 1.10),
                foot_l=(0.22, -0.22, 0.40), foot_r=(-0.24, 0.28, 0.40))
    android = Move("sweep_jump", "build", BEATS, "low", "crouch", [
        Key(0, LOW), Key(1.0, dip), Key(1.6, air), Key(2.0, pose(air, hips=(0.0, 0.0, 1.62))), Key(2.4, fall),
        Key(2.8, pose(CROUCH, hips=(0.0, 0.10, 0.44), spine_rot=(32.0, -5.0, 0.0)), "in"),
        Key(3.4, pose(CROUCH, hips=(0.0, 0.10, 0.48))), Key(4, CROUCH)], [])
    reach = gpose(LOOM, g_hips=(-0.2, -2.3, 2.2), g_hips_rot=(0.0, -25.0, 0.0), g_chest_rot=(40.0, -10.0, 0.0),
                  g_claw=(-1.9, -0.90, 0.45))
    through = gpose(LOOM, g_hips=(0.2, -2.3, 2.2), g_hips_rot=(0.0, 25.0, 0.0), g_chest_rot=(40.0, 10.0, 0.0),
                    g_claw=(1.6, -0.40, 0.50))
    giant = _giant("sweep_jump", "build", BEATS, [Key(0, LOOM), Key(1.2, reach), Key(2.0, gpose(
        reach, g_hips=(0.0, -2.3, 2.2), g_hips_rot=(0.0, 0.0, 0.0), g_claw=(-0.10, -0.45, 0.40))),
        Key(2.6, through, "out"), Key(3.4, gpose(LOOM, g_chest_rot=(25.0, 0.0, 0.0))), Key(4, LOOM)])
    return Exchange("sweep_jump", "build", BEATS, android, giant, [], [Dodge(2.0, "g_claw")])


def _knee_combo():
    step = shifted(GUARD, -0.95)
    android = Move("knee_combo", "build", BEATS, "guard", "guard", [
        Key(0, GUARD), Key(0.4, pose(GUARD, hips=(0.0, -0.15, 0.88), foot_l=(0.20, -0.70, 0.20))),
        Key(0.75, pose(step, foot_r=(-0.15, -0.45, 0.20))),
        Key(1.0, pose(step, hips=(0.0, -0.98, 0.86), hips_rot=(0.0, -35.0, 0.0), spine_rot=(14.0, -8.0, 0.0),
                      hand_l=JAB_KNEE), "in"),
        Key(1.3, pose(step, hand_l=(0.20, -1.40, 1.45))),
        Key(1.7, pose(step, hips_rot=(0.0, -28.0, 0.0), hand_r=(-0.06, -1.20, 1.48))),
        Key(2.0, pose(step, hips=(0.0, -1.02, 0.86), hips_rot=(0.0, 12.0, 0.0), spine_rot=(14.0, 14.0, 0.0),
                      head_rot=(-8.0, -10.0, 0.0), hand_r=CROSS_KNEE, foot_r=(-0.15, -0.65, 0.16),
                      foot_r_rot=(12.0, -5.0, 0.0)), "in"),
        Key(2.4, pose(step, foot_r=(-0.15, -0.65, 0.14), foot_r_rot=(6.0, -25.0, 0.0))),
        Key(2.8, pose(step, hips=(0.0, -0.85, 0.91), foot_l=(0.18, -0.95, 0.20))),
        Key(3.2, pose(GUARD, hips=(0.0, -0.30, 0.91), foot_r=(-0.15, -0.20, 0.18))), Key(4, GUARD)],
        [Hit(1.0, "hand_l", 0.7), Hit(2.0, "hand_r", 1.0)])
    buckle = gpose(LOOM, g_hips=(0.15, -2.6, 2.35), g_hips_rot=(0.0, -12.0, 0.0), g_chest_rot=(28.0, 0.0, 0.0),
                   g_hammer=(1.2, -2.2, 2.8), g_claw=(-1.1, -2.0, 2.2))
    giant = _giant("knee_combo", "build", BEATS, [Key(0, LOOM), Key(1.0, LOOM), Key(1.2, gpose(
        LOOM, g_hips=(0.05, -2.55, 2.5)), "out"), Key(2.0, gpose(LOOM, g_hips=(0.05, -2.52, 2.55))),
        Key(2.25, buckle, "out"), Key(3.2, gpose(LOOM, g_hips=(0.05, -2.5, 2.5))), Key(4, LOOM)])
    return Exchange("knee_combo", "build", BEATS, android, giant,
                    [Strike(1.0, "hand_l", 0.7, "g_knee_r"), Strike(2.0, "hand_r", 1.0, "g_knee_r")], [])


# ---------- drop ----------

def _hammer_hit():
    block = pose(GUARD, hips=(0.0, 0.02, 0.86), spine_rot=(10.0, -5.0, 0.0), head_rot=(10.0, 10.0, 0.0),
                 hand_l=(0.15, -0.25, 1.95), hand_r=(-0.10, -0.15, 1.95))
    crushed = pose(CROUCH, hips=(0.0, 0.10, 0.44), spine_rot=(38.0, -5.0, 0.0), head_rot=(-5.0, 0.0, 0.0),
                   hand_l=(0.25, -0.30, 0.90), hand_r=(-0.16, -0.36, 0.30))
    android = Move("hammer_hit", "drop", BEATS, "guard", "crouch", [
        Key(0, GUARD), Key(1.2, BOB_UP), Key(1.7, block), Key(2.0, pose(block, hips=(0.0, 0.02, 0.84))),
        Key(2.35, pose(crushed, hips=(0.0, 0.06, 0.56), hand_l=(0.22, -0.28, 1.25), hand_r=(-0.15, -0.20, 1.20),
                       foot_l=GUARD["foot_l"], foot_l_rot=GUARD["foot_l_rot"],
                       foot_r=GUARD["foot_r"], foot_r_rot=GUARD["foot_r_rot"]), "out"),
        Key(2.8, pose(crushed, foot_l=(0.20, -0.24, 0.18), foot_l_rot=(0.0, -10.0, 0.0),
                      foot_r=GUARD["foot_r"], foot_r_rot=GUARD["foot_r_rot"])),
        Key(3.2, pose(crushed, foot_r=(-0.20, 0.30, 0.18), foot_r_rot=(0.0, -35.0, 0.0))),
        Key(3.6, pose(CROUCH, hips=(0.0, 0.10, 0.48))), Key(4, CROUCH)], [Hit(2.0, "head", 1.0)])
    wind = gpose(LOOM, g_hips=(0.0, -2.6, 2.7), g_chest_rot=(-10.0, 0.0, 0.0), g_head_rot=(-25.0, 0.0, 0.0),
                 g_hammer=(0.45, -2.3, 5.2))
    land = gpose(LOOM, g_hips=(0.0, -2.2, 2.4), g_chest_rot=(40.0, 0.0, 0.0), g_head_rot=(5.0, 0.0, 0.0),
                 g_hammer=HAMMER_ON_HEAD)
    giant = _giant("hammer_hit", "drop", BEATS, [Key(0, LOOM), Key(1.0, wind), Key(2.0, land, "in"),
                                                 Key(2.35, gpose(land, g_hammer=(0.05, -0.20, 1.45)), "out"),
                                                 Key(3.0, gpose(LOOM, g_chest_rot=(30.0, 0.0, 0.0))), Key(4, LOOM)])
    return Exchange("hammer_hit", "drop", BEATS, android, giant, [Strike(2.0, "g_hammer", 1.0, "head")], [])


def _core_strike():
    coil = pose(CROUCH, hips=(0.0, 0.08, 0.44), head_rot=(-45.0, 0.0, 0.0), hand_l=(0.35, 0.10, 0.80),
                hand_r=(-0.30, 0.15, 0.80))
    rise = pose(GUARD, hips=(0.0, -0.55, 2.10), spine_rot=(-10.0, 10.0, 0.0), head_rot=(-25.0, 0.0, 0.0),
                hand_l=(0.25, -0.70, 2.75), hand_r=(-0.20, -0.40, 2.70),
                foot_l=(0.20, -0.60, 1.30), foot_l_rot=(-30.0, 0.0, 0.0),
                foot_r=(-0.19, -0.23, 1.28), foot_r_rot=(-30.0, -20.0, 0.0))
    punch = pose(rise, hips=(0.0, -1.39, 3.05), hips_rot=(0.0, 15.0, 0.0), spine_rot=(10.0, 20.0, 0.0),
                 hand_l=(0.30, -1.24, 3.40), hand_r=CORE_PUNCH,
                 foot_l=(0.19, -1.39, 2.18), foot_r=(-0.18, -1.13, 2.23))
    fall = pose(GUARD, hips=(0.0, -0.40, 1.80), spine_rot=(15.0, -5.0, 0.0),
                hand_l=(0.30, -0.50, 2.20), hand_r=(-0.25, -0.40, 2.20),
                foot_l=(0.15, -0.40, 0.93), foot_l_rot=(0.0, -15.0, 0.0),
                foot_r=(-0.14, 0.03, 1.02), foot_r_rot=(0.0, -45.0, 0.0))
    land = pose(GUARD, hips=(0.0, 0.02, 0.70), spine_rot=(25.0, -5.0, 0.0), hand_l=(0.30, -0.45, 1.20),
                hand_r=(-0.20, -0.35, 1.20))
    android = Move("core_strike", "drop", 8, "crouch", "guard", [
        Key(0, CROUCH), Key(1.2, coil), Key(2.2, rise), Key(3.0, punch, "in"),
        Key(3.3, pose(punch, hand_r=(-0.05, -1.54, 3.45)), "out"), Key(4.2, fall), Key(5.0, land, "in"),
        Key(5.6, pose(GUARD, hips=(0.0, 0.02, 0.82))), Key(6.5, pose(GUARD, head_rot=(-15.0, 22.0, 0.0))),
        Key(7.5, moves.BOB), Key(8, GUARD)], [Hit(3.0, "hand_r", 1.0), Hit(5.0, "foot_l", 0.6)])
    reel = gpose(LOOM, g_hips=(0.0, -2.9, 2.5), g_chest_rot=(-15.0, 0.0, 0.0), g_head_rot=(-35.0, 0.0, 0.0),
                 g_hammer=(1.4, -2.9, 3.4), g_claw=(-1.4, -2.8, 3.0))
    giant = _giant("core_strike", "drop", 8, [Key(0, LOOM), Key(2.2, gpose(LOOM, g_chest_rot=(22.0, 0.0, 0.0))),
                                              Key(3.0, gpose(LOOM, g_chest_rot=(22.0, 0.0, 0.0))),
                                              Key(3.4, reel, "out"), Key(5.0, gpose(reel, g_hips=(0.0, -2.75, 2.5))),
                                              Key(6.5, gpose(LOOM, g_chest_rot=(25.0, 0.0, 0.0))), Key(8, LOOM)])
    return Exchange("core_strike", "drop", 8, android, giant, [Strike(3.0, "hand_r", 1.0, "g_core")], [])


def _quake_stomp():
    brace = pose(LOW, hips=(0.0, 0.0, 0.66), spine_rot=(18.0, 0.0, 0.0), hand_l=(0.55, -0.15, 1.10),
                 hand_r=(-0.55, -0.15, 1.10))
    stomp = moves.MOVES["power_stomp"]
    keys = [Key(0, LOW), Key(1.5, pose(LOW, hips=(0.0, 0.0, 0.74))), Key(2.0, brace, "out"),
            Key(2.3, pose(brace, hips=(0.04, 0.0, 0.70), spine_rot=(12.0, 0.0, 6.0))),
            Key(2.6, pose(brace, hips=(-0.04, 0.0, 0.70), spine_rot=(12.0, 0.0, -6.0))), Key(3.3, LOW), Key(4, LOW)]
    keys += [Key(k.beat + 4, k.pose, k.ease) for k in stomp.keys[1:]]
    android = Move("quake_stomp", "drop", 8, "low", "low", keys, [Hit(h.beat + 4, h.limb, h.strength) for h in stomp.hits])
    lift = gpose(LOOM, g_hips=(-0.25, -2.5, 2.75), g_chest_rot=(5.0, 0.0, 0.0), g_head_rot=(-20.0, 0.0, 0.0),
                 g_hammer=(1.3, -2.2, 3.9), g_foot_r=(0.6, -2.0, 1.80))
    slam = gpose(LOOM, g_hips=(0.0, -2.4, 2.35), g_chest_rot=(30.0, 0.0, 0.0), g_head_rot=(0.0, 0.0, 0.0))
    giant = _giant("quake_stomp", "drop", 8, [Key(0, LOOM), Key(0.8, gpose(LOOM, g_hips=(-0.25, -2.5, 2.6))),
                                              Key(1.5, lift), Key(2.0, slam, "in"), Key(2.6, gpose(slam, g_hips=(0.0, -2.4, 2.45))),
                                              Key(4, LOOM), Key(5, gpose(LOOM, g_head_rot=(5.0, 0.0, 0.0))), Key(8, LOOM)])
    return Exchange("quake_stomp", "drop", 8, android, giant, [Strike(2.0, "g_foot_r", 1.0, "floor")] +
                    [Strike(h.beat + 4, h.limb, h.strength, "floor") for h in stomp.hits], [])


BOB_UP = pose(GUARD, hips=(0.0, 0.02, 0.89))
# contact targets, placed where the struck point stands at the Hit (checked by the tests)
JAB_KNEE = (0.43, -1.70, 1.40)
CROSS_KNEE = (0.40, -1.70, 1.38)
HAMMER_ON_HEAD = (0.0, -0.20, 2.38)
CORE_PUNCH = (0.0, -1.97, 3.75)

EXCHANGES = {e.name: e for e in (_duel_idle("duel_idle", "idle_guard"), _duel_idle("duel_idle_low", "idle_low"),
                                 _duel_idle("duel_idle_crouch", "idle_crouch"), _circle(), _hammer_dodge(), _sweep_jump(), _knee_combo(),
                                 _hammer_hit(), _core_strike(), _quake_stomp())}


def frames(ex):
    """[(Android Pose, giant Pose)] per frame, weighted (weight.py) with one time warp for both fighters: every
    Strike and Android Hit holds the whole Exchange. The giant gets the spring only (`body`)."""
    import weight
    n = moves.move_frames(ex.android)
    hits = sorted({(moves.beat_frame(s.beat), s.point, s.strength) for s in ex.hits} | set(moves.stops(ex.android)))
    firsts = {}
    for f, limb, strength in hits:
        firsts[f] = max(firsts.get(f, 0.0), strength)
    raw = list(zip(moves.frames(ex.android, weighted=False), moves.frames(ex.giant, weighted=False)))
    fast = [max(a, g) for a, g in zip(weight.speeds([a for a, _g in raw]), weight.speeds([g for _a, g in raw]))]
    warp = weight.time_warp(n, sorted(firsts.items()), moves.beat_frames(ex.android), fast)
    dodges = [moves.beat_frame(d.beat) for d in ex.dodges]
    return list(zip(moves.frames(ex.android, hits=hits, warp=warp, dodges=dodges),
                    moves.frames(ex.giant, hits=[h for h in hits if h[1].startswith("g_")], warp=warp)))


def body():
    """The giant for weight.py: its spring only."""
    import weight
    return weight.Body("g_hips", ("g_foot_l", "g_foot_r"), (), G_ANKLE_Z, g_hip_joint, G_THIGH + G_SHIN,
                       weight.GIANT_CHAINS, weight.GIANT_STRIKE, ("g_hammer", "g_claw"))
