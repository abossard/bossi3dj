"""Lists every possible line source of a .blend for the no-dummy-wireframe rule (round 10), one line per hit.

    blender -b --disable-autoexec FILE.blend --python blender/review/line_sources.py

WIRENODE  a Wireframe shader node, with the materials and objects that draw it
MODIFIER  a Wireframe modifier, or a Geometry Nodes modifier whose tree turns edges into curves or tubes
READER    an Attribute node reading rt_grid_phase or vj_grid_speed
GRIDMATH  a node group or material whose name says grid or lattice
Objects hidden from render and the viewport are marked (hidden).
"""
import bpy

EDGE_NODES = {"GeometryNodeMeshToCurve", "GeometryNodeCurveToMesh", "GeometryNodeMeshToPoints"}


def trees():
    for coll in (bpy.data.node_groups, bpy.data.materials, bpy.data.worlds):
        for block in coll:
            tree = getattr(block, "node_tree", None) or (block if block.rna_type.identifier.endswith("Tree") else None)
            if tree is not None:
                yield block, tree


def users_of(tree):
    """Materials whose tree is this one or uses it as a group, then the objects that draw those materials."""
    mats = set()
    for m in bpy.data.materials:
        if m.node_tree is None:
            continue
        if m.node_tree == tree or any(n.type == "GROUP" and n.node_tree == tree for n in m.node_tree.nodes):
            mats.add(m.name)
    obs = sorted({o.name + ("" if o.visible_get() or not o.hide_render else " (hidden)") for o in bpy.data.objects
                  if any(s.material and s.material.name in mats for s in getattr(o, "material_slots", []))})
    return sorted(mats), obs


for block, tree in trees():
    for n in tree.nodes:
        if n.type == "WIREFRAME":
            mats, obs = users_of(tree)
            print("WIRENODE %s px=%s size=%.2f linked=%s mats=%s obs=%s" % (
                block.name, n.use_pixel_size, n.inputs["Size"].default_value, n.outputs["Fac"].is_linked, mats, obs[:8]))
        if n.type == "ATTRIBUTE" and n.attribute_name in ("rt_grid_phase", "vj_grid_speed"):
            print("READER %s %s" % (n.attribute_name, block.name))
    if any(w in block.name.lower() for w in ("grid", "lattice", "wire")):
        print("GRIDMATH %s" % block.name)

for o in bpy.data.objects:
    for md in o.modifiers:
        hid = "" if not (o.hide_render and o.hide_viewport) else " (hidden)"
        if md.type == "WIREFRAME":
            print("MODIFIER %s wireframe%s" % (o.name, hid))
        elif md.type == "NODES" and md.node_group is not None:
            hits = sorted({n.bl_idname for g in [md.node_group] + [n.node_tree for n in md.node_group.nodes
                                                                     if n.type == "GROUP" and n.node_tree]
                           for n in g.nodes if n.bl_idname in EDGE_NODES})
            if hits:
                print("MODIFIER %s nodes=%s %s%s" % (o.name, md.node_group.name, hits, hid))
