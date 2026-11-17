"""Mocap proof: render each Mocap Clip (mocap.py) at low quality on the front and side Angles, beauty only, into
robot/build/probe/mocap/<clip>__<angle>.mov, to set beside the hand-keyed Clips of the package (#31).

    $B -b robot/build/robot.blend -P robot/build/review/mocap_proof.py -- [CLIP...]
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import build_robot as br  # noqa: E402
import mocap  # noqa: E402

OUT = os.path.join(br.HERE, "probe", "mocap")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    scene = bpy.context.scene
    br.use_gpu()
    br.set_beauty_format(scene, "qtrle")
    br.use_low(scene)
    for name in ("shadow", "depth"):
        scene.compositing_node_group.nodes[name].mute = True
    br._giant_coll().hide_render = True
    arm = br._arm()
    for name in argv or mocap.CLIPS:
        clip = mocap.CLIPS[name]
        arm.animation_data.action = bpy.data.actions["mocap." + name]
        scene.frame_start, scene.frame_end = 0, mocap.frames(clip) - 1
        for angle, cam, *_ in br.ANGLES:
            scene.camera = bpy.data.objects[cam]
            base = os.path.join(OUT, "%s__%s_" % (name, angle))
            scene.render.filepath = base
            bpy.ops.render.render(animation=True)
            os.replace(scene.render.frame_path(frame=scene.frame_start), base[:-1] + ".mov")
            print("rendered", name, angle)


main()
