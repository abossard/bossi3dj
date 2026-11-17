"""Extract capture tracks (#32): for each Mixamo clip in TRACKS, the Android's own channels per source frame as
retargeted by retarget.py, into robot/build/tracks/<name>.json: the hips joint in world space (moves.py's `hips` is
this less build_robot.HIPS_LIFT), the local Euler rotations of hips, spine, chest and head, the wrists, the ankles
and the foot targets' rotations, in moves.py's terms. Idle variants (variants.py) take their micro-motion from these
and a Key Pose can be read from one (captured.py), without Blender. Rerun only when a source clip or the retarget
changes.

    $B -b robot/build/robot.blend -P robot/build/extract_tracks.py
"""
import json
import math
import os
import sys

import bpy
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import retarget  # noqa: E402

OUT = os.path.join(HERE, "tracks")
TRACKS = {"breathing_idle": "action_adventure_pack/extracted/idle (2).fbx",
          "relaxed_idle": "locomotion_pack/extracted/idle.fbx",
          "crouched_idle": "action_adventure_pack/extracted/idle (4).fbx",
          "fighting_idle": "../fight/Fighting Idle.fbx",        # the guard Key Pose and a bouncing guard idle
          "fight_idle": "../fight/Fight Idle.fbx",              # Fight Idle-2.fbx holds the same frames
          "fight_idle_weave": "../fight/Fight Idle-3.fbx"}
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
            P, feet = rt.fk(src.pose(f))
            entry = {"hips": [round(c, 4) for c in P["hips"].translation]}
            for ch, bone in ROT.items():
                entry[ch] = [round(math.degrees(a), 3) for a in rt.local(P, bone).to_euler("XYZ")]
            for s, side in ((".L", "l"), (".R", "r")):
                entry["hand_" + side] = [round(c, 4) for c in rt.tail(P, "forearm" + s)]
                ankle = rt.tail(P, "shin" + s)
                entry["foot_" + side] = [round(c, 4) for c in ankle]
                foot = Matrix.Translation(ankle) @ feet[s].to_matrix().to_4x4()
                ik = foot @ (rt.A["foot_ik" + s].inverted() @ rt.A["foot" + s]).inverted()
                rot = (rt.A["foot_ik" + s].inverted() @ ik).to_euler("XYZ")
                entry["foot_%s_rot" % side] = [round(math.degrees(a), 3) for a in rot]
            frames.append(entry)
        src.remove()
        with open(os.path.join(OUT, name + ".json"), "w") as fh:
            json.dump({"source": fbx, "fps": 30, "frames": frames}, fh, separators=(",", ":"))
            fh.write("\n")
        print("TRACK", name, len(frames), "frames")


main()
