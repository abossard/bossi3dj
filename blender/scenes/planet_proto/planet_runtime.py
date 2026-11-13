"""Runtime for planet_proto.blend (registered text block, runs on load with Auto Run).

- integrates the clocks the shaders read (rt_time, rt_grid_phase, rt_cam_phase,
  rt_fog_phase) and an idle 124 BPM rt_beat, like synthwave_runtime.py, unless that
  runtime is in the file (the planet grafted into the island scene) and runs them;
- writes rt_space (0 on the ground, 1 from about 12 km up), which turns the sky to space
  and lights the atmosphere rim;
- turns the sky frame under the viewer (the On-Air Camera, or a free 3D view);
- props and the flamingo flock follow the camera: LOD_Anchor moves under it once its ground point is PROPS_STEP from
  the anchor while it is lower than PROPS_TOP, and the flock is copied from Flock_Birds evaluated there. The land and
  water are the streamed terrain (flight_rt.py, lod_scene), which follows the camera on its own.
"""
import math
import time

import bpy

R = 16000.0
CENTER = (0.0, 0.0, -R)
ANCHOR = "LOD_Anchor"
IDLE_BPM, IDLE_DEPTH = 124.0, 0.45
SKY_FRAME = "Sky_Frame"
FLOCK_ATTRS = ("heading", "fdir", "delay", "phase")
PROPS_STEP = 600.0      # m the camera's ground point gets from the anchor before props and flock follow
PROPS_TOP = 3000.0      # m over sea level above which they stay put (too small to see)
_state = {"last": None}


def place_sky(scene, up):
    """Turns the sky frame to the shot's radial up: shaders read rt_up_*, sun and fog ride on Sky_Frame."""
    from mathutils import Matrix, Vector
    frame = scene.objects.get(SKY_FRAME)
    if frame is None:        # grafted into the island scene: its sky stays in world space
        return
    up = Vector(up).normalized()
    north = (Vector((0.0, 1.0, 0.0)) - up * up.y).normalized()
    east = north.cross(up)
    scene["rt_up_x"], scene["rt_up_y"], scene["rt_up_z"] = up
    rot = Matrix((east, north, up)).transposed().to_4x4()
    frame.matrix_world = Matrix.Translation(Vector(CENTER) + up * R) @ rot


def copy_flock(scene):
    """Copies the flock spots Flock_Birds makes round the anchor into the island's Flamingos mesh, whose flight
    animates them every frame."""
    src_ob, dst = scene.objects.get("Flock_Birds"), scene.objects.get("Flamingos")
    if src_ob is None or dst is None:
        return
    src = src_ob.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
    n = len(src.vertices)
    co = [0.0] * (3 * n)
    src.vertices.foreach_get("co", co)
    out = dst.data
    out.clear_geometry()
    out.vertices.add(n)
    out.vertices.foreach_set("co", co)
    vals = [0.0] * n
    for name in FLOCK_ATTRS:
        if name in src.attributes:
            src.attributes[name].data.foreach_get("value", vals)
        at = out.attributes.get(name) or out.attributes.new(name, "FLOAT", "POINT")
        at.data.foreach_set("value", vals)
    out.update()


def follow_props(scene, c):
    """Moves LOD_Anchor to the ground point under c (on the sphere of radius R) when it is PROPS_STEP from it and c is
    under PROPS_TOP; then the props re-scatter there and the flock is copied."""
    from mathutils import Vector
    anchor = scene.objects.get(ANCHOR)
    if anchor is None or c is None:
        return False
    rel = Vector(c) - Vector(CENTER)
    if rel.length - R > PROPS_TOP:
        return False
    g = Vector(CENTER) + rel.normalized() * R
    a = Vector(CENTER) + (anchor.location - Vector(CENTER)).normalized() * R
    if (g - a).length < PROPS_STEP and _state.get("flock"):     # the first call copies the flock where the anchor is
        return False
    anchor.location = g
    copy_flock(scene)
    _state["flock"] = True
    return True


def tick(scene, depsgraph=None):
    if bpy.data.texts.get("vj_loader.py") is not None:     # grafted: the island runtime runs the clocks
        planet_tick(scene)
        return
    now = time.perf_counter()
    dt = 0.0 if _state["last"] is None else min(max(now - _state["last"], 0.0), 0.1)
    _state["last"] = now
    t = scene.get("rt_time", 0.0) + dt
    scene["rt_time"] = t
    scene["rt_grid_phase"] = scene.get("rt_grid_phase", 0.0) + dt * scene.get("vj_grid_speed", 0.6)
    scene["rt_cam_phase"] = scene.get("rt_cam_phase", 0.0) + dt * scene.get("vj_cam_speed", 1.0)
    scene["rt_fog_phase"] = scene.get("rt_fog_phase", 0.0) + dt * scene.get("vj_fog_speed", 10.0)
    phase = (t * IDLE_BPM / 60.0) % 1.0
    scene["rt_beat"] = max(scene.get("vj_beat", 0.0), math.exp(-5.0 * phase) * IDLE_DEPTH)
    planet_tick(scene)
    scene.update_tag()


def viewer(scene):
    """Where the scene is seen from: a 3D view that is not looking through the camera (a free view, zoomed out by
    hand) wins over the On-Air Camera, so the space blend, sky frame and horizon follow that view."""
    wm = bpy.context.window_manager
    for win in (wm.windows if wm else ()):
        for area in win.screen.areas:
            if area.type == "VIEW_3D" and area.spaces[0].region_3d.view_perspective != "CAMERA":
                return area.spaces[0].region_3d.view_matrix.inverted().translation, True
    return (scene.camera.matrix_world.translation if scene.camera else None), False


def moon_far(scene):
    """Cameras with pl_moon_far (m) sit that far behind the moon and 0.6 of it to the side, looking at the planet
    centre: the moon's far side in front, the planet beside it (straight behind, the moon hid the planet)."""
    from mathutils import Matrix, Vector
    m = Vector((scene.get("rt_moon_x", 0.0), scene.get("rt_moon_y", 0.0), scene.get("rt_moon_z", 0.0)))
    out = (m - Vector(CENTER)).normalized()
    # to the side toward the sun, so the moon's sunlit limb faces the camera: on the far side from the sun it was a
    # near-black disc with the sun's glare at its edge (CAM_SYS_MOON)
    s = Vector((scene.get("rt_sun_x", 0.0), scene.get("rt_sun_y", 0.0), scene.get("rt_sun_z", 0.0)))
    side = s - out * s.dot(out)
    if side.length < 1e-3 * max(s.length, 1e-9):
        side = out.cross(Vector((0.0, 0.0, 1.0)))
    side = (side if side.length > 1e-6 else Vector((1.0, 0.0, 0.0))).normalized()
    for ob in scene.objects:
        d = ob.get("pl_moon_far")
        if d is None or out.length < 0.5:
            continue
        p = m + out * d + side * (0.6 * d)
        z = (p - Vector(CENTER)).normalized()
        x = Vector((0.0, 0.0, 1.0)).cross(z)
        x = (x if x.length > 1e-6 else Vector((1.0, 0.0, 0.0))).normalized()
        ob.matrix_world = Matrix.Translation(p) @ Matrix((x, z.cross(x), z)).transposed().to_4x4()


def sun_rel(scene):
    """Cameras with pl_sun_rel (distance, angle in degrees, lead in m) sit that far from the planet centre, at that angle
    off the line behind the planet from the sun, looking at the point `lead` from the centre toward the sun: the sun,
    its glare and a lit crescent in frame at any time of day."""
    from mathutils import Matrix, Vector
    s = Vector((scene.get("rt_sun_x", 0.0), scene.get("rt_sun_y", 0.0), scene.get("rt_sun_z", 1.0)))
    if s.length < 0.5:
        return
    s.normalize()
    side = Vector((1.0, 0.0, 0.0))       # the spin axis: the sun's path is perpendicular to it
    c0 = Vector(CENTER)
    for ob in scene.objects:
        rel = ob.get("pl_sun_rel")
        if rel is None:
            continue
        d, a, lead = rel[0], math.radians(rel[1]), rel[2]
        p = c0 + (-s * math.cos(a) + side * math.sin(a)) * d
        z = (p - (c0 + s * lead)).normalized()            # the camera looks along -z, the spin axis across the frame
        x = side - z * side.dot(z)
        x = (x if x.length > 1e-6 else Vector((0.0, 1.0, 0.0))).normalized()
        ob.matrix_world = Matrix.Translation(p) @ Matrix((x, z.cross(x), z)).transposed().to_4x4()


def planet_tick(scene):
    c, free = viewer(scene)
    if c is not None:
        alt = math.dist(tuple(c), CENTER) - R
        scene["rt_space"] = min(max((alt - 2000.0) / 10000.0, 0.0), 1.0)
        scene["rt_cam_x"], scene["rt_cam_y"], scene["rt_cam_z"] = tuple(c)     # the moon's direction in the sky shaders
        scene["rt_fog_clear"] = float(scene.camera.get("fog_clear", 180.0)) if scene.camera else 180.0   # out to the shot's subject
        scene["rt_fog_dip"] = float(scene.camera.get("fog_dip", 0.005)) if scene.camera else 0.005      # the fog's horizon
        scene["rt_fog_k"] = float(scene.camera.get("fog_k", 1.0)) if scene.camera else 1.0             # and strength
    moon_far(scene)
    sun_rel(scene)
    if c is not None:
        place_sky(scene, [a - b for a, b in zip(c, CENTER)])
        if not free:
            follow_props(scene, c)


def show_camera_view():
    """Rendered camera view in every 3D view: the file's own layout is lost when Load UI is off."""
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                sp = area.spaces[0]
                sp.shading.type = "RENDERED"
                sp.shading.use_compositor = "ALWAYS"
                sp.overlay.show_overlays = False
                sp.show_gizmo = False
                sp.clip_start, sp.clip_end = 2.0, 1.0e6        # a free view zoomed out over the whole system
                sp.region_3d.view_perspective = "CAMERA"
    return None


def install():
    for h in list(bpy.app.handlers.depsgraph_update_pre):     # the old cut handler, from a file saved before
        if getattr(h, "__name__", "") == "on_cut" and getattr(h, "__module__", "") == __name__:
            bpy.app.handlers.depsgraph_update_pre.remove(h)
    for h in list(bpy.app.handlers.frame_change_pre):
        if getattr(h, "__name__", "") == tick.__name__:
            bpy.app.handlers.frame_change_pre.remove(h)
    bpy.app.handlers.frame_change_pre.append(tick)
    if not bpy.app.background:
        bpy.app.timers.register(show_camera_view, first_interval=0.5)


install()
