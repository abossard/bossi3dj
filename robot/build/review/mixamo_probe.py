"""Mixamo probe: what a Mixamo clip holds, in numbers, before it is retargeted (the mocap route, #31). Per FBX: the
armature's object transform, the rest heads and tails of the bones the retarget maps, and per sampled frame the hips,
wrists and ankles in world space, so idles, plants and strike frames can be told apart without images.

    $B -b --factory-startup -P robot/build/review/mixamo_probe.py -- [STEP [FIRST LAST]] FBX...
"""
import sys

import bpy

BONES = ("Hips", "Spine", "Spine2", "Neck", "Head", "LeftArm", "LeftForeArm", "LeftHand", "LeftUpLeg", "LeftLeg",
         "LeftFoot", "LeftToeBase", "RightHand", "RightFoot")


def rnd(v):
    return "(%s)" % " ".join("%.2f" % c for c in v)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    step = int(argv.pop(0)) if argv[0].isdigit() else 5
    span = (int(argv.pop(0)), int(argv.pop(0))) if argv[0].isdigit() else None
    for path in argv:
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o)
        bpy.ops.import_scene.fbx(filepath=path)
        rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
        act = rig.animation_data.action
        f0, f1 = (int(x) for x in act.frame_range)
        print("FBX %s object loc %s rot %s scale %s frames %d..%d fps %s" % (
            path.rsplit("/", 1)[-1], rnd(rig.location), rnd(rig.rotation_euler), rnd(rig.scale), f0, f1,
            bpy.context.scene.render.fps))
        mw = rig.matrix_world
        for b in BONES:
            bone = rig.data.bones["mixamorig:" + b]
            print("REST %-12s head %s tail %s" % (b, rnd(mw @ bone.head_local), rnd(mw @ bone.tail_local)))
        scene = bpy.context.scene
        for f in range(*(span or (f0, f1)), step):
            scene.frame_set(f)
            pb = rig.pose.bones
            w = {b: mw @ pb["mixamorig:" + b].head for b in ("Hips", "LeftHand", "RightHand", "LeftFoot", "RightFoot",
                                                            "Head")}
            print("F %3d hips %s head %s hand_l %s hand_r %s foot_l %s foot_r %s" % (
                f, rnd(w["Hips"]), rnd(w["Head"]), rnd(w["LeftHand"]), rnd(w["RightHand"]), rnd(w["LeftFoot"]),
                rnd(w["RightFoot"])))


main()
