"""One low preview frame per Geo-Scatter biome behind the Robot Scene's arena, for the Asset Lab reel.

    B=/Applications/Blender.app/Contents/MacOS/Blender
    $B -b robot/build/robot.blend -P robot/build/review/biome_preview.py -- OUT_DIR [options] BIOME.biome [...]

Options:
    --scale S     scale the emitter object by S after scattering, transforms not applied. Geo-Scatter's default
                  "local" spaces then scale positions, spacing and instance sizes together: a mainboard biome
                  (BinaryFrame) becomes a megastructure. Default 1.
    --area W D    world size of the scattered area in metres (default 200 230). The plane is W/S by D/S locally.
    --y0 Y        near edge of the area behind the Android, metres along +Y (default 15).
    --tag T       suffix for the output names (default none).
    --measure     no render: write OUT_DIR/<biome><tag>.json with the instance sizes (metres, world) and the number
                  of instances the depsgraph evaluates, to pick S before rendering.

Needs the Biome Reader installed and configured (review/biome_reader_setup.py). Per biome it reopens robot.blend,
hides the foundry hall (columns, gantries, back wall; rated 1 star) and shows the floor to the camera, adds the
emitter plane, scatters the biome on it, and renders the front Shot Camera with Eevee at half size to
OUT_DIR/<biome><tag>.png. robot.blend is never saved.
"""
import json
import os
import statistics
import sys

import bpy

KEEP = ("floor", "floor_catcher")


def _engine(scene):
    for name in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = name
            return name
        except TypeError:
            continue
    raise RuntimeError("no Eevee engine")


def _setup(blend, biome, scale, area, y0):
    bpy.ops.wm.open_mainfile(filepath=blend)
    scene = bpy.context.scene
    for o in bpy.data.objects:
        if o.get("robot_set"):
            keep = o.name.split(".")[0] in KEEP
            o.hide_render = not keep
            o.visible_camera = keep
    w, d = area
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0.0, 0.0, 0.0))
    plane = bpy.context.active_object
    plane.name = "biome_emitter"
    plane.scale = (w / scale, d / scale, 1.0)
    bpy.ops.object.transform_apply(scale=True)
    scene.scatter5.emitter = plane
    bpy.ops.scatter5.add_biome(emitter_name=plane.name, surfaces_names=plane.name, json_path=biome)
    plane.scale = (scale, scale, scale)
    plane.location = (0.0, y0 + d / 2.0, 0.0)
    bpy.context.view_layer.update()
    return scene, plane


def _measure(biome, scale):
    with open(biome) as f:
        d = json.load(f)
    names = {n for k, v in d.items() if k.isdigit() for n in v["instances"]}
    sizes = [max(o.dimensions) * scale for o in bpy.data.objects if o.name.split(".")[0] in names]
    dg = bpy.context.evaluated_depsgraph_get()
    count = sum(1 for i in dg.object_instances if i.is_instance)
    return {"scale": scale, "instances_evaluated": count, "instance_objects": len(sizes),
            "size_m_median": round(statistics.median(sizes), 3) if sizes else None,
            "size_m_max": round(max(sizes), 3) if sizes else None,
            "size_m_min": round(min(sizes), 3) if sizes else None}


def _render(scene, out_png):
    _engine(scene)
    scene.camera = bpy.data.objects["ShotCamera.front"]
    scene.camera.data.clip_end = 2000.0
    scene.render.film_transparent = False
    scene.render.resolution_percentage = 50
    try:
        scene.eevee.taa_render_samples = 16
    except AttributeError:
        pass
    scene.frame_set(0)
    scene.render.filepath = out_png
    if hasattr(scene.render.image_settings, "media_type"):   # robot.blend renders movies; Blender 5 splits media type
        scene.render.image_settings.media_type = "IMAGE"
    scene.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    print("rendered", out_png)


def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    out_dir = os.path.abspath(args.pop(0))
    scale, area, y0, tag, measure, biomes = 1.0, (200.0, 230.0), 15.0, "", False, []
    while args:
        a = args.pop(0)
        if a == "--scale":
            scale = float(args.pop(0))
        elif a == "--area":
            area = (float(args.pop(0)), float(args.pop(0)))
        elif a == "--y0":
            y0 = float(args.pop(0))
        elif a == "--tag":
            tag = args.pop(0)
        elif a == "--measure":
            measure = True
        else:
            biomes.append(os.path.abspath(a))
    os.makedirs(out_dir, exist_ok=True)
    blend = bpy.data.filepath
    for b in biomes:
        scene, _plane = _setup(blend, b, scale, area, y0)
        name = os.path.splitext(os.path.basename(b))[0] + tag
        if measure:
            rep = _measure(b, scale)
            with open(os.path.join(out_dir, name + ".json"), "w") as f:
                json.dump(rep, f, indent=1)
            print("measured", name, rep)
        else:
            _render(scene, os.path.join(out_dir, name + ".png"))


main()
