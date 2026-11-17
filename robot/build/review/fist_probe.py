"""Fist probe: the M2000's hands curled with the build's finger signs, in variants of the thumb (axis, sign, angle per
thumb bone, per hand) and of the finger curl (degrees for the base, middle and tip bone), rendered close up from the
front and the outside of each hand, one PNG per hand, view and variant, for review (rubric A1, line A2).

    $B -b --factory-startup robot/assets/humanoid_m2000/extracted/HUMANOID\\ M2000/DROID.blend \\
        -P robot/build/review/fist_probe.py -- OUT_DIR

Never pass -y: the file's scripts stay off. Round 1 (2026-11-17) swept the thumb over z/x, +/-, 30/60 with a 75 degree
curl on every finger bone: only x+60 (both hands) and z+30 (right hand) read tucked; the fingers' base knuckles read
too open from the outside.
"""
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import build_robot as br  # noqa: E402

THUMBS = {"Bone.015": "hand_l", "Bone.035": "hand_r"}
HANDS = {"hand_l": "Bone.013", "hand_r": "Bone.033"}
# name: (thumb of hand_l, thumb of hand_r, finger curl per depth: base, middle, tip)
VARIANTS = {
    "c75": (("x", 1, 60), ("z", 1, 30), (75, 75, 75)),
    "c100": (("x", 1, 60), ("z", 1, 30), (100, 90, 70)),
    "c120": (("x", 1, 60), ("z", 1, 30), (120, 95, 70)),
    "c100x": (("x", 1, 60), ("x", 1, 60), (100, 90, 70)),
}


def chain(rig, root):
    """(bone, depth) for the root and every bone below it."""
    out, todo = [], [(rig.pose.bones[root], 0)]
    while todo:
        pb, d = todo.pop()
        out.append((pb, d))
        todo += [(c, d + 1) for c in pb.children]
    return out


def pose(rig, variant):
    for pb in rig.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = (0.0, 0.0, 0.0)
    thumb_l, thumb_r, curl = variant
    for root, sign in br.M2000_FINGERS.items():
        if root in THUMBS:
            continue
        for pb, d in chain(rig, root):
            pb.rotation_euler.z += sign * math.radians(curl[min(d, 2)])
    for root, (axis, sign, deg) in zip(THUMBS, (thumb_l, thumb_r)):
        for pb, _ in chain(rig, root):
            pb.rotation_euler["xyz".index(axis)] += sign * math.radians(deg)
    bpy.context.view_layer.update()


def main():
    out = sys.argv[sys.argv.index("--") + 1]
    os.makedirs(out, exist_ok=True)
    scene = bpy.context.scene
    rig = next(o for o in scene.objects if o.type == "ARMATURE")
    try:
        scene.render.engine = "BLENDER_EEVEE"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = scene.render.resolution_y = 480
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    cam = bpy.data.objects.new("fist_cam", bpy.data.cameras.new("fist_cam"))
    cam.data.lens = 50.0
    scene.collection.objects.link(cam)
    scene.camera = cam
    for name, variant in VARIANTS.items():
        pose(rig, variant)
        for hand, bone in HANDS.items():
            pb = rig.pose.bones[bone]
            head, tail = rig.matrix_world @ pb.head, rig.matrix_world @ pb.tail
            centre = tail + (tail - head) * 0.6
            size = (tail - head).length * 5.0
            outside = Vector((1.0 if centre.x > 0 else -1.0, 0.0, 0.0))
            for view, d in (("front", Vector((0.0, 1.0, 0.15))), ("outside", outside + Vector((0.0, 0.0, 0.15)))):
                d.normalize()
                cam.location = centre + d * size
                cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
                scene.render.filepath = os.path.join(out, "%s_%s_%s.png" % (hand, view, name))
                bpy.ops.render.render(write_still=True)
    print("FISTS", out)


main()
