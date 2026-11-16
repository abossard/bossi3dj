"""Foot contact of one Move, numbers for what a still frame can't show (a stomp): per foot, the lowest point of its
sole parts at each Hit frame, the highest lift between Hits and the frames from that peak down to contact.

    $B -b robot/build/robot.blend -P robot/build/review/foot_contact.py -- power_stomp
"""
import json
import os
import sys

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import build_robot as br  # noqa: E402
import moves  # noqa: E402


def main():
    name = sys.argv[sys.argv.index("--") + 1]
    scene, move = bpy.context.scene, moves.MOVES[name]
    feet = {s: [o for o in bpy.data.objects if o.get("robot_part") == "foot" + s] for s in (".L", ".R")}
    br._use_move(scene, name)
    sole = {s: [] for s in feet}
    for f in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        for s, parts in feet.items():
            sole[s].append(min(br._min_z(o, dg) for o in parts))
    out, prev = [], 0
    for h in moves.hit_frames(move):
        s = ".L" if h["limb"] == "foot_l" else ".R"
        if h["limb"] not in ("foot_l", "foot_r"):
            continue
        seg = sole[s][prev:h["f"] + 1]
        peak = max(range(len(seg)), key=seg.__getitem__) + prev
        out.append({"hit_f": h["f"], "foot": s, "sole_at_hit_m": round(sole[s][h["f"]], 4),
                    "peak_lift_m": round(sole[s][peak], 3), "peak_f": peak, "frames_peak_to_contact": h["f"] - peak,
                    "lowest_sole_m": round(min(sole[s]), 4)})
        prev = h["f"]
    print("CONTACT", json.dumps({name: out}))


main()
