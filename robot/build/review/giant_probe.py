"""Giant machine probe: append the Security Bot (auto-run off) into the generated robot.blend, scale it to the giant's
height, stand it where GIANT.md puts it, drive it from exchanges.py through a bone map, time one Cycles and one Eevee
frame on a duel camera, and render one Exchange as an Eevee preview.

    $B -b --factory-startup robot/build/robot.blend -P robot/build/review/giant_probe.py -- OUT_DIR [EXCHANGE]
"""
import json
import math
import os
import sys
import time

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import build_robot as br  # noqa: E402
import exchanges as X  # noqa: E402
import moves  # noqa: E402

ASSET = os.path.join(HERE, "..", "..", "assets", "security_bot", "security_bot_v1", "security_bot_release_v1.blend")
RIG = "RIG-security_bot"
HEIGHT_M = float(os.environ.get("GIANT_H", "6.0"))
# a smaller giant stands closer (GIANT_Y) and its control points shrink about its root by GIANT_H / 6
GIANT_Y = float(os.environ.get("GIANT_Y", "-2.5"))
# giant control point -> Security Bot bone (IK targets and the torso; rotations on Torso and Chest)
BONE_MAP = {"g_hips": "Torso", "g_hammer": "IK-Wrist.R", "g_claw": "IK-Wrist.L",
            "g_foot_l": "IK-TGT-Ankle.L", "g_foot_r": "IK-TGT-Ankle.R"}
ROT_MAP = {"g_hips_rot": "Torso", "g_chest_rot": "Chest"}
DUEL_WIDE = ((12.0, -1.25, 2.4), (0.0, -1.25, 2.2), 24.0)


def append_bot():
    with bpy.data.libraries.load(ASSET, link=False) as (src, dst):
        dst.collections = [c for c in src.collections if c.startswith("CH")]
    coll = dst.collections[0]
    bpy.context.scene.collection.children.link(coll)
    return coll


def bot_meshes(coll):
    """The bot's body: rig widget shapes (WGT-) and the battery prop stay out of bounds and render."""
    out = []
    for o in list(coll.all_objects):          # setting hide_render while iterating all_objects ends the loop
        if o.type != "MESH":
            continue
        if o.name.startswith("WGT-") or "battery" in o.name:
            o.hide_render = True
            continue
        if not o.hide_render:
            out.append(o)
    return out


def bounds(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    zs = []
    for o in objs:
        ev = o.evaluated_get(dg)
        zs += [(ev.matrix_world @ Vector(c)).z for c in ev.bound_box]
    return min(zs), max(zs)


def place(rig, coll):
    z0, z1 = bounds(bot_meshes(coll))
    s = HEIGHT_M / (z1 - z0)
    rig.scale = (s, s, s)
    rig.rotation_euler = (0.0, 0.0, math.pi)          # the bot faces -Y; the giant faces the Android (+Y)
    rig.location = (0.0, GIANT_Y, -z0 * s)
    bpy.context.view_layer.update()
    return {"native_height_m": round(z1 - z0, 3), "scale": round(s, 3)}


def pose_giant(rig, g):
    inv = rig.matrix_world.inverted()
    for ch, bone in ROT_MAP.items():
        pb = rig.pose.bones[bone]
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = tuple(math.radians(v) for v in g[ch])
    bpy.context.view_layer.update()
    for ch, bone in BONE_MAP.items():
        pb = rig.pose.bones[bone]
        m = pb.matrix.copy()
        m.translation = inv @ Vector(g[ch])
        pb.matrix = m
        bpy.context.view_layer.update()


def key_giant(rig, f):
    for bone in set(BONE_MAP.values()) | set(ROT_MAP.values()):
        pb = rig.pose.bones[bone]
        pb.keyframe_insert("location", frame=f)
        pb.keyframe_insert("rotation_euler", frame=f)


def camera(scene):
    loc, aim, lens = DUEL_WIDE
    cam = bpy.data.objects.new("ShotCamera.duel_wide", bpy.data.cameras.new("duel_wide"))
    cam.data.lens = lens
    scene.collection.objects.link(cam)
    cam.location, cam.rotation_euler = loc, br._aim(loc, aim)
    scene.camera = cam


def time_frame(scene, path):
    scene.render.filepath = path
    t = time.time()
    bpy.ops.render.render(write_still=True)
    return round(time.time() - t, 1)


def main():
    out = sys.argv[sys.argv.index("--") + 1]
    ex = X.EXCHANGES[sys.argv[sys.argv.index("--") + 2] if len(sys.argv) > sys.argv.index("--") + 2 else "hammer_hit"]
    os.makedirs(out, exist_ok=True)
    scene = bpy.context.scene
    coll = append_bot()
    rig = bpy.data.objects[RIG]
    rep = place(rig, coll)
    rep["tris"] = sum(len(p.vertices) - 2 for o in bot_meshes(coll) for p in o.data.polygons)
    camera(scene)
    br.use_gpu()
    arm = br._arm()
    arm.animation_data.action = None
    seq = X.frames(ex)
    k = HEIGHT_M / 6.0
    if k != 1.0 or GIANT_Y != -2.5:
        def shrink(g):
            return {c: v if c.endswith("_rot") else (v[0] * k, GIANT_Y + (v[1] + 2.5) * k, v[2] * k) for c, v in g.items()}
        seq = [(a, shrink(g)) for a, g in seq]
    for f, (a, g) in enumerate(seq):
        br.apply_pose(arm, a)
        for ch, (bone, kind) in br.CHANNEL_BONES.items():
            arm.pose.bones[bone].keyframe_insert("location" if kind == "loc" else "rotation_euler", frame=f)
        pose_giant(rig, g)
        key_giant(rig, f)
    scene.frame_start, scene.frame_end = 0, len(seq) - 1
    hit = moves.beat_frame(ex.hits[0].beat) if ex.hits else len(seq) // 2
    scene.frame_set(hit)
    br.set_beauty_format(scene, "png")
    scene.cycles.samples = 64
    rep["cycles_64_s"] = time_frame(scene, os.path.join(out, "cycles_%04d.png" % hit))
    br.use_low(scene)
    rep["eevee_full_s"] = time_frame(scene, os.path.join(out, "eevee_%04d.png" % hit))
    br.use_preview(scene)
    br.set_beauty_format(scene, "qtrle")
    scene.render.filepath = os.path.join(out, ex.name + "_")
    rep["giant_height_m"], rep["giant_y"] = HEIGHT_M, GIANT_Y
    t = time.time()
    bpy.ops.render.render(animation=True)
    rep["preview_s"] = round(time.time() - t, 1)
    rep["preview_frames"] = len(seq)
    with open(os.path.join(out, "probe.json"), "w") as fh:
        json.dump(rep, fh, indent=1)
    print("PROBE", json.dumps(rep))


main()
