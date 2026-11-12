"""Procedural planet for the synthwave VJ scene.

A whole planet in Geometry Nodes that replaces the flat island of synthwave_pyramids.blend.
Run it headless, with no other Blender running:

    blender -b --factory-startup --python build_planet.py [-- --out PATH]
        standalone prototype, planet_proto.blend next to this file
    blender -b --factory-startup -Y ../synthwave_pyramids.blend --python build_planet.py -- --graft
        the island scene with the planet grafted in, saved as synthwave_planet.blend next to it

Graft mode keeps everything of the island scene that is not tied to its flat ground: the
runtime (OSC bridge, web page, Syphon, shockwaves, meteors, flamingo flight), the shared
VJ_* shader groups (sky, sun, ray-marched fog bank, haze, colour), sun, corona, moon,
nebula, pyramids, flamingos, render settings and bloom. It removes the island terrain,
sea and far sea, drops pyramids and flamingos onto the planet, pushes sun,
corona and moon out so the orbit shot keeps them in scale, and rebuilds CAM_0..CAM_6 with
the island's roles. Re-run it after the island scene changes to pick the changes up.

- Hydrology (object Planet_Hydro, evaluated once): an icosphere samples the elevation
  noise; sea level is the `Water` quantile of it (Sort Elements), so the ocean covers
  that fraction of the sphere. Shortest Edge Paths drains every land vertex to the
  ocean along low ground; pointer jumping along that tree gives each vertex the highest
  ground on its way to the sea, so depressions fill to their outlet as lakes. Paths
  from sparse springs merge into a river network that runs through the lakes into the
  ocean, smoothed and meandered as curves.
- Land, water and props are cube-sphere patches (6 x 16 x 16) instanced from grids of
  2^level cells. The level falls with the distance to the LOD_Anchor empty, patches
  past the anchor's horizon are dropped, and border vertices snap to the level of
  their edge, so neighbouring patches of any level share one polyline (no cracks).
  The anchor only moves on camera cuts (planet_runtime.py), so between cuts nothing
  is re-evaluated.
- Water reflections: the land within MirrorDistance is mirrored about sea level
  (radius R - h), as the flat scene mirrors it about z = 0; lakes and rivers above sea
  level reflect the sky in their own shader.
- Materials are the island's emission shaders, ported to a sphere: altitude is the
  distance to the sea sphere, "up" is the radial direction, and every vj_* control
  is read through Attribute nodes (VIEW_LAYER) as before.
"""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
GRAFT = "--graft" in ARGS
OUT = ARGS[ARGS.index("--out") + 1] if "--out" in ARGS else (
    os.path.join(os.path.dirname(bpy.data.filepath), "synthwave_planet.blend") if GRAFT else os.path.join(HERE, "planet_proto.blend"))
S = bpy.context.scene

# ================================================================ reset
ISLAND_GROUPS = {g.name: g for g in bpy.data.node_groups}       # graft: the island's shared shader groups
if GRAFT:
    if "Pyramid_A" not in S.objects:
        raise SystemExit("--graft needs the island scene (synthwave_pyramids.blend) open")
    for name in ("Terrain", "Sea", "Sea_Far"):
        if name in S.objects:
            bpy.data.objects.remove(S.objects[name], do_unlink=True)
    for o in [o for o in S.objects if o.name.startswith("CAM_") and o.name != "CAM_OUT"]:
        bpy.data.objects.remove(o, do_unlink=True)
    for name in ("Terrain", "Sea"):
        if name in bpy.data.materials:
            bpy.data.materials.remove(bpy.data.materials[name])
    if "Water Grid" in bpy.data.node_groups:
        bpy.data.node_groups.remove(bpy.data.node_groups["Water Grid"])
    bpy.data.orphans_purge(do_recursive=True)
else:
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    for coll_ in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights,
                  bpy.data.curves, bpy.data.node_groups, bpy.data.texts):
        for d in list(coll_):
            coll_.remove(d)

DEFAULTS = {   # the island's controls, unchanged, so the OSC bridge and the web page keep working
    "vj_level": 0.5, "vj_bass": 0.0, "vj_beat": 0.0,
    "vj_hue": 0.0, "vj_intensity": 1.0, "vj_strobe": 0.0,
    "vj_grid_speed": 0.6, "vj_cam": 0.0, "vj_cam_speed": 1.0,
    "vj_sun": 1.0, "vj_moon": 1.0, "vj_pyramids": 1.0,
    "vj_grid": 1.0, "vj_stars": 1.0, "vj_water": 1.0,
    "vj_night": 0.0, "vj_shock": 0.0,
    "vj_fog": 0.35, "vj_fog_height": 25.0, "vj_fog_glow": 0.6, "vj_fog_hue": 0.0,
    "vj_fog_noise": 0.6, "vj_fog_scale": 260.0, "vj_fog_speed": 10.0, "vj_fog_beat": 0.5,
    "vj_nebula": 1.0, "vj_meteor": 0.0, "vj_flamingos": 1.0, "vj_haze": 1.0, "vj_moon_phase": 1.0,
}
SHOCKS = 4
SHOCK_PROPS = ["rt_shock%d_%s" % (i, f) for i in range(SHOCKS) for f in ("x", "y", "r", "a")]
METEORS = 3
METEOR_PROPS = ["rt_met%d_%s" % (i, f) for i in range(METEORS) for f in ("ax", "ay", "az", "bx", "by", "bz", "s", "l", "a")]
for k, v in DEFAULTS.items():
    if not GRAFT or k not in S:
        S[k] = v
for k in ("rt_time", "rt_cam_phase", "rt_fog_phase", "rt_beat", *SHOCK_PROPS, "rt_shake",
          "rt_flock", "rt_flock_dir", *METEOR_PROPS, "rt_space", "rt_up_x", "rt_up_y", "rt_cam_x", "rt_cam_y", "rt_cam_z"):
    if not GRAFT or k not in S:
        S[k] = 0.0
S["rt_up_z"] = 1.0
PYR_SHADOWS = 4                 # the island's pyramids that cast a sun shadow on the ground (rt_pyr<i>_x/y/z base, a half base, h height)
for i in range(PYR_SHADOWS):
    for f in "xyzah":
        S["rt_pyr%d_%s" % (i, f)] = 0.0
S["rt_fog_clear"] = 180.0       # m: the fog opens this far around the camera (the runtime writes the shot's fog_clear)
S["rt_fog_dip"] = 0.005         # sine of the shot's fog horizon under level (the runtime writes the shot's fog_dip)
S["rt_fog_k"] = 1.0             # the shot's fog strength factor (the runtime writes the shot's fog_k)

# ================================================================ planet
R = 16000.0                    # m, sea-level radius
CENTER = Vector((0.0, 0.0, -R))   # the north pole sits at the origin, where the island was
PATCHES = 32                   # patches per cube face side; a power of two keeps lattice coordinates exact
LMAX = 7                       # finest patch: 2^7 cells per side (about 6 m, within about 200 m of the camera)
PATCH_M = R * math.pi / 2 / PATCHES    # m, patch side on the sphere
JITTER = 0.30                  # cells: each interior patch vertex moves up to this far sideways in a hashed direction,
#                                so the real edges at night form an uneven net instead of a lattice (round 12; under 0.35
#                                no triangle can fold over)
H_MAX = 650.0                  # m, highest terrain (horizon culling, reflection backdrop)
HYDRO_SUBDIV = 7               # hydrology icosphere: 40962 vertices, about 260 m apart
OCEAN_REACH = 3                # rings past the last sea vertex that still carry sea level (the coast comes from the fine terrain)
WATER = 0.40                   # ocean fraction of the sphere
SEED = float(ARGS[ARGS.index("--seed") + 1]) if "--seed" in ARGS else 6.0    # the planet: one seed moves every noise; 6 scored best
# for balance over seeds 0..80 (5 seas, the largest half the water, land spread evenly, 4.7% lakes, 13% mountains, 119 rivers)
SEED_AXIS = (7.31, 3.77, 5.13)   # noise-space offset per seed step
SENTINEL = -10000.0            # "no lake here" in the hydrology water level
VALLEY_SLOPE = 0.3             # river banks rise at most this much per metre away from the water
SHALLOW = 1.0                  # m of water under which the bed still shows (wet, darkened)
RIVER_SHORE = 30.0             # m past the bank where the river surface stays flat (hidden under the bank)
D_SUN = 150000.0               # m, sun distance (far beyond the planet, so the orbit view keeps its size)
D_MOON = 120000.0              # m, moon distance (the island's 21 km, scaled like the sun)
MOON_R = 11500.0               # m, moon radius at vj_moon 1, on star_system.py's 50 km orbit
PLAZA = (130.0, -110.0)        # m from the pole: where the island's pyramids stand
VALLEY_W = (320.0, 900.0)      # m: valley floor half-width (the pyramids stand within 250 m of its axis), blended into the terrain by the outer value
HILLS_M, KNOLLS_M = 70.0, 12.0  # m: rolling hills (1 km across) and little hills (220 m across) on all land away from the coast;
#                                taller knolls left far pyramids floating over the coarser distant land LOD
LAKE_MAX_H = 40.0              # m: no lakes above this: water stays in the low valleys and on the coast (lakes in
#                                the rolling hills stood as flat slabs on the slopes)
VALLEY_KNOLLS = (1.5, 9.0)     # m: little hills on the valley floor, near its axis and at its edge: only ever up from the floor, so no pits
PLAIN_SWELL = (24.0, 320.0)    # m, m across: swells on all land, (noise - 0.5) x 2 x this (about 4 m std), so the drawn
PLAIN_KNOLL = (8.0, 90.0)      # mesh's real edges bend at night; knolls on them, a few cells of the near LOD (round 11:
#                                at half these the plain in front of CAM_0 still read as a lattice)
SHADE_TILT = (2.5, 0.01, 0.06)  # the gentle slopes' light (round 13): the tilt of the land's own normal off its up, times 2.5 for
# the sun and the key below 8 deg of slope, fading to 1 by 20 deg. The plain's 4 to 5 deg swells under a 20 deg sun
# varied the light by about 17 % and read as one flat purple band (CAM_0, CAM_3 by day, rounds 11 and 12)
VALLEY_Y = (-3000.0,)          # m: the valley head; it runs north from there
VALLEY_E, VALLEY_FALL = 4.5, 0.0015    # floor elevation at the pole, fall per metre north: the river runs near sea level and meets the bay about 1.7 km north, as on the island


def coll(name, parent=None):
    c = bpy.data.collections.new(name)
    (parent or S.collection).children.link(c)
    return c


# ================================================================ node helpers
class NT:
    def __init__(self, tree):
        self.t, self.n, self.l = tree, tree.nodes, tree.links
        self.shared = {}     # one Attribute node per name and one node per input-less group: EEVEE pays each once per pixel

    def node(self, kind, **props):
        nd = self.n.new(kind)
        for k, v in props.items():
            setattr(nd, k, v)
        return nd

    def feed(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.l.new(v, sock)
        else:
            if isinstance(v, (tuple, list, Vector)) and sock.type == "VECTOR":
                v = tuple(v)[:3]
            elif isinstance(v, (tuple, list)) and sock.type == "RGBA" and len(v) == 3:
                v = (*v, 1.0)
            sock.default_value = v

    def math(self, op, a, b=0.0, c=None, clamp=False):
        nd = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        self.feed(nd.inputs[0], a)
        self.feed(nd.inputs[1], b)
        if c is not None:
            self.feed(nd.inputs[2], c)
        return nd.outputs[0]

    def mul(self, a, b):
        return self.math("MULTIPLY", a, b)

    def addf(self, a, b):
        return self.math("ADD", a, b)

    def sub(self, a, b):
        return self.math("SUBTRACT", a, b)

    def vmath(self, op, a, b=None, scale=None):
        nd = self.node("ShaderNodeVectorMath", operation=op)
        self.feed(nd.inputs[0], a)
        if b is not None:
            self.feed(nd.inputs[1], b)
        if scale is not None:
            self.feed(nd.inputs["Scale"], scale)
        return nd.outputs["Value"] if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else nd.outputs["Vector"]

    def dot(self, a, b):
        return self.vmath("DOT_PRODUCT", a, b)

    def attr(self, name):
        return self.gattr(name, kind="VIEW_LAYER")

    def gattr(self, name, out="Fac", kind="GEOMETRY"):
        key = (kind, name)
        if key not in self.shared:
            self.shared[key] = self.node("ShaderNodeAttribute", attribute_type=kind, attribute_name=name)
        return self.shared[key].outputs[out]

    def sep(self, vec):
        nd = self.node("ShaderNodeSeparateXYZ")
        self.feed(nd.inputs[0], vec)
        return nd.outputs

    def comb(self, x, y, z):
        nd = self.node("ShaderNodeCombineXYZ")
        for i, v in enumerate((x, y, z)):
            self.feed(nd.inputs[i], v)
        return nd.outputs[0]

    def mrange(self, v, a, b, c, d, clamp=True, interp="LINEAR"):
        nd = self.node("ShaderNodeMapRange", clamp=clamp, interpolation_type=interp)
        for name, val in zip(("Value", "From Min", "From Max", "To Min", "To Max"), (v, a, b, c, d)):
            self.feed(nd.inputs[name], val)
        return nd.outputs["Result"]

    def smooth(self, v, a, b, c=0.0, d=1.0):
        return self.mrange(v, a, b, c, d, interp="SMOOTHSTEP")

    def mix(self, fac, a, b):
        nd = self.node("ShaderNodeMix", data_type="RGBA", blend_type="MIX", clamp_factor=True)
        ins = {s.identifier: s for s in nd.inputs}
        self.feed(ins["Factor_Float"], fac)
        self.feed(ins["A_Color"], a)
        self.feed(ins["B_Color"], b)
        return {s.identifier: s for s in nd.outputs}["Result_Color"]

    def vmix(self, fac, a, b):
        nd = self.node("ShaderNodeMix", data_type="VECTOR", clamp_factor=False)
        ins = {s.identifier: s for s in nd.inputs}
        self.feed(ins["Factor_Float"], fac)
        self.feed(ins["A_Vector"], a)
        self.feed(ins["B_Vector"], b)
        return {s.identifier: s for s in nd.outputs}["Result_Vector"]

    def fmix(self, fac, a, b):
        return self.addf(a, self.mul(self.sub(b, a), fac))

    def ramp(self, fac, stops, interp="LINEAR"):
        nd = self.node("ShaderNodeValToRGB")
        cr = nd.color_ramp
        cr.interpolation = interp
        while len(cr.elements) < len(stops):
            cr.elements.new(0.5)
        for el, (p, col) in zip(cr.elements, stops):
            el.position = p
            el.color = (*col, 1.0)
        self.feed(nd.inputs["Fac"], fac)
        return nd.outputs["Color"]

    def scale(self, col, k):
        return self.vmath("SCALE", col, scale=k)

    def add(self, *cols):
        out = cols[0]
        for c in cols[1:]:
            out = self.vmath("ADD", out, c)
        return out

    def phase(self):
        return self.group(g_phase)

    def group(self, tree, **inputs):
        key = ("GROUP", tree.name)
        if not inputs and not any(it.in_out == "INPUT" for it in tree.interface.items_tree if it.item_type == "SOCKET"):
            if key not in self.shared:
                self.shared[key] = self.group_node(tree)
            return self.shared[key].outputs
        nd = self.group_node(tree)
        for k, v in inputs.items():
            self.feed(nd.inputs[k], v)
        return nd.outputs

    def group_node(self, tree):
        nd = self.node("GeometryNodeGroup" if tree.bl_idname == "GeometryNodeTree" else "ShaderNodeGroup")
        nd.node_tree = tree
        return nd

    # --- geometry nodes
    def pos(self):
        return self.node("GeometryNodeInputPosition").outputs[0]

    def index(self):
        return self.node("GeometryNodeInputIndex").outputs[0]

    def read(self, name, dtype="FLOAT"):
        nd = self.node("GeometryNodeInputNamedAttribute", data_type=dtype)
        nd.inputs["Name"].default_value = name
        return nd.outputs["Attribute"]

    def store(self, geo, name, value, dtype="FLOAT", domain="POINT"):
        nd = self.node("GeometryNodeStoreNamedAttribute", data_type=dtype, domain=domain)
        self.feed(nd.inputs["Geometry"], geo)
        nd.inputs["Name"].default_value = name
        self.feed(nd.inputs["Value"], value)
        return nd.outputs["Geometry"]

    def setpos(self, geo, position=None, offset=None, sel=None):
        nd = self.node("GeometryNodeSetPosition")
        self.feed(nd.inputs["Geometry"], geo)
        for k, v in (("Position", position), ("Offset", offset), ("Selection", sel)):
            if v is not None:
                self.feed(nd.inputs[k], v)
        return nd.outputs[0]

    def delete(self, geo, sel, domain="POINT"):
        nd = self.node("GeometryNodeDeleteGeometry", domain=domain)
        self.feed(nd.inputs["Geometry"], geo)
        self.feed(nd.inputs["Selection"], sel)
        return nd.outputs[0]

    def sample(self, geo, value, index, dtype="FLOAT_VECTOR", domain="POINT"):
        nd = self.node("GeometryNodeSampleIndex", data_type=dtype, domain=domain)
        self.feed(nd.inputs["Geometry"], geo)
        self.feed(nd.inputs["Value"], value)
        self.feed(nd.inputs["Index"], index)
        return nd.outputs[0]

    def at(self, value, index, dtype="FLOAT", domain="POINT"):
        nd = self.node("GeometryNodeFieldAtIndex", data_type=dtype, domain=domain)
        self.feed(nd.inputs["Value"], value)
        self.feed(nd.inputs["Index"], index)
        return nd.outputs[0]

    def join(self, *geos):
        nd = self.node("GeometryNodeJoinGeometry")
        for g in geos:
            self.feed(nd.inputs[0], g)
        return nd.outputs[0]

    def transform(self, geo, t=(0, 0, 0), r=(0, 0, 0), s=(1, 1, 1)):
        nd = self.node("GeometryNodeTransform")
        self.feed(nd.inputs["Geometry"], geo)
        self.feed(nd.inputs["Translation"], t)
        self.feed(nd.inputs["Rotation"], r)
        self.feed(nd.inputs["Scale"], s)
        return nd.outputs[0]

    def noise(self, vec, detail, rough=0.5):
        nd = self.node("ShaderNodeTexNoise", noise_dimensions="3D", normalize=True)
        self.feed(nd.inputs["Vector"], vec)
        nd.inputs["Scale"].default_value = 1.0
        nd.inputs["Detail"].default_value = detail
        nd.inputs["Roughness"].default_value = rough
        return nd.outputs["Fac"]


def make_group(name, inputs, outputs, kind="ShaderNodeTree"):
    g = bpy.data.node_groups.new(name, kind)
    for n, t, dv in inputs:
        s = g.interface.new_socket(n, in_out="INPUT", socket_type=t)
        if dv is not None:
            s.default_value = dv
    for n, t in outputs:
        g.interface.new_socket(n, in_out="OUTPUT", socket_type=t)
    T = NT(g)
    return g, T, T.node("NodeGroupInput").outputs, T.node("NodeGroupOutput").inputs


def gn_group(name, inputs, outputs):
    return make_group(name, inputs, outputs, "GeometryNodeTree")


def direction(az_deg, el_deg):
    az, el = math.radians(az_deg), math.radians(el_deg)
    return Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))


# ================================================================ sky model (the island's, plus rt_space: from high up the sky turns to space)
SUN_R = (0.18, 0.30)
MOON_C = direction(30.0, 22.0)
FOG_D = 6500.0
FOG_TOP = 800.0                # m over the sea: the fog box's top (the fog lies on valley floors up to a few hundred m)
FOG_TAIL = 0.06                # haze over the fog layer's top, as a share of its density
FOG_TAIL_NIGHT = (0.12, 4.0)   # at night: its share and its height in layer tops (round 13; 0.3 and 6 filled the mid and far
# sky with purple haze at fog 1 seen from high up, CAM_4 night f1, round 9)
FOG_NIGHT_ALB = (0.055, 0.055, 0.06)   # the night fog's albedo, near neutral under the blue moon light (0.06, 0.05, 0.08 read purple)
FOG_DENSITY = 0.005            # volume fog density at /vj/fog 1 on a valley floor: about 600 m of sight; it grows as /vj/fog^1.5
FOG_RAMP = [(0.0, (1.0, 0.25, 0.65)), (0.33, (0.55, 0.20, 1.0)), (0.66, (0.15, 0.75, 1.0)), (1.0, (1.0, 0.25, 0.65))]   # fog colour by vj_fog_hue
FOG_CLEAR = 0.25               # the fog fades in from this fraction of the shot's clear distance (rt_fog_clear) to all of it

FOG_FLOOR = bpy.data.images.new("Fog_Floor", 768, 384, float_buffer=True, alpha=False)   # filled by fill_fog_floor
FOG_FLOOR.colorspace_settings.name = "Non-Color"


def fog_floor(T, pos):
    """The valley floor under pos, in m over the sea: the hydrology's ground (the sea at 0), its low envelope over about
    800 m, smoothed (fill_fog_floor). An equirectangular map about the spin axis +x, so the shots lie off its poles."""
    dx, dy, dz = T.sep(T.vmath("NORMALIZE", T.vmath("SUBTRACT", pos, tuple(CENTER))))
    u = T.addf(T.math("DIVIDE", T.math("ARCTAN2", dz, dy), 2 * math.pi), 0.5)
    v = T.addf(T.math("DIVIDE", T.math("ARCSINE", T.math("MINIMUM", T.math("MAXIMUM", dx, -1.0), 1.0)), math.pi), 0.5)
    tex = T.node("ShaderNodeTexImage", interpolation="Linear", extension="REPEAT")
    tex.image = FOG_FLOOR
    T.feed(tex.inputs["Vector"], T.comb(u, v, 0.0))
    return T.sep(tex.outputs["Color"])[0]


def fog_top(T, roll):
    """The fog layer's top over its valley floor, in m: vj_fog_height (25 m) thick at /vj/fog 1, rolling with roll (a
    0..1 noise, 0.5 for its mean) between 0.4 and 1.6 of that, and 0.7 of it at /vj/fog 0.5."""
    fog_ = T.math("MINIMUM", T.math("MAXIMUM", T.attr("vj_fog"), 0.0), 1.0)
    return T.mul(T.mul(T.math("MAXIMUM", T.attr("vj_fog_height"), 1.0), T.addf(0.4, T.mul(roll, 1.2))), T.addf(0.4, T.mul(fog_, 0.6)))


def fog_layer(T, h, top, tail_k=1.0):
    """The fog's density share at h m over its valley floor: a layer full up to half its top, thinning to its top, and
    a thin haze above (times tail_k). An exponential over height was one smooth gradient with no top, which swallowed
    the pyramids (CAM_0 f1) and laid flat milky bands over rivers and the sea (round 3)."""
    over = T.math("MAXIMUM", T.sub(h, top), 0.0)
    # at night a thicker, higher haze: dark, it shows only where a capstone lamp lights it. A tall pyramid's capstone
    # stood over the layer with nothing to light (CAM_2)
    night_ = T.phase()["Night"]
    tail = T.mul(T.math("EXPONENT", T.math("DIVIDE", over, T.mul(top, T.fmix(night_, -2.0, -FOG_TAIL_NIGHT[1])))),
                 T.fmix(night_, FOG_TAIL, FOG_TAIL_NIGHT[0]))
    # thinning from a quarter of its top to a quarter over it: full to half its top, the layer's edge was sharp enough
    # for the volume's depth slices to draw it as stepped terraces seen from high up (CAM_4 f1, round 7)
    return T.addf(T.smooth(h, T.mul(top, 1.25), T.mul(top, 0.25)), T.mul(tail, tail_k))


def fog_look(T):
    """The fog's colour by the time of day, after reference_fog/: white by day, the poster's pink and gold at sunset
    (its only own glow), near black at night, where only lights show it (capstone lamps, the moon, the neon below).
    Returns (albedo, own glow colour, radiance of thick fog for the water's analytic fog)."""
    ph = T.phase()
    fc = T.ramp(T.math("FRACT", T.attr("vj_fog_hue")), FOG_RAMP)
    dusk_c = T.mix(0.45, fc, (1.0, 0.62, 0.40))
    alb = T.mix(ph["Night"], T.mix(ph["Twilight"], (0.92, 0.90, 0.98), dusk_c), FOG_NIGHT_ALB)
    glow = T.scale(fc, T.mul(T.mul(T.attr("vj_fog_glow"), ph["Twilight"]), T.sub(1.0, ph["Night"])))
    rad = T.mix(ph["Night"], T.mix(ph["Twilight"], (0.80, 0.80, 0.90), T.add(T.scale(dusk_c, 0.55), T.scale(glow, 0.6))), (0.004, 0.0035, 0.008))
    return alb, glow, rad
PALM_CLEAR = 90.0              # m: no palm grove this close to a set's anchor (the camera of a fixed shot)
FLOCK_NEAR = 3000.0            # m: flamingo flocks stand in shallows this close to a pyramid group
FLOCK_DENSITY = 24.0           # candidate flock spots per km2 around the shot (shallows are thin strips)
FLOCK_SIZE = (16, 48)          # birds per flock, smallest and largest
MIRROR_REACH = 1800.0      # m from the camera within which the land's mirror copy shows (reflections in the sea)

ATMO_SHELL = 1500.0        # m, the canvas shell the limb glow is drawn on (the glow itself fades out within a few pixels)
ATMO_H = 6000.0            # m, haze only builds up inside this shell, so the orbit view is not washed out
RIVER_SPEED = 2.6
FLOW_CYCLE = 3.5
MW_N = tuple(Vector((0.45, -0.30, 0.84)).normalized())
# the real sky: NASA SVS Deep Star Maps 2020 (svs.gsfc.nasa.gov/4851, public domain; NASA/Goddard Space Flight Center
# Scientific Visualization Studio), plate carree in J2000 celestial coordinates, linear. Not in the repo: starmaps/
# next to this script, "--stars 16k" for the larger one. A dark sky with contrast (S6): a black point over the faint-star
# field, then a square curve on luminance (colours kept), so the empty sky is black, the naked-eye stars (0.2 to 1.0 in
# the map) stand out as points and the Milky Way (0.02 to 0.05) stays a subtle glow with its dust lanes. A linear gain
# over a 0.0012 black point lifted the faint field (0.005 to 0.03) into a grey speckled veil (user: "too bright")
STAR_RES = ARGS[ARGS.index("--stars") + 1] if "--stars" in ARGS else "8k"
STAR_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "starmaps", "starmap_2020_%s.exr" % STAR_RES)
STAR_BLACK, STAR_K = 0.002, 3.0
NEB_LO, NEB_HI, NEB_K = 0.006, 0.03, 0.35     # the Milky Way band (space_sky): texel luminance where it fades in, its gain
STAR_INTERP = "Cubic"    # (round 13) Linear drew an 8k texel as a square at 200 mm (the orbit limb); at 24 mm the same points
STAR_IMG = bpy.data.images.load(STAR_PATH, check_existing=True)     # referenced, not packed (124 or 423 MB)
STAR_IMG.use_half_precision = True       # a half-float GPU texture: the map itself is half float
STAR_CAP = math.radians(35.0)    # (20 deg left the plate carree's sideways stretch, 1/cos(declination), up to 3x at
# 70 deg: stars smeared into elongated blobs in the limb close-up, round 6; now at most 1.7x)


def star_caps(n=1792):     # about the map's own 0.044 deg per texel over the 35 deg cap
    """The star map's two polar caps (within STAR_CAP of each celestial pole), north and south side by side, in an
    orthographic azimuthal projection (radius sin(colatitude) / sin(STAR_CAP)). The plate carree map pinches each
    pole to a point, and its texture filter smeared the stars there into a radial starburst (CAM_4 at night, S6).
    Made once from the map and kept next to it."""
    path = STAR_PATH[:-4] + "_caps%d.exr" % round(math.degrees(STAR_CAP))
    if not os.path.exists(path) or os.path.getmtime(path) < os.path.getmtime(STAR_PATH):
        w_, h_ = STAR_IMG.size
        src = np.empty(w_ * h_ * 4, dtype=np.float32)
        STAR_IMG.pixels.foreach_get(src)
        src = src.reshape(h_, w_, 4)
        ys, xs = np.mgrid[0:n, 0:n]
        x, y = (xs + 0.5) / n * 2.0 - 1.0, (ys + 0.5) / n * 2.0 - 1.0
        colat = np.arcsin(np.clip(np.hypot(x, y) * math.sin(STAR_CAP), 0.0, 1.0))
        ra = np.arctan2(y, x)
        out = np.zeros((n, 2 * n, 4), dtype=np.float32)
        for k_, sign in ((0, 1.0), (1, -1.0)):
            u = ((0.5 - ra / (2 * math.pi)) % 1.0) * w_ - 0.5
            v = (0.5 + sign * (math.pi / 2 - colat) / math.pi) * h_ - 0.5
            u0, v0 = np.floor(u).astype(np.int64), np.floor(v).astype(np.int64)
            fu, fv = (u - u0)[..., None], (v - v0)[..., None]
            u1, v1 = (u0 + 1) % w_, np.clip(v0 + 1, 0, h_ - 1)
            u0, v0 = u0 % w_, np.clip(v0, 0, h_ - 1)
            out[:, k_ * n:(k_ + 1) * n] = (src[v0, u0] * (1 - fu) * (1 - fv) + src[v0, u1] * fu * (1 - fv)
                                           + src[v1, u0] * (1 - fu) * fv + src[v1, u1] * fu * fv)
        out[..., 3] = 1.0
        img = bpy.data.images.new("starmap_caps_new", 2 * n, n, float_buffer=True, alpha=True)
        img.pixels.foreach_set(out.ravel())
        img.filepath_raw = path
        img.file_format = "OPEN_EXR"
        img.save()
        bpy.data.images.remove(img)
    cap = bpy.data.images.load(path, check_existing=True)
    cap.use_half_precision = True
    return cap


STAR_CAPS = star_caps()
STAR_BG_K = 1.0                 # (round 13) at /vj/nebula 0 the stars less this share of the map's blurred light: the core's
# diffuse glow, under the lum^2 gain, read as a glow band with the nebula off (CAM_10 neb0, round 9). A cut on texel
# luminance took every star point with it; this keeps the points that stand above their surroundings


def star_bg(w=1024, passes=3):
    """The star map's diffuse light: block means to w x w/2 texels, then `passes` box blurs 3 texels wide (wrapping
    round in right ascension). Made once from the map and kept next to it."""
    path = STAR_PATH[:-4] + "_bg%d.exr" % w
    if not os.path.exists(path) or os.path.getmtime(path) < os.path.getmtime(STAR_PATH):
        w_, h_ = STAR_IMG.size
        src = np.empty(w_ * h_ * 4, dtype=np.float32)
        STAR_IMG.pixels.foreach_get(src)
        k = w_ // w
        out = src.reshape(h_ // k, k, w, k, 4).mean(axis=(1, 3))
        del src
        for _ in range(passes):
            out = (np.roll(out, 1, axis=1) + out + np.roll(out, -1, axis=1)) / 3.0
            pad = np.concatenate([out[:1], out, out[-1:]], axis=0)
            out = (pad[:-2] + pad[1:-1] + pad[2:]) / 3.0
        out[..., 3] = 1.0
        img = bpy.data.images.new("starmap_bg_new", w, out.shape[0], float_buffer=True, alpha=True)
        img.pixels.foreach_set(np.ascontiguousarray(out, dtype=np.float32).ravel())
        img.filepath_raw = path
        img.file_format = "OPEN_EXR"
        img.save()
        bpy.data.images.remove(img)
    bg = bpy.data.images.load(path, check_existing=True)
    bg.use_half_precision = True
    return bg


STAR_BG = star_bg()

g_phase, T, gi, go = make_group("VJ_Phase", [], [("Dusk", "NodeSocketFloat"), ("Twilight", "NodeSocketFloat"), ("Night", "NodeSocketFloat")])
nv = T.attr("vj_night")
dusk = T.smooth(nv, 0.0, 0.5)
nightf = T.smooth(nv, 0.5, 1.0)
T.feed(go["Dusk"], dusk)
T.feed(go["Night"], nightf)
T.feed(go["Twilight"], T.mul(dusk, T.math("SUBTRACT", 1.0, nightf)))

# --- VJ_SkyPhase: VJ_Phase for the sky only; rt_space (camera altitude) reads as night, without twilight
g_skyph, T, gi, go = make_group("VJ_SkyPhase", [], [("Dusk", "NodeSocketFloat"), ("Twilight", "NodeSocketFloat"), ("Night", "NodeSocketFloat")])
ph, sp = T.phase(), T.attr("rt_space")
T.feed(go["Dusk"], ph["Dusk"])
T.feed(go["Night"], T.math("MAXIMUM", ph["Night"], sp))
T.feed(go["Twilight"], T.mul(ph["Twilight"], T.sub(1.0, sp)))

# --- VJ_Frame: the sky's frame. On the flat island z was up everywhere; on the planet the runtime
#     writes the shot's radial up (rt_up_*) at every camera cut, and sky, sun and haze turn with it.
g_frame, T, gi, go = make_group("VJ_Frame", [], [("Up", "NodeSocketVector"), ("North", "NodeSocketVector"), ("East", "NodeSocketVector")])
upv = T.vmath("NORMALIZE", T.comb(T.attr("rt_up_x"), T.attr("rt_up_y"), T.attr("rt_up_z")))
north = T.vmath("NORMALIZE", T.vmath("SUBTRACT", (0.0, 1.0, 0.0), T.vmath("SCALE", upv, scale=T.sep(upv)[1])))
T.feed(go["Up"], upv)
T.feed(go["North"], north)
T.feed(go["East"], T.vmath("CROSS_PRODUCT", north, upv))


def to_local(T, v):
    fr = T.group(g_frame)
    return T.comb(T.dot(v, fr["East"]), T.dot(v, fr["North"]), T.dot(v, fr["Up"]))


def to_world(T, v):
    fr = T.group(g_frame)
    x_, y_, z_ = T.sep(v)
    return T.add(T.scale(fr["East"], x_), T.scale(fr["North"], y_), T.scale(fr["Up"], z_))


g_sun, T, gi, go = make_group("VJ_SunDir", [], [("Dir", "NodeSocketVector"), ("Up", "NodeSocketVector"), ("Day", "NodeSocketFloat")])
sun_amt = T.mul(T.attr("vj_sun"), T.math("SUBTRACT", 1.0, T.phase()["Dusk"]))
el = T.mrange(sun_amt, 0, 1, -0.24, 0.16)
ce, se = T.math("COSINE", el), T.math("SINE", el)
fr = T.group(g_frame)
T.feed(go["Dir"], T.add(T.scale(fr["North"], ce), T.scale(fr["Up"], se)))          # world space
T.feed(go["Up"], T.add(T.scale(fr["North"], T.mul(se, -1.0)), T.scale(fr["Up"], ce)))
T.feed(go["Day"], T.smooth(el, -0.16, 0.06))
g_sun.interface.new_socket("Local Dir", in_out="OUTPUT", socket_type="NodeSocketVector")   # in the sky frame
T.feed(T.n["Group Output"].inputs["Local Dir"], T.comb(0.0, ce, se))
for name, val in (("Amount", sun_amt), ("Radius", T.smooth(sun_amt, 0.3, 1.0, *SUN_R)),
                  ("Moon", T.math("SUBTRACT", 1.0, T.smooth(sun_amt, 0.3, 0.85)))):
    g_sun.interface.new_socket(name, in_out="OUTPUT", socket_type="NodeSocketFloat")
    T.feed(T.n["Group Output"].inputs[name], val)

g_base, T, gi, go = make_group("VJ_SkyBase", [("Direction", "NodeSocketVector", None)], [("Color", "NodeSocketColor")])   # Direction in the sky frame


def fill_sky_base(g):
    """A real sky: an even pastel blue by day (paler toward the horizon, a warm white glow around the sun),
    the synthwave sunset only at twilight, near black at night and from space."""
    for n in list(g.nodes):
        g.nodes.remove(n)
    T = NT(g)
    gi, go = T.node("NodeGroupInput").outputs, T.node("NodeGroupOutput").inputs
    d = T.vmath("NORMALIZE", gi["Direction"])
    dx, dy, z = T.sep(d)
    sun, ph = T.group(g_sun), T.group(g_skyph)
    lvl = T.attr("vj_level")
    ang = T.math("ARCCOSINE", T.math("MINIMUM", T.dot(d, sun["Local Dir"]), 1.0))
    near_sun = T.math("POWER", T.mrange(ang, sun["Radius"], T.mul(sun["Radius"], 1.35), 1, 0), 2.0)    # the stylized sun is huge: keep its glow tight
    halo = T.mul(T.math("POWER", T.mrange(ang, sun["Radius"], T.mul(sun["Radius"], 4.0), 1, 0), 2.0), sun["Amount"])
    dayc = T.ramp(T.mrange(z, -0.02, 0.6, 0, 1), [(0.00, (0.58, 0.74, 1.00)), (0.15, (0.42, 0.62, 1.00)), (1.00, (0.20, 0.40, 0.90))])
    dayc = T.add(dayc, T.scale((1.0, 0.86, 0.80), T.mul(T.mul(near_sun, sun["Amount"]), T.addf(0.14, T.mul(lvl, 0.12)))))
    # the synthwave sunset poster: hot orange on the horizon under the sun, through pink and magenta to violet and
    # navy overhead; away from the sun the same bands in violet
    warm = T.ramp(T.mrange(z, 0.0, 0.8, 0, 1), [
        (0.00, (1.00, 0.55, 0.14)), (0.04, (1.00, 0.28, 0.22)), (0.11, (0.98, 0.13, 0.42)), (0.24, (0.60, 0.09, 0.60)),
        (0.45, (0.22, 0.05, 0.42)), (1.00, (0.025, 0.018, 0.11))])
    cool = T.ramp(T.mrange(z, 0.0, 0.8, 0, 1), [
        (0.00, (0.62, 0.17, 0.55)), (0.10, (0.40, 0.10, 0.52)), (0.35, (0.13, 0.05, 0.32)), (1.00, (0.02, 0.015, 0.09))])
    sx, sy, _ = T.sep(sun["Local Dir"])
    toward = T.dot(T.vmath("NORMALIZE", T.comb(dx, dy, 0.0)), T.vmath("NORMALIZE", T.comb(sx, sy, 0.0)))
    twc = T.mix(T.smooth(toward, -0.6, 0.85), cool, warm)
    glow = T.mul(T.mrange(z, 0.0, 0.09, 1, 0), T.addf(0.2, T.mul(lvl, 0.8)))
    twc = T.add(twc, T.scale((1.0, 0.22, 0.6), T.mul(glow, 0.35)), T.scale((1.0, 0.30, 0.42), T.mul(halo, T.addf(0.55, T.mul(lvl, 0.9)))))
    col = T.mix(ph["Twilight"], dayc, twc)
    nightc = T.ramp(T.mrange(z, 0.0, 0.3, 0, 1), [(0.00, (0.035, 0.012, 0.07)), (0.35, (0.008, 0.004, 0.02)),
                                                 (1.00, (0.0008, 0.0008, 0.002))])     # a faint violet glow under black silhouettes
    T.feed(go["Color"], T.mix(ph["Night"], col, nightc))


def stars_in_the_dark(g):
    """VJ_Sky's star layer shines by day at 3.5: a real day sky has none. Scaled by night and twilight."""
    T = NT(g)
    base = next((n for n in T.n if n.type == "MATH" and n.operation == "ADD" and not n.inputs[0].is_linked
                 and abs(n.inputs[0].default_value - 3.5) < 1e-4), None)
    if base is None or not base.outputs[0].links:
        print("PLANET warning: VJ_Sky star term not found, stars stay as they are")
        return
    tail = base.outputs[0].links[0].to_node            # 3.5 + 10 night (+ 4 beat)
    ph = T.group(g_skyph)
    dark = T.math("MAXIMUM", ph["Night"], T.mul(ph["Twilight"], 0.6))
    for ln in list(tail.outputs[0].links):
        T.l.new(T.mul(tail.outputs[0], dark), ln.to_socket)


g_met, T, gi, go = make_group("VJ_Meteor", [("Direction", "NodeSocketVector", None), ("A", "NodeSocketVector", None), ("B", "NodeSocketVector", None),
                                            ("Head", "NodeSocketFloat", 0.0), ("Length", "NodeSocketFloat", 0.0), ("Amount", "NodeSocketFloat", 0.0)],
                              [("Color", "NodeSocketColor")])
d = T.vmath("NORMALIZE", gi["Direction"])
C_ = T.vmath("CROSS_PRODUCT", gi["A"], gi["B"])
s_ = T.math("ARCTAN2", T.dot(d, gi["B"]), T.dot(d, gi["A"]))
perp = T.dot(d, C_)
ds = T.math("SUBTRACT", gi["Head"], s_)
u = T.math("DIVIDE", ds, T.math("MAXIMUM", gi["Length"], 0.001))
inside = T.mul(T.math("GREATER_THAN", u, 0.0), T.math("LESS_THAN", u, 1.0))
tail = T.math("POWER", T.math("SUBTRACT", 1.0, T.math("MINIMUM", T.math("MAXIMUM", u, 0.0), 1.0)), 2.2)
w = T.mul(T.addf(0.35, T.mul(tail, 0.65)), 0.0017)
core = T.math("EXPONENT", T.mul(T.math("POWER", T.math("DIVIDE", perp, w), 2.0), -1.0))
streak = T.mul(T.mul(core, tail), inside)
head = T.math("EXPONENT", T.mul(T.math("DIVIDE", T.addf(T.mul(ds, ds), T.mul(perp, perp)), 0.0032 ** 2), -1.0))
tc = T.ramp(u, [(0.0, (0.75, 0.95, 1.0)), (0.35, (0.45, 0.55, 1.0)), (1.0, (1.0, 0.15, 0.75))])
T.feed(go["Color"], T.scale(T.add(T.scale(tc, T.mul(streak, 5.0)), T.scale((1.0, 0.95, 1.0), T.mul(head, 14.0))), gi["Amount"]))

g_sky, T, gi, go = make_group("VJ_Sky", [("Direction", "NodeSocketVector", None)], [("Color", "NodeSocketColor")])   # Direction in world space
d = T.vmath("NORMALIZE", to_local(T, gi["Direction"]))
dx, dy, dz = T.sep(d)
spc = T.attr("rt_space")
below = T.mul(T.math("LESS_THAN", dz, 0.0), T.sub(1.0, spc))      # from space there is no sea horizon: the sky is space all round
az_ = T.fmix(spc, T.math("ABSOLUTE", dz), 1.0)
rip = T.node("ShaderNodeTexNoise")
T.feed(rip.inputs["Vector"], T.comb(T.mul(dx, 3.0), T.mul(az_, 420.0), T.mul(T.attr("rt_time"), 0.35)))
rip.inputs["Scale"].default_value = 1.0
rip.inputs["Detail"].default_value = 2.0
wob = T.mul(T.mul(T.math("SUBTRACT", rip.outputs["Fac"], 0.5), T.mrange(az_, 0.0, 0.25, 0.10, 0.03)), below)
col = T.group(g_base, Direction=T.comb(dx, dy, T.addf(az_, wob)))["Color"]
dm = T.comb(dx, dy, T.addf(T.fmix(spc, T.math("ABSOLUTE", dz), dz), wob))   # stars: mirrored below the horizon, the true direction in space
vor = T.node("ShaderNodeTexVoronoi", voronoi_dimensions="3D", feature="F1")
T.feed(vor.inputs["Vector"], dm)
vor.inputs["Scale"].default_value = 240.0
ph = T.group(g_skyph)
star = T.math("POWER", T.mrange(vor.outputs["Distance"], 0.0, T.addf(0.09, T.mul(ph["Night"], 0.05)), 1, 0), 3.0)
rnd = T.sep(vor.outputs["Color"])
tw = T.mrange(T.math("SINE", T.addf(T.mul(T.attr("rt_time"), 2.5), T.mul(rnd[0], 60.0))), -1, 1, 0.25, 1.0)
star = T.mul(T.mul(star, tw), T.addf(0.3, rnd[1]))
smask = T.mul(T.mrange(az_, 0.05, 0.3, 0, 1), T.attr("vj_stars"))
star = T.mul(T.mul(star, smask), T.addf(T.addf(3.5, T.mul(ph["Night"], 10.0)), T.mul(T.attr("rt_beat"), 4.0)))
col = T.add(col, T.scale((0.85, 0.85, 1.0), star))
nk = T.mul(T.math("MAXIMUM", ph["Night"], T.mul(ph["Twilight"], 0.3)), T.attr("vj_stars"))
hz = T.mrange(az_, 0.01, 0.12, 0, 1)
band = T.math("EXPONENT", T.mul(T.math("POWER", T.math("DIVIDE", T.dot(dm, MW_N), 0.13), 2.0), -1.0))
cl = T.node("ShaderNodeTexNoise")
T.feed(cl.inputs["Vector"], dm)
cl.inputs["Scale"].default_value = 3.0
cl.inputs["Detail"].default_value = 7.0
cl.inputs["Roughness"].default_value = 0.62
dust = T.node("ShaderNodeTexNoise")
T.feed(dust.inputs["Vector"], T.vmath("SCALE", dm, scale=2.3))
dust.inputs["Scale"].default_value = 4.0
dust.inputs["Detail"].default_value = 6.0
lanes = T.mrange(dust.outputs["Fac"], 0.48, 0.62, 1.0, 0.15)
mw = T.mul(T.mul(band, T.math("POWER", T.mrange(cl.outputs["Fac"], 0.35, 0.75, 0.05, 1.0), 1.6)), lanes)
mwc = T.ramp(cl.outputs["Fac"], [(0.3, (0.35, 0.05, 0.85)), (0.55, (0.75, 0.30, 1.0)), (0.75, (0.10, 0.60, 1.0))])
col = T.add(col, T.scale(mwc, T.mul(T.mul(mw, 0.30), T.mul(nk, hz))))
neb = T.node("ShaderNodeTexNoise")
T.feed(neb.inputs["Vector"], T.vmath("ADD", dm, (3.1, 1.7, 0.4)))
neb.inputs["Scale"].default_value = 1.6
neb.inputs["Detail"].default_value = 5.0
nebm = T.math("POWER", T.mrange(neb.outputs["Fac"], 0.58, 0.82, 0.0, 1.0), 3.0)
nebc = T.ramp(T.sep(neb.outputs["Color"])[0], [(0.3, (1.0, 0.05, 0.55)), (0.7, (0.0, 0.65, 0.90))])
col = T.add(col, T.scale(nebc, T.mul(T.mul(nebm, 0.14), T.mul(nk, hz))))
vor2 = T.node("ShaderNodeTexVoronoi", voronoi_dimensions="3D", feature="F1")
T.feed(vor2.inputs["Vector"], dm)
vor2.inputs["Scale"].default_value = 800.0
st2 = T.math("POWER", T.mrange(vor2.outputs["Distance"], 0.0, 0.11, 1, 0), 4.0)
st2 = T.mul(st2, T.math("POWER", T.sep(vor2.outputs["Color"])[2], 3.0))
st2 = T.mul(st2, T.mul(T.addf(0.35, T.mul(band, 3.0)), T.mul(T.mul(nk, hz), 14.0)))
col = T.add(col, T.scale((0.8, 0.85, 1.0), st2))
metk = T.mul(T.mul(T.addf(0.45, T.mul(ph["Night"], 0.55)), T.mrange(az_, 0.0, 0.04, 0, 1)), T.attr("vj_stars"))
for i in range(METEORS):
    a_ = lambda f: T.attr("rt_met%d_%s" % (i, f))
    mc = T.group(g_met, Direction=dm, A=T.comb(a_("ax"), a_("ay"), a_("az")), B=T.comb(a_("bx"), a_("by"), a_("bz")),
                 Head=a_("s"), Length=a_("l"), Amount=a_("a"))["Color"]
    col = T.add(col, T.scale(mc, metk))
streak = T.node("ShaderNodeTexNoise")
T.feed(streak.inputs["Vector"], T.comb(T.mul(dx, 1.5), T.addf(T.mul(az_, 1100.0), T.mul(T.attr("rt_time"), 0.8)), 0.0))
streak.inputs["Scale"].default_value = 1.0
streak.inputs["Detail"].default_value = 1.0
refl = T.mul(T.mrange(az_, 0.0, 0.25, 0.85, 0.5), T.mrange(streak.outputs["Fac"], 0.38, 0.55, 0.35, 1.0))
col = T.scale(col, T.mix(below, (1, 1, 1), T.comb(refl, refl, refl)))
T.feed(go["Color"], col)


def planet_frame(T, pos):
    """Radial up and altitude above the sea sphere."""
    rel = T.vmath("SUBTRACT", pos, tuple(CENTER))
    return T.vmath("NORMALIZE", rel), T.math("SUBTRACT", T.vmath("LENGTH", rel), R)


def horizon_dip(T):
    """The camera (rt_cam_*), its radial up and the sine of its horizon's dip: the visible horizon lies
    acos(R / (R + h)) below level from h metres up."""
    cam = T.comb(T.attr("rt_cam_x"), T.attr("rt_cam_y"), T.attr("rt_cam_z"))
    u_c, h_c = planet_frame(T, cam)
    k_ = T.math("DIVIDE", R, T.addf(T.math("MAXIMUM", h_c, 0.5), R))
    return cam, u_c, T.math("SQRT", T.math("MAXIMUM", T.sub(1.0, T.mul(k_, k_)), 0.0))


def eye_alt(T):
    """The altitude of the viewer of this pixel, from its own position (shading point + incoming x view distance):
    right from any view, the cameras' and a free zoomed-out viewport's alike."""
    geo = T.node("ShaderNodeNewGeometry")
    eye = T.vmath("ADD", geo.outputs["Position"],
                  T.vmath("SCALE", geo.outputs["Incoming"], scale=T.node("ShaderNodeCameraData").outputs["View Distance"]))
    return planet_frame(T, eye)[1]


def eye_space(T):
    """How far the viewer of this pixel is out in space, 0 under 2 km up to 1 from 12 km (rt_space's ramp)."""
    return T.smooth(eye_alt(T), 2000.0, 12000.0)


GLOBE_BAND = (8000.0, 12000.0)     # m: the globe takes the planet over from the ground's patches across this band
SITE_GLOW = 140.0                  # m, the radius of a pyramid site's light seen from high up


def globe_share(T):
    """1 where the globe draws this pixel, 0 where the ground's patches do: across GLOBE_BAND they trade pixels by a
    fixed noise per screen pixel against the viewer's progress through the band, a dissolve with no flicker. Both draw
    the same orbit look there (orbit_look), so the trade does not show. Switched at one height, the planet jumped from
    one look and outline to the other (FL2)."""
    cell = T.vmath("FLOOR", T.vmath("MULTIPLY", T.node("ShaderNodeTexCoord").outputs["Window"], (1920.0, 1080.0, 0.0)))
    wn = T.node("ShaderNodeTexWhiteNoise", noise_dimensions="2D")
    T.feed(wn.inputs["Vector"], cell)
    return T.math("LESS_THAN", wn.outputs["Value"], T.smooth(eye_alt(T), GLOBE_BAND[0], GLOBE_BAND[1]))


def coast_w(T):
    """Half-width in m of the coast's land/sea edge in the orbit look: 1.5, and 6 inside the globe handover band, where
    the ground's patches and the globe place their coasts from different resolutions and the per-pixel dissolve drew
    the difference as dark specks along the coasts (10 km, round 6)."""
    ea = eye_alt(T)
    band = T.mul(T.smooth(ea, GLOBE_BAND[0] - 1500.0, GLOBE_BAND[0]), T.sub(1.0, T.smooth(ea, GLOBE_BAND[1], GLOBE_BAND[1] + 3000.0)))
    return T.addf(1.5, T.mul(band, 13.5))     # 15 m (round 9): at 6 m the 10 km coasts still speckled


def orbit_look(T, pos, inc, up, n_, h, depth, land, sun, city=0.0):
    """The planet seen from high up, one look for the ground's patches, its water and the globe (S8, S9, FL2): land
    magenta to violet by height h with lighter pink peaks and a fine mottling in the flat lowlands, lit on its normal n_
    by the real sun; water by its depth, a cyan fringe to deep teal-indigo, with a soft glint; land is the land share.
    On the night side the pyramid sites (city, 1 at a site) as warm lights. On the globe alone, they vanished across the
    handover band and came back above it (night)."""
    land_c = T.ramp(T.mrange(h, 0.0, 520.0, 0.0, 1.0), [(0.0, (0.62, 0.08, 0.36)), (0.35, (0.48, 0.08, 0.46)), (0.7, (0.40, 0.10, 0.52)),
                                                        (0.88, (0.62, 0.22, 0.54)), (1.0, (0.80, 0.42, 0.66))])   # lighter pink peaks
    sea_c = T.ramp(T.mrange(depth, 0.0, 30.0, 0.0, 1.0), [(0.0, (0.10, 0.50, 0.60)), (0.25, (0.04, 0.20, 0.34)), (1.0, (0.02, 0.07, 0.18))])
    mu = T.dot(up, sun["Dir"])
    day = T.smooth(mu, -0.12, 0.18)
    lam = T.math("MAXIMUM", T.dot(n_, sun["Dir"]), 0.0)
    # texture in the flat lowlands (a fifth of the land, under 40 m): a fine mottling toward violet over 400 m, fading out
    # over the ranges, where the relief carries the detail. Flat, they read as a hot magenta slab
    mot = T.node("ShaderNodeTexNoise")
    T.feed(mot.inputs["Vector"], T.vmath("SCALE", pos, scale=1.0 / 400.0))
    mot.inputs["Scale"].default_value = 1.0
    mot.inputs["Detail"].default_value = 4.0
    flat_k = T.smooth(h, 120.0, 20.0)
    land_c = T.mix(T.mul(T.mrange(mot.outputs["Fac"], 0.35, 0.65, 0.0, 1.0), T.mul(flat_k, 0.55)), land_c, (0.34, 0.07, 0.42))
    land_c = T.scale(land_c, T.addf(1.0, T.mul(T.sub(mot.outputs["Fac"], 0.5), T.mul(flat_k, 0.5))))
    # shade at 0.3: at 0.12 the relief's shaded slopes went grey-brown, blocky blotches from 10 km up (S9)
    # and flat inside the globe handover band: the ground's patches and the globe shade the relief from normals of
    # different resolution, and their per-pixel dissolve showed that difference as salt-and-pepper speckle (10 km)
    ea = eye_alt(T)
    band = T.mul(T.smooth(ea, GLOBE_BAND[0] - 1500.0, GLOBE_BAND[0]), T.sub(1.0, T.smooth(ea, GLOBE_BAND[1], GLOBE_BAND[1] + 3000.0)))
    lam = T.fmix(band, lam, 0.6)     # fully flat (round 9; at 0.8 the speckle stayed on the 10 km limb)
    lit_land = T.scale(land_c, T.mul(day, T.addf(0.3, T.mul(lam, 0.7))))
    # a warm pink-orange band along the terminator, where the ground sees the sun set (S9: it showed only where the
    # terminator met the limb)
    dusk_b = T.mul(T.smooth(mu, -0.06, 0.0), T.sub(1.0, T.smooth(mu, 0.01, 0.10)))
    lit_land = T.add(lit_land, T.scale((0.55, 0.20, 0.12), T.mul(dusk_b, 0.35)))     # (twice as wide and strong, it read as a
    # broad salmon stripe across the disc)
    rv = T.vmath("REFLECT", T.vmath("SCALE", inc, scale=-1.0), up)
    # a soft lobe: at 0.35 its middle burnt to a white blob, at 0.15 it was gone (S9)
    spec = T.mul(T.math("POWER", T.math("MAXIMUM", T.dot(rv, sun["Dir"]), 0.0), 36.0), T.mul(day, 0.24))
    lit_sea = T.add(T.scale(sea_c, T.mul(day, T.addf(0.35, T.mul(T.math("MAXIMUM", mu, 0.0), 0.65)))), T.scale((1.0, 0.80, 0.90), spec))
    col = T.mix(land, lit_sea, lit_land)
    night = T.sub(1.0, T.smooth(mu, -0.2, 0.05))
    # no lines on the night side (user, 2026-11-11: no dummy wireframe, ever; the 600 m lattice here was one). The
    # sites' lights are small points: city^3 peaks within about 30 m of a site (squared, they were blobs)
    return T.add(col, T.scale((1.0, 0.70, 0.35), T.mul(T.math("POWER", city, 3.0), T.mul(night, 2.0))), (0.003, 0.002, 0.008))


def sun_lit(T, up, n_, sun):
    """Daylight on a surface point from the real sun: a soft terminator about its own horizon (up) and Lambert on its
    normal n_. Emission-only shaders, so this is the only light the system view has."""
    s_ = sun["Dir"]
    return T.mul(T.smooth(T.dot(up, s_), -0.22, 0.3), T.addf(0.25, T.mul(T.math("MAXIMUM", T.dot(n_, s_), 0.0), 0.75)))


def above_horizon(T, pos):
    """Metres of pos above the visible horizon from the camera, along the camera's up: a body cut on the level
    plane hung a few degrees above the horizon."""
    cam, u_c, sin_dip = horizon_dip(T)
    v = T.vmath("SUBTRACT", pos, cam)
    return T.addf(T.dot(v, u_c), T.mul(T.vmath("LENGTH", v), sin_dip))


# --- VJ_Fog(Color): distance haze, but only over the stretch of the view ray inside the ATMO_H shell
g_fog, T, gi, go = make_group("VJ_Fog", [("Color", "NodeSocketColor", None)], [("Color", "NodeSocketColor")])
geo = T.node("ShaderNodeNewGeometry")
cam = T.node("ShaderNodeCameraData")
vd = T.vmath("SCALE", geo.outputs["Incoming"], scale=-1.0)
fx, fy, fz = T.sep(to_local(T, vd))
fdir = T.comb(fx, fy, T.addf(T.mul(T.math("ABSOLUTE", fz), 0.55), 0.004))
fogc = T.group(g_base, Direction=fdir)["Color"]
_, alt = planet_frame(T, geo.outputs["Position"])
pz = T.math("ABSOLUTE", alt)
dist = cam.outputs["View Distance"]
eye = T.vmath("SUBTRACT", T.vmath("ADD", geo.outputs["Position"], T.vmath("SCALE", geo.outputs["Incoming"], scale=dist)), tuple(CENTER))
b_ = T.dot(eye, vd)
c_ = T.sub(T.dot(eye, eye), (R + ATMO_H) ** 2)
t_in = T.math("MAXIMUM", T.sub(T.mul(b_, -1.0), T.math("SQRT", T.math("MAXIMUM", T.sub(T.mul(b_, b_), c_), 0.0))), 0.0)
t_in = T.mul(t_in, T.math("GREATER_THAN", c_, 0.0))      # camera inside the shell: haze from the eye on
dn = T.math("DIVIDE", T.math("MAXIMUM", T.sub(dist, t_in), 0.0), FOG_D)
f = T.math("SUBTRACT", 1.0, T.math("EXPONENT", T.mul(T.mul(dn, dn), -1.0)))
f = T.mul(T.mul(f, T.mrange(pz, 0.0, 600.0, 1.0, 0.7)), T.math("MINIMUM", T.math("MAXIMUM", T.attr("vj_haze"), 0.0), 1.0))
T.feed(go["Color"], T.mix(f, gi["Color"], fogc))

g_col, T, gi, go = make_group("VJ_Color", [("Color", "NodeSocketColor", None), ("Strength", "NodeSocketFloat", 1.0)], [("Color", "NodeSocketColor")])
hue = T.math("FRACT", T.addf(T.attr("vj_hue"), 0.5))
hs = T.node("ShaderNodeHueSaturation")
T.feed(hs.inputs["Hue"], hue)
T.feed(hs.inputs["Color"], gi["Color"])
lit = T.scale(hs.outputs["Color"], T.mul(gi["Strength"], T.attr("vj_intensity")))
T.feed(go["Color"], T.mix(T.attr("vj_strobe"), lit, (6.0, 6.0, 6.0)))


def finish(T, col, fog=True, strength=1.0):
    if fog:
        col = T.group(g_fog, Color=col)["Color"]
    return T.group(g_col, Color=col, Strength=strength)["Color"]


def emission_mat(name, build, blended=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    T = NT(m.node_tree)
    for nd in list(T.n):
        if nd.type != "OUTPUT_MATERIAL":
            T.n.remove(nd)
    out = [nd for nd in T.n if nd.type == "OUTPUT_MATERIAL"][0]
    res = build(T)
    col, alpha = res if isinstance(res, tuple) and len(res) == 2 and not isinstance(res[1], float) else (res, None)
    em = T.node("ShaderNodeEmission")
    T.feed(em.inputs["Color"], col)
    em.inputs["Strength"].default_value = 1.0
    if alpha is None:
        T.feed(out.inputs["Surface"], em.outputs[0])
    else:
        tr = T.node("ShaderNodeBsdfTransparent")
        mx = T.node("ShaderNodeMixShader")
        T.feed(mx.inputs[0], alpha)
        T.feed(mx.inputs[1], tr.outputs[0])
        T.feed(mx.inputs[2], em.outputs[0])
        T.feed(out.inputs["Surface"], mx.outputs[0])
    if blended:
        m.surface_render_method = "BLENDED"
    m.use_backface_culling = False
    return m


def driver(obj, path, index, expr, props):
    fc = obj.driver_add(path, index) if index is not None else obj.driver_add(path)
    dr = fc.driver
    dr.type = "SCRIPTED"
    for name, prop in props.items():
        var = dr.variables.new()
        var.name = name
        var.targets[0].id_type = "SCENE"
        var.targets[0].id = S
        var.targets[0].data_path = '["%s"]' % prop
    dr.expression = expr
    return fc


def chain(ob, path, index, expr, props, own=(), src=None):
    fc = driver(ob, path, index, expr, props)
    for name in own:
        var = fc.driver.variables.new()
        var.name = name
        var.targets[0].id_type = "OBJECT"
        var.targets[0].id = src or ob
        var.targets[0].data_path = '["%s"]' % name
    fc.driver.expression = expr
    return fc


def planetize_fog(g):
    """The island's fog bank and haze take heights as world z (|z| for the mirror). On the planet the
    ground falls away from z = 0 (125 m at 2 km), so the bank vanished beyond about 1 km: surface and
    camera heights become altitudes over the sea sphere."""
    T = NT(g)
    geo = next(n for n in T.n if n.type == "NEW_GEOMETRY")
    P, inc = geo.outputs["Position"], geo.outputs["Incoming"]
    dist = next(n for n in T.n if n.type == "CAMERA").outputs["View Distance"]
    alt_p = planet_frame(T, P)[1]
    alt_c = planet_frame(T, T.vmath("ADD", P, T.vmath("SCALE", inc, scale=dist)))[1]
    for sep in [n for n in T.n if n.type == "SEPXYZ" and n.inputs[0].is_linked and n.inputs[0].links[0].from_socket == P]:
        for ln in list(sep.outputs[2].links):
            if ln.to_node.type == "MATH" and ln.to_node.operation == "ABSOLUTE":        # surface height
                T.l.new(alt_p, ln.to_socket)
            elif ln.to_node.type == "MATH" and ln.to_node.operation == "ADD":           # camera height
                for ln2 in list(ln.to_node.outputs[0].links):
                    T.l.new(alt_c, ln2.to_socket)


def sun_stripes_to_horizon():
    """The island sun's stripes sit on the lower half of its disc (object z), which is exactly the part below the
    horizon when it sets. Their coordinate becomes the lower of object z and the height above the horizon in disc
    radii minus one, so a setting sun shows the full stripe pattern above the horizon, and a high sun is unchanged."""
    m = bpy.data.materials.get("Sun")
    if m is None:
        return
    T = NT(m.node_tree)
    sep = next(n for n in T.n if n.type == "SEPXYZ" and any(l.to_node.type == "MAP_RANGE" and not l.to_node.inputs["From Min"].is_linked
                                                            and abs(l.to_node.inputs["From Min"].default_value - 0.2) < 1e-4 for l in n.outputs["Z"].links))
    stripe_inputs = [l.to_socket for l in sep.outputs["Z"].links if l.to_node.type == "MATH" or (
        l.to_node.type == "MAP_RANGE" and not l.to_node.inputs["From Min"].is_linked
        and abs(l.to_node.inputs["From Min"].default_value - 0.2) < 1e-4)]       # before u exists: u reads Z too
    up_ = T.group(g_frame)["Up"]
    pos = T.node("ShaderNodeNewGeometry").outputs["Position"]
    above = above_horizon(T, pos)
    per_m = T.node("ShaderNodeVectorTransform", vector_type="VECTOR", convert_from="WORLD", convert_to="OBJECT")
    T.feed(per_m.inputs["Vector"], up_)
    u = T.math("MINIMUM", sep.outputs["Z"], T.sub(T.mul(above, T.vmath("LENGTH", per_m.outputs["Vector"])), 1.0))
    # stripes toward sunset only: by day a striped disc with sky in its gaps read as a salmon card, not a sun (T-day)
    u = T.fmix(T.smooth(T.phase()["Twilight"], 0.2, 0.6), 1.0, u)
    for sock in stripe_inputs:
        T.l.new(u, sock)


def drop_fog_bank(g):
    """VJ_Fog mixes its fog bank over the distance haze in its last node; the volume fog replaces the bank on the
    planet, so only the haze stays (and no material pays for the bank per pixel)."""
    T = NT(g)
    fac = next(n for n in T.n if n.type == "GROUP_OUTPUT").inputs[0].links[0].from_node.inputs["Factor"]
    T.l.remove(fac.links[0])
    fac.default_value = 0.0


def no_haze_in_space(g):
    """VJ_Fog's distance haze is the ground's: from space, rays cross its 6 km shell edge-on and it dimmed the whole
    planet and the moon to its night colour. It fades out with the viewer's altitude."""
    T = NT(g)
    gout = next(n for n in T.n if n.type == "GROUP_OUTPUT")
    src = gout.inputs[0].links[0].from_socket
    T.feed(gout.inputs[0], T.mix(eye_space(T), src, next(n for n in T.n if n.type == "GROUP_INPUT").outputs["Color"]))


def frame_island_sky():
    """The island's sky is in world space, z up: right at the pole only. Its shared groups turn with the
    shot's frame (VJ_Frame, rt_up_* written on every cut): VJ_SunDir gives the sun in world space plus a
    Local Dir, VJ_SkyBase works in the frame, VJ_Sky and the haze colour convert their view direction into
    it. VJ_Sky folds its lower half up: its painted sea showed as a grey band between its level horizon and the
    planet's real one (2 to 5 degrees lower from shot heights), and from space behind the planet."""
    T = NT(g_sun)
    gout = next(n for n in T.n if n.type == "GROUP_OUTPUT")
    local = gout.inputs["Dir"].links[0].from_socket
    upl = gout.inputs["Up"].links[0].from_socket
    g_sun.interface.new_socket("Local Dir", in_out="OUTPUT", socket_type="NodeSocketVector")
    T.feed(gout.inputs["Local Dir"], local)
    T.feed(gout.inputs["Dir"], to_world(T, local))
    T.feed(gout.inputs["Up"], to_world(T, upl))
    T = NT(g_base)
    for n in T.n:
        if n.type == "GROUP" and n.node_tree == g_sun:
            for ln in list(n.outputs["Dir"].links):
                T.l.new(n.outputs["Local Dir"], ln.to_socket)
    # heights count from the visible horizon (the sky's horizon glow sits on it), folded below it. Folded at the
    # level plane with the dip added afterwards, the glow stood as a band at the level line, 7 to 17 deg over the
    # ground from 130 to 750 m up (CAM_8, CAM_4)
    T = NT(g_sky)
    gin = next(n for n in T.n if n.type == "GROUP_INPUT")
    for ln in list(gin.outputs["Direction"].links):
        dl = to_local(T, gin.outputs["Direction"])
        lx, ly, lz = T.sep(dl)
        # in space it has no horizon at all: its horizon glow ringed the planet's limb as a purple halo (S6)
        T.feed(ln.to_socket, T.comb(lx, ly, T.fmix(T.attr("rt_space"), T.math("ABSOLUTE", T.addf(lz, horizon_dip(T)[2])), 1.0)))
    # sun and corona set below the island's flat sea (world z = 0): on the planet that is the visible horizon. The
    # moon is a real sphere on its orbit and the whole planet occludes it, so it keeps no cut: cut, it read as a dome
    # from a free view and hung over the horizon in low shots (S4)
    for mname in ("Sun", "Sun Corona", "Moon"):
        m = bpy.data.materials.get(mname)
        if m is None:
            continue
        T = NT(m.node_tree)
        for n in [n for n in T.n if n.type == "SEPXYZ" and n.inputs[0].is_linked and n.inputs[0].links[0].from_socket.name == "Position"]:
            pos_ = n.inputs[0].links[0].from_socket
            if mname == "Moon":
                local_z = T.node("ShaderNodeValue").outputs[0]
                local_z.default_value = 1.0e5
            else:
                local_z = above_horizon(T, pos_)
            for ln in list(n.outputs[2].links):
                T.l.new(local_z, ln.to_socket)
    T = NT(g_fog)
    for n in [n for n in T.n if n.type == "SEPXYZ" and n.inputs[0].is_linked]:
        src = n.inputs[0].links[0].from_node
        if src.type == "VECT_MATH" and src.operation == "SCALE" and src.inputs[0].is_linked \
                and src.inputs[0].links[0].from_socket.name == "Incoming":
            T.feed(n.inputs[0], to_local(T, src.outputs[0]))


def sunset_band(g):
    """At sunset a pink band low in the sky all round, most away from the sun: there the island's gradient was flat
    violet from a few degrees up, no poster gradient (CAM_1 sunset, T-sunset). Sky and reflections both use it."""
    T = NT(g)
    gout = next(n for n in T.n if n.type == "GROUP_OUTPUT")
    gin = next(n for n in T.n if n.type == "GROUP_INPUT")
    src = gout.inputs["Color"].links[0].from_socket
    dx, dy, dz = T.sep(T.vmath("NORMALIZE", gin.outputs["Direction"]))
    sx, sy, _ = T.sep(T.group(g_sun)["Local Dir"])
    away = T.mrange(T.addf(T.mul(dx, sx), T.mul(dy, sy)), 0.3, -0.5, 0.0, 1.0)
    ph = T.phase()
    k_ = T.mul(T.mul(T.mul(ph["Twilight"], T.sub(1.0, ph["Night"])), T.smooth(dz, 0.5, 0.0)), away)
    T.feed(gout.inputs["Color"], T.add(src, T.scale((0.55, 0.10, 0.35), T.mul(k_, 0.6))))


if GRAFT:   # the planet's materials call the island's shared groups, so later island changes show up here too
    g_phase, g_sun, g_base, g_sky, g_fog, g_col, g_met = (
        ISLAND_GROUPS[n] for n in ("VJ_Phase", "VJ_SunDir", "VJ_SkyBase", "VJ_Sky", "VJ_Fog", "VJ_Color", "VJ_Meteor"))
    planetize_fog(g_fog)
    frame_island_sky()
    sunset_band(g_base)
    sun_stripes_to_horizon()
    # the island sun's large spots (a noise darkening its disc by up to 30%) at 8%: they read as a dark blotch on the
    # sun (CAM_0 sunset, round 5)
    for n in bpy.data.materials["Sun"].node_tree.nodes:
        if n.type == "MAP_RANGE" and n.inputs[0].is_linked and n.inputs[0].links[0].from_node.type == "TEX_NOISE":
            n.inputs[4].default_value = 1.0 - (1.0 - n.inputs[4].default_value) * 0.27


def star_texels(T, d, bg=False):
    """The star map's colour toward the world direction d: the map's north celestial pole on the spin axis +x, so the
    sky turns about it with rt_star_ang the way the real one turns about the pole (the camera area sits on the
    equator, both celestial poles on its horizon). Right ascension runs to the left in the map, 0h in its middle."""
    vr = T.node("ShaderNodeVectorRotate", rotation_type="AXIS_ANGLE")
    T.feed(vr.inputs["Vector"], T.vmath("NORMALIZE", d))
    vr.inputs["Axis"].default_value = (1.0, 0.0, 0.0)
    T.feed(vr.inputs["Angle"], T.attr("rt_star_ang"))
    cx, cy, cz = T.sep(vr.outputs["Vector"])
    u = T.sub(0.5, T.math("DIVIDE", T.math("ARCTAN2", cz, cy), 2 * math.pi))
    v = T.addf(0.5, T.math("DIVIDE", T.math("ARCSINE", T.math("MINIMUM", T.math("MAXIMUM", cx, -1.0), 1.0)), math.pi))

    def sample(img, uv, ext):
        tex = T.node("ShaderNodeTexImage", interpolation=STAR_INTERP, extension=ext)
        tex.image = img
        tex.label = "space_sky"
        T.feed(tex.inputs["Vector"], uv)
        return tex.outputs["Color"]
    # two lookups of the same texels: u jumps from 1 to 0 at the map's edge, and its filter took that jump for a huge
    # footprint, a line of smeared stars (CAM_4 at night). The second one runs on past 1 there (the map repeats) and
    # jumps in the map's middle instead, where the first one is used
    ub = T.addf(u, T.math("LESS_THAN", u, 0.5))
    edge = T.math("MAXIMUM", T.math("LESS_THAN", u, 0.25), T.math("GREATER_THAN", u, 0.75))
    col = T.mix(edge, sample(STAR_IMG, T.comb(u, v, 0.0), "REPEAT"), sample(STAR_IMG, T.comb(ub, v, 0.0), "REPEAT"))
    # near a celestial pole the caps (star_caps), blended in from 33 to 29 deg off it
    k_ = 1.0 / math.sin(STAR_CAP)
    uc = T.addf(T.sub(0.75, T.mul(T.math("GREATER_THAN", cx, 0.0), 0.5)), T.mul(cy, 0.25 * k_))
    vc = T.addf(0.5, T.mul(cz, 0.5 * k_))
    capk = T.smooth(T.math("ABSOLUTE", cx), math.cos(STAR_CAP - math.radians(2.0)), math.cos(STAR_CAP - math.radians(6.0)))
    col = T.mix(capk, col, sample(STAR_CAPS, T.comb(uc, vc, 0.0), "EXTEND"))
    v_ = T.vmath("MAXIMUM", T.vmath("SUBTRACT", col, (STAR_BLACK,) * 3), (0.0, 0.0, 0.0))
    if bg:       # (round 13) the points only, as /vj/nebula goes to 0: the map less its blurred light (STAR_BG)
        hp = T.vmath("MAXIMUM", T.vmath("SUBTRACT", v_, T.vmath("SCALE", sample(STAR_BG, T.comb(u, v, 0.0), "REPEAT"),
                                                                 scale=STAR_BG_K)), (0.0, 0.0, 0.0))
        nk = T.math("MINIMUM", T.math("MAXIMUM", T.attr("vj_nebula"), 0.0), 1.0)
        v_ = T.mix(nk, hp, v_)
    return v_, T.dot(v_, (0.2126, 0.7152, 0.0722))


def star_gain(T, v_, lum):
    return T.scale(v_, T.mul(T.mul(lum, STAR_K), T.addf(1.0, T.mul(T.math("MINIMUM", T.attr("rt_space"), 1.0), 0.5))))   # a little more in space


def star_map(T, d):
    return star_gain(T, *star_texels(T, d))


def space_sky(g):
    """The sky of a star system (S5, S6). The island's night layers (a purple milky way, dust lanes, a nebula and its
    stars) read as a purple haze band, from space above all: each now feeds a constant that zeroes it. In their place
    the real sky (star_map), at night and in space; and from space the real sun as a small round disc with glare (the
    striped card is a ground-shot object and hides there)."""
    T = NT(g)
    # every procedural star layer, the island's 240-cell one too: a 3D voronoi cut by the unit sphere showed its
    # lattice as rings of stars, and the island's layer was mirrored below the horizon and pulsed with the beat
    for n in [n for n in T.n if (n.type == "TEX_NOISE" and n.inputs["Detail"].default_value >= 5.0)
                                or (n.type == "TEX_VORONOI" and n.inputs["Scale"].default_value >= 200.0)]:
        for out in n.outputs:
            for ln in list(out.links):
                k_ = T.node("ShaderNodeValue")
                k_.outputs[0].default_value = 1.0 if (n.type == "TEX_VORONOI" and out.name == "Distance") else 0.0
                T.l.new(k_.outputs[0], ln.to_socket)
    gin = next(n for n in T.n if n.type == "GROUP_INPUT")
    gout = next(n for n in T.n if n.type == "GROUP_OUTPUT")
    prev = gout.inputs["Color"].links[0].from_socket
    d = T.vmath("NORMALIZE", gin.outputs["Direction"])
    spc = T.attr("rt_space")
    lz = T.sep(to_local(T, d))[2]
    hz = T.fmix(spc, T.mrange(T.addf(lz, horizon_dip(T)[2]), 0.0, 0.1, 0.0, 1.0), 1.0)     # ground: none at the horizon
    w = T.mul(T.mul(T.math("MAXIMUM", T.group(g_skyph)["Night"], spc), T.attr("vj_stars")), hz)
    v_, lum = star_texels(T, d, bg=True)
    stars = star_gain(T, v_, lum)
    # /vj/nebula (round 9): the map's diffuse light, the Milky Way and its dust lanes, in its own colours. The lum^2
    # gain keeps the points crisp and crushes it (texels under 0.05 give 9 % of the drawn light,
    # review/star_map_stats.py); the band adds those texels linearly from the same lookups, the empty field (median 0,
    # 90th percentile 0.008) stays black. The island's purple nebula volume and sky layer stay off (S6 smear)
    band = T.scale(v_, T.mul(T.smooth(lum, NEB_LO, NEB_HI), NEB_K))
    wb = T.mul(T.mul(T.math("MAXIMUM", T.group(g_skyph)["Night"], spc), T.attr("vj_nebula")), hz)
    s_ = T.vmath("NORMALIZE", T.comb(T.attr("rt_sun_x"), T.attr("rt_sun_y"), T.attr("rt_sun_z")))
    ang = T.math("ARCCOSINE", T.math("MINIMUM", T.dot(d, s_), 1.0))
    glow = T.addf(T.mul(T.math("EXPONENT", T.math("DIVIDE", ang, -0.03)), 0.8), T.mul(T.math("EXPONENT", T.math("DIVIDE", ang, -0.12)), 0.04))
    sunw = T.mul(T.smooth(spc, 0.2, 0.6), T.attr("vj_sun"))
    disc = T.scale((1.0, 0.95, 0.86), T.mul(T.addf(T.mul(T.smooth(ang, 0.014, 0.011), 12.0), glow), sunw))
    T.feed(gout.inputs["Color"], T.add(prev, T.scale(stars, w), T.scale(band, wb), disc))


fill_sky_base(g_base)           # both modes: the island's sunset-all-day sky becomes a real one
stars_in_the_dark(g_sky)
if GRAFT:
    space_sky(g_sky)

# ================================================================ world
if not GRAFT:      # graft: the island's world, its VJ_Sky turned with the shot (frame_island_sky)
    W = bpy.data.worlds.get("Synthwave Sky") or bpy.data.worlds.new("Synthwave Sky")
    W.use_nodes = True
    S.world = W
    T = NT(W.node_tree)
    for nd in list(T.n):
        T.n.remove(nd)
    wout = T.node("ShaderNodeOutputWorld")
    gen = T.node("ShaderNodeTexCoord").outputs["Generated"]
    bg = T.node("ShaderNodeBackground")
    T.feed(bg.inputs["Color"], finish(T, T.group(g_sky, Direction=gen)["Color"], fog=False))
    T.feed(wout.inputs["Surface"], bg.outputs[0])

# ================================================================ GN: elevation, the one noise every part samples
g_elev, G, gi, go = gn_group("PL_Elevation", [("Dir", "NodeSocketVector", None), ("Seed", "NodeSocketFloat", SEED)],
                             [("Elevation", "NodeSocketFloat"), ("Mountain", "NodeSocketFloat")])
P_m = G.vmath("SCALE", gi["Dir"], scale=R)
seed_v = G.vmath("SCALE", SEED_AXIS, scale=gi["Seed"])      # every noise moves to another region of noise space


def nz(scale_m, detail, rough=0.5, seed=(0.0, 0.0, 0.0)):
    return G.noise(G.add(G.vmath("SCALE", P_m, scale=1.0 / scale_m), seed, seed_v), detail, rough)


cont = nz(7000.0, 4, 0.55, (3.1, 7.7, 1.3))                            # continents
pole = G.sep(gi["Dir"])[2]
cont = G.addf(cont, G.mul(G.smooth(pole, math.cos(0.30), math.cos(0.06)), 0.16))   # the show region at the north pole stays land
shape = nz(2400.0, 2, 0.5, (11.0, 5.0, 2.0))
mmask = G.smooth(G.addf(cont, G.mul(G.sub(shape, 0.5), 0.7)), 0.52, 0.68)      # ranges inland, more and narrower
rg = nz(1250.0, 5, 0.55, (19.0, 3.0, 7.0))
ridge = G.math("POWER", G.mrange(G.sub(1.0, G.math("ABSOLUTE", G.sub(G.mul(rg, 2.0), 1.0))), 0.35, 1.0, 0.0, 1.0), 1.6)
hills = nz(420.0, 2, 0.5, (5.0, 13.0, 17.0))
knolls = nz(220.0, 2, 0.5, (23.0, 2.0, 9.0))
roll = nz(1000.0, 2, 0.5, (29.0, 17.0, 4.0))
inland = G.smooth(cont, 0.47, 0.58)              # 0 at the coast: beaches and shores stay low
# the 300 m hydrology grid must resolve every dip, or its flat lake levels stand as walls over the finer ground:
# hills are 1 km across, and the little hills only ever rise (no pits under the grid)
rolling = G.mul(G.addf(G.mul(G.sub(roll, 0.3), HILLS_M), G.mul(G.smooth(knolls, 0.45, 0.85), KNOLLS_M)), inland)
foot = G.mul(G.smooth(G.addf(cont, G.mul(G.sub(shape, 0.5), 0.7)), 0.45, 0.56), G.mul(ridge, 60.0))   # ridged foothills around the ranges
elev = G.addf(G.addf(G.mul(G.sub(cont, 0.5), 900.0), G.addf(rolling, foot)),
              G.mul(G.mul(mmask, ridge), G.addf(260.0, G.mul(hills, 300.0))))
# the island's valley at the pole: its meander (valley_x), a floor that falls north into a bay below sea
# level, so it drains (a flat basin would fill up as a lake), mountains either side
px, py = G.sep(P_m)[:2]
vx = G.addf(G.mul(G.math("SINE", G.math("DIVIDE", py, 650.0)), 140.0), G.mul(G.math("SINE", G.addf(G.math("DIVIDE", py, 230.0), 1.0)), 60.0))
across = G.math("ABSOLUTE", G.sub(px, vx))
valley = G.mul(G.mul(G.sub(1.0, G.smooth(across, VALLEY_W[0], VALLEY_W[1])), G.smooth(py, VALLEY_Y[0] - 800.0, VALLEY_Y[0])),
               G.math("GREATER_THAN", pole, 0.9))
bumps = G.mul(G.smooth(knolls, 0.45, 0.85), G.mrange(across, 120.0, VALLEY_W[0], *VALLEY_KNOLLS))
floor_ = G.addf(G.addf(G.sub(VALLEY_E, G.mul(py, VALLEY_FALL)), G.mul(hills, 3.0)), bumps)
G.feed(go["Elevation"], G.fmix(valley, elev, floor_))
G.feed(go["Mountain"], G.mul(mmask, G.sub(1.0, valley)))

# ================================================================ GN: hydrology (static; the land, water and props read it)
H_COST = 45.0          # m: an edge this high costs twice its length, so drainage follows low ground
JUMPS = 10             # pointer-jumping rounds: covers drainage paths up to 2^10 edges
FILL_ROUNDS = 24       # neighbour relaxation rounds after it (seed 6 converges in 16)
LOD_PATH_SETS = 3      # precomputed land and water sets along each camera flight path
ESTUARY = 0.04         # river grade toward the sea: the river level is at most this x its distance to the sea
DRY_MTN = 0.1          # Mountain mask above which no lake or river forms
g_hyd, G, gi, go = gn_group("PL_Hydrology", [
    ("Water", "NodeSocketFloat", WATER), ("Lake Depth", "NodeSocketFloat", 4.0), ("Springs", "NodeSocketFloat", 0.012),
    ("Spring Height", "NodeSocketFloat", 70.0), ("River Width", "NodeSocketFloat", 38.0), ("Meander", "NodeSocketFloat", 55.0),
    ("Seed", "NodeSocketFloat", SEED)],
    [("Geometry", "NodeSocketGeometry")])
ico = G.node("GeometryNodeMeshIcoSphere")
ico.inputs["Radius"].default_value = R
ico.inputs["Subdivisions"].default_value = HYDRO_SUBDIV
nrm = G.vmath("NORMALIZE", G.pos())
el = G.group(g_elev, Dir=nrm, Seed=gi["Seed"])
geo = G.store(ico.outputs["Mesh"], "e", el["Elevation"])
geo = G.store(geo, "mtn", el["Mountain"])
geo = G.store(geo, "seed", gi["Seed"])      # the one seed: land, water and props read it back from here
srt = G.node("GeometryNodeSortElements", domain="POINT")
G.feed(srt.inputs["Geometry"], geo)
G.feed(srt.inputs["Sort Weight"], G.read("e"))
nvs = G.node("GeometryNodeAttributeDomainSize", component="MESH")
G.feed(nvs.inputs["Geometry"], geo)
k = G.math("FLOOR", G.mul(G.math("MINIMUM", G.math("MAXIMUM", gi["Water"], 0.0), 0.999), G.sub(nvs.outputs["Point Count"], 1.0)))
sea_e = G.sample(srt.outputs[0], G.read("e"), k, "FLOAT")      # sea level: the Water quantile of the elevation
geo = G.store(geo, "sea", sea_e)
geo = G.store(geo, "h", G.sub(G.read("e"), sea_e))
ocean = G.math("LESS_THAN", G.read("h"), 0.0)
ev = G.node("GeometryNodeInputMeshEdgeVertices")
elen = G.vmath("DISTANCE", ev.outputs["Position 1"], ev.outputs["Position 2"])
cost = G.mul(elen, G.addf(1.0, G.math("POWER", G.math("DIVIDE", G.math("MAXIMUM", G.read("h"), 0.0), H_COST), 2.0)))
spn = G.node("GeometryNodeInputShortestEdgePaths")
G.feed(spn.inputs["End Vertex"], ocean)
G.feed(spn.inputs["Edge Cost"], cost)
geo = G.store(geo, "nx0", spn.outputs["Next Vertex Index"], "INT")
geo = G.store(geo, "nx", G.read("nx0", "INT"), "INT")
geo = G.store(geo, "m", G.mul(G.sub(1.0, ocean), G.read("h")))
spd = G.node("GeometryNodeInputShortestEdgePaths")       # distance to the sea along the edges
G.feed(spd.inputs["End Vertex"], ocean)
G.feed(spd.inputs["Edge Cost"], elen)
geo = G.store(geo, "dsea", spd.outputs["Total Cost"])
# pointer jumping: m = highest ground on the way to the sea (the outlet a depression fills up to)
rin = G.node("GeometryNodeRepeatInput")
rout = G.node("GeometryNodeRepeatOutput")
rin.pair_with_output(rout)
rin.inputs["Iterations"].default_value = JUMPS
G.feed(rin.inputs["Geometry"], geo)
jg = G.store(rin.outputs["Geometry"], "m", G.math("MAXIMUM", G.read("m"), G.at(G.read("m"), G.read("nx", "INT"))))
jg = G.store(jg, "nx", G.at(G.read("nx", "INT"), G.read("nx", "INT"), "INT"), "INT")
G.feed(rout.inputs["Geometry"], jg)
geo = rout.outputs["Geometry"]
# exact depression fill: one path's highest point overfills where another way out is lower (half the lakes were
# false, up to 200 m above their spill, flat plateaus in the mountains); relaxing against the neighbours
# (Planchon-Darboux) from that upper bound converges in about 16 rounds
for k_ in range(6):
    eov = G.node("GeometryNodeEdgesOfVertex")
    eov.inputs["Sort Index"].default_value = k_
    edv = G.node("GeometryNodeInputMeshEdgeVertices")
    e_ = eov.outputs["Edge Index"]
    v12 = G.addf(G.at(edv.outputs["Vertex Index 1"], e_, "INT", "EDGE"), G.at(edv.outputs["Vertex Index 2"], e_, "INT", "EDGE"))
    geo = G.store(geo, "nb%d" % k_, G.sub(v12, G.node("GeometryNodeInputIndex").outputs[0]), "INT")
rin = G.node("GeometryNodeRepeatInput")
rout = G.node("GeometryNodeRepeatOutput")
rin.pair_with_output(rout)
rin.inputs["Iterations"].default_value = FILL_ROUNDS
G.feed(rin.inputs["Geometry"], geo)
lo = G.read("m")
for k_ in range(6):
    lo = G.math("MINIMUM", lo, G.at(G.read("m"), G.read("nb%d" % k_, "INT")))
G.feed(rout.inputs["Geometry"], G.store(rin.outputs["Geometry"], "m", G.math("MAXIMUM", G.math("MAXIMUM", G.read("h"), 0.0), lo)))
geo = rout.outputs["Geometry"]
fill = G.read("m")
# no lakes in the ranges: their ridges are finer than this grid, so its pits drain through valleys it cannot see
lowland = G.math("LESS_THAN", G.read("mtn"), DRY_MTN)
lake = G.mul(G.mul(G.math("GREATER_THAN", G.sub(fill, G.read("h")), gi["Lake Depth"]), lowland), G.math("LESS_THAN", fill, LAKE_MAX_H))
wet = G.math("MAXIMUM", ocean, lake)
geo = G.store(geo, "wet", wet)
bw = G.node("GeometryNodeBlurAttribute", data_type="FLOAT")
G.feed(bw.inputs["Value"], G.read("wet"))
bw.inputs["Iterations"].default_value = 1
bl = G.node("GeometryNodeBlurAttribute", data_type="FLOAT")
G.feed(bl.inputs["Value"], G.mul(G.read("wet"), G.read("m")))
bl.inputs["Iterations"].default_value = 1
near = G.math("GREATER_THAN", bw.outputs[0], 1e-4)
bk = G.node("GeometryNodeBlurAttribute", data_type="FLOAT")      # lakes and their first ring: no relief there (PL_Surface)
G.feed(bk.inputs["Value"], lake)
bk.inputs["Iterations"].default_value = 1
geo = G.store(geo, "lake_near", G.math("GREATER_THAN", bk.outputs[0], 1e-4))
ring = G.math("DIVIDE", bl.outputs[0], G.math("MAXIMUM", bw.outputs[0], 1e-6))   # first ring around a lake carries its level, so shores come from the fine terrain
dry_wl = G.addf(G.mul(near, ring), G.mul(G.sub(1.0, near), SENTINEL))
# sea level reaches OCEAN_REACH rings inland: the fine terrain dips under 0 between dry hydrology vertices near a coast,
# and where the sea's level ended there the coast ran along hydrology triangle edges, stair-stepped at 260 m (CAM_6, S8)
bo = G.node("GeometryNodeBlurAttribute", data_type="FLOAT")
G.feed(bo.inputs["Value"], ocean)
bo.inputs["Iterations"].default_value = OCEAN_REACH
dry_wl = G.fmix(G.mul(G.math("GREATER_THAN", bo.outputs[0], 1e-4), G.sub(1.0, near)), dry_wl, 0.0)
geo = G.store(geo, "wl", G.fmix(G.read("wet"), dry_wl, G.mul(G.read("m"), G.sub(1.0, ocean))))
# one flat level per hydrology triangle: the level of its water corners, carried across the whole triangle so the
# water ends well under rising ground (the terrain draws the waterline per pixel, no plunging slivers); where two
# water bodies at different levels share a triangle the lower wins (interpolating them tilted water over dry land)
whi, wlo = None, None
for k_ in range(3):
    cof = G.node("GeometryNodeCornersOfFace")
    cof.inputs["Sort Index"].default_value = k_
    voc = G.node("GeometryNodeVertexOfCorner")
    G.feed(voc.inputs["Corner Index"], cof.outputs["Corner Index"])
    wk = G.at(G.read("wl"), voc.outputs["Vertex Index"])
    wv = G.fmix(G.math("GREATER_THAN", wk, SENTINEL * 0.5), 1e9, wk)     # no water: ignored by the minimum
    whi = wk if whi is None else G.math("MAXIMUM", whi, wk)
    wlo = wv if wlo is None else G.math("MINIMUM", wlo, wv)
one_body = G.math("LESS_THAN", G.sub(whi, wlo), 1.0)
geo = G.store(geo, "wl_face", G.fmix(one_body, wlo, whi), domain="FACE")
# rivers: drainage paths from sparse springs, merged where they meet
wn = G.node("ShaderNodeTexWhiteNoise", noise_dimensions="3D")
G.feed(wn.inputs["Vector"], G.vmath("ADD", G.vmath("SCALE", nrm, scale=937.0), G.vmath("SCALE", SEED_AXIS, scale=gi["Seed"])))
spring = G.mul(G.mul(G.math("LESS_THAN", wn.outputs["Value"], gi["Springs"]), G.math("GREATER_THAN", G.read("h"), gi["Spring Height"])),
               G.mul(G.sub(1.0, G.read("wet")), lowland))
ep = G.node("GeometryNodeEdgePathsToSelection")
G.feed(ep.inputs["Start Vertices"], spring)
G.feed(ep.inputs["Next Vertex Index"], G.read("nx0", "INT"))
m2c = G.node("GeometryNodeMeshToCurve")
G.feed(m2c.inputs["Mesh"], geo)
G.feed(m2c.inputs["Selection"], G.mul(ep.outputs["Selection"], lowland))     # the ranges stay dry: rivers start at their foot
rs = G.node("GeometryNodeResampleCurve")
G.feed(rs.inputs["Curve"], m2c.outputs[0])
rs.inputs["Mode"].default_value = "Length"
rs.inputs["Length"].default_value = 30.0
cur = rs.outputs[0]
ends = G.node("GeometryNodeCurveEndpointSelection")
ends.inputs["Start Size"].default_value = 1
ends.inputs["End Size"].default_value = 1
free = G.math("SUBTRACT", 1.0, ends.outputs[0])      # endpoints stay put, so confluences stay joined
blur = G.node("GeometryNodeBlurAttribute", data_type="FLOAT_VECTOR")
G.feed(blur.inputs["Value"], G.pos())
blur.inputs["Iterations"].default_value = 5
cur = G.setpos(cur, blur.outputs[0], sel=free)
tan = G.node("GeometryNodeInputTangent").outputs[0]
side = G.vmath("NORMALIZE", G.vmath("CROSS_PRODUCT", tan, G.vmath("NORMALIZE", G.pos())))
mz = G.noise(G.vmath("SCALE", G.pos(), scale=1.0 / 450.0), 2, 0.5)
cur = G.setpos(cur, offset=G.vmath("SCALE", side, scale=G.mul(G.mul(G.sub(mz, 0.5), 2.0), gi["Meander"])), sel=free)
cur = G.setpos(cur, G.vmath("SCALE", G.vmath("NORMALIZE", G.pos()), scale=R))
h_fine = G.sub(G.group(g_elev, Dir=G.vmath("NORMALIZE", G.pos()), Seed=gi["Seed"])["Elevation"], sea_e)
rwl_dry = G.math("MINIMUM", G.sub(G.read("m"), 1.5), G.sub(h_fine, 0.8))     # in the fine terrain, never floating over lower ground
# lake level where the river crosses a lake; and no steeper than ESTUARY toward the sea: the last hydrology vertex
# stands 15 to 75 m up 260 m from the coast, so every river ended in a raised pool over a rapid (no river met the sea)
cur = G.store(cur, "rwl", G.math("MINIMUM", G.fmix(G.read("wet"), rwl_dry, G.read("m")), G.sub(G.mul(G.read("dsea"), ESTUARY), 1.5)))
cur = G.store(cur, "rhw", G.mul(gi["River Width"], G.mrange(G.read("dsea"), 0.0, 9000.0, 1.0, 0.3)))
idx = G.index()
d_fwd = G.sub(G.read("dsea"), G.at(G.read("dsea"), G.addf(idx, 1.0)))
d_bwd = G.sub(G.at(G.read("dsea"), G.sub(idx, 1.0)), G.read("dsea"))
endsel = G.node("GeometryNodeCurveEndpointSelection")
endsel.inputs["Start Size"].default_value = 0
endsel.inputs["End Size"].default_value = 1
sgn = G.math("SIGN", G.fmix(endsel.outputs[0], d_fwd, d_bwd))
cur = G.store(cur, "rflow", G.vmath("SCALE", G.node("GeometryNodeInputTangent").outputs[0], scale=sgn), "FLOAT_VECTOR")
G.feed(go["Geometry"], G.join(geo, cur))

# ================================================================ GN: surface at a direction (carved terrain, water level, river)
g_surf, G, gi, go = gn_group("PL_Surface", [("Dir", "NodeSocketVector", None), ("Hydro", "NodeSocketGeometry", None),
                                            ("Rivers", "NodeSocketGeometry", None), ("River Water", "NodeSocketFloat", 1.0)],
                             [("Height", "NodeSocketFloat"), ("Water", "NodeSocketFloat"), ("Channel", "NodeSocketFloat"),
                              ("Flow", "NodeSocketVector"), ("Mountain", "NodeSocketFloat")])
p = G.vmath("SCALE", gi["Dir"], scale=R)
seed_s = G.sample(gi["Hydro"], G.read("seed"), 0, "FLOAT")
el = G.group(g_elev, Dir=gi["Dir"], Seed=seed_s)
h0 = G.sub(el["Elevation"], G.sample(gi["Hydro"], G.read("sea"), 0, "FLOAT"))
sns = G.node("GeometryNodeSampleNearestSurface", data_type="FLOAT")
G.feed(sns.inputs["Mesh"], gi["Hydro"])
G.feed(sns.inputs["Value"], G.read("wl_face"))     # flat per hydrology triangle
G.feed(sns.inputs["Sample Position"], p)
w_lake = sns.outputs["Value"]
prox = G.node("GeometryNodeProximity", target_element="FACES")
G.feed(prox.inputs["Target"], gi["Rivers"])
G.feed(prox.inputs["Source Position"], p)
dr = G.addf(prox.outputs["Distance"], G.mul(G.sub(1.0, prox.outputs["Is Valid"]), 1e6))


def along_river(name, dtype="FLOAT"):
    """The river attribute interpolated along the river at its nearest point: a nearest-point lookup stepped
    the river level every 30 m into terraces with sawtooth edges."""
    sn = G.node("GeometryNodeSampleNearestSurface", data_type=dtype)
    G.feed(sn.inputs["Mesh"], gi["Rivers"])
    G.feed(sn.inputs["Value"], G.read(name, dtype))
    G.feed(sn.inputs["Sample Position"], prox.outputs["Position"])
    return sn.outputs["Value"]


rwl = along_river("rwl")
rhw = G.math("MAXIMUM", along_river("rhw"), 4.0)
# relief of the plains (round 11): the patch mesh is a regular grid of cells, so on flat ground its real edges drew a
# lattice at night. Swells and knolls bend them. Only here, after the hydrology (which reads PL_Elevation), so lakes and
# rivers stay where they were. Nothing at or under the sea or a river within its shore: no new islands, the shores stay;
# rises fade in over the first 3 m above it, dips go at most half way down to it, so no pit holds water. The reference
# level is continuous (sea 0, the river's level falling 1 m per m past its shore): the lakes' level is flat per hydrology
# triangle and stepped the relief along its edges, so lakes and their first ring get none (lake_near, interpolated).
# Level under the island's pyramids (each stands at one height).
seed_p = G.vmath("SCALE", SEED_AXIS, scale=seed_s)
relief = G.addf(G.mul(G.sub(G.noise(G.add(G.vmath("SCALE", p, scale=1.0 / PLAIN_SWELL[1]), (37.0, 11.0, 3.0), seed_p), 2), 0.5), 2.0 * PLAIN_SWELL[0]),
                G.mul(G.sub(G.noise(G.add(G.vmath("SCALE", p, scale=1.0 / PLAIN_KNOLL[1]), (13.0, 31.0, 7.0), seed_p), 1), 0.5), 2.0 * PLAIN_KNOLL[0]))
for o_ in (o_ for o_ in S.objects if GRAFT and o_.type == "MESH" and o_.name[:8] == "Pyramid_" and len(o_.name) == 9):
    r_ = max(o_.dimensions.x, o_.dimensions.y) * 0.71 + 10.0      # half-diagonal and a margin (fading over 150 m left a
    c_ = Vector((o_.location.x, o_.location.y, R)).normalized() * R      # level lattice at their foot in CAM_3)
    relief = G.mul(relief, G.smooth(G.vmath("DISTANCE", p, tuple(c_)), r_, r_ + 60.0))
snl = G.node("GeometryNodeSampleNearestSurface", data_type="FLOAT")
G.feed(snl.inputs["Mesh"], gi["Hydro"])
G.feed(snl.inputs["Value"], G.read("lake_near"))
G.feed(snl.inputs["Sample Position"], p)
relief = G.mul(relief, G.sub(1.0, G.smooth(snl.outputs["Value"], 0.0, 0.5)))
above = G.sub(h0, G.math("MAXIMUM", G.sub(rwl, G.math("MAXIMUM", G.sub(dr, G.addf(rhw, RIVER_SHORE + 15.0)), 0.0)), 0.0))
relief = G.math("MAXIMUM", G.mul(relief, G.smooth(above, 0.0, 3.0)), G.mul(G.math("MAXIMUM", above, 0.0), -0.5))
h = G.addf(h0, relief)
x = G.math("DIVIDE", dr, rhw)
depth = G.addf(1.2, G.mul(rhw, 0.06))
bed = G.sub(rwl, G.mul(depth, G.sub(1.0, G.math("MINIMUM", G.mul(x, x), 1.0))))
bank = G.addf(rwl, G.mul(G.sub(dr, rhw), VALLEY_SLOPE))     # the river cuts a V valley, no cliffs; under the water
# inside the channel, so the bed wins there (a bank clamped at the water level left the bed 0 m deep)
hc = G.math("MINIMUM", h, G.math("MAXIMUM", bed, bank))
in_r = G.mul(G.sub(1.0, G.smooth(G.sub(dr, rhw), RIVER_SHORE, RIVER_SHORE + 15.0)),   # flat past the bank, under the rising
             G.math("GREATER_THAN", h0, G.sub(G.sub(rwl, depth), 1.0)))                # ground: the terrain draws the waterline;
# river water only where it cuts a channel, not over lower ground
# The water level is continuous everywhere, so nothing interpolated across a triangle (the water surface, the land's
# water cut) can zigzag: the highest of lake level, sea level (0) and "15 m under the ground", with the river level
# blended in over its channel. Low land beside the sea gets the flat sea under it; it rises out of it 15 m up.
bg = G.math("MAXIMUM", G.math("MAXIMUM", w_lake, G.sub(hc, 15.0)), 0.0)
wat = G.math("MAXIMUM", bg, G.fmix(G.mul(in_r, gi["River Water"]), bg, rwl))
G.feed(go["Height"], hc)
G.feed(go["Water"], wat)
G.feed(go["Channel"], in_r)
G.feed(go["Flow"], G.vmath("SCALE", along_river("rflow", "FLOAT_VECTOR"), scale=in_r))
G.feed(go["Mountain"], el["Mountain"])


# ================================================================ GN: cube-sphere patches with camera-dependent LOD
def face_uv(G, c):
    """Patch lattice coordinate (0..PATCHES) to the equal-angle cube face coordinate."""
    return G.math("TANGENT", G.mul(G.sub(G.mul(G.math("DIVIDE", c, PATCHES), 2.0), 1.0), math.pi / 4.0))


def cube_dir(G, f, a, b):
    """Unit direction of point (a, b) on cube face f (0..5: +x +y +z -x -y -z), faces wound outward."""
    axis = G.math("FLOORED_MODULO", f, 3.0)
    sign = G.sub(1.0, G.mul(G.math("GREATER_THAN", f, 2.5), 2.0))

    def unit(kk):
        return G.comb(*(G.math("COMPARE", kk, float(i), 0.5) for i in range(3)))

    n_ = G.vmath("SCALE", unit(axis), scale=sign)
    u_ = unit(G.math("FLOORED_MODULO", G.addf(axis, 1.0), 3.0))
    v_ = G.vmath("SCALE", unit(G.math("FLOORED_MODULO", G.addf(axis, 2.0), 3.0)), scale=sign)
    return G.vmath("NORMALIZE", G.add(n_, G.vmath("SCALE", u_, scale=a), G.vmath("SCALE", v_, scale=b)))


PATCH_REACH = 0.75 * PATCH_M     # m, centre to the farthest corner of a patch (the equal-angle cube map stretches them little)


def level_at(G, dvec, anchor, kp, lmin, lmax, reach):
    """Level for the nearest point of a patch (or edge) within reach of dvec: a camera near a patch corner
    must get the fine level under it, not the level of the patch centre."""
    s = G.vmath("ADD", G.vmath("SCALE", dvec, scale=R), tuple(CENTER))
    dist = G.math("MAXIMUM", G.sub(G.vmath("DISTANCE", s, anchor), reach), 1.0)
    lv = G.math("FLOOR", G.math("LOGARITHM", G.math("DIVIDE", kp, dist), 2.0))
    return G.math("MINIMUM", G.math("MAXIMUM", lv, lmin), lmax)


def patch_points(G, anchor, detail, lmin, lmax, cull, cull_alt, mirror_dist):
    """One point per patch: face, index, level (finest of its centre and edge midpoints) and the level of each edge.
    With cull, every point past the anchor's horizon (with H_MAX mountains on either side) takes the lowest level:
    the planet stays a whole sphere from any view at little cost (deleted, a zoomed-out view showed one cap on a black
    ball; at their distance levels, the far side cost a cut 50 ms more). Edge midpoints are shared, so neighbours agree."""
    pts = G.node("GeometryNodePoints")
    pts.inputs["Count"].default_value = 6 * PATCHES * PATCHES
    idx = G.index()
    f = G.math("FLOOR", G.math("DIVIDE", idx, PATCHES * PATCHES))
    r = G.math("FLOORED_MODULO", idx, PATCHES * PATCHES)
    i = G.math("FLOORED_MODULO", r, PATCHES)
    j = G.math("FLOOR", G.math("DIVIDE", r, PATCHES))
    kp = G.math("DIVIDE", PATCH_M, G.math("MAXIMUM", detail, 1e-4))     # level 0 at the distance where a patch spans `detail` rad
    rel = G.vmath("SUBTRACT", anchor, tuple(CENTER))
    a_alt = G.math("MAXIMUM", G.sub(G.vmath("LENGTH", rel), R), cull_alt)
    lim = G.addf(G.math("ARCCOSINE", G.math("DIVIDE", R, G.addf(R, a_alt))), math.acos(R / (R + H_MAX)) + 1.5 * math.pi / 2 / PATCHES)

    def far_level(dvec, reach):
        lv = level_at(G, dvec, anchor, kp, lmin, lmax, reach)
        ang = G.math("ARCCOSINE", G.math("MINIMUM", G.math("MAXIMUM", G.dot(dvec, G.vmath("NORMALIZE", rel)), -1.0), 1.0))
        return G.fmix(G.mul(cull, G.math("GREATER_THAN", ang, lim)), lv, lmin)

    def lvl(ci, cj):
        return far_level(cube_dir(G, f, face_uv(G, ci), face_uv(G, cj)), 0.55 * PATCH_M)

    centre = cube_dir(G, f, face_uv(G, G.addf(i, 0.5)), face_uv(G, G.addf(j, 0.5)))
    lc = far_level(centre, PATCH_REACH)
    lw, le, ls, ln = lvl(i, G.addf(j, 0.5)), lvl(G.addf(i, 1.0), G.addf(j, 0.5)), lvl(G.addf(i, 0.5), j), lvl(G.addf(i, 0.5), G.addf(j, 1.0))
    lp = G.math("MAXIMUM", G.math("MAXIMUM", G.math("MAXIMUM", lc, lw), G.math("MAXIMUM", le, ls)), ln)
    geo = pts.outputs[0]
    for name, v in (("pl_f", f), ("pl_i", i), ("pl_j", j), ("pl_l", lp), ("pl_lw", lw), ("pl_le", le), ("pl_ls", ls), ("pl_ln", ln)):
        geo = G.store(geo, name, v)
    cpos = G.vmath("ADD", G.vmath("SCALE", centre, scale=R), tuple(CENTER))
    return G.store(geo, "pl_mir", G.math("LESS_THAN", G.vmath("DISTANCE", cpos, anchor), mirror_dist))


def patch_mesh(G, points, levels):
    """Instance a grid of 2^level cells on every patch point (all at the origin) and realize them."""
    parts = []
    lvl = G.read("pl_l")
    for k_ in range(levels + 1):
        grid = G.node("GeometryNodeMeshGrid")
        grid.inputs["Size X"].default_value = grid.inputs["Size Y"].default_value = 1.0
        grid.inputs["Vertices X"].default_value = grid.inputs["Vertices Y"].default_value = 2 ** k_ + 1
        iop = G.node("GeometryNodeInstanceOnPoints")
        G.feed(iop.inputs["Points"], points)
        G.feed(iop.inputs["Selection"], G.math("COMPARE", lvl, float(k_), 0.5))
        G.feed(iop.inputs["Instance"], grid.outputs["Mesh"])
        parts.append(iop.outputs[0])
    real = G.node("GeometryNodeRealizeInstances")
    G.feed(real.inputs[0], G.join(*parts))
    x_, y_ = G.sep(G.pos())[:2]
    n_ = G.math("POWER", 2.0, G.read("pl_l"))
    geo = G.store(real.outputs[0], "pl_x", G.math("ROUND", G.mul(G.addf(x_, 0.5), n_)))
    return G.store(geo, "pl_y", G.math("ROUND", G.mul(G.addf(y_, 0.5), n_)))


def lattice_hash(G, x, y, salt):
    """Three values in 0..1 from a lattice position (x, y), the patch's level and the patch itself: no time, no
    camera, so nothing moves while the LOD stands still. salt keeps separate hashes apart."""
    seed = G.addf(G.mul(G.read("pl_f"), PATCHES * PATCHES), G.addf(G.mul(G.read("pl_j"), PATCHES), G.read("pl_i")))
    wn = G.node("ShaderNodeTexWhiteNoise", noise_dimensions="4D")
    G.feed(wn.inputs["Vector"], G.comb(x, y, G.read("pl_l")))
    G.feed(wn.inputs["W"], G.addf(seed, salt))
    return wn.outputs["Color"]


def patch_dir(G):
    """Unit direction of a patch vertex. Interior vertices sit up to JITTER cells off their lattice point in a hashed
    direction (uniform over a disc); the height is read there, so the surface keeps its shape and only the sampling
    moves. Border vertices stay on the lattice, so stitch() and the neighbour patch see the same border."""
    n_ = G.math("POWER", 2.0, G.read("pl_l"))
    x_, y_ = G.read("pl_x"), G.read("pl_y")
    inner = G.mul(G.mul(G.math("GREATER_THAN", x_, 0.5), G.math("LESS_THAN", x_, G.sub(n_, 0.5))),
                  G.mul(G.math("GREATER_THAN", y_, 0.5), G.math("LESS_THAN", y_, G.sub(n_, 0.5))))
    u_, v_ = G.sep(lattice_hash(G, x_, y_, 0.0))[:2]
    rad = G.mul(G.math("SQRT", v_), G.mul(inner, JITTER))
    ang = G.mul(u_, 2.0 * math.pi)
    x_ = G.addf(x_, G.mul(rad, G.math("COSINE", ang)))
    y_ = G.addf(y_, G.mul(rad, G.math("SINE", ang)))
    a = face_uv(G, G.addf(G.read("pl_i"), G.math("DIVIDE", x_, n_)))
    b = face_uv(G, G.addf(G.read("pl_j"), G.math("DIVIDE", y_, n_)))
    return cube_dir(G, G.read("pl_f"), a, b)


def cell_triangles(G, mesh):
    """Split every cell along the same diagonal, explicitly: the jittered quads are not planar, and left to the draw
    tessellation the night edges flooded the far field (CAM_0 line share 17 % against 9.5 %). The diagonal is not
    hashed: with randomly flipped diagonals EEVEE's Wireframe node drew almost no edge (share 1.3 %, round 12)."""
    tri = G.node("GeometryNodeTriangulate")
    G.feed(tri.inputs["Mesh"], mesh)
    tri.inputs["Quad Method"].default_value = "Fixed"
    return tri.outputs[0]


def stitch(G, geo, attrs=()):
    """Border vertices snap onto the lattice of their edge's level: both patches along an
    edge then trace the same polyline, whatever their own levels."""
    ix, iy, lp = G.read("pl_x"), G.read("pl_y"), G.read("pl_l")
    n_ = G.math("POWER", 2.0, lp)
    on = lambda a, b: G.math("COMPARE", a, b, 0.5)
    ow, oe, os_, on_ = on(ix, 0.0), on(ix, n_), on(iy, 0.0), on(iy, n_)
    vert = G.math("MAXIMUM", ow, oe)
    horz = G.mul(G.sub(1.0, vert), G.math("MAXIMUM", os_, on_))
    lv = G.fmix(ow, G.read("pl_le"), G.read("pl_lw"))
    lh = G.fmix(os_, G.read("pl_ln"), G.read("pl_ls"))
    step = G.math("POWER", 2.0, G.addf(G.mul(vert, G.sub(lp, lv)), G.mul(horz, G.sub(lp, lh))))
    t = G.fmix(vert, ix, iy)
    t0 = G.mul(G.math("FLOOR", G.math("DIVIDE", t, step)), step)
    t1 = G.math("MINIMUM", G.addf(t0, step), n_)
    al = G.math("DIVIDE", G.sub(t, t0), step)
    row = G.addf(n_, 1.0)

    def local(tt):
        return G.addf(G.mul(G.fmix(vert, tt, ix), row), G.fmix(vert, iy, tt))

    base = G.sub(G.index(), G.addf(G.mul(ix, row), iy))
    ia, ib = G.addf(base, local(t0)), G.addf(base, local(t1))
    pa = G.sample(geo, G.pos(), ia)
    pb = G.sample(geo, G.pos(), ib)
    # and the water attributes along with the position: a border vertex moved down onto a coarse edge kept the water
    # level of its own height, 34 m over the moved ground, and drew a wet slab with a neon outline on a hillside (CAM_4)
    out = G.setpos(geo, G.vmix(al, pa, pb))
    for name in attrs:
        va = G.sample(geo, G.read(name), ia, "FLOAT")
        vb = G.sample(geo, G.read(name), ib, "FLOAT")
        out = G.store(out, name, G.fmix(al, va, vb))
    return out


def river_near(G, dvec, anc):
    """Rivers carry water only within RIVER_REACH of the set's anchor: past it the land's cells (98 m at 1.8 km) are
    wider than the rivers, and a cell with one river corner drew a water slab with a neon outline on a far hillside
    (CAM_4). The river level sinks under its bed over the last 500 m, so a river narrows out instead of ending."""
    d_ = G.vmath("DISTANCE", G.vmath("ADD", G.vmath("SCALE", dvec, scale=R), tuple(CENTER)), anc)
    return G.smooth(d_, RIVER_REACH, RIVER_REACH - 500.0)


RIVER_REACH = 1800.0           # m from a set's anchor within which rivers carry water


LOD_INPUTS = [("Anchor", "NodeSocketObject", None), ("Hydro", "NodeSocketObject", None),
              ("Detail", "NodeSocketFloat", 0.03), ("Min Level", "NodeSocketInt", 0), ("Max Level", "NodeSocketInt", 6),
              ("Cull", "NodeSocketBool", True), ("Cull Altitude", "NodeSocketFloat", 1500.0)]


def hydro_inputs(G, gi):
    hi = G.node("GeometryNodeObjectInfo")
    G.feed(hi.inputs["Object"], gi["Hydro"])
    hi.transform_space = "ORIGINAL"
    sc = G.node("GeometryNodeSeparateComponents")
    G.feed(sc.inputs[0], hi.outputs["Geometry"])
    ribbon = G.node("GeometryNodeCurvePrimitiveLine")        # rivers as a 1 m ribbon: its faces interpolate the
    ribbon.inputs["Start"].default_value = (-0.5, 0.0, 0.0)  # river level along the river (points are 30 m apart)
    ribbon.inputs["End"].default_value = (0.5, 0.0, 0.0)
    c2m = G.node("GeometryNodeCurveToMesh")
    G.feed(c2m.inputs["Curve"], sc.outputs["Curve"])
    G.feed(c2m.inputs["Profile Curve"], ribbon.outputs[0])
    return sc.outputs["Mesh"], c2m.outputs["Mesh"]


def lod_inputs(G, gi):
    oi = G.node("GeometryNodeObjectInfo")
    G.feed(oi.inputs["Object"], gi["Anchor"])
    return (oi.outputs["Location"], *hydro_inputs(G, gi))


def shade(G, geo, mat, smooth=False):
    ss = G.node("GeometryNodeSetShadeSmooth", domain="FACE")
    G.feed(ss.inputs["Mesh"], geo)
    ss.inputs["Shade Smooth"].default_value = smooth
    sm = G.node("GeometryNodeSetMaterial")
    G.feed(sm.inputs["Geometry"], ss.outputs[0])
    sm.inputs["Material"].default_value = mat
    return sm.outputs[0]


# ================================================================ terrain material (the island's, on a sphere)
SUN_KEY = (-0.72, -0.30, 0.62)     # standalone only: in the graft the star system's sun is the key


def key_dir(T, sun):
    return sun["Dir"] if GRAFT else T.vmath("NORMALIZE", SUN_KEY)


SHOCK_LAMBDA, SHOCK_LAND, SHOCK_FALLOFF, SHOCK_PEAKS, SHOCK_WATER = 170.0, 16.0, 2400.0, 4.0, 12.0
SHOCK_CHOP = (55.0, 4.0, 7.0)


def shock_ring(T, P, i, width_k=1.0):
    a_ = lambda f: T.attr("rt_shock%d_%s" % (i, f))
    dx = T.math("SUBTRACT", P[0], a_("x"))
    dy = T.math("SUBTRACT", P[1], a_("y"))
    dist = T.math("SQRT", T.addf(T.mul(dx, dx), T.mul(dy, dy)))
    off = T.math("SUBTRACT", dist, a_("r"))
    width = T.mul(T.addf(12.0, T.mul(a_("r"), 0.045)), width_k)
    ring = T.mul(T.math("EXPONENT", T.mul(T.math("POWER", T.math("DIVIDE", off, width), 2.0), -1.0)), a_("a"))
    return ring, off, dist, dx, dy


def shock_wave(T, P, amp, lam=SHOCK_LAMBDA, train=0.9):
    total = None
    for i in range(SHOCKS):
        _, off, dist, _, _ = shock_ring(T, P, i)
        q = T.math("DIVIDE", T.addf(off, 0.6 * lam * train / 0.9), train * lam)
        env = T.math("DIVIDE", T.mul(T.attr("rt_shock%d_a" % i), T.math("EXPONENT", T.mul(T.mul(q, q), -1.0))),
                     T.addf(1.0, T.math("DIVIDE", dist, SHOCK_FALLOFF)))
        h_ = T.mul(T.math("SINE", T.mul(off, 2 * math.pi / lam)), env)
        total = h_ if total is None else T.addf(total, h_)
    return T.mul(T.math("TANH", total), amp)


def sea_reflection(T, pos, inc):
    """What the sea reflects at pos for a view along -inc, without the mirrored land: the sky gradient mirrored about
    the local surface, the striped sun and the moon. The reflection backdrop draws it, and the shallow sea bed fades
    into it with depth, so the bed has no edge where it ends."""
    up, _ = planet_frame(T, pos)
    Rd = T.vmath("REFLECT", T.vmath("SCALE", inc, scale=-1.0), up)
    rx, ry, rz = T.sep(to_local(T, Rd))
    arz = T.math("ABSOLUTE", rz)     # the sky gradient only: stars and meteors in the full sky cost too much under every water pixel
    col = T.scale(T.group(g_base, Direction=T.comb(rx, ry, arz))["Color"], T.mrange(arz, 0.0, 0.25, 0.85, 0.5))
    col = T.vmath("MULTIPLY", col, (0.92, 0.80, 1.0))     # toward violet: the pastel day sky made a dull grey-blue sea (CAM_10)
    sun = T.group(g_sun)
    ang = T.math("ARCCOSINE", T.math("MINIMUM", T.dot(Rd, sun["Dir"]), 1.0))
    disc = T.mul(T.smooth(ang, sun["Radius"], T.mul(sun["Radius"], 0.97)), sun["Amount"])
    v = T.math("DIVIDE", T.dot(Rd, sun["Up"]), T.math("SINE", sun["Radius"]))
    gap = T.mrange(v, 0.2, -1.0, 0.0, 0.85)
    band = T.math("FRACT", T.addf(T.mul(v, 9.0), T.mul(T.attr("rt_time"), 0.3)))
    holes = T.mul(T.mul(T.mrange(band, T.sub(gap, 0.04), gap, 1, 0), T.math("GREATER_THAN", gap, 0.01)),
                  T.smooth(T.phase()["Twilight"], 0.2, 0.6))       # striped toward sunset only, like the sun
    scol = T.ramp(T.mrange(v, -1, 1, 0, 1), [(0.00, (1.00, 0.02, 0.40)), (0.38, (1.00, 0.14, 0.22)),
                                             (0.70, (1.00, 0.40, 0.06)), (1.00, (1.00, 0.78, 0.10))])
    # the sun's image down to 5 deg under the horizon: its mirrored top stood on the near water as a lone blob, the
    # middle hidden by the mirrored hills (CAM_7 at sunset)
    col = T.add(col, T.scale(scol, T.mul(T.mul(T.mul(disc, T.sub(1.0, holes)), 0.8), T.smooth(arz, 0.09, 0.03))))
    if GRAFT:   # the real moon (rt_moon_*, where the star system puts it), mirrored the same way: the island's moon arc
        # put a pale disc in the water where the sky had no moon
        mv = T.vmath("SUBTRACT", T.comb(T.attr("rt_moon_x"), T.attr("rt_moon_y"), T.attr("rt_moon_z")), pos)
        mdir = T.vmath("NORMALIZE", mv)
        mr = T.math("ARCSINE", T.math("MINIMUM", T.math("DIVIDE", T.mul(T.math("MAXIMUM", T.attr("vj_moon"), 0.0001), MOON_R),
                                                         T.math("MAXIMUM", T.vmath("LENGTH", mv), MOON_R)), 1.0))
        mang = T.math("ARCCOSINE", T.math("MINIMUM", T.dot(Rd, mdir), 1.0))
        mdisc = T.mul(T.smooth(mang, mr, T.mul(mr, 0.95)), sun["Moon"])
        mglow = T.mul(T.math("EXPONENT", T.mul(T.math("POWER", T.math("DIVIDE", T.sub(mang, mr), 0.03), 2.0), -1.0)), sun["Moon"])
        ph_r = T.phase()
        e_r = T.math("MINIMUM", T.math("MAXIMUM", T.attr("vj_eclipse"), 0.0), 1.0)
        # its magenta rim by day only, like the moon's own, and none in an eclipse: at sunset e1 it lay on the water as a
        # pink oval (CAM_10, round 7)
        mglow = T.mul(mglow, T.mul(T.mul(T.sub(1.0, ph_r["Night"]), T.sub(1.0, ph_r["Twilight"])), T.sub(1.0, e_r)))
        # in a lunar eclipse the moon is a dim copper disc, and so is its image: pale, it lay on the night sea as a bright
        # band (CAM_10 night e1, round 6). In a solar eclipse (day, sunset) it is the dark new moon
        mcol = T.mix(T.mul(e_r, ph_r["Night"]), (0.62, 0.58, 0.75), (0.15, 0.025, 0.015))
        mcol = T.mix(T.mul(e_r, T.sub(1.0, ph_r["Night"])), mcol, (0.01, 0.005, 0.012))
        col = T.add(col, T.scale(mcol, T.mul(mdisc, 0.7)), T.scale((1.0, 0.18, 0.85), T.mul(mglow, 0.25)))
    # at night the real sky in it, at half strength (the sea absorbs): mirrored noise stood in for it before
    night_ = T.mul(T.mul(T.phase()["Night"], T.attr("vj_stars")), T.sub(1.0, T.math("MINIMUM", T.attr("rt_space"), 1.0)))
    col = T.add(col, T.scale(star_map(T, Rd), T.mul(night_, 0.7)))
    return col


def pyramid_shadow(T, pos, s_):
    """1 where an island pyramid shades the ground at pos from the sun along s_, 0 in the sun: each pyramid as a cone
    on its base plane, its shadow the hull of its base and the apex cast along the sun, with a 2 m soft edge. Every
    surface is emission only, so without it the pyramids stood on an even, unshaded plane and read as floating (G5)."""
    tot = None
    for i in range(PYR_SHADOWS):
        a_ = lambda f: T.attr("rt_pyr%d_%s" % (i, f))
        B = T.comb(a_("x"), a_("y"), a_("z"))
        up_ = T.vmath("NORMALIZE", T.vmath("SUBTRACT", B, tuple(CENTER)))
        su = T.math("MAXIMUM", T.dot(s_, up_), 0.08)          # a low sun's shadow at most 12 heights long
        ax = T.vmath("SUBTRACT", T.vmath("SCALE", up_, scale=a_("h")), T.vmath("SCALE", s_, scale=T.math("DIVIDE", a_("h"), su)))
        ax = T.vmath("SUBTRACT", ax, T.vmath("SCALE", up_, scale=T.dot(ax, up_)))     # the apex's shadow, on the base plane
        v = T.vmath("SUBTRACT", pos, B)
        v = T.vmath("SUBTRACT", v, T.vmath("SCALE", up_, scale=T.dot(v, up_)))
        u = T.math("MINIMUM", T.math("MAXIMUM", T.math("DIVIDE", T.dot(v, ax), T.math("MAXIMUM", T.dot(ax, ax), 1.0)), 0.0), 1.0)
        d = T.vmath("LENGTH", T.vmath("SUBTRACT", v, T.vmath("SCALE", ax, scale=u)))
        r = T.mul(T.mul(a_("a"), 1.15), T.sub(1.0, u))
        sh = T.mul(T.smooth(d, T.addf(r, 2.0), T.math("MAXIMUM", T.sub(r, 2.0), 0.0)), T.math("GREATER_THAN", a_("h"), 0.0))
        tot = sh if tot is None else T.math("MAXIMUM", tot, sh)
    return tot


def terrain_build(T):
    geo = T.node("ShaderNodeNewGeometry")
    P = T.sep(geo.outputs["Position"])
    up, alt = planet_frame(T, geo.outputs["Position"])
    mir = T.gattr("mirror")
    flip = T.sub(1.0, T.mul(mir, 2.0))
    Nn = geo.outputs["Normal"]
    nu = T.dot(Nn, up)
    N = T.vmath("SUBTRACT", Nn, T.vmath("SCALE", up, scale=T.mul(T.math("MINIMUM", nu, 0.0), 2.0)))   # mirror: normal back up, like |Nz| on the island
    anu = T.math("ABSOLUTE", nu)
    z = T.math("ABSOLUTE", alt)
    zw = T.sub(T.mul(alt, flip), T.gattr("pl_w"))          # height above its own water (sea, lake or river)
    sun = T.group(g_sun)
    hgt = T.mrange(z, 0.0, 480.0, 0.0, 1.0)
    # the light on gentle slopes from the land's own normal with its tilt exaggerated (SHADE_TILT): the mesh, its edges
    # and every other term keep N
    tilt_k = T.addf(1.0, T.mul(T.sub(1.0, T.smooth(T.sub(1.0, anu), SHADE_TILT[1], SHADE_TILT[2])), SHADE_TILT[0] - 1.0))
    N_l = T.vmath("NORMALIZE", T.vmath("ADD", T.vmath("SCALE", up, scale=T.dot(N, up)),
                                       T.vmath("SCALE", T.vmath("SUBTRACT", N, T.vmath("SCALE", up, scale=T.dot(N, up))), scale=tilt_k)))
    lam_s = T.math("POWER", T.math("MAXIMUM", T.dot(N_l, sun["Dir"]), 0.0), 1.4)
    lam_k = T.math("POWER", T.math("MAXIMUM", T.dot(N_l, key_dir(T, sun)), 0.0), 1.6)
    slope = T.math("SUBTRACT", 1.0, T.smooth(anu, 0.9, 0.99))
    fv = 1.0          # smooth shaded, no per-face shade: flat faces read as blocky stepped squares on near mountains (CAM_4)
    sunc = T.ramp(hgt, [(0.0, (0.9, 0.05, 0.45)), (0.6, (1.0, 0.12, 0.40)), (1.0, (1.0, 0.38, 0.22))])
    sunc = T.scale(sunc, T.mul(T.mul(lam_s, 1.05), sun["Day"]))
    sunc = T.scale(sunc, T.sub(1.0, pyramid_shadow(T, geo.outputs["Position"], sun["Dir"])))
    keyc = T.ramp(hgt, [(0.0, (0.50, 0.03, 0.55)), (1.0, (0.90, 0.10, 0.62))])
    keyc = T.scale(keyc, T.mul(lam_k, T.addf(0.03, T.mul(T.math("POWER", hgt, 0.8), 0.62))))
    base = T.ramp(hgt, [(0.0, (0.004, 0.001, 0.018)), (1.0, (0.03, 0.006, 0.09))])
    # the sky's fill on faces turned from the sun and the key: without it they were navy-black holes (CAM_4)
    amb = T.scale((0.10, 0.035, 0.17), T.mul(sun["Day"], T.addf(0.5, T.mul(anu, 0.5))))
    col = T.add(base, sunc, keyc, amb)
    ndv = T.math("ABSOLUTE", T.dot(N, geo.outputs["Incoming"]))
    rimk = T.mul(T.math("POWER", T.math("SUBTRACT", 1.0, ndv), 4.0), T.math("MAXIMUM", T.addf(T.dot(N, sun["Dir"]), 0.25), 0.0))
    col = T.add(col, T.scale((1.0, 0.25, 0.55), T.mul(T.mul(rimk, T.mul(slope, 1.4)), sun["Day"])))
    col = T.add(col, T.scale((1.0, 0.5, 0.8), T.mul(T.smooth(hgt, 0.75, 1.0), T.mul(lam_s, 0.5))))
    ph = T.phase()
    tw = ph["Twilight"]
    col = T.scale(col, T.mrange(tw, 0.0, 1.0, 1.0, 0.22))
    glowk = T.mul(T.math("MAXIMUM", T.dot(N, T.group(g_frame)["North"]), 0.0), slope)
    col = T.add(col, T.scale((1.0, 0.32, 0.30), T.mul(T.mul(T.math("POWER", T.math("SUBTRACT", 1.0, ndv), 3.0), glowk), T.mul(tw, 0.55))))
    land_lit = col               # the ground lit as if dry: what a bank's mirror image in the water shows
    bank = T.smooth(zw, 0.0, 7.0)
    col = T.scale(col, T.mrange(bank, 0.0, 1.0, 0.6, 1.0))
    col = T.scale(col, T.mrange(zw, -SHALLOW, 0.0, 0.03, 0.55))   # the wet bed darkens with depth, so where it ends the reflection takes over unseen
    # at night a slight glow (T-night) at every distance, but only as lines: where they crowd under a pixel they fade out,
    # not into their mean glow, so the far floor stays a dark silhouette (a flat grey-violet plane at 0.03 to 0.05 read
    # as a slab, CAM_0 at night)
    col = T.mix(ph["Night"], col, (0.0015, 0.0, 0.006))
    # the only lines on the planet: the real edges of the drawn ground mesh (Wireframe node, pixel size), from sunset to
    # night (vj_night 0.25 to 0.5), strength vj_grid, pulsed by bass and beat. No lattice of any kind (user, 2026-11-11:
    # "I NVER want to see ANY dummy wireframe"); the 24 m terrain lattice and its scroll were one. Only on dry land and
    # not on the mirror copy, and faded where a cell's smaller side is under about 10 px on screen, where the edges
    # crowd into a solid fill. The globe draws no edges: its sphere is a proxy under shaded relief
    cam = T.node("ShaderNodeCameraData")
    wf = T.node("ShaderNodeWireframe", use_pixel_size=True)
    wf.inputs["Size"].default_value = 1.0
    cell_px = T.math("DIVIDE", T.math("DIVIDE", PATCH_M, T.math("POWER", 2.0, T.gattr("pl_l"))),
                     T.mul(cam.outputs["View Distance"], 0.0011))
    # the smaller side of a cell on screen: its size in pixels, foreshortened by the view's slant (ndv). Faded by
    # distance alone, the far ground's edges crowded into a cyan web over 29% of CAM_0 at night (round 10)
    dense = T.mrange(T.mul(cell_px, ndv), 4.0, 10.0, 0.0, 1.0)
    edge = T.mul(T.mul(wf.outputs["Fac"], dense), T.mul(T.smooth(zw, 0.3, 2.0), T.sub(1.0, mir)))
    pulse = T.addf(1.0, T.addf(T.mul(T.attr("rt_beat"), 1.6), T.mul(T.attr("vj_bass"), 1.2)))
    edge = T.mul(T.mul(edge, pulse), T.mul(T.smooth(T.attr("vj_night"), 0.25, 0.5), T.attr("vj_grid")))
    col = T.mix(T.math("MINIMUM", T.mul(edge, 0.7), 1.0), col, (0.05, 0.75, 1.0))
    # the shallow bed fades into what the sea reflects where the bed ends (1 m down): cut off there, its edge drew a
    # bowl's lip across the sea (CAM_7) and pale polygon blotches over sandbanks (CAM_10)
    # and flats under 0.5 m above it read as wet (with their mirror copies): sandbanks just above the sea showed as
    # pale pink polygons floating on it, doubled by their reflection (CAM_10)
    bed_k = T.smooth(zw, 0.5, -0.1)
    # above the water the flats have no water layer over them: dimmed by the sea's own alpha (1 - its Fresnel
    # reflection) they match the water around them (lighter, they still showed as patches)
    refl_w = T.mrange(T.math("POWER", T.math("SUBTRACT", 1.0, ndv), 4.0), 0.0, 1.0, 0.5, 0.94)
    # flats just above it are wet sand: the ground darkened with a faint sheen of the sky. The water beside them mirrors
    # the dark hills, and with the sky in them they read as a pale raised ledge along the water (CAM_7)
    refl_s = sea_reflection(T, geo.outputs["Position"], geo.outputs["Incoming"])
    # the ground just under the waterline is dark wet sand, the sea's reflection only from 0.6 m down: drawing the
    # reflected sky right up to the shore, it showed as a bright line between the hills and their mirror image
    # (CAM_10 at sunset, round 6). Its sheen of the sky at 0.08 (0.2 lit it as part of that line)
    # Under a sloped bank, down to 2 m, it draws the bank itself as its mirror image does: the real bed lies right under
    # the surface there, in front of the mirrored hill, and its reflected sky was the bright line (the water, the mirror
    # object, the rim light and the dusk glow hidden, it stayed). Flat shallows keep the sky (sandbanks in a river)
    bank_k = T.mul(T.smooth(zw, -2.0, -0.2), T.sub(1.0, T.smooth(anu, 0.9, 0.98)))
    under_ = T.mix(T.smooth(zw, -0.6, -0.1), refl_s, T.scale(col, 0.3))
    # at 0.2 (round 9): at 0.6 the bank under the water was about 1.8 x the dry bank above it (col x 0.33), a bright
    # strip along the waterline (CAM_1 bank lines, round 8)
    under_ = T.mix(bank_k, under_, T.scale(land_lit, T.mul(0.2, T.sub(1.0, T.mul(ph["Night"], 0.95)))))
    # The flats over it at 0.3 of their colour (0.45 left sandbanks in the river as bright pink blotches, CAM_1 by day)
    wet_col = T.mix(T.smooth(zw, -0.02, 0.05), under_, T.add(T.scale(col, 0.3), T.scale(refl_s, T.mul(refl_w, 0.08))))
    col = T.mix(bed_k, col, wet_col)
    # no neon waterline: a pink line, one of the "violet lines" the user cut ("ONLY the wireframe please"), and it
    # traced the land's triangles where they meet the water as a zigzag (CAM_1)
    # from space the ground's own palette (S8): magenta and violet land under the real sun with a soft terminator,
    # dark violet on the night side, and the sea drawn here by zw per pixel (the water mesh drops dry faces whole,
    # which drew the coasts stair-stepped). Grey-tan rock read as another planet from far away
    cw_ = coast_w(T)
    sim = orbit_look(T, geo.outputs["Position"], geo.outputs["Incoming"], up, N, alt, T.mul(zw, -1.0), T.smooth(zw, T.mul(cw_, -1.0), cw_), sun,
                     T.gattr("pl_city"))
    col = T.mix(eye_space(T), col, sim)
    vd_ = T.node("ShaderNodeVectorDisplacement", space="OBJECT")
    vd_.inputs["Midlevel"].default_value = 0.0
    vd_.inputs["Scale"].default_value = 1.0
    peaks = T.addf(1.0, T.mul(T.smooth(z, 20.0, 400.0), SHOCK_PEAKS))
    T.feed(vd_.inputs["Vector"], T.vmath("SCALE", up, scale=T.mul(T.mul(shock_wave(T, P, SHOCK_LAND), peaks), flip)))
    T.feed([nd for nd in T.n if nd.type == "OUTPUT_MATERIAL"][0].inputs["Displacement"], vd_.outputs["Displacement"])
    # visible above its own water level, and as the shallow bed down to SHALLOW under it; the mirror copy only above
    # the mirror copy only within MIRROR_REACH of the camera: a sphere mirrored radially is only a mirror nearby. A
    # view ray that dips under the near water travels on underground and met mirrored land kilometres away, shown as
    # pale detached patches on the sea (CAM_10)
    cam_m = T.comb(T.attr("rt_cam_x"), T.attr("rt_cam_y"), T.attr("rt_cam_z"))
    far_m = T.mul(mir, T.math("GREATER_THAN", T.vmath("DISTANCE", geo.outputs["Position"], cam_m), MIRROR_REACH))
    vis = T.mul(T.math("GREATER_THAN", zw, T.mul(T.sub(1.0, mir), -SHALLOW)), T.sub(1.0, far_m))
    # from space the globe draws the planet (globe_build): the LOD patches drew a ragged, faceted limb (S9)
    vis = T.mul(vis, T.sub(1.0, globe_share(T)))
    return finish(T, col), vis


m_terrain = emission_mat("Terrain", terrain_build)
m_terrain.displacement_method = "DISPLACEMENT"


# ================================================================ water material
WAVES = [((0.30, 1.00), 150.0, 1.30), ((-0.62, 0.78), 88.0, 0.80), ((0.92, 0.38), 57.0, 0.45), ((-0.18, -1.00), 36.0, 0.22)]


def wave_height(T, P, t, sea, vdist):
    gust = T.node("ShaderNodeTexNoise")
    T.feed(gust.inputs["Vector"], T.comb(T.mul(P[0], 0.0011), T.mul(P[1], 0.0011), T.mul(t, 0.02)))
    gust.inputs["Scale"].default_value = 1.0
    gust.inputs["Detail"].default_value = 1.0
    amp = T.mul(T.mrange(gust.outputs["Fac"], 0.3, 0.7, 0.35, 1.5), T.addf(0.12, T.mul(sea, 0.88)))
    edge = T.mrange(vdist, 2500.0, 6000.0, 1.0, 0.0)     # coarse far patches cannot carry the waves
    total, amax = 0.0, 0.0
    for (dxw, dyw), lam, a in WAVES:
        n_ = math.hypot(dxw, dyw)
        k_ = 2 * math.pi / lam
        w_ = math.sqrt(9.81 * k_)
        ph_ = T.math("SUBTRACT", T.addf(T.mul(P[0], dxw / n_ * k_), T.mul(P[1], dyw / n_ * k_)), T.mul(t, w_))
        peaked = T.math("SUBTRACT", T.mul(T.math("POWER", T.mul(T.addf(T.math("SINE", ph_), 1.0), 0.5), 1.8), 2.0), 0.6)
        total = T.addf(total, T.mul(peaked, a)) if not isinstance(total, float) else T.mul(peaked, a)
        amax += a
    hgt = T.mul(T.mul(total, amp), edge)
    # only the tips (the sum peaks at 1.4): where the four wave trains add up, a crest band from 0.62 lit patches tens
    # of metres across, read as bright blotches on the sea (pink by day, cyan at night, CAM_8 and CAM_10)
    crest = T.mul(T.smooth(T.math("DIVIDE", hgt, T.math("MAXIMUM", T.mul(amp, amax), 0.05)), 1.2, 1.38), T.math("POWER", sea, 1.5))
    return hgt, crest


RIPPLE_TILT = 0.5              # ripple normal tilt at vj_water 1
WATER_HAZE = (900.0, 7000.0)   # m, the water hazes toward the horizon sky between these distances


SEA_DAY = (0.010, 0.042, 0.085)    # the sea's own colour by day: deep teal-indigo, as from orbit


def water_shader(m):
    """The island's water: ocean blended over the mirrored land, lakes and rivers above sea
    level opaque with the sky reflected in the shader. Rivers flow along pl_flow."""
    T = NT(m.node_tree)
    for nd in list(T.n):
        if nd.type != "OUTPUT_MATERIAL":
            T.n.remove(nd)
    out = [nd for nd in T.n if nd.type == "OUTPUT_MATERIAL"][0]
    geo = T.node("ShaderNodeNewGeometry")
    pos = geo.outputs["Position"]
    P = T.sep(pos)
    up, alt = planet_frame(T, pos)
    t = T.attr("rt_time")
    vdist = T.node("ShaderNodeCameraData").outputs["View Distance"]
    depth = T.gattr("pl_depth")
    lake = T.smooth(alt, 3.0, 8.0)       # up to 3 m the water is sea level for the mirrored land; higher lakes reflect the sky themselves
    sea = T.mul(T.smooth(depth, 3.0, 25.0), T.sub(1.0, lake))
    flow = T.add(T.scale(T.gattr("pl_flow", "Vector"), RIVER_SPEED), T.scale((0.3, -1.0, 0.0), T.mul(sea, 1.4)))
    ph1 = T.math("FRACT", T.math("DIVIDE", t, FLOW_CYCLE))
    ph2 = T.math("FRACT", T.addf(T.math("DIVIDE", t, FLOW_CYCLE), 0.5))
    w1 = T.math("SUBTRACT", 1.0, T.math("ABSOLUTE", T.math("SUBTRACT", 1.0, T.mul(ph1, 2.0))))

    def ripples(ph_, shift):
        q = T.vmath("ADD", T.vmath("SUBTRACT", pos, T.scale(flow, T.mul(ph_, FLOW_CYCLE))), shift)
        nd = T.node("ShaderNodeTexNoise")
        T.feed(nd.inputs["Vector"], T.vmath("MULTIPLY", q, (0.06, 0.16, 0.06)))
        nd.inputs["Scale"].default_value = 1.0
        nd.inputs["Detail"].default_value = 2.0
        return nd.outputs["Fac"], nd.outputs["Color"]

    (r1, c1), (r2, c2) = ripples(ph1, (0.0, 0.0, 0.0)), ripples(ph2, (37.0, 11.0, 0.0))
    hh = T.addf(T.mul(r1, w1), T.mul(r2, T.math("SUBTRACT", 1.0, w1)))
    ripple_tilt = T.vmath("SUBTRACT", T.vmix(T.math("SUBTRACT", 1.0, w1), c1, c2), (0.5, 0.5, 0.5))
    swell = T.math("SINE", T.math("SUBTRACT", T.addf(T.mul(P[0], 0.011), T.mul(P[1], 0.032)), T.mul(t, 1.1)))
    hh = T.addf(hh, T.mul(swell, T.mul(sea, 0.25)))
    wav, crest = wave_height(T, P, t, sea, vdist)
    swellz = shock_wave(T, P, SHOCK_LAND + SHOCK_WATER)
    shockz = T.addf(swellz, shock_wave(T, P, SHOCK_CHOP[2], SHOCK_CHOP[0], SHOCK_CHOP[1]))
    shockz = T.mul(T.mul(shockz, T.smooth(vdist, 40.0, 220.0)), T.sub(1.0, lake))
    lift = T.mul(T.mul(T.addf(wav, shockz), T.attr("vj_water")), T.smooth(depth, 0.3, 3.0))   # calm at the shore: no moving jagged coast
    disp = T.node("ShaderNodeDisplacement")
    T.feed(disp.inputs["Height"], lift)
    disp.inputs["Midlevel"].default_value = 0.0
    disp.inputs["Scale"].default_value = 1.0
    T.feed(out.inputs["Displacement"], disp.outputs["Displacement"])
    for i in range(SHOCKS):
        ring, off, _, _, _ = shock_ring(T, P, i, 2.2)
        pass     # shockwaves are movement only: no ring of brighter ripples
    # ripple normal from the ripple noise's own colour (same evaluation): a Bump node evaluated the two noises three
    # times more per pixel, the largest share of the water's cost (scene-perf); the waves themselves are geometry
    tilt = T.vmath("SCALE", T.vmath("SUBTRACT", ripple_tilt, T.vmath("SCALE", up, scale=T.dot(ripple_tilt, up))),
                   scale=T.mul(T.attr("vj_water"), RIPPLE_TILT))
    N = T.vmath("NORMALIZE", T.vmath("ADD", geo.outputs["Normal"], tilt))
    inc = geo.outputs["Incoming"]
    ndv = T.math("MAXIMUM", T.dot(N, inc), 0.0)
    fres = T.math("POWER", T.math("SUBTRACT", 1.0, ndv), 4.0)
    bands = T.mrange(hh, 0.38, 0.62, T.mrange(fres, 0.0, 0.5, 1.0, 0.85), 1.0)    # softer: the mirrored banks broke into pink
    # blotches on the river (CAM_1 by day)
    # at least 0.3, not 0.5: half the pastel sky over every metre of sea left it a washed-out grey-blue with no depth
    # (CAM_10 by day)
    refl = T.mul(T.mul(T.mrange(fres, 0.0, 1.0, 0.3, 0.94), bands), T.attr("vj_water"))
    Rv = T.vmath("REFLECT", T.vmath("SCALE", inc, scale=-1.0), N)
    sun = T.group(g_sun)
    sd = T.dot(Rv, sun["Dir"])
    # a soft glint (a hard step drew a cut-out disc at sunset), on a low sun only: a high sun caught only the steepest
    # ripples, as white specks over the sea (CAM_10 by day)
    sparkle = T.mul(T.smooth(sd, 0.990, 0.999), T.mrange(T.dot(up, sun["Dir"]), 0.2, 0.45, 0.7, 0.0))   # soft and dim: a
    # bright one stood as a lone disc on the near water (CAM_7 sunset)
    sheen = T.mul(T.math("POWER", T.math("MAXIMUM", sd, 0.0), 40.0), 0.10)
    glit = T.mul(T.addf(sparkle, sheen), T.mul(sun["Amount"], T.addf(0.8, T.attr("vj_level"))))
    # on water seen within a few degrees of the horizon only, where a low sun's glitter path lies: nearer, the ripples
    # caught it as a lone golden blob on the near water (CAM_7 at sunset)
    glit = T.mul(glit, T.smooth(T.dot(inc, up), 0.10, 0.03))
    gcol = T.ramp(T.mrange(sd, 0.99, 1.0, 0, 1), [(0.0, (1.0, 0.12, 0.55)), (1.0, (1.0, 0.75, 0.25))])
    moon_at = T.comb(T.attr("rt_moon_x"), T.attr("rt_moon_y"), T.attr("rt_moon_z"))
    md = T.dot(Rv, T.vmath("NORMALIZE", T.vmath("SUBTRACT", moon_at, pos)) if GRAFT else tuple(MOON_C))
    mglit = T.mul(T.mul(T.smooth(md, 0.990, 0.998), 0.6), T.mul(T.attr("vj_moon"), sun["Moon"]))    # a hard step: specks
    mglit = T.mul(mglit, T.sub(1.0, T.mul(T.math("MINIMUM", T.math("MAXIMUM", T.attr("vj_eclipse"), 0.0), 1.0),
                                          T.mul(T.phase()["Night"], 0.9))))     # an eclipsed moon casts no glitter
    nightw = T.phase()["Night"]
    crestk = T.mul(T.mul(crest, T.mrange(fres, 0.0, 0.6, 0.12, 1.0)), T.mul(T.addf(0.12, T.mul(T.attr("rt_beat"), 0.1)), T.sub(1.0, nightw)))   # none at night: water does not glow
    crestc = (0.9, 0.15, 0.75)
    # no shallow tint: the shore's crisp line is on the land (exact per pixel), and a tint over every sandbank showed
    # as surf blotches by day and cyan ones at night (CAM_10)
    # the water's own deep violet by day and at dusk; near black at night, where water only reflects (T-night): at
    # 0.022 blue it lit every river and the sea as a flat glowing violet slab (CAM_1, CAM_8)
    # by day a deep teal-indigo, the sea's colour from orbit (S8): its own violet read as grey under the sky (CAM_10)
    deep = T.mix(nightw, T.mix(T.phase()["Twilight"], SEA_DAY, (0.004, 0.0, 0.022)), (0.0006, 0.0, 0.003))
    col = T.add(deep, T.scale(gcol, glit), T.scale((0.7, 0.65, 1.0), mglit), T.scale(crestc, crestk))   # no shock foam
    # lakes and rivers: the mirrored land is about sea level, so they reflect the sky themselves, by Fresnel: seen
    # from above they are dark (half the sky everywhere made a raised pool a bright glassy bowl, CAM_1 and CAM_8)
    # The mirrored land does not reach them, so near the horizon they reflect the valley's hills as a band of the
    # land's colour (pink by day, violet at dusk, dark at night): the sky alone read as muddy slate grey (CAM_1)
    lsky = T.group(g_base, Direction=to_local(T, Rv))["Color"]
    rzl = T.sep(to_local(T, Rv))[2]
    ph_l = T.phase()
    # the night hills at (0.02, 0.007, 0.035) (round 9): the ripple-tilted rzl threw (0.07, 0.025, 0.12) across the river in
    # noise-shaped violet patches (CAM_1 night blotches, round 8)
    hillc = T.mix(ph_l["Night"], T.mix(ph_l["Twilight"], (0.55, 0.12, 0.38), (0.22, 0.05, 0.25)), (0.02, 0.007, 0.035))
    lsky = T.mix(T.smooth(rzl, 0.3, 0.03), T.vmath("MULTIPLY", lsky, (0.92, 0.78, 1.0)), hillc)
    lrefl = T.mul(T.mul(T.mrange(fres, 0.0, 1.0, 0.12, 0.94), bands), T.attr("vj_water"))
    col = T.add(col, T.scale(lsky, T.mul(T.mul(lrefl, 0.7), lake)))
    # and the real sky in them at night: the violet ripples alone read as a flat slab (CAM_1)
    col = T.add(col, T.scale(star_map(T, Rv), T.mul(T.mul(lrefl, lake), T.mul(T.mul(nightw, T.attr("vj_stars")), 0.6))))
    # at night the violet horizon glow in the ripples, sea and rivers alike: the night sky alone left the water a flat
    # black slab (CAM_1, CAM_7). Reflected light, not its own: it follows the ripple bands and Fresnel, so only water
    # seen toward the horizon carries it. A floor of 0.3 lit the near water as a flat glowing violet slab (round 5)
    col = T.add(col, T.scale((0.02, 0.007, 0.04), T.mul(T.mul(T.mul(nightw, bands), T.mrange(fres, 0.0, 0.5, 0.0, 1.0)),     # at
    # 0.07 blue it read as violet cloud-like blotches over the far water (CAM_1 night, round 6)
                                                         T.smooth(rzl, 0.2, 0.02))))     # where it mirrors the horizon
    alpha = T.math("SUBTRACT", 1.0, refl)
    alpha = T.math("MAXIMUM", alpha, T.mul(crest, 0.2))
    alpha = T.math("MAXIMUM", alpha, lake)
    # toward space the orbit look's sea; across GLOBE_BAND the globe takes its pixels over
    sp = eye_space(T)
    col = T.mix(sp, col, orbit_look(T, pos, inc, up, up, 0.0, depth, 0.0, sun))
    alpha = T.mul(T.math("MAXIMUM", alpha, T.math("MINIMUM", T.mul(sp, 4.0), 1.0)), T.sub(1.0, globe_share(T)))
    # distance haze toward the horizon sky only: the fog bank (VJ_Fog) per water pixel cost a third of the frame
    # (scene-perf), and the land seen through the water carries its own fog
    ix, iy, _ = T.sep(to_local(T, T.vmath("SCALE", inc, scale=-1.0)))
    hsky = T.group(g_base, Direction=T.comb(ix, iy, 0.02))["Color"]
    col = T.mix(T.mul(T.mul(T.smooth(vdist, WATER_HAZE[0], WATER_HAZE[1]), T.mul(T.attr("vj_haze"), 0.85)), T.sub(1.0, sp)), col, hsky)
    # the volume fog: EEVEE does not apply volumes over a blended surface, so a fogged valley showed its river clear
    # (CAM_1). The fog in front of the water, along the view ray at the ray's mean height over the valley floor, as
    # fog_build lays it out, in the fog's colour for the time of day
    cam_w = T.comb(T.attr("rt_cam_x"), T.attr("rt_cam_y"), T.attr("rt_cam_z"))
    floor_w = fog_floor(T, pos)
    zm = T.mul(T.addf(T.math("MAXIMUM", T.sub(alt, floor_w), 0.0), T.math("MAXIMUM", T.sub(planet_frame(T, cam_w)[1], floor_w), 0.0)), 0.5)
    sig = T.mul(T.mul(T.mul(T.math("POWER", T.math("MAXIMUM", T.attr("vj_fog"), 0.0), 1.5), FOG_DENSITY), T.attr("rt_fog_k")),
                fog_layer(T, zm, fog_top(T, 0.5)))
    clear_w = T.attr("rt_fog_clear")
    # from 25 m: the near water carries no froxel artefacts (the volume's own clear zone keeps them off the sky), and
    # a low camera over a river sees mostly water within the clear zone (CAM_1: f1 left the river unfogged)
    tau = T.mul(sig, T.math("MAXIMUM", T.sub(vdist, T.math("MINIMUM", T.mul(clear_w, 0.6), 25.0)), 0.0))
    fogk = T.mul(T.sub(1.0, T.math("EXPONENT", T.mul(tau, -1.0))), T.sub(1.0, sp))
    fog_rad = fog_look(T)[2]
    col = T.mix(fogk, col, fog_rad)
    alpha = T.math("MAXIMUM", alpha, fogk)
    em = T.node("ShaderNodeEmission")
    T.feed(em.inputs["Color"], finish(T, col, fog=False))
    tr = T.node("ShaderNodeBsdfTransparent")
    mx = T.node("ShaderNodeMixShader")
    T.feed(mx.inputs[0], alpha)
    T.feed(mx.inputs[1], tr.outputs[0])
    T.feed(mx.inputs[2], em.outputs[0])
    T.feed(out.inputs["Surface"], mx.outputs[0])
    m.surface_render_method = "BLENDED"
    m.displacement_method = "DISPLACEMENT"
    # every water layer (overlap on), front faces only: all water faces point outward, so a back face is the underside
    # of water far behind, seen where a view ray left the sea sphere again (bright blotches on the near water)
    m.use_backface_culling = True


m_water = bpy.data.materials.new("Sea")
m_water.use_nodes = True
water_shader(m_water)


def backdrop_build(T):
    """Opaque sphere under the sea: the sea's reflection (sea_reflection), so the ocean shows a reflection beyond the
    mirrored land too."""
    geo = T.node("ShaderNodeNewGeometry")
    return finish(T, sea_reflection(T, geo.outputs["Position"], geo.outputs["Incoming"]), fog=False)


m_backdrop = emission_mat("Sea Backdrop", backdrop_build)
m_backdrop.use_backface_culling = True


def atmosphere_mat():
    m = bpy.data.materials.new("Atmosphere")
    m.use_nodes = True
    T = NT(m.node_tree)
    for nd in list(T.n):
        if nd.type != "OUTPUT_MATERIAL":
            T.n.remove(nd)
    out = [nd for nd in T.n if nd.type == "OUTPUT_MATERIAL"][0]
    # a limb glow, not a lit shell: the shell is only a canvas past the limb. Each view ray's closest approach to the
    # planet's centre (b) gives the glow, brightest where the ray grazes the limb (b = R), fading over about two pixels
    # outward and one inward at any distance, so it is concentric by construction (S3, S9). Pale pink-lavender on the sun
    # side, none on the night side, a warm pink-orange band only where the terminator meets the limb. A lit shell laid a
    # glossy sheen over the disc and stood off the limb as crescents (user: "the atmosphere is too weird")
    geo = T.node("ShaderNodeNewGeometry")
    dist = T.node("ShaderNodeCameraData").outputs["View Distance"]
    eye = T.vmath("ADD", geo.outputs["Position"], T.vmath("SCALE", geo.outputs["Incoming"], scale=dist))
    ray = T.vmath("SCALE", geo.outputs["Incoming"], scale=-1.0)
    oc = T.vmath("SUBTRACT", tuple(CENTER), eye)
    near_ = T.vmath("ADD", eye, T.vmath("SCALE", ray, scale=T.dot(oc, ray)))
    rel_ = T.vmath("SUBTRACT", near_, tuple(CENTER))
    b_ = T.vmath("LENGTH", rel_)
    px_ = T.math("MAXIMUM", T.mul(dist, 0.0011), 20.0)        # a pixel at the limb, in metres
    out_ = T.math("EXPONENT", T.math("DIVIDE", T.math("MAXIMUM", T.sub(b_, R), 0.0), T.mul(px_, -1.6)))
    in_ = T.math("EXPONENT", T.math("DIVIDE", T.math("MAXIMUM", T.sub(R, b_), 0.0), T.mul(px_, -0.8)))
    glow = T.mul(out_, in_)
    ns = T.dot(T.vmath("NORMALIZE", rel_), T.group(g_sun)["Dir"])
    term = T.mul(T.smooth(ns, -0.25, 0.0), T.sub(1.0, T.smooth(ns, 0.0, 0.25)))
    # the warm band dimmer and fading out twice as fast past the limb: as bright as the day side, its tail stood out over
    # the dark night limb as "ears" (S9)
    col = T.add(T.scale((0.92, 0.72, 1.0), T.mul(T.smooth(ns, -0.05, 0.4), 0.9)), T.scale((1.0, 0.50, 0.32), T.mul(T.mul(term, out_), 0.7)))
    amt = T.mul(T.mul(glow, eye_space(T)), T.addf(1.0, T.mul(T.attr("vj_level"), 0.5)))
    em = T.node("ShaderNodeEmission")
    T.feed(em.inputs["Color"], finish(T, T.scale(col, amt), fog=False))
    add = T.node("ShaderNodeAddShader")
    T.feed(add.inputs[0], T.node("ShaderNodeBsdfTransparent").outputs[0])
    T.feed(add.inputs[1], em.outputs[0])
    T.feed(out.inputs["Surface"], add.outputs[0])
    m.surface_render_method = "BLENDED"
    m.use_backface_culling = True
    return m


m_atmo = atmosphere_mat()


# ================================================================ prop materials
def pyr_build(T):
    geo = T.node("ShaderNodeNewGeometry")
    Nn = geo.outputs["Normal"]
    zl = T.gattr("pz")
    sun = T.group(g_sun)
    lam_s = T.math("MAXIMUM", T.dot(Nn, sun["Dir"]), 0.0)
    lam_k = T.math("MAXIMUM", T.dot(Nn, key_dir(T, sun)), 0.0)
    lit = T.ramp(zl, [(0.0, (0.85, 0.06, 0.42)), (0.55, (1.0, 0.20, 0.22)), (1.0, (1.0, 0.45, 0.10))])
    lit = T.scale(lit, T.mul(T.mul(T.math("POWER", lam_s, 1.2), 0.95), sun["Day"]))
    key = T.scale((0.42, 0.06, 0.70), T.mul(lam_k, T.addf(0.25, T.mul(zl, 0.6))))
    col = T.add((0.014, 0.003, 0.045), lit, key)
    col = T.scale(col, T.mrange(T.math("FRACT", T.mul(zl, 26.0)), 0.0, 0.12, 0.55, 1.0))
    col = T.scale(col, T.mrange(zl, 0.0, 0.3, 0.45, 1.0))
    cap = T.smooth(zl, 0.90, 0.93)
    capc = T.scale((1.0, 0.72, 0.25), T.addf(2.2, T.mul(T.attr("rt_beat"), 4.0)))
    ph = T.phase()
    col = T.mix(cap, T.scale(col, T.mrange(ph["Twilight"], 0.0, 1.0, 1.0, 0.45)), capc)
    col = T.mix(ph["Night"], col, T.mix(cap, T.scale(col, 0.04), capc))
    # neon edges: the island's wireframe-modifier tubes, here the Wireframe node on the same faces
    wf = T.node("ShaderNodeWireframe", use_pixel_size=True)
    wf.inputs["Size"].default_value = 1.6
    ecol = T.ramp(zl, [(0.0, (0.05, 0.85, 1.0)), (1.0, (1.0, 0.25, 0.95))])
    glow = T.addf(T.addf(T.addf(2.6, T.mul(ph["Night"], 1.8)), T.mul(ph["Twilight"], 1.0)), T.mul(T.attr("rt_beat"), 7.0))
    glow = T.mul(glow, T.mrange(ph["Night"], 0.0, 1.0, 1.0, 0.08))     # a slight glow at night, like the wires: white and cyan
    # outlines were too bright (CAM_2)
    col = T.mix(wf.outputs["Fac"], col, T.scale(ecol, glow))
    # /vj/pyramids raises them from the ground on the GPU (no geometry re-evaluation)
    vd_ = T.node("ShaderNodeVectorDisplacement", space="OBJECT")
    vd_.inputs["Midlevel"].default_value = 0.0
    T.feed(vd_.inputs["Vector"], T.scale(T.gattr("rise", "Vector"), T.sub(1.0, T.math("MAXIMUM", T.attr("vj_pyramids"), 0.001))))
    T.feed([nd for nd in T.n if nd.type == "OUTPUT_MATERIAL"][0].inputs["Displacement"], vd_.outputs["Displacement"])
    col = T.mix(eye_space(T), col, (0.10, 0.025, 0.14))     # from space dim violet stone: no glowing specks on the globe,
    # and black ones read as holes (the pull-out at 10 km)
    # a mirrored pyramid (under the sea) shows only within MIRROR_REACH of the camera, like the land's mirror copy: a
    # view ray dipping under the near sea met mirrored pyramid groups kilometres away, as white specks on it (CAM_10)
    pos = geo.outputs["Position"]
    cam_m = T.comb(T.attr("rt_cam_x"), T.attr("rt_cam_y"), T.attr("rt_cam_z"))
    far_m = T.mul(T.math("LESS_THAN", planet_frame(T, pos)[1], -0.5),
                  T.math("GREATER_THAN", T.vmath("DISTANCE", pos, cam_m), MIRROR_REACH))
    return finish(T, col), T.mul(T.sub(1.0, far_m), T.sub(1.0, globe_share(T)))     # the globe from space


def palm_build(T):
    geo = T.node("ShaderNodeNewGeometry")
    kind = T.gattr("pc")
    sun, ph = T.group(g_sun), T.phase()
    ndv = T.math("ABSOLUTE", T.dot(geo.outputs["Normal"], geo.outputs["Incoming"]))
    trunk = (0.05, 0.008, 0.07)
    frond = T.ramp(T.gattr("pt"), [(0.0, (0.02, 0.20, 0.22)), (1.0, (0.05, 0.75, 0.70))])
    col = T.mix(kind, trunk, frond)
    rim = T.mul(T.math("POWER", T.sub(1.0, ndv), 2.5), T.addf(T.mul(sun["Day"], 0.8), T.mul(ph["Twilight"], 0.6)))
    col = T.add(T.scale(col, T.mrange(ph["Twilight"], 0.0, 1.0, 1.0, 0.3)), T.scale((1.0, 0.25, 0.6), rim))
    col = T.mix(ph["Night"], col, T.scale(col, 0.04))     # dark crowns at night: only the wires and the capstones glow (T-night)
    return finish(T, col)


PINK, LIGHT, PALE, BLACK, LEG = (1.0, 0.13, 0.38), (1.0, 0.26, 0.50), (1.0, 0.80, 0.78), (0.02, 0.0, 0.02), (1.0, 0.22, 0.42)
FL_SCALE = 3.2


def flamingo_build(T):
    geo = T.node("ShaderNodeNewGeometry")
    N, inc = geo.outputs["Normal"], geo.outputs["Incoming"]
    c = T.gattr("fcol", "Color")
    sun, ph = T.group(g_sun), T.phase()
    ndv = T.math("ABSOLUTE", T.dot(N, inc))
    key = T.math("ABSOLUTE", T.dot(N, key_dir(T, sun)))
    light = T.mul(T.addf(0.32, T.mul(key, 0.8)), T.mrange(ph["Twilight"], 0.0, 1.0, 1.0, 0.35))
    rim = T.mul(T.math("POWER", T.math("SUBTRACT", 1.0, ndv), 3.0), T.addf(T.mul(sun["Day"], 0.7), T.mul(ph["Twilight"], 0.6)))
    # /vj/flamingos shrinks them into their feet on the GPU; at dusk (the island's rt_flock flight clock) they are gone
    vd_ = T.node("ShaderNodeVectorDisplacement", space="OBJECT")
    vd_.inputs["Midlevel"].default_value = 0.0
    obj = T.node("ShaderNodeTexCoord").outputs["Object"]
    keep = T.mul(T.math("MINIMUM", T.math("MAXIMUM", T.attr("vj_flamingos"), 0.0), 1.0), T.mrange(T.attr("rt_flock"), 0.5, 6.0, 1.0, 0.0))
    T.feed(vd_.inputs["Vector"], T.scale(obj, T.sub(keep, 1.0)))
    T.feed([nd for nd in T.n if nd.type == "OUTPUT_MATERIAL"][0].inputs["Displacement"], vd_.outputs["Displacement"])
    return finish(T, T.add(T.scale(c, light), T.scale((1.0, 0.55, 0.40), rim)))


m_pyr = emission_mat("Pyramid", pyr_build)
m_pyr.displacement_method = "DISPLACEMENT"
m_palm = emission_mat("Palm", palm_build)
m_fl = emission_mat("Flamingo", flamingo_build)
m_fl.displacement_method = "DISPLACEMENT"


# ================================================================ flamingo mesh (the island's standing bird)
def fl_tube(pts, r, col, sides=4):
    pts = [Vector(p) for p in pts]
    vs, fs = [], []
    for k_, p_ in enumerate(pts):
        tg = (pts[min(k_ + 1, len(pts) - 1)] - pts[max(k_ - 1, 0)]).normalized()
        upv = Vector((0, 0, 1)) if abs(tg.z) < 0.9 else Vector((0, 1, 0))
        a = tg.cross(upv).normalized()
        b = tg.cross(a)
        vs += [tuple(p_ + (a * math.cos(2 * math.pi * i / sides) + b * math.sin(2 * math.pi * i / sides)) * r) for i in range(sides)]
    for k_ in range(len(pts) - 1):
        fs += [(k_ * sides + i, k_ * sides + (i + 1) % sides, (k_ + 1) * sides + (i + 1) % sides, (k_ + 1) * sides + i) for i in range(sides)]
    return vs, fs, col


def fl_loft(tip0, rings, tip1, col, sides=6):
    vs = [tip0]
    for x_, zc, ry, rz in rings:
        vs += [(x_, ry * math.cos(2 * math.pi * i / sides), zc + rz * math.sin(2 * math.pi * i / sides)) for i in range(sides)]
    vs.append(tip1)
    n_, last = len(rings), len(vs) - 1
    fs = [(0, 1 + (i + 1) % sides, 1 + i) for i in range(sides)]
    for k_ in range(n_ - 1):
        fs += [(1 + k_ * sides + i, 1 + k_ * sides + (i + 1) % sides, 1 + (k_ + 1) * sides + (i + 1) % sides, 1 + (k_ + 1) * sides + i) for i in range(sides)]
    fs += [(1 + (n_ - 1) * sides + i, 1 + (n_ - 1) * sides + (i + 1) % sides, last) for i in range(sides)]
    return vs, fs, col


def fl_mesh(name, parts):
    V, F, Cc = [], [], []
    for vs, fs, col in parts:
        o = len(V)
        V += [tuple(v) for v in vs]
        F += [tuple(i + o for i in f) for f in fs]
        Cc += [col] * len(vs)
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(c * FL_SCALE for c in v) for v in V], [], F)
    at = me.color_attributes.new("fcol", "FLOAT_COLOR", "POINT")
    for i, c in enumerate(Cc):
        at.data[i].color = (*c, 1.0)
    me.materials.append(m_fl)
    return me


c_parts = coll("Planet Parts")
fl_ob = bpy.data.objects.new("Flamingo", fl_mesh("Flamingo", [
    fl_loft((0.36, 0, 1.06), [(0.22, 1.08, 0.12, 0.13), (0.0, 1.07, 0.16, 0.16), (-0.22, 1.10, 0.12, 0.12)], (-0.44, 0, 1.16), PINK),
    fl_tube([(0.24, 0, 1.12), (0.34, 0, 1.30), (0.30, 0, 1.50), (0.17, 0, 1.64), (0.19, 0, 1.80), (0.28, 0, 1.87)], 0.035, LIGHT),
    fl_loft((0.39, 0, 1.875), [(0.34, 1.885, 0.04, 0.045), (0.28, 1.88, 0.045, 0.05)], (0.24, 0, 1.885), LIGHT),
    fl_tube([(0.38, 0, 1.875), (0.45, 0, 1.85), (0.48, 0, 1.80)], 0.022, PALE),
    fl_tube([(0.48, 0, 1.80), (0.49, 0, 1.75)], 0.016, BLACK),
    fl_tube([(0.0, 0.05, 0.95), (0.03, 0.05, 0.50), (0.0, 0.05, -0.40)], 0.016, LEG),
    fl_tube([(0.0, -0.05, 0.95), (0.06, -0.05, 0.68), (-0.06, -0.05, 0.80)], 0.015, LEG),
]))
c_parts.objects.link(fl_ob)
c_parts.hide_render = True
c_parts.hide_viewport = True

# ================================================================ objects
c_planet = coll("Planet")
c_hidden = coll("Planet Data")
anchor = bpy.data.objects.new("LOD_Anchor", None)
anchor.empty_display_size = 200.0
c_planet.objects.link(anchor)
sky_frame = bpy.data.objects.new("Sky_Frame", None)    # the shot's ground point and local axes; sun, moon, nebula and fog ride on it
sky_frame.empty_display_size = 500.0
c_planet.objects.link(sky_frame)
if GRAFT:
    for name in ("Sun", "Sun_Corona", "Moon", "Nebula"):
        if name in S.objects:
            S.objects[name].parent = sky_frame


def gn_object(name, group, collection, **inputs):
    ob = bpy.data.objects.new(name, bpy.data.meshes.new(name))
    collection.objects.link(ob)
    mod = ob.modifiers.new("Planet", "NODES")
    mod.node_group = group
    ids = {it.name: it.identifier for it in group.interface.items_tree if getattr(it, "in_out", "") == "INPUT"}
    for k_, v in inputs.items():
        getattr(mod.properties.inputs, ids[k_]).value = v
    return ob


hydro = gn_object("Planet_Hydro", g_hyd, c_hidden)
c_hidden.hide_render = True
c_hidden.hide_viewport = True

# --- land: patches, carved terrain, mirror copy about sea level
g_land, G, gi, go = gn_group("PL_Land", LOD_INPUTS + [("Mirror Distance", "NodeSocketFloat", MIRROR_REACH + PATCH_M),
                                                    ("Sites", "NodeSocketObject", None)], [("Geometry", "NodeSocketGeometry")])
anc, hmesh, rivers = lod_inputs(G, gi)
pts = patch_points(G, anc, gi["Detail"], gi["Min Level"], gi["Max Level"], gi["Cull"], gi["Cull Altitude"], gi["Mirror Distance"])
mesh = patch_mesh(G, pts, LMAX)
dvec = patch_dir(G)
sf = G.group(g_surf, Dir=dvec, Hydro=hmesh, Rivers=rivers, **{"River Water": river_near(G, dvec, anc)})
mesh = G.store(mesh, "pl_w", sf["Water"])
soi_l = G.node("GeometryNodeObjectInfo")       # the pyramid sites' lights seen from high up, as on the globe (orbit_look)
G.feed(soi_l.inputs["Object"], gi["Sites"])
i2p_l = G.node("GeometryNodeInstancesToPoints")
G.feed(i2p_l.inputs["Instances"], soi_l.outputs["Geometry"])
px_l = G.node("GeometryNodeProximity", target_element="POINTS")
G.feed(px_l.inputs["Target"], i2p_l.outputs["Points"])
G.feed(px_l.inputs["Source Position"], G.vmath("ADD", G.vmath("SCALE", dvec, scale=G.addf(R, sf["Height"])), tuple(CENTER)))
mesh = G.store(mesh, "pl_city", G.mul(G.math("SUBTRACT", 1.0, G.math("MINIMUM", G.math("DIVIDE", px_l.outputs["Distance"], SITE_GLOW), 1.0)),
                                      px_l.outputs["Is Valid"]))
land = G.setpos(mesh, G.vmath("ADD", G.vmath("SCALE", dvec, scale=G.addf(R, sf["Height"])), tuple(CENTER)))
facet_n = G.node("ShaderNodeTexWhiteNoise", noise_dimensions="3D")     # one shade per triangle: the low-poly facets
G.feed(facet_n.inputs["Vector"], G.vmath("SCALE", G.pos(), scale=0.37))
land = G.store(land, "pl_facet", facet_n.outputs["Value"], domain="FACE")
land = cell_triangles(G, land)     # after pl_facet: both triangles of a cell keep its one shade
rel = G.vmath("SUBTRACT", G.pos(), tuple(CENTER))
mirr = G.delete(land, G.math("LESS_THAN", G.read("pl_mir"), 0.5))
mirr = G.setpos(mirr, G.vmath("ADD", G.vmath("SCALE", G.vmath("NORMALIZE", rel), scale=G.sub(2.0 * R, G.vmath("LENGTH", rel))), tuple(CENTER)))
flipf = G.node("GeometryNodeFlipFaces")
G.feed(flipf.inputs[0], stitch(G, mirr, ("pl_w",)))
land = G.store(stitch(G, land, ("pl_w",)), "mirror", 0.0)
mirr = G.store(flipf.outputs[0], "mirror", 1.0)
G.feed(go["Geometry"], shade(G, G.join(land, mirr), m_terrain, smooth=True))

# --- water: the same patches at the water level (sea, lakes, rivers), dry faces removed
g_water, G, gi, go = gn_group("PL_Water", LOD_INPUTS, [("Geometry", "NodeSocketGeometry")])
anc, hmesh, rivers = lod_inputs(G, gi)
pts = patch_points(G, anc, gi["Detail"], gi["Min Level"], gi["Max Level"], gi["Cull"], gi["Cull Altitude"], 0.0)
mesh = patch_mesh(G, pts, LMAX)
dvec = patch_dir(G)
sf = G.group(g_surf, Dir=dvec, Hydro=hmesh, Rivers=rivers, **{"River Water": river_near(G, dvec, anc)})
mesh = G.store(mesh, "pl_depth", G.sub(sf["Water"], sf["Height"]))
mesh = G.store(mesh, "pl_flow", sf["Flow"], "FLOAT_VECTOR")
mesh = G.setpos(mesh, G.vmath("ADD", G.vmath("SCALE", dvec, scale=G.addf(R, sf["Water"])), tuple(CENTER)))
mesh = stitch(G, mesh, ("pl_depth",))
wetf = G.math("MINIMUM", G.math("MAXIMUM", G.addf(G.read("pl_depth"), 1.0), 0.0), 1.0)   # face average > 0: some corner is wet
mesh = G.delete(mesh, G.math("LESS_THAN", wetf, 0.001), "FACE")
mesh = cell_triangles(G, mesh)     # the land's triangles, so water and shore meet on the same faces; wet test per cell as before
G.feed(go["Geometry"], shade(G, mesh, m_water))

# --- reflection backdrop and atmosphere shell
g_shell, G, gi, go = gn_group("PL_Shell", [("Radius", "NodeSocketFloat", R), ("Subdivisions", "NodeSocketInt", 5),
                                            ("Material", "NodeSocketMaterial", None), ("Inward", "NodeSocketBool", False)],
                               [("Geometry", "NodeSocketGeometry")])
ico = G.node("GeometryNodeMeshIcoSphere")
G.feed(ico.inputs["Radius"], gi["Radius"])
G.feed(ico.inputs["Subdivisions"], gi["Subdivisions"])
flip_ = G.node("GeometryNodeFlipFaces")
G.feed(flip_.inputs["Mesh"], ico.outputs["Mesh"])
G.feed(flip_.inputs["Selection"], gi["Inward"])
sm = G.node("GeometryNodeSetMaterial")
G.feed(sm.inputs["Geometry"], G.transform(flip_.outputs[0], t=tuple(CENTER)))
G.feed(sm.inputs["Material"], gi["Material"])
G.feed(go["Geometry"], sm.outputs[0])

# --- props, scattered on a fixed icosphere so they never move with the LOD
PLAZA_PT = tuple(CENTER + Vector((PLAZA[0], PLAZA[1], R)).normalized() * R)


def scatter(G, sel, per_km2, seed, hmesh, rivers, extra=None):
    """Random sites on the icosphere faces in sel, plus the points in extra; returns (points, surface, direction)."""
    ico = G.node("GeometryNodeMeshIcoSphere")
    ico.inputs["Radius"].default_value = R
    ico.inputs["Subdivisions"].default_value = 6
    dp = G.node("GeometryNodeDistributePointsOnFaces", distribute_method="RANDOM")
    G.feed(dp.inputs["Mesh"], ico.outputs["Mesh"])
    if sel is not None:
        G.feed(dp.inputs["Selection"], sel)
    dp.inputs["Density"].default_value = per_km2 * 1e-6
    dp.inputs["Seed"].default_value = seed
    pts = dp.outputs["Points"] if extra is None else G.join(dp.outputs["Points"], extra)
    dv = G.vmath("NORMALIZE", G.pos())
    return pts, G.group(g_surf, Dir=dv, Hydro=hmesh, Rivers=rivers), dv


def place(G, pts, ok, dv, ground, inst, fixed=None):
    """Keeps the points where ok, sets them on the ground, aligned to the radial up with a random turn and size."""
    pts = G.delete(pts, G.math("LESS_THAN", ok, 0.5))
    pts = G.setpos(pts, G.vmath("ADD", G.vmath("SCALE", dv, scale=G.addf(R, ground)), tuple(CENTER)))
    up_ = G.vmath("NORMALIZE", G.vmath("SUBTRACT", G.pos(), tuple(CENTER)))
    al = G.node("FunctionNodeAlignRotationToVector", axis="Z")
    G.feed(al.inputs["Vector"], up_)
    rnd = G.node("ShaderNodeTexWhiteNoise", noise_dimensions="3D")
    G.feed(rnd.inputs["Vector"], G.vmath("SCALE", G.pos(), scale=0.0137))
    free = 1.0 if fixed is None else G.sub(1.0, fixed)
    spin = G.node("FunctionNodeEulerToRotation")
    G.feed(spin.inputs[0], G.comb(0.0, 0.0, G.mul(G.mul(rnd.outputs["Value"], 2 * math.pi), free)))
    rr = G.node("FunctionNodeRotateRotation", rotation_space="LOCAL")
    G.feed(rr.inputs["Rotation"], al.outputs[0])
    G.feed(rr.inputs["Rotate By"], spin.outputs[0])
    sc_ = G.mrange(rnd.outputs["Value"], 0.0, 1.0, 0.75, 1.25) if fixed is None else G.fmix(fixed, G.mrange(rnd.outputs["Value"], 0.0, 1.0, 0.75, 1.25), 1.0)
    iop = G.node("GeometryNodeInstanceOnPoints")
    G.feed(iop.inputs["Points"], pts)
    G.feed(iop.inputs["Instance"], inst)
    G.feed(iop.inputs["Rotation"], rr.outputs[0])
    G.feed(iop.inputs["Scale"], G.comb(sc_, sc_, sc_))
    return iop.outputs[0]


# pyramid groups all over the planet, on dry flat lowland away from the rivers: static, evaluated once
g_sites, G, gi, go = gn_group("PL_Sites", [("Hydro", "NodeSocketObject", None), ("Hero", "NodeSocketBool", True),
                                            ("Keep Out", "NodeSocketFloat", 0.0)], [("Geometry", "NodeSocketGeometry")])
hmesh, rivers = hydro_inputs(G, gi)


def unit_pyramid():
    cone = G.node("GeometryNodeMeshCone", fill_type="NGON")
    cone.inputs["Vertices"].default_value = 4
    cone.inputs["Radius Top"].default_value = 0.0
    cone.inputs["Radius Bottom"].default_value = math.sqrt(2.0)
    cone.inputs["Depth"].default_value = 1.27
    # the Cone node's base already sits at z = 0: a lift by half the depth, for a cone centred on the origin, put every
    # site pyramid 0.635 x its size over its ground (15 to 29 m), and its capstone glow over the upper half
    g_ = G.transform(cone.outputs["Mesh"], r=(0, 0, math.pi / 4))
    return G.store(g_, "pz", G.math("DIVIDE", G.sep(G.pos())[2], 1.27))


PYR_PARTS = ((0.0, 0.0, 46.0, 8.0), (82.0, 140.0, 36.0, -6.0), (-60.0, 235.0, 24.0, 14.0))   # m offset, size, turn


def pyr_part(ox, oy, sz, rz):
    g_ = G.transform(unit_pyramid(), t=(ox, oy, -1.5), r=(0, 0, math.radians(rz)), s=(sz, sz, sz))
    g_ = G.store(g_, "rise", G.comb(0.0, 0.0, G.mul(G.sep(G.pos())[2], -1.0)), "FLOAT_VECTOR")
    sm = G.node("GeometryNodeSetMaterial")
    G.feed(sm.inputs["Geometry"], g_)
    sm.inputs["Material"].default_value = m_pyr
    return sm.outputs[0]



hero = G.node("GeometryNodePoints")          # the hero group on the plaza, where the island's Pyramid_A stood
G.feed(hero.inputs["Count"], gi["Hero"])
hero.inputs["Position"].default_value = tuple(Vector((138.0, -150.0, R)).normalized() * R)
pts, s_, dv = scatter(G, None, 0.9, 3, hmesh, rivers, G.store(hero.outputs[0], "hero", 1.0))
isher = G.read("hero")
dry = G.sub(s_["Height"], s_["Water"])
world = G.vmath("ADD", G.pos(), tuple(CENTER))
ok = G.mul(G.mul(G.math("GREATER_THAN", dry, 6.0), G.math("LESS_THAN", s_["Height"], 70.0)),
           G.mul(G.math("LESS_THAN", s_["Mountain"], 0.08), G.math("LESS_THAN", s_["Channel"], 0.01)))
ok = G.mul(ok, G.math("GREATER_THAN", G.vmath("DISTANCE", world, PLAZA_PT), gi["Keep Out"]))
# each pyramid of a group stands on its own ground (they spread up to 240 m: at the group's one height the far
# ones floated over rolling ground), and only where that ground is dry
up_s = G.vmath("NORMALIZE", dv)
t1 = G.vmath("NORMALIZE", G.vmath("CROSS_PRODUCT", up_s, (0.31, 0.52, 0.79)))
t2 = G.vmath("CROSS_PRODUCT", up_s, t1)
parts = []
for ox, oy, sz, rz in PYR_PARTS:
    dk = G.vmath("NORMALIZE", G.add(G.vmath("SCALE", up_s, scale=R), G.vmath("SCALE", t1, scale=ox), G.vmath("SCALE", t2, scale=oy)))
    sk = G.group(g_surf, Dir=dk, Hydro=hmesh, Rivers=rivers)
    okk = G.mul(ok, G.mul(G.math("GREATER_THAN", G.sub(sk["Height"], sk["Water"]), 3.0), G.math("LESS_THAN", sk["Channel"], 0.01)))
    parts.append(place(G, pts, G.math("MAXIMUM", okk, isher), dk, sk["Height"], pyr_part(0.0, 0.0, sz, rz), fixed=isher))
G.feed(go["Geometry"], G.join(*parts))

# palm groves near water and flamingo flocks in the shallows next to pyramids, around the LOD anchor
g_props, G, gi, go = gn_group("PL_Props", [("Anchor", "NodeSocketObject", None), ("Hydro", "NodeSocketObject", None),
                                            ("Sites", "NodeSocketObject", None), ("Flamingo", "NodeSocketObject", None),
                                            ("Distance", "NodeSocketFloat", 5000.0), ("Flock Near", "NodeSocketFloat", 1500.0),
                                            ("Keep Out", "NodeSocketFloat", 0.0)],
                              [("Geometry", "NodeSocketGeometry")])
anc, hmesh, rivers = lod_inputs(G, gi)


def curve_line(a, b, count):
    ln_ = G.node("GeometryNodeCurvePrimitiveLine")
    ln_.inputs["Start"].default_value = a
    ln_.inputs["End"].default_value = b
    rs_ = G.node("GeometryNodeResampleCurve")
    G.feed(rs_.inputs["Curve"], ln_.outputs[0])
    rs_.inputs["Count"].default_value = count
    return rs_.outputs[0]


def sweep(curve, profile, radius):
    scr = G.node("GeometryNodeSetCurveRadius")
    G.feed(scr.inputs["Curve"], curve)
    G.feed(scr.inputs["Radius"], radius)
    c2m = G.node("GeometryNodeCurveToMesh")
    G.feed(c2m.inputs["Curve"], scr.outputs[0])
    G.feed(c2m.inputs["Profile Curve"], profile)
    return c2m.outputs[0]


fac = G.node("GeometryNodeSplineParameter").outputs["Factor"]
trunk = G.setpos(curve_line((0, 0, 0), (0, 0, 12.0), 6), offset=G.comb(G.mul(G.math("POWER", G.math("DIVIDE", G.sep(G.pos())[2], 12.0), 2.0), 1.6), 0.0, 0.0))
circ = G.node("GeometryNodeCurvePrimitiveCircle")
circ.inputs["Resolution"].default_value = 4
circ.inputs["Radius"].default_value = 0.32
trunk = G.store(sweep(trunk, circ.outputs[0], G.sub(1.0, G.mul(fac, 0.4))), "pc", 0.0)
frond_c = G.setpos(curve_line((0, 0, 0), (4.6, 0, 0), 5), offset=G.comb(0.0, 0.0, G.sub(G.mul(G.math("SINE", G.mul(fac, 1.9)), 1.3), G.mul(G.mul(fac, fac), 2.6))))
blade = G.node("GeometryNodeCurvePrimitiveLine")
blade.inputs["Start"].default_value = (0, -0.7, 0)
blade.inputs["End"].default_value = (0, 0.7, 0)
frond = G.store(G.store(sweep(frond_c, blade.outputs[0], G.sub(1.0, G.mul(fac, 0.85))), "pc", 1.0), "pt", fac)
palm = G.join(trunk, *(G.transform(frond, t=(1.6, 0, 12.0), r=(math.radians(10.0 * ((i % 3) - 1)), math.radians(-12.0 + 8.0 * (i % 2)), 2 * math.pi * i / 6 + 0.3 * i))
                       for i in range(6)))
grove = G.join(*(G.transform(palm, t=(math.cos(2.4 * i) * (8.0 + 5.0 * i), math.sin(2.4 * i) * (8.0 + 5.0 * i), -1.5),
                             r=(0, 0, 1.3 * i), s=(1.0, 1.0, 0.75 + 0.06 * i)) for i in range(7)))
sm = G.node("GeometryNodeSetMaterial")
G.feed(sm.inputs["Geometry"], grove)
sm.inputs["Material"].default_value = m_palm
grove = sm.outputs[0]
fli = G.node("GeometryNodeObjectInfo")
G.feed(fli.inputs["Object"], gi["Flamingo"])
fli.inputs["As Instance"].default_value = True
flock_pts = G.node("GeometryNodePoints")
flock_pts.inputs["Count"].default_value = 14
fi = G.index()
G.feed(flock_pts.inputs["Position"], G.comb(G.mul(G.math("COSINE", G.mul(fi, 2.4)), G.mul(G.math("SQRT", fi), 5.5)),
                                            G.mul(G.math("SINE", G.mul(fi, 2.4)), G.mul(G.math("SQRT", fi), 5.5)), -0.6))
eul = G.node("FunctionNodeEulerToRotation")
G.feed(eul.inputs[0], G.comb(0.0, 0.0, G.mul(fi, 1.7)))
fiop = G.node("GeometryNodeInstanceOnPoints")
G.feed(fiop.inputs["Points"], flock_pts.outputs[0])
G.feed(fiop.inputs["Instance"], fli.outputs["Geometry"])
G.feed(fiop.inputs["Rotation"], eul.outputs[0])
flock = fiop.outputs[0]

world = G.vmath("ADD", G.pos(), tuple(CENTER))
nearf = G.math("LESS_THAN", G.vmath("DISTANCE", world, anc), gi["Distance"])
pts, s_, dv = scatter(G, nearf, 6.0, 7, hmesh, rivers)
dry = G.sub(s_["Height"], s_["Water"])
ok = G.mul(G.mul(G.math("GREATER_THAN", dry, 0.8), G.math("LESS_THAN", dry, 14.0)),
           G.mul(G.math("LESS_THAN", s_["Height"], 90.0), G.math("LESS_THAN", s_["Mountain"], 0.3)))
# no grove (palms spread 40 m round its point) at a set's anchor, which is the camera of a fixed shot: a trunk stood
# right in front of a low camera and cut a third of the frame
ok = G.mul(ok, G.math("GREATER_THAN", G.vmath("DISTANCE", G.vmath("ADD", G.pos(), tuple(CENTER)), anc), PALM_CLEAR))
palms = place(G, pts, ok, dv, s_["Height"], grove)
soi = G.node("GeometryNodeObjectInfo")
G.feed(soi.inputs["Object"], gi["Sites"])
i2p = G.node("GeometryNodeInstancesToPoints")
G.feed(i2p.inputs["Instances"], soi.outputs["Geometry"])
prox = G.node("GeometryNodeProximity", target_element="POINTS")
G.feed(prox.inputs["Target"], i2p.outputs["Points"])
G.feed(prox.inputs["Source Position"], world)
by_pyr = G.math("LESS_THAN", prox.outputs["Distance"], G.addf(gi["Flock Near"], 300.0))
pts, s_, dv = scatter(G, G.mul(nearf, by_pyr), 4.0, 11, hmesh, rivers)
dry = G.sub(s_["Height"], s_["Water"])
world = G.vmath("ADD", G.pos(), tuple(CENTER))
prox2 = G.node("GeometryNodeProximity", target_element="POINTS")
G.feed(prox2.inputs["Target"], i2p.outputs["Points"])
G.feed(prox2.inputs["Source Position"], world)
ok = G.mul(G.mul(G.math("GREATER_THAN", dry, -1.2), G.math("LESS_THAN", dry, -0.15)),
           G.math("LESS_THAN", prox2.outputs["Distance"], gi["Flock Near"]))
ok = G.mul(ok, G.math("GREATER_THAN", G.vmath("DISTANCE", world, PLAZA_PT), gi["Keep Out"]))
flocks = place(G, pts, ok, dv, G.math("MAXIMUM", s_["Height"], s_["Water"]), flock)
G.feed(go["Geometry"], G.join(palms, flocks))

# --- reflections of instances: each one mirrored about the sea surface under it (radially, like the land)
g_refl, G, gi, go = gn_group("PL_Reflect", [("Geometry", "NodeSocketGeometry", None)], [("Geometry", "NodeSocketGeometry")])
u_ = G.vmath("NORMALIZE", G.vmath("SUBTRACT", G.pos(), tuple(CENTER)))
ux, uy, uz = G.sep(u_)
d2 = G.mul(G.addf(R, G.dot(u_, tuple(CENTER))), 2.0)         # x' = (I - 2uu^T) x + 2 (R + C.u) u
cm_ = G.node("FunctionNodeCombineMatrix")
uu = (ux, uy, uz)
for col in range(3):
    for row in range(3):
        G.feed(cm_.inputs[col * 4 + row], G.addf(1.0 if row == col else 0.0, G.mul(G.mul(uu[row], uu[col]), -2.0)))
    G.feed(cm_.inputs[12 + col], G.mul(uu[col], d2))
mm = G.node("FunctionNodeMatrixMultiply")
G.feed(mm.inputs[0], cm_.outputs[0])
G.feed(mm.inputs[1], G.node("GeometryNodeInstanceTransform").outputs[0])
sit = G.node("GeometryNodeSetInstanceTransform")
G.feed(sit.inputs[0], gi["Geometry"])
G.feed(sit.inputs["Transform"], mm.outputs[0])
G.feed(go["Geometry"], G.join(gi["Geometry"], sit.outputs[0]))

# --- graft: flamingo flocks planet-wide in the shallows next to pyramids, as points for the island's flight (Flamingo Flock)
g_birds, G, gi, go = gn_group("PL_FlockBirds", [("Anchor", "NodeSocketObject", None), ("Hydro", "NodeSocketObject", None),
                                                 ("Sites", "NodeSocketObject", None), ("Pyramids", "NodeSocketObject", None),
                                                 ("Distance", "NodeSocketFloat", 5000.0), ("Flock Near", "NodeSocketFloat", FLOCK_NEAR)],
                              [("Geometry", "NodeSocketGeometry")])
anc, hmesh, rivers = lod_inputs(G, gi)
soi = G.node("GeometryNodeObjectInfo")
G.feed(soi.inputs["Object"], gi["Sites"])
spots = G.node("GeometryNodeObjectInfo")      # the island's pyramids as fixed spots: the live ones move with every shockwave
G.feed(spots.inputs["Object"], gi["Pyramids"])
i2p = G.node("GeometryNodeInstancesToPoints")
G.feed(i2p.inputs["Instances"], soi.outputs["Geometry"])
m2p = G.node("GeometryNodeMeshToPoints")
G.feed(m2p.inputs["Mesh"], spots.outputs["Geometry"])
pyr_pts = G.join(i2p.outputs["Points"], m2p.outputs["Points"])


def near_pyramid(radius):
    px_ = G.node("GeometryNodeProximity", target_element="POINTS")
    G.feed(px_.inputs["Target"], pyr_pts)
    G.feed(px_.inputs["Source Position"], G.vmath("ADD", G.pos(), tuple(CENTER)))
    return G.math("LESS_THAN", px_.outputs["Distance"], radius)


nearf = G.math("LESS_THAN", G.vmath("DISTANCE", G.vmath("ADD", G.pos(), tuple(CENTER)), anc), gi["Distance"])
pts, s_, dv = scatter(G, G.mul(nearf, near_pyramid(G.addf(gi["Flock Near"], 300.0))), FLOCK_DENSITY, 11, hmesh, rivers)
dry = G.sub(s_["Height"], s_["Water"])
ok = G.mul(G.mul(G.math("GREATER_THAN", dry, -1.8), G.math("LESS_THAN", dry, -0.1)), near_pyramid(gi["Flock Near"]))
centres = G.delete(pts, G.math("LESS_THAN", ok, 0.5))
centres = G.setpos(centres, G.vmath("ADD", G.vmath("SCALE", dv, scale=G.addf(R, G.math("MAXIMUM", s_["Height"], s_["Water"]))), tuple(CENTER)))


def rnd(scale, offset):
    wn_ = G.node("ShaderNodeTexWhiteNoise", noise_dimensions="3D")
    G.feed(wn_.inputs["Vector"], G.vmath("ADD", G.vmath("SCALE", G.pos(), scale=scale), offset))
    return wn_.outputs["Value"]


for name, v in (("f_fdir", G.addf(math.pi / 2, G.mul(G.sub(rnd(0.0131, (1, 0, 0)), 0.5), 0.9))),     # into the sunset, like the island's
                ("f_head", G.mul(G.sub(rnd(0.0131, (0, 2, 0)), 0.5), 2 * math.pi)),
                ("f_delay", G.mul(rnd(0.0131, (0, 0, 3)), 3.0)),
                ("f_count", G.addf(FLOCK_SIZE[0], G.math("FLOOR", G.mul(rnd(0.0131, (4, 0, 0)), FLOCK_SIZE[1] - FLOCK_SIZE[0] + 1.0))))):
    centres = G.store(centres, name, v)
pattern = G.node("GeometryNodePoints")       # bird spots on a golden-angle spiral, about 5 m apart
pattern.inputs["Count"].default_value = FLOCK_SIZE[1]
bi = G.index()
G.feed(pattern.inputs["Position"], G.comb(G.mul(G.math("COSINE", G.mul(bi, 2.39996)), G.mul(G.math("SQRT", bi), 5.2)),
                                          G.mul(G.math("SINE", G.mul(bi, 2.39996)), G.mul(G.math("SQRT", bi), 5.2)), 0.0))
al = G.node("FunctionNodeAlignRotationToVector", axis="Z")
G.feed(al.inputs["Vector"], G.vmath("NORMALIZE", G.vmath("SUBTRACT", G.pos(), tuple(CENTER))))
iop = G.node("GeometryNodeInstanceOnPoints")
G.feed(iop.inputs["Points"], centres)
G.feed(iop.inputs["Instance"], G.store(pattern.outputs[0], "f_bi", bi))
G.feed(iop.inputs["Rotation"], al.outputs[0])
real = G.node("GeometryNodeRealizeInstances")
G.feed(real.inputs[0], iop.outputs[0])
birds = G.delete(real.outputs[0], G.math("GREATER_THAN", G.addf(G.read("f_bi"), 0.5), G.read("f_count")))
birds = G.store(birds, "heading", G.addf(G.read("f_head"), G.mul(G.sub(rnd(0.37, (5, 0, 0)), 0.5), 1.2)))
birds = G.store(birds, "fdir", G.addf(G.read("f_fdir"), G.mul(G.sub(rnd(0.37, (0, 6, 0)), 0.5), 0.16)))
birds = G.store(birds, "delay", G.addf(G.read("f_delay"), G.mul(rnd(0.37, (0, 0, 7)), 2.5)))
birds = G.store(birds, "phase", rnd(0.37, (8, 8, 0)))
p2v = G.node("GeometryNodePointsToVertices")
G.feed(p2v.inputs[0], birds)
G.feed(go["Geometry"], p2v.outputs[0])

def planetize_flock(g):
    """The island's flight (Flamingo Flock) climbs along world z and turns about it: right at the pole only.
    Offsets and bird rotations turn into each bird's local frame (radial up)."""
    T = NT(g)

    def align():
        a_ = T.node("FunctionNodeAlignRotationToVector", axis="Z")
        T.feed(a_.inputs["Vector"], T.vmath("NORMALIZE", T.vmath("SUBTRACT", T.pos(), tuple(CENTER))))
        return a_.outputs[0]

    for n in [n for n in T.n if n.bl_idname == "GeometryNodeSetPosition"]:
        if n.inputs["Offset"].is_linked:
            rv = T.node("FunctionNodeRotateVector")
            T.feed(rv.inputs["Vector"], n.inputs["Offset"].links[0].from_socket)
            T.feed(rv.inputs["Rotation"], align())
            T.feed(n.inputs["Offset"], rv.outputs[0])
    for n in [n for n in T.n if n.bl_idname == "GeometryNodeInstanceOnPoints"]:
        if n.inputs["Rotation"].is_linked:
            rr = T.node("FunctionNodeRotateRotation", rotation_space="LOCAL")
            T.feed(rr.inputs["Rotation"], align())
            T.feed(rr.inputs["Rotate By"], n.inputs["Rotation"].links[0].from_socket)
            T.feed(n.inputs["Rotation"], rr.outputs[0])


land_ob = gn_object("Planet", g_land, c_planet, Anchor=anchor, Hydro=hydro, **{"Max Level": LMAX})     # about 6 m cells close to the camera
water_ob = gn_object("Water", g_water, c_planet, Anchor=anchor, Hydro=hydro, **{"Min Level": 1, "Max Level": LMAX})
sites_ob = gn_object("Planet_Sites", g_sites, c_planet, Hydro=hydro, Hero=not GRAFT, **{"Keep Out": 1200.0 if GRAFT else 0.0})
mod_ = land_ob.modifiers[0]           # the land's site lights (pl_city) read the sites
getattr(mod_.properties.inputs, next(it.identifier for it in g_land.interface.items_tree
                                     if getattr(it, "in_out", "") == "INPUT" and it.name == "Sites")).value = sites_ob
props_ob = gn_object("Props", g_props, c_planet, Anchor=anchor, Hydro=hydro, Sites=sites_ob, Flamingo=None if GRAFT else fl_ob)
for ob in (sites_ob, props_ob):
    ob.modifiers.new("Reflections", "NODES").node_group = g_refl
if GRAFT:   # one flamingo system: the island's flight on flocks wherever shallows lie next to pyramids
    # not "Pyramid_*": the island runtime moves every object with that prefix each frame (shockwave), which re-evaluated the flock scatter
    spots_me = bpy.data.meshes.new("Spots_Pyramids")
    spots_me.from_pydata([tuple(o.location) for o in S.objects if o.name.startswith("Pyramid_")], [], [])
    spots_ob = bpy.data.objects.new("Spots_Pyramids", spots_me)
    c_hidden.objects.link(spots_ob)
    # Flock_Birds (loose points) is baked per camera set (lod_sets) and removed. The runtime copies the set's points
    # into the island's Flamingos mesh on each cut: a GN link from the per-frame flight to it re-evaluated the flock
    # scatter every frame (about 30 ms)
    birds_ob = gn_object("Flock_Birds", g_birds, c_planet, Anchor=anchor, Hydro=hydro, Sites=sites_ob, Pyramids=spots_ob)
    fob = S.objects["Flamingos"]
    flight = fob.modifiers[0].node_group
    planetize_flock(flight)
    fob.data.clear_geometry()
    fob.modifiers.new("Reflections", "NODES").node_group = g_refl
    lm = S.objects.get("Land_Mirror")     # the island's flat mirror stays for its own pyramids by the pole only
    if lm:
        lm.instance_collection = bpy.data.collections["Pyramids"]
# the reflection backdrop: a sphere just under the sea, facing inward. A view ray that crosses the sea without meeting
# the mirrored land leaves the sphere again further out, at the same angle to its surface as where it went in, so the
# backdrop there shows the reflection for that angle. A backdrop 700 m down (facing out) caught only rays dipping more
# than 17 deg: the rest met the far water's underside (pale patches), and its edge curved across the near water (CAM_10)
underside_ob = gn_object("Sea_Underside", g_shell, c_planet, Radius=R - 0.5, Subdivisions=5, Material=m_backdrop, Inward=True)
atmo_ob = gn_object("Atmosphere", g_shell, c_planet, Radius=R + ATMO_SHELL, Subdivisions=6, Material=m_atmo)


# ================================================================ the globe: the planet from space (S8, S9)
# One smooth icosphere at sea level (a perfectly round limb), carrying the ground's own surface (PL_Surface) per vertex:
# height, water level, rivers, the pyramid sites, and a relief normal from the height exaggerated GLOBE_RELIEF times.
# The LOD patches from space drew a ragged, faceted limb and blotchy low-resolution land (S9). It takes over across
# GLOBE_BAND (globe_share) and scales to nothing near the ground (no draw cost there)
GLOBE_SUB = 9                  # about 66 m between vertices (Blender's subdivision 9: 655 k vertices)
GLOBE_RELIEF = 2.0             # at 6 the peaks read as white blotches, at 3 the shaded slopes as dark blotches

g_globe, G, gi, go = gn_group("PL_Globe", [("Hydro", "NodeSocketObject", None), ("Sites", "NodeSocketObject", None),
                                            ("Subdivisions", "NodeSocketInt", GLOBE_SUB), ("Material", "NodeSocketMaterial", None)],
                              [("Geometry", "NodeSocketGeometry")])
ico = G.node("GeometryNodeMeshIcoSphere")
ico.inputs["Radius"].default_value = 1.0
G.feed(ico.inputs["Subdivisions"], gi["Subdivisions"])
gdir = G.vmath("NORMALIZE", G.pos())
hmesh_g, rivers_g = hydro_inputs(G, gi)
sf = G.group(g_surf, Dir=gdir, Hydro=hmesh_g, Rivers=rivers_g, **{"River Water": 1.0})
gm = G.store(ico.outputs["Mesh"], "o_h", sf["Height"])
gm = G.store(gm, "o_w", sf["Water"])
prox = G.node("GeometryNodeProximity", target_element="FACES")       # rivers 300 m wide: visible from orbit, like a map's
G.feed(prox.inputs["Target"], rivers_g)
G.feed(prox.inputs["Source Position"], G.vmath("SCALE", gdir, scale=R))
gm = G.store(gm, "o_riv", G.mul(G.math("SUBTRACT", 1.0, G.math("MINIMUM", G.math("MAXIMUM", G.math("DIVIDE", G.sub(prox.outputs["Distance"], 60.0), 90.0), 0.0), 1.0)),
                                 prox.outputs["Is Valid"]))
soi = G.node("GeometryNodeObjectInfo")
G.feed(soi.inputs["Object"], gi["Sites"])
i2p = G.node("GeometryNodeInstancesToPoints")
G.feed(i2p.inputs["Instances"], soi.outputs["Geometry"])
px_ = G.node("GeometryNodeProximity", target_element="POINTS")
G.feed(px_.inputs["Target"], i2p.outputs["Points"])
G.feed(px_.inputs["Source Position"], G.vmath("ADD", G.vmath("SCALE", gdir, scale=G.addf(R, sf["Height"])), tuple(CENTER)))
gm = G.store(gm, "o_city", G.math("SUBTRACT", 1.0, G.math("MINIMUM", G.math("DIVIDE", px_.outputs["Distance"], SITE_GLOW), 1.0)))
gm = G.setpos(gm, G.vmath("SCALE", gdir, scale=G.addf(R, G.math("MAXIMUM", sf["Height"], 0.0))))
gm = G.store(gm, "o_n1", G.node("GeometryNodeInputNormal").outputs[0], dtype="FLOAT_VECTOR")     # the true relief
gm = G.setpos(gm, G.vmath("SCALE", gdir, scale=G.addf(R, G.mul(G.math("MAXIMUM", sf["Height"], 0.0), GLOBE_RELIEF))))
gm = G.store(gm, "o_n", G.node("GeometryNodeInputNormal").outputs[0], dtype="FLOAT_VECTOR")
gm = G.setpos(gm, G.vmath("ADD", G.vmath("SCALE", gdir, scale=R), tuple(CENTER)))
G.feed(go["Geometry"], shade(G, gm, None, smooth=True))
sm_ = next(n for n in G.n if n.type == "SET_MATERIAL" and not n.inputs["Material"].is_linked and n.inputs["Material"].default_value is None)
G.feed(sm_.inputs["Material"], gi["Material"])


def globe_build(T):
    """The globe's look: the ground's palette under the real sun, relief-shaded ridges, rivers and lakes, a deep
    teal-indigo sea with a soft glint, and on the night side the pyramid sites as city lights. No lines: its sphere is
    a proxy under the shaded relief, so its edges would be a dummy wireframe."""
    geo = T.node("ShaderNodeNewGeometry")
    pos, inc = geo.outputs["Position"], geo.outputs["Incoming"]
    up, _ = planet_frame(T, pos)
    sun = T.group(g_sun)
    h, w = T.gattr("o_h"), T.gattr("o_w")
    riv, city = T.gattr("o_riv"), T.gattr("o_city")
    # the globe's own extras grow in over the 12 to 20 km above the band, so at the band it draws exactly the ground's
    # orbit look: its rivers (about 200 m wide, like a map's) and its relief (exaggerated GLOBE_RELIEF times)
    ex = T.smooth(eye_alt(T), GLOBE_BAND[1], GLOBE_BAND[1] + 8000.0)
    n_ = T.vmath("NORMALIZE", T.vmix(ex, T.gattr("o_n1", "Vector"), T.gattr("o_n", "Vector")))
    riv = T.mul(riv, ex)
    cw_ = coast_w(T)
    land = T.mul(T.smooth(T.sub(h, w), T.mul(cw_, -1.0), cw_), T.sub(1.0, T.smooth(riv, 0.3, 0.6)))
    col = orbit_look(T, pos, inc, up, n_, h, T.sub(w, h), land, sun, city)
    mu = T.dot(up, sun["Dir"])
    day = T.smooth(mu, -0.12, 0.18)
    # rivers as cyan threads (in the shallow-sea teal they did not stand out from the land), by day only: mixed in with
    # their unlit colour at night they cut the (since removed) night lattice as black strokes (S9 orbit night, round 6). At 70% over
    # the land, not full: solid, the short coastal rivers read as cyan capsules
    col = T.mix(T.mul(T.smooth(riv, 0.3, 0.7), T.mul(day, 0.7)), col,
                T.scale((0.18, 0.62, 0.72), T.mul(day, T.addf(0.35, T.mul(T.math("MAXIMUM", mu, 0.0), 0.65)))))
    return finish(T, col, fog=False), globe_share(T)


m_globe = emission_mat("Globe", globe_build)
# a sphere at sea level from orbit (a round limb, S9), but the ground's true relief inside the handover band: there
# the patches' mountains stood over the sphere, and their per-pixel dissolve drew a ragged limb and land edge (10 km)
T = NT(m_globe.node_tree)
disp_ = T.node("ShaderNodeDisplacement")
cam_alt = planet_frame(T, T.comb(T.attr("rt_cam_x"), T.attr("rt_cam_y"), T.attr("rt_cam_z")))[1]    # the viewer's (per frame):
# the view ray (eye_alt) is not there when displacement is evaluated
T.feed(disp_.inputs["Height"], T.mul(T.math("MAXIMUM", T.gattr("o_h"), 0.0), T.sub(1.0, T.smooth(cam_alt, GLOBE_BAND[1], GLOBE_BAND[1] + 8000.0))))
disp_.inputs["Midlevel"].default_value = 0.0
disp_.inputs["Scale"].default_value = 1.0
T.feed(next(n for n in T.n if n.type == "OUTPUT_MATERIAL").inputs["Displacement"], disp_.outputs["Displacement"])
m_globe.displacement_method = "DISPLACEMENT"
globe_ob = gn_object("Planet_Globe", g_globe, c_planet, Hydro=hydro, Sites=sites_ob, Material=m_globe)
for i in range(3):     # nothing near the ground (a scale, not a hide: a driven hide rebuilt the depsgraph on every cut)
    driver(globe_ob, "scale", i, "1.0*(sp > 0.3)", {"sp": "rt_space"})


# ================================================================ sun (far beyond the planet, sized to the same angular radius)
def sun_build(T):
    geo = T.node("ShaderNodeNewGeometry")
    ob = T.sep(T.node("ShaderNodeTexCoord").outputs["Object"])
    v, t = ob[2], T.attr("rt_time")
    sun = T.group(g_sun)
    gap = T.mrange(v, 0.2, -1.0, 0.0, 0.85)
    band = T.math("FRACT", T.addf(T.mul(v, 9.0), T.mul(t, 0.3)))
    holes = T.mul(T.mrange(band, T.math("SUBTRACT", gap, 0.04), gap, 1, 0), T.math("GREATER_THAN", gap, 0.01))
    col = T.ramp(T.mrange(v, -1, 1, 0, 1), [(0.00, (1.00, 0.02, 0.40)), (0.38, (1.00, 0.14, 0.22)),
                                            (0.70, (1.00, 0.40, 0.06)), (1.00, (1.00, 0.78, 0.10))])
    mu = T.math("ABSOLUTE", T.dot(geo.outputs["Normal"], geo.outputs["Incoming"]))
    limb = T.addf(0.5, T.mul(T.math("POWER", mu, 0.6), 0.5))
    gran = T.node("ShaderNodeTexVoronoi", voronoi_dimensions="4D", feature="F1")
    T.feed(gran.inputs["Vector"], T.node("ShaderNodeTexCoord").outputs["Object"])
    T.feed(gran.inputs["W"], T.mul(t, 0.12))
    gran.inputs["Scale"].default_value = 22.0
    cells = T.mrange(gran.outputs["Distance"], 0.0, 0.6, 1.06, 0.92)
    k_ = T.mul(T.mul(limb, cells), T.addf(T.addf(1.2, T.mul(T.attr("vj_level"), 0.9)), T.mul(T.attr("rt_beat"), 0.5)))
    alpha = T.mul(T.math("SUBTRACT", 1.0, holes), T.math("GREATER_THAN", sun["Amount"], 0.001))
    return finish(T, T.scale(col, k_), fog=False), alpha


def sphere_mesh(name, segs=96, rings=48):
    import bmesh
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=1.0)
    bm.to_mesh(me)
    bm.free()
    for p_ in me.polygons:
        p_.use_smooth = True
    return me


if not GRAFT:
    sun_ob = bpy.data.objects.new("Sun", sphere_mesh("Sun"))
    sun_ob.data.materials.append(emission_mat("Sun", sun_build))
    sun_ob.data.materials[0].use_backface_culling = True
    sun_ob["sa"], sun_ob["ang"] = 1.0, SUN_R[1]
    c_planet.objects.link(sun_ob)
    sun_ob.parent = sky_frame
    K_ = "min(max(n*2.0, 0.0), 1.0)"
    chain(sun_ob, '["sa"]', None, "min(max(s*(1.0 - %s*%s*(3.0 - 2.0*%s)), 0.0), 1.0)" % (K_, K_, K_), {"s": "vj_sun", "n": "vj_night"})
    Q_ = "min(max((sa - 0.3)/0.7, 0.0), 1.0)"
    chain(sun_ob, '["ang"]', None, "%g + %g*%s*%s*(3.0 - 2.0*%s)" % (SUN_R[0], SUN_R[1] - SUN_R[0], Q_, Q_, Q_), {}, ("sa",))
    chain(sun_ob, "location", 1, "%g*cos(-0.24 + 0.40*sa)" % D_SUN, {}, ("sa",), sun_ob)
    chain(sun_ob, "location", 2, "%g*sin(-0.24 + 0.40*sa)" % D_SUN, {}, ("sa",), sun_ob)
    for i in range(3):
        chain(sun_ob, "scale", i, "%g*tan(ang)" % D_SUN, {}, ("ang",), sun_ob)
else:   # graft: the island's sun, corona and moon, pushed out so the orbit shot keeps them far and in scale
    import re
    for name, k_ in (("Sun", D_SUN / 26000.0), ("Sun_Corona", D_SUN / 26000.0), ("Moon", D_MOON / 21000.0)):
        ob = S.objects.get(name)
        for fc in (ob.animation_data.drivers if ob and ob.animation_data else ()):
            if fc.data_path in ("location", "scale"):
                fc.driver.expression = re.sub(r"^([0-9.]+)\*", lambda m: "%g*" % (float(m.group(1)) * k_), fc.driver.expression)
    # an eclipse shrinks the sun to its sunset size (0.18 rad, the corona with it): by day its 0.30 rad disc stood out
    # round the 0.23 rad moon as a thick striped ring instead of a corona (E1-day)
    # (the island's size goes to "ang0" first: both in one expression passed the 256-character limit)
    sun_ = S.objects["Sun"]
    fc = sun_.animation_data.drivers.find('["ang"]')
    sun_["ang0"] = sun_["ang"]
    chain(sun_, '["ang0"]', None, fc.driver.expression, {}, ("sa",))
    sun_.animation_data.drivers.remove(fc)
    chain(sun_, '["ang"]', None, "ang0 - max(ang0 - 0.18, 0.0)*min(max(e, 0.0), 1.0)", {"e": "vj_eclipse"}, ("ang0",))
    # and the corona grows 0.10 rad past it: at 1.12 of the sun it stayed behind the 0.23 rad moon, a bare black disc
    # at sunset (CAM_7, CAM_9)
    for fc in S.objects["Sun_Corona"].animation_data.drivers:
        if fc.data_path == "scale" and "tan(ang)" in fc.driver.expression:
            e_ = fc.driver.variables.new()
            e_.name, e_.targets[0].id_type = "e", "SCENE"
            e_.targets[0].id, e_.targets[0].data_path = S, '["vj_eclipse"]'
            fc.driver.expression = fc.driver.expression.replace("tan(ang)", "tan(ang + 0.10*min(max(e, 0.0), 1.0))")


# ================================================================ ground fog: the island's volume, density by altitude over the sphere
def box_mesh(name, x0, x1, y0, y1, z0, z1):
    me = bpy.data.meshes.new(name)
    v = [(x_, y_, z_) for z_ in (z0, z1) for y_ in (y0, y1) for x_ in (x0, x1)]
    me.from_pydata(v, [], [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])
    return me


def fog_build(T, pv):
    pos = T.node("ShaderNodeNewGeometry").outputs["Position"]
    P = T.vmath("SUBTRACT", pos, tuple(CENTER))      # world space: the fog stays put when its box follows the shot
    _, pz = planet_frame(T, pos)
    # height over the valley floor, not over the sea: fog lies in every valley and hollow, high ones too, and the
    # ridges stand out of it (one absolute ceiling drew a flat-topped slab over every view, round 2)
    hag = T.sub(pz, fog_floor(T, pos))
    wind = T.scale((0.6, 0.8, 0.0), T.attr("rt_fog_phase"))
    n_ = T.node("ShaderNodeTexNoise", noise_dimensions="4D")
    T.feed(n_.inputs["Vector"], T.scale(T.vmath("SUBTRACT", P, wind), T.math("DIVIDE", 1.0, T.math("MAXIMUM", T.attr("vj_fog_scale"), 10.0))))
    T.feed(n_.inputs["W"], T.mul(T.attr("rt_fog_phase"), 0.004))
    n_.inputs["Scale"].default_value = 1.0
    n_.inputs["Detail"].default_value = 3.0
    big = T.node("ShaderNodeTexNoise")                # the top rolls: its height changes over a kilometre or two
    T.feed(big.inputs["Vector"], T.scale(T.vmath("SUBTRACT", P, T.scale(wind, 0.3)), 1.0 / 1800.0))
    big.inputs["Scale"].default_value = 1.0
    big.inputs["Detail"].default_value = 2.0
    top = fog_top(T, big.outputs["Fac"])
    # billows on the top as deep as the layer (the noise keeps within about 0.3 of its middle) and swells of 500 m, so
    # ridges and pyramid tops stand out of it as islands; at a quarter of that depth the top read as a ruler-straight
    # band from low shots (CAM_3, CAM_10, round 4)
    mid_ = T.node("ShaderNodeTexNoise")
    T.feed(mid_.inputs["Vector"], T.scale(T.vmath("SUBTRACT", P, T.scale(wind, 0.6)), 1.0 / 500.0))
    mid_.inputs["Scale"].default_value = 1.0
    mid_.inputs["Detail"].default_value = 1.0
    hb = T.sub(hag, T.mul(T.addf(T.mul(T.sub(n_.outputs["Fac"], 0.5), 3.0), T.mul(T.sub(mid_.outputs["Fac"], 0.5), 2.5)), top))
    # rays steeper than about 11 deg meet only the layer, not the haze over it, so the stars stay sharp: a wide fade with
    # no edge. The view ray comes from the camera position (rt_cam_*): Incoming carries no view direction in a volume.
    # On the whole density, it cut a camera's own layer off at its eye level, a ruler-straight fog top (CAM_5 f1)
    cam = T.comb(T.attr("rt_cam_x"), T.attr("rt_cam_y"), T.attr("rt_cam_z"))
    upk = T.dot(T.vmath("NORMALIZE", T.vmath("SUBTRACT", pos, cam)), planet_frame(T, cam)[0])
    hf = T.mul(fog_layer(T, hb, top, T.smooth(upk, 0.2, 0.0)), T.smooth(pz, -1.5, 0.0))      # none under the sea, seen through the water
    # in banks 700 m across with clear gaps between, so the layer reads as a lumpy sea of fog and not one band
    bank_ = T.node("ShaderNodeTexNoise")
    T.feed(bank_.inputs["Vector"], T.scale(T.vmath("SUBTRACT", P, T.scale(wind, 0.8)), 1.0 / 700.0))
    bank_.inputs["Scale"].default_value = 1.0
    bank_.inputs["Detail"].default_value = 1.0
    hf = T.mul(hf, T.addf(0.4, T.mul(T.smooth(bank_.outputs["Fac"], 0.38, 0.62), 0.6)))     # gaps at 0.25 left f1 shots
    # in a gap reading like f0 (CAM_7, CAM_9, round 5)
    patch = T.attr("vj_fog_noise")
    clouds = T.math("MAXIMUM", T.mrange(n_.outputs["Fac"], 0.3, 0.7, T.math("SUBTRACT", 1.0, T.mul(patch, 1.2)), T.addf(1.0, patch), clamp=False), 0.0)
    pump = T.addf(1.0, T.mul(T.attr("rt_beat"), T.attr("vj_fog_beat")))
    # /vj/fog^1.5: at 1 the valleys fill and the far ground goes; 0.5 is a third of that, a haze
    f_ = T.math("POWER", T.math("MAXIMUM", T.attr("vj_fog"), 0.0), 1.5)
    dens = T.mul(T.mul(T.mul(f_, FOG_DENSITY), T.mul(hf, clouds)), T.mul(pump, T.attr("rt_fog_k")))
    # it opens around the camera out to the shot's subject (its fog_clear): EEVEE's froxels within about 150 m of the
    # camera do not hold the sky fade, so fog there veils the sky
    clear = T.attr("rt_fog_clear")
    dens = T.mul(dens, T.smooth(T.vmath("DISTANCE", pos, cam), T.mul(clear, FOG_CLEAR), clear))
    dens = T.mul(dens, T.math("LESS_THAN", T.attr("rt_space"), 0.5))     # valley fog, not from space (no hide: see Land_Mirror)
    T.feed(pv.inputs["Density"], dens)
    pv.inputs["Anisotropy"].default_value = 0.4       # forward scattering: halos round the sun and the lamps (0.6 blinded by day)
    alb, glow, _ = fog_look(T)
    T.feed(pv.inputs["Color"], alb)
    # own light: the sunset glow (the night lattice's cyan light on its lowest metres went with the lattice, round 10)
    # by day the sky's light on it: the scene's only light in the volume is the sun, so away from it the fog went a
    # muddy mauve-grey over the sea (CAM_10 f1), not the white of the reference photos
    ph_f = T.phase()
    skyl = T.scale((0.30, 0.30, 0.35), T.mul(T.sub(1.0, ph_f["Night"]), T.sub(1.0, T.mul(ph_f["Twilight"], 0.6))))   # 0.5 burnt
    # thick fog near a camera into a flat white slab (CAM_2 f1, round 6)
    T.feed(pv.inputs["Emission Color"], T.group(g_col, Color=T.add(T.scale(glow, T.mul(pump, 0.6)), skyl), Strength=1.0)["Color"])
    T.feed(pv.inputs["Emission Strength"], dens)


# real volume fog in both modes: a box under the shot (it rides on Sky_Frame), hidden while /vj/fog is 0 so it
# costs nothing then. In the graft it replaces the island's ray-marched fog bank, which would count the fog twice
FOG_HALF = 4500.0
fog_m = bpy.data.materials.new("Fog")
fog_m.use_nodes = True
T = NT(fog_m.node_tree)
for nd in list(T.n):
    if nd.type != "OUTPUT_MATERIAL":
        T.n.remove(nd)
pv = T.node("ShaderNodeVolumePrincipled")
fog_build(T, pv)
T.feed([nd for nd in T.n if nd.type == "OUTPUT_MATERIAL"][0].inputs["Volume"], pv.outputs[0])
drop = FOG_HALF ** 2 / (2 * R)          # the sphere falls away under a flat box: the box must reach down that far
fog = bpy.data.objects.new("Fog", box_mesh("Fog", -FOG_HALF, FOG_HALF, -FOG_HALF, FOG_HALF, -drop - 40.0, FOG_TOP))
fog.data.materials.append(fog_m)
c_planet.objects.link(fog)
fog.parent = sky_frame
for path in ("hide_viewport", "hide_render"):
    driver(fog, path, None, "v < 0.001", {"v": "vj_fog"})
if GRAFT:
    drop_fog_bank(g_fog)
    no_haze_in_space(g_fog)
    S.eevee.volumetric_samples = 32         # 64 cost the fog 13 fps at CAM_2; 32 looked the same
# 8 px froxels showed as a checker in thick fog (CAM_2), 4 px cost about 1 fps there. The range ends with the fog box:
# an 8 km range veiled the day sky and stretched the depth slices (the night nebula looks the same at 4.5 km)
S.eevee.volumetric_tile_size = "4"   # (round 13) 4 draws a pale band along CAM_5's top edge in fog (rows 0 to 5 at 1.37 x the
# rows under them), 2 and 8 none. 8 costs the same as 4 but brings back the checker in thick fog by day (CAM_2, CAM_5,
# reviewer round 13); 2 costs 8.5 ms (34.8 to 43.3, CAM_2 fog 1). The band stays
S.eevee.volumetric_end = FOG_HALF
S.eevee.volumetric_start = 30.0   # (round 9) from 1 m the 32 slices were 90 to 140 m deep at 300 m, against a fog layer about
# 30 m thick: terraces along the bottom of CAM_4 at fog 1. The fog's density is 0 inside its clear zone (37 m and more)
S.eevee.gi_cubemap_resolution = "128"     # the world probe only lights the fog (every material is emission): it is
# re-rendered on every world swap (day world <-> full world, on cuts into space by day)

# ================================================================ render + compositor
if not GRAFT:
    S.render.engine = "BLENDER_EEVEE"
    S.render.resolution_x, S.render.resolution_y, S.render.resolution_percentage = 1920, 1080, 100
    S.render.fps = 60
    S.frame_start, S.frame_end = 1, 216000
    S.sync_mode = "FRAME_DROP"
    S.view_settings.view_transform = "Standard"
    S.view_settings.look = "None"
    ee = S.eevee
    for attr, val in (("taa_samples", 4), ("taa_render_samples", 16), ("use_shadows", False),
                      ("use_raytracing", False), ("use_gtao", False), ("use_motion_blur", False),
                      ("volumetric_start", 1.0), ("volumetric_end", FOG_HALF), ("volumetric_tile_size", "4"),
                      ("volumetric_samples", 32), ("volumetric_sample_distribution", 0.85),
                      ("use_volumetric_shadows", False)):
        if hasattr(ee, attr):
            try:
                setattr(ee, attr, val)
            except Exception:
                pass
    cg = bpy.data.node_groups.new("VJ Bloom", "CompositorNodeTree")
    cg.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    rl = cg.nodes.new("CompositorNodeRLayers")
    gout = cg.nodes.new("NodeGroupOutput")
    glr = cg.nodes.new("CompositorNodeGlare")
    glr.inputs["Type"].default_value = "Bloom"
    glr.inputs["Quality"].default_value = "Medium"
    glr.inputs["Highlights Threshold"].default_value = 1.0
    glr.inputs["Strength"].default_value = 0.7
    glr.inputs["Size"].default_value = 0.6
    cg.links.new(rl.outputs["Image"], glr.inputs["Image"])
    cg.links.new(glr.outputs["Image"], gout.inputs[0])
    S.compositing_node_group = cg

# ================================================================ cameras, placed on the evaluated planet
c_cam = bpy.data.collections.get("Cameras") if GRAFT else coll("Cameras")
planet_centre = bpy.data.objects.new("Planet_Centre", None)
planet_centre.location = CENTER
c_cam.objects.link(planet_centre)


def add_camera(name, lens, clip=(1.0, 250000.0), lod="surface"):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start, cd.clip_end = clip
    co = bpy.data.objects.new(name, cd)
    co["lod"] = lod
    c_cam.objects.link(co)
    return co


def add_target(name, loc):
    em = bpy.data.objects.new(name, None)
    em.empty_display_size = 20
    c_cam.objects.link(em)
    em.location = loc
    return em


def track(co, target, local_up=True):
    """Aims the camera at target. With local_up the target's Z is the radial up (it tracks the planet centre),
    so the horizon stays level anywhere on the planet, not just at the pole."""
    con = co.constraints.new("TRACK_TO")
    con.target = target
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    if local_up:
        dt = target.constraints.new("DAMPED_TRACK")
        dt.target = planet_centre
        dt.track_axis = "TRACK_NEGATIVE_Z"
        con.use_target_z = True


def path_curve(name, pts, closed=True):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    spl = cu.splines.new("BEZIER")
    spl.bezier_points.add(len(pts) - 1)
    for bp, p_ in zip(spl.bezier_points, pts):
        bp.co = p_
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    spl.use_cyclic_u = closed
    ob = bpy.data.objects.new(name, cu)
    c_cam.objects.link(ob)
    ob.hide_render = True
    return ob


def follow(co, curve, period):
    con = co.constraints.new("FOLLOW_PATH")
    con.target = curve
    con.use_fixed_location = True
    co.location = (0, 0, 0)
    co["path_period"] = period
    driver(co, 'constraints["%s"].offset_factor' % con.name, None, "p/%g - floor(p/%g)" % (period, period), {"p": "rt_cam_phase"})
    return con


SHAKE = {"s": "rt_shake", "t": "rt_time"}
# per axis: metres at rt_shake 1, rad/s, phase. The island's 1 m at 7-10 Hz, sampled at about 50 fps, read as jitter
SHAKE_AXES = ((0.12, 22.0, 0.0), (0.08, 19.0, 1.3), (0.10, 25.0, 2.1))


def drift(co, ax, az, ph):
    for i, (amp, (sk, sw, sp)) in enumerate(zip(((ax, 0.35, ph), (ax * 0.8, 0.17, ph * 0.6), (az, 0.23, ph * 1.7)), SHAKE_AXES)):
        driver(co, "delta_location", i, "%g*sin(p*%g + %g) + s*%g*sin(t*%g + %g)" % (*amp, sk, sw, sp), {"p": "rt_cam_phase", **SHAKE})


def shake(co):
    for i, (k_, f_, ph_) in enumerate(SHAKE_AXES):
        driver(co, "delta_location", i, "s*%g*sin(t*%g + %g)" % (k_, f_, ph_), SHAKE)


def evaluate(anchor_at):
    anchor.location = anchor_at
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    return dg


def probe(ob, dg, dvec, start=None):
    """ob's first ray hit down along -dvec from 3 km up, on the near side only: a ray that found nothing there went
    on through the planet and stood CAM_7 on its far side."""
    start = start or CENTER + dvec * (R + 3000.0)
    return ob.ray_cast(start, -dvec, distance=(start - (CENTER + dvec * (R - 3000.0))).length, depsgraph=dg)


def land_hit(dg, dvec):
    """The land's ray hit from above along -dvec, past its mirror copies: the sea bed's copy stands over the sea as
    hills as high as the sea is deep (CAM_7 found no water behind its flock and stood on the shore)."""
    me_ = land_ob.evaluated_get(dg).data
    mir_ = me_.attributes["mirror"].data
    hit = probe(land_ob, dg, dvec)
    for _ in range(3):
        if not hit[0] or mir_[me_.polygons[hit[3]].vertices[0]].value < 0.5:
            break
        hit = probe(land_ob, dg, dvec, hit[1] - dvec * 0.01)
    return hit


def land_between(dg, a_, b_):
    """Whether real land (past its mirror copies) lies on the segment from a_ to b_."""
    me_ = land_ob.evaluated_get(dg).data
    mir_ = me_.attributes["mirror"].data
    d_ = (b_ - a_).normalized()
    start, left = a_, (b_ - a_).length
    for _ in range(6):
        hit = land_ob.ray_cast(start, d_, distance=left, depsgraph=dg)
        if not hit[0]:
            return False
        if mir_[me_.polygons[hit[3]].vertices[0]].value < 0.5:
            return True
        left -= (hit[1] - start).length + 0.01
        start = hit[1] + d_ * 0.01
    return False


def ground(dg, dvec):
    """Terrain or water surface along a direction from the planet centre."""
    dvec = Vector(dvec).normalized()
    best = CENTER + dvec * R
    for hit in (land_hit(dg, dvec), probe(water_ob, dg, dvec)):
        if hit[0] and (hit[1] - CENTER).length > (best - CENTER).length:
            best = hit[1]
    return best


def surf(dg, x, y):
    """Ground under the point (x, y) of the pole's tangent plane, where the island's coordinates live."""
    return ground(dg, Vector((x, y, R)))


def up_at(p_):
    return (Vector(p_) - CENTER).normalized()


def water_at(dg, p_):
    """The water surface under p_, or the ground where there is none."""
    dvec = up_at(p_)
    hit = probe(water_ob, dg, dvec)
    return hit[1] if hit[0] else ground(dg, dvec)


SKY_DISTS = list(range(150, 1000, 150)) + list(range(1000, 9001, 500))


def skyline(dg, eye, fwd, spread, dists=SKY_DISTS):
    """Per bearing (tangents off fwd in spread), the highest ground elevation in radians seen from eye."""
    dvec = up_at(eye)
    fwd = (fwd - dvec * fwd.dot(dvec)).normalized()
    side = dvec.cross(fwd)
    return [max(math.asin(max(-1.0, min(1.0, (ground(dg, dvec * R + (fwd + side * s_) * d_) - eye).normalized().dot(dvec))))
                for d_ in dists)
            for s_ in spread]


def pitch_for(sky_, half, share):
    """The frame centre's elevation at which the ground (all of it under each bearing's skyline) fills share of a
    frame half a field of view high."""
    lo_, hi_ = -half, math.radians(60.0)
    for _ in range(30):
        mid_ = (lo_ + hi_) / 2.0
        cover = sum(min(max((e_ - (mid_ - half)) / (2.0 * half), 0.0), 1.0) for e_ in sky_) / len(sky_)
        lo_, hi_ = (mid_, hi_) if cover > share else (lo_, mid_)
    return lo_


def straight_runs(cur, back, ahead, min_hw):
    """River points with `back` points upstream and `ahead` downstream on their own river (points run downstream,
    30 m apart), where that stretch is about straight, so no bank stands between its ends.
    Returns (index, upstream end, downstream end) at sea-level radius."""
    pos = np.array([a.vector[:] for a in cur.attributes["position"].data]) + np.array(CENTER[:])
    hw = np.array([a.value for a in cur.attributes["rhw"].data])
    runs = []
    for c_ in cur.curves:
        a_, n_ = c_.first_point_index, c_.points_length
        for k_ in range(a_ + back, a_ + n_ - ahead):
            if hw[k_] < min_hw:
                continue
            u_, d_ = pos[k_ - back], pos[k_ + ahead]
            ax = (d_ - u_) / max(np.linalg.norm(d_ - u_), 1e-6)
            seg = pos[k_ - back:k_ + ahead + 1] - u_
            if np.linalg.norm(seg - np.outer(seg @ ax, ax), axis=1).max() < 1.5 * hw[k_]:
                runs.append((k_, Vector(u_), Vector(d_)))
    return runs


def tangent_dir(lat_ang, az):
    """Direction at angular distance lat_ang from the pole, azimuth az (0 = +y, toward the sun)."""
    return Vector((math.sin(lat_ang) * math.sin(az), math.sin(lat_ang) * math.cos(az), math.cos(lat_ang)))


for o in (hydro, land_ob, water_ob, props_ob):
    o.update_tag()
dg = evaluate((PLAZA[0], PLAZA[1], 200.0))


def fill_fog_floor(dg):
    """Bakes the valley floor (fog_floor): the hydrology's ground with the sea at 0, its minimum over 1 ring of
    neighbours (about 300 m), smoothed over 2, into the Fog_Floor map, packed into the file. Over 3 rings a river
    20 m up a narrow valley took the floor of the lowland 900 m off and stood over the fog (CAM_1 f1)."""
    from mathutils.kdtree import KDTree
    gs_ = hydro.evaluated_get(dg).evaluated_geometry()     # held: the mesh lives only as long as its geometry set
    hm_ = gs_.mesh
    n_ = len(hm_.vertices)
    co_ = np.empty(n_ * 3)
    hm_.vertices.foreach_get("co", co_)
    co_ = co_.reshape(-1, 3)
    fl = np.empty(n_)
    hm_.attributes["h"].data.foreach_get("value", fl)
    fl = np.maximum(fl, 0.0)
    nb = np.empty((6, n_), dtype=np.int64)
    for k_ in range(6):
        a_ = np.empty(n_, dtype=np.int32)
        hm_.attributes["nb%d" % k_].data.foreach_get("value", a_)
        nb[k_] = np.where((a_ >= 0) & (a_ < n_), a_, np.arange(n_))
    fl = np.minimum(fl, fl[nb].min(axis=0))
    for _ in range(2):
        fl = 0.5 * fl + 0.5 * fl[nb].mean(axis=0)
    kd = KDTree(n_)
    for i, c_ in enumerate(co_):
        kd.insert(c_ / np.linalg.norm(c_), i)
    kd.balance()
    w_, h_ = FOG_FLOOR.size
    px = np.zeros((h_, w_, 4), dtype=np.float32)
    lat = (np.arange(h_) + 0.5) / h_ * math.pi - math.pi / 2
    lon = (np.arange(w_) + 0.5) / w_ * 2 * math.pi - math.pi
    for j_, la in enumerate(lat):
        for i_, lo in enumerate(lon):
            # weighted over the 4 nearest hydrology vertices: the nearest one alone made the floor, and the fog's top
            # over it, step in 260 m terraces (CAM_4 f1, round 6)
            nn_ = kd.find_n((math.sin(la), math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo)), 4)
            ws_ = [1.0 / max(d_, 1e-7) ** 2 for _, _, d_ in nn_]
            px[j_, i_, 0] = sum(w_ * fl[i__] for w_, (_, i__, _) in zip(ws_, nn_)) / sum(ws_)
    px[:, :, 3] = 1.0
    FOG_FLOOR.pixels.foreach_set(px.ravel())
    FOG_FLOOR.file_format = "OPEN_EXR"
    FOG_FLOOR.pack()


fill_fog_floor(dg)
HERO = (138.0, -150.0)            # the island's Pyramid_A
if GRAFT:
    for o in S.objects:          # the island's pyramids stand on the plaza
        if o.name.startswith("Pyramid_"):
            o.location.z = surf(dg, o.location.x, o.location.y).z + 0.4
    HERO = tuple(S.objects["Pyramid_A"].location)[:2]
    pyrs = sorted((o for o in S.objects if o.type == "MESH" and o.name[:8] == "Pyramid_" and len(o.name) == 9), key=lambda o: o.name)
    bpy.context.view_layer.update()
    for i, o in enumerate(pyrs[:PYR_SHADOWS]):
        b_ = o.matrix_world.translation
        for f, v in zip("xyz", b_):
            S["rt_pyr%d_%s" % (i, f)] = v
        S["rt_pyr%d_a" % i] = max(o.dimensions.x, o.dimensions.y) * 0.5
        S["rt_pyr%d_h" % i] = o.dimensions.z
H = surf(dg, *HERO)
UP = up_at(H)
NORTH = (Vector((0.0, 1.0, 0.0)) - UP * UP.y).normalized()
# CAM_0: wide, up the plaza toward the pyramids and the sun
c0 = add_camera("CAM_0", 24.0)
c0.location = surf(dg, HERO[0] - 40.0, HERO[1] - 1350.0) + UP * 70.0
track(c0, add_target("CAM_0_target", c0.location + NORTH * 3000.0 + UP * 120.0))
drift(c0, 6.0, 3.0, 0.0)
# CAM_1: skim low over the nearest river, looking downstream: 9 m over its water 150 m upstream, toward its water
# 750 m downstream (on a bank beside it, the camera looked down into a pool like a glass bowl)
hgeo = hydro.evaluated_get(dg).evaluated_geometry()      # keep the set alive while its curves are read
cur = hgeo.curves
runs = straight_runs(cur, 5, 25, 10.0) if cur is not None and len(cur.points) else []
best = min(runs, key=lambda r_: (r_[1] - Vector(PLAZA_PT)).length) if runs else None
c1 = add_camera("CAM_1", 18.0)
if best:
    _, up_p, dn_p = best
    dg = evaluate(tuple(up_p + up_at(up_p) * 200.0))
    c1.location = max(water_at(dg, up_p) + up_at(up_p) * 9.0, ground(dg, up_at(up_p)) + up_at(up_p) * 4.0,
                      key=lambda q: (q - CENTER).length)
    track(c1, add_target("CAM_1_target", water_at(dg, dn_p) + up_at(dn_p) * 1.0))
else:
    c1.location = surf(dg, HERO[0] + 300.0, HERO[1] - 700.0) + UP * 14.0
    track(c1, add_target("CAM_1_target", c1.location + NORTH * 2000.0))
drift(c1, 3.0, 0.8, 1.3)
dg = evaluate((PLAZA[0], PLAZA[1], 200.0))
# CAM_2: pyramid hero shot; CAM_3: tilt up to the moon over the pyramids
c2 = add_camera("CAM_2", 34.0)      # at 30 mm the striped sun's rim showed in the top-left corner, uncovered at e1
c2.location = surf(dg, HERO[0] - 150.0, HERO[1] - 120.0) + UP * 8.0
track(c2, add_target("CAM_2_target", H + UP * 41.0))
drift(c2, 4.0, 1.5, 2.1)
c3 = add_camera("CAM_3", 28.0)
if GRAFT:   # the night full moon (star_system.py at /vj/night 1) sits on the horizon from the ground (its 50 km orbit is
    # 3 planet radii out), half its 27 deg disc up: CAM_3 stands where the horizon toward it is lowest, the pyramids
    # in between. South-west of them the moon stayed behind the valley's ridge as a cut sliver
    import importlib.util
    spec_ = importlib.util.spec_from_file_location("star_system_build", os.path.join(os.path.dirname(bpy.data.filepath), "star_system.py"))
    ss_ = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(ss_)
    probe_ = H + UP * 8.0
    moon_ = Vector(ss_.solve(tuple(CENTER), R, tuple(probe_), 0.0, 1.0, 1.0, 0.0, 0.0)["moon"])
    m_flat = ((moon_ - probe_) - UP * (moon_ - probe_).dot(UP)).normalized()
    m_side = UP.cross(m_flat)

    sun_ = Vector(ss_.solve(tuple(CENTER), R, tuple(probe_), 0.0, 0.5, 1.0, 0.0, 0.0)["sun"])
    s_flat = (sun_ - UP * sun_.dot(UP)).normalized()

    def horizon_toward(p_, flat_, half_):
        """Highest ground elevation seen from p_ across a body's disc (tangent half_ either side), out to 8 km: along
        its centre line alone, a slope beside it covered a third of the moon (night e1)."""
        return max(skyline(dg, p_, flat_, (-half_, -half_ / 2.0, 0.0, half_ / 2.0, half_),
                           list(range(100, 1000, 100)) + list(range(1000, 8001, 250))))
    # at the pyramids' own level (within 20 m): from the lowest horizon overall it stood on a 330 m hill and looked down.
    # The sunset sun's horizon first (with eclipse 1 the camera holds the moon over the sun, which sits on the horizon:
    # a near slope half-hid it), then the night moon's
    h_pyr = (H - CENTER).length - R
    spots3 = []
    for back_ in (250.0, 350.0, 450.0, 600.0, 800.0, 1000.0):
        for side_ in (-450.0, -300.0, -150.0, 0.0, 150.0, 300.0, 450.0):
            xy_ = H - m_flat * back_ + m_side * side_
            g_ = surf(dg, xy_.x, xy_.y)
            q = g_ + UP * 12.0
            spots3.append((abs((g_ - CENTER).length - R - h_pyr) > 20.0, round(math.degrees(horizon_toward(q, s_flat, 0.18)) / 2.0),
                           horizon_toward(q, m_flat, 0.24), back_, q))
    c3.location = min(spots3, key=lambda r_: (r_[0], r_[1], round(r_[2], 2), r_[3]))[4]
else:
    c3.location = surf(dg, HERO[0] - 260.0, HERO[1] - 420.0) + UP * 6.0
track(c3, add_target("CAM_3_target", H + Vector(MOON_C) * 2500.0))
# while the moon is under the horizon it turns to the pyramids under the sky where the moon will rise (a rig it copies the
# rotation of; the star system moves every TRACK_TO target on the camera itself): at 5 deg over an empty horizon it
# framed blank sky over a flat slab (G3)
rig3 = add_target("CAM_3_hold_rig", tuple(c3.location))
# toward the pyramids, the sky just over the skyline: the ground fills 40% of the frame. Aimed 8 deg over their base
# it framed the ridge behind them, nearly no sky (day and sunset e0)
up3 = up_at(c3.location)
v3 = H - c3.location
flat3 = (v3 - up3 * v3.dot(up3)).normalized()
pitch3 = pitch_for(skyline(dg, c3.location, flat3, (-0.6, -0.3, 0.0, 0.3, 0.6)), math.atan(36.0 * 9.0 / 16.0 / 2.0 / 28.0), 0.4)
track(rig3, add_target("CAM_3_hold", c3.location + (flat3 * math.cos(pitch3) + up3 * math.sin(pitch3)) * 1000.0))
hold3 = c3.constraints.new("COPY_ROTATION")
hold3.target = rig3
c3_up = up_at(c3.location)
for k_ in ("rt_moon_x", "rt_moon_y", "rt_moon_z"):
    S[k_] = S.get(k_, 0.0)
# by the moon's top edge (its centre's elevation + its angular radius, 11.5 km at its distance, as a sine): held while
# it is under the skyline toward it, on the moon from 3 deg over it. Toward the night moon the valley walls stand
# about 10 deg high: measured from the level horizon, CAM_3 turned halfway to a moon behind the ridge and framed a
# wire hillside (night e0)
c3_moon_d = "max(((mx-%g)**2 + (my-%g)**2 + (mz-%g)**2)**0.5, 1.0)" % tuple(c3.location)
c3["moon_top"], c3["moon_toward"] = -1.0, 0.0
driver(c3, '["moon_top"]', None, "(((mx-%g)*%g + (my-%g)*%g + (mz-%g)*%g) + %g) / %s"
       % (c3.location.x, c3_up.x, c3.location.y, c3_up.y, c3.location.z, c3_up.z, MOON_R, c3_moon_d),
       {"mx": "rt_moon_x", "my": "rt_moon_y", "mz": "rt_moon_z"})
m3 = (m_flat - c3_up * m_flat.dot(c3_up)).normalized() if GRAFT else c3_up
driver(c3, '["moon_toward"]', None, "((mx-%g)*%g + (my-%g)*%g + (mz-%g)*%g) / %s"
       % (c3.location.x, m3.x, c3.location.y, m3.y, c3.location.z, m3.z, c3_moon_d),
       {"mx": "rt_moon_x", "my": "rt_moon_y", "mz": "rt_moon_z"})
sky3 = math.sin(horizon_toward(c3.location, m_flat, 0.24)) if GRAFT else 0.0
chain(c3, 'constraints["%s"].influence' % hold3.name, None,
      "1.0 - min(max((moon_top - %g*min(max((moon_toward - 0.75)/0.15, 0.0), 1.0))*20.0, 0.0), 1.0)" % sky3, {},
      ("moon_top", "moon_toward"))
print("PLANET CAM_3 skyline toward the night moon %.1f deg" % math.degrees(math.asin(sky3)))
drift(c3, 3.0, 1.0, 3.7)
# CAM_4: flyover loop around the pole, FLY_CLEAR over every hill in its view cone up to 3 km ahead (flying 140 m over
# the ground under it looked into the next hillside)
# 170 m clear and 48% ground: at 120 m and 45% one near ridge filled 55% of the frame (p25, p50, round 5); at 42% the
# open views were 65% blank sky (p0, round 6)
FLY_N, FLY_ANG, FLY_CLEAR, FLY_GROUND, FLY_AHEAD = 24, 0.22, 170.0, 0.48, 0.03     # ground share of the frame
loop_dirs = [tangent_dir(FLY_ANG, 2 * math.pi * i / FLY_N) for i in range(FLY_N)]
need = []
for i, dvec in enumerate(loop_dirs):
    dg = evaluate(tuple(CENTER + dvec * (R + 300.0)))
    nxt = loop_dirs[(i + 1) % FLY_N]
    fwd = (nxt - dvec * nxt.dot(dvec)).normalized()
    side = dvec.cross(fwd)
    need.append(max((ground(dg, dvec * R + fwd * f_ + side * (f_ * s_)) - CENTER).length - R - f_ * f_ / (2 * R)
                    for f_ in range(250, 3001, 250) for s_ in (-0.6, -0.3, 0.0, 0.3, 0.6)))
alts = [max(need[i - 1], need[i], need[(i + 1) % FLY_N], 0.0) + FLY_CLEAR for i in range(FLY_N)]
fly = path_curve("CAM_4_path", [tuple(CENTER + d_ * (R + a_)) for d_, a_ in zip(loop_dirs, alts)])
# the frame centre where the ground covers FLY_GROUND of the frame (40% left 62% blank sky at p0): per bearing across the frame its skyline (the
# highest ground elevation out to 9 km) and all ground under it, seen from where the camera is when it looks at that
# aim point (FLY_AHEAD behind it). A fixed angle over the skyline left a lowland view 65% sky (p0) and a mountain
# wall ahead 60% of the frame (p50)
lag = FLY_AHEAD * FLY_N
aim_pts = []
for j, dj in enumerate(loop_dirs):
    i0 = math.floor(j - lag)
    pa, pb = (CENTER + loop_dirs[k_ % FLY_N] * (R + alts[k_ % FLY_N]) for k_ in (i0, i0 + 1))
    eye = pa.lerp(pb, (j - lag) - i0)
    dvec = up_at(eye)
    to_aim = CENTER + dj * (R + alts[j]) - eye
    fwd = (to_aim - dvec * to_aim.dot(dvec)).normalized()
    dg = evaluate(tuple(CENTER + dvec * (R + 300.0)))
    p4 = pitch_for(skyline(dg, eye, fwd, (-0.8, -0.4, 0.0, 0.4, 0.8)), math.atan(36.0 * 9.0 / 16.0 / 2.0 / 22.0), FLY_GROUND)
    aim_pts.append(tuple(eye + (fwd + dvec * math.tan(p4)) * to_aim.dot(fwd)))
aim_path = path_curve("CAM_4_aim", aim_pts)
c4 = add_camera("CAM_4", 22.0)
follow(c4, fly, 240.0)
c4["lod_path_sets"] = 8          # a 22 km loop: with 3 sets the camera flew up to 3.6 km from its set, over 200 m cells
ahead = add_target("CAM_4_target", (0, 0, 0))
follow(ahead, aim_path, 240.0)
ahead.animation_data.drivers[-1].driver.expression = "(p/240 + %g) - floor(p/240 + %g)" % (FLY_AHEAD, FLY_AHEAD)
track(c4, ahead)
shake(c4)
# CAM_5: orbit the pyramids, lifted over the ground under the circle
dg = evaluate((PLAZA[0], PLAZA[1], 200.0))
ring = []
for i in range(8):
    a = 2 * math.pi * i / 8
    q = surf(dg, HERO[0] + 20.0 + 230.0 * math.cos(a), HERO[1] + 40.0 + 230.0 * math.sin(a))
    ring.append(tuple(q + up_at(q) * max(45.0, (H - CENTER).length - (q - CENTER).length + 45.0)))
c5 = add_camera("CAM_5", 30.0)
follow(c5, path_curve("CAM_5_path", ring), 70.0)
track(c5, add_target("CAM_5_target", surf(dg, HERO[0] + 40.0, HERO[1] + 30.0) + UP * 30.0))
shake(c5)
# CAM_6: orbit, the whole planet in frame
ORBIT = 5.0 * R                  # 80 km: clear of the star system's moon orbit (50 km + 11.5 km moon)
tilt = math.radians(24.0)
orbit = path_curve("CAM_6_path", [tuple(CENTER + Vector((ORBIT * math.cos(a), ORBIT * math.sin(a) * math.cos(tilt), ORBIT * math.sin(a) * math.sin(tilt))))
                                   for a in (2 * math.pi * i / 12 for i in range(12))])
c6 = add_camera("CAM_6", 38.0, clip=(50.0, 400000.0), lod="orbit")      # the lens keeps the planet's size in frame
follow(c6, orbit, 120.0)
track(c6, add_target("CAM_6_target", tuple(CENTER)), local_up=False)
shake(c6)


# CAM_7..CAM_10: shots across the planet, 3.5 to 9 km from the pole (the sky turns with each shot)
def arc(p_):
    return math.acos(max(-1.0, min(1.0, up_at(p_).z))) * R


def local_north(p_):
    u = up_at(p_)
    return (Vector((0.0, 1.0, 0.0)) - u * u.y).normalized()


def instances_of(dg, test):
    return [inst.matrix_world.translation.copy() for inst in dg.object_instances
            if inst.is_instance and test(inst) and (inst.matrix_world.translation - CENTER).length > R - 5.0]   # no reflections


dg = evaluate((0.0, 0.0, 100.0))
far = sorted((q for q in instances_of(dg, lambda i: i.parent and i.parent.name == "Planet_Sites") if 3500.0 < arc(q) < 9000.0),
             key=lambda q: abs(arc(q) - 6500.0))
# CAM_9: a pyramid group far from the valley, the sun behind it
c9 = add_camera("CAM_9", 26.0)
site9 = far[0] if far else surf(dg, 0.0, 6500.0)
dg = evaluate(tuple(site9 + up_at(site9) * 200.0))
c9.location = ground(dg, site9 - local_north(site9) * 380.0 - CENTER) + up_at(site9) * 25.0
track(c9, add_target("CAM_9_target", site9 + up_at(site9) * 35.0))
drift(c9, 4.0, 1.5, 4.4)
if GRAFT:   # it tracks the sun (vj_track): a high sun put the pyramids under the frame. The frame slides down (lens
    # shift, verticals stay) by the Sun Height over 8 deg, up to 14 deg (the star system writes rt_sun_h; a driver
    # built before the property exists stays invalid)
    S["rt_sun_h"] = S.get("rt_sun_h", math.radians(20.0))
    driver(c9.data, "shift_y", None, "-tan(min(max(h - 0.14, 0.0), 0.25))*%g" % (c9.data.lens / 36.0), {"h": "rt_sun_h"})
# CAM_7: a flamingo flock on the water next to pyramids, low, looking toward the sun (close: at 150 m a flamingo
# was 6 px in the preview)
C7_BACK = 55.0
c7 = add_camera("CAM_7", 35.0)


def land_at(dg, p_):
    dvec = up_at(p_)
    hit = land_hit(dg, dvec)
    return hit[1] if hit[0] else CENTER + dvec * R


def toward_sun(p_):
    """The sunset sun's bearing at p_ (local north off the graft): local north missed it by up to 90 deg away from
    the pole, and the sun left the frame."""
    if not GRAFT:
        return local_north(p_)
    s_ = Vector(ss_.solve(tuple(CENTER), R, tuple(p_), 0.0, 0.5, 1.0, 0.0, 0.0)["sun"])
    u_ = up_at(p_)
    return (s_ - u_ * s_.dot(u_)).normalized()


def spot_behind(dg, fc_):
    """The best place behind a flock: (in water over 0.3 m deep, the sunset sun in frame, water all the way to the
    flock, less wet flat in the near frame, turn, distance off C7_BACK, place). Standing on the land behind it, the
    shore curved round the camera as a raised lip (G6); with land between, a channel's banks did. A flat just above
    the water reflects the sky but not the mirrored hills, so it showed as a glassy sheet. With the sun 51 deg off,
    a sunset after the flock had flown was 80% plain sky and water (G3)."""
    def depth(q):
        return (water_at(dg, q) - CENTER).length - (land_at(dg, q) - CENTER).length
    n_ = toward_sun(fc_)
    e_ = up_at(fc_).cross(n_)
    spots = []
    for d_ in (45.0, 60.0, 75.0, 90.0, 110.0):
        for a_ in range(-70, 71, 10):
            dir_ = n_ * math.cos(math.radians(a_)) + e_ * math.sin(math.radians(a_))
            q = fc_ - dir_ * d_
            wet_ = [depth(fc_ - dir_ * t_) for t_ in np.arange(d_, 20.0, -5.0)]
            side_ = up_at(q).cross(dir_)
            flats = [-0.5 < depth(q + (dir_ + side_ * math.tan(math.radians(b_))) * t_) < 0.0
                     for b_ in (-20, -10, 0, 10, 20) for t_ in range(8, 51, 6)] if wet_[0] > 0.3 else [True]
            spots.append((wet_[0] > 0.3, abs(a_) <= 20, min(wet_) > 0.0, -round(sum(flats) / len(flats), 1), -abs(a_),
                          -abs(d_ - C7_BACK), q))
    return max(spots, key=lambda r_: r_[:6])


# flock clusters near the far pyramid groups: the first with a spot in open water and the sun in frame, else the best
flock_c, flock_b, best7 = None, [], None
sites_ = instances_of(dg, lambda i: i.parent and i.parent.name == "Planet_Sites")
seen7 = []
for q in far[:8]:
    dg = evaluate(tuple(q + up_at(q) * 200.0))
    if GRAFT:      # flock spots (the flight's input), before the runtime copies them into Flamingos
        birds = [Vector(v.co) for v in S.objects["Flock_Birds"].evaluated_get(dg).data.vertices if 2500.0 < arc(Vector(v.co))]
    else:
        birds = instances_of(dg, lambda i: i.object.name.startswith("Flamingo") and 2500.0 < arc(i.matrix_world.translation))
    left_ = sorted((b for b in birds if (b - q).length < 1500.0), key=lambda b: (b - q).length)
    while left_ and not (best7 and best7[:4] == (True, True, True, 0.0)):
        b0 = left_[0]
        near_b = [b for b in left_ if (b - b0).length < 40.0]
        left_ = [b for b in left_ if (b - b0).length >= 40.0]
        fc_ = sum(near_b, Vector()) / len(near_b)
        if len(near_b) < 8 or any((fc_ - f_).length < 60.0 for f_ in seen7) or \
                min((s_ - (fc_ - toward_sun(fc_) * C7_BACK)).length for s_ in sites_) < 90.0:
            continue        # a straggler, a flock already tried, or the camera would stand inside a pyramid group
        seen7.append(fc_)
        dg = evaluate(tuple(fc_ + up_at(fc_) * 200.0))
        b7 = spot_behind(dg, fc_)
        if best7 is None or b7[:4] > best7[:4]:
            flock_c, flock_b, best7 = fc_, birds, b7
    if best7 and best7[:4] == (True, True, True, 0.0):
        break
flock_c = flock_c or site9
flock_b = flock_b if flock_c is not site9 else []
dg = evaluate(tuple(flock_c + up_at(flock_c) * 200.0))
n7 = toward_sun(flock_c)
best7 = best7 or spot_behind(dg, flock_c)
print("PLANET CAM_7 from %d flocks: in water %s, sun in frame %s, clear %s, flats %s, turn %s" % ((len(seen7),) + tuple(best7[:5])))
if best7[0]:
    c7.location = water_at(dg, best7[-1]) + up_at(best7[-1]) * 2.5
else:   # no water behind the flock: on the shore itself, at the last dry point toward the flock, 1.8 m up, and at
    # least 18 m from any bird (one bird 5 m away filled the frame)
    shore7 = flock_c - n7 * C7_BACK
    for f_ in np.linspace(0.0, 1.0, 41):
        q = flock_c - n7 * (C7_BACK * (1.0 - f_) + 22.0 * f_)
        if (water_at(dg, q) - CENTER).length - (land_at(dg, q) - CENTER).length > 0.05 or \
                min(((b_ - q).length for b_ in flock_b), default=1e9) < 18.0:
            break
        shore7 = q
    c7.location = ground(dg, shore7 - CENTER) + up_at(shore7) * 1.8
track(c7, add_target("CAM_7_target", flock_c + up_at(flock_c) * 3.0))
drift(c7, 2.0, 0.6, 5.1)
# CAM_8: a river running into the sea, looking downstream
hgeo = hydro.evaluated_get(dg).evaluated_geometry()
cur, hm = hgeo.curves, hgeo.mesh
c8 = add_camera("CAM_8", 22.0)
mouth = None
if cur is not None and len(cur.points):
    # a straight stretch of river 240 m on either side, with the sea 150 to 650 m past it: rivers now come down to the
    # sea at the ESTUARY grade, so the shot looks down the river onto the sea it runs into
    dsea_ = np.array([a.value for a in cur.attributes["dsea"].data])
    cand_ = [r_ for r_ in straight_runs(cur, 6, 6, 6.0) if 120.0 < dsea_[r_[0]] < 700.0 and 1500.0 < arc(r_[1]) < 12000.0
             and (r_[1] - c1.location).length > 2000.0]     # not CAM_1's river
    if cand_:
        mouth = min(cand_, key=lambda r_: abs(dsea_[r_[0]] - 300.0))
if mouth:
    k_, up_p, dn_p = mouth
    dg = evaluate(tuple(dn_p + up_at(dn_p) * 200.0))
    fl = (dn_p - up_p).normalized()
    c8.location = max(water_at(dg, up_p) + up_at(up_p) * 16.0, ground(dg, up_at(up_p)) + up_at(up_p) * 6.0,
                      key=lambda q: (q - CENTER).length)
    track(c8, add_target("CAM_8_target", CENTER + (dn_p + fl * (dsea_[k_] + 300.0) - CENTER).normalized() * R))
else:      # level along the local north (the pole's NORTH tilts up this far out)
    c8.location = surf(dg, 0.0, 5000.0) + up_at(surf(dg, 0.0, 5000.0)) * 30.0
    track(c8, add_target("CAM_8_target", c8.location + local_north(c8.location) * 2000.0 - up_at(c8.location) * 150.0))
drift(c8, 3.0, 1.0, 5.9)
# CAM_10: low pass along a coast, sea on one side. The coast is ragged at the hydrology's 260 m (sea and land
# alternate within a few hundred metres), so no straight coast exists to fly along: the pass runs 300 m out over open
# water past a shore vertex, on the bearing with the most sea under it and land behind, and looks 23 deg toward land
hco = np.array([v.co[:] for v in hm.vertices])
hh_ = np.array([a.value for a in hm.attributes["h"].data])
hds = np.array([a.value for a in hm.attributes["dsea"].data])
harc = np.arccos(np.clip(hco[:, 2] / R, -1.0, 1.0)) * R
coast = np.nonzero((hh_ >= 0.0) & (hh_ < 4.0) & (hds < 300.0) & (harc > 3000.0) & (harc < 10000.0))[0]
c10 = add_camera("CAM_10", 24.0)
if len(coast):
    from mathutils.kdtree import KDTree
    kd = KDTree(len(hco))
    for i, co_ in enumerate(hco):
        kd.insert(co_, i)
    kd.balance()
    h_at = lambda p_: hh_[kd.find(Vector(p_).normalized() * R)[1]]

    def coast_pass(k_):
        """(score, shore point, seaward, along): the best of 24 bearings at shore vertex k_."""
        cpt = Vector(hco[k_])
        u = cpt.normalized()
        e1 = u.cross(Vector((0.0, 0.0, 1.0)) if abs(u.z) < 0.9 else Vector((1.0, 0.0, 0.0))).normalized()
        best_ = (-1, cpt, None, None)
        for i in range(24):
            sw = e1 * math.cos(2 * math.pi * i / 24) + u.cross(e1) * math.sin(2 * math.pi * i / 24)
            al = u.cross(sw)
            s_ = sum(h_at(cpt + sw * 300.0 + al * t) < -1.0 for t in (-500.0, -250.0, 0.0, 250.0, 500.0, 800.0))
            s_ += sum(h_at(cpt + sw * d_) < -1.0 for d_ in (600.0, 900.0, 1300.0))
            s_ += sum(h_at(cpt - sw * 300.0 + al * t) > 0.5 for t in (-250.0, 250.0, 800.0))
            if s_ > best_[0]:
                best_ = (s_, cpt, sw, al)
        return best_
    _, cpt, seaward, along = max((coast_pass(int(k)) + (-abs(harc[k] - 6000.0),) for k in coast), key=lambda r_: (r_[0], r_[4]))[:4]
    dg = evaluate(tuple(CENTER + cpt.normalized() * (R + 200.0)))

    def pass_curve(name, out_m, shift, lower):       # 30 m over the sea, or 25 m over higher ground it crosses
        pts_ = []
        for t in np.linspace(-500.0, 500.0, 5) + shift:
            d_ = (cpt + seaward * out_m + along * t).normalized()
            top = max((ground(dg, (cpt + seaward * out_m + along * (t + dt_)).normalized()) - CENTER).length - R for dt_ in (-150.0, 0.0, 150.0))
            pts_.append(tuple(CENTER + d_ * (R + max(30.0, top + 25.0) - lower)))
        return path_curve(name, pts_, closed=False)
    follow(c10, pass_curve("CAM_10_path", 300.0, 0.0, 0.0), 45.0)
    ahead10 = add_target("CAM_10_target", (0, 0, 0))     # 350 m ahead all the way (an offset on the open path wrapped)
    # aimed 60 m off the shore and 45 m down: 150 m off and 20 m down, the shot was over 60% blank sky and open sea
    follow(ahead10, pass_curve("CAM_10_aim", 60.0, 350.0, 45.0), 45.0)
    track(c10, ahead10)
    shake(c10)
else:
    c10.location = surf(dg, -2000.0, 4000.0) + up_at(surf(dg, -2000.0, 4000.0)) * 30.0
    track(c10, add_target("CAM_10_target", c10.location + local_north(c10.location) * 2000.0 - up_at(c10.location) * 150.0))
# CAM_SYS and the system views (docs/research/synthwave-visual-check.md, System view): the star system from far out.
# CAM_SYS sits on the spin axis (+x): the sun turns about it, so the terminator always faces the frame side-on, and
# the moon's tilted orbit (50 km) stays in frame. The views look from front, back, above and behind the moon (the
# runtime keeps that one on the moon's far side). Outside /vj/cam's range; they share CAM_6's whole-planet set
SYS_D = 165000.0


def sys_cam(name, pos, lens=24.0):
    co = add_camera(name, lens, clip=(100.0, 600000.0), lod="orbit")
    co.location = pos
    co.rotation_euler = (Vector(CENTER) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    co["lod_share"] = "CAM_6"
    return co


c_sys = sys_cam("CAM_SYS", CENTER + Vector((SYS_D, 0.0, 0.0)), lens=40.0)
# the runtime keeps it 25 deg off the line behind the planet from the sun, looking between the planet and the sun:
# the sun and its glare in frame with a lit crescent and the terminator (on the spin axis the sun was 90 deg out).
# 300 km out at 40 mm: at 125 km the moon's orbit needed 16 to 19 mm, which stretched the moon at the frame edge into
# an oval (night e1)
c_sys["pl_sun_rel"] = (300000.0, 25.0, 70000.0)
for name, dvec in (("CAM_SYS_FRONT", (0.0, -1.0, 0.35)), ("CAM_SYS_BACK", (0.0, 1.0, -0.35)), ("CAM_SYS_ABOVE", (0.05, 0.0, 1.0))):
    sys_cam(name, CENTER + Vector(dvec).normalized() * 140000.0)
sys_cam("CAM_SYS_MOON", CENTER + Vector((0.0, 0.0, 90000.0)), lens=30.0)["pl_moon_far"] = 45000.0
# proof shots, not on /vj/cam. The pull-out over the pyramids from CAM_0 (the ground) to 165 km (S8), 60 deg down
# along CAM_0's view: 1 and 10 km on CAM_0's land set, 50 and 165 km on CAM_6's whole planet. And two free views the
# grab aims (G2 LOD rings, S6 celestial poles and the map's seam): one over the plaza, one out in space
up_h = up_at(H)
look_ = H - c0.location
look_ = (look_ - up_h * look_.dot(up_h)).normalized()
for name, alt_ in (("CAM_PULL_1K", 1000.0), ("CAM_PULL_10K", 10000.0), ("CAM_PULL_50K", 50000.0), ("CAM_PULL_165K", 165000.0)):
    pos_ = H + up_h * alt_ - look_ * (alt_ / math.tan(math.radians(60.0)))
    if alt_ < 20000.0:
        co = add_camera(name, 35.0, clip=(2.0, 400000.0))
        co["lod_share"] = "CAM_0"
    else:
        co = sys_cam(name, pos_, lens=35.0)
    co.location = pos_
    co.rotation_euler = (H - pos_).to_track_quat("-Z", "Y").to_euler()
co = add_camera("CAM_PROOF_GROUND", 28.0, clip=(2.0, 400000.0))
co["lod_share"] = "CAM_0"
co.location = H + up_h * 60.0
sys_cam("CAM_PROOF_SPACE", CENTER + Vector((SYS_D, 0.0, 0.0)), lens=35.0)
# how far the fog opens around each shot, so its subject reads in thick fog (rt_fog_clear, 180 m for the others).
# Out past far subjects (1.4 km for CAM_0) it left no fog in frame
# At least 150 m: EEVEE's froxels within about 150 m of the camera do not hold the sky mask, and fog there drew a dither
# over the water (CAM_10 f1, 60 m) and veiled the night sky (CAM_1, 45 m)
# CAM_2 150 m too (from 80): at 80 its fog drew the froxels' dither as a dotted grid in the night sky and a checker over
# the sunset mountains (round 6); its capstone, 140 m off, keeps most of its halo at the clear zone's soft edge
for co, clear_m in ((c0, 250.0), (c1, 150.0), (c2, 150.0), (c3, 150.0), (c5, 150.0), (c7, 150.0), (c8, 150.0), (c9, 200.0), (c10, 150.0)):
    co["fog_clear"] = clear_m
c1["fog_k"] = 3.5       # its river and banks lie within 600 m: at the others' strength f1 was hardly thicker than f05
# (at 2.0 its f1 showed only on the far water, round 5)
c9["fog_k"] = 2.0       # its plain lies flat round the pyramids: f1 was a thin band on the horizon, barely thicker than f05
c4["fog_k"] = 2.5       # it flies 650 m over the valley fog: f1 read hardly thicker than f05
for co in (c7, c8, c10):    # they stand in the layer by the sea: at full strength f1 erased the sea and the river mouth
    co["fog_k"] = 0.5
c7["fog_k"] = 1.2          # at 0.5 and 0.8 its f1 by day and at sunset read like f0 (round 5)
for co, h_ in ((c7, (c7.location - CENTER).length - R), (c8, (c8.location - CENTER).length - R), (c10, 60.0)):
    co["fog_dip"] = math.sqrt(2.0 * max(h_, 5.0) / R)   # over the sea: the fog ends at its visible horizon (CAM_10 flies about 60 m up)
S.camera = c0
if GRAFT:
    lm = S.objects.get("Land_Mirror")    # the island's mirror of pyramids, flamingos, sun and moon about z = 0: right at the pole, wrong from space
    if lm:   # scaled to nothing there: a driven hide_viewport rebuilt the depsgraph's relations on every cut into space
        for i, v in enumerate(tuple(lm.scale)):
            driver(lm, "scale", i, "%g*(s <= 0.3)*(x*x + y*y + z*z < 4.0e6)" % v,      # and only near the pole: far from it
                   {"s": "rt_space", "x": "rt_cam_x", "y": "rt_cam_y", "z": "rt_cam_z"})  # its mirrored sun lay on the water (CAM_7)
    out_cam = S.objects["CAM_OUT"]
    out_cam.data.clip_start, out_cam.data.clip_end = 1.0, 400000.0
    out_cam.constraints["Copy Transforms"].target = c0

# ================================================================ runtime (LOD anchor on camera cuts; clocks unless the island runtime runs), save
rt = bpy.data.texts.new("planet_runtime.py")      # embedded: the scene must not depend on where this folder lives
with open(os.path.join(HERE, "planet_runtime.py")) as f:
    rt.from_string(f.read())
rt.use_module = True
rtm = rt.as_module()


# ================================================================ star system (docs/research/synthwave-star-system.md, graft):
# the planet stays still and the sky turns; star_system.py (loaded by the island runtime) solves it every frame
# and writes rt_sun_* (world sun direction), rt_sun_h (Sun Height), rt_moon_* (moon centre) and rt_star_ang
SUN_ALPHA = math.radians(0.2667)     # the true-size sun: it sets the planet's umbra and penumbra on the moon
UMBRA_TINT = (0.42, 0.07, 0.04)      # the moon in the planet's shadow: only reddened light reaches it
UMBRA_GLOW = 0.6                     # its level on the rock's colour, about a lit moon's mean shading


def clear_group(g):
    T = NT(g)
    for nd in [nd for nd in T.n if nd.type not in ("GROUP_INPUT", "GROUP_OUTPUT")]:
        T.n.remove(nd)
    return T, next(nd for nd in T.n if nd.type == "GROUP_OUTPUT").inputs


MOON_CAP = math.radians(30.0)       # the moon maps' polar caps reach this far from each pole


def moon_caps(a_, path, n=1024):
    """A moon map's two polar caps (within MOON_CAP of each pole), north and south side by side, in an orthographic
    azimuthal projection, like the star map's (star_caps). The plate carree map pinches each pole to a point, and its
    filter drew radial streaks round the moon's texture poles (CAM_6, S9). Longitude is u * 2 pi, latitude (v - 0.5) pi."""
    h_, w_ = a_.shape[:2]
    ys, xs = np.mgrid[0:n, 0:n]
    x, y = (xs + 0.5) / n * 2.0 - 1.0, (ys + 0.5) / n * 2.0 - 1.0
    colat = np.arcsin(np.clip(np.hypot(x, y) * math.sin(MOON_CAP), 0.0, 1.0))
    u = ((np.arctan2(y, x) / (2 * math.pi)) % 1.0) * w_ - 0.5
    out = np.zeros((n, 2 * n, 4), dtype=np.float32)
    for k_, sign in ((0, 1.0), (1, -1.0)):
        v = (0.5 + sign * (math.pi / 2 - colat) / math.pi) * h_ - 0.5
        u0, v0 = np.floor(u).astype(np.int64), np.floor(v).astype(np.int64)
        fu, fv = (u - u0)[..., None], (v - v0)[..., None]
        u1, v1 = (u0 + 1) % w_, np.clip(v0 + 1, 0, h_ - 1)
        u0, v0 = u0 % w_, np.clip(v0, 0, h_ - 1)
        cap_ = (a_[v0, u0] * (1 - fu) * (1 - fv) + a_[v0, u1] * fu * (1 - fv) + a_[v1, u0] * (1 - fu) * fv + a_[v1, u1] * fu * fv)
        # blurred the same in every direction, more toward the pole: the maps' polar data differ along longitude far more
        # than along latitude (sparse polar passes), and the cap drew that as spokes converging on the pole (CAM_6). A
        # Gaussian of 1.5 cap pixels (about 0.1 deg) at the cap's edge, 10 pixels within 9 deg of the pole
        def blur(c_, sig):
            r_ = int(3 * sig)
            g_ = np.exp(-0.5 * (np.arange(-r_, r_ + 1) / sig) ** 2)
            g_ /= g_.sum()
            for ax in (0, 1):
                c_ = np.apply_along_axis(lambda row: np.convolve(np.pad(row, r_, mode="edge"), g_, mode="valid"), ax, c_)
            return c_
        pk_ = np.clip((0.9 - np.hypot(x, y)) / 0.6, 0.0, 1.0)[..., None]     # to 27 deg off the pole: from 16 deg spokes stayed (S9)
        out[:, k_ * n:(k_ + 1) * n] = blur(cap_, 1.5) * (1.0 - pk_) + blur(cap_, 10.0) * pk_
    out[..., 3] = 1.0
    img = bpy.data.images.new("moon_caps_tmp", 2 * n, n, float_buffer=True, alpha=True)
    img.pixels.foreach_set(out.ravel())
    img.filepath_raw = path
    img.file_format = "OPEN_EXR"
    img.save()
    bpy.data.images.remove(img)


def moon_cap_lookup(T, n, cap):
    """Image node n samples a plate carree moon map at its (u, v): within 24 to 28 deg of a pole its colour comes from
    the map's polar caps (moon_caps) at the same point instead."""
    cap.colorspace_settings.name = n.image.colorspace_settings.name
    src = n.inputs["Vector"].links[0].from_socket if n.inputs["Vector"].is_linked else T.node("ShaderNodeTexCoord").outputs["UV"]
    u, v, _ = T.sep(src)
    lat = T.mul(T.sub(v, 0.5), math.pi)
    lon = T.mul(u, 2 * math.pi)
    r_ = T.math("DIVIDE", T.math("COSINE", lat), math.sin(MOON_CAP))
    uc = T.addf(T.sub(0.75, T.mul(T.math("GREATER_THAN", lat, 0.0), 0.5)), T.mul(T.mul(r_, T.math("COSINE", lon)), 0.25))
    vc = T.addf(0.5, T.mul(T.mul(r_, T.math("SINE", lon)), 0.5))
    tex = T.node("ShaderNodeTexImage", interpolation=n.interpolation, extension="EXTEND")
    tex.image = cap
    T.feed(tex.inputs["Vector"], T.comb(uc, vc, 0.0))
    capk = T.smooth(T.math("ABSOLUTE", lat), math.radians(62.0), math.radians(66.0))
    users = [ln.to_socket for ln in n.outputs["Color"].links]
    mixed = T.mix(capk, n.outputs["Color"], tex.outputs["Color"])
    for sock in users:
        T.l.new(mixed, sock)


def star_system():
    S["pl_radius"] = R
    # VJ_Phase from the Sun Height: the same ramps vj_night had for the on-air camera (+20 deg to 0, 0 to -18 deg)
    T, go_ = clear_group(g_phase)
    h = T.attr("rt_sun_h")
    dusk, night = T.smooth(h, math.radians(20.0), 0.0), T.smooth(h, 0.0, math.radians(-18.0))
    T.feed(go_["Dusk"], dusk)
    T.feed(go_["Night"], night)
    T.feed(go_["Twilight"], T.mul(dusk, T.sub(1.0, night)))
    # VJ_SunDir: the real sun and moon; its outputs keep their meaning, so every island shader stays wired
    T, go_ = clear_group(g_sun)
    s_ = T.vmath("NORMALIZE", T.comb(T.attr("rt_sun_x"), T.attr("rt_sun_y"), T.attr("rt_sun_z")))
    h = T.attr("rt_sun_h")
    sun_amt = T.mul(T.attr("vj_sun"), T.mrange(h, -0.24, 0.16, 0.0, 1.0))     # as the old arc's elevation
    up_ = T.group(g_frame)["Up"]
    moon_at = T.comb(T.attr("rt_moon_x"), T.attr("rt_moon_y"), T.attr("rt_moon_z"))
    cam_at = T.comb(T.attr("rt_cam_x"), T.attr("rt_cam_y"), T.attr("rt_cam_z"))
    for name, val in (("Dir", s_), ("Local Dir", to_local(T, s_)),
                      ("Up", T.vmath("NORMALIZE", T.vmath("SUBTRACT", up_, T.vmath("SCALE", s_, scale=T.dot(up_, s_))))),
                      ("Day", T.smooth(h, -0.16, 0.06)), ("Amount", sun_amt), ("Radius", T.smooth(sun_amt, 0.3, 1.0, *SUN_R)),
                      ("Moon", T.math("SUBTRACT", 1.0, T.smooth(sun_amt, 0.3, 0.85))),
                      ("MoonDir", to_local(T, T.vmath("NORMALIZE", T.vmath("SUBTRACT", moon_at, cam_at))))):
        T.feed(go_[name], val)
    # VJ_Sky: the star layers turn with the sky (rt_star_ang about the spin axis +x); the gradient stays local
    T = NT(g_sky)
    gin = next(nd for nd in T.n if nd.type == "GROUP_INPUT")
    local_dir = next(nd for nd in T.n if nd.type == "TEX_VORONOI" and abs(nd.inputs["Scale"].default_value - 240.0) < 1.0).inputs["Vector"].links[0].from_node
    star_users = [ln.to_socket for ln in local_dir.outputs[0].links if ln.to_node.type != "GROUP"]   # the star layers;
    vr = T.node("ShaderNodeVectorRotate", rotation_type="AXIS_ANGLE")              # the sky base and meteors keep the view
    T.feed(vr.inputs["Vector"], gin.outputs["Direction"])
    vr.inputs["Axis"].default_value = (1.0, 0.0, 0.0)
    T.feed(vr.inputs["Angle"], T.attr("rt_star_ang"))
    star_dir = T.comb(*T.sep(vr.outputs["Vector"]))
    for sock in star_users:
        T.l.new(star_dir, sock)
    # the moon: lit by the real sun (its light vector moved into the moon's object space), dimmed and reddened
    # in the planet's shadow: t = -(p - C).s deep behind the planet, d from the shadow axis, umbra R - t tan a,
    # penumbra R + t tan a, a linear ramp between them. The earthshine term stays as it was
    T = NT(bpy.data.materials["Moon"].node_tree)
    light = T.n["Vector Math.019"]
    to_obj = T.node("ShaderNodeVectorTransform", vector_type="VECTOR", convert_from="WORLD", convert_to="OBJECT")
    T.feed(to_obj.inputs["Vector"], T.comb(T.attr("rt_sun_x"), T.attr("rt_sun_y"), T.attr("rt_sun_z")))
    for ln in list(light.outputs["Vector"].links):
        T.l.new(to_obj.outputs["Vector"], ln.to_socket)
    s_ = T.vmath("NORMALIZE", T.comb(T.attr("rt_sun_x"), T.attr("rt_sun_y"), T.attr("rt_sun_z")))
    pc = T.vmath("SUBTRACT", T.node("ShaderNodeNewGeometry").outputs["Position"], tuple(CENTER))
    t_ = T.mul(T.dot(pc, s_), -1.0)
    d_ = T.vmath("LENGTH", T.vmath("ADD", pc, T.vmath("SCALE", s_, scale=t_)))
    spread = T.mul(t_, math.tan(SUN_ALPHA))
    shadow = T.mul(T.mrange(d_, T.addf(spread, R), T.sub(R, spread), 0.0, 1.0), T.math("GREATER_THAN", t_, 0.0))
    lit_out = T.n["Vector Math.028"].outputs["Vector"]
    users = [ln.to_socket for ln in lit_out.links]       # before the mix exists: relinking its own inputs makes a cycle
    # in the umbra no sunlight reaches it, only the planet's ring of sunsets from all round: an even copper glow on
    # its rock over the whole disc. The sunlit shading tinted copper left the far half black, a half-copper oval from
    # the side (CAM_SYS night e1)
    rock = max((n for n in T.n if n.type == "TEX_IMAGE" and n.image is not None), key=lambda n: n.image.size[0])
    dim = T.vmix(shadow, lit_out, T.vmath("MULTIPLY", rock.outputs["Color"], tuple(c * UMBRA_GLOW for c in UMBRA_TINT)))
    for sock in users:
        T.l.new(dim, sock)
    # bodies: the runtime places them every frame (vj_body), so they leave Sky_Frame and their place drivers
    for name, kind in (("Sun", "sun"), ("Sun_Corona", "sun"), ("Moon", "moon")):
        ob = S.objects[name]
        ob.parent = None
        ob["vj_body"] = kind
        if kind == "sun":
            ob["vj_dist"] = D_SUN
        for fc in list(ob.animation_data.drivers if ob.animation_data else ()):
            if fc.data_path in ("location", "rotation_axis_angle", '["mk"]', '["mel"]'):
                ob.animation_data.drivers.remove(fc)
            elif kind == "moon" and fc.data_path == "scale":
                fc.driver.expression = "%g*max(m, 0.0001)" % MOON_R
        if kind == "sun":   # the striped card faces the On-Air Camera: from space (and any other view) it read as an
            # ellipse. It is a ground-shot sun and hides there; VJ_Sky draws the real, round sun from space (S5)
            for fc in ob.animation_data.drivers:     # scaled to nothing (a driven hide rebuilt the depsgraph on every cut)
                if fc.data_path == "scale":
                    v_ = fc.driver.variables.new()
                    v_.name = "sp"
                    v_.targets[0].id_type = "SCENE"
                    v_.targets[0].id = S
                    v_.targets[0].data_path = '["rt_space"]'
                    fc.driver.expression = "(%s)*(sp <= 0.5)" % fc.driver.expression
    neb = S.objects.get("Nebula")    # an 18 km purple volume over the camera area: a smear from space and in the sky (S6)
    if neb is not None:
        for fc in list(neb.animation_data.drivers if neb.animation_data else ()):
            neb.animation_data.drivers.remove(fc)
        neb.hide_viewport = neb.hide_render = True
    # the moon's magenta rim is a ground-shot glow: from space the moon is plain rock lit by the sun (S4), and in an
    # eclipse it is copper all over (a magenta limb, night e1)
    T = NT(bpy.data.materials["Moon"].node_tree)
    for n in [n for n in T.n if n.type == "VECT_MATH" and n.operation == "SCALE" and not n.inputs[0].is_linked
              and tuple(round(v, 2) for v in n.inputs[0].default_value) == (1.0, 0.18, 0.85)]:
        k_ = n.inputs["Scale"].links[0].from_socket if n.inputs["Scale"].is_linked else n.inputs["Scale"].default_value
        ph_m = T.phase()
        no_rim = T.mul(T.mul(T.sub(1.0, eye_space(T)), T.sub(1.0, T.math("MINIMUM", T.math("MAXIMUM", T.attr("vj_eclipse"), 0.0), 1.0))),
                       T.mul(T.sub(1.0, ph_m["Night"]), T.sub(1.0, ph_m["Twilight"])))      # by day only: a magenta limb on the
        # night moon (CAM_4 p25) and at sunset (CAM_4 sunset p25, round 5)
        T.feed(n.inputs["Scale"], T.mul(k_, no_rim))
    # the moon's maps pre-filtered (S9): its 8k colour map and the seven samples of its height map behind the relief
    # aliased into moire black craters once the moon was a few hundred pixels across. A 2k colour map and the height map
    # blurred over about 2.5 texels, made once next to the star map (starmaps/, not in the repo); and its albedo at 0.65 (it
    # outshone the planet)
    T = NT(bpy.data.materials["Moon"].node_tree)
    for n in [n for n in T.n if n.type == "TEX_IMAGE" and n.image is not None]:
        src = n.image
        key = src.name + "_filtered_r9"     # (round 9) a new name: the old files stay valid for older checkouts
        img = bpy.data.images.get(key)
        if img is None:
            w_, h_ = src.size
            a_ = np.empty(w_ * h_ * 4, dtype=np.float32)
            src.pixels.foreach_get(a_)
            a_ = a_.reshape(h_, w_, 4)
            if w_ > 4096:      # colour: box-filtered down to 4096 wide (2048 smeared the moon once it passed about 650 px
                f_ = w_ // 4096    # across, CAM_6 and S9, round 8)
                a_ = a_[: h_ // f_ * f_, : w_ // f_ * f_].reshape(h_ // f_, f_, w_ // f_, f_, 4).mean(axis=(1, 3))
            else:              # height: a 3-tap blur six times, wrapping in longitude (twice left aliased black craters)
                for _ in range(4):     # (six smeared the craters, round 8; self-shadow is at 5 now, not 61.5)
                    a_ = (np.roll(a_, 1, 1) + 2 * a_ + np.roll(a_, -1, 1)) / 4.0
                    a_ = (np.vstack([a_[:1], a_[:-1]]) + 2 * a_ + np.vstack([a_[1:], a_[-1:]])) / 4.0
            moon_caps(a_, os.path.join(os.path.dirname(STAR_PATH), key + "_caps.exr"))
            # toward each pole the map turns into its polar cap's mean (all of it from 85 deg): every texel of a row
            # meets at the pole, and their differences drew radial streaks (CAM_6); each row's own mean drew rings.
            # The caps (moon_caps) draw over it from 62 deg
            lat_ = (np.arange(a_.shape[0]) + 0.5) / a_.shape[0] * 180.0 - 90.0
            for sign in (-1.0, 1.0):
                cap = a_[lat_ * sign > 80.0].mean(axis=(0, 1))
                k_ = np.clip((lat_ * sign - 65.0) / 20.0, 0.0, 1.0)[:, None, None]
                a_ = a_ * (1.0 - k_) + cap * k_
            a_ = a_.astype(np.float32)
            path_ = os.path.join(os.path.dirname(STAR_PATH), key + ".exr")
            tmp_ = bpy.data.images.new(key + "_tmp", a_.shape[1], a_.shape[0], float_buffer=True, alpha=False)
            tmp_.pixels.foreach_set(a_.ravel())
            tmp_.filepath_raw = path_
            tmp_.file_format = "OPEN_EXR"
            tmp_.save()
            bpy.data.images.remove(tmp_)
            img = bpy.data.images.load(path_)
            img.name = key
            img.colorspace_settings.name = src.colorspace_settings.name
        n.image = img
        if src.name.startswith("moon_lroc"):
            for ln in list(n.outputs["Color"].links):
                T.l.new(T.scale(n.outputs["Color"], 0.65), ln.to_socket)
        moon_cap_lookup(T, n, bpy.data.images.load(os.path.join(os.path.dirname(STAR_PATH), key + "_caps.exr"), check_existing=True))
    # and its relief softer: the island's crater self-shadow (height steps x 61.5) and slope gain (x 143.5) drew hard black
    # blotches once the moon filled the frame (CAM_6)
    for n in T.n:
        if n.type == "MATH" and n.operation == "MULTIPLY" and not n.inputs[1].is_linked:
            if abs(n.inputs[1].default_value - 61.5) < 1e-3:
                n.inputs[1].default_value = 5.0        # 20 and 10 still left black holes in the craters at full resolution (S9)
            elif abs(n.inputs[1].default_value - 143.5) < 1e-3:
                n.inputs[1].default_value = 50.0
    # the island pyramids' neon edges (their wireframe tubes) at a slight glow at night, like the wires: white and cyan
    # outlines were too bright (CAM_2)
    T = NT(bpy.data.materials["Pyramid Edge"].node_tree)
    em_ = next(n for n in T.n if n.type == "EMISSION")
    T.feed(em_.inputs["Strength"], T.mrange(T.phase()["Night"], 0.0, 1.0, 1.0, 0.08))
    T = NT(bpy.data.materials["Moon"].node_tree)
    # its earthshine (2.2% of the rock) at a quarter from space: there it lit the night side as an evenly grey disc
    # with no terminator (CAM_SYS e1, S2)
    shine = T.n["Vector Math.030"]
    T.feed(shine.inputs["Scale"], T.mul(shine.inputs["Scale"].default_value, T.sub(1.0, T.mul(eye_space(T), 0.75))))
    # sun and moon shots aim at their body on every cut; the others keep their framing
    S.objects["CAM_3"]["vj_track"] = "moon"
    S.objects["CAM_9"]["vj_track"] = "sun"


if GRAFT:
    star_system()


def fog_lights():
    """The lights the fog shows (reference_fog/): every material is emission, so lights reach only the fog volume.
    - the sun (white, warm when low) and the moon (cool, night only), aimed by the star system's bodies;
    - a warm lamp at each glowing capstone near a ground shot, at night: a halo round it, the fog lit above it."""
    S["rt_sun_h"] = S.get("rt_sun_h", math.radians(20.0))
    made = []

    def light(name, kind, energy_expr, props, color, target=None, loc=(0, 0, 0)):
        ld = bpy.data.lights.new(name, kind)
        ld.color = color
        for attr, val in (("diffuse_factor", 0.0), ("specular_factor", 0.0), ("transmission_factor", 0.0), ("volume_factor", 1.0)):
            if hasattr(ld, attr):
                setattr(ld, attr, val)
        ob = bpy.data.objects.new(name, ld)
        c_planet.objects.link(ob)
        ob.location = loc
        driver(ld, "energy", None, energy_expr, props)
        if target is not None:
            con = ob.constraints.new("DAMPED_TRACK")
            con.target = target
            con.track_axis = "TRACK_Z"       # the light shines along -Z: away from the body
        made.append(ob)
        return ob
    sun_l = light("Fog_Sun", "SUN", "2.2*min(max((h + 0.05)/0.2, 0.0), 1.0)", {"h": "rt_sun_h"}, (1.0, 0.95, 0.88), S.objects["Sun"])
    for i, (c0_, c1_) in enumerate(((1.0, 1.0), (0.62, 0.95), (0.38, 0.88))):     # warmer as the sun sinks
        driver(sun_l.data, "color", i, "%g + %g*min(max(h/0.35, 0.0), 1.0)" % (c0_, c1_ - c0_), {"h": "rt_sun_h"})
    # (at 0.8 the moonlit fog read as self-lit violet bands at night, CAM_3 and CAM_5)
    # 0.12: at 0.25 the moonlit night haze, seen from high up, smeared purple over the far sky (CAM_4 night f1, round 6)
    light("Fog_Moon", "SUN", "0.12*m*min(max((n - 0.55)/0.3, 0.0), 1.0)", {"n": "vj_night", "m": "vj_moon"}, (0.55, 0.68, 1.0), S.objects["Moon"])
    def apex(M_, box):
        """The top centre of a pyramid's bounding box: its highest corner put the lamp beside the apex, as an orb in
        the night fog (CAM_9)."""
        pts = [M_ @ Vector(v) for v in box]
        up_ = (M_.translation - CENTER).normalized()
        ctr = sum(pts, Vector()) / len(pts)
        return ctr + up_ * (max((q - CENTER).dot(up_) for q in pts) - (ctr - CENTER).dot(up_))

    dg_ = bpy.context.evaluated_depsgraph_get()
    tops = []
    coll_ = bpy.data.collections.get("Pyramids")
    for ob in (coll_.objects if coll_ else ()):
        e_ = ob.evaluated_get(dg_)
        tops.append(apex(e_.matrix_world, e_.bound_box))
    shots = [S.objects[n].matrix_world.translation.copy() for n in ("CAM_0", "CAM_2", "CAM_3", "CAM_5", "CAM_7", "CAM_9")]
    for inst in dg_.object_instances:
        if inst.is_instance and inst.parent is not None and inst.parent.original.name == "Planet_Sites":
            M_ = inst.matrix_world
            base_ = M_.translation
            if (base_ - CENTER).length > R - 5.0 and min((base_ - c_).length for c_ in shots) < 1500.0:
                tops.append(apex(M_, inst.object.bound_box))
    # a lamp shines in the shots that see its capstone (or stand over 3 km off): behind a ridge its halo hung in the
    # night fog as an orb over the horizon (CAM_9). A bit per /vj/cam in its "seen" mask, read by its energy driver
    lamps = [t_ + (t_ - CENTER).normalized() * 1.5 for t_ in tops]
    seen = [0] * len(lamps)
    was = tuple(anchor.location)
    for k_ in range(11):
        c_ = S.objects["CAM_%d" % k_].matrix_world.translation.copy()
        dg_ = evaluate(tuple(c_))
        for i, l_ in enumerate(lamps):
            if (l_ - c_).length > 3000.0 or not land_between(dg_, c_, l_):
                seen[i] |= 1 << k_
    evaluate(was)
    for i, l_ in enumerate(lamps):
        # (off in space, where there is no fog: every lamp turned on in CAM_6, the slowest cut at night, 87 ms)
        lamp = light("Lamp_Capstone.%03d" % i, "POINT", "LAMP_W*min(max((n - 0.55)/0.3, 0.0), 1.0)*(floor(%d/2**floor(c)) %% 2)*(sp < 0.5)"
                     .replace("LAMP_W", "%g" % LAMP_W) % seen[i], {"n": "vj_night", "c": "vj_cam", "sp": "rt_space"}, (1.0, 0.72, 0.36), loc=l_)
        lamp.data.shadow_soft_size = 1.0
    print("PLANET capstone lamps: %d, hidden from %d shot views" % (len(lamps), sum(11 - bin(m_).count("1") for m_ in seen)))
    return made


LAMP_W = 120000.0        # W per capstone lamp: it lights the fog only. At 300 kW its light spread through the night haze
# as a warm wash over half the frame, which read as the fog glowing on its own (CAM_5, CAM_2 f1)


if GRAFT:
    fog_lights()


def bake_points(src, name):
    """A mesh of src's points and their flight attributes, kept with a fake user (no object uses it)."""
    me = bpy.data.meshes.new(name)
    n_ = len(src.vertices)
    co_ = np.empty(3 * n_)
    src.vertices.foreach_get("co", co_)
    me.vertices.add(n_)
    me.vertices.foreach_set("co", co_)
    for nm in rtm.FLOCK_ATTRS:
        vals = np.zeros(n_)
        if nm in src.attributes:
            src.attributes[nm].data.foreach_get("value", vals)
        me.attributes.new(nm, "FLOAT", "POINT").data.foreach_set("value", vals)
    me.use_fake_user = True
    return me


def lod_sets():
    """Land, water and props for every camera, evaluated once on load, and its flamingo flock baked into a mesh
    (Flock.<set>): a cut then only switches which set the camera sees (visible_camera) and copies the flock,
    instead of a 250-400 ms rebuild under a moved anchor (the props and flock scatter alone cost 30-60 ms per cut).
    A flight path gets LOD_PATH_SETS anchors along it; the runtime takes the nearest. The originals are removed."""
    for co in sorted((o for o in S.objects if o.type == "CAMERA" and o.name.startswith("CAM_") and o.name != "CAM_OUT"
                      and "lod_share" not in o), key=lambda o: o.name):
        centre, cull, lmin_land, lmin_water = rtm.MODES[co.get("lod", "surface")]
        if centre:
            targets = [Vector(CENTER)]
        elif "path_period" in co:
            targets = []
            n_ = co.get("lod_path_sets", LOD_PATH_SETS)
            for j in range(n_):
                S["rt_cam_phase"] = co["path_period"] * (j + 0.5) / n_
                S.update_tag()
                targets.append(co.evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_world.translation.copy())
        else:
            targets = [co.matrix_world.translation.copy()]
        keys = []
        for t in targets:
            key = "%s.%d" % (co.name, len(keys))
            a = bpy.data.objects.new("LOD_Anchor." + key, None)
            c_planet.objects.link(a)
            a.location = t
            for src, lmin in ((land_ob, lmin_land), (water_ob, lmin_water), (props_ob, None)):
                d = src.copy()
                d.name = "%s.%s" % (src.name, key)
                c_planet.objects.link(d)
                d["lod_set"] = key
                rtm.set_input(d, "Anchor", a)
                if lmin is not None:
                    rtm.set_input(d, "Cull", cull)
                    rtm.set_input(d, "Min Level", lmin)
            if GRAFT:
                rtm.set_input(birds_ob, "Anchor", a)
                bake_points(birds_ob.evaluated_get(bpy.context.evaluated_depsgraph_get()).data, "Flock." + key)
                print("PLANET flock %s: %d points" % (key, len(bpy.data.meshes["Flock." + key].vertices)))
            keys.append(key)
        co["lod_sets"] = keys
    S["rt_cam_phase"] = 0.0
    for co in [o for o in S.objects if o.type == "CAMERA" and "lod_share" in o]:
        co["lod_sets"] = list(S.objects[co["lod_share"]]["lod_sets"])
    for ob in (land_ob, water_ob, props_ob) + ((birds_ob,) if GRAFT else ()):
        bpy.data.objects.remove(ob)


lod_sets()
rtm.place_anchor(S, c0)
S["pl_lod_step"] = 0.0
S.render.use_border = True          # camera view renders only the camera frame (scene-perf: +50%, same pixels)
S.render.border_min_x = S.render.border_min_y = 0.0
S.render.border_max_x = S.render.border_max_y = 1.0
if GRAFT and os.path.exists(os.path.join(os.path.dirname(bpy.data.filepath), "shader_dedupe.py")):
    sys.path.insert(0, os.path.dirname(bpy.data.filepath))
    import shader_dedupe            # the island's trees: one lookup per attribute, as the planet's own trees are built
    shader_dedupe.dedupe_all()
if GRAFT:   # drops the planet's own copies of the shared groups, unused here
    bpy.data.orphans_purge(do_recursive=True)
if GRAFT and os.path.exists(os.path.join(os.path.dirname(bpy.data.filepath), "day_world.py")):
    sys.path.insert(0, os.path.dirname(bpy.data.filepath))
    import day_world                # the sky without its night layers, swapped in by the runtime by day (scene-perf)
    # the 240 stars are night-only here because stars_in_the_dark gates them
    day_world.make(S.world, cut=lambda n: day_world.night_only(n) or n.label == "space_sky" or (
        n.type == "TEX_VORONOI" and abs(n.inputs["Scale"].default_value - 240.0) < 1.0))
if GRAFT:   # the island file embeds its runtime texts as last saved there, and Blender runs that copy on load
    for tx in bpy.data.texts:
        src_path = bpy.path.abspath(tx.filepath) if tx.filepath else ""
        if os.path.exists(src_path):
            with open(src_path) as f_:
                tx.from_string(f_.read())
for scr in bpy.data.screens:
    for area in scr.areas:
        if area.type == "VIEW_3D":
            sp_ = area.spaces[0]
            sp_.shading.type = "RENDERED"
            sp_.clip_start, sp_.clip_end = 2.0, 1.0e6       # a free view zoomed out over the whole system
            sp_.region_3d.view_perspective = "CAMERA"
for img_ in bpy.data.images:      # maps next to the scene file by a relative path: a build made elsewhere keeps them
    if img_.source == "FILE" and img_.filepath and os.path.isabs(bpy.path.abspath(img_.filepath)) and not img_.filepath.startswith("//"):
        img_.filepath = bpy.path.relpath(img_.filepath, start=os.path.dirname(OUT))
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True, relative_remap=True)
print("PLANET saved %s (graft=%s), CAM_0 at %s, river shot: %s" % (OUT, GRAFT, tuple(round(c, 1) for c in c0.location), bool(best)))
