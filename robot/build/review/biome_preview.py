"""One low preview frame per Geo-Scatter biome behind the Robot Scene's arena, for the Asset Lab reel.

    B=/Applications/Blender.app/Contents/MacOS/Blender
    $B -b robot/build/robot.blend -P robot/build/review/biome_preview.py -- OUT_DIR BIOME.biome [BIOME.biome ...]

Needs the Biome Reader installed and configured (review/biome_reader_setup.py). Per biome it reopens robot.blend,
hides the foundry hall (columns, gantries, back wall; rated 1 star) and shows the floor to the camera, adds a
200 x 230 m emitter plane behind the Android (+Y, 15 m to 245 m), scatters the biome on it, and renders the front
Shot Camera with Eevee at half size to OUT_DIR/<biome>.png. robot.blend is never saved.
"""
import os
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


def preview(blend, biome, out_dir):
    bpy.ops.wm.open_mainfile(filepath=blend)
    scene = bpy.context.scene
    for o in bpy.data.objects:
        if o.get("robot_set"):
            keep = o.name.split(".")[0] in KEEP
            o.hide_render = not keep
            o.visible_camera = keep
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0.0, 130.0, 0.0))
    plane = bpy.context.active_object
    plane.name = "biome_emitter"
    plane.scale = (200.0, 230.0, 1.0)
    bpy.ops.object.transform_apply(scale=True)
    scene.scatter5.emitter = plane
    bpy.ops.scatter5.add_biome(emitter_name=plane.name, surfaces_names=plane.name, json_path=biome)
    _engine(scene)
    scene.camera = bpy.data.objects["ShotCamera.front"]
    scene.camera.data.clip_end = 1000.0
    scene.render.film_transparent = False
    scene.render.resolution_percentage = 50
    try:
        scene.eevee.taa_render_samples = 16
    except AttributeError:
        pass
    scene.frame_set(0)
    name = os.path.splitext(os.path.basename(biome))[0]
    scene.render.filepath = os.path.join(os.path.abspath(out_dir), name + ".png")
    scene.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    print("rendered", scene.render.filepath)


def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    out_dir, biomes = args[0], args[1:]
    os.makedirs(out_dir, exist_ok=True)
    blend = bpy.data.filepath
    for b in biomes:
        preview(blend, os.path.abspath(b), out_dir)


main()
