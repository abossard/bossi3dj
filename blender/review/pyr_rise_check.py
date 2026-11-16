"""Issue #26, /vj/pyramids does not lower the far site pyramids: same-frame A/B of the control through ridge_check.py.
In the live planet Blender:
    DN["pr_job"] = {"out": "/abs/dir", "shots": [{"name", "set", "pose"?}], "variant": "control" | "const"}; exec this file.
Per shot, after = /vj/pyramids 1, before = 0 (ridge_check's switch), everything else held. changed_share in ridges.json
then says how much of the frame the control moves.
Variants: "control" as built. "const": the Pyramid material's Vector Displacement takes a constant (0, 0, -20) m in place
of rise x (1 - vj_pyramids) while the control is 0 (JOB["const"], m in object space): if the pyramids then move, the displacement runs and the attribute
"rise" or the control does not reach it; if not, the displacement does not run on the instanced site pyramids. "control": False leaves /vj/pyramids alone (the island's
Pyramid_A to D follow it through drivers), so only the site pyramids' displacement switches. "plain": [x, y, z] adds
a plain mesh copy of the site pyramid nearest that point (plain_copy).
"""
import os

import bpy

DN = bpy.app.driver_namespace
S = bpy.context.scene
JOB = DN["pr_job"]
REVIEW = os.path.join(os.path.dirname(os.path.dirname(bpy.data.filepath)), "review")
NT = bpy.data.materials["Pyramid"].node_tree
VD = next(n for n in NT.nodes if n.type == "VECTOR_DISPLACEMENT")
LINK = VD.inputs["Vector"].links[0].from_socket


def plain_copy(point):
    """A plain mesh object (not an instance) of the site pyramid nearest point, at its place, with its attributes and
    the Pyramid material: the "const" variant on it tells EEVEE ignoring displacement on GN instances from ignoring it
    on this material. Removed with the scene (the .blend is generated, never saved)."""
    from mathutils import Vector
    dg = bpy.context.evaluated_depsgraph_get()
    best, me, mw = 1e18, None, None
    for inst in dg.object_instances:        # an instance is only valid inside the loop: copy as we go
        if not (inst.is_instance and inst.parent and inst.parent.name == "Planet_Sites") or inst.matrix_world.determinant() <= 0.0:
            continue
        d = (inst.matrix_world.translation - Vector(point)).length
        if d < best:
            if me is not None:
                bpy.data.meshes.remove(me)
            best, me, mw = d, bpy.data.meshes.new_from_object(inst.object), inst.matrix_world.copy()
    me.materials.clear()
    me.materials.append(bpy.data.materials["Pyramid"])
    ob = bpy.data.objects.new("PR_Plain", me)
    ob.matrix_world = mw
    S.collection.objects.link(ob)
    return ob


if JOB.get("plain") is not None:
    plain_copy(JOB["plain"])


def switch(k):
    if JOB.get("control", True):            # False: the control stays, only the variant's displacement switches
        S["vj_pyramids"] = 1.0 if k else 0.0
    if JOB.get("variant") == "const":
        if k:
            NT.links.new(LINK, VD.inputs["Vector"])
        else:
            for ln in list(VD.inputs["Vector"].links):
                NT.links.remove(ln)
            VD.inputs["Vector"].default_value = tuple(JOB.get("const", (0.0, 0.0, -20.0))) + (0.0,)     # an RGBA socket
    S.update_tag()


DN["rg_job"] = {"out": JOB["out"], "settle": JOB.get("settle", 12.0), "frames": JOB.get("frames", 10), "switch": switch,
                "shots": JOB["shots"]}
exec(compile(open(os.path.join(REVIEW, "ridge_check.py")).read(), "ridge_check.py", "exec"), {"__name__": "rg"})
