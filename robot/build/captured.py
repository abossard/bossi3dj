"""Key Poses read from capture tracks (#32, tracks/*.json from extract_tracks.py). Pure, no bpy.

A captured Key Pose is the mean of a track over its frames (an idle's loop averages out its bounce and breathing),
in moves.py's channels: the hips joint less HIPS_LIFT (moves.py writes hips for a rig resting at 1.00 m), the local
rotations as they are, wrists and ankles in root space. The feet are planted: ankles at ANKLE_Z, foot targets turned
about the vertical only (toe pitch and roll 0), so both soles stand flat; or the feet of another Pose.
"""
import json
import os

TRACKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tracks")
HIPS_LIFT = 0.094          # build_robot.HIPS_LIFT: the rig's hips rest at 1.094 m
ANKLE_Z = 0.10
CHANNELS = ("hips", "hips_rot", "spine_rot", "chest_rot", "head_rot", "hand_l", "hand_r",
            "foot_l", "foot_l_rot", "foot_r", "foot_r_rot")


def key_pose(track, first=0, last=None, sink=0.0, feet=None):
    """The mean Pose of a track's frames [first:last]; the hips `sink` metres lower (more knee bend); with `feet` (a
    Pose) its feet and foot turns instead of the capture's, so a Key Pose can keep the planted spots its Moves use."""
    with open(os.path.join(TRACKS, track + ".json")) as fh:
        frames = json.load(fh)["frames"][first:last]
    mean = {ch: tuple(round(sum(f[ch][i] for f in frames) / len(frames), 4) for i in range(3)) for ch in CHANNELS}
    x, y, z = mean["hips"]
    mean["hips"] = (x, y, round(z - HIPS_LIFT - sink, 4))
    for side in ("l", "r"):
        fx, fy, _fz = mean["foot_" + side]
        mean["foot_" + side] = (fx, fy, ANKLE_Z)
        mean["foot_%s_rot" % side] = (0.0, mean["foot_%s_rot" % side][1], 0.0)
        if feet:
            mean["foot_" + side], mean["foot_%s_rot" % side] = feet["foot_" + side], feet["foot_%s_rot" % side]
    return mean
