"""The Planet's terrain on the GPU (docs/handover/gpu-terrain.md): one fixed grid round the camera that the material
puts on the Planet, from a height map of the Planet's own surface. Started and fed by flight_rt; loaded from disk.

- The height source: PL_Surface, probed once (flight_rt.probe_group) into an equirectangular map in a frame turned so
  the pyramids' valley lies on its equator: W x W/2 texels (12.3 m at the valley), cached under
  ~/Library/Caches/swiftvj-flight. Image GT_Map: land height and water level (m over R), each as a coarse part (whole
  multiples of 16 m) and a fine rest, so the GPU's half floats keep them to about a centimetre (one float went up as a
  half and terraced the slopes). Image GT_Flow: the rivers' flow, half the resolution.
- The grid: a geometry clipmap in the map's longitude and latitude. LEVELS square rings of N x N cells, CELL_M at the
  centre and twice as large per ring. Ring l is snapped to two of its cells round the camera, so every vertex sits on a
  fixed point of its ring's lattice: nothing swims. Over a ring's outer band (MORPH) its height blends to the next
  ring's lattice, so the rings meet with no crack and a vertex leaving a ring was already where the next one draws it.
  Where a ring lies under the finer ring inside it (one cell of overlap in the mesh), its pixels are cut away (a
  transparent mix at the material's output): the see-through water drew the overlap twice, as dark ring outlines.
- Near detail: two octaves of noise (NOISE) on the land within NOISE_NEAR of the camera, none at the water, in the
  vertices and in the shading normal; beyond, the map alone.
- The material: a copy of Terrain (land) and of Sea (water) with Vector Displacement in object space; the grid's own
  normals stay flat under displacement, so the land is lit by a normal from the map's slope and the noise's (smooth,
  per pixel). Their geometry attributes come from the maps: pl_w, pl_depth, pl_flow; mirror and pl_city (site lights,
  dropped) are 0. Water: a second grid at the water level where there is water and 2 m under the land elsewhere.
- Bounds: eight loose corner vertices round the whole Planet, so the grids are never culled.
- Per frame flight_rt calls follow(): the camera's map longitude and latitude to rt_gt_lam, rt_gt_phi.
"""
import math
import os
import time

import bpy
import numpy as np

import flight as fl

CACHE = os.path.expanduser("~/Library/Caches/swiftvj-flight")
W = 8192                    # map texels round the equator: 12.3 m each
N = 128                     # cells per ring side
LEVELS = 8                  # rings: cells 3 m to 384 m, the outer ring 24.6 km from the camera
CELL_M = 3.0
MORPH = (0.70, 0.92)        # share of a ring's half side over which its height blends to the next ring's
COARSE = 16.0               # m: the coarse part of a height is a whole multiple of this
NOISE = ((22.0, 1.4), (6.0, 0.45))     # (wavelength m, amplitude m) of the near detail
NOISE_NEAR = (60.0, 120.0)  # m from the camera over which the detail fades out (ring 0's blend starts at 134 m)
NOISE_DRY = (0.5, 3.0)      # m of land over its water level over which the detail fades in
LAND, WATER = "GT_Land", "GT_Water"
_state = {"axes": None}


def axes(scene):
    """The map frame: x through the pyramids' valley, z a pole 90 degrees off it."""
    t = scene.objects["PathTarget.pyramids"].matrix_world.translation
    x = fl.norm(fl.sub(tuple(t), fl.CENTRE))
    z = fl.norm(fl.sub((0.0, 1.0, 0.0), fl.scale(x, x[1])))
    y = fl.cross(z, x)
    return np.array([x, y, z])


def bake(scene, probe_group, w=W):
    """(h, wl, flow): (w/2, w) float32 land height and water level, (w/4, w/2, 3) float16 flow."""
    rows = w // 2
    path = bpy.data.filepath
    key = "gt-%s-%d-%d.npz" % (os.path.splitext(os.path.basename(path))[0], int(os.path.getmtime(path)) if path else 0, w)
    cache = os.path.join(CACHE, key)
    if os.path.exists(cache):
        d = np.load(cache)
        if "f" in d:
            return d["h"], d["w"], d["f"]
    A = axes(scene)
    lam = -math.pi + (np.arange(w) + 0.5) * 2.0 * math.pi / w
    h_out = np.empty((rows, w), np.float32)
    w_out = np.empty((rows, w), np.float32)
    f_out = np.empty((rows, w, 3), np.float32)
    g = probe_group(bpy.data.objects["Planet_Hydro"])
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
            hh, ww, ff = np.empty(len(d), np.float32), np.empty(len(d), np.float32), np.empty(3 * len(d), np.float32)
            ev.attributes["fl_h"].data.foreach_get("value", hh)
            ev.attributes["fl_w"].data.foreach_get("value", ww)
            ev.attributes["fl_f"].data.foreach_get("vector", ff)
            h_out[r0:r1] = hh.reshape(r1 - r0, w)
            w_out[r0:r1] = ww.reshape(r1 - r0, w)
            f_out[r0:r1] = ff.reshape(r1 - r0, w, 3)
    finally:
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(me)
        bpy.data.node_groups.remove(g)
    f_half = (0.25 * (f_out[0::2, 0::2] + f_out[1::2, 0::2] + f_out[0::2, 1::2] + f_out[1::2, 1::2])).astype(np.float16)
    os.makedirs(CACHE, exist_ok=True)
    np.savez_compressed(cache, h=h_out, w=w_out, f=f_half)
    print("gpu_terrain: map %dx%d baked in %.1f s -> %s" % (w, rows, time.perf_counter() - t0, cache))
    return h_out, w_out, f_half


def image(name, px):
    """A packed float image of px ((rows, cols, 4) float32), its channels as they are."""
    img = bpy.data.images.get(name)
    if img is not None:
        bpy.data.images.remove(img)
    rows, cols = px.shape[:2]
    img = bpy.data.images.new(name, cols, rows, alpha=True, float_buffer=True, is_data=True)
    img.alpha_mode = "CHANNEL_PACKED"
    img.pixels.foreach_set(px.astype(np.float32).ravel())     # after the colour space: setting it regenerates the image
    img.update()
    img.pack()
    return img


def split(x):
    c = np.round(x / COARSE) * COARSE
    return c, x - c


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
    big = 40000.0
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
    """Shader node helpers."""

    def __init__(self, nt):
        self.nt, self.N, self.L = nt, nt.nodes, nt.links

    def node(self, kind, **kw):
        n = self.N.new(kind)
        for k, v in kw.items():
            setattr(n, k, v)
        return n

    def feed(self, sock, v):
        if isinstance(v, (int, float)) or isinstance(v, tuple) and not hasattr(v[0], "node"):
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

    def lerp(self, a, b, t):
        return self.math("ADD", a, self.math("MULTIPLY", self.math("SUBTRACT", b, a), t))

    def smooth(self, v, a, b):
        n = self.node("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
        self.feed(n.inputs["Value"], v)
        n.inputs["From Min"].default_value, n.inputs["From Max"].default_value = a, b
        return n.outputs["Result"]

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
        return n.outputs["Value"] if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else n.outputs["Vector"]

    def attr(self, name, kind="GEOMETRY"):
        return self.node("ShaderNodeAttribute", attribute_type=kind, attribute_name=name).outputs["Fac"]

    def uv(self, lam, phi):
        u = self.math("ADD", self.math("DIVIDE", lam, 2.0 * math.pi), 0.5)
        v = self.math("ADD", self.math("DIVIDE", phi, math.pi), 0.5)
        return self.vec(u, v, 0.0)

    def tex(self, img, lam, phi):
        tx = self.node("ShaderNodeTexImage", image=img, interpolation="Cubic", extension="REPEAT")
        self.feed(tx.inputs["Vector"], self.uv(lam, phi))
        return tx

    def lookup(self, img, lam, phi):
        """(land height, water level) of the map at longitude lam, latitude phi."""
        tx = self.tex(img, lam, phi)
        sp = self.node("ShaderNodeSeparateColor")
        self.feed(sp.inputs[0], tx.outputs["Color"])
        return self.math("ADD", sp.outputs[0], sp.outputs[1]), self.math("ADD", sp.outputs[2], tx.outputs["Alpha"])

    def frame_vec(self, A, lx, ly, lz):
        out = None
        for k, comp in enumerate((lx, ly, lz)):
            term = self.vmath("SCALE", tuple(float(x) for x in A[k]), scale=comp)
            out = term if out is None else self.vmath("ADD", out, term)
        return out

    def world_dir(self, A, lam, phi):
        c = self.math("COSINE", phi)
        return self.frame_vec(A, self.math("MULTIPLY", c, self.math("COSINE", lam)), self.math("MULTIPLY", c, self.math("SINE", lam)),
                              self.math("SINE", phi))

    def map_coords(self, A, d):
        cx, cy, cz = (self.vmath("DOT_PRODUCT", d, tuple(float(x) for x in A[k])) for k in range(3))
        return self.math("ARCTAN2", cy, cx), self.math("ARCSINE", self.math("MINIMUM", self.math("MAXIMUM", cz, -1.0), 1.0))

    def cam(self):
        return self.vec(self.attr("rt_cam_x", "VIEW_LAYER"), self.attr("rt_cam_y", "VIEW_LAYER"), self.attr("rt_cam_z", "VIEW_LAYER"))

    def detail(self, p, h, w):
        """The near noise (m) at world point p on land of height h over water level w."""
        out = None
        for wave, amp in NOISE:
            nz = self.node("ShaderNodeTexNoise", noise_dimensions="3D")
            nz.inputs["Scale"].default_value = 1.0 / wave
            nz.inputs["Detail"].default_value = 1.0
            self.feed(nz.inputs["Vector"], p)
            term = self.math("MULTIPLY", self.math("SUBTRACT", nz.outputs["Fac"], 0.5), 2.0 * amp)
            out = term if out is None else self.math("ADD", out, term)
        near = self.math("SUBTRACT", 1.0, self.smooth(self.vmath("DISTANCE", p, self.cam()), *NOISE_NEAR))
        dry = self.smooth(self.math("SUBTRACT", h, w), *NOISE_DRY)
        return self.math("MULTIPLY", out, self.math("MULTIPLY", near, dry))


def displacement(nb, img, A, water):
    """Vector Displacement (object space) that puts a clipmap vertex on the Planet."""
    lv, i, j = nb.attr("gt_l"), nb.attr("gt_i"), nb.attr("gt_j")
    lc, pc = nb.attr("rt_gt_lam", "VIEW_LAYER"), nb.attr("rt_gt_phi", "VIEW_LAYER")
    step = nb.math("MULTIPLY", CELL_M / fl.R, nb.math("POWER", 2.0, lv))
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
    cs = [nb.lookup(img, *at(a, b)) for a, b in ((i0, j0), (i1, j0), (i0, j1), (i1, j1))]

    def bil(k):
        return nb.lerp(nb.lerp(cs[0][k], cs[1][k], fx), nb.lerp(cs[2][k], cs[3][k], fx), fy)

    rr = nb.math("DIVIDE", nb.math("MAXIMUM", nb.math("ABSOLUTE", i), nb.math("ABSOLUTE", j)), N / 2.0)
    a = nb.math("MULTIPLY", nb.smooth(rr, *MORPH), nb.math("LESS_THAN", lv, LEVELS - 1 - 0.5))
    hland = nb.lerp(h, bil(0), a)
    d = nb.world_dir(A, lam, phi)
    if water:
        wl = nb.lerp(w, bil(1), a)
        wet = nb.math("GREATER_THAN", nb.math("SUBTRACT", wl, hland), -0.5)
        hv = nb.lerp(nb.math("SUBTRACT", hland, 2.0), wl, wet)
    else:
        p0 = nb.vmath("ADD", tuple(fl.CENTRE), nb.vmath("SCALE", d, scale=nb.math("ADD", hland, fl.R)))
        hv = nb.math("ADD", hland, nb.detail(p0, hland, w))
    pos = nb.vmath("ADD", tuple(fl.CENTRE), nb.vmath("SCALE", d, scale=nb.math("ADD", hv, fl.R)))
    geo = nb.node("ShaderNodeNewGeometry")         # the object sits at the origin, unrotated: object space = world
    vd = nb.node("ShaderNodeVectorDisplacement", space="OBJECT")
    vd.inputs["Midlevel"].default_value = 0.0
    vd.inputs["Scale"].default_value = 1.0
    nb.feed(vd.inputs["Vector"], nb.vmath("SUBTRACT", pos, geo.outputs["Position"]))
    return vd.outputs[0]


def surface(nb, img, flow, A):
    """Per pixel: the map's height and water level, the flow, and the land's normal from the map's slope and the
    near noise's."""
    geo = nb.node("ShaderNodeNewGeometry")
    up = nb.vmath("NORMALIZE", nb.vmath("SUBTRACT", geo.outputs["Position"], tuple(fl.CENTRE)))
    lam, phi = nb.map_coords(A, up)
    h, w = nb.lookup(img, lam, phi)
    ftx = nb.tex(flow, lam, phi)
    dl = 2.0 * math.pi / W          # one texel
    hx = nb.math("SUBTRACT", nb.lookup(img, nb.math("ADD", lam, dl), phi)[0], nb.lookup(img, nb.math("SUBTRACT", lam, dl), phi)[0])
    hy = nb.math("SUBTRACT", nb.lookup(img, lam, nb.math("ADD", phi, dl))[0], nb.lookup(img, lam, nb.math("SUBTRACT", phi, dl))[0])
    span = 2.0 * dl * fl.R
    gx = nb.math("DIVIDE", hx, nb.math("MULTIPLY", span, nb.math("MAXIMUM", nb.math("COSINE", phi), 0.05)))
    gy = nb.math("DIVIDE", hy, span)
    east = nb.frame_vec(A, nb.math("MULTIPLY", nb.math("SINE", lam), -1.0), nb.math("COSINE", lam), 0.0)
    north = nb.frame_vec(A, nb.math("MULTIPLY", nb.math("MULTIPLY", nb.math("SINE", phi), nb.math("COSINE", lam)), -1.0),
                         nb.math("MULTIPLY", nb.math("MULTIPLY", nb.math("SINE", phi), nb.math("SINE", lam)), -1.0), nb.math("COSINE", phi))
    eps = 0.75
    p = geo.outputs["Position"]

    def dnoise(axis):
        pa = nb.detail(nb.vmath("ADD", p, nb.vmath("SCALE", axis, scale=eps)), h, w)
        pb = nb.detail(nb.vmath("SUBTRACT", p, nb.vmath("SCALE", axis, scale=eps)), h, w)
        return nb.math("DIVIDE", nb.math("SUBTRACT", pa, pb), 2.0 * eps)

    gx = nb.math("ADD", gx, dnoise(east))
    gy = nb.math("ADD", gy, dnoise(north))
    n = nb.vmath("NORMALIZE", nb.vmath("SUBTRACT", nb.vmath("SUBTRACT", up, nb.vmath("SCALE", east, scale=gx)),
                                       nb.vmath("SCALE", north, scale=gy)))
    return {"h": h, "w": w, "flow": ftx.outputs["Color"], "normal": n}


def covered(nb, A):
    """1 where this pixel of ring l lies inside ring l-1 (snapped to this ring's cell, N/4 of them each side)."""
    lv = nb.attr("gt_l")
    lc, pc = nb.attr("rt_gt_lam", "VIEW_LAYER"), nb.attr("rt_gt_phi", "VIEW_LAYER")
    step = nb.math("MULTIPLY", CELL_M / fl.R, nb.math("POWER", 2.0, nb.math("ROUND", lv)))
    geo = nb.node("ShaderNodeNewGeometry")
    lam, phi = nb.map_coords(A, nb.vmath("NORMALIZE", nb.vmath("SUBTRACT", geo.outputs["Position"], tuple(fl.CENTRE))))
    reach = nb.math("MULTIPLY", step, N / 4.0 - 0.01)

    def inside(x, c):
        base = nb.math("MULTIPLY", nb.math("FLOOR", nb.math("DIVIDE", c, step)), step)
        return nb.math("LESS_THAN", nb.math("ABSOLUTE", nb.math("SUBTRACT", x, base)), reach)

    return nb.math("MULTIPLY", nb.math("MULTIPLY", inside(lam, lc), inside(phi, pc)), nb.math("GREATER_THAN", lv, 0.5))


def material(src, name, img, flow, A, water):
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
    # the overlap: a pixel the finer ring draws is cut from this one
    shader = out.inputs["Surface"].links[0].from_socket
    mix = nb.node("ShaderNodeMixShader")
    nt.links.new(covered(nb, A), mix.inputs["Fac"])
    nt.links.new(shader, mix.inputs[1])
    nt.links.new(nb.node("ShaderNodeBsdfTransparent").outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    sf = surface(nb, img, flow, A)
    given = {"pl_w": sf["w"], "pl_depth": nb.math("SUBTRACT", sf["w"], sf["h"]), "pl_flow": sf["flow"]}
    for n in [n for n in nt.nodes if n.type == "ATTRIBUTE" and n.attribute_type == "GEOMETRY" and not n.attribute_name.startswith("gt_")]:
        for o in n.outputs:
            for lk in list(o.links):
                to = lk.to_socket
                nt.links.remove(lk)
                if n.attribute_name in given:
                    nt.links.new(given[n.attribute_name], to)
                elif hasattr(to, "default_value"):         # mirror, pl_city: 0
                    dv = to.default_value
                    to.default_value = type(dv)((0.0,) * len(dv)) if hasattr(dv, "__len__") else 0.0
    # the shading normal: the grid's own normals stay flat under displacement. Land: the map's and the noise's slope;
    # water: the displaced triangle's
    for n in [n for n in nt.nodes if n.type == "NEW_GEOMETRY"]:
        for lk in list(n.outputs["Normal"].links):
            to = lk.to_socket
            nt.links.remove(lk)
            nt.links.new(n.outputs["True Normal"] if water else sf["normal"], to)
    return m


def follow(scene, cam):
    """The camera's map longitude and latitude, for the grids' snapping (flight_rt.frame)."""
    A = _state["axes"]
    if A is None:
        return
    c = A @ np.array(fl.norm(fl.sub(tuple(cam), fl.CENTRE)))
    scene["rt_gt_lam"] = float(math.atan2(c[1], c[0]))
    scene["rt_gt_phi"] = float(math.asin(max(-1.0, min(1.0, c[2]))))


def start(scene, probe_group):
    t = time.perf_counter()
    A = _state["axes"] = axes(scene)
    h, wl, f = bake(scene, probe_group)
    hc, hf = split(h)
    wc, wf = split(wl)
    img = image("GT_Map", np.stack([hc, hf, wc, wf], -1))
    flow = image("GT_Flow", np.concatenate([f.astype(np.float32), np.ones(f.shape[:2] + (1,), np.float32)], -1))
    land, water = make_mesh(LAND), make_mesh(WATER)
    for ob, src, name, wet in ((land, "Terrain", "Terrain GPU", False), (water, "Sea", "Sea GPU", True)):
        ob.data.materials.clear()
        ob.data.materials.append(material(src, name, img, flow, A, wet))
        ob.hide_viewport = ob.hide_render = False
    follow(scene, scene.camera.matrix_world.translation if scene.camera else fl.add(fl.CENTRE, (0.0, 0.0, 1.0), fl.R))
    print("gpu_terrain: started in %.1f s" % (time.perf_counter() - t))


def stop(scene):
    for nm in (LAND, WATER):
        ob = scene.objects.get(nm)
        if ob is not None:
            ob.hide_viewport = ob.hide_render = True
