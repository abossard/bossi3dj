"""Switches for round 17's pyramid and land changes in the live planet, for flicker.py's A/B probes ({"r17": {...}}).
exec this file in the live planet Blender; it sets DN["r17_apply"](flags). flags (each true as built, missing = true):
    "edges"   the Wireframe node's width in world units grown with the distance (false: round 16's 2.5 px pixel width)
    "pulse"   the whole pyramid's gain on rt_pulse (false: 0)
    "foot"    the foot's shade (false: off)
    "contact" the land's shade round the foot (false: off; not switchable with the regional map)
The pads and the foundation are in the map and the geometry: not switchable here.
"""
import bpy

DN = bpy.app.driver_namespace
PYR = bpy.data.materials["Pyramid"].node_tree
LAND = bpy.data.materials["Terrain GPU"].node_tree


def _find():
    wf = next(n for n in PYR.nodes if n.type == "WIREFRAME")
    size_src = wf.inputs["Size"].links[0].from_socket
    gain = next(n for n in PYR.nodes if n.type == "MATH" and n.operation == "MULTIPLY"
                and any(lk.from_node.type == "ATTRIBUTE" and lk.from_node.attribute_name == "rt_pulse"
                        for i in n.inputs for lk in i.links))
    gi = next(i for i in gain.inputs[:2] if not i.is_linked)
    foot = next(n for n in PYR.nodes if n.type == "MAP_RANGE" and abs(n.inputs["To Min"].default_value - 0.5) < 1e-6
                and abs(n.inputs["From Max"].default_value - 0.06) < 1e-6)
    shade = next(n for n in LAND.nodes if n.type == "MATH" and n.operation == "MULTIPLY"
                 and any(lk.from_node.type == "TEX_IMAGE" and lk.from_socket.name == "Alpha"
                         and lk.from_node.image and lk.from_node.image.name == "GT_Flow" for lk in n.inputs[0].links), None)
    # None with the regional map: the contact then comes from a blend of GT_Flow and GT_RegionFlow
    gains = []      # the rt_pulse gain of every pyramid material (site, island body, island edges)
    for m in ("Pyramid", "Pyramid Body", "Pyramid Edge"):
        for n in bpy.data.materials[m].node_tree.nodes:
            if n.type == "MATH" and n.operation == "MULTIPLY" and any(
                    lk.from_node.type == "ATTRIBUTE" and lk.from_node.attribute_name == "rt_pulse" for i in n.inputs for lk in i.links):
                gains += [i for i in n.inputs[:2] if not i.is_linked]
    return {"gains": gains, "wf": wf, "size_src": size_src, "gain": gi, "gain0": gi.default_value, "foot": foot, "shade": shade,
            "shade0": shade.inputs[1].default_value if shade else None}


F = _find()


def apply(flags=None):
    f = dict({"edges": True, "pulse": True, "foot": True, "contact": True}, **(flags or {}))
    wf = F["wf"]
    if f["edges"] and not wf.inputs["Size"].is_linked:
        wf.use_pixel_size = False
        PYR.links.new(F["size_src"], wf.inputs["Size"])
    elif not f["edges"]:
        for lk in list(wf.inputs["Size"].links):
            PYR.links.remove(lk)
        wf.use_pixel_size = True
        wf.inputs["Size"].default_value = 2.5
    F["gain"].default_value = F["gain0"] if f["pulse"] else 0.0
    F["foot"].inputs["To Min"].default_value = 0.5 if f["foot"] else 1.0
    if F["shade"] is not None:
        F["shade"].inputs[1].default_value = F["shade0"] if f["contact"] else 0.0


DN["r17_apply"] = apply
DN["r17_nodes"] = F
