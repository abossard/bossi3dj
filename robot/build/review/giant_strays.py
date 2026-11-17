"""Giant strays: which parts of the Security Bot reach the Android's spot (round X1, the dark rods to the floor at the
origin). For one Exchange frame it prints every render-visible giant mesh with vertices within RADIUS of the world
origin in xy and below 2 m, the giant bones whose head or tail lies there, and the rig's constraints with no target.

    $B -b robot/build/robot.blend -P robot/build/review/giant_strays.py -- [EXCHANGE [FRAME]]
"""
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import build_robot as br  # noqa: E402

RADIUS = 1.2


def near(co):
    return Vector((co.x, co.y)).length < RADIUS and co.z < 2.0


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    move = argv[0] if argv else "duel_idle"
    frame = int(argv[1]) if len(argv) > 1 else 0
    scene = bpy.context.scene
    br._use_move(scene, move)
    scene.frame_set(frame)
    dg = bpy.context.evaluated_depsgraph_get()
    coll = br._giant_coll()
    rig = bpy.data.objects[br.GIANT_RIG]
    for ob in coll.all_objects:
        if ob.type != "MESH" or ob.hide_render:
            continue
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        hits = [ev.matrix_world @ v.co for v in me.vertices if near(ev.matrix_world @ v.co)]
        if hits:
            groups = [g.name for g in ob.vertex_groups][:6]
            print("MESH %s verts %d of %d parent %s/%s groups %s first %s" % (
                ob.name, len(hits), len(me.vertices), ob.parent.name if ob.parent else "-", ob.parent_bone or "-",
                groups, tuple(round(c, 2) for c in hits[0])))
        ev.to_mesh_clear()
    for pb in rig.pose.bones:
        for end in (pb.head, pb.tail):
            if near(rig.matrix_world @ end):
                print("BONE %s %s" % (pb.name, tuple(round(c, 2) for c in rig.matrix_world @ end)))
                break
        for c in pb.constraints:
            if hasattr(c, "target") and c.target is None and c.enabled:
                print("NOTARGET %s %s %s" % (pb.name, c.type, c.name))
    for ob in coll.all_objects:
        for c in getattr(ob, "constraints", []):
            if hasattr(c, "target") and c.target is None and c.enabled:
                print("NOTARGET object %s %s" % (ob.name, c.type))


main()
