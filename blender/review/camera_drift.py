"""How far the on-air camera turns between two grabs, in pixels (the 1 px night edges land on other pixels when it drifts).
Exec BEFORE grid_numbers.py (or any grabber job): logs the evaluated on-air camera's world matrix and lens every 0.1 s,
with time.perf_counter, in DN["camdrift"]. After the jobs, drift_px(DN, t_a, t_b) gives the angle between the two
poses times the focal length in px of a 1920 px wide frame; grab times are DN["grabber"]["jobs"][i]["_w"]["t"]."""
import time

import bpy

DN = bpy.app.driver_namespace
S = bpy.context.scene
DN["camdrift"] = log = []
DN["camdrift_stop"] = False


def tick():
    if DN.get("camdrift_stop") or len(log) > 4000:
        return None
    c = S.camera.evaluated_get(bpy.context.evaluated_depsgraph_get())
    log.append((time.perf_counter(), c.matrix_world.copy(), c.data.lens))
    return 0.1


def drift_px(dn, ta, tb):
    lg = dn["camdrift"]
    a = min(lg, key=lambda r: abs(r[0] - ta))
    b = min(lg, key=lambda r: abs(r[0] - tb))
    q = a[1].to_quaternion().rotation_difference(b[1].to_quaternion())
    focal = 1920.0 * a[2] / 36.0
    return {"deg": round(q.angle * 57.29578, 5), "px": round(q.angle * focal, 3), "move_m": round((a[1].translation - b[1].translation).length, 5),
            "lens_a_b": [round(a[2], 4), round(b[2], 4)]}


bpy.app.timers.register(tick, first_interval=0.1)
