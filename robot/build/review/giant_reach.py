"""Giant reach: how low the giant's hammer hand really gets (the deform wrist and the lowest point of the right
forearm and hand meshes) for a grid of crouched smash poses, so a floor Strike can be placed where the arm reaches
(round X1, line X3, hammer_dodge).

    $B -b robot/build/robot.blend -P robot/build/review/giant_reach.py
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import build_robot as br  # noqa: E402
import exchanges as X  # noqa: E402

HAND_MESHES = ("GEO-arm_lower.R", "GEO-hand_joint.R", "GEO-shell_arm_lower.R")


def main():
    scene = bpy.context.scene
    br._use_move(scene, "duel_idle")
    rig = bpy.data.objects[br.GIANT_RIG]
    rig.animation_data.action = None
    for hz in (2.0, 1.7, 1.4):
        for chest in (45.0, 60.0, 75.0):
            for ty in (-1.4, -1.0, -0.6):
                g = X.gpose(X.LOOM, g_hips=(0.0, -2.3, hz), g_chest_rot=(chest, 0.0, 0.0), g_head_rot=(10.0, 0.0, 0.0),
                            g_hammer=(0.10, ty, 0.30), g_claw=(-1.0, -1.9, 1.6))
                br.pose_giant(rig, g)
                dg = bpy.context.evaluated_depsgraph_get()
                low = min((o.evaluated_get(dg).matrix_world @ v.co
                           for o in (bpy.data.objects[n] for n in HAND_MESHES)
                           for v in o.evaluated_get(dg).data.vertices), key=lambda c: c.z)
                w = rig.matrix_world @ rig.pose.bones["ROBO-Wrist.R"].head
                print("REACH hips_z %.1f chest %2.0f target_y %.1f wrist (%.2f %.2f %.2f) lowest (%.2f %.2f %.2f)" % (
                    hz, chest, ty, *w, *low))


main()
