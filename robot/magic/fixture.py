"""Fixture Render Package: 4 Moves x 2 Angles, one Key Pose, 4 beats at 124 BPM and 30 fps, at 480x270.

    python3 robot/magic/fixture.py            # manifest, Clip Data, Camera Tracks (committed)
    python3 robot/magic/fixture.py --media    # also the placeholder Clips (git-ignored; ffmpeg, ProRes)

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
BPM, FPS, SIZE = 124, 30, [480, 270]
MOVES = [("idle", "calm", [0, 2], []), ("jab_cross", "build", [0, 2], [1, 2]), ("front_kick", "drop", [0, 2], [2]),
         ("take_hit", "build", [0, 2], [1])]        # name, tier, cut points, beats with a Hit
ANGLES = [("front", "CAM_FRONT"), ("side", "CAM_SIDE")]
BEATS = 4
LIMBS = ("head", "eye_l", "eye_r", "hand_l", "hand_r", "foot_l", "foot_r")


def manifest():
    frames = frames_for(BEATS, BPM, FPS)
    clips = []
    for move, tier, cuts, _ in MOVES:
        for angle, _cam in ANGLES:
            cid = "%s__%s" % (move, angle)
            clips.append({"id": cid, "move": move, "angle": angle, "beats": BEATS, "frames": frames, "key_in": "guard",
                          "key_out": "guard", "tier": tier, "cut_points": cuts,
                          "passes": {p: "%s/%s.mov" % (p, cid) for p in ("beauty", "shadow", "depth")},
                          "clip_data": "clip_data/%s.json" % cid, "camera_track": "camera/%s.json" % angle})
    return {"version": 1, "bpm": BPM, "fps": FPS, "size": SIZE, "key_poses": ["guard"],
            "angles": [{"id": a, "camera": c} for a, c in ANGLES], "clips": clips}


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
        frames.append(e)
    hits = [{"f": min(n - 1, int(b * per_beat)), "point": [0.6, 0.5, 2.9], "strength": 0.8, "limb": "hand_r"} for b in hit_beats]
    return {"clip": clip["id"], "frames": frames, "hits": hits}


def camera_track(angle_index, frames):
    entry = {"location": [0.0, -6.0 + angle_index * 2, 1.6], "rotation": [0.7071, 0.7071, 0.0, 0.0], "focal_length": 50.0,
             "sensor_width": 36.0}
    return {"angle": ANGLES[angle_index][0], "camera": ANGLES[angle_index][1], "frames": [dict(entry, f=f) for f in range(frames)]}


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=1)
        f.write("\n")


def write_package(root=PACKAGE):
    m = manifest()
    write_json(os.path.join(root, "manifest.json"), m)
    hits = {name: h for name, _t, _c, h in MOVES}
    for c in m["clips"]:
        write_json(os.path.join(root, c["clip_data"]), clip_data(c, hits[c["move"]]))
    for i, (angle, _) in enumerate(ANGLES):
        write_json(os.path.join(root, "camera", "%s.json" % angle), camera_track(i, frames_for(BEATS, BPM, FPS)))
    return m


def render_media(root=PACKAGE, m=None):
    m = m or manifest()
    w, h = SIZE
    for i, c in enumerate(m["clips"]):
        card = "testsrc2=size=%dx%d:rate=%d,hue=h=%d" % (w, h, FPS, i * 45)
        beauty = ["-f", "lavfi", "-i", card, "-f", "lavfi", "-i", "color=white:size=%dx%d:rate=%d" % (w, h, FPS),
                  "-filter_complex", "[1]format=gray,geq=lum='if(lt(hypot(X-W/2,Y-H/2),H*0.4),255,0)'[a];"
                  "[0][a]alphamerge,format=yuva444p10le", "-c:v", "prores_ks", "-profile:v", "4444"]
        grey = ["-f", "lavfi", "-i", card + ",format=gray,format=yuv422p10le", "-c:v", "prores_ks", "-profile:v", "3"]
        for name, args in (("beauty", beauty), ("shadow", grey), ("depth", grey)):
            out = os.path.join(root, c["passes"][name])
            os.makedirs(os.path.dirname(out), exist_ok=True)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args, "-frames:v", str(c["frames"]), out], check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--media", action="store_true", help="also render the placeholder Clips with ffmpeg")
    ap.add_argument("--out", default=PACKAGE)
    a = ap.parse_args()
    m = write_package(a.out)
    if a.media:
        render_media(a.out, m)
    print("wrote %s (%d clips%s)" % (os.path.abspath(a.out), len(m["clips"]), ", media" if a.media else ""))


if __name__ == "__main__":
    main()
