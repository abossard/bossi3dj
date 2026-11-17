"""Fixture Render Packages at 124 BPM and 30 fps, 480x270, 2 Angles:
  package/fixture  3 Moves and 1 Idle Clip, one Key Pose, 4 beats each
  package/many     3 Key Poses (guard, crouch, stance), 6 Moves per Intensity Tier of 4, 8 and 16 beats, an Idle Clip per Key Pose
  package/duel     2 Key Poses, solo Moves on 2 solo Angles and Exchanges with the giant machine on 2 duel Angles (#23)
  package/variants package/duel with 4 variants of every Move and 3 of every Idle Clip (`variant_of`, #32), and 4 backdrops

    python3 robot/magic/fixture.py [--many | --duel | --variants]   # manifest, Clip Data, Camera Tracks (committed)
    python3 robot/magic/fixture.py [--many | --duel | --variants] --media    # also the placeholder Clips (git-ignored; ffmpeg, ProRes)

Each Clip is a numbered test card tinted per Clip: beauty is ProRes 4444 with an alpha disc (the Matte), shadow and depth are
ProRes 422. This ffmpeg has no Hap encoder.
"""
import argparse
import json
import os
import subprocess

from manifest import frames_for

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE = os.path.join(HERE, "..", "package", "fixture")
PACKAGE_MANY = os.path.join(HERE, "..", "package", "many")
BPM, FPS, SIZE = 124, 30, [480, 270]
# A Move: name, tier, Key Pose in, Key Pose out, beats, cut points, beats with a Hit. An Idle Clip is a Move named in IDLES: looped by
# Magic, first and last frame identical. The first Move is the one the Clip Graph starts on.
MOVES = [("idle", "calm", "guard", "guard", 4, [0, 2], []), ("jab_cross", "build", "guard", "guard", 4, [0, 2], [1, 2]),
         ("front_kick", "drop", "guard", "guard", 4, [0, 2], [2]), ("take_hit", "build", "guard", "guard", 4, [0, 2], [1])]
IDLES = {"guard": "idle"}
KEY_POSES = ["guard"]
CUTS = {4: [0, 2], 8: [0, 2, 4, 6], 16: [0, 4, 8, 12]}
# 3 Key Poses; every Key Pose has two ways out in every tier (stay, and move on around the ring guard, crouch, stance), with lengths of 4, 8 and 16 beats
MANY_MOVES = [("idle_guard", "calm", "guard", "guard", 4, CUTS[4], []), ("idle_crouch", "calm", "crouch", "crouch", 4, CUTS[4], []),
              ("idle_stance", "calm", "stance", "stance", 4, CUTS[4], [])] + [
    (name, tier, a, b, n, CUTS[n], hits) for tier, rows in {
        "calm": [("sway", "guard", "guard", 4, []), ("duck", "guard", "crouch", 4, []), ("crouch_hold", "crouch", "crouch", 8, []),
                 ("rise_side", "crouch", "stance", 4, []), ("stance_shift", "stance", "stance", 8, []), ("recover", "stance", "guard", 16, [])],
        "build": [("jab_cross", "guard", "guard", 4, [1, 2]), ("feint_duck", "guard", "crouch", 8, [4]), ("crouch_weave", "crouch", "crouch", 4, [2]),
                  ("spring_up", "crouch", "stance", 8, [6]), ("side_step", "stance", "stance", 4, [2]), ("pivot_back", "stance", "guard", 4, [1])],
        "drop": [("front_kick", "guard", "guard", 4, [2]), ("flying_knee", "guard", "crouch", 16, [8, 12]), ("sweep", "crouch", "crouch", 8, [4]),
                 ("uppercut_rise", "crouch", "stance", 4, [2]), ("spin_kick", "stance", "stance", 16, [4, 12]), ("roundhouse", "stance", "guard", 8, [4])],
    }.items() for name, a, b, n, hits in rows]
MANY_IDLES = {"guard": "idle_guard", "crouch": "idle_crouch", "stance": "idle_stance"}
MANY_KEY_POSES = ["guard", "crouch", "stance"]
ANGLES = [("front", "CAM_FRONT"), ("side", "CAM_SIDE")]
LIMBS = ("head", "eye_l", "eye_r", "hand_l", "hand_r", "foot_l", "foot_r")
GIANT = ("g_head", "g_core", "g_hammer", "g_claw", "g_knee_l", "g_knee_r", "g_foot_l", "g_foot_r")
# package/duel: an 8th field True makes the Move an Exchange (both fighters, the duel Angles). The giant comes in the drop.
PACKAGE_DUEL = os.path.join(HERE, "..", "package", "duel")
DUEL_ANGLES = ANGLES + [("duel_wide", "CAM_DUEL_WIDE", True), ("duel_low", "CAM_DUEL_LOW", True)]
DUEL_KEY_POSES = ["guard", "crouch"]
DUEL_MOVES = [
    ("idle_guard", "calm", "guard", "guard", 4, CUTS[4], []), ("idle_crouch", "calm", "crouch", "crouch", 4, CUTS[4], []),
    ("sway", "calm", "guard", "guard", 4, CUTS[4], []), ("duck", "calm", "guard", "crouch", 4, CUTS[4], []),
    ("rise", "calm", "crouch", "guard", 4, CUTS[4], []), ("crouch_hold", "calm", "crouch", "crouch", 8, CUTS[8], []),
    ("jab_cross", "build", "guard", "guard", 4, CUTS[4], [1, 2]), ("feint_duck", "build", "guard", "crouch", 4, CUTS[4], [2]),
    ("spring_up", "build", "crouch", "guard", 8, CUTS[8], [6]), ("crouch_weave", "build", "crouch", "crouch", 4, CUTS[4], [2]),
    ("front_kick", "drop", "guard", "guard", 4, CUTS[4], [2]), ("flying_knee", "drop", "guard", "crouch", 8, CUTS[8], [4]),
    ("uppercut_rise", "drop", "crouch", "guard", 4, CUTS[4], [2]), ("sweep", "drop", "crouch", "crouch", 4, CUTS[4], [2]),
    ("duel_idle_guard", "drop", "guard", "guard", 4, CUTS[4], [], True), ("duel_idle_crouch", "drop", "crouch", "crouch", 4, CUTS[4], [], True),
    ("clash", "drop", "guard", "guard", 4, CUTS[4], [2], True), ("hammer_dodge", "drop", "guard", "crouch", 8, CUTS[8], [4], True),
    ("claw_counter", "drop", "crouch", "guard", 4, CUTS[4], [1, 3], True), ("stomp_block", "drop", "crouch", "crouch", 8, CUTS[8], [4], True),
]
DUEL_IDLES = {"guard": "idle_guard", "crouch": "idle_crouch", "duel_guard": "duel_idle_guard", "duel_crouch": "duel_idle_crouch"}
PACKAGE_VARIANTS = os.path.join(HERE, "..", "package", "variants")


def with_variants(moves, idles, n=4, n_idle=3):
    """Each Move followed by its variants <name>_v2.. (n in all, n_idle for an Idle Clip): (moves, {variant: base})."""
    out, of = [], {}
    for mv in moves:
        out.append(mv)
        for v in range(2, (n_idle if mv[0] in idles.values() else n) + 1):
            out.append(("%s_v%d" % (mv[0], v),) + tuple(mv[1:]))
            of[out[-1][0]] = mv[0]
    return out, of


VARIANT_MOVES, VARIANT_OF = with_variants(DUEL_MOVES, DUEL_IDLES)
BACKDROPS, BACKDROP_FRAMES = ["arclink_city_1", "chipset_04", "greeble_01", "greeble_03"], 60


def duel(entry):
    """An Angle or a Move entry's duel flag (an optional last field)."""
    return len(entry) > 2 and entry[-1] is True


def manifest(moves=MOVES, idles=IDLES, key_poses=KEY_POSES, angles=ANGLES, variants=None, backdrops=()):
    variants = variants or {}
    clips = []
    for mv in moves:
        move, tier, key_in, key_out, beats, cuts = mv[:6]
        exchange = len(mv) > 7 and mv[7] is True
        for a in angles:
            if duel(a) != exchange:
                continue
            cid = "%s__%s" % (move, a[0])
            clip = {"id": cid, "move": move, "angle": a[0], "beats": beats, "frames": frames_for(beats, BPM, FPS), "key_in": key_in,
                    "key_out": key_out, "tier": tier, "idle": variants.get(move, move) in idles.values(), "cut_points": cuts,
                    "passes": {p: "%s/%s.mov" % (p, cid) for p in ("beauty", "shadow", "depth")},
                    "clip_data": "clip_data/%s.json" % cid, "camera_track": "camera/%s.json" % a[0]}
            if exchange:
                clip["opponent"] = True
            if move in variants:
                clip["variant_of"] = variants[move]
            clips.append(clip)
    out = {"version": 1, "bpm": BPM, "fps": FPS, "size": SIZE, "key_poses": list(key_poses),
           "angles": [dict({"id": a[0], "camera": a[1]}, **({"opponent": True} if duel(a) else {})) for a in angles], "clips": clips}
    if backdrops:
        out["backdrops"] = [{"id": b, "frames": BACKDROP_FRAMES, "angles": {a[0]: "backdrop/%s/%s.mov" % (b, a[0]) for a in angles}} for b in backdrops]
    return out


def clip_data(clip, hit_beats):
    n = clip["frames"]
    per_beat = FPS * 60.0 / BPM
    base = {"head": (0.5, 0.25), "eye_l": (0.48, 0.24), "eye_r": (0.52, 0.24), "hand_l": (0.4, 0.5), "hand_r": (0.6, 0.5),
            "foot_l": (0.45, 0.9), "foot_r": (0.55, 0.9)}
    frames = []
    for f in range(n):
        sway = 0.02 * ((f / n) * 2 - 1)
        e = {"f": f}
        for k in LIMBS:
            e[k] = [round(base[k][0] + sway, 4), base[k][1], 3.0]
        if clip.get("opponent"):
            for i, k in enumerate(GIANT):
                e[k] = [0.75, round(0.1 + 0.1 * i, 2), 9.0]
        frames.append(e)
    hits = [{"f": min(n - 1, int(b * per_beat)), "point": [0.6, 0.5, 2.9], "strength": 0.8, "limb": "hand_r"} for b in hit_beats]
    if clip.get("opponent"):        # an Exchange: the Android and the giant strike in turn
        hits = [dict(h, limb="hand_r" if i % 2 == 0 else "g_hammer", target="g_core" if i % 2 == 0 else "head") for i, h in enumerate(hits)]
    return {"clip": clip["id"], "frames": frames, "hits": hits}


def camera_track(angle_index, frames, angles=ANGLES):
    entry = {"location": [0.0, -6.0 + angle_index * 2, 1.6], "rotation": [0.7071, 0.7071, 0.0, 0.0], "focal_length": 50.0,
             "sensor_width": 36.0}
    return {"angle": angles[angle_index][0], "camera": angles[angle_index][1], "frames": [dict(entry, f=f) for f in range(frames)]}


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=1)
        f.write("\n")


def write_package(root=PACKAGE, moves=MOVES, idles=IDLES, key_poses=KEY_POSES, angles=ANGLES, variants=None, backdrops=()):
    m = manifest(moves, idles, key_poses, angles, variants, backdrops)
    write_json(os.path.join(root, "manifest.json"), m)
    hits = {mv[0]: mv[6] for mv in moves}
    for c in m["clips"]:
        write_json(os.path.join(root, c["clip_data"]), clip_data(c, hits[c["move"]]))
    for i, a in enumerate(angles):
        write_json(os.path.join(root, "camera", "%s.json" % a[0]), camera_track(i, max(c["frames"] for c in m["clips"]), angles))
    return m


def render_media(root=PACKAGE, m=None):
    m = m or manifest()
    w, h = SIZE
    for i, c in enumerate(m["clips"]):
        card = "testsrc2=size=%dx%d:rate=%d,hue=h=%d" % (w, h, FPS, i * 45)
        radius = "H*0.4"
        if c["idle"]:       # a still card and a disc breathing once per Clip: frame 0 and the last frame are equal, so Magic loops it
            card = "color=c=0x305080:size=%dx%d:rate=%d" % (w, h, FPS)
            radius = "H*(0.4+0.02*sin(2*PI*N/%d))" % (c["frames"] - 1)
        beauty = ["-f", "lavfi", "-i", card, "-f", "lavfi", "-i", "color=white:size=%dx%d:rate=%d" % (w, h, FPS),
                  "-filter_complex", "[1]format=gray,geq=lum='if(lt(hypot(X-W/2,Y-H/2),%s),255,0)'[a];" % radius +
                  "[0][a]alphamerge,format=yuva444p10le", "-c:v", "prores_ks", "-profile:v", "4444"]
        grey = ["-f", "lavfi", "-i", card + ",format=gray,format=yuv422p10le", "-c:v", "prores_ks", "-profile:v", "3"]
        for name, args in (("beauty", beauty), ("shadow", grey), ("depth", grey)):
            out = os.path.join(root, c["passes"][name])
            os.makedirs(os.path.dirname(out), exist_ok=True)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args, "-frames:v", str(c["frames"]), out], check=True)
    for i, bd in enumerate(m.get("backdrops", [])):     # opaque H.264 plates: a hue per backdrop, a bar per Angle that crosses in whole loops of 2 s
        for j, (angle, rel) in enumerate(sorted(bd["angles"].items())):
            out = os.path.join(root, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            card = "smptebars=size=%dx%d:rate=%d,hue=h=%d,drawbox=x='mod(t*%d,iw)':y=%d:w=24:h=ih/4:color=white:t=fill" % (w, h, FPS, 60 + i * 80, w // 2 * (j + 1), h // 2)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", card, "-frames:v", str(bd["frames"]), "-c:v", "libx264", "-pix_fmt", "yuvj420p",
                            "-color_range", "pc", out], check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--media", action="store_true", help="also render the placeholder Clips with ffmpeg")
    ap.add_argument("--many", action="store_true", help="the package with 3 Key Poses and mixed lengths (package/many)")
    ap.add_argument("--duel", action="store_true", help="the package with Exchanges on duel Angles (package/duel)")
    ap.add_argument("--variants", action="store_true", help="package/duel with variants of every Move (package/variants)")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.variants:
        a.out = a.out or PACKAGE_VARIANTS
        m = write_package(a.out, VARIANT_MOVES, DUEL_IDLES, DUEL_KEY_POSES, DUEL_ANGLES, VARIANT_OF, BACKDROPS)
    elif a.duel:
        a.out = a.out or PACKAGE_DUEL
        m = write_package(a.out, DUEL_MOVES, DUEL_IDLES, DUEL_KEY_POSES, DUEL_ANGLES)
    elif a.many:
        a.out = a.out or PACKAGE_MANY
        m = write_package(a.out, MANY_MOVES, MANY_IDLES, MANY_KEY_POSES)
    else:
        a.out = a.out or PACKAGE
        m = write_package(a.out)
    if a.media:
        render_media(a.out, m)
    print("wrote %s (%d clips%s)" % (os.path.abspath(a.out), len(m["clips"]), ", media" if a.media else ""))


if __name__ == "__main__":
    main()
