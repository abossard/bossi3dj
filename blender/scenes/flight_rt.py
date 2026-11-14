"""Runtime of the Path Camera in the planet scene (docs/handover/path-camera.md, blender/scenes/path_camera.py).

Loaded by synthwave_runtime.py next to star_system.py; start() installs a frame handler that runs before the
others, so the planet runtime, the star system and the fog all read this frame's view.

- CAM_RIG is always scene.camera, the On-Air Camera. Its pose is the Path Camera's: /vj/path and /vj/target pick the
  path and what it looks at, /vj/height the height over the ground, /vj/cam_speed the speed, /vj/blend the time the
  longest change takes (0: a cut). A camera set from elsewhere hands scene.camera back to the rig.
- The targets: the empties PathTarget.<name> of the build (pyramids, lake, river, coast) on the ground of the
  clearance map; the moon and the sun live from the star system (rt_moon_*, rt_sun_*); the planet.
- The rig carries the per-pose numbers (fog_k, fog_clear, fog_dip) that the planet runtime reads from scene.camera,
  and its near clip grows with the clearance.
- Energy (energy.py): /vj/energy, /vj/hit and the pulse rt_beat; the path runs faster with the Drive's speed, the
  Director puts the kick and the pulse on the rig. rt_energy and rt_kick are written for the recorder.
- The terrain: the GPU terrain (gpu_terrain: a grid round the rig, displaced in the material from the Planet's height
  map), the only one; above about 10 km the globe takes the Planet over.
- The capstone lamps: a lamp hidden by land within LAMP_NEAR fades to black (lamp_sight).
- The clearance map: ground (conservative: a 3x3 max, pyramids stamped in) and water level over the whole Planet on
  a cube map, probed once from the planet's own PL_Surface group and cached under ~/Library/Caches. The paths, the
  blends and their floors read it.
"""
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, "planet_proto")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
for _m in ("director", "energy", "flight", "gpu_terrain", "path_camera"):     # loaded again: every module fresh
    sys.modules.pop(_m, None)
import energy as en  # noqa: E402
import flight as fl  # noqa: E402
import gpu_terrain  # noqa: E402
import path_camera as pc  # noqa: E402

RIG = "CAM_RIG"
SHOT_KEY = "vj_shot"                # driver_namespace: () -> "path target", the page's and the check's name of the view
TARGET_PREFIX = "PathTarget."
MAP_RES = 512                       # texels per cube face side: about 49 m
PYR_PAD = 25.0                      # m around a pyramid's footprint
CACHE = os.path.expanduser("~/Library/Caches/swiftvj-flight")
MOON_R = 11500.0
LAMP_NEAR, LAMP_FADE = 3000.0, 0.4    # m within which land hides a capstone lamp (build_planet.fog_lights), s to fade it
SUN_DIST, SUN_SIZE = 2.0e6, 60000.0     # m: where the sun target is put along the sun's direction, and its size to frame
_state = {"last": None, "path": None, "map": None, "terrain": False, "drive": None, "targets": None, "n": 0}


# ---------------------------------------------------------------- the cube sphere (the clearance map's faces)
def _unit(k):
    return tuple(1.0 if i == k else 0.0 for i in range(3))


FACES = []
for _f in range(6):
    _axis, _s = _f % 3, (1.0 if _f < 3 else -1.0)
    FACES.append((tuple(_s * c for c in _unit(_axis)), _unit((_axis + 1) % 3), tuple(_s * c for c in _unit((_axis + 2) % 3))))


def dir_face(p):
    """The face and equal-angle coordinates of a unit direction."""
    best = max(range(6), key=lambda f: sum(FACES[f][0][k] * p[k] for k in range(3)))
    n, u, v = FACES[best]
    dn = sum(n[k] * p[k] for k in range(3))
    a = math.atan(sum(u[k] * p[k] for k in range(3)) / dn) * 4.0 / math.pi
    b = math.atan(sum(v[k] * p[k] for k in range(3)) / dn) * 4.0 / math.pi
    return best, a, b


# ---------------------------------------------------------------- the clearance map
def face_dirs(f, n):
    """Unit directions of the texel centres of cube face f, (n, n, 3), row = b, column = a."""
    t = -1.0 + (np.arange(n) + 0.5) * 2.0 / n
    a, b = np.meshgrid(t, t)
    nrm, u, v = (np.array(x) for x in FACES[f])
    d = nrm[None, None, :] + np.tan(a * np.pi / 4.0)[..., None] * u + np.tan(b * np.pi / 4.0)[..., None] * v
    return d / np.linalg.norm(d, axis=-1, keepdims=True)


def probe_group(hydro):
    """A GN tree that stores per point (a unit direction) the Planet's surface height (fl_h), its water level (fl_w)
    and the rivers' flow (fl_f, for gpu_terrain)."""
    g = bpy.data.node_groups.new("FLT_Probe", "GeometryNodeTree")
    g.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    g.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = g.nodes, g.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    oi = N.new("GeometryNodeObjectInfo")
    oi.inputs["Object"].default_value = hydro
    oi.transform_space = "ORIGINAL"
    sc = N.new("GeometryNodeSeparateComponents")
    L.new(oi.outputs["Geometry"], sc.inputs[0])
    rib = N.new("GeometryNodeCurvePrimitiveLine")
    rib.inputs["Start"].default_value, rib.inputs["End"].default_value = (-0.5, 0, 0), (0.5, 0, 0)
    c2m = N.new("GeometryNodeCurveToMesh")
    L.new(sc.outputs["Curve"], c2m.inputs["Curve"])
    L.new(rib.outputs[0], c2m.inputs["Profile Curve"])
    nrm = N.new("ShaderNodeVectorMath")
    nrm.operation = "NORMALIZE"
    L.new(N.new("GeometryNodeInputPosition").outputs[0], nrm.inputs[0])
    sg = N.new("GeometryNodeGroup")
    sg.node_tree = bpy.data.node_groups["PL_Surface"]
    L.new(nrm.outputs[0], sg.inputs["Dir"])
    L.new(sc.outputs["Mesh"], sg.inputs["Hydro"])
    L.new(c2m.outputs["Mesh"], sg.inputs["Rivers"])
    sg.inputs["River Water"].default_value = 1.0
    sh = N.new("GeometryNodeStoreNamedAttribute")
    sh.inputs["Name"].default_value = "fl_h"
    L.new(gi.outputs[0], sh.inputs["Geometry"])
    L.new(sg.outputs["Height"], sh.inputs["Value"])
    sw = N.new("GeometryNodeStoreNamedAttribute")
    sw.inputs["Name"].default_value = "fl_w"
    L.new(sh.outputs[0], sw.inputs["Geometry"])
    L.new(sg.outputs["Water"], sw.inputs["Value"])
    sf = N.new("GeometryNodeStoreNamedAttribute")
    sf.data_type = "FLOAT_VECTOR"
    sf.inputs["Name"].default_value = "fl_f"
    L.new(sw.outputs[0], sf.inputs["Geometry"])
    L.new(sg.outputs["Flow"], sf.inputs["Value"])
    L.new(sf.outputs[0], go.inputs[0])
    return g


def bake_map(scene, n=MAP_RES):
    """Height and water level (m over R) per texel, (6, n, n) each, probed through PL_Surface."""
    hydro = bpy.data.objects["Planet_Hydro"]
    g = probe_group(hydro)
    me = bpy.data.meshes.new("FLT_Probe")
    ob = bpy.data.objects.new("FLT_Probe", me)
    scene.collection.objects.link(ob)
    ob.hide_render = True
    ob.modifiers.new("probe", "NODES").node_group = g
    dirs = np.concatenate([face_dirs(f, n).reshape(-1, 3) for f in range(6)])
    me.vertices.add(len(dirs))
    me.vertices.foreach_set("co", dirs.astype(np.float32).ravel())     # unit vectors: the probe needs directions only
    me.update()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = ob.evaluated_get(dg).data
    h = np.empty(len(dirs), np.float32)
    w = np.empty(len(dirs), np.float32)
    ev.attributes["fl_h"].data.foreach_get("value", h)
    ev.attributes["fl_w"].data.foreach_get("value", w)
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    bpy.data.node_groups.remove(g)
    return h.reshape(6, n, n), w.reshape(6, n, n)


def conservative(h):
    """The 3x3 neighbourhood max of each face (edges replicated): bilinear lookups never fall under a sample."""
    p = np.pad(h, ((0, 0), (1, 1), (1, 1)), mode="edge")
    out = h.copy()
    for dy in (0, 1, 2):
        for dx in (0, 1, 2):
            out = np.maximum(out, p[:, dy:dy + h.shape[1], dx:dx + h.shape[2]])
    return out


class ClearanceMap:
    """flight.Terrain on the baked cube map."""

    def __init__(self, ground, water, cands, raw=None):
        self.n = ground.shape[1]
        self.g, self.w, self.cands = ground, water, cands
        self.raw = ground if raw is None else raw       # the baked surface itself: no 3x3 max, no pyramids

    def _texel(self, u):
        f, a, b = dir_face(u)
        x = (a + 1.0) * 0.5 * self.n - 0.5
        y = (b + 1.0) * 0.5 * self.n - 0.5
        x0, y0 = min(max(int(math.floor(x)), 0), self.n - 2), min(max(int(math.floor(y)), 0), self.n - 2)
        return f, x0, y0, min(max(x - x0, 0.0), 1.0), min(max(y - y0, 0.0), 1.0)

    def _bilinear(self, arr, u):
        f, x0, y0, fx, fy = self._texel(u)
        a = arr[f]
        return float((a[y0, x0] * (1 - fx) + a[y0, x0 + 1] * fx) * (1 - fy) + (a[y0 + 1, x0] * (1 - fx) + a[y0 + 1, x0 + 1] * fx) * fy)

    def ground(self, u):
        return self._bilinear(self.g, u)

    def water(self, u):
        w = self._bilinear(self.w, u)
        return w if w > self.ground(u) - 1.0 else None

    def surface(self, u):
        w = self._bilinear(self.w, u)
        return max(self.ground(u), w)

    def candidates(self):
        return self.cands

    def land_between(self, a, b, spare=60.0):
        """Whether the baked surface (land or water, not the padded ground) rises over the straight line a-b, one
        sample per texel, except within spare m of b (a lamp's own capstone)."""
        d = fl.length(fl.sub(b, a))
        n = max(2, int(d / (fl.R * math.pi / 2.0 / self.n)))
        for k in range(1, n):
            if d * (1.0 - k / n) < spare:
                break
            rq = fl.sub(fl.add(a, fl.sub(b, a), k / n), fl.CENTRE)
            u = fl.norm(rq)
            if fl.length(rq) - fl.R < max(self._bilinear(self.raw, u), self._bilinear(self.w, u)):
                return True
        return False


def find_regions(h, w, step=8, relief=250.0, reach=2500.0, spacing=3000.0):
    """Mountain spots with water nearby: on a coarse grid, the local relief within 2 km and any wet texel within
    reach; the best spots at least spacing apart."""
    n = h.shape[1]
    cell = fl.R * math.pi / 2.0 / n * step
    hc, wc = h[:, ::step, ::step], w[:, ::step, ::step]
    wet = wc > hc + 1.0
    k = max(1, int(2000.0 / cell))
    kw = max(1, int(reach / cell))
    m = hc.shape[1]
    out = []
    for f in range(6):
        for y in range(k, m - k):
            for x in range(k, m - k):
                win = hc[f, y - k:y + k + 1, x - k:x + k + 1]
                rel = float(win.max() - win.min())
                if rel < relief or wet[f, y, x]:
                    continue
                ww = wet[f, max(0, y - kw):y + kw + 1, max(0, x - kw):x + kw + 1]
                if ww.any():
                    out.append((rel, f, x, y))
    out.sort(reverse=True)
    picked = []
    for rel, f, x, y in out:
        d = tuple(face_dirs(f, m)[y, x])
        if all(fl.R * fl.angle(d, p) >= spacing for p in picked):
            picked.append(d)
    return picked


def stamp_pyramids(scene, g):
    """Raises the ground map to the top of each pyramid over its footprint, so paths clear them."""
    coll = bpy.data.collections.get("Pyramids")
    if coll is None:
        return
    n = g.shape[1]
    centre = Vector(fl.CENTRE)
    for ob in coll.all_objects:
        if ob.type != "MESH":
            continue
        corners = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        top = max((c - centre).length for c in corners) - fl.R
        mid = sum(corners, Vector()) / 8.0
        rad = max((c - mid).length for c in corners) + PYR_PAD
        u = tuple((mid - centre).normalized())
        f, a, b = dir_face(u)
        cx, cy = (a + 1.0) * 0.5 * n, (b + 1.0) * 0.5 * n
        r = rad / (fl.R * math.pi / 2.0 / n) + 1.0
        y0, y1 = max(0, int(cy - r)), min(n, int(cy + r) + 1)
        x0, x1 = max(0, int(cx - r)), min(n, int(cx + r) + 1)
        g[f, y0:y1, x0:x1] = np.maximum(g[f, y0:y1, x0:x1], top)


def load_map(scene):
    path = bpy.data.filepath
    key = "%s-%d-%d.npz" % (os.path.splitext(os.path.basename(path))[0], int(os.path.getmtime(path)) if path else 0, MAP_RES)
    cache = os.path.join(CACHE, key)
    if os.path.exists(cache):
        d = np.load(cache)
        h, w = d["h"], d["w"]
    else:
        t = time.perf_counter()
        h, w = bake_map(scene)
        os.makedirs(CACHE, exist_ok=True)
        np.savez_compressed(cache, h=h, w=w)
        print("flight_rt: clearance map baked in %.1f s -> %s" % (time.perf_counter() - t, cache))
    g = conservative(h)
    stamp_pyramids(scene, g)
    return ClearanceMap(g, w, find_regions(h, w), h)


# ---------------------------------------------------------------- capstone lamps
def lamp_sight(scene, cam, dt):
    """A capstone lamp's colour fades to black while land stands between it and the camera within LAMP_NEAR: behind a
    ridge its halo hung in the night fog as an orb (CAM_9). One lamp tested per frame, in turn; farther lamps shine.
    Per lamp [object, colour, shown 0..1, wanted]; the build's colour is kept on the lamp (lamp_rgb) for a restart."""
    lamps = _state.get("lamps")
    if lamps is None:
        lamps = _state["lamps"] = []
        for o in scene.objects:
            if o.name.startswith("Lamp_Capstone."):
                o["lamp_rgb"] = tuple(o.get("lamp_rgb", o.data.color))
                lamps.append([o, tuple(o["lamp_rgb"]), 1.0, 1.0])
                o.data.color = o["lamp_rgb"]
    if not lamps:
        return
    L = lamps[_state["n"] % len(lamps)]
    p = tuple(L[0].matrix_world.translation)
    L[3] = 0.0 if math.dist(cam, p) < LAMP_NEAR and _state["map"].land_between(cam, p) else 1.0
    for L in lamps:
        if L[2] != L[3]:
            L[2] = min(max(L[2] + math.copysign(dt / LAMP_FADE, L[3] - L[2]), 0.0), 1.0)
            L[0].data.color = [c * L[2] for c in L[1]]


def lamps_reset():
    for o, rgb, _, _ in _state.pop("lamps", None) or ():
        o.data.color = rgb


# ---------------------------------------------------------------- rig, targets and the frame
def ensure_rig(scene):
    rig = scene.objects.get(RIG)
    if rig is None:
        cd = bpy.data.cameras.new(RIG)
        cd.clip_start, cd.clip_end = 1.0, pc.CLIP_FAR
        rig = bpy.data.objects.new(RIG, cd)
        scene.collection.objects.link(rig)
    rig.data.clip_end = pc.CLIP_FAR
    return rig


def place(ob, pose):
    p, fwd, up, lens, props = pose
    z = -Vector(fwd).normalized()
    y = Vector(up)
    x = y.cross(z).normalized()
    y = z.cross(x)
    ob.matrix_world = Matrix.Translation(Vector(p)) @ Matrix((x, y, z)).transposed().to_4x4()
    if abs(ob.data.lens - lens) > 1e-4:
        ob.data.lens = lens
    for k, v in props.items():
        if k == "clip":
            if abs(ob.data.clip_start - v) > 1e-3:
                ob.data.clip_start = v
        else:
            ob[k] = v


def ground_targets(scene, cmap):
    """name -> path_camera.Target of the build's PathTarget.<name> empties, on the clearance map's ground."""
    out = {}
    for ob in scene.objects:
        if ob.name.startswith(TARGET_PREFIX):
            u = fl.norm(fl.sub(tuple(ob.location), fl.CENTRE))
            out[ob.name[len(TARGET_PREFIX):]] = pc.ground_target(ob.name[len(TARGET_PREFIX):], u, cmap, float(ob.get("path_size", 200.0)),
                                                                 float(ob.get("path_lift", 0.0)))
    return out


def live_targets(scene):
    """The ground targets with the moon, the sun and the planet as they are this frame."""
    s = scene.get
    t = dict(_state["targets"])
    moon = (s("rt_moon_x", 0.0), s("rt_moon_y", 0.0), s("rt_moon_z", 50000.0))
    sun = fl.norm((s("rt_sun_x", 0.0), s("rt_sun_y", 1.0), s("rt_sun_z", 0.0)))
    t["moon"] = pc.Target("moon", "sky", moon, MOON_R * max(s("vj_moon", 1.0), 0.05))
    t["sun"] = pc.Target("sun", "sky", fl.add(fl.CENTRE, sun, SUN_DIST), SUN_SIZE)
    t["planet"] = pc.Target("planet", "planet", fl.CENTRE, fl.R)
    return t


def choice(scene, key, names):
    return names[int(fl.clamp(round(scene.get(key, 0.0)), 0, len(names) - 1))]


def frame(scene, depsgraph=None):
    now = time.perf_counter()
    dt = 0.0 if _state["last"] is None else min(max(now - _state["last"], 0.0), 0.1)
    _state["last"] = now
    rt = bpy.app.driver_namespace.get("vj_runtime")     # the runtime's clock: a check that stops it stops this too
    if rt is not None:
        dt = rt.peek_dt(now, dt)
    if _state["map"] is None:
        return
    rig = ensure_rig(scene)
    if scene.camera != rig:
        scene.camera = rig
    drive = _state["drive"]
    if drive is None:
        drive = _state["drive"] = en.Drive(scene.get("vj_energy", en.E0))
    drive.step(dt, scene.get("vj_energy", en.E0), scene.get("vj_hit", 0.0), scene.get("rt_beat", 0.0))
    scene["rt_energy"], scene["rt_kick"] = drive.e, drive.kick
    P = _state["path"]
    if P is None:
        P = _state["path"] = pc.PathCamera(live_targets(scene), _state["map"])
    P.targets = live_targets(scene)
    path, target = choice(scene, "vj_path", pc.PATHS), choice(scene, "vj_target", pc.TARGETS)
    _state["view"] = "%s %s" % (path, target)
    pose = P.step(dt, path, target, scene.get("vj_height", 0.3), scene.get("vj_cam_speed", 1.0) * drive.speed,
                  scene.get("vj_blend", 30.0), drive)
    scene["rt_blending"] = 1.0 if P.blending() else 0.0
    _state["n"] += 1
    place(rig, pose)
    gpu_terrain.follow(scene, pose[0])
    lamp_sight(scene, tuple(rig.matrix_world.translation), dt)


def on_cut(scene, depsgraph=None):
    """Another camera set as scene.camera: the rig takes it back before the frame is drawn."""
    rig = scene.objects.get(RIG)
    if rig is not None and scene.camera is not None and scene.camera != rig:
        scene.camera = rig


def quiesce(seed=None):
    """The self-check's reset, per cell (synthwave_runtime.quiesce): the next frame starts the Drive and the Path
    Camera afresh (phase 0, the height on its fader), so the same controls show the same frames."""
    _state.update(drive=None, path=None)


def start():
    scene = bpy.context.scene
    if scene.objects.get("Planet_Hydro") is None or "PL_Surface" not in bpy.data.node_groups:
        print("flight_rt: not a planet scene, not started")
        return
    _state["map"] = load_map(scene)
    _state["targets"] = ground_targets(scene, _state["map"])
    rig = ensure_rig(scene)
    for handlers, fn in ((bpy.app.handlers.frame_change_pre, frame), (bpy.app.handlers.depsgraph_update_pre, on_cut)):
        for h in list(handlers):
            if getattr(h, "__name__", "") == fn.__name__ and getattr(h, "__module__", "") == __name__:
                handlers.remove(h)
        handlers.insert(0, fn)
    scene.camera = rig
    bpy.app.driver_namespace[SHOT_KEY] = lambda: _state.get("view")
    gpu_terrain.start(scene, probe_group)
    _state["terrain"] = True
    print("flight_rt: started, Path Camera on %s, targets %s" % (RIG, ", ".join(sorted(_state["targets"]))))


def stop():
    bpy.app.driver_namespace.pop(SHOT_KEY, None)
    lamps_reset()
    if _state["terrain"]:
        gpu_terrain.stop(bpy.context.scene)
        _state["terrain"] = False
    for handlers in (bpy.app.handlers.frame_change_pre, bpy.app.handlers.depsgraph_update_pre):
        for h in list(handlers):
            if getattr(h, "__module__", "") == __name__:
                handlers.remove(h)
