"""Numbers for the Exchanges in the built robot.blend: where the giant's bones land against the key table of
exchanges.py (per Exchange, first frame and each Strike frame), its leg bone names, and the closest approach of each
Android hand to the thighs in power_stomp (rubric A1, A4).

    $B -b robot/build/robot.blend -P robot/build/review/giant_points_check.py -- OUT.json
"""
import json
import os
import sys

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import build_robot as br  # noqa: E402
import exchanges as X  # noqa: E402
import moves  # noqa: E402


def main():
    out = sys.argv[sys.argv.index("--") + 1]
    scene = bpy.context.scene
    rig = bpy.data.objects[br.GIANT_RIG]
    rep = {"leg_bones": [b.name for b in rig.data.bones
                         if any(k in b.name.lower() for k in ("knee", "shin", "thigh", "leg", "calf"))],
           "exchanges": {}}
    for name, ex in X.EXCHANGES.items():
        if "exchange." + name not in bpy.data.actions:
            continue
        br._use_move(scene, name)
        fr = X.frames(ex)
        rows = []
        for f in sorted({0} | {moves.beat_frame(s.beat) for s in ex.hits}):
            scene.frame_set(f)
            table = X.points(*fr[f])
            got = br.giant_points(rig)
            rows.append({"f": f, "error_m": {p: round((got[p] - __import__("mathutils").Vector(table[p])).length, 3)
                                             for p in got if p in table},
                         "bone": {p: [round(v, 2) for v in got[p]] for p in got}})
        rep["exchanges"][name] = rows
    arm = br._arm()
    br._use_move(scene, "power_stomp")
    thighs = [o for o in bpy.data.objects if o.get("robot_part", "").startswith("thigh")]
    hands = {s: [o for o in bpy.data.objects if o.get("robot_part") == "hand" + s] for s in (".L", ".R")}
    dg = None
    worst = {}
    for f in range(moves.move_frames(moves.MOVES["power_stomp"])):
        scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        for s, objs in hands.items():
            hv = [o.evaluated_get(dg).matrix_world @ v.co for o in objs for v in o.evaluated_get(dg).data.vertices][::7]
            for t in thighs:
                ev = t.evaluated_get(dg)
                ok, loc, _n, _i = ev.closest_point_on_mesh(ev.matrix_world.inverted() @ hv[0])
                inside = 0
                inv = ev.matrix_world.inverted()
                for v in hv:
                    ok, loc, nrm, _i = ev.closest_point_on_mesh(inv @ v)
                    if ok and (inv @ v - loc).dot(nrm) < 0:
                        inside += 1
                key = "hand%s_in_%s" % (s, t.get("robot_part"))
                worst[key] = max(worst.get(key, (0, 0)), (inside, f))
    rep["power_stomp_hand_vertices_inside_thigh"] = {k: {"vertices": v[0], "frame": v[1]} for k, v in worst.items()}
    _ = arm
    with open(out, "w") as fh:
        json.dump(rep, fh, indent=1)
    print("CHECKED", out)


main()
