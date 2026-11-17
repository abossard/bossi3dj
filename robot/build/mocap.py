"""Mocap Clips: Mixamo captures as Moves (#31). Pure, no bpy; `retarget.py` does the Blender side.

A Mocap Clip names a Mixamo FBX and Anchors: (beat, source frame) pairs. The time map runs through them piecewise
linearly, so a capture's key moments (a strike's contact, a landing) land on the 124 BPM grid and the capture plays
faster or slower between them. Hits name their source frame; the time map puts them on their beat.

The ends: a Clip with Key Poses blends from `key_in` into the capture over the first beat and from the capture into
`key_out` over the last (smoothstep weights). An Idle Clip has no Key Pose of its own yet: its last `LOOP_FRAMES`
frames blend back into its first frame, so it loops without a seam.

Root travel: the capture's net travel in the floor plane is taken out in proportion to the hips' path, so the Clip
ends where it starts and still moves while the capture moves. Feet: a foot counts as planted when its ankle is near
the floor and nearly still; a planted run holds its ankle at one spot on the floor, blending in and out over
`LOCK_BLEND` frames.

Weight (weight.py) on top: a hold at each Hit with the catch-up (`warp`), and in retarget.py the recoil after it
and the dip after a stomp. No ballistic layer and no landing dip: the capture flies and lands by itself.

    python3 -m unittest discover robot/build/tests
"""
import math
from collections import namedtuple

import moves
import weight

PACKS = "robot/assets/mixamo/packs"
FIGHT = "../fight/"         # relative to PACKS: the fight clips the user downloaded on 2026-11-17
LOOP_FRAMES = 12
PLANT_HEIGHT_M = 0.04      # ankle within this of ANKLE_Z
PLANT_SPEED_M = 0.012      # per frame at 30 fps (0.36 m/s)
PLANT_MIN_FRAMES = 3
LOCK_BLEND = 3

MocapClip = namedtuple("MocapClip", "name tier beats key_in key_out fbx anchors hits idle variant_of",
                       defaults=(False, None))
SourceHit = namedtuple("SourceHit", "src limb strength")

CLIPS = {c.name: c for c in [
    # the breathing idle of the Action Adventure pack: staggered, left foot forward; 10 s, one bar of it loops
    MocapClip("mocap_idle", "calm", 4, None, None, "action_adventure_pack/extracted/idle (2).fbx",
              ((0, 1), (4, 59)), (), True),
    # the Free Test pack's one fight clip: guard, back flip, rush in, left and right uppercut, back to guard
    MocapClip("mocap_flip_uppercut", "drop", 8, "guard", "guard", "free_test_pack/extracted/back flip to uppercut.fbx",
              ((0, 9), (5, 106), (6, 121), (8, 160)),     # drops the held guard at both ends: 1.34x, 1x, 1.34x
              (SourceHit(106, "hand_l", 0.8), SourceHit(121, "hand_r", 1.0))),
    # its takes (#32): the same capture on other anchors, so the flip, the rush and the uppercuts fall elsewhere
    MocapClip("mocap_flip_uppercut_v2", "drop", 8, "guard", "guard", "free_test_pack/extracted/back flip to uppercut.fbx",
              ((0, 9), (4, 106), (5, 121), (8, 165)),    # earlier strikes, a longer settle
              (SourceHit(106, "hand_l", 0.8), SourceHit(121, "hand_r", 1.0)), False, "mocap_flip_uppercut"),
    # the user's fight clips (robot/assets/mixamo/fight/): Hits on each strike's contact frame (the fist furthest
    # forward, the elbow's forward stop), Anchors put them on beats and half beats
    MocapClip("mocap_fist_fight", "drop", 8, "guard", "guard", FIGHT + "Fist Fight A.fbx",
              ((0, 5), (2, 47), (4, 75), (4.5, 83), (7, 129), (8, 141)),
              (SourceHit(47, "hand_l", 0.6), SourceHit(75, "hand_r", 0.9), SourceHit(83, "hand_l", 0.7),
               SourceHit(129, "hand_l", 1.0))),
    MocapClip("mocap_fist_fight_v2", "drop", 8, "guard", "guard", FIGHT + "Fist Fight A.fbx",
              ((0, 1), (2.5, 47), (4.5, 75), (5, 83), (7, 129), (8, 141)),     # a later start, the combo tighter
              (SourceHit(47, "hand_l", 0.6), SourceHit(75, "hand_r", 0.9), SourceHit(83, "hand_l", 0.7),
               SourceHit(129, "hand_l", 1.0)), False, "mocap_fist_fight"),
    MocapClip("mocap_jab_elbow", "build", 8, "guard", "guard", FIGHT + "Jab To Elbow Punch.fbx",
              ((0, 1), (2, 31), (3, 47), (8, 99)),
              (SourceHit(31, "hand_l", 0.7), SourceHit(47, "hand_r", 1.0))),          # the elbow drives the right arm
    MocapClip("mocap_jab_elbow_v2", "build", 8, "guard", "guard", FIGHT + "Jab To Elbow Punch.fbx",
              ((0, 1), (3, 31), (4, 47), (8, 99)),                                   # a longer wind-up
              (SourceHit(31, "hand_l", 0.7), SourceHit(47, "hand_r", 1.0)), False, "mocap_jab_elbow"),
    MocapClip("mocap_uppercut_jab", "drop", 8, "guard", "guard", FIGHT + "Uppercut Jab.fbx",
              ((0, 1), (2, 25), (3, 43), (3.5, 53), (4, 61), (4.5, 69), (5, 77), (8, 109)),
              (SourceHit(25, "hand_l", 0.6), SourceHit(43, "hand_r", 0.8), SourceHit(53, "hand_l", 0.6),
               SourceHit(61, "hand_r", 0.8), SourceHit(69, "hand_l", 0.7), SourceHit(77, "hand_r", 1.0))),
    MocapClip("mocap_uppercut_jab_v2", "drop", 8, "guard", "guard", FIGHT + "Uppercut Jab-2.fbx",     # another clip
              ((0, 1), (1, 27), (2.5, 57), (3.5, 77), (4.5, 95), (5.5, 115), (6.5, 133), (8, 175)),
              (SourceHit(27, "hand_l", 0.6), SourceHit(57, "hand_r", 0.8), SourceHit(77, "hand_l", 0.7),
               SourceHit(95, "hand_r", 0.8), SourceHit(115, "hand_l", 0.8), SourceHit(133, "hand_r", 1.0)),
              False, "mocap_uppercut_jab"),
    MocapClip("mocap_uppercut_jab_v3", "drop", 8, "guard", "guard", FIGHT + "Uppercut Jab.fbx",
              ((0, 1), (2.5, 25), (3.5, 43), (4, 53), (4.5, 61), (5, 69), (6, 77), (8, 109)),   # a later, looser combo
              (SourceHit(25, "hand_l", 0.6), SourceHit(43, "hand_r", 0.8), SourceHit(53, "hand_l", 0.6),
               SourceHit(61, "hand_r", 0.8), SourceHit(69, "hand_l", 0.7), SourceHit(77, "hand_r", 1.0)),
              False, "mocap_uppercut_jab"),
    MocapClip("mocap_flip_uppercut_v3", "drop", 8, "guard", "guard", "free_test_pack/extracted/back flip to uppercut.fbx",
              ((0, 13), (5.5, 106), (6.5, 121), (8, 158)),    # a slower flip, off-beat strikes, a quick settle
              (SourceHit(106, "hand_l", 0.8), SourceHit(121, "hand_r", 1.0)), False, "mocap_flip_uppercut"),
]}


def src_frame(clip, frame):
    """The source frame (float) the Clip's `frame` shows."""
    beat = frame / moves.frames_per_beat()
    a = clip.anchors
    if beat <= a[0][0]:
        return float(a[0][1])
    for (b0, s0), (b1, s1) in zip(a, a[1:]):
        if beat <= b1:
            return s0 + (s1 - s0) * (beat - b0) / (b1 - b0)
    return float(a[-1][1])


def hit_beat(clip, src):
    """The beat a source frame lands on (inverse of the time map)."""
    for (b0, s0), (b1, s1) in zip(clip.anchors, clip.anchors[1:]):
        if s0 <= src <= s1:
            return b0 + (b1 - b0) * (src - s0) / (s1 - s0)
    raise ValueError("source frame %s outside the anchors of %s" % (src, clip.name))


def hits(clip):
    """moves.Hit list, so hit_frames and Clip Data treat a Mocap Clip like a Move."""
    return [moves.Hit(hit_beat(clip, h.src), h.limb, h.strength) for h in clip.hits]


def frames(clip):
    return moves.clip_frames(clip.beats)


def stops(clip):
    """[(frame, limb, strength)] of the Hits, for weight.py."""
    return [(moves.beat_frame(h.beat), h.limb, h.strength) for h in hits(clip)]


def warp(clip):
    """Source frame per Clip frame: weight.py's hit-stop (hold at each Hit, catch up by the next beat) through the
    Anchors' time map."""
    s = weight.time_warp(frames(clip), [(h, st, limb) for h, limb, st in stops(clip)],
                         [moves.beat_frame(b) for b in range(clip.beats + 1)])
    return [src_frame(clip, f) for f in s]


def key_weight(clip, frame):
    """(weight of key_in, weight of key_out) at `frame`: 1 at the ends, 0 inside, smoothstep over the end beats."""
    if clip.idle:
        return 0.0, 0.0
    fpb, last = moves.frames_per_beat(), frames(clip) - 1
    w_in = 1.0 - moves._smoothstep(min(frame / fpb, 1.0))
    w_out = moves._smoothstep(max(0.0, min((frame - (last - fpb)) / fpb, 1.0)))
    return w_in, w_out


def loop_weight(clip, frame):
    """Weight of the first frame over the last LOOP_FRAMES of an Idle Clip: 1 on the last frame."""
    if not clip.idle:
        return 0.0
    last = frames(clip) - 1
    return moves._smoothstep(max(0.0, min((frame - (last - LOOP_FRAMES)) / LOOP_FRAMES, 1.0)))


def travel_offsets(hips_xy):
    """Per frame, the floor offset that takes the net travel out in proportion to the path walked so far."""
    net = (hips_xy[-1][0] - hips_xy[0][0], hips_xy[-1][1] - hips_xy[0][1])
    steps = [math.dist(a, b) for a, b in zip(hips_xy, hips_xy[1:])]
    total = sum(steps)
    out, walked = [(0.0, 0.0)], 0.0
    for s in steps:
        walked += s
        t = walked / total if total else 0.0
        out.append((-net[0] * t, -net[1] * t))
    return out


def plants(ankles):
    """Per frame, whether the ankle (x, y, z) is planted: near the floor, nearly still, for PLANT_MIN_FRAMES."""
    n = len(ankles)
    still = [ankles[f][2] <= moves.ANKLE_Z + PLANT_HEIGHT_M and
             math.dist(ankles[f], ankles[f - 1 if f else min(1, n - 1)]) <= PLANT_SPEED_M for f in range(n)]
    out, f = [False] * n, 0
    while f < n:
        if still[f]:
            g = f
            while g < n and still[g]:
                g += 1
            if g - f >= PLANT_MIN_FRAMES:
                out[f:g] = [True] * (g - f)
            f = g
        else:
            f += 1
    return out


def runs(flags):
    """[(first, last)] of each run of True."""
    out, f = [], 0
    while f < len(flags):
        if flags[f]:
            g = f
            while g + 1 < len(flags) and flags[g + 1]:
                g += 1
            out.append((f, g))
            f = g + 1
        else:
            f += 1
    return out


def lock_feet(ankles):
    """Ankles with each planted run held at its mean spot on the floor (z = ANKLE_Z); the frames next to a run blend
    toward that spot. Returns (ankles, lock weights): 1 in a planted run, falling to 0 over LOCK_BLEND frames."""
    out = [list(a) for a in ankles]
    weights = [0.0] * len(ankles)
    for f0, f1 in runs(plants(ankles)):
        spot = (sum(a[0] for a in ankles[f0:f1 + 1]) / (f1 - f0 + 1),
                sum(a[1] for a in ankles[f0:f1 + 1]) / (f1 - f0 + 1), moves.ANKLE_Z)
        for f in range(max(0, f0 - LOCK_BLEND), min(len(ankles), f1 + 1 + LOCK_BLEND)):
            d = f0 - f if f < f0 else f - f1 if f > f1 else 0
            w = moves._smoothstep(1.0 - d / (LOCK_BLEND + 1))
            out[f] = [a + (s - a) * w for a, s in zip(out[f], spot)]
            weights[f] = max(weights[f], w)
    return [tuple(a) for a in out], weights
