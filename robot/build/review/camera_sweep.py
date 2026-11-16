"""Front Shot Camera sweep, numbers only (no render): for camera azimuths around the Android, project the Clip Data
points over every frame of every Move and report how far apart left and right hands and feet land in the image
(limbs that stack read as one, review R1), the chest's facing angle to the camera (0 face-on, 90 profile; review
F2) and whether head and feet stay in frame.

    $B -b robot/build/robot.blend -P robot/build/review/camera_sweep.py -- [--azimuths -70,-50,35,50,65]

Azimuth 0 is straight in front of the Android (-y), positive toward +x (the side Angle is near 87). The camera keeps
the front Angle's horizontal distance, height, lens and aim point."""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import build_robot  # noqa: E402
import moves  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--azimuths", default="-75,-60,-45,-30,35,45,55,65,75")
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    scene = bpy.context.scene
    _id, name, loc, target, _lens = build_robot.ANGLES[0]
    cam = bpy.data.objects[name]
    dx, dy = loc[0] - target[0], loc[1] - target[1]
    radius = math.hypot(dx, dy)
    pts = build_robot._points()
    arm = build_robot._arm()
    chest = arm.pose.bones["chest"]
    W, H = build_robot.SIZE
    out = {}
    for az in (float(x) for x in a.azimuths.split(",")):
        r = math.radians(az)
        cam.location = (target[0] + radius * math.sin(r), target[1] - radius * math.cos(r), loc[2])
        cam.rotation_euler = build_robot._aim(cam.location, target)
        spread = {"hands": [], "feet": [], "facing": [], "eyes": []}
        edge = {"top": H, "bottom": 0, "left": W, "right": 0}
        for move in moves.MOVES:
            build_robot._use_move(scene, move)
            for f in range(scene.frame_start, scene.frame_end + 1):
                scene.frame_set(f)
                p = {k: dict(zip("xy", (v[0] * W, v[1] * H))) for k, v in
                     ((k, build_robot._project(scene, cam, o.matrix_world.translation)) for k, o in pts.items())}
                spread["hands"].append(math.hypot(p["hand_l"]["x"] - p["hand_r"]["x"], p["hand_l"]["y"] - p["hand_r"]["y"]))
                spread["feet"].append(abs(p["foot_l"]["x"] - p["foot_r"]["x"]))
                spread["eyes"].append(p["eye_l"]["x"] - p["eye_r"]["x"])
                fwd = arm.matrix_world.to_3x3() @ chest.matrix.to_3x3() @ Vector((0, 0, 1))   # bone +z is world -y
                to_cam = cam.location - arm.matrix_world @ chest.head
                fwd.z = to_cam.z = 0
                spread["facing"].append(math.degrees(fwd.angle(to_cam)))
                for q in p.values():
                    edge["top"] = min(edge["top"], q["y"])
                    edge["bottom"] = max(edge["bottom"], q["y"])
                    edge["left"] = min(edge["left"], q["x"])
                    edge["right"] = max(edge["right"], q["x"])
        out[az] = {"hands_min_px": round(min(spread["hands"])), "hands_median_px": round(sorted(spread["hands"])[len(spread["hands"]) // 2]),
                   "feet_min_px": round(min(spread["feet"])), "feet_median_px": round(sorted(spread["feet"])[len(spread["feet"]) // 2]),
                   "eyes_median_px": round(sorted(spread["eyes"])[len(spread["eyes"]) // 2], 1),
                   "facing_deg_median": round(sorted(spread["facing"])[len(spread["facing"]) // 2]),
                   "points_box_px": [round(edge[k]) for k in ("left", "top", "right", "bottom")]}
    print("SWEEP", json.dumps(out))


if __name__ == "__main__":
    main()
