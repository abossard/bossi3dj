"""Clip frames: single frames of Clips, Eevee preview settings without motion blur, so a Hit's contact and pose can
be judged before a whole render (rounds A1 and X1; the preview's blur hid the Android at some Hits).

    $B -b robot/build/robot.blend -P robot/build/review/clip_frames.py -- OUT_DIR CLIP_ID:FRAME...
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import build_robot as br  # noqa: E402


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    out, specs = argv[0], [a.split(":") for a in argv[1:]]
    os.makedirs(out, exist_ok=True)
    scene = bpy.context.scene
    br.use_gpu()
    br.use_preview(scene)
    scene.render.use_motion_blur = False
    scene.render.image_settings.media_type = "IMAGE"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    clips = {clip_id: (move, cam) for clip_id, move, _angle, cam in br.clip_list()}
    for clip_id, frame in specs:
        move, cam = clips[clip_id]
        br._use_move(scene, move)
        scene.frame_set(int(frame))
        scene.camera = bpy.data.objects[cam]
        scene.render.filepath = os.path.join(out, "%s_%04d.png" % (clip_id, int(frame)))
        bpy.ops.render.render(write_still=True)
    print("FRAMES", out)


main()
