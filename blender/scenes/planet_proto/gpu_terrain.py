"""GPU terrain prototype (docs/handover/gpu-terrain.md): the Planet's land as displacement in the material, on a
camera-centred grid, beside the streamed terrain (lod_scene) and switchable against it. Loaded from disk.

- The height source: the Planet's own PL_Surface, probed once into an equirectangular map (land height and water level,
  m over R), W x W/2 texels, in a frame turned so the pyramids' valley lies on its equator (no pole near the show).
  Cached under ~/Library/Caches/swiftvj-flight; a float image GT_Map (R height, G water).
- The grid: a geometry clipmap in the map's own longitude and latitude. LEVELS square rings of N x N cells, cell
  CELL_M at the centre and twice as large per ring; ring l is snapped to 2 of its cells round the camera, so every
  vertex sits on a fixed point of its ring's lattice and the ground does not swim. Ring l's outer band blends its
  height to the next ring's lattice (bilinear over the even vertices), so the rings meet without a crack or a pop.
  The mesh is flat and the same every frame; the material puts each vertex on the sphere (Vector Displacement,
  object space). Its bounds cover the whole Planet, so it is never culled.
- The material: a copy of the Terrain material, its geometry attributes taken from the map (pl_w) or set to 0
  (mirror, pl_city), the Wireframe's edges off. Water: a second grid with a copy of the Sea material, at the water
  level where there is water and 2 m under the land elsewhere.
- Per frame (frame_change_pre, after flight_rt): the camera's map longitude and latitude to rt_gt_lam, rt_gt_phi.
- switch(True): the stream paused and its update a no-op, the grids shown; switch(False) the other way round.
"""
import math
import os
import time

import bpy
import numpy as np

CACHE = os.path.expanduser("~/Library/Caches/swiftvj-flight")
W = 8192                    # map texels round the equator: 12.3 m each
N = 128                     # cells per ring side
LEVELS = 8                  # rings: cells 3 m to 384 m, the outer ring 24.6 km from the camera
CELL_M = 3.0
MORPH = (0.70, 0.92)        # share of a ring's half side over which its height blends to the next ring's
LAND, WATER = "GT_Land", "GT_Water"
_state = {"on": False, "update": None, "axes": None}


def fl_mod():
    fr = next(h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "frame" and h.__module__ == "flight_rt")
    return fr.__globals__


def axes(scene):
    """The map frame: x through the pyramids' valley, z a pole 90 degrees off it."""
    G = fl_mod()
    fl = G["fl"]
    t = scene.objects["PathTarget.pyramids"].matrix_world.translation
    x = fl.norm(fl.sub(tuple(t), fl.CENTRE))
    z = fl.norm(fl.sub((0.0, 1.0, 0.0), fl.scale(x, x[1])))
    y = fl.cross(z, x)
    return np.array([x, y, z])


def bake(scene, w=W):
    """(h, wl): (w/2, w) float32 maps of land height and water level, m over R."""
    rows = w // 2
    path = bpy.data.filepath
    key = "gt-%s-%d-%d.npz" % (os.path.splitext(os.path.basename(path))[0], int(os.path.getmtime(path)) if path else 0, w)
    cache = os.path.join(CACHE, key)
    if os.path.exists(cache):
        d = np.load(cache)
        return d["h"], d["w"]
    G = fl_mod()
    A = axes(scene)
    lam = -math.pi + (np.arange(w) + 0.5) * 2.0 * math.pi / w
    h_out = np.empty((rows, w), np.float32)
    w_out = np.empty((rows, w), np.float32)
    hydro = bpy.data.objects["Planet_Hydro"]
    g = G["probe_group"](hydro)
    me = bpy.data.meshes.new("GT_Probe")
    ob = bpy.data.objects.new("GT_Probe", me)
    scene.collection.objects.link(ob)
    ob.hide_render = True
    ob.modifiers.new("probe", "NODES").node_group = g
    t0 = time.perf_counter()
    step = max(1, (1 << 21) // w)        # rows per chunk: about 2 M points
    try:
        for r0 in range(0, rows, step):
            r1 = min(rows, r0 + step)
            phi = -math.pi / 2.0 + (np.arange(r0, r1) + 0.5) * math.pi / rows
            L, P = np.meshgrid(lam, phi)
            loc = np.stack([np.cos(P) * np.cos(L), np.cos(P) * np.sin(L), np.sin(P)], -1).reshape(-1, 3)
            d = loc @ A
            me.clear_geometry()
            me.vertices.add(len(d))
            me.vertices.foreach_set("co", d.astype(np.float32).ravel())
            me.update()
            dg = bpy.context.evaluated_depsgraph_get()
            dg.update()
            ev = ob.evaluated_get(dg).data
            hh = np.empty(len(d), np.float32)
            ww = np.empty(len(d), np.float32)
            ev.attributes["fl_h"].data.foreach_get("value", hh)
            ev.attributes["fl_w"].data.foreach_get("value", ww)
            h_out[r0:r1] = hh.reshape(r1 - r0, w)
            w_out[r0:r1] = ww.reshape(r1 - r0, w)
    finally:
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(me)
        bpy.data.node_groups.remove(g)
    os.makedirs(CACHE, exist_ok=True)
    np.savez_compressed(cache, h=h_out, w=w_out)
    print("gpu_terrain: map %dx%d baked in %.1f s -> %s" % (w, rows, time.perf_counter() - t0, cache))
    return h_out, w_out


def make_image(h, wl):
    img = bpy.data.images.get("GT_Map")
    if img is not None:
        bpy.data.images.remove(img)
    rows, w = h.shape
    img = bpy.data.images.new("GT_Map", w, rows, alpha=False, float_buffer=True, is_data=True)
    px = np.zeros((rows, w, 4), np.float32)
    px[..., 0], px[..., 1], px[..., 3] = h, wl, 1.0
    img.pixels.foreach_set(px.ravel())      # after the colour space: setting it regenerates a generated image blank
    img.update()
    img.pack()
    return img


def make_mesh(name):
    """The clipmap: per vertex its ring (gt_l) and lattice index (gt_i, gt_j) round the ring's centre."""
    me = bpy.data.meshes.get(name) or bpy.data.meshes.new(name)
    me.clear_geometry()
    verts, faces, li, ii, jj = [], [], [], [], []
    h = N // 2
    for lv in range(LEVELS):
        idx = {}
        for j in range(-h, h + 1):
            for i in range(-h, h + 1):
                idx[(i, j)] = len(verts)
                verts.append((i * 0.01, j * 0.01, lv * 0.01))
                li.append(float(lv))
                ii.append(float(i))
                jj.append(float(j))
        inner = h // 2 - 1 if lv else -1        # ring l leaves the inner part to ring l-1, one cell of overlap
        for j in range(-h, h):
            for i in range(-h, h):
                if lv and -inner <= i < inner and -inner <= j < inner:
                    continue
                a, b, c, d = idx[(i, j)], idx[(i + 1, j)], idx[(i + 1, j + 1)], idx[(i, j + 1)]
                faces.append((a, b, c))
                faces.append((a, c, d))
    big = 40000.0           # loose corner vertices: bounds round the whole Planet, never culled
    for x in (-big, big):
        for y in (-big, big):
            for z in (-big, 2000.0):
                verts.append((x, y, z))
                li.append(-1.0)
                ii.append(0.0)
                jj.append(0.0)
    me.from_pydata(verts, [], faces)
    for nm, vals in (("gt_l", li), ("gt_i", ii), ("gt_j", jj)):
        at = me.attributes.get(nm) or me.attributes.new(nm, "FLOAT", "POINT")
        at.data.foreach_set("value", vals)
    me.update()
    ob = bpy.data.objects.get(name) or bpy.data.objects.new(name, me)
    if ob.name not in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.link(ob)
    ob.data = me
    return ob


class NB:
    """A few shader node helpers."""

    def __init__(self, nt):
        self.nt, self.N, self.L = nt, nt.nodes, nt.links

    def node(self, kind, **kw):
        n = self.N.new(kind)
        for k, v in kw.items():
            setattr(n, k, v)
        return n

    def feed(self, sock, v):
        if isinstance(v, (int, float)):
            sock.default_value = v
        elif isinstance(v, tuple) and not hasattr(v[0], "node"):
            sock.default_value = v
        else:
            self.L.new(v, sock)

    def math(self, op, a, b=0.0, c=None):
        n = self.node("ShaderNodeMath", operation=op)
        self.feed(n.inputs[0], a)
        self.feed(n.inputs[1], b)
        if c is not None:
            self.feed(n.inputs[2], c)
        return n.outputs[0]

    def vec(self, x, y, z):
        n = self.node("ShaderNodeCombineXYZ")
        for k, v in enumerate((x, y, z)):
            self.feed(n.inputs[k], v)
        return n.outputs[0]

    def vmath(self, op, a, b=None, scale=None):
        n = self.node("ShaderNodeVectorMath", operation=op)
        self.feed(n.inputs[0], a)
        if b is not None:
            self.feed(n.inputs[1], b)
        if scale is not None:
            self.feed(n.inputs["Scale"], scale)
        return n.outputs["Vector"] if op not in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else n.outputs["Value"]

    def attr(self, name, kind="GEOMETRY"):
        a = self.node("ShaderNodeAttribute", attribute_type=kind, attribute_name=name)
        return a.outputs["Fac"]

    def lookup(self, img, lam, phi):
        """(height, water) of the map at longitude lam, latitude phi (radians)."""
        u = self.math("ADD", self.math("DIVIDE", lam, 2.0 * math.pi), 0.5)
        v = self.math("ADD", self.math("DIVIDE", phi, math.pi), 0.5)
        tx = self.node("ShaderNodeTexImage", image=img, interpolation="Linear", extension="REPEAT")
        self.feed(tx.inputs["Vector"], self.vec(u, v, 0.0))
        sp = self.node("ShaderNodeSeparateColor")
        self.feed(sp.inputs[0], tx.outputs["Color"])
        return sp.outputs[0], sp.outputs[1]

    def world_dir(self, A, lam, phi):
        """The world direction of map longitude and latitude."""
        c = self.math("COSINE", phi)
        lx, ly, lz = self.math("MULTIPLY", c, self.math("COSINE", lam)), self.math("MULTIPLY", c, self.math("SINE", lam)), self.math("SINE", phi)
        out = None
        for k, comp in enumerate((lx, ly, lz)):
            term = self.vmath("SCALE", tuple(float(x) for x in A[k]), scale=comp)
            out = term if out is None else self.vmath("ADD", out, term)
        return out

    def map_coords(self, A, d):
        """Longitude and latitude in the map frame of a world direction d."""
        cx, cy, cz = (self.vmath("DOT_PRODUCT", d, tuple(float(x) for x in A[k])) for k in range(3))
        lam = self.math("ARCTAN2", cy, cx)
        phi = self.math("ARCSINE", self.math("MINIMUM", self.math("MAXIMUM", cz, -1.0), 1.0))
        return lam, phi


def displacement(nb, img, A, water):
    """Vector Displacement (object space) that puts a clipmap vertex on the Planet."""
    import flight as fl     # noqa: E402 (flight_rt put blender/scenes on sys.path)
    lv, i, j = nb.attr("gt_l"), nb.attr("gt_i"), nb.attr("gt_j")
    lc, pc = nb.attr("rt_gt_lam", "VIEW_LAYER"), nb.attr("rt_gt_phi", "VIEW_LAYER")
    d0 = CELL_M / fl.R
    step = nb.math("MULTIPLY", d0, nb.math("POWER", 2.0, lv))
    two = nb.math("MULTIPLY", step, 2.0)
    bl = nb.math("MULTIPLY", nb.math("FLOOR", nb.math("DIVIDE", lc, two)), two)
    bp = nb.math("MULTIPLY", nb.math("FLOOR", nb.math("DIVIDE", pc, two)), two)

    def at(ii, jj):
        return nb.math("MULTIPLY_ADD", ii, step, bl), nb.math("MULTIPLY_ADD", jj, step, bp)

    lam, phi = at(i, j)
    h, w = nb.lookup(img, lam, phi)
    # the next ring's lattice: the even vertices round this one, bilinear
    i0 = nb.math("MULTIPLY", nb.math("FLOOR", nb.math("MULTIPLY", i, 0.5)), 2.0)
    j0 = nb.math("MULTIPLY", nb.math("FLOOR", nb.math("MULTIPLY", j, 0.5)), 2.0)
    fx = nb.math("MULTIPLY", nb.math("SUBTRACT", i, i0), 0.5)
    fy = nb.math("MULTIPLY", nb.math("SUBTRACT", j, j0), 0.5)
    i1, j1 = nb.math("ADD", i0, 2.0), nb.math("ADD", j0, 2.0)
    hs = [nb.lookup(img, *at(a, b)) for a, b in ((i0, j0), (i1, j0), (i0, j1), (i1, j1))]
    k = 0 if not water else 1

    def lerp(a, b, t):
        return nb.math("ADD", a, nb.math("MULTIPLY", nb.math("SUBTRACT", b, a), t))

    hc = lerp(lerp(hs[0][k], hs[1][k], fx), lerp(hs[2][k], hs[3][k], fx), fy)
    hl = lerp(lerp(hs[0][0], hs[1][0], fx), lerp(hs[2][0], hs[3][0], fx), fy)
    # the blend over the ring's outer band (none on the outermost ring)
    rr = nb.math("DIVIDE", nb.math("MAXIMUM", nb.math("ABSOLUTE", i), nb.math("ABSOLUTE", j)), N / 2.0)
    mr = nb.node("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
    nb.feed(mr.inputs["Value"], rr)
    mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = MORPH
    a = nb.math("MULTIPLY", mr.outputs["Result"], nb.math("LESS_THAN", lv, LEVELS - 1 - 0.5))
    hv = lerp(h if not water else w, hc, a)
    if water:       # where there is no water (level under the land), 2 m under the land
        hland = lerp(h, hl, a)
        wet = nb.math("GREATER_THAN", nb.math("SUBTRACT", hv, hland), -0.5)
        hv = lerp(nb.math("SUBTRACT", hland, 2.0), hv, wet)
    d = nb.world_dir(A, lam, phi)
    pos = nb.vmath("ADD", tuple(fl.CENTRE), nb.vmath("SCALE", d, scale=nb.math("ADD", hv, fl.R)))
    geo = nb.node("ShaderNodeNewGeometry")         # the object sits at the origin, unrotated: object space = world
    disp = nb.vmath("SUBTRACT", pos, geo.outputs["Position"])
    vd = nb.node("ShaderNodeVectorDisplacement", space="OBJECT")
    vd.inputs["Midlevel"].default_value = 0.0
    vd.inputs["Scale"].default_value = 1.0
    nb.feed(vd.inputs["Vector"], disp)
    return vd.outputs[0]


def material(src, name, img, A, water):
    old = bpy.data.materials.get(name)
    if old is not None:
        bpy.data.materials.remove(old)
    m = bpy.data.materials[src].copy()
    m.name = name
    nt = m.node_tree
    nb = NB(nt)
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
    for lk in list(out.inputs["Displacement"].links):
        nt.links.remove(lk)
    nt.links.new(displacement(nb, img, A, water), out.inputs["Displacement"])
    m.displacement_method = "DISPLACEMENT"
    # the surface's geometry attributes: water level from the map, the rest 0
    geo = nb.node("ShaderNodeNewGeometry")
    import flight as fl     # noqa: E402
    dpos = nb.vmath("NORMALIZE", nb.vmath("SUBTRACT", geo.outputs["Position"], tuple(fl.CENTRE)))
    lam, phi = nb.map_coords(A, dpos)
    _, wmap = nb.lookup(img, lam, phi)
    for n in [n for n in nt.nodes if n.type == "ATTRIBUTE" and n.attribute_type == "GEOMETRY" and not n.attribute_name.startswith("gt_")]:
        for o in n.outputs:
            for lk in list(o.links):
                to = lk.to_socket
                nt.links.remove(lk)
                if n.attribute_name == "pl_w" and o.name == "Fac":
                    nt.links.new(wmap, to)
                elif hasattr(to, "default_value"):
                    try:
                        to.default_value = 0.0 if not hasattr(to.default_value, "__len__") else type(to.default_value)((0.0,) * len(to.default_value))
                    except (TypeError, AttributeError):
                        pass
    # the shading normals: the flat grid's own normals stay under displacement; True Normal is the displaced
    # triangle's (the terrain is lit in the shader from the Geometry node's normal, emission only)
    for n in [n for n in nt.nodes if n.type == "NEW_GEOMETRY"]:
        for lk in list(n.outputs["Normal"].links):
            to = lk.to_socket
            nt.links.remove(lk)
            nt.links.new(n.outputs["True Normal"], to)
    for n in [n for n in nt.nodes if n.type == "WIREFRAME"]:     # no edges: the user's call (2026-11-13)
        for lk in list(n.outputs["Fac"].links):
            to = lk.to_socket
            nt.links.remove(lk)
            to.default_value = 0.0
    return m


def frame(scene, depsgraph=None):
    if not _state["on"]:
        return
    A = _state["axes"]
    cam = scene.camera.matrix_world.translation
    import flight as fl     # noqa: E402
    d = np.array(fl.norm(fl.sub(tuple(cam), fl.CENTRE)))
    c = A @ d
    scene["rt_gt_lam"] = float(math.atan2(c[1], c[0]))
    scene["rt_gt_phi"] = float(math.asin(max(-1.0, min(1.0, c[2]))))


def build(scene=None, w=W):
    scene = scene or bpy.context.scene
    A = _state["axes"] = axes(scene)
    t = time.perf_counter()
    h, wl = bake(scene, w)
    img = make_image(h, wl)
    land, water = make_mesh(LAND), make_mesh(WATER)
    land.data.materials.clear()
    land.data.materials.append(material("Terrain", "Terrain GPU", img, A, False))
    water.data.materials.clear()
    water.data.materials.append(material("Sea LOD", "Sea GPU", img, A, True))
    for ob in (land, water):
        ob.hide_viewport = ob.hide_render = True
    for hl in list(bpy.app.handlers.frame_change_pre):
        if getattr(hl, "__name__", "") == "frame" and getattr(hl, "__module__", "") == __name__:
            bpy.app.handlers.frame_change_pre.remove(hl)
    bpy.app.handlers.frame_change_pre.append(frame)
    return round(time.perf_counter() - t, 1)


def switch(on):
    """True: the GPU terrain on air, the stream paused; False: the stream back."""
    G = fl_mod()
    LOD = G["lod_scene"]
    if on and not _state["on"]:
        _state["update"] = LOD.update
        LOD.update = lambda *a, **k: 0
        LOD.pause()
    elif not on and _state["on"]:
        LOD.update = _state["update"]
        LOD.resume()
    _state["on"] = on
    frame(bpy.context.scene)
    for nm in (LAND, WATER):
        ob = bpy.context.scene.objects.get(nm)
        if ob is not None:
            ob.hide_viewport = ob.hide_render = not on
