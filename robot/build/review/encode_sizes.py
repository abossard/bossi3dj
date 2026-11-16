"""File size per Clip and beauty format, like for like: Blender's own movie writer encodes the same rendered PNG
frames (<package>/beauty/<clip id>/NNNN.png) once per format of build_robot.BEAUTY_FORMATS. A measurement only; the
Clips themselves are rendered straight to their format by build_robot.py render.

    $B -b --factory-startup -P robot/build/review/encode_sizes.py -- --package robot/package/v1 --out robot/build/probe/sizes
"""
import argparse
import json
import os
import sys

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import build_robot  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    scene = bpy.context.scene
    r = scene.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = 1920, 1080, 100
    r.fps, r.fps_base = 30, 1.0
    scene.view_settings.view_transform = "Standard"   # the PNGs already carry AgX
    seq = scene.sequence_editor_create()
    sizes = {}
    beauty = os.path.join(os.path.abspath(a.package), "beauty")
    for clip in sorted(d for d in os.listdir(beauty) if os.path.isdir(os.path.join(beauty, d))):
        files = sorted(f for f in os.listdir(os.path.join(beauty, clip)) if f.endswith(".png"))
        for s in list(seq.strips):
            seq.strips.remove(s)
        strip = seq.strips.new_image(clip, os.path.join(beauty, clip, files[0]), 1, 1)
        for f in files[1:]:
            strip.elements.append(f)
        scene.frame_start, scene.frame_end = 1, len(files)
        sizes[clip] = {"frames": len(files)}
        for fmt in build_robot.BEAUTY_FORMATS:
            if fmt == "png":
                continue
            build_robot.set_beauty_format(scene, fmt)
            r.filepath = os.path.join(os.path.abspath(a.out), fmt, clip + "_")
            bpy.ops.render.render(animation=True)
            sizes[clip][fmt] = os.path.getsize(r.frame_path(frame=scene.frame_start))
    print("SIZES", json.dumps(sizes))


if __name__ == "__main__":
    main()
