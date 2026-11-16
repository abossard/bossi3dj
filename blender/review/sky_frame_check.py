"""Issue #25, the SKY_FRAME variant (path_camera.sky_frame), without Blender: python3 blender/review/sky_frame_check.py
On verify_paths.py's synthetic terrain, vantage, orbit and rise on the moon and the sun at /vj/height 0, 0.3 and 1, 40 s each,
with the variant off and on: the least share of the frame's centre column on the planet, whether the body stays in the
frame (its angle off the view over the vertical half field, at most 1), the view's largest turn (deg/s) and lens change
(log per s), and how far the eye moves over 10 s (m).
"""
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
G = {"__name__": "sky_frame_check", "__file__": os.path.join(HERE, "verify_paths.py")}
exec(open(G["__file__"]).read().split("# 1. live paths")[0], G)
dr, fl, pc, T, TARGETS, DT, FPS, half_v = (G[k] for k in ("dr", "fl", "pc", "T", "TARGETS", "DT", "FPS", "half_v"))


def land(p, fwd, lens):
    u, h = dr.spherical(p)
    pitch = math.asin(fl.clamp(fl.dot(fwd, u), -1.0, 1.0))
    dip = math.acos(fl.clamp(fl.R / (fl.R + max(h, 0.0)), -1.0, 1.0))
    hv = half_v(lens)
    return fl.clamp((-dip - (pitch - hv)) / (2.0 * hv), 0.0, 1.0)


for on in (False, True):
    pc.SKY_FRAME = on
    for path in ("vantage", "orbit", "rise"):
        for target in ("moon", "sun"):
            for w in (0.0, 0.3, 1.0):
                C = pc.PathCamera(TARGETS, T)
                poses = [C.step(DT, path, target, w, 1.0, 30.0) for _ in range(int(40 * FPS))][int(2 * FPS):]
                least = min(land(q[0], q[1], q[3]) for q in poses)
                off = max(fl.angle(q[1], fl.norm(fl.sub(pc.look_point(TARGETS[target], q[0], q[1]), q[0]))) / half_v(q[3])
                          for q in poses)
                turn = max(math.degrees(fl.angle(a[1], b[1])) / DT for a, b in zip(poses, poses[1:]))
                lens = max(abs(math.log(b[3] / a[3])) / DT for a, b in zip(poses, poses[1:]))
                move = fl.length(fl.sub(poses[int(10 * FPS)][0], poses[0][0]))
                print("SKY_FRAME %-5s %-7s %-4s h %.1f  land %.2f  body off %.2f  turn %5.1f  lens %.3f  move %6.0f m" % (
                    on, path, target, w, least, off, turn, lens, move))
