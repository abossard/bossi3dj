"""LOD build time in the open planet scene (round 12): re-evaluates every object whose Geometry Nodes modifier runs
PL_Land or PL_Water, ROUNDS times, and times each depsgraph update. Result in DN["lod_build_ms"] (and printed as JSON):
per object the median ms and its evaluated vertex and triangle counts, and the median of the summed update.
Run it headless (in the live UI the loop blocked the main thread for over 10 minutes, round 12):
    blender -b --disable-autoexec FILE.blend --python blender/review/lod_build_ms.py [-- CAM_0 [OBJECT ...]]
A tag re-evaluates everything that depends on the object too (sites, palms, flocks), about 5 s per set at load 80:
without object names it times only CAM_0's land and water set (all 44 LOD objects did not finish in 15 min).
Context only under load. Each timing is printed as it is taken."""
import json
import statistics
import sys
import time

import bpy

ROUNDS = 2
DN = bpy.app.driver_namespace
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if ARGS:
    bpy.context.scene.camera = bpy.context.scene.objects[ARGS[0]]
obs = [bpy.context.scene.objects[n] for n in (ARGS[1:] or ["Planet.CAM_0.0", "Water.CAM_0.0"])]
dg = bpy.context.evaluated_depsgraph_get()
per, total = {o.name: [] for o in obs}, []
for _ in range(ROUNDS):
    t_all = 0.0
    for o in obs:
        o.update_tag(refresh={"OBJECT", "DATA"})
        t = time.perf_counter()
        dg.update()
        ms = (time.perf_counter() - t) * 1000.0
        per[o.name].append(ms)
        print("LOD_EVAL %s %.1f ms" % (o.name, ms), flush=True)
        t_all += ms
    total.append(t_all)
out = {"total_ms": round(statistics.median(total), 1), "objects": {}}
for o in obs:
    me = o.evaluated_get(dg).data
    me.calc_loop_triangles()
    out["objects"][o.name] = {"ms": round(statistics.median(per[o.name]), 1), "verts": len(me.vertices),
                              "tris": len(me.loop_triangles), "polys": len(me.polygons)}
DN["lod_build_ms"] = out
print("LOD_BUILD_MS " + json.dumps(out))
