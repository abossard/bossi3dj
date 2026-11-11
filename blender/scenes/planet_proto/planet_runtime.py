"""Runtime for planet_proto.blend (registered text block, runs on load with Auto Run).

- integrates the clocks the shaders read (rt_time, rt_grid_phase, rt_cam_phase,
  rt_fog_phase) and an idle 124 BPM rt_beat, like synthwave_runtime.py, unless that
  runtime is in the file (the planet grafted into the island scene) and runs them;
- writes rt_space (0 on the ground, 1 from about 12 km up), which turns the sky to space
  and lights the atmosphere rim;
- on a camera cut shows the camera's precomputed land, water and props set (no rebuild) and
  copies its baked flamingo flock into the Flamingos mesh; a flight switches to the set
  nearest the camera as it flies. The cut is handled before the new shot's first frame is
  evaluated (depsgraph_update_pre), so that frame already has its land, sky frame and aim.
  Without sets the anchor jumps under the new camera and the LOD is rebuilt once.
  A camera's "lod" property picks the
  mode: "surface" (anchor at the camera, horizon culling), "orbit" (anchor at the planet
  centre: one even level, no culling) or "follow" (anchor on the camera every frame).
  Scene property pl_lod_step > 0 also moves a surface anchor once the camera has
  travelled that many metres from it.
- with the Flight runtime (flight_rt.py) scene.camera is its On-Air rig: the sets, the anchor,
  the flock and a path shot's sky follow the shot behind the rig (driver_namespace vj_terrain),
  and while the Flight's streamed terrain is shown the sets' land and water stay hidden.
"""
import math
import time

import bpy

R = 16000.0
CENTER = (0.0, 0.0, -R)
ANCHOR = "LOD_Anchor"
LOD_OBJECTS = ("Planet", "Water", "Props")
IDLE_BPM, IDLE_DEPTH = 124.0, 0.45
SKY_FRAME = "Sky_Frame"
MODES = {   # mode: (anchor at centre, Cull: patches past the horizon at the lowest level, Min Level for Planet, Water)
    "surface": (False, True, 0, 0),      # water at the land's levels: one level finer, it stood 15 m under the fine
    "follow": (False, True, 0, 0),       # terrain, above a far coarse land quad (a water quad on a hilltop, CAM_4)
    "orbit": (True, False, 1, 1),
}
FLOCK_ATTRS = ("heading", "fdir", "delay", "phase")
TERRAIN_KEY = "vj_terrain"      # flight_rt: () -> (the shot whose sets are shown, the streamed terrain replaces them)
STREAMED = ("Planet.", "Water.")    # the sets' objects the streamed terrain replaces
_state = {"last": None, "camera": None, "set": None, "streamed": False}


def on_air(scene):
    """The shot camera the sets follow, and whether the Flight's streamed terrain is shown instead of their land and
    water: scene.camera and False without flight_rt."""
    f = bpy.app.driver_namespace.get(TERRAIN_KEY)
    if f is None:
        return scene.camera, False
    name, streamed = f()
    return (scene.objects.get(name) if name else None) or scene.camera, streamed


def set_input(ob, name, value):
    mod = ob.modifiers[0]
    for it in mod.node_group.interface.items_tree:
        if getattr(it, "in_out", "") == "INPUT" and it.name == name:
            sock = getattr(mod.properties.inputs, it.identifier)
            if sock.value != value:
                sock.value = value
                ob.update_tag()


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


def copy_flocks(scene, key):
    """Copies the set's baked flock spots (mesh Flock.<key>) into the island's Flamingos mesh, whose flight
    animates them every frame."""
    src, dst = bpy.data.meshes.get("Flock." + key), scene.objects.get("Flamingos")
    if src is None or dst is None:
        return
    n = len(src.vertices)
    co = [0.0] * (3 * n)
    src.vertices.foreach_get("co", co)
    out = dst.data
    out.clear_geometry()
    out.vertices.add(n)
    out.vertices.foreach_set("co", co)
    vals = [0.0] * n
    for name in FLOCK_ATTRS:
        src.attributes[name].data.foreach_get("value", vals)
        at = out.attributes.get(name) or out.attributes.new(name, "FLOAT", "POINT")
        at.data.foreach_set("value", vals)
    out.update()


def nearest_set(scene, cam):
    """The camera's precomputed set nearest to it (a flight path has several) and its anchor; None without sets."""
    keys = list(cam.get("lod_sets", []))
    anchors = [scene.objects.get("LOD_Anchor." + k) for k in keys]
    if not keys or None in anchors:
        return None
    c = cam.matrix_world.translation
    return min(zip(keys, anchors), key=lambda ka: (ka[1].location - c).length)


def show_lod_set(scene, key):
    """Shows the set's land, water and props and hides the others: hide_set for the viewport (hide_viewport would
    re-evaluate them) and visible_camera for renders."""
    for ob in scene.objects:
        k = ob.get("lod_set")
        if k is not None:
            on = k == key and not (_state["streamed"] and ob.name.startswith(STREAMED))
            if ob.visible_camera != on:
                ob.visible_camera = on
            if ob.hide_get() == on:
                ob.hide_set(not on)
    _state["set"] = key


def place_anchor(scene, cam):
    """Puts the LOD anchor where the camera's mode wants it (its land and water set's anchor when the scene has
    sets); returns True if it moved."""
    anchor = scene.objects.get(ANCHOR)
    if anchor is None or cam is None:
        return False
    centre, cull, lmin_land, lmin_water = MODES.get(cam.get("lod", "surface"), MODES["surface"])
    near = nearest_set(scene, cam)
    if near is not None:
        target = tuple(near[1].location)
        if near[0] != _state["set"]:
            show_lod_set(scene, near[0])
            copy_flocks(scene, near[0])
    else:
        target = CENTER if centre else tuple(cam.matrix_world.translation)
    place_sky(scene, (0.0, 0.0, 1.0) if centre else [a - b for a, b in zip(target, CENTER)])
    for name, lmin in zip(LOD_OBJECTS, (lmin_land, lmin_water, 0)):
        ob = scene.objects.get(name)
        if ob is not None and name != "Props":
            set_input(ob, "Cull", cull)
            set_input(ob, "Min Level", lmin)
    if tuple(anchor.location) == target:
        return False
    anchor.location = target
    return True


def update_lod(scene):
    cam, streamed = on_air(scene)
    if streamed != _state["streamed"]:
        _state["streamed"] = streamed
        if _state["set"] is not None:
            show_lod_set(scene, _state["set"])
    if cam is None:
        return
    mode = cam.get("lod", "surface")
    if cam != _state["camera"] or mode == "follow":
        _state["camera"] = cam
        place_anchor(scene, cam)
        return
    if "path_period" in cam and len(cam.get("lod_sets", [])) > 1:      # a flight: the set nearest the camera
        near = nearest_set(scene, cam)
        if near is not None and near[0] != _state["set"]:
            place_anchor(scene, cam)
        return
    step = scene.get("pl_lod_step", 0.0)
    anchor = scene.objects.get(ANCHOR)
    if mode == "surface" and step > 0.0 and anchor is not None:
        if (cam.matrix_world.translation - anchor.location).length > step:
            place_anchor(scene, cam)


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
    update_lod(scene)
    cam = None if _state["streamed"] else on_air(scene)[0]
    if free:
        place_sky(scene, [a - b for a, b in zip(c, CENTER)])        # the free view's own horizon
    elif cam is not None and "path_period" in cam and cam.get("lod", "surface") != "orbit":
        place_sky(scene, [a - b for a, b in zip(cam.matrix_world.translation, CENTER)])   # flights: the sky's horizon stays level


def on_cut(scene, depsgraph=None):
    """A cut (OSC or the web page sets scene.camera from a timer) is drawn before the next frame change, which
    showed the new camera with the old camera's land, sky frame, sun and aim for one frame. The frame-change
    work runs here instead, before that first frame is evaluated."""
    cam = on_air(scene)[0]
    if cam is None or cam == _state["camera"]:
        return
    planet_tick(scene)
    for h in list(bpy.app.handlers.frame_change_pre):
        if getattr(h, "__name__", "") == "synthwave_tick":
            h(scene)


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


def camera_range():
    """/vj/cam reaches every CAM_N (the planet adds shots past the island's CAM_6); the web page builds its
    camera buttons from this range. Runs after the island runtime has set its own range on load."""
    scene = bpy.context.scene
    n = max((int(o.name[4:]) for o in scene.objects if o.type == "CAMERA" and o.name[4:].isdigit()), default=0)
    if "vj_cam" in scene:
        scene.id_properties_ui("vj_cam").update(min=0.0, max=float(n), soft_min=0.0, soft_max=float(n))
    return None


def install():
    for handlers, fn in ((bpy.app.handlers.frame_change_pre, tick), (bpy.app.handlers.depsgraph_update_pre, on_cut)):
        for h in list(handlers):
            if getattr(h, "__name__", "") == fn.__name__:
                handlers.remove(h)
        handlers.append(fn)
    bpy.app.timers.register(camera_range, first_interval=1.0)
    if not bpy.app.background:
        bpy.app.timers.register(show_camera_view, first_interval=0.5)


install()
