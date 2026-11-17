"""Mocap check: numbers for each baked Mocap Clip (#31), the same measures as `build_robot.py check` for Moves: how
far the IK targets lie past the arms and legs, how much a planted ankle slides, the lowest point, the gap between the
first and last frame's Clip Data points and the Key Pose (or, for an Idle Clip, each other), and the largest step of
a point between frames; each with the frame (and point) where it is worst.

    $B -b robot/build/robot.blend -P robot/build/review/mocap_check.py
"""
import json
import os
import sys

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import build_robot as br  # noqa: E402
import mocap  # noqa: E402
import moves  # noqa: E402


def points(pts):
    return {p: pts[p].matrix_world.translation.copy() for p in br.POINTS}


def main():
    scene = bpy.context.scene
    arm, pts = br._arm(), br._points()
    parts = [o for o in bpy.data.objects if "robot_part" in o]
    key_pts = {}
    for key in moves.KEY_POSES:
        br.apply_pose(arm, moves.KEY_POSES[key])
        arm.animation_data.action = None
        for b in br.retarget.EXTRA_BONES:
            arm.pose.bones[b].location, arm.pose.bones[b].rotation_euler = (0, 0, 0), (0, 0, 0)
        bpy.context.view_layer.update()
        key_pts[key] = points(pts)
    report = {}
    for name, clip in mocap.CLIPS.items():
        arm.animation_data.action = bpy.data.actions["mocap." + name]
        n = mocap.frames(clip)
        reach = {c[0]: (0.0, 0) for c in br.IK_CHAINS}
        lowest, step, seq, ankle_slide = (1e9, 0), (0.0, 0, ""), [], (0.0, 0)
        prev_ankle = {}
        for f in range(n):
            scene.frame_set(f)
            dg = bpy.context.evaluated_depsgraph_get()
            pb = arm.pose.bones
            for owner, target, _pole in br.IK_CHAINS:
                reach[owner] = max(reach[owner], ((pb[owner].tail - pb[target].head).length, f))
            lowest = min(lowest, (min(br._min_z(o, dg) for o in parts), f))
            p = points(pts)
            if seq:
                step = max(step, max(((p[k] - seq[-1][k]).length, f, k) for k in p))
            seq.append(p)
            for s in (".L", ".R"):
                a = pb["shin" + s].tail.copy()
                if a.z <= moves.ANKLE_Z + 0.005 and s in prev_ankle and prev_ankle[s].z <= moves.ANKLE_Z + 0.005:
                    ankle_slide = max(ankle_slide, ((a - prev_ankle[s]).length, f))
                prev_ankle[s] = a
        ends = {"first": (seq[0], key_pts.get(clip.key_in, seq[-1])),
                "last": (seq[-1], key_pts.get(clip.key_out, seq[0]))}
        report[name] = {"frames": n, "ik_gap_m": {k: [round(v, 4), f] for k, (v, f) in reach.items()},
                        "lowest_point_m": [round(lowest[0], 4), lowest[1]],
                        "planted_ankle_slide_m": [round(ankle_slide[0], 4), ankle_slide[1]],
                        "end_gap_m": {e: round(max((a[k] - b[k]).length for k in a), 4) for e, (a, b) in ends.items()},
                        "largest_point_step_m": [round(step[0], 4), step[1], step[2]],
                        "hits": moves.hit_frames(moves.Move(name, clip.tier, clip.beats, clip.key_in, clip.key_out,
                                                            [], mocap.hits(clip)))}
    print("MOCAP " + json.dumps(report))


main()
