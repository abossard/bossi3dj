"""The Planet's terrain on the GPU (docs/handover/gpu-terrain.md): one fixed grid round the camera that the material
puts on the Planet, from a height map of the Planet's own surface. Started and fed by flight_rt; loaded from disk.

- The height source: PL_Surface, probed once (flight_rt.probe_group) into an equirectangular map in a frame turned so
  the pyramids' valley lies on its equator: W x W/2 texels (12.3 m at the valley), cached under
  ~/Library/Caches/swiftvj-flight. Image GT_Map: land height and water level (m over R), each as a coarse part (whole
  multiples of 16 m) and a fine rest, so the GPU's half floats keep them to about a centimetre (one float went up as a
  half and terraced the slopes). Image GT_Flow: the rivers' flow, half the resolution, spread from the river's centre
  line over its whole water (FLOW_SPREAD); its alpha is the pads' contact.
- The regional map (GT_Region, GT_RegionFlow): the same at REGION_M a texel over REGION, the box of the camera targets
  with a margin, so rivers under 25 m that the 12 m map never had are drawn. The shaders read both and blend to the
  regional one over REGION_EDGE inside its border.
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
REGION_ON = False           # bake and draw the regional map. Off (2026-11-15): it drew no new rivers (the planet's are
#                             50 to 100 m wide; 0.006 km² more inland water, none under 25 m), cost about 7.5 ms a frame
#                             under load and drew stripes on the land at its blend (review/water_map_check.py, river_check.py)
REGION = ((-10200.0, 4600.0), (-14000.0, 10000.0))    # m along the map's longitude and latitude at R: the box of the
#                                                       camera targets (pyramids, lake, river, coast) and 2 km round it
REGION_M = 4.0              # m a texel of the regional map (at its equator)
REGION_EDGE = 300.0         # m inside the regional map's border over which the shaders blend from the 12 m map to it
FLOW_SPREAD = 150.0         # m: the flow, stored on the river's centre line, is spread this far over the water round it
CACHE_V = "gt2"             # cache file prefix: gt2 holds the spread flow
_state = {"axes": None}


def grid(region=False):
    """A map's texel lattice: (lam0, dlam, cols, phi0, dphi, rows, wrap), texel centres at lam0 + (x + 0.5) dlam."""
    if not region:
        return (-math.pi, 2.0 * math.pi / W, W, -math.pi / 2.0, math.pi / (W // 2), W // 2, True)
    (l0, l1), (p0, p1) = REGION
    d = REGION_M / fl.R
    cols, rows = int(round((l1 - l0) / REGION_M)), int(round((p1 - p0) / REGION_M))
    return (l0 / fl.R, d, cols, p0 / fl.R, d, rows, False)


def spread(f, wet, reach):
    """f (rows, cols, 3) with the flow on the river's centre line: every wet texel within reach (texels) of it takes the
    mean of its flowing neighbours, ring by ring outward. Dry texels and texels already flowing keep theirs."""
    f = f.copy()
    have = np.abs(f).sum(-1) > 1e-6
    for _ in range(int(reach)):
        need = wet & ~have
        acc, cnt = np.zeros_like(f), np.zeros(have.shape, np.float32)
        for ax, sh in ((0, 1), (0, -1), (1, 1), (1, -1)):
            acc += np.roll(f * have[..., None], sh, ax)
            cnt += np.roll(have, sh, ax)
        fill = need & (cnt > 0)
        if not fill.any():
            break
        f[fill] = acc[fill] / cnt[fill][:, None]
        have |= fill
    return f


def axes(scene):
    """The map frame: x through the pyramids' valley, z a pole 90 degrees off it."""
    t = scene.objects["PathTarget.pyramids"].matrix_world.translation
    x = fl.norm(fl.sub(tuple(t), fl.CENTRE))
    z = fl.norm(fl.sub((0.0, 1.0, 0.0), fl.scale(x, x[1])))
    y = fl.cross(z, x)
    return np.array([x, y, z])


def bake(scene, probe_group, region=False):
    """(h, wl, flow) on grid(region): (rows, cols) float32 land height and water level, (rows/2, cols/2, 3) float16 flow
    spread over the water. Cached per .blend file and grid."""
    lam0, dl, cols, phi0, dp, rows, _ = grid(region)
    path = bpy.data.filepath
    key = "%s-%s-%d-%s.npz" % (CACHE_V, os.path.splitext(os.path.basename(path))[0], int(os.path.getmtime(path)) if path else 0,
                                "region%dx%d" % (cols, rows) if region else str(cols))
    cache = os.path.join(CACHE, key)
    if os.path.exists(cache):
        d = np.load(cache)
        if "f" in d:
            return d["h"], d["w"], d["f"]
    A = axes(scene)
    lam = lam0 + (np.arange(cols) + 0.5) * dl
    h_out = np.empty((rows, cols), np.float32)
    w_out = np.empty((rows, cols), np.float32)
    f_out = np.empty((rows, cols, 3), np.float32)
    g = probe_group(bpy.data.objects["Planet_Hydro"])
    me = bpy.data.meshes.new("GT_Probe")
    ob = bpy.data.objects.new("GT_Probe", me)
    scene.collection.objects.link(ob)
    ob.hide_render = True
    ob.modifiers.new("probe", "NODES").node_group = g
    t0 = time.perf_counter()
    step = max(1, (1 << 21) // cols)        # rows per chunk: about 2 M points
    try:
        for r0 in range(0, rows, step):
            r1 = min(rows, r0 + step)
            phi = phi0 + (np.arange(r0, r1) + 0.5) * dp
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
            h_out[r0:r1] = hh.reshape(r1 - r0, cols)
            w_out[r0:r1] = ww.reshape(r1 - r0, cols)
            f_out[r0:r1] = ff.reshape(r1 - r0, cols, 3)
    finally:
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(me)
        bpy.data.node_groups.remove(g)
    t1 = time.perf_counter()
    f_half = half(f_out)
    wet = half((w_out - h_out)[..., None])[..., 0] > 0.0
    f_half = spread(f_half, wet, FLOW_SPREAD / (2.0 * dp * fl.R)).astype(np.float16)
    os.makedirs(CACHE, exist_ok=True)
    np.savez_compressed(cache, h=h_out, w=w_out, f=f_half)
    print("gpu_terrain: %s %dx%d baked in %.1f s, flow spread in %.1f s -> %s" % (
        "region" if region else "map", cols, rows, t1 - t0, time.perf_counter() - t1, cache))
    return h_out, w_out, f_half


def half(x):
    """x (rows, cols, k) at half the resolution: the mean of each 2 x 2 block (odd edges dropped)."""
    r, c = x.shape[0] // 2 * 2, x.shape[1] // 2 * 2
    x = x[:r, :c]
    return 0.25 * (x[0::2, 0::2] + x[1::2, 0::2] + x[0::2, 1::2] + x[1::2, 1::2])


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

    def tex(self, img, lam, phi, region=False):
        tx = self.node("ShaderNodeTexImage", image=img, interpolation="Cubic", extension="EXTEND" if region else "REPEAT")
        if region:
            lam0, dl, cols, phi0, dp, rows, _ = grid(True)
            uv = self.vec(self.math("DIVIDE", self.math("SUBTRACT", lam, lam0), cols * dl),
                          self.math("DIVIDE", self.math("SUBTRACT", phi, phi0), rows * dp), 0.0)
        else:
            uv = self.uv(lam, phi)
        self.feed(tx.inputs["Vector"], uv)
        return tx

    def region_k(self, lam, phi):
        """1 inside the regional map, falling to 0 over REGION_EDGE to its border."""
        lam0, dl, cols, phi0, dp, rows, _ = grid(True)
        e = [self.math("SUBTRACT", lam, lam0), self.math("SUBTRACT", lam0 + cols * dl, lam),
             self.math("SUBTRACT", phi, phi0), self.math("SUBTRACT", phi0 + rows * dp, phi)]
        m = self.math("MINIMUM", self.math("MINIMUM", e[0], e[1]), self.math("MINIMUM", e[2], e[3]))
        return self.smooth(m, 0.0, REGION_EDGE / fl.R)

    def pair(self, M, key, lam, phi):
        """(colour, alpha) of map M[key] at lam, phi, blended to the regional M["r" + key] inside the region."""
        tx = self.tex(M[key], lam, phi)
        col, al = tx.outputs["Color"], tx.outputs["Alpha"]
        if M.get("r" + key) is None:
            return col, al
        rx = self.tex(M["r" + key], lam, phi, region=True)
        k = self.region_k(lam, phi)
        mix = self.node("ShaderNodeMix", data_type="VECTOR", clamp_factor=False)
        ins = {s.identifier: s for s in mix.inputs}
        self.feed(ins["Factor_Float"], k)
        self.feed(ins["A_Vector"], col)
        self.feed(ins["B_Vector"], rx.outputs["Color"])
        return {s.identifier: s for s in mix.outputs}["Result_Vector"], self.lerp(al, rx.outputs["Alpha"], k)

    def lookup(self, M, lam, phi):
        """(land height, water level) of the maps at longitude lam, latitude phi."""
        col, al = self.pair(M, "map", lam, phi)
        sp = self.node("ShaderNodeSeparateColor")
        self.feed(sp.inputs[0], col)
        return self.math("ADD", sp.outputs[0], sp.outputs[1]), self.math("ADD", sp.outputs[2], al)

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

    def detail(self, p, h, w, contact=None):
        """The near noise (m) at world point p on land of height h over water level w; none on a site's pad (contact,
        GT_Flow's alpha)."""
        out = None
        for wave, amp in NOISE:
            nz = self.node("ShaderNodeTexNoise", noise_dimensions="3D")
            nz.inputs["Scale"].default_value = 1.0 / wave
            nz.inputs["Detail"].default_value = 1.0
            self.feed(nz.inputs["Vector"], p)
            term = self.math("MULTIPLY", self.math("SUBTRACT", nz.outputs["Fac"], 0.5), 2.0 * amp)
            term.node.label = "gt_noise_amp"        # review/flicker.py scales it
            out = term if out is None else self.math("ADD", out, term)
        near = self.math("SUBTRACT", 1.0, self.smooth(self.vmath("DISTANCE", p, self.cam()), *NOISE_NEAR))
        dry = self.smooth(self.math("SUBTRACT", h, w), *NOISE_DRY)
        if contact is not None:
            dry = self.math("MULTIPLY", dry, self.math("SUBTRACT", 1.0, self.smooth(contact, 0.0, 0.05)))
        return self.math("MULTIPLY", out, self.math("MULTIPLY", near, dry))


def displacement(nb, M, A, water):
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
    h, w = nb.lookup(M, lam, phi)
    # the next ring's lattice: the even vertices round this one, bilinear
    i0 = nb.math("MULTIPLY", nb.math("FLOOR", nb.math("MULTIPLY", i, 0.5)), 2.0)
    j0 = nb.math("MULTIPLY", nb.math("FLOOR", nb.math("MULTIPLY", j, 0.5)), 2.0)
    fx = nb.math("MULTIPLY", nb.math("SUBTRACT", i, i0), 0.5)
    fy = nb.math("MULTIPLY", nb.math("SUBTRACT", j, j0), 0.5)
    i1, j1 = nb.math("ADD", i0, 2.0), nb.math("ADD", j0, 2.0)
    cs = [nb.lookup(M, *at(a, b)) for a, b in ((i0, j0), (i1, j0), (i0, j1), (i1, j1))]

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
        hv = nb.math("ADD", hland, nb.detail(p0, hland, w, nb.pair(M, "flow", lam, phi)[1]))
    pos = nb.vmath("ADD", tuple(fl.CENTRE), nb.vmath("SCALE", d, scale=nb.math("ADD", hv, fl.R)))
    geo = nb.node("ShaderNodeNewGeometry")         # the object sits at the origin, unrotated: object space = world
    vd = nb.node("ShaderNodeVectorDisplacement", space="OBJECT")
    vd.inputs["Midlevel"].default_value = 0.0
    vd.inputs["Scale"].default_value = 1.0
    nb.feed(vd.inputs["Vector"], nb.vmath("SUBTRACT", pos, geo.outputs["Position"]))
    return vd.outputs[0]


def surface(nb, M, A):
    """Per pixel: the map's height and water level, the flow, and the land's normal from the map's slope and the
    near noise's."""
    geo = nb.node("ShaderNodeNewGeometry")
    up = nb.vmath("NORMALIZE", nb.vmath("SUBTRACT", geo.outputs["Position"], tuple(fl.CENTRE)))
    lam, phi = nb.map_coords(A, up)
    h, w = nb.lookup(M, lam, phi)
    fcol, fal = nb.pair(M, "flow", lam, phi)
    dl = 2.0 * math.pi / W          # one texel, of the regional map inside it
    if M.get("rmap") is not None:
        dl = nb.lerp(dl, REGION_M / fl.R, nb.region_k(lam, phi))
    hx = nb.math("SUBTRACT", nb.lookup(M, nb.math("ADD", lam, dl), phi)[0], nb.lookup(M, nb.math("SUBTRACT", lam, dl), phi)[0])
    hy = nb.math("SUBTRACT", nb.lookup(M, lam, nb.math("ADD", phi, dl))[0], nb.lookup(M, lam, nb.math("SUBTRACT", phi, dl))[0])
    span = nb.math("MULTIPLY", dl, 2.0 * fl.R)
    gx = nb.math("DIVIDE", hx, nb.math("MULTIPLY", span, nb.math("MAXIMUM", nb.math("COSINE", phi), 0.05)))
    gy = nb.math("DIVIDE", hy, span)
    east = nb.frame_vec(A, nb.math("MULTIPLY", nb.math("SINE", lam), -1.0), nb.math("COSINE", lam), 0.0)
    north = nb.frame_vec(A, nb.math("MULTIPLY", nb.math("MULTIPLY", nb.math("SINE", phi), nb.math("COSINE", lam)), -1.0),
                         nb.math("MULTIPLY", nb.math("MULTIPLY", nb.math("SINE", phi), nb.math("SINE", lam)), -1.0), nb.math("COSINE", phi))
    eps = 0.75
    p = geo.outputs["Position"]

    def dnoise(axis):
        pa = nb.detail(nb.vmath("ADD", p, nb.vmath("SCALE", axis, scale=eps)), h, w, fal)
        pb = nb.detail(nb.vmath("SUBTRACT", p, nb.vmath("SCALE", axis, scale=eps)), h, w, fal)
        return nb.math("DIVIDE", nb.math("SUBTRACT", pa, pb), 2.0 * eps)

    gx = nb.math("ADD", gx, dnoise(east))
    gy = nb.math("ADD", gy, dnoise(north))
    n = nb.vmath("NORMALIZE", nb.vmath("SUBTRACT", nb.vmath("SUBTRACT", up, nb.vmath("SCALE", east, scale=gx)),
                                       nb.vmath("SCALE", north, scale=gy)))
    return {"h": h, "w": w, "flow": fcol, "normal": n, "contact": fal}


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


def material(src, name, M, A, water):
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
    nt.links.new(displacement(nb, M, A, water), out.inputs["Displacement"])
    m.displacement_method = "DISPLACEMENT"
    # the overlap: a pixel the finer ring draws is cut from this one
    shader = out.inputs["Surface"].links[0].from_socket
    mix = nb.node("ShaderNodeMixShader")
    nt.links.new(covered(nb, A), mix.inputs["Fac"])
    nt.links.new(shader, mix.inputs[1])
    nt.links.new(nb.node("ShaderNodeBsdfTransparent").outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    sf = surface(nb, M, A)
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
    if not water:       # the land's shade round a site pyramid's foot, under the haze (round 17)
        shade = nb.math("SUBTRACT", 1.0, nb.math("MULTIPLY", sf["contact"], 1.0 - CONTACT_DARK))
        for n in [n for n in nt.nodes if n.type == "GROUP" and n.node_tree and n.node_tree.name == "VJ_Fog"]:
            for lk in list(n.inputs["Color"].links):
                nt.links.new(nb.vmath("SCALE", lk.from_socket, scale=shade), n.inputs["Color"])
    return m


def follow(scene, cam):
    """The camera's map longitude and latitude, for the grids' snapping (flight_rt.frame)."""
    A = _state["axes"]
    if A is None:
        return
    c = A @ np.array(fl.norm(fl.sub(tuple(cam), fl.CENTRE)))
    scene["rt_gt_lam"] = float(math.atan2(c[1], c[0]))
    scene["rt_gt_phi"] = float(math.asin(max(-1.0, min(1.0, c[2]))))


CONTACT = 0.6               # the land's shade round a site pyramid's foot reaches this x its half side
CONTACT_DARK = 0.6          # the land's light right at the foot, against 1 away from it
PAD_SINK = 1.0              # m: the pad under a site pyramid lies this far over its base (the base stays buried)
PAD_EDGE = (20.0, 160.0)    # m past the base edge: level, then blended back into the land (a 60 m blend was lost
#                             on the 48 m cells: 705 of 1355 floated there; 160 m: 165)


def site_base(vs, up):
    """The base square of a site pyramid's vertices: the four over its foundation's (build_planet.unit_pyramid)."""
    order = np.argsort(vs @ up)
    return vs[order[4:8]] if len(vs) > 5 else vs[order[:4]]


def pads(scene, h, A, g=None):
    """(h, contact): h with a level pad under every site pyramid (Planet_Sites' instances): the sites are placed at the land height
    under their centre, and across a base of up to 115 m the land rose or fell by tens of metres, so a pyramid floated
    on one side and was cut by the slope on the other (round 17, review/pyramid_ground.py). Like a real pyramid's
    levelled bedrock, the pad holds the base's height and blends into the land over PAD_EDGE. contact (same shape as h)
    is 1 under a base and falls to 0 at CONTACT x its half side past it: the land's shade at the pyramid's foot.
    g: the map's grid() (default the 12 m map's)."""
    gl0, gdl, _, gp0, gdp, _, wrap = g or grid()
    ob = scene.objects.get("Planet_Sites")
    contact = np.zeros(h.shape, np.float32)
    if ob is None:
        return h, contact
    h0, h = h, h.copy()
    kmax = np.zeros(h.shape, np.float32)       # where pads overlap (a group's pyramids), the nearer footprint wins
    rows, cols = h.shape
    C = np.array(fl.CENTRE, float)
    dg = bpy.context.evaluated_depsgraph_get()
    for inst in dg.object_instances:
        if not (inst.is_instance and inst.parent and inst.parent.name == ob.name):
            continue
        m = np.array(inst.matrix_world.copy())
        if np.linalg.det(m[:3, :3]) <= 0.0:          # the mirrored copy under the sea
            continue
        vs = (m[:3, :3] @ np.array([tuple(v.co) for v in inst.object.data.vertices], float).T).T + m[:3, 3]
        up = vs.mean(0) - C
        up /= np.linalg.norm(up)
        base = site_base(vs, up)
        bc = base.mean(0)
        level = float(np.linalg.norm(bc - C)) - fl.R + PAD_SINK
        e1 = base[0] - bc
        e1 -= up * (e1 @ up)
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(up, e1)
        half = float(np.max(np.abs((base - bc) @ e1))) / math.sqrt(2.0)       # e1 runs along a half diagonal
        rad = half * math.sqrt(2.0) + PAD_EDGE[1]
        c = A @ up
        lam0, phi0 = math.atan2(c[1], c[0]), math.asin(max(-1.0, min(1.0, c[2])))
        x0 = (lam0 - gl0) / gdl - 0.5
        y0 = (phi0 - gp0) / gdp - 0.5
        rx = rad / (fl.R * max(math.cos(phi0), 0.05)) / gdl + 2
        ry = rad / fl.R / gdp + 2
        xs = np.arange(int(x0 - rx), int(x0 + rx) + 2)
        if not wrap:
            xs = xs[(xs >= 0) & (xs < cols)]
        ys = np.arange(max(int(y0 - ry), 0), min(int(y0 + ry) + 2, rows))
        if not len(xs) or not len(ys):
            continue
        L = gl0 + (xs + 0.5) * gdl
        P = gp0 + (ys + 0.5) * gdp
        LL, PP = np.meshgrid(L, P)
        d = np.stack([np.cos(PP) * np.cos(LL), np.cos(PP) * np.sin(LL), np.sin(PP)], -1) @ A
        q = d * fl.R - up * fl.R
        a, b = q @ e1, q @ e2               # along the half diagonals: the base square is |a| + |b| <= half * sqrt 2
        u, v = (a + b) / math.sqrt(2.0), (a - b) / math.sqrt(2.0)
        out = np.maximum(np.abs(u), np.abs(v)) - half
        k = 1.0 - np.clip((out - PAD_EDGE[0]) / (PAD_EDGE[1] - PAD_EDGE[0]), 0.0, 1.0)
        k = k * k * (3.0 - 2.0 * k)
        xi = xs % cols
        ix = np.ix_(ys, xi)
        win = k > kmax[ix]
        h[ix] = np.where(win, h0[ix] + (level - h0[ix]) * k, h[ix])
        kmax[ix] = np.where(win, k, kmax[ix])
        c = 1.0 - np.clip(out / (CONTACT * half), 0.0, 1.0)
        contact[ix] = np.maximum(contact[ix], c * c)
    return h, contact


def maps(scene, probe_group, region):
    """(GT_Map-style RGBA, flow RGBA with the pads' contact in alpha, padded h) of the 12 m map or the regional one."""
    h, wl, f = bake(scene, probe_group, region)
    h, contact = pads(scene, h, _state["axes"], grid(region))
    hc, hf = split(h)
    wc, wf = split(wl)
    c2 = half(contact[..., None])
    return np.stack([hc, hf, wc, wf], -1), np.concatenate([f.astype(np.float32), c2], -1), h


def start(scene, probe_group, region=None):
    region = REGION_ON if region is None else region
    t = time.perf_counter()
    A = _state["axes"] = axes(scene)
    px, fpx, _state["h_padded"] = maps(scene, probe_group, False)
    M = {"map": image("GT_Map", px), "flow": image("GT_Flow", fpx)}
    if region:
        px, fpx, _state["h_region"] = maps(scene, probe_group, True)
        M["rmap"], M["rflow"] = image("GT_Region", px), image("GT_RegionFlow", fpx)
    land, water = make_mesh(LAND), make_mesh(WATER)
    for ob, src, name, wet in ((land, "Terrain", "Terrain GPU", False), (water, "Sea", "Sea GPU", True)):
        ob.data.materials.clear()
        ob.data.materials.append(material(src, name, M, A, wet))
        ob.hide_viewport = ob.hide_render = False
    follow(scene, scene.camera.matrix_world.translation if scene.camera else fl.add(fl.CENTRE, (0.0, 0.0, 1.0), fl.R))
    print("gpu_terrain: started in %.1f s" % (time.perf_counter() - t))


def stop(scene):
    for nm in (LAND, WATER):
        ob = scene.objects.get(nm)
        if ob is not None:
            ob.hide_viewport = ob.hide_render = True
