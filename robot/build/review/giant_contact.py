"""Giant contact: at a Strike frame of an Exchange, where the giant's hands really are (the deform wrist bones and the
lowest point of each hand's meshes, not the IK targets) and how far the giant's surface is from a point, cast along a
direction (round X1, line X3).

    $B -b robot/build/robot.blend -P robot/build/review/giant_contact.py -- EXCHANGE FRAME [X Y Z DX DY DZ]
"""
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import build_robot as br  # noqa: E402


def rnd(v):
    return tuple(round(c, 3) for c in v)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    move, frame = argv[0], int(argv[1])
    scene = bpy.context.scene
    br._use_move(scene, move)
    br._giant_coll().hide_render = False
    scene.frame_set(frame)
    rig = bpy.data.objects[br.GIANT_RIG]
    for pb in rig.pose.bones:
        if "wrist" in pb.name.lower() or "hand" in pb.name.lower():
            print("BONE %-28s head %s tail %s" % (pb.name, rnd(rig.matrix_world @ pb.head), rnd(rig.matrix_world @ pb.tail)))
    dg = bpy.context.evaluated_depsgraph_get()
    for ob in br._giant_coll().all_objects:
        if ob.type == "MESH" and not ob.hide_render and any(k in ob.name.lower() for k in ("hand", "arm", "finger", "gun", "claw")):
            ev = ob.evaluated_get(dg)
            low = min((ev.matrix_world @ v.co for v in ev.data.vertices), key=lambda c: c.z)
            print("MESH %-32s lowest %s" % (ob.name, rnd(low)))
    if len(argv) >= 8:
        origin, d = Vector(map(float, argv[2:5])), Vector(map(float, argv[5:8])).normalized()
        hit, loc, _n, _i, ob, _m = scene.ray_cast(dg, origin, d)
        print("RAY from %s hit %s at %s distance %s" % (rnd(origin), ob and ob.name, rnd(loc) if hit else None,
                                                       round((loc - origin).length, 3) if hit else None))


main()
