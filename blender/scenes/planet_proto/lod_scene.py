"""The LOD stream in the planet scene: lod_stream.py's nodes as block objects (docs/research/synthwave-flight.md).

- Each block (a node depth and its ancestor BLOCK_UP depths up) is one object, land and water. Its base mesh holds
  one point per node (face, i, j, depth, morph range); a lean GN tree (FLT_Lod) instances one
  (N+1) x (N+1) grid per node, puts it on the Planet's PL_Surface, stores what the Terrain and Sea materials read
  (pl_w, mirror, pl_depth, pl_flow, pl_facet) and the morph target pl_morph (the parent lattice point) with the
  morph range pl_mr. Fine land blocks add the mirror copy about sea level that the water reflects.
- "Terrain LOD" and "Sea LOD" are copies of the planet's materials with a vector displacement of
  m * pl_morph, m = smoothstep(pl_mr.x, pl_mr.y, |position - rt_cam|): the morph runs every frame on the GPU,
  the geometry only changes when a block's node list does.
- update() selects the nodes once the camera has moved SEL_STEP metres (the margin covers that travel and the
  lag) and wants that selection. A timer (build_tick) bakes the missing nodes between frames, a few ms a tick,
  through GN builder objects into arrays (the cache, per node: a node's grid is the same in every block), and shows
  the whole selection at once when they are all there, each block assembled from its nodes.
- Shown blocks are written into slots: objects that always stay in the depsgraph and are drawn, one block each.
  A changed block rewrites its slot's mesh in place, which re-evaluates only that object; showing or hiding objects
  instead rebuilt the scene's depsgraph relations, 15-20 ms on every change.
- flight_rt resumes the stream at its start and it runs from then on: resume() starts the timer, pause() stops it and
  empties the slots (an empty slot draws nothing); the caches stay. live() says when a resumed stream shows a whole
  view.
"""
import math
import time
import traceback

import bpy
import numpy as np
from mathutils import Matrix

import lod_stream as ls

R = ls.R
CENTRE = ls.CENTRE
MIRROR_FROM = 7                     # depth from which land blocks carry the mirror copy (range under about 1.8 km)
LAG = 2                             # frames between a selection and its drawing
FRAME_MS = 8.0                      # ms of LOD work per drawn frame while moving (selection, baking, writing)
BAKE_FIXED_MS, BAKE_NODE_MS = 3.0, 0.12     # a bake's cost: per depsgraph update and per node (estimates)
WRITE_MS = 0.5                      # assembling and writing one block into its slot
SWAP_WAIT = 3                       # frames a ready selection may wait for a frame with room
STAGE_MIN = 24                      # a cut changing more blocks than this is staged (stage_tick)
STAGE_BLOCKS, STAGE_MS = 30, 25.0   # blocks written per frame while staging, and the frame's LOD budget then
HOLD_MAX = 12                       # frames a staged cut may hold the old view
HIDDEN, SHOWN = Matrix.Diagonal((0.0, 0.0, 0.0, 1.0)), Matrix.Identity(4)
BATCH = 8                           # builders evaluated in one depsgraph update (in parallel)
NODE_BATCH = 6                      # nodes per builder
CUT_MS, CUT_SHARE = 60.0, 0.5       # the budget while more than this share of the wanted nodes is missing
BUILD_LAG = 0.4                     # s a selection may wait for its blocks; the margin covers the travel
TICK = 0.005                        # s between build ticks
RIVERS = "FLT_Rivers"
CACHE_MAX = 40000                   # baked nodes kept as arrays (about 20 kB each): every fixed shot's, the path shots'
                                    # and the Flight's; the least recently used goes first
SLOTS = 200                         # slot objects made at the start (a static view shows about 150 blocks)
BLOCKS_MAX = 2000                   # assembled blocks kept (about 0.18 MB each; a block recurs on every pass of a path)
HOLD_TIME, MIN_FPS, STEP_DOWN = 2.0, 20.0, 0.35     # the margin's speed hold (travel())
STEP_SHARE = 0.25                   # moving fast, the selection step is this share of the margin's travel term
MORPH_WATER_LEVEL = True            # the land's water level follows its morph (Terrain LOD; set before start())
SEL_STEP = 8.0                     # m the camera moves before the next selection (covered by the margin)
NODE_ATTRS = ("nf", "ni", "nj", "nd", "r0", "r1")
_state = {"cache": {}, "blocks": {}, "near_missing": set(), "shown": {}, "slots": [], "free": [], "nodes": {},
          "params": None, "groups": None, "mats": None, "coll": None, "prev": None, "hr": None, "live": False,
          "want": None, "builders": [], "queue": [], "sel_queue": []}


# ---------------------------------------------------------------- node trees
class T:
    """A small node-tree builder (geometry nodes)."""

    def __init__(self, g):
        self.g, self.N, self.L = g, g.nodes, g.links

    def node(self, kind, **props):
        n = self.N.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def link(self, a, b):
        self.L.new(a, b)

    def _in(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.link(v, sock)
        else:
            sock.default_value = v

    def math(self, op, a, b=0.0, c=0.0):
        n = self.node("ShaderNodeMath", operation=op)
        self._in(n.inputs[0], a)
        self._in(n.inputs[1], b)
        self._in(n.inputs[2], c)
        return n.outputs[0]

    def vmath(self, op, a, b=(0.0, 0.0, 0.0), scale=None):
        n = self.node("ShaderNodeVectorMath", operation=op)
        self._in(n.inputs[0], a)
        self._in(n.inputs[1], b)
        if scale is not None:
            self._in(n.inputs["Scale"], scale)
        out = "Value" if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else "Vector"
        return n.outputs[out]

    def comb(self, x, y, z):
        n = self.node("ShaderNodeCombineXYZ")
        for s, v in zip(n.inputs, (x, y, z)):
            self._in(s, v)
        return n.outputs[0]

    def sep(self, v):
        n = self.node("ShaderNodeSeparateXYZ")
        self._in(n.inputs[0], v)
        return n.outputs

    def read(self, name, kind="FLOAT"):
        n = self.node("GeometryNodeInputNamedAttribute", data_type=kind)
        n.inputs["Name"].default_value = name
        return n.outputs["Attribute"]

    def store(self, geo, name, value, kind="FLOAT", domain="POINT"):
        n = self.node("GeometryNodeStoreNamedAttribute", data_type=kind, domain=domain)
        n.inputs["Name"].default_value = name
        self.link(geo, n.inputs["Geometry"])
        self._in(n.inputs["Value"], value)
        return n.outputs[0]

    def sample(self, geo, value, index, kind="FLOAT_VECTOR"):
        n = self.node("GeometryNodeSampleIndex", data_type=kind, domain="POINT")
        self.link(geo, n.inputs["Geometry"])
        self._in(n.inputs["Value"], value)
        self._in(n.inputs["Index"], index)
        return n.outputs[0]

    def setpos(self, geo, pos):
        n = self.node("GeometryNodeSetPosition")
        self.link(geo, n.inputs["Geometry"])
        self._in(n.inputs["Position"], pos)
        return n.outputs[0]


def cube_dir(t, f, a, b):
    """normalize(n + tan(a pi/4) u + tan(b pi/4) v) for face f, as build_planet.cube_dir."""
    axis = t.math("FLOORED_MODULO", f, 3.0)
    sign = t.math("SUBTRACT", 1.0, t.math("MULTIPLY", t.math("GREATER_THAN", f, 2.5), 2.0))

    def unit(k):
        return t.comb(*(t.math("COMPARE", k, float(i), 0.5) for i in range(3)))

    n_ = t.vmath("SCALE", unit(axis), scale=sign)
    u_ = unit(t.math("FLOORED_MODULO", t.math("ADD", axis, 1.0), 3.0))
    v_ = t.vmath("SCALE", unit(t.math("FLOORED_MODULO", t.math("ADD", axis, 2.0), 3.0)), scale=sign)
    ta = t.math("TANGENT", t.math("MULTIPLY", a, math.pi / 4.0))
    tb = t.math("TANGENT", t.math("MULTIPLY", b, math.pi / 4.0))
    return t.vmath("NORMALIZE", t.vmath("ADD", t.vmath("ADD", n_, t.vmath("SCALE", u_, scale=ta)), t.vmath("SCALE", v_, scale=tb)))


def lattice_dir(t, f, d, gx, gy, n):
    """Unit direction of global lattice point (gx, gy) at depth d of face f, shifted as lod_stream.jitter (uniform
    over a disc of JITTER cells, hashed from face, depth and point; none on the cube's edges). The hash is
    Blender's white noise, not lod_stream's: only that it is the same for a point wherever it is evaluated matters."""
    m = t.math("MULTIPLY", float(n), t.math("POWER", 2.0, d))
    inner = t.math("MULTIPLY", t.math("MULTIPLY", t.math("GREATER_THAN", gx, 0.5), t.math("LESS_THAN", gx, t.math("SUBTRACT", m, 0.5))),
                   t.math("MULTIPLY", t.math("GREATER_THAN", gy, 0.5), t.math("LESS_THAN", gy, t.math("SUBTRACT", m, 0.5))))
    wn = t.node("ShaderNodeTexWhiteNoise", noise_dimensions="4D")
    t.link(t.comb(gx, gy, d), wn.inputs["Vector"])
    t.link(f, wn.inputs["W"])
    u_, v_ = t.sep(wn.outputs["Color"])[:2]
    rad = t.math("MULTIPLY", t.math("SQRT", v_), t.math("MULTIPLY", inner, ls.JITTER))
    ang = t.math("MULTIPLY", u_, 2.0 * math.pi)
    a = t.math("ADD", -1.0, t.math("DIVIDE", t.math("MULTIPLY", t.math("MULTIPLY_ADD", rad, t.math("COSINE", ang), gx), 2.0), m))
    b = t.math("ADD", -1.0, t.math("DIVIDE", t.math("MULTIPLY", t.math("MULTIPLY_ADD", rad, t.math("SINE", ang), gy), 2.0), m))
    return cube_dir(t, f, a, b)


def rivers_object():
    """Planet_Hydro's river curves as ribbons (Curve to Mesh with a 1 m line profile), baked once into a plain mesh
    object: converting them in every block's evaluation cost 2 of its 7 ms."""
    ob = bpy.data.objects.get(RIVERS)
    if ob is not None:
        return ob
    g = bpy.data.node_groups.new("FLT_Rivers_Bake", "GeometryNodeTree")
    g.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    g.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    t = T(g)
    go = t.node("NodeGroupOutput")
    oi = t.node("GeometryNodeObjectInfo", transform_space="ORIGINAL")
    oi.inputs["Object"].default_value = bpy.data.objects["Planet_Hydro"]
    sc = t.node("GeometryNodeSeparateComponents")
    t.link(oi.outputs["Geometry"], sc.inputs[0])
    rib = t.node("GeometryNodeCurvePrimitiveLine")
    rib.inputs["Start"].default_value, rib.inputs["End"].default_value = (-0.5, 0, 0), (0.5, 0, 0)
    c2m = t.node("GeometryNodeCurveToMesh")
    t.link(sc.outputs["Curve"], c2m.inputs["Curve"])
    t.link(rib.outputs[0], c2m.inputs["Profile Curve"])
    t.link(c2m.outputs["Mesh"], go.inputs[0])
    tmp = bpy.data.objects.new("FLT_Rivers_Tmp", bpy.data.meshes.new("FLT_Rivers_Tmp"))
    _state["coll"].objects.link(tmp)
    tmp.modifiers.new("bake", "NODES").node_group = g
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    me = tmp.evaluated_get(dg).data.copy()
    me.name = RIVERS
    tmp_me = tmp.data
    bpy.data.objects.remove(tmp)
    bpy.data.meshes.remove(tmp_me)
    bpy.data.node_groups.remove(g)
    ob = bpy.data.objects.new(RIVERS, me)
    _state["coll"].objects.link(ob)
    for k in ("visible_camera", "visible_shadow", "visible_diffuse", "visible_glossy", "visible_transmission",
              "visible_volume_scatter"):
        setattr(ob, k, False)
    return ob


def build_group(name, n):
    """The GN tree that turns a block's node points into its drawn land (with its mirror copy) and water: the surface
    is evaluated once per vertex and both read it."""
    g = bpy.data.node_groups.get(name)
    if g is not None:
        bpy.data.node_groups.remove(g)
    g = bpy.data.node_groups.new(name, "GeometryNodeTree")
    g.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    g.interface.new_socket("Mirror", in_out="INPUT", socket_type="NodeSocketBool")
    g.interface.new_socket("Land Material", in_out="INPUT", socket_type="NodeSocketMaterial")
    g.interface.new_socket("Water Material", in_out="INPUT", socket_type="NodeSocketMaterial")
    g.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    t = T(g)
    gi, go = t.node("NodeGroupInput"), t.node("NodeGroupOutput")
    grid = t.node("GeometryNodeMeshGrid")
    grid.inputs["Size X"].default_value = grid.inputs["Size Y"].default_value = 1.0
    grid.inputs["Vertices X"].default_value = grid.inputs["Vertices Y"].default_value = n + 1
    tri = t.node("GeometryNodeTriangulate")
    t.link(grid.outputs["Mesh"], tri.inputs["Mesh"])
    iop = t.node("GeometryNodeInstanceOnPoints")
    t.link(gi.outputs["Geometry"], iop.inputs["Points"])
    t.link(tri.outputs[0], iop.inputs["Instance"])
    real = t.node("GeometryNodeRealizeInstances")
    t.link(iop.outputs[0], real.inputs[0])
    geo = real.outputs[0]
    pos = t.node("GeometryNodeInputPosition").outputs[0]
    px, py, _ = t.sep(pos)
    x = t.math("ROUND", t.math("MULTIPLY", t.math("ADD", px, 0.5), float(n)))
    y = t.math("ROUND", t.math("MULTIPLY", t.math("ADD", py, 0.5), float(n)))
    geo = t.store(geo, "fl_x", x)
    geo = t.store(geo, "fl_y", y)
    x, y = t.read("fl_x"), t.read("fl_y")
    f, i, j, d = t.read("nf"), t.read("ni"), t.read("nj"), t.read("nd")
    gx, gy = t.math("MULTIPLY_ADD", i, float(n), x), t.math("MULTIPLY_ADD", j, float(n), y)
    dvec = lattice_dir(t, f, d, gx, gy, n)
    # the parent depth's own shifted point: an even vertex's morph target (lod_stream.morph_targets)
    dpar = lattice_dir(t, f, t.math("SUBTRACT", d, 1.0), t.math("FLOOR", t.math("MULTIPLY", gx, 0.5)),
                       t.math("FLOOR", t.math("MULTIPLY", gy, 0.5)), n)
    hydro = bpy.data.objects["Planet_Hydro"]
    oi = t.node("GeometryNodeObjectInfo", transform_space="ORIGINAL")
    oi.inputs["Object"].default_value = hydro
    sc = t.node("GeometryNodeSeparateComponents")
    t.link(oi.outputs["Geometry"], sc.inputs[0])
    ri = t.node("GeometryNodeObjectInfo", transform_space="ORIGINAL")      # the rivers' ribbons, baked once
    ri.inputs["Object"].default_value = rivers_object()

    def surface(dir_):
        sg_ = t.node("GeometryNodeGroup")
        sg_.node_tree = bpy.data.node_groups["PL_Surface"]
        t.link(dir_, sg_.inputs["Dir"])
        t.link(sc.outputs["Mesh"], sg_.inputs["Hydro"])
        t.link(ri.outputs["Geometry"], sg_.inputs["Rivers"])
        sg_.inputs["River Water"].default_value = 1.0
        return sg_

    sg = surface(dvec)
    # the surface once, as attributes both branches read: one Capture evaluates its outputs together (a Store per
    # output evaluated PL_Surface again for each, 2.5x the cost)
    cap = t.node("GeometryNodeCaptureAttribute", domain="POINT")
    for name, kind in (("h", "FLOAT"), ("w", "FLOAT"), ("flow", "VECTOR")):
        cap.capture_items.new(kind, name)
    t.link(geo, cap.inputs["Geometry"])
    t.link(sg.outputs["Height"], cap.inputs["h"])
    t.link(sg.outputs["Water"], cap.inputs["w"])
    t.link(sg.outputs["Flow"], cap.inputs["flow"])
    geo = t.store(cap.outputs["Geometry"], "fl_h", cap.outputs["h"])
    geo = t.store(geo, "pl_w", cap.outputs["w"])
    geo = t.store(geo, "pl_depth", t.math("SUBTRACT", cap.outputs["w"], cap.outputs["h"]))
    geo = t.store(geo, "pl_flow", cap.outputs["flow"], "FLOAT_VECTOR")
    geo = t.store(geo, "pl_mr", t.comb(t.read("r0"), t.read("r1"), 0.0), "FLOAT_VECTOR")
    ox, oy = t.math("FLOORED_MODULO", x, 2.0), t.math("FLOORED_MODULO", y, 2.0)
    # the even vertices' parent points: the surface once more, on those vertices only (a quarter of them), as points
    # ranked in vertex order; fl_rk is each vertex's rank among them
    even = t.math("COMPARE", t.math("ADD", ox, oy), 0.0, 0.5)
    acc = t.node("GeometryNodeAccumulateField", data_type="FLOAT", domain="POINT")
    t.link(even, acc.inputs["Value"])
    geo = t.store(geo, "fl_rk", acc.outputs["Trailing"])
    m2p = t.node("GeometryNodeMeshToPoints", mode="VERTICES")
    t.link(geo, m2p.inputs["Mesh"])
    t.link(even, m2p.inputs["Selection"])
    sp = surface(dpar)
    cap2 = t.node("GeometryNodeCaptureAttribute", domain="POINT")
    for name in ("h", "w"):
        cap2.capture_items.new("FLOAT", name)
    t.link(m2p.outputs["Points"], cap2.inputs["Geometry"])
    t.link(sp.outputs["Height"], cap2.inputs["h"])
    t.link(sp.outputs["Water"], cap2.inputs["w"])
    pts = cap2.outputs["Geometry"]
    for name in ("h", "w"):
        pts = t.store(pts, "pp_" + name, t.vmath("ADD", t.vmath("SCALE", dpar, scale=t.math("ADD", cap2.outputs[name], R)),
                                                 CENTRE), "FLOAT_VECTOR")
    row = float(n + 1)
    idx = t.node("GeometryNodeInputIndex").outputs[0]
    base = t.math("SUBTRACT", idx, t.math("ADD", t.math("MULTIPLY", x, row), y))      # Mesh Grid indices run x-major
    ia = t.math("ADD", base, t.math("ADD", t.math("MULTIPLY", t.math("SUBTRACT", x, ox), row), t.math("ADD", y, oy)))
    ib = t.math("ADD", base, t.math("ADD", t.math("MULTIPLY", t.math("ADD", x, ox), row), t.math("SUBTRACT", y, oy)))

    def placed(level, parent):
        """The grid at a level (land height or water level) with its morph target: the midpoint of the parent points
        of (x - ox, y + oy) and (x + ox, y - oy), an even vertex's own parent point. Triangulate splits every cell
        along its (0,1)-(1,0) diagonal, so an odd-odd point lies on that diagonal of its parent cell."""
        out = t.setpos(geo, t.vmath("ADD", t.vmath("SCALE", dvec, scale=t.math("ADD", t.read(level), R)), CENTRE))
        p_now = t.node("GeometryNodeInputPosition").outputs[0]
        rk = t.read("fl_rk")
        pa, pb = (t.sample(pts, t.read(parent, "FLOAT_VECTOR"), t.sample(out, rk, k, "FLOAT")) for k in (ia, ib))
        mid = t.vmath("SCALE", t.vmath("ADD", pa, pb), scale=0.5)
        return t.store(out, "pl_morph", t.vmath("SUBTRACT", mid, p_now), "FLOAT_VECTOR")

    def material(geo_, sock):
        sm = t.node("GeometryNodeSetMaterial")
        t.link(geo_, sm.inputs["Geometry"])
        t.link(gi.outputs[sock], sm.inputs["Material"])
        return sm.outputs[0]

    land = placed("fl_h", "pp_h")
    noise = t.node("ShaderNodeTexWhiteNoise", noise_dimensions="3D")
    t.link(t.vmath("SCALE", t.node("GeometryNodeInputPosition").outputs[0], scale=0.37), noise.inputs["Vector"])
    land = t.store(land, "pl_facet", noise.outputs["Value"], domain="FACE")
    land = t.store(land, "mirror", 0.0)
    # the mirror copy about sea level (radius R - h), faces flipped, its morph mirrored along the radial
    rel = t.vmath("SUBTRACT", t.node("GeometryNodeInputPosition").outputs[0], CENTRE)
    unit = t.vmath("NORMALIZE", rel)
    mpos = t.vmath("ADD", t.vmath("SCALE", unit, scale=t.math("SUBTRACT", 2.0 * R, t.vmath("LENGTH", rel))), CENTRE)
    mir = t.setpos(land, mpos)
    mm = t.read("pl_morph", "FLOAT_VECTOR")
    mm2 = t.vmath("SUBTRACT", mm, t.vmath("SCALE", unit, scale=t.math("MULTIPLY", t.vmath("DOT_PRODUCT", mm, unit), 2.0)))
    mir = t.store(mir, "pl_morph", mm2, "FLOAT_VECTOR")
    mir = t.store(mir, "mirror", 1.0)
    flip = t.node("GeometryNodeFlipFaces")
    t.link(mir, flip.inputs["Mesh"])
    sw = t.node("GeometryNodeSwitch", input_type="GEOMETRY")
    t.link(gi.outputs["Mirror"], sw.inputs["Switch"])
    t.link(flip.outputs[0], sw.inputs["True"])
    join = t.node("GeometryNodeJoinGeometry")
    t.link(sw.outputs[0], join.inputs[0])
    t.link(land, join.inputs[0])
    ss = t.node("GeometryNodeSetShadeSmooth", domain="FACE")
    t.link(join.outputs[0], ss.inputs["Mesh"])
    land = material(ss.outputs[0], "Land Material")
    water = placed("pl_w", "pp_w")
    wet = t.math("MINIMUM", t.math("MAXIMUM", t.math("ADD", t.read("pl_depth"), 1.0), 0.0), 1.0)
    fa = t.node("GeometryNodeFieldOnDomain", domain="FACE", data_type="FLOAT")
    t.link(wet, fa.inputs[0])
    dl = t.node("GeometryNodeDeleteGeometry", domain="FACE")
    t.link(water, dl.inputs["Geometry"])
    t.link(t.math("LESS_THAN", fa.outputs[0], 0.001), dl.inputs["Selection"])
    water = material(dl.outputs[0], "Water Material")
    both = t.node("GeometryNodeJoinGeometry")
    t.link(water, both.inputs[0])
    t.link(land, both.inputs[0])
    out = both.outputs[0]
    for name in ("fl_x", "fl_y", "fl_h", "fl_rk") + NODE_ATTRS:        # only what the materials read is baked and uploaded
        rm = t.node("GeometryNodeRemoveAttribute")
        rm.inputs["Name"].default_value = name
        t.link(out, rm.inputs["Geometry"])
        out = rm.outputs[0]
    t.link(out, go.inputs[0])
    return g


def morph_material(src_name):
    """A copy of the planet material with the morph as vector displacement (object space = world: the Planet is at
    the origin)."""
    name = src_name + " LOD"
    old = bpy.data.materials.get(name)
    if old is not None:
        bpy.data.materials.remove(old)
    m = bpy.data.materials[src_name].copy()
    m.name = name
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    out = next(n for n in N if n.type == "OUTPUT_MATERIAL" and n.is_active_output)

    def attr(name, kind="GEOMETRY", out_="Vector"):
        a = N.new("ShaderNodeAttribute")
        a.attribute_type, a.attribute_name = kind, name
        return a.outputs[out_]

    cam = N.new("ShaderNodeCombineXYZ")
    for k, ax in enumerate("xyz"):
        L.new(attr("rt_cam_" + ax, "VIEW_LAYER", "Fac"), cam.inputs[k])
    geo = N.new("ShaderNodeNewGeometry")
    dist = N.new("ShaderNodeVectorMath")
    dist.operation = "DISTANCE"
    L.new(geo.outputs["Position"], dist.inputs[0])
    L.new(cam.outputs[0], dist.inputs[1])
    mr = N.new("ShaderNodeSeparateXYZ")
    L.new(attr("pl_mr"), mr.inputs[0])
    ss = N.new("ShaderNodeMapRange")
    ss.interpolation_type = "SMOOTHSTEP"
    L.new(dist.outputs["Value"], ss.inputs["Value"])
    L.new(mr.outputs[0], ss.inputs["From Min"])
    L.new(mr.outputs[1], ss.inputs["From Max"])
    sc = N.new("ShaderNodeVectorMath")
    sc.operation = "SCALE"
    L.new(attr("pl_morph"), sc.inputs[0])
    L.new(ss.outputs["Result"], sc.inputs["Scale"])
    vd = N.new("ShaderNodeVectorDisplacement")
    vd.space = "OBJECT"
    vd.inputs["Midlevel"].default_value = 0.0
    vd.inputs["Scale"].default_value = 1.0
    L.new(sc.outputs["Vector"], vd.inputs["Vector"])
    disp = out.inputs["Displacement"]
    if disp.is_linked:
        prev = disp.links[0].from_socket
        add = N.new("ShaderNodeVectorMath")
        add.operation = "ADD"
        L.new(prev, add.inputs[0])
        L.new(vd.outputs[0], add.inputs[1])
        L.new(add.outputs[0], disp)
    else:
        L.new(vd.outputs[0], disp)
    m.displacement_method = "DISPLACEMENT"
    if MORPH_WATER_LEVEL:
        # the land's own water level moves with its morph: zw (height over its own water) is the unmorphed one. The
        # land is drawn only down to SHALLOW under that level, and a coarse node's morph lowered dry land beside a
        # hillside lake by tens of metres under it: cut out, the Approach's holes (docs/handover/terrain-test.md)
        rel = N.new("ShaderNodeVectorMath")
        rel.operation = "SUBTRACT"
        L.new(geo.outputs["Position"], rel.inputs[0])
        rel.inputs[1].default_value = CENTRE
        un = N.new("ShaderNodeVectorMath")
        un.operation = "NORMALIZE"
        L.new(rel.outputs["Vector"], un.inputs[0])
        rad = N.new("ShaderNodeVectorMath")
        rad.operation = "DOT_PRODUCT"
        L.new(sc.outputs["Vector"], rad.inputs[0])
        L.new(un.outputs["Vector"], rad.inputs[1])
        flip = N.new("ShaderNodeMath")          # the mirror copy's morph is mirrored along the radial: 1 - 2 mirror
        flip.operation = "MULTIPLY_ADD"
        L.new(attr("mirror", out_="Fac"), flip.inputs[0])
        flip.inputs[1].default_value, flip.inputs[2].default_value = -2.0, 1.0
        shift = N.new("ShaderNodeMath")
        shift.operation = "MULTIPLY"
        L.new(rad.outputs["Value"], shift.inputs[0])
        L.new(flip.outputs[0], shift.inputs[1])
        for a in [n for n in N if n.type == "ATTRIBUTE" and n.attribute_name == "pl_w"]:
            for link in list(a.outputs["Fac"].links):
                to = link.to_socket
                L.remove(link)
                lw = N.new("ShaderNodeMath")
                lw.operation = "ADD"
                L.new(a.outputs["Fac"], lw.inputs[0])
                L.new(shift.outputs[0], lw.inputs[1])
                L.new(lw.outputs[0], to)
    return m


# ---------------------------------------------------------------- blocks
def builder(i=0):
    """GN object i of the pool that turns node lists into block geometry; blocks are baked from them, BATCH at a
    time in one depsgraph update."""
    pool = _state.setdefault("builders", [])
    while len(pool) <= i:
        me = bpy.data.meshes.new("LOD_BUILDER")
        b = bpy.data.objects.new("LOD_BUILDER", me)
        _state["coll"].objects.link(b)
        for k in ("visible_camera", "visible_shadow", "visible_diffuse", "visible_glossy", "visible_transmission",
                  "visible_volume_scatter"):
            setattr(b, k, False)
        mod = b.modifiers.new("lod", "NODES")
        mod.node_group = _state["groups"]
        ids = {it.name: it.identifier for it in mod.node_group.interface.items_tree if getattr(it, "in_out", "") == "INPUT"}
        ins = mod.properties.inputs
        getattr(ins, ids["Land Material"]).value = _state["mats"]["land"]
        getattr(ins, ids["Water Material"]).value = _state["mats"]["water"]
        _state["mirror_id"] = ids["Mirror"]
        for name in NODE_ATTRS:
            me.attributes.new(name, "FLOAT", "POINT")
        pool.append(b)
    return pool[i]


ATTR_KEY = {"FLOAT": ("value", np.float32, 1), "FLOAT_VECTOR": ("vector", np.float32, 3), "INT": ("value", np.int32, 1),
            "BOOLEAN": ("value", bool, 1), "INT32_2D": ("value", np.int32, 2), "FLOAT2": ("vector", np.float32, 2),
            "FLOAT_COLOR": ("color", np.float32, 4), "INT8": ("value", np.int8, 1)}
INDEX_OF = {".edge_verts": "POINT", ".corner_vert": "POINT", ".corner_edge": "EDGE"}   # attributes holding indices
DOMAIN_N = {"POINT": 0, "EDGE": 1, "FACE": 2, "CORNER": 2}     # a node's count for the domain (corners: 3 per face)


def read_nodes(me, keys):
    """A builder's evaluated mesh cut into its nodes (node i's grid carries nid i): per node, its vertex, edge and
    face counts and every attribute, with vertex and edge indices made node-local and the material indices mapped to
    the slots' order (land 0, water 1). Every face is a triangle."""
    nf = len(me.polygons)
    if len(me.loops) != 3 * nf:
        raise ValueError("FLT_Lod faces must be triangles")
    water = _state["mats"]["water"]
    # an evaluated mesh lists evaluated copies of its materials: compared with the original by identity they never
    # matched, and every water face was drawn with the land material (Flight review 2026-11-12: no water in the stream)
    lut = np.array([1 if m is not None and m.original == water else 0 for m in me.materials] or [0], np.int32)
    raw = {}
    for at in me.attributes:
        if at.name.startswith(".") and at.name not in INDEX_OF:
            continue
        key, dt, w = ATTR_KEY[at.data_type]
        v = np.empty(len(at.data) * w, dt)
        at.data.foreach_get(key, v)
        raw[at.name] = (at.domain, at.data_type, key, v.reshape(-1, w) if w > 1 else v)
    mi = raw.get("material_index", (0, 0, 0, np.zeros(nf, np.int32)))[3]
    raw["material_index"] = ("FACE", "INT", "value", lut[np.clip(mi, 0, len(lut) - 1)])
    nid_v = raw.pop("nid")[3].astype(np.int64)
    ids = {"POINT": nid_v, "EDGE": nid_v[raw[".edge_verts"][3][:, 0]], "FACE": nid_v[raw[".corner_vert"][3][::3]]}
    order, cut, local = {}, {}, {}
    for dom, nid in ids.items():
        order[dom] = np.argsort(nid, kind="stable")
        cut[dom] = np.concatenate(([0], np.cumsum(np.bincount(nid, minlength=len(keys)))))
        rank = np.empty(len(nid), np.int64)
        rank[order[dom]] = np.arange(len(nid))
        local[dom] = (rank - cut[dom][nid]).astype(np.int32)
    order["CORNER"] = (order["FACE"][:, None] * 3 + np.arange(3)).ravel()
    cut["CORNER"] = cut["FACE"] * 3
    out = [{"n": tuple(int(cut[d][i + 1] - cut[d][i]) for d in ("POINT", "EDGE", "FACE")), "attrs": {}}
           for i in range(len(keys))]
    for name, (dom, kind, key, v) in raw.items():
        if name in INDEX_OF:
            v = local[INDEX_OF[name]][v]
        v = v[order[dom]]
        for i, nd in enumerate(out):
            nd["attrs"][name] = (dom, kind, key, v[cut[dom][i]:cut[dom][i + 1]].copy())
    return dict(zip(keys, out))


def assemble(keys):
    """A block's mesh (write_mesh's input) from its nodes' arrays: concatenated, the indices offset."""
    parts = [_state["cache"][k] for k in keys]
    off = {"POINT": np.cumsum([0] + [p["n"][0] for p in parts], dtype=np.int32),        # int32 as the attributes:
           "EDGE": np.cumsum([0] + [p["n"][1] for p in parts], dtype=np.int32)}         # foreach_set converts others
    nf = sum(p["n"][2] for p in parts)
    kinds = {}
    for p in parts:
        kinds.update({name: v[:3] + (v[3].dtype, v[3].shape[1:]) for name, v in p["attrs"].items()})
    attrs = []
    for name, (dom, kind, key, dt, shape) in sorted(kinds.items()):
        # an attribute some batches lack (sharp_face) is zero there, its default
        arrs = [p["attrs"][name][3] if name in p["attrs"] else
                np.zeros((p["n"][DOMAIN_N[dom]] * (3 if dom == "CORNER" else 1),) + shape, dt) for p in parts]
        if name in INDEX_OF:
            arrs = [a + off[INDEX_OF[name]][i] for i, a in enumerate(arrs)]
        attrs.append((name, dom, kind, key, np.concatenate(arrs).ravel()))
    return {"n": (int(off["POINT"][-1]), int(off["EDGE"][-1]), 3 * nf, nf), "ls": np.arange(0, 3 * nf, 3, dtype=np.int32),
            "attrs": attrs}


def write_mesh(me, d):
    """Rewrites a slot's mesh in place: a geometry change re-evaluates only that object (showing or hiding an object,
    or pointing it at another mesh, rebuilds the scene's depsgraph relations: 15-20 ms every time)."""
    me.clear_geometry()
    if d is None:
        return
    nv, ne, nl, np_ = d["n"]
    me.vertices.add(nv)
    me.edges.add(ne)
    me.loops.add(nl)
    me.polygons.add(np_)
    me.polygons.foreach_set("loop_start", d["ls"])
    for name, domain, kind, key, v in d["attrs"]:
        a = me.attributes.get(name) or me.attributes.new(name, kind, domain)
        a.data.foreach_set(key, v)      # the attribute API: the old per-element API took 1.2 ms for edges alone
    me.update()


def bake(keys):
    """New nodes' geometry as arrays: NODE_BATCH nodes per builder (the mirror depths apart), all evaluated in one
    depsgraph update. A node's grid is the same in every block, so only nodes never baked are evaluated (a block that
    changes usually gains one to four new nodes of its 16)."""
    jobs = []
    for mirror in (True, False):
        ks = [k for k in keys if (k[1] >= MIRROR_FROM) == mirror]
        jobs += [(mirror, ks[i:i + NODE_BATCH]) for i in range(0, len(ks), NODE_BATCH)]
    for i, (mirror, ks) in enumerate(jobs):
        b = builder(i)
        flag = getattr(b.modifiers[0].properties.inputs, _state["mirror_id"])
        if flag.value != mirror:
            flag.value = mirror
        write_nodes(b.data, ks, _state["params"])
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    out = {}
    for i, (mirror, ks) in enumerate(jobs):
        out.update(read_nodes(builder(i).evaluated_get(dg).data, ks))
    return out


def store(nodes):
    """Keeps baked nodes; with the cache full, the least recently used ones that are not wanted go."""
    cache, want = _state["cache"], _state.get("want_nodes") or set()
    for k, d in nodes.items():
        if len(cache) >= CACHE_MAX:
            old = next((o for o in cache if o not in want), None)
            if old is not None:
                del cache[old]
        cache[k] = d
        _state["near_missing"].discard(k)


def write_nodes(me, nodes, p):
    me.clear_geometry()
    me.vertices.add(len(nodes))
    cols = {k: [] for k in NODE_ATTRS + ("nid",)}
    for i, nd in enumerate(nodes):
        d = nd[1]
        for name, v in zip(NODE_ATTRS + ("nid",), (nd[0], nd[2], nd[3], d, p.m0 * p.range(d), p.range(d), i)):
            cols[name].append(float(v))
    me.vertices.foreach_set("co", [0.0] * (3 * len(nodes)))   # every node's grid is instanced at the origin
    for name, v in cols.items():
        at = me.attributes.get(name) or me.attributes.new(name, "FLOAT", "POINT")
        at.data.foreach_set("value", v)
    me.update()


def slots(n):
    """Makes sure n free slot objects exist: always in the depsgraph and drawn, each showing one block (or nothing).
    New ones are made in one go, since adding objects rebuilds the depsgraph relations."""
    free = _state["free"]
    while len(free) < n:
        me = bpy.data.meshes.new("LOD.slot")
        me.materials.append(_state["mats"]["land"])
        me.materials.append(_state["mats"]["water"])
        ob = bpy.data.objects.new("LOD.slot", me)
        _state["coll"].objects.link(ob)
        _state["slots"].append(ob)
        free.append(ob)


def block(b, nodes):
    """A block's assembled mesh, kept for the next time it is shown (BLOCKS_MAX, the least recently used go)."""
    blocks = _state["blocks"]
    d = blocks.pop((b, nodes), None)
    if d is None:
        d = assemble(nodes)
        if len(blocks) >= BLOCKS_MAX:
            del blocks[next(iter(blocks))]
    blocks[(b, nodes)] = d
    return d


def ready(nodes):
    cache = _state["cache"]
    return all(k in cache for k in nodes)


def swap(limit=None):
    """Shows the wanted selection once every block of it that is not wholly past the horizon is baked, all in the
    same frame (no mix of two selections in view, so no crack between them); far blocks join as they are baked.
    Changed blocks are assembled from their nodes and written into slots, unless that would take more than limit ms
    (then it waits for a frame with room). Returns True when the shown set is the wanted one."""
    want = _state.get("want")
    if want is None:
        return True
    cache, shown, far = _state["cache"], _state["shown"], _state.get("far", set())
    if _state["near_missing"]:
        return False
    new = {b: nodes for b, nodes in want.items() if b not in far or ready(nodes)}
    if limit is not None and WRITE_MS * sum(1 for b, nodes in new.items() if shown.get(b, (0, 0))[1] != nodes) > limit:
        return False
    free = _state["free"]
    for b in [b for b in shown if b not in new]:
        ob = shown.pop(b)[0]
        write_mesh(ob.data, None)
        free.append(ob)
    slots(sum(1 for b in new if b not in shown))
    for b, nodes in new.items():
        cur = shown.get(b)
        if cur is not None and cur[1] == nodes:
            continue
        ob = cur[0] if cur is not None else free.pop()
        for k in nodes:
            cache[k] = cache.pop(k)              # recently used
        write_mesh(ob.data, block(b, nodes))
        shown[b] = (ob, nodes)
    _state["nodes"], _state["shown_cam"] = dict(new), _state.get("want_cam")
    _state["live"] = True
    done = len(new) == len(want)
    if done:
        _state["want"] = None
    return done


def live():
    """The stream shows a view with all its near blocks (since the last resume)."""
    return _state["live"]


def holding():
    """A cut is being staged: the On-Air Camera keeps the old view until its terrain is shown (flight_rt)."""
    return _state.get("stage") is not None


def stage_tick(force=False):
    """A cut's blocks written into hidden slots (a zero matrix) at most STAGE_BLOCKS a frame, while the old view is
    drawn; once the last ones have been drawn hidden (their GPU upload done), one frame flips the matrices. Writing
    a cut's 140 blocks in one frame took 42 ms and its first draw 92 ms (M1: 70 ms); a flip is 2 ms and a normal draw.
    """
    sg = _state["stage"]
    if _state["near_missing"] and not force:
        return
    shown, free = _state["shown"], _state["free"]
    if sg["todo"] is None:
        want, far = _state["want"], _state.get("far", set())
        sg["new"] = {b: nodes for b, nodes in want.items() if ready(nodes)}     # all near ones but when forced
        sg["todo"] = [(b, nodes) for b, nodes in sg["new"].items()
                      if shown.get(b, (0, 0))[1] != nodes and sg["ready"].get(b, (0, 0))[1] != nodes]
        slots(len(sg["todo"]))
    n = len(sg["todo"]) if force else STAGE_BLOCKS
    for b, nodes in sg["todo"][:n]:
        ob = free.pop()
        ob.matrix_world = HIDDEN
        write_mesh(ob.data, block(b, nodes))
        sg["ready"][b] = (ob, nodes)
        sg["written"] = _state["frame"]
    del sg["todo"][:n]
    if sg["todo"] or (_state["frame"] <= sg.get("written", -1) and not force):
        return
    old = []
    for b, (ob, nodes) in sg["ready"].items():
        if b in shown:
            old.append(shown[b][0])
        ob.matrix_world = SHOWN
        shown[b] = (ob, nodes)
    for b in [b for b in shown if b not in sg["new"]]:
        old.append(shown.pop(b)[0])
    for ob in old:
        ob.matrix_world = HIDDEN
    _state["retire"] = _state.get("retire", []) + old
    _state["retire_frame"] = _state["frame"]
    _state["nodes"], _state["shown_cam"] = dict(sg["new"]), _state.get("want_cam")
    _state["live"] = _state["live"] or not _state["near_missing"]
    if len(sg["new"]) == len(_state["want"]):
        _state["want"] = None
    _state["stage"] = None


def build_tick():
    """The timer that bakes nodes between frames: the selection's missing nodes first, then the prewarm queue.
    A drawn frame's LOD work (selection, baking, writing slots) stays within FRAME_MS, so a fast flight spreads it
    over frames rather than drawing one slow frame (selection, baking and writing together took 20-30 ms). CUT_MS
    while most of the wanted nodes are missing (a cut to a place nothing was prebuilt for). A ready selection is shown
    when its writes fit the frame, or once it has waited SWAP_WAIT frames."""
    if _state.get("coll") is None:
        return None
    t0 = time.perf_counter()
    if t0 - _state.get("frame_t", 0.0) > 0.1:      # no frame drawn for a while (playback stopped): a fresh budget
        _state["spent"], _state["frame_t"] = 0.0, t0
    retire = _state.get("retire")
    if retire and _state.get("frame", 0) > _state.get("retire_frame", -1):     # the flip has been drawn
        for ob in retire:
            write_mesh(ob.data, None)
            ob.matrix_world = SHOWN
        _state["free"] += retire
        _state["retire"] = []
    sg = _state.get("stage")
    sel, q = _state.setdefault("sel_queue", []), _state.setdefault("queue", [])
    cut = len(sel) > CUT_SHARE * max(len(_state.get("want_nodes") or ()), 1)
    budget = STAGE_MS - _state.get("spent", 0.0) if sg else CUT_MS if cut else FRAME_MS - _state.get("spent", 0.0)
    built = 0
    cache = _state["cache"]
    while sel or q:
        left = budget - (time.perf_counter() - t0) * 1000.0
        if left <= BAKE_FIXED_MS:
            break
        n = BATCH * NODE_BATCH if cut else max(NODE_BATCH, int((left - BAKE_FIXED_MS) / BAKE_NODE_MS))
        batch = []
        seen = set()
        while (sel or q) and len(batch) < min(n, BATCH * NODE_BATCH):
            k = sel.pop(0) if sel else q.pop(0)
            if k not in cache and k not in seen:
                batch.append(k)
                seen.add(k)
        if not batch:
            continue
        try:
            store(bake(batch))
        except Exception:                        # a raising timer is unregistered: the LOD would freeze silently
            traceback.print_exc()
        built += len(batch)
    if sg is not None:
        try:
            stage_tick(force=_state.get("frame", 0) - sg["start"] >= HOLD_MAX)
        except Exception:
            traceback.print_exc()
            _state["stage"] = None
    elif _state.get("want") is not None:
        waited = _state.get("frame", 0) - _state.get("want_frame", 0) >= SWAP_WAIT
        left = budget - (time.perf_counter() - t0) * 1000.0
        try:
            swap(None if cut or waited else left)
        except Exception:
            traceback.print_exc()
    _state["spent"] = _state.get("spent", 0.0) + (time.perf_counter() - t0) * 1000.0
    _state["built"] = _state.get("built", 0) + built
    return TICK


def make_hr(cmap):
    """A node's height range from the clearance map (conservative max, raw min) at its corners and centre."""
    cache = {}

    def hr(key):
        if key[1] == 0:
            return None
        v = cache.get(key)
        if v is None:
            hs = [cmap.ground(ls.node_dir(key, x, y, 2)) for x in (0, 1, 2) for y in (0, 1, 2)]
            ws = [cmap._bilinear(cmap.w, ls.node_dir(key, x, y, 2)) for x in (0, 1, 2) for y in (0, 1, 2)]
            pad = 5.0 + 0.1 * ls.FACE_ARC / (1 << key[1])
            v = cache[key] = (min(min(hs), min(ws)) - pad - 60.0, max(max(hs), max(ws)) + pad)
        return v
    return hr


def start(scene, cmap, p=None):
    p = p or ls.Params()
    _state["params"] = p
    coll = bpy.data.collections.get("Planet LOD")
    if coll is None:
        coll = bpy.data.collections.new("Planet LOD")
        scene.collection.children.link(coll)
    _state["coll"] = coll
    _state["groups"] = build_group("FLT_Lod", p.n)
    _state["mats"] = {"land": morph_material("Terrain"), "water": morph_material("Sea")}
    _state["hr"] = make_hr(cmap)
    _state["nodes"], _state["prev"], _state["sel_cam"], _state["want"] = {}, None, None, None
    _state["queue"], _state["sel_queue"] = [], []
    _state["live"] = False
    slots(SLOTS)


def resume():
    """The stream on: the build timer runs; the next update() selects afresh."""
    if not bpy.app.timers.is_registered(build_tick):
        bpy.app.timers.register(build_tick, first_interval=TICK, persistent=True)


def pause():
    """The stream off: no timer, no builds, every slot emptied (shown, staged or waiting to be retired); the node and
    block caches stay, so a later resume near the same place writes its blocks without baking."""
    if bpy.app.timers.is_registered(build_tick):
        bpy.app.timers.unregister(build_tick)
    sg = _state.get("stage")
    hidden = list(sg["ready"].values()) if sg else []
    for ob in [ob for ob, _ in _state["shown"].values()] + [ob for ob, _ in hidden] + _state.get("retire", []):
        write_mesh(ob.data, None)
        if ob.matrix_world != SHOWN:
            ob.matrix_world = SHOWN
        _state["free"].append(ob)
    _state["shown"].clear()
    _state["nodes"], _state["want"], _state["far"], _state["near_missing"] = {}, None, set(), set()
    _state["sel_queue"], _state["stage"], _state["retire"], _state["sel_cam"] = [], None, [], None
    _state["hist"], _state["travel"], _state["v_hold"], _state["live"] = [], 0.0, 0.0, False


def travel(cam, speed, dt):
    """How far the camera travels until a selection is drawn: the look-ahead segment's length, at MIN_FPS and at
    the recent peak speed (falling with a HOLD_TIME s time constant: 8 km/s from orbit is under 100 m/s within 9 s).
    The speed and direction are the camera's own over the last half second (the Director's frame velocity spikes to
    3x the true speed). It goes in steps (0, then 4, 8, 16 ... m) that step down only once the travel is under
    STEP_DOWN of the step: following the speed and fps of every frame changed 30-50 blocks at a time. 0 after a cut
    (speed 0) or at rest."""
    now = time.perf_counter()
    hist = _state.setdefault("hist", [])
    if speed <= 0.0:
        hist.clear()
    hist.append((now, tuple(cam)))
    while now - hist[0][0] > 0.5:
        hist.pop(0)
    span = now - hist[0][0]
    moved = math.dist(cam, hist[0][1])
    v = moved / span if span > 0.05 else max(speed, 0.0)
    _state["vdir"] = tuple((c - h) / moved for c, h in zip(cam, hist[0][1])) if moved > 1e-3 else None
    v = 0.0 if speed <= 0.0 else max(v, _state.get("v_hold", 0.0) * math.exp(-dt / HOLD_TIME))
    _state["v_hold"] = v
    m = v * ((LAG + 1) / MIN_FPS + BUILD_LAG)
    q = _state.get("travel", 0.0)
    if m > q or m < STEP_DOWN * q:
        q = 0.0 if m <= 0.0 else 4.0 * 2.0 ** max(0, math.ceil(math.log2(m / 4.0)))
    _state["travel"] = q
    return q


def update(scene, cam, speed, fps=60.0):
    """Selects the nodes for a camera at cam (moving at speed m/s) and wants that selection: its missing nodes go to
    the front of the build queue and it is shown as soon as they are all baked (build_tick). Returns the number of
    nodes it is missing."""
    t0 = time.perf_counter()
    _state["frame"] = _state.get("frame", 0) + 1
    _state["spent"], _state["frame_t"] = 0.0, t0
    p = _state["params"]
    last = _state.get("sel_cam")
    q = travel(cam, speed, 1.0 / max(fps, 1.0))
    step = max(SEL_STEP, STEP_SHARE * q)    # fast, a selection every few frames: fewer passing versions of a block
    if last is not None and math.dist(cam, last) < step:
        return 0
    _state["sel_cam"] = _state["want_cam"] = tuple(cam)       # want_cam: where the wanted selection was made
    p.margin = SEL_STEP + 1.0       # as prewarm(); the travel goes into the look-ahead segment (lod_stream.select)
    vdir = _state.get("vdir")
    ahead = None if not q or vdir is None else tuple(c + v * (q + step) for c, v in zip(cam, vdir))
    blocks = {}
    for k in ls.select(cam, p, _state["hr"], ahead):
        blocks.setdefault(ls.block_of(k, p), []).append(k)
    want = {b: tuple(sorted(v)) for b, v in blocks.items()}
    # blocks wholly past the horizon can't be seen: the selection doesn't wait for them (the horizon cull changes
    # them with every few metres of height)
    past = ls.horizon(cam)
    far = {b for b, nodes in want.items() if all(past(k) for k in nodes)}
    cache = _state["cache"]
    order = sorted(want, key=lambda b: (b in far, -b[1]))      # near blocks first, the finest first
    missing = list(dict.fromkeys(k for b in order for k in want[b] if k not in cache))
    _state["want"], _state["far"] = want, far
    _state["want_nodes"] = {k for nodes in want.values() for k in nodes}
    _state["near_missing"] = {k for b, nodes in want.items() if b not in far for k in nodes if k not in cache}
    _state["sel_queue"] = missing
    _state["want_frame"] = _state["frame"]
    sg = _state.get("stage")
    if sg is not None:              # a staged cut still being written follows the new selection
        sg["todo"] = None
        for b in [b for b, (ob, nodes) in sg["ready"].items() if want.get(b) != nodes]:
            _state.setdefault("retire", []).append(sg["ready"].pop(b)[0])
    elif speed == 0.0:                # a cut, or a view at rest: shown in this frame, or staged when it changes a lot
        shown = _state["shown"]
        if sum(1 for b, nodes in want.items() if shown.get(b, (0, 0))[1] != nodes) > STAGE_MIN:
            _state["stage"] = {"todo": None, "ready": {}, "start": _state["frame"]}
        else:
            swap()
    _state["spent"] = (time.perf_counter() - t0) * 1000.0
    return len(missing)


def prewarm(cam):
    """Queues the nodes a camera at cam would show at rest, so a cut or a blend to it finds them baked."""
    q_ = _state["params"]
    p = ls.Params(q_.n, q_.k, q_.m0, q_.d_max, SEL_STEP + 1.0, q_.block_up, q_.cull)     # update()'s margin at rest
    blocks = {}
    for k in ls.select(cam, p, _state["hr"]):
        blocks.setdefault(ls.block_of(k, p), []).append(k)
    q = _state.setdefault("queue", [])
    q.extend(k for v in blocks.values() for k in v if k not in _state["cache"])
    return len(q)


def stop(scene):
    if bpy.app.timers.is_registered(build_tick):
        bpy.app.timers.unregister(build_tick)
    obs = _state["slots"] + _state.get("builders", []) + [o for o in (bpy.data.objects.get(RIVERS),) if o]
    bpy.data.batch_remove(obs + [ob.data for ob in obs])     # one unlink pass, not one per ID
    _state["cache"].clear()
    _state["blocks"].clear()
    _state["shown"].clear()
    _state["nodes"], _state["want"], _state["builders"], _state["queue"], _state["sel_queue"] = {}, None, [], [], []
    _state["slots"], _state["free"], _state["stage"], _state["retire"], _state["live"] = [], [], None, [], False
