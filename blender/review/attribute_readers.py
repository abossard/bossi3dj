"""Lists where shader Attribute nodes and drivers read the vj_* properties of a .blend, one line per reader.

    blender -b --disable-autoexec FILE.blend --python blender/review/attribute_readers.py -- vj_hue vj_fog_hue

Prints `READER <property> <kind> <where>` and, for an Attribute node, how many links leave each output.
`DEAD <property> <tree>` marks a property whose Attribute nodes in that tree reach no group output, material
output or world output: the reader is wired into a dead end (duplicates that shader_dedupe.py left unlinked
do not count while the first node of the same name is alive). Without names, every vj_* and rt_*
Attribute is listed (only the DEAD lines are interesting then).
"""
import sys

import bpy

keys = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


OUTPUTS = ("GROUP_OUTPUT", "OUTPUT_MATERIAL", "OUTPUT_WORLD", "OUTPUT_LIGHT", "OUTPUT_AOV", "OUTPUT_LINESTYLE")


def reaches_output(node, seen=None):
    seen = seen if seen is not None else set()
    if node.name in seen:
        return False
    seen.add(node.name)
    if node.type in OUTPUTS:
        return True
    return any(reaches_output(lk.to_node, seen) for o in node.outputs for lk in o.links)


def trees():
    for coll in (bpy.data.node_groups, bpy.data.materials, bpy.data.worlds):
        for block in coll:
            tree = getattr(block, "node_tree", None) or (block if block.rna_type.identifier.endswith("Tree") else None)
            if tree is not None:
                yield block.name, tree


for owner, tree in trees():
    if not keys:
        alive = {}
        for node in tree.nodes:
            if node.bl_idname == "ShaderNodeAttribute":
                name = node.attribute_name.strip("[]\"' ")
                if name.startswith(("vj_", "rt_")):
                    alive[name] = alive.get(name, False) or reaches_output(node)
        for name, ok in sorted(alive.items()):
            if not ok:
                print("DEAD", name, owner)
    for node in tree.nodes:
        if node.bl_idname == "ShaderNodeAttribute":
            name = node.attribute_name.strip("[]\"' ")
            if keys and name in keys:
                links = sum(len(o.links) for o in node.outputs)
                used = sorted({lk.to_node.name for o in node.outputs for lk in o.links})
                print("READER", name, "attribute", owner, node.name, "links=%d" % links, "to=%s" % used)
    ad = tree.animation_data
    for fc in (ad.drivers if ad else ()):
        d = fc.driver
        text = d.expression + " " + " ".join(t.data_path for v in d.variables for t in v.targets)
        for k in keys:
            if k in text:
                print("READER", k, "driver", owner, fc.data_path, d.expression[:80])
