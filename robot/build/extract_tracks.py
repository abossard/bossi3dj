"""Extract capture tracks (#32): for each Mixamo clip in TRACKS, the Android's own channels per source frame (hips
position, and the local Euler rotations of hips, spine, chest and head, in moves.py's terms) as retargeted by
retarget.py, into robot/build/tracks/<name>.json. Idle variants (variants.py) take their micro-motion from these
without Blender. Rerun only when a source clip or the retarget changes.

    $B -b robot/build/robot.blend -P robot/build/extract_tracks.py
"""
import json
import math
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import retarget  # noqa: E402

OUT = os.path.join(HERE, "tracks")
TRACKS = {"breathing_idle": "action_adventure_pack/extracted/idle (2).fbx",
          "relaxed_idle": "locomotion_pack/extracted/idle.fbx",
          "crouched_idle": "action_adventure_pack/extracted/idle (4).fbx"}
ROT = {"hips_rot": "hips", "spine_rot": "spine", "chest_rot": "chest", "head_rot": "head"}


def main():
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    os.makedirs(OUT, exist_ok=True)
    for name, fbx in TRACKS.items():
        src = retarget.Source(os.path.join(retarget.PACKS, fbx))
        rt = retarget.Retarget(arm, src)
        f0, f1 = (int(x) for x in src.action.frame_range)
        frames = []
        for f in range(f0, f1 + 1):
            P, _feet = rt.fk(src.pose(f))
            entry = {"hips": [round(c, 4) for c in P["hips"].translation]}
            for ch, bone in ROT.items():
                entry[ch] = [round(math.degrees(a), 3) for a in rt.local(P, bone).to_euler("XYZ")]
            frames.append(entry)
        src.remove()
        with open(os.path.join(OUT, name + ".json"), "w") as fh:
            json.dump({"source": fbx, "fps": 30, "frames": frames}, fh, separators=(",", ":"))
            fh.write("\n")
        print("TRACK", name, len(frames), "frames")


main()
