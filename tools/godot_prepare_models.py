"""Prepare the Sketchfab source rigs for the Godot Colossus Scene: headless Blender, glTF out.

Blender -b --factory-startup --disable-autoexec --python tools/godot_prepare_models.py -- \
    <nomad|grock> <source .blend> <output .gltf>

`make godot-models` unpacks the archives from ~/Downloads and runs both. The .blend opens with
scripts off; nothing from an archive is executed.

nomad: Nomad Marksman Rig (Hunter106.blend). Rig controls, twist and pole bones go; helper bones
    (knee, elbow, pelvis sides, finger bases, shoulder cloth) hand their weights to the bone they
    move with; the rest is renamed to Godot's humanoid profile (Root, Hips, LeftUpperLeg, ...) so
    the BoneMap at import is one to one and Mixamo clips retarget onto it. The rifle goes. Scaled
    to 1.75 m, feet at 0. Textures stay 2k.
grock: Grock Endboss (master.blend). Deform bones only (the IK targets are baked into the clips),
    all eight clips. The all-black metallic map and the flat normal map go; a normal map is made
    from the author's height map. Exported at its own size: Godot scales it to 28 m at import
    (`nodes/root_scale`), so clips and rest scale together.
"""

import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

NOMAD_HEIGHT_M = 1.75
# The height map read as the author set it (scale 1) tilts half the surface past 50 degrees:
# a crumpled look. Scaled so the median tilt is this.
GROCK_NORMAL_SLOPE_DEG = 12.0

# Bones whose weights go to another bone, which they move with in the source rig.
NOMAD_MERGE = {
    "knee.L": "thigh.L",
    "knee.R": "thigh.R",
    "elbow.L": "upperarm.L",
    "elbow.R": "upperarm.R",
    "pelvis.l": "pelvis",
    "pelvis.r": "pelvis",
    "Shouldercloth.L": "upperarm.L",
    "Shouldercloth.R": "upperarm.R",
    "thumb3.L": "thumb2.L",
    "thumb3.R": "thumb2.R",
}
for _s in "LR":
    for _f in ("indexfingerbase", "mfingerbase", "ringfingerbase", "pinkybase"):
        NOMAD_MERGE[f"{_f}.{_s}"] = f"hand.{_s}"

# Source name -> Godot SkeletonProfileHumanoid name (Scarf bones keep their names).
NOMAD_RENAME = {
    "Root Bone": "Root",
    "pelvis": "Hips",
    "spine": "Spine",
    "chest": "Chest",
    "neck": "Neck",
    "HeadIK": "Head",
}
for _s, _side in (("L", "Left"), ("R", "Right")):
    NOMAD_RENAME.update(
        {
            f"shoulder.{_s}": f"{_side}Shoulder",
            f"upperarm.{_s}": f"{_side}UpperArm",
            f"forearm.{_s}": f"{_side}LowerArm",
            f"hand.{_s}": f"{_side}Hand",
            f"thumbbase.{_s}": f"{_side}ThumbMetacarpal",
            f"thumb1.{_s}": f"{_side}ThumbProximal",
            f"thumb2.{_s}": f"{_side}ThumbDistal",
            f"thigh.{_s}": f"{_side}UpperLeg",
            f"lowerleg.{_s}": f"{_side}LowerLeg",
            f"foot.{_s}": f"{_side}Foot",
        }
    )
    for _src, _dst in (
        ("indexfinger", "Index"),
        ("mfinger", "Middle"),
        ("ringfinger", "Ring"),
        ("pinky", "Little"),
    ):
        for _i, _part in ((1, "Proximal"), (2, "Intermediate"), (3, "Distal")):
            NOMAD_RENAME[f"{_src}{_i}.{_s}"] = f"{_side}{_dst}{_part}"

# Target hierarchy after the merge (child -> parent, source names).
NOMAD_PARENT = {
    "thigh.L": "pelvis",
    "thigh.R": "pelvis",
    "chest": "spine",
    "HeadIK": "neck",
}
NOMAD_KEEP_EXTRA = {"Scarf1", "Scarf2", "Scarf3"}
NOMAD_MESHES = {"Attire", "Bae Mesh"}


def report(key: str, value: object) -> None:
    print("PREPARE " + json.dumps({key: value}))


def open_source(path: str) -> None:
    bpy.ops.wm.open_mainfile(filepath=path, load_ui=False, use_scripts=False)


def armature() -> bpy.types.Object:
    return next(o for o in bpy.data.objects if o.type == "ARMATURE")


def delete_objects(keep: set) -> None:
    for o in list(bpy.data.objects):
        if o.name not in keep:
            bpy.data.objects.remove(o, do_unlink=True)


def merge_weights(mesh: bpy.types.Object, src: str, dst: str) -> None:
    g_src = mesh.vertex_groups.get(src)
    if g_src is None:
        return
    g_dst = mesh.vertex_groups.get(dst) or mesh.vertex_groups.new(name=dst)
    for v in mesh.data.vertices:
        for g in v.groups:
            if g.group == g_src.index and g.weight > 0.0:
                g_dst.add([v.index], g.weight, "ADD")
    mesh.vertex_groups.remove(g_src)


def clear_constraints(arm: bpy.types.Object) -> None:
    for pb in arm.pose.bones:
        for c in list(pb.constraints):
            pb.constraints.remove(c)
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)
    arm.animation_data_clear()


def edit_mode(obj: bpy.types.Object) -> None:
    bpy.ops.object.mode_set(mode="OBJECT")
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")


def mesh_bounds(meshes: list) -> tuple:
    lo = np.array([math.inf] * 3)
    hi = np.array([-math.inf] * 3)
    for m in meshes:
        co = np.empty(len(m.data.vertices) * 3)
        m.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        mw = np.array(m.matrix_world)
        world = co @ mw[:3, :3].T + mw[:3, 3]
        lo = np.minimum(lo, world.min(axis=0))
        hi = np.maximum(hi, world.max(axis=0))
    return lo, hi


def image_pixels(img: bpy.types.Image) -> np.ndarray:
    w, h = img.size
    px = np.empty(w * h * img.channels, dtype=np.float32)
    img.pixels.foreach_get(px)
    return px.reshape(h, w, img.channels)


def alpha_share_used(mesh: bpy.types.Object, img: bpy.types.Image) -> float:
    """Share of the mesh's UV triangles whose centre samples alpha below 0.5."""
    px = image_pixels(img)
    h, w = px.shape[:2]
    me = mesh.data
    me.calc_loop_triangles()
    uv = me.uv_layers.active.data
    hits = 0
    for t in me.loop_triangles:
        u = sum(uv[i].uv[0] for i in t.loops) / 3.0
        v = sum(uv[i].uv[1] for i in t.loops) / 3.0
        x = int(u % 1.0 * (w - 1))
        y = int(v % 1.0 * (h - 1))
        if px[y, x, 3] < 0.5:
            hits += 1
    return hits / max(len(me.loop_triangles), 1)


def make_opaque(mat: bpy.types.Material) -> None:
    nodes = mat.node_tree.nodes
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    for link in list(bsdf.inputs["Alpha"].links):
        mat.node_tree.links.remove(link)
    bsdf.inputs["Alpha"].default_value = 1.0
    for n in list(nodes):
        if n.type == "MATH":
            nodes.remove(n)
    mat.surface_render_method = "DITHERED"
    if hasattr(mat, "blend_method"):
        mat.blend_method = "OPAQUE"


def prepare_nomad() -> dict:
    arm = armature()
    delete_objects({arm.name} | NOMAD_MESHES)
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    clear_constraints(arm)
    for m in meshes:
        for src, dst in NOMAD_MERGE.items():
            merge_weights(m, src, dst)
    used = set()
    for m in meshes:
        names = {g.index: g.name for g in m.vertex_groups}
        for v in m.data.vertices:
            for g in v.groups:
                if g.weight > 0.0:
                    used.add(names[g.group])
    keep = set(NOMAD_RENAME) | NOMAD_KEEP_EXTRA
    unmapped_used = sorted(used - keep)
    if unmapped_used:
        raise SystemExit(f"weighted bones without a place: {unmapped_used}")

    edit_mode(arm)
    eb = arm.data.edit_bones
    for child, parent in NOMAD_PARENT.items():
        eb[child].parent = eb[parent]
    # A kept bone under a removed one hangs from the nearest kept ancestor.
    for b in eb:
        if b.name in keep:
            p = b.parent
            while p is not None and p.name not in keep:
                p = p.parent
            b.parent = p
    for b in list(eb):
        if b.name not in keep:
            eb.remove(b)
    bpy.ops.object.mode_set(mode="OBJECT")
    for b in arm.data.bones:
        b.use_deform = True
    for src, dst in NOMAD_RENAME.items():
        arm.data.bones[src].name = dst  # renames the vertex groups with it
    for m in meshes:
        for g in list(m.vertex_groups):
            if g.name not in arm.data.bones:
                m.vertex_groups.remove(g)

    # Scale to 1.75 m with the feet at 0 and the hips over the origin.
    lo, hi = mesh_bounds(meshes)
    k = NOMAD_HEIGHT_M / (hi[2] - lo[2])
    hips = arm.matrix_world @ arm.data.bones["Hips"].head_local
    move = Matrix.Translation(Vector((-hips.x, -hips.y, -lo[2])))
    arm.matrix_world = Matrix.Scale(k, 4) @ move @ arm.matrix_world
    bpy.context.view_layer.update()
    for o in bpy.context.view_layer.objects:
        o.select_set(o.name == arm.name or o.name in NOMAD_MESHES)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    bpy.data.materials["Material"].use_backface_culling = True
    attire = bpy.data.materials["Attire"]
    attire_img = next(
        n.image
        for n in attire.node_tree.nodes
        if n.type == "TEX_IMAGE" and n.outputs["Alpha"].links
    )
    share = alpha_share_used(bpy.data.objects["Attire"], attire_img)
    if share == 0.0:
        make_opaque(attire)
    lo, hi = mesh_bounds(meshes)
    tris = 0
    for m in meshes:
        m.data.calc_loop_triangles()
        tris += len(m.data.loop_triangles)
    return {
        "bones": len(arm.data.bones),
        "tris": tris,
        "height_m": round(float(hi[2] - lo[2]), 4),
        "feet_z": round(float(lo[2]), 4),
        "attire_alpha_cut_share": round(share, 4),
        "bone_names": [b.name for b in arm.data.bones],
    }


def normal_from_height(height: np.ndarray, median_slope_deg: float) -> tuple:
    """OpenGL tangent-space normal map from a height map (rows bottom to top, as Blender stores),
    scaled so the median surface tilts `median_slope_deg`. Returns the map and that scale."""
    dy, dx = np.gradient(height)
    k = math.tan(math.radians(median_slope_deg)) / max(float(np.median(np.hypot(dx, dy))), 1e-9)
    n = np.stack([-dx * k, -dy * k, np.ones_like(height)], axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5, k


def prepare_grock() -> dict:
    arm = armature()
    mesh = next(o for o in bpy.data.objects if o.type == "MESH" and o.parent == arm)
    delete_objects({arm.name, mesh.name})
    mat = mesh.material_slots[0].material
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    disp = next(n for n in nodes if n.type == "DISPLACEMENT")
    height_img = disp.inputs["Height"].links[0].from_node.image
    disp_scale = disp.inputs["Scale"].default_value
    disp_mid = disp.inputs["Midlevel"].default_value
    metallic_img = bsdf.inputs["Metallic"].links[0].from_node.image
    metallic_max = float(image_pixels(metallic_img)[..., 0].max())
    normal_node = bsdf.inputs["Normal"].links[0].from_node
    old_normal = normal_node.inputs["Color"].links[0].from_node
    old_px = image_pixels(old_normal.image)
    old_flat = float(np.abs(old_px[..., :2] - 0.5).max())

    # World size of a texel: surface area over UV area.
    me = mesh.data
    me.calc_loop_triangles()
    uv = me.uv_layers.active.data
    area = sum(t.area for t in me.loop_triangles)
    uv_area = 0.0
    for t in me.loop_triangles:
        a, b, c = (uv[i].uv for i in t.loops)
        uv_area += abs((b - a).cross(c - a)) * 0.5
    w, h = height_img.size
    texel = math.sqrt(area / max(uv_area, 1e-9)) / w
    hp = image_pixels(height_img)[..., 0] - disp_mid
    nmap, strength = normal_from_height(hp, GROCK_NORMAL_SLOPE_DEG)
    slope = np.degrees(np.arccos(np.clip((nmap[..., 2] - 0.5) * 2.0, -1.0, 1.0)))

    img = bpy.data.images.new("Grock_normal", w, h, alpha=False, float_buffer=False)
    img.colorspace_settings.name = "Non-Color"
    rgba = np.concatenate([nmap, np.ones((h, w, 1))], axis=-1).astype(np.float32)
    img.pixels.foreach_set(rgba.ravel())
    img.pack()
    img.filepath_raw = "//Grock_normal.png"
    img.file_format = "PNG"
    old_normal.image = img

    # Drop the displacement, the metallic map and the identity mapping.
    for link in list(bsdf.inputs["Metallic"].links):
        links.remove(link)
    bsdf.inputs["Metallic"].default_value = 0.0
    for n in list(nodes):
        if n.type in ("DISPLACEMENT", "MAPPING", "TEX_COORD", "REROUTE", "FRAME"):
            nodes.remove(n)
        elif n.type == "TEX_IMAGE" and n.image in (height_img, metallic_img):
            nodes.remove(n)
    mat.use_backface_culling = True
    lo, hi = mesh_bounds([mesh])
    return {
        "bones_deform": sum(1 for b in arm.data.bones if b.use_deform),
        "tris": len(me.loop_triangles),
        "height_units": round(float(hi[2] - lo[2]), 4),
        "feet_z": round(float(lo[2]), 4),
        "root_scale_for_28m": round(28.0 / float(hi[2] - lo[2]), 4),
        "metallic_max": metallic_max,
        "old_normal_max_tilt": old_flat,
        "texel_units": texel,
        "displacement_scale": disp_scale,
        "normal_strength_per_texel": round(strength, 2),
        "normal_slope_deg_p50_p95": [
            round(float(np.percentile(slope, 50)), 2),
            round(float(np.percentile(slope, 95)), 2),
        ],
        "actions": [a.name for a in bpy.data.actions],
    }


def export(out: str, animations: bool) -> None:
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=out,
        export_format="GLTF_SEPARATE",
        export_texture_dir="textures",
        export_image_format="AUTO",
        use_selection=False,
        export_yup=True,
        export_apply=False,
        export_tangents=True,
        export_skins=True,
        export_def_bones=True,
        export_influence_nb=4,
        export_animations=animations,
        export_animation_mode="ACTIONS",
        export_force_sampling=True,
        export_rest_position_armature=True,
        export_lights=False,
        export_cameras=False,
        export_extras=False,
    )


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1 :]
    kind, src, out = argv
    open_source(src)
    if kind == "nomad":
        facts = prepare_nomad()
        export(out, animations=False)
    elif kind == "grock":
        facts = prepare_grock()
        export(out, animations=True)
    else:
        raise SystemExit(f"unknown model {kind}")
    report(kind, facts)


main()
