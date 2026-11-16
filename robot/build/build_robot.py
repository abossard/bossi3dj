"""Robot Scene build: the Android, its Moves, the foundry set and the Shot Cameras, generated into a .blend
that nobody edits by hand; renders Clips and exports Clip Data, Camera Tracks and the Manifest
(robot/CONTRACTS.md). Every Blender run needs the Blender slot (AGENTS.md, "Shared machine").

    B=/Applications/Blender.app/Contents/MacOS/Blender
    $B -b --factory-startup -P robot/build/build_robot.py -- build [--out robot/build/robot.blend]
    $B -b robot/build/robot.blend -P robot/build/build_robot.py -- export --package robot/package/v1
    $B -b robot/build/robot.blend -P robot/build/build_robot.py -- render --package robot/package/v1 \\
        [--clip jab_cross__side ...] [--samples 128] [--percent 100] [--frames 0-57] [--preview]
    $B -b robot/build/robot.blend -P robot/build/build_robot.py -- check [--out FILE]
    $B -b robot/build/robot.blend -P robot/build/build_robot.py -- check-renders --package robot/package/v1

The beauty Pass is written as <package>/beauty/<clip id>.mov (qtrle, RGBA); Shadow and Depth Pass frames land in
<package>/<pass>/<clip id>/NNNN.<ext> (git-ignored) and wait for the encode step to <pass>/<clip id>.mov.
"""
import argparse
import json
import math
import os
import sys

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import moves  # noqa: E402

SIZE = (1920, 1080)
DEFAULT_BLEND = os.path.join(HERE, "robot.blend")
POINTS = ("head", "eye_l", "eye_r", "hand_l", "hand_r", "foot_l", "foot_r")
# Shot Cameras: id, camera name, location, aim point, focal length (mm). The Android stands at the origin, faces -Y.
ANGLES = (
    ("front", "ShotCamera.front", (-2.32, -3.51, 0.55), (0.0, -0.20, 1.05), 32.0),   # low front, the guard's chest faces it (review/camera_sweep.py)
    ("side", "ShotCamera.side", (6.50, -0.35, 1.30), (0.0, -0.35, 1.00), 35.0),     # wide side, lead side
)
UP = Matrix.Rotation(math.radians(90.0), 4, "X")      # part frame: x width, y up, z forward (-Y)
FWD = Matrix.Rotation(math.radians(180.0), 4, "Z")    # part frame: y toward the toes (-Y), z up
SODIUM = (1.0, 0.60, 0.24)
MOLTEN = (1.0, 0.32, 0.06)


# ---------- rig ----------

def _rig_bones():
    """(name, head, tail, parent, deform, connected) in rest pose, metres."""
    b = [("root", (0, 0, 0), (0, 0, 0.3), None, False, False),
         ("hips", (0, 0, 1.00), (0, 0, 1.12), "root", True, False),
         ("spine", (0, 0, 1.12), (0, 0, 1.36), "hips", True, True),
         ("chest", (0, 0, 1.36), (0, 0, 1.62), "spine", True, True),
         ("neck", (0, 0, 1.62), (0, 0, 1.70), "chest", True, True),
         ("head", (0, 0, 1.70), (0, 0, 1.98), "neck", True, True)]
    for s, sfx in ((1, ".L"), (-1, ".R")):
        b += [("upperarm" + sfx, (0.25 * s, 0, 1.54), (0.27 * s, 0.04, 1.25), "chest", True, False),
              ("forearm" + sfx, (0.27 * s, 0.04, 1.25), (0.27 * s, 0, 0.97), "upperarm" + sfx, True, True),
              ("hand" + sfx, (0.27 * s, 0, 0.97), (0.27 * s, 0, 0.87), "forearm" + sfx, True, True),
              ("thigh" + sfx, (0.11 * s, 0, 0.96), (0.11 * s, -0.03, 0.53), "hips", True, False),
              ("shin" + sfx, (0.11 * s, -0.03, 0.53), (0.11 * s, 0, moves.ANKLE_Z), "thigh" + sfx, True, True),
              ("hand_ik" + sfx, (0.27 * s, 0, 0.97), (0.27 * s, 0, 1.07), "root", False, False),
              ("foot_ik" + sfx, (0.11 * s, 0, moves.ANKLE_Z), (0.11 * s, 0, 0.20), "root", False, False),
              ("foot" + sfx, (0.11 * s, 0, moves.ANKLE_Z), (0.11 * s, -0.16, 0.03), "foot_ik" + sfx, True, False),
              ("elbow_pole" + sfx, (0.55 * s, 0.45, 1.0), (0.55 * s, 0.45, 1.1), "root", False, False),
              ("knee_pole" + sfx, (0.15 * s, -1.0, 0.55), (0.15 * s, -1.0, 0.65), "root", False, False)]
    return b


BONES = _rig_bones()
REST_HEAD = {name: Vector(head) for name, head, *_ in BONES}
# channel -> (bone, "loc" | "rot"); every bone here points up at rest with roll 0 (see moves.py)
CHANNEL_BONES = {"hips": ("hips", "loc"), "hips_rot": ("hips", "rot"), "spine_rot": ("spine", "rot"),
                 "chest_rot": ("chest", "rot"), "head_rot": ("head", "rot"),
                 "hand_l": ("hand_ik.L", "loc"), "hand_r": ("hand_ik.R", "loc"),
                 "foot_l": ("foot_ik.L", "loc"), "foot_l_rot": ("foot_ik.L", "rot"),
                 "foot_r": ("foot_ik.R", "loc"), "foot_r_rot": ("foot_ik.R", "rot")}
IK_CHAINS = (("forearm.L", "hand_ik.L", "elbow_pole.L"), ("forearm.R", "hand_ik.R", "elbow_pole.R"),
             ("shin.L", "foot_ik.L", "knee_pole.L"), ("shin.R", "foot_ik.R", "knee_pole.R"))


def to_bone_local(v):
    """Root-space offset to the local frame of an up-pointing bone with roll 0 (x, y=up, z=-Y)."""
    return Vector((v.x, v.z, -v.y))


def apply_pose(arm, pose):
    for ch, (bone, kind) in CHANNEL_BONES.items():
        pb = arm.pose.bones[bone]
        if kind == "loc":
            pb.location = to_bone_local(Vector(pose[ch]) - REST_HEAD[bone])
        else:
            pb.rotation_euler = [math.radians(a) for a in pose[ch]]


def build_rig(coll):
    data = bpy.data.armatures.new("Android")
    arm = bpy.data.objects.new("Android", data)
    coll.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for name, head, tail, parent, deform, connected in BONES:
        eb = data.edit_bones.new(name)
        eb.head, eb.tail, eb.roll, eb.use_deform = head, tail, 0.0, deform
        if parent:
            eb.parent = data.edit_bones[parent]
            eb.use_connect = connected
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
    for owner, target, pole in IK_CHAINS:
        c = arm.pose.bones[owner].constraints.new("IK")
        c.target, c.subtarget, c.pole_target, c.pole_subtarget, c.chain_count = arm, target, arm, pole, 2
    return arm


def calibrate_poles(arm):
    """Pick each pole angle so the elbow or knee bends toward its pole in the guard pose."""
    apply_pose(arm, moves.GUARD)
    for owner, _target, pole in IK_CHAINS:
        c = arm.pose.bones[owner].constraints["IK"]
        best = None
        for deg in range(-180, 180, 5):
            c.pole_angle = math.radians(deg)
            bpy.context.view_layer.update()
            pb = arm.pose.bones[owner]
            root, mid, tip = pb.parent.head, pb.head, pb.tail
            line = (tip - root).normalized()
            off = lambda p: (p - root) - line * (p - root).dot(line)  # noqa: E731
            score = off(mid).normalized().dot(off(arm.pose.bones[pole].head).normalized())
            if best is None or score > best[0]:
                best = (score, deg)
        c.pole_angle = math.radians(best[1])
    apply_pose(arm, moves.GUARD)


# ---------- parts ----------

def _mesh_box(name, w, l, d, taper=1.0):
    """Box with x width w, y length l, z depth d, centred; the +y end scaled by taper in x and z."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        k = taper if v.co.y > 0 else 1.0
        v.co = Vector((v.co.x * w * k, v.co.y * l, v.co.z * d * k))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def _mesh_sphere(name, r, scale=(1, 1, 1)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=32, radius=r)
    for v in bm.verts:
        v.co = Vector((v.co.x * scale[0], v.co.y * scale[1], v.co.z * scale[2]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def _mesh_cylinder(name, r, h):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=r, radius2=r, depth=h)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def _bone_parent(obj, arm, bone, world):
    db = arm.data.bones[bone]
    parent = arm.matrix_world @ db.matrix_local @ Matrix.Translation((0, db.length, 0))
    obj.parent, obj.parent_type, obj.parent_bone = arm, "BONE", bone
    obj.matrix_parent_inverse = parent.inverted()
    obj.matrix_basis = world


def _add_part(coll, arm, name, bone, me, world, mat, bevel=0.012):
    obj = bpy.data.objects.new(name, me)
    coll.objects.link(obj)
    me.materials.append(mat)
    me.shade_smooth()
    if bevel:
        m = obj.modifiers.new("Bevel", "BEVEL")
        m.width, m.segments, m.limit_method, m.harden_normals = bevel, 3, "ANGLE", True
    obj["robot_part"] = bone
    _bone_parent(obj, arm, bone, world)
    return obj


def _along(arm, bone, t=0.5):
    """World matrix at fraction t along a bone, axes of the bone (y along it)."""
    db = arm.data.bones[bone]
    m = db.matrix_local.copy()
    m.translation = db.head_local.lerp(db.tail_local, t)
    return m


def build_parts(coll, arm, mats):
    steel, gun, visor = mats["steel"], mats["gunmetal"], mats["visor"]
    at = lambda frame, x, y, z: Matrix.Translation((x, y, z)) @ frame  # noqa: E731
    P = lambda *a, **k: _add_part(coll, arm, *a, **k)  # noqa: E731
    P("pelvis", "hips", _mesh_box("pelvis", 0.32, 0.16, 0.22, 1.1), at(UP, 0, 0, 0.99), gun)
    P("abdomen", "spine", _mesh_cylinder("abdomen", 0.10, 0.32), Matrix.Translation((0, 0, 1.22)), gun, bevel=0.006)
    P("ab_plate", "spine", _mesh_box("ab_plate", 0.20, 0.14, 0.06), at(UP, 0, -0.08, 1.22), steel)
    P("chest", "chest", _mesh_box("chest", 0.34, 0.30, 0.26, 1.35), at(UP, 0, 0, 1.48), steel, bevel=0.02)
    P("back_pack", "chest", _mesh_box("back_pack", 0.24, 0.22, 0.10), at(UP, 0, 0.16, 1.47), gun)
    P("neck", "neck", _mesh_cylinder("neck", 0.05, 0.12), Matrix.Translation((0, 0, 1.66)), gun, bevel=0.004)
    P("head", "head", _mesh_box("head", 0.17, 0.24, 0.23, 1.12), at(UP, 0, 0.01, 1.83), steel, bevel=0.025)
    P("visor", "head", _mesh_box("visor", 0.17, 0.045, 0.03), at(UP, 0, -0.11, 1.855), visor, bevel=0.008)
    P("crest", "head", _mesh_box("crest", 0.03, 0.03, 0.20), at(UP, 0, 0.0, 1.965), steel, bevel=0.008)
    for s, sfx in ((1, ".L"), (-1, ".R")):
        P("shoulder" + sfx, "upperarm" + sfx, _mesh_sphere("shoulder", 0.10, (1.15, 1.0, 0.85)),
          Matrix.Translation((0.26 * s, 0, 1.56)), steel, bevel=0)
        P("upperarm" + sfx, "upperarm" + sfx, _mesh_box("upperarm", 0.11, 0.26, 0.11, 0.85),
          _along(arm, "upperarm" + sfx), steel)
        P("elbow" + sfx, "forearm" + sfx, _mesh_sphere("elbow", 0.055), Matrix.Translation((0.27 * s, 0.04, 1.25)),
          gun, bevel=0)
        P("forearm" + sfx, "forearm" + sfx, _mesh_box("forearm", 0.12, 0.26, 0.12, 1.2),
          _along(arm, "forearm" + sfx), steel, bevel=0.015)
        P("fist" + sfx, "hand" + sfx, _mesh_box("fist", 0.10, 0.11, 0.11), _along(arm, "hand" + sfx), steel)
        P("hip" + sfx, "thigh" + sfx, _mesh_sphere("hip", 0.07), Matrix.Translation((0.11 * s, 0, 0.96)), gun, bevel=0)
        P("thigh" + sfx, "thigh" + sfx, _mesh_box("thigh", 0.15, 0.40, 0.16, 0.8), _along(arm, "thigh" + sfx), steel)
        P("knee" + sfx, "shin" + sfx, _mesh_sphere("knee", 0.07), Matrix.Translation((0.11 * s, -0.03, 0.53)),
          gun, bevel=0)
        P("shin" + sfx, "shin" + sfx, _mesh_box("shin", 0.12, 0.38, 0.14, 0.85), _along(arm, "shin" + sfx), steel)
        P("ankle" + sfx, "foot" + sfx, _mesh_sphere("ankle", 0.055), Matrix.Translation((0.11 * s, 0, moves.ANKLE_Z)),
          gun, bevel=0)
        P("foot" + sfx, "foot" + sfx, _mesh_box("foot", 0.12, 0.27, 0.10), at(FWD, 0.11 * s, -0.06, 0.05), steel)


def build_points(coll, arm):
    """Empties whose positions become Clip Data; found by the custom property robot_point."""
    spots = {"head": ("head", (0, -0.02, 1.84)), "eye_l": ("head", (0.05, -0.125, 1.855)),
             "eye_r": ("head", (-0.05, -0.125, 1.855)), "hand_l": ("hand.L", (0.27, 0, 0.92)),
             "hand_r": ("hand.R", (-0.27, 0, 0.92)), "foot_l": ("foot.L", (0.11, -0.12, 0.05)),
             "foot_r": ("foot.R", (-0.11, -0.12, 0.05))}
    for name, (bone, co) in spots.items():
        e = bpy.data.objects.new("point." + name, None)
        e.empty_display_size = 0.03
        coll.objects.link(e)
        e["robot_point"] = name
        _bone_parent(e, arm, bone, Matrix.Translation(co))


# ---------- materials, set, lights, cameras ----------

def _material(name, base, metallic, rough, rough_noise=0.0, emission=None, strength=0.0):
    mat = bpy.data.materials.new(name)
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*base, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = rough
    if rough_noise:
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 6.0
        rng = nt.nodes.new("ShaderNodeMapRange")
        rng.inputs["To Min"].default_value, rng.inputs["To Max"].default_value = rough, rough + rough_noise
        nt.links.new(noise.outputs["Fac"], rng.inputs["Value"])
        nt.links.new(rng.outputs["Result"], bsdf.inputs["Roughness"])
    if emission:   # AgX turns a hot emitter cream-white; keep it dim and without white reflections
        bsdf.inputs["Specular IOR Level"].default_value = 0.0
        bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
        bsdf.inputs["Emission Strength"].default_value = strength
    return mat


def build_materials():
    return {"steel": _material("steel", (0.80, 0.82, 0.85), 1.0, 0.06, rough_noise=0.08),
            "gunmetal": _material("gunmetal", (0.12, 0.13, 0.14), 1.0, 0.35),
            "visor": _material("visor", (0.02, 0.02, 0.02), 0.0, 0.7, emission=(1.0, 0.35, 0.03), strength=1.5),
            "floor": _material("floor_plate", (0.06, 0.055, 0.05), 0.8, 0.45, rough_noise=0.2),
            "wall": _material("wall", (0.05, 0.045, 0.04), 0.0, 0.8),
            "iron": _material("iron", (0.10, 0.09, 0.08), 0.9, 0.5),
            "molten": _material("molten", (0.1, 0.02, 0.0), 0.0, 0.6, emission=MOLTEN, strength=8.0)}


def _set_object(coll, name, me, world, mat, camera=False):
    obj = bpy.data.objects.new(name, me)
    coll.objects.link(obj)
    me.materials.append(mat)
    obj.matrix_world = world
    obj.visible_camera = camera     # the beauty Pass holds the Android only; the set lights and mirrors it
    obj.visible_shadow = False      # the Shadow Pass holds the Android's shadow only
    obj["robot_set"] = True
    return obj


def build_set(coll, mats):
    """The foundry hall around the Android. The Live World (robot/live/) shows it; the Clips only reflect it."""
    T = Matrix.Translation
    # the Shadow Pass comes from one unbroken 12 m catcher around the Android: a floor edge at the channel and the
    # far set both left streaks in it; the hall floor below it only mirrors in the steel
    catcher = _set_object(coll, "floor_catcher", _mesh_box("floor_catcher", 12.0, 12.0, 0.02), T((0, -0.5, -0.01)),
                          mats["floor"], camera=True)
    catcher.is_shadow_catcher = True
    _set_object(coll, "floor", _mesh_box("floor", 40.0, 40.0, 0.02), T((0, 0, -0.03)), mats["floor"])
    _set_object(coll, "channel_melt", _mesh_box("channel_melt", 30.0, 1.2, 0.02), T((0, 3.5, -0.12)), mats["molten"])
    for y in (2.9, 4.1):
        _set_object(coll, "channel_wall", _mesh_box("channel_wall", 30.0, 0.06, 0.14), T((0, y, -0.07)), mats["iron"])
    for x in (-7.0, 7.0):
        for y in range(-10, 11, 4):
            _set_object(coll, "column", _mesh_box("column", 0.4, 10.0, 0.4), T((x, y, 5.0)) @ UP, mats["iron"])
    for y in (-6.0, 0.0, 6.0):
        _set_object(coll, "gantry", _mesh_box("gantry", 14.4, 0.5, 0.6), T((0, y, 8.0)), mats["iron"])
    _set_object(coll, "back_wall", _mesh_box("back_wall", 40.0, 12.0, 0.3), T((0, 12.0, 6.0)) @ UP, mats["wall"])
    world = bpy.data.worlds.new("foundry")
    bg = world.node_tree.nodes.get("Background") if world.node_tree else None
    if bg:
        bg.inputs["Color"].default_value = (0.010, 0.006, 0.004, 1.0)
    bpy.context.scene.world = world


def _aim(loc, target):
    return (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


def _light(coll, name, kind, loc, energy, color, target=None, **props):
    data = bpy.data.lights.new(name, kind)
    data.energy, data.color = energy, color
    for k, v in props.items():
        setattr(data, k, v)
    obj = bpy.data.objects.new(name, data)
    coll.objects.link(obj)
    obj.location = loc
    if target is not None:
        obj.rotation_euler = _aim(loc, target)
    return obj


def build_lights(coll):
    for i, (x, y) in enumerate(((-4, -4), (4, -4), (-4, 3), (4, 3), (0, -1))):
        _light(coll, "sodium_%d" % i, "SPOT", (x, y, 7.5), 2500.0, SODIUM, target=(x, y, 0),
               spot_size=math.radians(70), spot_blend=0.5, shadow_soft_size=0.4)
    _light(coll, "sodium_key", "SPOT", (3.0, -3.5, 5.0), 4000.0, SODIUM, target=(0, 0, 1.3),
           spot_size=math.radians(40), spot_blend=0.3, shadow_soft_size=0.3)
    _light(coll, "molten_glow", "AREA", (0, 3.5, 0.15), 3000.0, MOLTEN, target=(0, 3.5, 5.0),
           shape="RECTANGLE", size=28.0, size_y=1.0)
    _light(coll, "steel_strip", "AREA", (-2.5, -4.0, 4.5), 800.0, (0.85, 0.90, 1.0), target=(0, 0, 1.4),
           shape="RECTANGLE", size=8.0, size_y=0.6)
    _light(coll, "roof_rim", "AREA", (0, 6.0, 9.0), 1500.0, (0.55, 0.70, 1.0), target=(0, 0, 1.4), size=6.0)


def build_cameras(coll):
    for _id, name, loc, target, lens in ANGLES:
        cam = bpy.data.cameras.new(name)
        cam.lens, cam.sensor_width, cam.sensor_fit = lens, 36.0, "HORIZONTAL"
        obj = bpy.data.objects.new(name, cam)
        coll.objects.link(obj)
        obj.location, obj.rotation_euler = loc, _aim(loc, target)
        obj["robot_angle"] = _id


# ---------- Moves ----------

def bake_moves(arm):
    """One Action per Move, a key on every frame from moves.py, linear between them."""
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
    arm.animation_data_create()
    for name, move in moves.MOVES.items():
        act = bpy.data.actions.new("move." + name)
        act.use_fake_user = True
        arm.animation_data.action = act
        for f, pose in enumerate(moves.frames(move)):
            apply_pose(arm, pose)
            for ch, (bone, kind) in CHANNEL_BONES.items():
                arm.pose.bones[bone].keyframe_insert("location" if kind == "loc" else "rotation_euler", frame=f)
    arm.animation_data.action = bpy.data.actions["move." + next(iter(moves.MOVES))]


# ---------- render settings ----------

def setup_render(scene):
    r = scene.render
    r.engine = "CYCLES"
    r.resolution_x, r.resolution_y, r.resolution_percentage = SIZE[0], SIZE[1], 100
    r.fps, r.fps_base = moves.FPS, 1.0
    r.film_transparent = True
    r.use_motion_blur, r.motion_blur_shutter = True, 0.5
    set_beauty_format(scene, "qtrle")
    scene.cycles.device = "GPU"
    scene.cycles.samples, scene.cycles.adaptive_threshold = 128, 0.02
    scene.cycles.use_denoising = True
    c = scene.cycles
    c.max_bounces, c.diffuse_bounces, c.glossy_bounces, c.transmission_bounces, c.volume_bounces = 6, 2, 3, 0, 0
    c.caustics_reflective = c.caustics_refractive = False
    c.sample_clamp_indirect = 3.0
    scene.view_settings.view_transform = "AgX"
    vl = scene.view_layers[0]
    vl.use_pass_z = True
    vl.cycles.use_pass_shadow_catcher = True
    _setup_passes(scene)


# Beauty Pass formats: qtrle is the Clip format (R4 decode cost, 2026-11-16); prores and png for comparison.
BEAUTY_FORMATS = {"qtrle": ("QTRLE", None), "prores": ("PRORES", "4444"), "png": (None, None)}


def set_beauty_format(scene, name):
    """Beauty with alpha to the main output: an RGBA QuickTime movie, or a 16-bit PNG sequence for png."""
    im, codec_profile = scene.render.image_settings, BEAUTY_FORMATS[name]
    codec, profile = codec_profile
    if codec is None:
        im.media_type = "IMAGE"
        im.file_format, im.color_mode, im.color_depth = "PNG", "RGBA", "16"
        return
    im.media_type = "VIDEO"
    im.file_format = "FFMPEG"
    ff = scene.render.ffmpeg
    ff.format, ff.codec = "QUICKTIME", codec
    if profile:
        ff.ffmpeg_prores_profile = profile
    ff.audio_codec = "NONE"
    im.color_mode = "RGBA"


def _setup_passes(scene):
    """Beauty with alpha to the main output; Shadow Pass (black, alpha = shadow) and Depth Pass (metres) to files."""
    tree = bpy.data.node_groups.new("Robot Passes", "CompositorNodeTree")
    scene.compositing_node_group = tree
    tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    n, link = tree.nodes, tree.links.new
    rl = n.new("CompositorNodeRLayers")
    out = n.new("NodeGroupOutput")
    link(rl.outputs["Image"], out.inputs[0])
    bw = n.new("CompositorNodeRGBToBW")
    link(rl.outputs["Shadow Catcher"], bw.inputs[0])
    inv = n.new("ShaderNodeMath")
    inv.operation, inv.use_clamp = "SUBTRACT", True
    inv.inputs[0].default_value = 1.0
    link(bw.outputs[0], inv.inputs[1])
    sa = n.new("CompositorNodeSetAlpha")
    sa.inputs["Image"].default_value = (0.0, 0.0, 0.0, 1.0)
    link(inv.outputs[0], sa.inputs["Alpha"])
    shadow = n.new("CompositorNodeOutputFile")
    shadow.name = "shadow"
    shadow.format.media_type = "IMAGE"
    shadow.format.file_format, shadow.format.color_mode, shadow.format.color_depth = "PNG", "RGBA", "16"
    shadow.file_name = ""
    shadow.file_output_items.new("RGBA", "####")
    link(sa.outputs[0], shadow.inputs[0])
    depth = n.new("CompositorNodeOutputFile")
    depth.name = "depth"
    depth.format.media_type = "IMAGE"
    depth.format.file_format, depth.format.color_mode, depth.format.color_depth = "OPEN_EXR", "BW", "16"
    depth.file_name = ""
    depth.file_output_items.new("FLOAT", "####")
    link(rl.outputs["Depth"], depth.inputs[0])


def use_gpu():
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = True


# ---------- build ----------

def build(out):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = "Robot"
    scene.frame_start, scene.frame_end = 0, _longest() - 1
    scene["robot_build"] = "robot/build/build_robot.py (generated, do not edit)"
    colls = {}
    for name in ("Android", "Set", "Lights", "Cameras"):
        colls[name] = bpy.data.collections.new(name)
        scene.collection.children.link(colls[name])
    mats = build_materials()
    arm = build_rig(colls["Android"])
    build_parts(colls["Android"], arm, mats)
    build_points(colls["Android"], arm)
    calibrate_poles(arm)
    build_set(colls["Set"], mats)
    build_lights(colls["Lights"])
    build_cameras(colls["Cameras"])
    bake_moves(arm)
    setup_render(scene)
    scene.camera = bpy.data.objects[ANGLES[0][1]]
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out), relative_remap=True)
    print("built", out)


# ---------- clips, export ----------

def clip_list():
    """[(clip id, move, angle id, camera name)], Moves in table order, Angles in ANGLES order."""
    return [("%s__%s" % (m, a), m, a, cam) for m in moves.MOVES for a, cam, *_ in ANGLES]


def _arm():
    return next(o for o in bpy.data.objects if o.type == "ARMATURE")


def _points():
    return {o["robot_point"]: o for o in bpy.data.objects if "robot_point" in o}


def _longest():
    return max(moves.move_frames(m) for m in moves.MOVES.values())


def _use_move(scene, move):
    _arm().animation_data.action = bpy.data.actions["move." + move]
    scene.frame_start, scene.frame_end = 0, moves.move_frames(moves.MOVES[move]) - 1


def _project(scene, cam, co):
    x, y, depth = world_to_camera_view(scene, cam, co)
    return [round(x, 4), round(1.0 - y, 4), round(depth, 3)]


def export_clip_data(scene, clip_id, move, cam):
    _use_move(scene, move)
    pts = _points()
    frames = []
    for f in range(moves.move_frames(moves.MOVES[move])):
        scene.frame_set(f)
        entry = {"f": f}
        entry.update({p: _project(scene, cam, pts[p].matrix_world.translation) for p in POINTS})
        frames.append(entry)
    hits = [{"f": h["f"], "point": frames[h["f"]][h["limb"]], "strength": h["strength"], "limb": h["limb"]}
            for h in moves.hit_frames(moves.MOVES[move])]
    return {"clip": clip_id, "frames": frames, "hits": hits}


def export_camera_track(scene, angle, cam):
    """One entry per frame of the longest Clip, so every Clip finds its frame."""
    frames = []
    for f in range(_longest()):
        scene.frame_set(f)
        loc, rot, _ = cam.matrix_world.decompose()
        frames.append({"f": f, "location": [round(v, 5) for v in loc], "rotation": [round(v, 6) for v in rot],
                       "focal_length": cam.data.lens, "sensor_width": cam.data.sensor_width})
    return {"angle": angle, "camera": cam.name, "frames": frames}


def manifest():
    clips = []
    for clip_id, move, angle, _cam in clip_list():
        m = moves.MOVES[move]
        clips.append({"id": clip_id, "move": move, "angle": angle, "beats": m.beats,
                      "frames": moves.move_frames(m), "key_in": m.key_in, "key_out": m.key_out,
                      "tier": m.tier, "idle": m.idle,
                      "cut_points": moves.cut_points(m),
                      "passes": {p: "%s/%s.mov" % (p, clip_id) for p in ("beauty", "shadow", "depth")},
                      "clip_data": "clip_data/%s.json" % clip_id, "camera_track": "camera/%s.json" % angle})
    return {"version": 1, "bpm": moves.BPM, "fps": moves.FPS, "size": list(SIZE),
            "key_poses": list(moves.KEY_POSES), "angles": [{"id": a, "camera": cam} for a, cam, *_ in ANGLES],
            "clips": clips}


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")


def export(package):
    scene = bpy.context.scene
    for angle, name, *_ in ANGLES:
        _write_json(os.path.join(package, "camera", angle + ".json"),
                    export_camera_track(scene, angle, bpy.data.objects[name]))
    for clip_id, move, _angle, cam in clip_list():
        _write_json(os.path.join(package, "clip_data", clip_id + ".json"),
                    export_clip_data(scene, clip_id, move, bpy.data.objects[cam]))
    _write_json(os.path.join(package, "manifest.json"), manifest())
    print("exported", package)


# ---------- render ----------

def use_preview(scene):
    """The cheap path for reviewing motion: Eevee at half size, beauty only (Shadow and Depth outputs muted).
    Eevee has no Shadow Catcher, so the catcher floor shows as a plain floor."""
    try:
        scene.render.engine = "BLENDER_EEVEE"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.eevee.taa_render_samples = 16
    scene.render.resolution_percentage = 50
    for name in ("shadow", "depth"):
        scene.compositing_node_group.nodes[name].mute = True


def use_low(scene):
    """The low quality path for a whole Clip Library: Eevee at full size, all three Passes. The Shadow Catcher floor
    turns into a holdout (transparent in the beauty) and the Shadow Pass comes from Eevee's shadow pass on it."""
    try:
        scene.render.engine = "BLENDER_EEVEE"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.eevee.taa_render_samples = 8
    bpy.data.objects["floor_catcher"].is_holdout = True
    scene.view_layers[0].use_pass_shadow = True
    tree = scene.compositing_node_group
    rl = next(n for n in tree.nodes if n.bl_idname == "CompositorNodeRLayers")
    bw = next(n for n in tree.nodes if n.bl_idname == "CompositorNodeRGBToBW")
    tree.links.new(rl.outputs["Shadow"], bw.inputs[0])


def render(package, clip_ids, samples, percent, frame_range, beauty="qtrle", preview=False, quality="high"):
    """Beauty to <package>/beauty/<clip id>.mov (a movie, so --frames writes a movie of just those frames), or to
    <package>/beauty/<clip id>/NNNN.png for png; Shadow and Depth Pass frames to <package>/<pass>/<clip id>/.
    --preview: see use_preview; write it to a review folder, not to the package."""
    scene = bpy.context.scene
    use_gpu()
    set_beauty_format(scene, beauty)
    scene.cycles.samples, scene.render.resolution_percentage = samples, percent
    if preview:
        use_preview(scene)
    elif quality == "low":
        use_low(scene)
    tree = scene.compositing_node_group
    for clip_id, move, _angle, cam in clip_list():
        if clip_ids and clip_id not in clip_ids:
            continue
        _use_move(scene, move)
        if frame_range:
            scene.frame_start, scene.frame_end = frame_range
        scene.camera = bpy.data.objects[cam]
        base = os.path.abspath(package)
        movie = beauty != "png"
        scene.render.filepath = os.path.join(base, "beauty", clip_id + "_") if movie else \
            os.path.join(base, "beauty", clip_id, "####")
        tree.nodes["shadow"].directory = os.path.join(base, "shadow", clip_id) + os.sep
        tree.nodes["depth"].directory = os.path.join(base, "depth", clip_id) + os.sep
        bpy.ops.render.render(animation=True)
        if movie:   # Blender names a movie after its frame range; the Manifest names <clip id>.mov
            written = scene.render.frame_path(frame=scene.frame_start)
            os.replace(written, os.path.join(base, "beauty", clip_id + ".mov"))
        print("rendered", clip_id)


# ---------- checks (numbers) ----------

def _min_z(obj, dg):
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    z = min((ev.matrix_world @ v.co).z for v in me.vertices)
    ev.to_mesh_clear()
    return z


def check():
    """Per Move: how far punches reach past the arm (by design), the gap between shin and planted ankle,
    sole height of planted feet, lowest point of the Android,
    and the Key Pose match of the first and last frame (Clip Data points, metres)."""
    scene = bpy.context.scene
    arm, pts = _arm(), _points()
    feet = {s: [o for o in bpy.data.objects if o.get("robot_part") == "foot" + s] for s in (".L", ".R")}
    parts = [o for o in bpy.data.objects if "robot_part" in o]
    report = {}
    for name, move in moves.MOVES.items():
        _use_move(scene, name)
        seq = moves.frames(move)
        reach, sole, ankle, lowest, ends = 0.0, 0.0, 0.0, 1e9, []
        for f in range(len(seq)):
            scene.frame_set(f)
            dg = bpy.context.evaluated_depsgraph_get()
            pb = arm.pose.bones
            for owner, target, _pole in IK_CHAINS[:2]:
                reach = max(reach, (pb[owner].tail - pb[target].head).length)
            for s, ch in ((".L", "foot_l"), (".R", "foot_r")):
                if seq[f][ch][2] <= moves.ANKLE_Z + 1e-6 and seq[f][ch + "_rot"][0] == 0.0:
                    sole = max(sole, abs(min(_min_z(o, dg) for o in feet[s])))
                    ankle = max(ankle, (pb["shin" + s].tail - pb["foot_ik" + s].head).length)
            lowest = min(lowest, min(_min_z(o, dg) for o in parts))
            if f in (0, len(seq) - 1):
                ends.append({p: pts[p].matrix_world.translation.copy() for p in POINTS})
        key_match = max((ends[0][p] - ends[1][p]).length for p in POINTS)
        report[name] = {"hand_overreach_m": round(reach, 4), "planted_ankle_gap_m": round(ankle, 4),
                        "planted_sole_error_m": round(sole, 4),
                        "lowest_point_m": round(lowest, 4), "key_pose_end_gap_m": round(key_match, 5)}
    return report


def _load_pixels(path):
    import numpy as np
    img = bpy.data.images.load(path, check_existing=False)
    px = np.empty(len(img.pixels), dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px


def _beauty_frames(package, clip_id):
    """Beauty frames of a Clip as float RGBA arrays (0..1): decoded from <clip id>.mov with ffmpeg, else the PNG
    sequence of a --beauty png render."""
    import subprocess
    import numpy as np
    movie = os.path.join(package, "beauty", clip_id + ".mov")
    if os.path.isfile(movie):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", movie, "-f", "rawvideo", "-pix_fmt", "rgba", "-"],
                             check=True, capture_output=True).stdout
        size = SIZE[0] * SIZE[1] * 4
        for i in range(0, len(raw), size):
            yield np.frombuffer(raw[i:i + size], dtype=np.uint8).astype(np.float32) / 255.0
        return
    folder = os.path.join(package, "beauty", clip_id)
    if os.path.isdir(folder):
        for fn in sorted(f for f in os.listdir(folder) if f.endswith(".png")):
            yield _load_pixels(os.path.join(folder, fn))


def check_renders(package):
    """Per rendered Clip: Key Pose match (mean abs pixel difference of last and first beauty frame, the loop step of
    an Idle Clip), the steps out of the first and into the last frame, and flicker
    (frame-to-frame mean difference; spikes are frames above 3x the median)."""
    import numpy as np
    out = {}
    for clip_id, *_ in clip_list():
        prev, diffs, first, n = None, [], None, 0
        for px in _beauty_frames(package, clip_id):
            n += 1
            if first is None:
                first = px
            if prev is not None:
                diffs.append(float(np.mean(np.abs(px - prev))))
            prev = px
        if n < 2:
            continue
        med = float(np.median(diffs))
        out[clip_id] = {"frames": n, "key_pose_end_diff": round(float(np.mean(np.abs(prev - first))), 5),
                        "seam_neighbours": [round(diffs[0], 5), round(diffs[-1], 5)],
                        "frame_diff_median": round(med, 5), "frame_diff_max": round(max(diffs), 5),
                        "spikes": [i + 1 for i, d in enumerate(diffs) if d > 3 * med and d > 0.005]}
    return out


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="build_robot.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out", default=DEFAULT_BLEND)
    e = sub.add_parser("export")
    e.add_argument("--package", required=True)
    r = sub.add_parser("render")
    r.add_argument("--package", required=True)
    r.add_argument("--clip", action="append", default=[])
    r.add_argument("--samples", type=int, default=128)
    r.add_argument("--percent", type=int, default=100)
    r.add_argument("--frames", default="")
    r.add_argument("--beauty", choices=sorted(BEAUTY_FORMATS), default="qtrle")
    r.add_argument("--preview", action="store_true")
    r.add_argument("--quality", choices=("low", "high"), default="high")
    c = sub.add_parser("check")
    c.add_argument("--out", default="")
    cr = sub.add_parser("check-renders")
    cr.add_argument("--package", required=True)
    cr.add_argument("--out", default="")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        build(a.out)
    elif a.cmd == "export":
        export(a.package)
    elif a.cmd == "render":
        fr = tuple(int(x) for x in a.frames.split("-")) if a.frames else None
        render(a.package, set(a.clip), a.samples, a.percent, fr, a.beauty, a.preview, a.quality)
    else:
        result = check() if a.cmd == "check" else check_renders(a.package)
        text = json.dumps(result, indent=1)
        print(text)
        if a.out:
            with open(a.out, "w") as f:
                f.write(text + "\n")


if __name__ == "__main__":
    main()
