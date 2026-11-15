"""The Android's Key Pose and Moves as key tables on a beat grid. Pure, no bpy.

A Pose maps a channel to a tuple. Channels ending in `_rot` are Euler XYZ degrees in the bone's own frame;
every rotated bone points up at rest, so x bends forward, y twists counter-clockwise seen from above and z
leans to the Android's right (for a foot: x points the toe down, y turns the toe counter-clockwise). The other
channels are absolute positions in metres in the rig's root space: Z up, the Android faces -Y, its left is +X.
`hips` is the hips joint, `hand_*` the wrist and `foot_*` the ankle (IK targets). A planted ankle sits at 0.10.

Keys sit on beats; the frame of beat b is b x 60 / bpm x fps. The last key is pulled onto the last frame, so a
Clip's first and last frame both show its Key Pose. Between keys every channel eases with smoothstep.

    python3 -m unittest discover robot/build/tests
"""
from collections import namedtuple

BPM = 124
FPS = 30
BEATS = 4
ANKLE_Z = 0.10

Move = namedtuple("Move", "name tier key_in key_out keys hits")
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
KEY_POSES = {"guard": GUARD}


def pose(base, **changes):
    """A full Pose: `base` with some channels replaced. Unknown channels raise."""
    unknown = set(changes) - set(CHANNELS)
    if unknown:
        raise KeyError("unknown channels: %s" % ", ".join(sorted(unknown)))
    out = dict(base)
    out.update({k: tuple(float(x) for x in v) for k, v in changes.items()})
    return out


def is_rotation(channel):
    return channel.endswith("_rot")


# the bob: weight settles a little between beats, so a held guard never freezes
BOB = pose(GUARD, hips=(0.0, 0.02, 0.895), hand_l=(0.15, -0.42, 1.49), hand_r=(-0.10, -0.20, 1.51))


def _idle():
    def sway(side):
        return pose(GUARD, hips=(0.02 * side, 0.02, 0.88), hips_rot=(0.0, -25.0 + 3.0 * side, 0.0),
                    chest_rot=(8.0, 0.0, -2.0 * side), head_rot=(-6.0, 22.0, 0.0),
                    hand_l=(0.16, -0.41, 1.47), hand_r=(-0.09, -0.19, 1.49))

    keys = [Key(0, GUARD)]
    for beat in range(BEATS):
        keys += [Key(beat + 0.5, sway(1 if beat % 2 == 0 else -1)), Key(beat + 1, GUARD)]
    return Move("idle", "calm", "guard", "guard", keys, [])


def _jab_cross():
    jab = pose(GUARD, hips=(0.0, 0.0, 0.90), hips_rot=(0.0, -32.0, 0.0), spine_rot=(8.0, -8.0, 0.0),
               chest_rot=(6.0, -6.0, 0.0), head_rot=(-8.0, 30.0, 0.0),
               hand_l=(0.10, -0.86, 1.52), hand_r=(-0.08, -0.22, 1.54))
    jab_back = pose(GUARD, hips=(0.0, 0.01, 0.90), hand_l=(0.15, -0.44, 1.51))
    cross_load = pose(GUARD, hips=(0.0, 0.0, 0.90), hips_rot=(0.0, -28.0, 0.0), spine_rot=(7.0, -7.0, 0.0),
                      hand_l=(0.14, -0.40, 1.52), hand_r=(-0.10, -0.18, 1.52))
    cross = pose(GUARD, hips=(0.0, -0.04, 0.89), hips_rot=(0.0, 10.0, 0.0), spine_rot=(10.0, 12.0, 0.0),
                 chest_rot=(6.0, 8.0, 0.0), head_rot=(-8.0, -10.0, 0.0),
                 hand_l=(0.12, -0.36, 1.52), hand_r=(-0.02, -0.88, 1.52),
                 foot_r=(-0.15, 0.30, 0.14), foot_r_rot=(12.0, -5.0, 0.0))
    cross_back = pose(GUARD, hips=(0.0, -0.01, 0.90), hips_rot=(0.0, -12.0, 0.0), spine_rot=(7.0, 2.0, 0.0),
                      head_rot=(-8.0, 8.0, 0.0), hand_r=(-0.06, -0.40, 1.50),
                      foot_r=(-0.15, 0.30, 0.12), foot_r_rot=(6.0, -25.0, 0.0))
    keys = [Key(0, GUARD), Key(0.7, BOB), Key(1.0, jab), Key(1.3, jab_back), Key(1.7, cross_load),
            Key(2.0, cross), Key(2.5, cross_back), Key(3.0, GUARD), Key(3.5, BOB), Key(4, GUARD)]
    return Move("jab_cross", "build", "guard", "guard", keys, [Hit(1.0, "hand_l", 0.6), Hit(2.0, "hand_r", 1.0)])


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
    return Move("front_kick", "drop", "guard", "guard", keys, [Hit(2.0, "foot_l", 1.0)])


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
    return Move("take_hit", "build", "guard", "guard", keys, [Hit(1.0, "head", 1.0)])


MOVES = {m.name: m for m in (_idle(), _jab_cross(), _front_kick(), _take_hit())}


def frames_per_beat(bpm=BPM, fps=FPS):
    return 60.0 / bpm * fps


def clip_frames(beats=BEATS, bpm=BPM, fps=FPS):
    """Frames of a Clip: beats x 60 / bpm x fps, rounded half up (robot/CONTRACTS.md)."""
    return int(beats * frames_per_beat(bpm, fps) + 0.5)


def beat_frame(beat, bpm=BPM, fps=FPS):
    """The frame a beat lands on."""
    return int(beat * frames_per_beat(bpm, fps) + 0.5)


def _smoothstep(t):
    return t * t * (3.0 - 2.0 * t)


def _key_frames(move, bpm, fps):
    last = clip_frames(BEATS, bpm, fps) - 1
    return [min(k.beat * frames_per_beat(bpm, fps), last) for k in move.keys]


def sample(move, frame, bpm=BPM, fps=FPS):
    """The Pose of `move` at `frame` (0-based)."""
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
    return [sample(move, f, bpm, fps) for f in range(clip_frames(BEATS, bpm, fps))]


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
    for beat in range(BEATS):
        rot, pos = pose_distance(sample(move, beat_frame(beat, bpm, fps), bpm, fps), key)
        if rot <= tol_deg and pos <= tol_m:
            out.append(beat)
    return out
