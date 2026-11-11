"""Does the evaluated land mesh keep the same triangle edges from one frame to the next? Through the Blender MCP:
    DN["stab"] = {"obj": "Planet.CAM_0.0", "n": 3, "gap": 1.5}   (all optional)
    exec(open(bpy.path.abspath("//../review/edge_stability.py")).read())
Takes n snapshots of the object's evaluated mesh, gap s apart (timer, one snapshot per tick, a second each at most), and
returns in DN["stab_result"] per snapshot the vertex and triangle count, the edge count, and against the first snapshot the
edges (by vertex index) that are in only one of the two, and the vertices that moved by more than 1 mm."""
import bpy
import numpy as np

DN = bpy.app.driver_namespace
cfg = DN.get("stab", {})
name, n, gap = cfg.get("obj", "Planet.CAM_0.0"), cfg.get("n", 3), cfg.get("gap", 1.5)
snaps, res = [], []
DN["stab_result"] = {"done": False, "rows": res}


def edge_keys(tri, nv):
    e = np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]])
    e.sort(axis=1)
    return np.unique(e[:, 0].astype(np.int64) * nv + e[:, 1])


def snap():
    ob = bpy.data.objects[name].evaluated_get(bpy.context.evaluated_depsgraph_get())
    m = ob.data
    nv = len(m.vertices)
    co = np.empty(nv * 3, np.float32)
    m.vertices.foreach_get("co", co)
    lt = np.empty(len(m.loop_triangles) * 3, np.int32)
    m.loop_triangles.foreach_get("vertices", lt)
    keys = edge_keys(lt.reshape(-1, 3), nv)
    row = {"verts": nv, "tris": len(m.loop_triangles), "edges": int(len(keys))}
    if snaps:
        k0, co0 = snaps[0]
        row["edges_only_in_one"] = int(len(np.setxor1d(keys, k0)))
        row["verts_moved_1mm"] = int((np.abs(co.reshape(-1, 3) - co0.reshape(-1, 3)).max(axis=1) > 0.001).sum()) if len(co0) == len(co) else None
    snaps.append((keys, co))
    res.append(row)


def tick():
    try:
        snap()
    except Exception as e:
        res.append({"error": str(e)})
        DN["stab_result"]["done"] = True
        return None
    if len(res) >= n:
        DN["stab_result"]["done"] = True
        return None
    return gap


bpy.app.timers.register(tick, first_interval=0.1)
