"""Blender part of render_plates.py: one biome, scattered as a megastructure behind the arena, rendered from each
Angle's Shot Camera as two stills, `base` and `glow` (the biome's emission times GLOW), for the host to blend into a loop.

    $B -b robot/build/robot.blend -P robot/backdrop/plates_blender.py -- JOB.json

JOB.json: {"biome": path, "scale": S, "area": [W, D], "y0": Y, "angles": [...], "out": dir, "glow": G}, optional
"per_angle": {angle: overrides}, "seed" (added to the scatter seeds), "sky", "rim", "fill" (see _light), "tag"
(suffix of the output names, for variants).
Per Angle it reopens robot.blend, hides every mesh and curve but the floor (the fighters, the giant, the foundry hall),
adds the emitter plane, scatters the biome on it, then turns, scales and moves the plane so it lies behind the Shot
Camera's target along the camera's view, wide enough to fill the lens. Compositing is off, so the package's Pass
outputs are never written. robot.blend is never saved. Writes OUT/<angle>_base.png, <angle>_glow.png, <angle>.json.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

KEEP = ("floor", "floor_catcher")
HIDE_TYPES = ("MESH", "CURVE", "SURFACE", "META", "FONT", "CURVES", "POINTCLOUD", "VOLUME", "GPENCIL", "GREASEPENCIL")


def _engine(scene):
    for name in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = name
            return
        except TypeError:
            continue
    raise RuntimeError("no Eevee engine")


def _hide_all_but_floor():
    for o in bpy.data.objects:
        if o.type not in HIDE_TYPES:
            continue
        keep = o.name.split(".")[0] in KEEP
        o.hide_render = not keep
        if keep:
            o.visible_camera = True
            o.is_holdout = False
            o.is_shadow_catcher = False


def _placement(cam, area, y0):
    """Plane centre, yaw and width: near edge y0 metres beyond the fighters (the Android at the origin, the giant
    within 3 m of it), along the view's horizontal direction; wide enough for the lens at the far edge."""
    fwd = cam.matrix_world.to_quaternion() @ Vector((0.0, 0.0, -1.0))
    flat = Vector((fwd.x, fwd.y, 0.0)).normalized()
    loc = cam.matrix_world.translation
    reach = Vector((loc.x, loc.y, 0.0)).length + 3.0
    w, d = area
    near = reach + y0
    hfov = 2.0 * math.atan(cam.data.sensor_width / 2.0 / cam.data.lens)
    width = max(w, 2.2 * math.tan(hfov / 2.0) * (near + d))
    centre = Vector((loc.x, loc.y, 0.0)) + flat * (near + d / 2.0)
    yaw = math.atan2(flat.y, flat.x) - math.pi / 2.0      # the plane's local +Y points along the view
    return centre, yaw, width, flat


def _scatter(scene, biome, scale, width, depth):
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0.0, 0.0, 0.0))
    plane = bpy.context.active_object
    plane.name = "backdrop_emitter"
    plane.scale = (width / scale, depth / scale, 1.0)
    bpy.ops.object.transform_apply(scale=True)
    floor = bpy.data.objects.get("floor")
    if floor and floor.active_material:
        plane.data.materials.append(floor.active_material)
    scene.scatter5.emitter = plane
    bpy.ops.scatter5.add_biome(emitter_name=plane.name, surfaces_names=plane.name, json_path=biome)
    return plane


def _biome_materials(biome):
    with open(biome) as f:
        d = json.load(f)
    names = {n for k, v in d.items() if k.isdigit() for n in v["instances"]}
    mats = set()
    for o in bpy.data.objects:
        if o.name.split(".")[0] in names:
            mats.update(s.material for s in o.material_slots if s.material and s.material.use_nodes)
    return mats


def _emission_inputs(mats):
    out = []
    for m in mats:
        for n in m.node_tree.nodes:
            for key in ("Emission Strength", "Strength") if n.type in ("BSDF_PRINCIPLED", "EMISSION") else ():
                s = n.inputs.get(key)
                if s is not None and not s.is_linked and s.default_value > 0.0:
                    out.append(s)
    return out


SEEDS = ("s_distribution_seed", "s_distribution_stable_seed", "s_distribution_clump_seed")


def _reseed(plane, seed):
    """Another random layout of the same biome: add `seed` to every scatter layer's distribution seeds."""
    for p in plane.scatter5.particle_systems:
        for attr in SEEDS:
            if hasattr(p, attr):
                setattr(p, attr, getattr(p, attr) + seed)


def _light(scene, flat, sky, rim, fill):
    """Plates only: `sky` lifts the world to a dim warm haze so dark structures read as silhouettes; `rim` is a low
    sun from behind the biome towards the camera, `fill` a low sun from the camera's side, energies in W/m2."""
    bg = scene.world.node_tree.nodes.get("Background") if scene.world and scene.world.node_tree else None
    if bg and sky > 0.0:
        bg.inputs["Color"].default_value = (sky, sky * 0.72, sky * 0.5, 1.0)
    yaw = math.atan2(flat.y, flat.x)
    for name, energy, toward in (("plate_rim", rim, -1.0), ("plate_fill", fill, 1.0)):
        if energy <= 0.0:
            continue
        sun = bpy.data.objects.new(name, bpy.data.lights.new(name, "SUN"))
        sun.data.energy, sun.data.color = energy, (1.0, 0.78, 0.55)
        scene.collection.objects.link(sun)
        d = Vector((math.cos(yaw), math.sin(yaw), 0.0)) * toward      # the direction the light travels, flat
        d = (d + Vector((0.0, 0.0, -0.15))).normalized()                # 8 degrees down
        sun.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def _render(scene, path):
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def plate(job, angle):
    job = dict(job, **job.get("per_angle", {}).get(angle, {}))
    bpy.ops.wm.open_mainfile(filepath=job["blend"])
    scene = bpy.context.scene
    _engine(scene)
    scene.eevee.taa_render_samples = job.get("samples", 32)
    r = scene.render
    r.resolution_percentage, r.film_transparent, r.use_motion_blur, r.use_compositing = 100, False, False, False
    if hasattr(r.image_settings, "media_type"):     # robot.blend renders movies; Blender 5 splits the media type
        r.image_settings.media_type = "IMAGE"
    r.image_settings.file_format, r.image_settings.color_mode = "PNG", "RGB"
    cam = next(o for o in bpy.data.objects if o.get("robot_angle") == angle)
    cam.data.clip_end = 3000.0
    scene.camera = cam
    scene.frame_set(0)
    _hide_all_but_floor()
    centre, yaw, width, flat = _placement(cam, job["area"], job["y0"])
    s = job["scale"]
    plane = _scatter(scene, job["biome"], s, width, job["area"][1])
    _reseed(plane, int(job.get("seed", 0)))
    plane.scale = (s, s, s)
    plane.rotation_euler = (0.0, 0.0, yaw)
    plane.location = centre
    _light(scene, flat, job.get("sky", 0.0), job.get("rim", 0.0), job.get("fill", 0.0))
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    count = sum(1 for i in dg.object_instances if i.is_instance)
    out, tag = job["out"], job.get("tag", "")
    _render(scene, os.path.join(out, angle + tag + "_base.png"))
    sockets = _emission_inputs(_biome_materials(job["biome"]))
    for sk in sockets:
        sk.default_value *= job["glow"]
    _render(scene, os.path.join(out, angle + tag + "_glow.png"))
    rep = {"angle": angle, "tag": tag, "camera": cam.name, "scale": s, "y0": job["y0"],
           "seed": job.get("seed", 0), "sky": job.get("sky", 0.0), "rim": job.get("rim", 0.0),
           "fill": job.get("fill", 0.0), "lens": cam.data.lens,
           "camera_location": [round(v, 3) for v in cam.matrix_world.translation], "size": [r.resolution_x, r.resolution_y],
           "plane_centre": [round(c, 2) for c in centre], "plane_yaw_deg": round(math.degrees(yaw), 1),
           "plane_size_m": [round(width, 1), job["area"][1]], "instances": count, "emission_inputs": len(sockets)}
    with open(os.path.join(out, angle + tag + ".json"), "w") as f:
        json.dump(rep, f, indent=1)
    print("plate", rep)


def main():
    with open(sys.argv[sys.argv.index("--") + 1]) as f:
        job = json.load(f)
    job["blend"] = bpy.data.filepath
    os.makedirs(job["out"], exist_ok=True)
    for angle in job["angles"]:
        plate(job, angle)


main()
