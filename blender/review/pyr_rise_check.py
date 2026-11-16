"""Issue #26, /vj/pyramids does not lower the far site pyramids: same-frame A/B of the control through ridge_check.py.
In the live planet Blender:
    DN["pr_job"] = {"out": "/abs/dir", "shots": [{"name", "set", "pose"?}], "variant": "control" | "const"}; exec this file.
Per shot, after = /vj/pyramids 1, before = 0 (ridge_check's switch), everything else held. changed_share in ridges.json
then says how much of the frame the control moves.
Variants: "control" as built. "const": the Pyramid material's Vector Displacement takes a constant (0, 0, -20) m in place
of rise x (1 - vj_pyramids) while the control is 0: if the pyramids then move, the displacement runs and the attribute
"rise" or the control does not reach it; if not, the displacement does not run on the instanced site pyramids. "control": False leaves /vj/pyramids alone (the island's
Pyramid_A to D follow it through drivers), so only the site pyramids' displacement switches.
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


def switch(k):
    if JOB.get("control", True):            # False: the control stays, only the variant's displacement switches
        S["vj_pyramids"] = 1.0 if k else 0.0
    if JOB.get("variant") == "const":
        if k:
            NT.links.new(LINK, VD.inputs["Vector"])
        else:
            for ln in list(VD.inputs["Vector"].links):
                NT.links.remove(ln)
            VD.inputs["Vector"].default_value = (0.0, 0.0, -20.0, 0.0)     # an RGBA socket
    S.update_tag()


DN["rg_job"] = {"out": JOB["out"], "settle": JOB.get("settle", 12.0), "frames": JOB.get("frames", 10), "switch": switch,
                "shots": JOB["shots"]}
exec(compile(open(os.path.join(REVIEW, "ridge_check.py")).read(), "ridge_check.py", "exec"), {"__name__": "rg"})
