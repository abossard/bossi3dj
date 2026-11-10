"""Runtime of the Flight and the blended shots in the planet scene (docs/research/synthwave-flight.md).

Loaded by synthwave_runtime.py next to star_system.py; start() installs a frame handler that runs before the
others, so the planet runtime, the star system and the fog all read this frame's view.

- CAM_RIG is always scene.camera, the On-Air Camera. A cut from /vj/cam or the web page sets scene.camera to a shot
  camera; the depsgraph handler hands the rig back the same moment and the Director flies the rig to that shot
  (director.py), at /vj/blend times its duration (0: a cut).
- The Flight is one more shot: the camera CAM_<n> with vj_flight_cam, driven by /vj/flight and /vj/boost through
  flight.py. Its integrator runs while it is on air or being blended to.
- The rig carries the blended per-shot numbers (fog_k, fog_clear, fog_dip) that the planet runtime reads from
  scene.camera.
- Energy (energy.py): /vj/energy, /vj/hit and the pulse rt_beat drive every camera's move. A fixed shot gets an
  ellipse round its pose with its aim held (energy.move); shots on a path (path_period) run their path faster: the
  camera clock rt_cam_phase gains the Drive's rate (and a hit's swoop) on top of /vj/cam_speed. The Flight takes the
  energy and the hit as speed. The Director puts the kick and the pulse on the rig. rt_energy and rt_kick are written
  for the recorder.
- The clearance map: ground (conservative: a 3x3 max, pyramids stamped in) and water level over the whole Planet on
  a cube map, probed once from the planet's own PL_Surface group and cached under ~/Library/Caches. The Flight, the
  blends and their clearance floors read it.
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
import director as dr  # noqa: E402
import energy as en  # noqa: E402
import flight as fl  # noqa: E402
import lod_scene  # noqa: E402
import lod_stream as ls  # noqa: E402

RIG = "CAM_RIG"
FLIGHT_KEY = "vj_flight_cam"
SHOT_PROPS = {"fog_k": 1.0, "fog_clear": 180.0, "fog_dip": 0.005}
MAP_RES = 512                       # texels per cube face side: about 49 m
PYR_PAD = 25.0                      # m around a pyramid's footprint
CACHE = os.path.expanduser("~/Library/Caches/swiftvj-flight")
MOON_R = 11500.0
SUBJECT = 300.0                     # m down the view: the aim point of a shot that tracks nothing
_state = {"last": None, "director": None, "flight": None, "shot": None, "map": None, "fix": 0, "lod": False, "lod_ms": [],
          "every": 1, "n": 0, "drive": None}


# ---------------------------------------------------------------- the clearance map
def face_dirs(f, n):
    """Unit directions of the texel centres of cube face f, (n, n, 3), row = b, column = a."""
    t = -1.0 + (np.arange(n) + 0.5) * 2.0 / n
    a, b = np.meshgrid(t, t)
    nrm, u, v = (np.array(x) for x in ls.FACES[f])
    d = nrm[None, None, :] + np.tan(a * np.pi / 4.0)[..., None] * u + np.tan(b * np.pi / 4.0)[..., None] * v
    return d / np.linalg.norm(d, axis=-1, keepdims=True)


def probe_group(hydro):
    """A GN tree that moves each point to the Planet's surface along its own direction and stores its water level."""
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
    L.new(sw.outputs[0], go.inputs[0])
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

    def __init__(self, ground, water, cands):
        self.n = ground.shape[1]
        self.g, self.w, self.cands = ground, water, cands

    def _texel(self, u):
        f, a, b = ls.dir_face(u)
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
        f, a, b = ls.dir_face(u)
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
    return ClearanceMap(g, w, find_regions(h, w))


# ---------------------------------------------------------------- shots, rig and the frame
def ensure_cameras(scene):
    rig = scene.objects.get(RIG)
    if rig is None:
        cd = bpy.data.cameras.new(RIG)
        cd.clip_start, cd.clip_end = 1.0, 250000.0
        rig = bpy.data.objects.new(RIG, cd)
        scene.collection.objects.link(rig)
    fc = next((o for o in scene.objects if o.type == "CAMERA" and o.get(FLIGHT_KEY)), None)
    if fc is None:
        n = max((int(o.name[4:]) for o in scene.objects if o.type == "CAMERA" and o.name[4:].isdigit()), default=0) + 1
        cd = bpy.data.cameras.new("CAM_%d" % n)
        cd.clip_start, cd.clip_end = 1.0, 250000.0
        fc = bpy.data.objects.new("CAM_%d" % n, cd)
        fc[FLIGHT_KEY] = 1
        for k, v in SHOT_PROPS.items():
            fc[k] = v
        scene.collection.objects.link(fc)
        cam_range = scene.id_properties_ui("vj_cam") if "vj_cam" in scene else None
        if cam_range is not None:
            cam_range.update(max=float(n), soft_max=float(n))
    return rig, fc


def pose_of(ob, dg):
    m = ob.evaluated_get(dg).matrix_world
    r = m.to_3x3().normalized()
    fwd = tuple(-r.col[2])
    up = tuple(r.col[1])
    props = {k: float(ob.get(k, v)) for k, v in SHOT_PROPS.items()}
    return tuple(m.translation), fwd, up, ob.data.lens, props


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
        ob[k] = v


def moved_pose(ob, dg, drive):
    """A fixed shot's live pose with its energy move. Shots on a path move along it (the camera clock); the others
    get the ellipse round their aim point: the tracked target's distance down the view, or the planet centre's for
    the orbit views, or SUBJECT. The orbit views keep their lens (it fits the planet)."""
    pose = pose_of(ob, dg)
    if "path_period" in ob:
        return pose
    p, fwd = pose[0], pose[1]
    con = next((c for c in ob.constraints if c.type == "TRACK_TO" and c.target is not None), None)
    orbit = ob.get("lod") == "orbit"
    if con is not None:
        subject = fl.dot(fl.sub(tuple(con.target.matrix_world.translation), p), fwd)
    elif orbit:
        subject = fl.dot(fl.sub(fl.CENTRE, p), fwd)
    else:
        subject = SUBJECT
    u, h = dr.spherical(p)
    clear = h - _state["map"].surface(u)
    seed = (sum(map(ord, ob.name)) % 97) * 0.37          # each shot its own place on its ellipse
    moved = en.move(pose, max(subject, 20.0), clear, drive, seed, tighten=not orbit)
    u2, h2 = dr.spherical(moved[0])
    floor = min(_state["map"].surface(u2) + en.FLOOR, h)    # the move never goes lower than this, nor lifts the shot
    if h2 < floor:
        moved = (fl.add(moved[0], u2, floor - h2),) + moved[1:]
    return moved


def flight_pose(scene, dt, fc):
    s = scene.get
    sun = (s("rt_sun_x", 0.0), s("rt_sun_y", 1.0), s("rt_sun_z", 0.0))
    moon = ((s("rt_moon_x", 0.0), s("rt_moon_y", 0.0), s("rt_moon_z", 0.0)), MOON_R * s("vj_moon", 1.0))
    F = _state["flight"]
    if F is None:
        F = _state["flight"] = fl.Flight(_state["map"], seed=int(time.time()) % 100000, sun=sun)
    drive = _state["drive"]
    p, fwd, up, lens, info = F.step(dt, s("vj_flight", 0.0), s("vj_boost", 0.0), en.level(drive.e), drive.kick, sun,
                                   moon if moon[1] > 0.0 else None)
    w = info["w"]
    props = {"fog_k": fl.mix(w, (1.0, 1.0, 2.0, 1.5)), "fog_clear": fl.mix(w, (180.0, 600.0, 250.0, 150.0)),
             "fog_dip": math.sqrt(2.0 * max(info["clear"], 5.0) / fl.R)}
    pose = (p, fwd, up, lens, props)
    place(fc, pose)
    scene["rt_flight_stage"] = float(max(range(4), key=lambda k: w[k]))
    return pose


def frame(scene, depsgraph=None):
    now = time.perf_counter()
    dt = 0.0 if _state["last"] is None else min(max(now - _state["last"], 0.0), 0.1)
    _state["last"] = now
    if _state["map"] is None:
        return
    rig, fc = ensure_cameras(scene)
    if scene.camera is not None and scene.camera != rig:
        _state["shot"] = scene.camera
        scene.camera = rig
    shot = _state["shot"] or fc
    dg = bpy.context.evaluated_depsgraph_get()
    D = _state["director"]
    if D is None:
        D = _state["director"] = dr.Director()
    drive = _state["drive"]
    if drive is None:
        drive = _state["drive"] = en.Drive(scene.get("vj_energy", en.E0))
    drive.step(dt, scene.get("vj_energy", en.E0), scene.get("vj_hit", 0.0), scene.get("rt_beat", 0.0))
    scene["rt_energy"], scene["rt_kick"] = drive.e, drive.kick
    # the camera clock (synthwave_runtime adds dt * vj_cam_speed after this handler): paths run at the Drive's rate
    scene["rt_cam_phase"] = scene.get("rt_cam_phase", 0.0) + dt * scene.get("vj_cam_speed", 1.0) * (drive.speed - 1.0)
    target = flight_pose(scene, max(dt, 1e-3), fc) if shot == fc else moved_pose(shot, dg, drive)
    had = D.tr
    pose = D.step(dt, shot.name, target, scene.get("vj_blend", 1.0), _state["map"], drive)
    if _state["lod"] and D.tr is not None and D.tr is not had:      # a blend began: build the target's blocks ahead
        lod_scene.prewarm(target[0])
    up_r = fl.norm(fl.sub(pose[0], fl.CENTRE))         # the clearance floor under the rig during blends
    u, h = dr.spherical(pose[0])
    floor = _state["map"].surface(u) + 2.0
    if h < floor and not shot.get(FLIGHT_KEY) and D.tr is not None:
        pose = (fl.add(pose[0], up_r, floor - h),) + pose[1:]
        _state["fix"] += 1
    scene["rt_blending"] = 1.0 if D.tr is not None else 0.0
    _state["n"] += 1
    if _state["lod"] and _state["n"] % _state["every"] == 0:   # the terrain follows the rig (lod_scene)
        t = time.perf_counter()
        cut = shot.name != _state.get("lod_shot") and D.tr is None      # a hard cut: the jump is no speed
        _state["lod_shot"] = shot.name
        blocks = lod_scene.update(scene, pose[0], 0.0 if cut else fl.length(D.vel), 1.0 / max(dt, 1e-3) / _state["every"])
        _state["lod_ms"] = (_state["lod_ms"] + [(round((time.perf_counter() - t) * 1000.0, 2), blocks)])[-600:]
    if not (_state["lod"] and lod_scene.holding()):    # a cut shows when its terrain is ready (lod_scene.stage)
        place(rig, pose)
        _state["on_air"] = shot
    elif _state.get("on_air") not in (None, shot):     # meanwhile the old shot keeps moving (EN1)
        old = _state["on_air"]
        place(rig, flight_pose(scene, max(dt, 1e-3), fc) if old == fc else moved_pose(old, dg, drive))


def on_cut(scene, depsgraph=None):
    """A cut sets scene.camera to a shot; the rig takes it back before the frame is drawn."""
    rig = scene.objects.get(RIG)
    if rig is not None and scene.camera is not None and scene.camera != rig:
        _state["shot"] = scene.camera
        scene.camera = rig


def start():
    scene = bpy.context.scene
    if scene.objects.get("Planet_Hydro") is None or "PL_Surface" not in bpy.data.node_groups:
        print("flight_rt: not a planet scene, not started")
        return
    _state["map"] = load_map(scene)
    rig, fc = ensure_cameras(scene)
    _state["shot"] = scene.camera if scene.camera not in (None, rig) else fc
    for handlers, fn in ((bpy.app.handlers.frame_change_pre, frame), (bpy.app.handlers.depsgraph_update_pre, on_cut)):
        for h in list(handlers):
            if getattr(h, "__name__", "") == fn.__name__ and getattr(h, "__module__", "") == __name__:
                handlers.remove(h)
        handlers.insert(0, fn)
    scene.camera = rig
    lod_scene.start(scene, _state["map"])
    _state["lod"] = True
    dg = bpy.context.evaluated_depsgraph_get()
    for ob in scene.objects:                 # every fixed shot's blocks, built in the background
        if ob.type == "CAMERA" and ob.name[4:].isdigit() and not ob.get(FLIGHT_KEY) and "path_period" not in ob:
            lod_scene.prewarm(tuple(ob.evaluated_get(dg).matrix_world.translation))
    print("flight_rt: started, %d flight regions, Flight shot %s" % (len(_state["map"].cands), fc.name))


def stop():
    if _state["lod"]:
        lod_scene.stop(bpy.context.scene)
        _state["lod"] = False
    for handlers in (bpy.app.handlers.frame_change_pre, bpy.app.handlers.depsgraph_update_pre):
        for h in list(handlers):
            if getattr(h, "__module__", "") == __name__:
                handlers.remove(h)
    if _state["shot"] is not None:
        bpy.context.scene.camera = _state["shot"]
