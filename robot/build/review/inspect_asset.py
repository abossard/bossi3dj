"""Read a downloaded .blend without running anything from it: open it with auto-run off, dump its text blocks for
reading, and report its armatures, IK constraints, height, triangle count and materials as JSON.

    $B -b --factory-startup FILE.blend -P robot/build/review/inspect_asset.py -- OUT_DIR

Never pass -y or --enable-autoexec: scripts and Python drivers in the file stay off. OUT_DIR gets report.json and
texts/<name> (the text blocks, as data to read before any of them is trusted)."""
import json
import os
import sys

import bpy


def main():
    out = sys.argv[sys.argv.index("--") + 1]
    os.makedirs(os.path.join(out, "texts"), exist_ok=True)
    prefs = bpy.context.preferences.filepaths
    rep = {"file": bpy.data.filepath, "saved_with": list(bpy.data.version),
           "autoexec": prefs.use_scripts_auto_execute, "texts": [], "armatures": [], "meshes": {}, "materials": []}
    for t in bpy.data.texts:
        rep["texts"].append({"name": t.name, "lines": len(t.lines), "registered": t.use_module})
        with open(os.path.join(out, "texts", t.name.replace("/", "_") + ".txt"), "w") as f:
            f.write(t.as_string())
    dg = bpy.context.evaluated_depsgraph_get()
    tris, zmin, zmax = 0, 1e9, -1e9
    for o in bpy.data.objects:
        if o.type == "MESH" and not o.hide_render:
            ev = o.evaluated_get(dg)
            me = ev.to_mesh()
            tris += sum(len(p.vertices) - 2 for p in me.polygons)
            for v in me.vertices:
                z = (o.matrix_world @ v.co).z
                zmin, zmax = min(zmin, z), max(zmax, z)
            ev.to_mesh_clear()
    rep["meshes"] = {"render_tris": tris, "height_m": round(zmax - zmin, 3), "z_range": [round(zmin, 3), round(zmax, 3)]}
    for o in bpy.data.objects:
        if o.type != "ARMATURE":
            continue
        bones = o.data.bones
        ik = [{"bone": pb.name, "target": c.target.name if c.target else None, "subtarget": c.subtarget,
               "pole": c.pole_subtarget, "chain": c.chain_count}
              for pb in o.pose.bones for c in pb.constraints if c.type == "IK"]
        rep["armatures"].append({
            "object": o.name, "bones": len(bones), "deform": [b.name for b in bones if b.use_deform][:200],
            "roots": [b.name for b in bones if b.parent is None],
            "collections": [c.name for c in o.data.collections_all] if hasattr(o.data, "collections_all") else [],
            "ik_constraints": ik,
            "control_like": [b.name for b in bones if not b.use_deform and any(
                k in b.name.upper() for k in ("IK", "FK", "MSTR", "CTR", "ROOT", "TORSO", "HIP", "CHEST", "HEAD",
                                               "FOOT", "HAND", "ARM", "LEG"))][:200]})
    rep["materials"] = sorted(m.name for m in bpy.data.materials if m.users)
    rep["actions"] = sorted(a.name for a in bpy.data.actions)
    with open(os.path.join(out, "report.json"), "w") as f:
        json.dump(rep, f, indent=1)
    print("INSPECTED", out)


main()
