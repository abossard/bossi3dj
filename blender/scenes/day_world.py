"""A day-only copy of the sky world, used while the night sky layers have no weight.

VJ_Sky computes its night layers (milky way, dust lanes, sky nebula, dense stars) for every sky
pixel, also by day, where they are scaled by 0. make() copies the world and its VJ_Sky into
"<world> Day" with those layers unlinked, so the shader compiler drops them. sync() shows the day
world only while vj_night <= 0 and rt_space <= 0 (camera altitude, planet build), which is exactly
when their weight is 0: the image is the same, and the full world is back before any night layer
could show. Measured on the live planet scene (M1 Max, day): 47.8 -> 53.2 drawn fps.
"""
import bpy

DAY_KEY, FULL_KEY = "vj_day_world", "vj_full_world"


def night_only(node):
    """The night layers: fractal noise with 5+ octaves and the 800-cell dense star voronoi."""
    if node.type == "TEX_NOISE":
        return node.inputs["Detail"].default_value >= 5.0
    return node.type == "TEX_VORONOI" and node.inputs["Scale"].default_value >= 800.0


def make(world, cut=night_only, sky="VJ_Sky"):
    """Builds (or rebuilds) the day copy of `world`; `cut(node)` picks the VJ_Sky nodes to drop."""
    old = bpy.data.worlds.get(world.get(DAY_KEY, ""))
    if old is not None:
        bpy.data.worlds.remove(old)
    old = bpy.data.node_groups.get(sky + " Day")
    if old is not None:
        bpy.data.node_groups.remove(old)
    group = bpy.data.node_groups[sky].copy()
    group.name = sky + " Day"
    for node in [n for n in group.nodes if cut(n)]:
        for out in node.outputs:
            for link in list(out.links):
                group.links.remove(link)
    day = world.copy()
    day.name = world.name + " Day"
    for node in day.node_tree.nodes:
        if node.type == "GROUP" and node.node_tree is not None and node.node_tree.name == sky:
            node.node_tree = group
    world[DAY_KEY], day[FULL_KEY] = day.name, world.name
    world.use_fake_user = day.use_fake_user = True   # the one sync() is not showing has no user and would not be saved
    return day


def sync(scene):
    """Day world while the night layers have no weight, the full world otherwise."""
    world = scene.world
    if world is None:
        return
    full = bpy.data.worlds.get(world.get(FULL_KEY, "")) or world
    day = bpy.data.worlds.get(full.get(DAY_KEY, ""))
    if day is None:
        return
    want = day if scene.get("vj_night", 0.0) <= 0.0 and scene.get("rt_space", 0.0) <= 0.0 else full
    if scene.world != want:
        scene.world = want
