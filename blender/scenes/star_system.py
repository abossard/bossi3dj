"""The planet scene's Star System: one sun, moon and star sky shared by every camera.

The Planet never turns; the sky turns about the spin axis AXIS through the planet centre, which puts the
camera area (the mesh pole) on the equator. The math and its checks are in
docs/research/synthwave-star-system.md and verify_star_system.py.

Each frame sync() solves, for the On-Air Camera:
- the spin angle theta that puts the sun at the Sun Height h(vj_night): 0 -> +20 deg, 0.5 -> horizon,
  1 -> -18 deg, always on the setting branch, so turning the knob back runs time backwards;
- the moon on its orbit (radius MOON_ORBIT, tilt MOON_TILT) at the Moon Phase vj_moon_phase (0 new, 1 full),
  with vj_eclipse (0..1) turning the line of nodes onto the sun line; near new moon it also pulls the moon
  onto the camera->sun ray, because the moon's parallax (up to 18.7 deg) would miss the sun otherwise;
- the Star Drift: stars turn by theta + beta, beta += dt * vj_star_speed * STAR_RATE.

It writes rt_sun_x/y/z (world direction to the sun), rt_sun_h (radians), rt_moon_x/y/z (world moon centre),
rt_sky_ang (theta) and rt_star_ang (theta + beta), and places the scene's bodies:
- objects with custom property vj_body = "sun" go to camera + s * vj_dist, local Z along the camera's
  up perpendicular to s (the stripes stay level), local Y along s;
- vj_body = "moon" goes to the moon centre, local -Y toward the planet centre (tidally locked), local Z
  along the orbit normal;
- every camera with vj_track = "sun" or "moon" (not only the On-Air Camera) gets its TRACK_TO target moved
  onto that body, raised to at least AIM_MIN above the horizon while the body is below it, so a cut to a
  tracking shot starts on its aim.
The sun height is measured from the camera's own up on the ground and from the camera area's up (POLE_UP) in
space, turned smoothly between them over rt_space (0 at 2 km up, 1 at 12 km).
It does nothing in a scene without PLANET_CENTRE (the island).
"""
import math

PLANET_CENTRE = "Planet_Centre"
RADIUS_KEY, DEFAULT_RADIUS = "pl_radius", 16000.0
AXIS = (1.0, 0.0, 0.0)            # spin axis: the camera area is on its equator and the sun sets toward +y
POLE_UP = (0.0, 0.0, 1.0)         # the camera area's up, used for orbit shots (rt_space 1)
MOON_ORBIT = 50000.0              # m from the planet centre; with an 11.5 km moon a true-size sun's umbra covers it
MOON_TILT = math.radians(40.0)    # > 33.7 deg, so ordinary full moons pass beside the shadow (check 11c)
STAR_RATE = math.radians(1.0)     # rad/s of Star Drift at vj_star_speed 1
HEIGHT_DAY, HEIGHT_NIGHT = math.radians(20.0), math.radians(-18.0)
AIM_MIN = math.radians(5.0)       # a tracking camera never aims lower than this above its horizon

_state = {"beta": 0.0}


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def add(a, b, k=1.0):
    return (a[0] + k * b[0], a[1] + k * b[1], a[2] + k * b[2])


def scale(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def norm(a):
    n = math.sqrt(dot(a, a))
    return scale(a, 1.0 / n) if n > 1e-12 else (0.0, 0.0, 1.0)


def rot(axis, ang, v):
    """Rodrigues: v turned by ang about the unit axis."""
    c, s = math.cos(ang), math.sin(ang)
    return add(add(scale(v, c), cross(axis, v), s), axis, dot(axis, v) * (1.0 - c))


def night_to_height(n):
    """Sun Height for vj_night: linear in each half, 0 -> +20 deg, 0.5 -> 0, 1 -> -18 deg."""
    n = min(max(n, 0.0), 1.0)
    return HEIGHT_DAY * (1.0 - 2.0 * n) if n < 0.5 else HEIGHT_NIGHT * (2.0 * n - 1.0)


def sun_dir(theta):
    """theta 0: the sun at the camera area's zenith; growing theta turns it down toward +y."""
    return rot(AXIS, -theta, POLE_UP)


def solve_theta(h, up):
    """The spin angle that puts the sun at height h above the horizon of `up`, on the setting branch.
    sin h = up . sun_dir(theta) = a cos theta + b sin theta."""
    a, b = dot(up, sun_dir(0.0)), dot(up, sun_dir(math.pi / 2.0))
    r = math.hypot(a, b)
    return math.atan2(b, a) + math.acos(min(max(math.sin(h) / max(r, 1e-9), -1.0), 1.0))


def moon_centre(centre, s, phase, eclipse, cam):
    """The moon at elongation phase*pi from the sun on its tilted orbit; vj_eclipse turns the line of nodes
    onto the sun line (lunar eclipse at full) and, near new moon, onto the camera->sun ray (solar eclipse)."""
    e = min(max(eclipse, 0.0), 1.0)
    elong = math.pi * min(max(phase, 0.0), 1.0)
    nodes = rot(AXIS, (1.0 - e) * math.pi / 2.0, s)              # line of nodes, in the sun's path plane
    normal = rot(nodes, MOON_TILT, AXIS)                         # tilted orbit normal
    s_p = norm(add(s, normal, -dot(s, normal)))                  # the sun projected into the orbit plane
    w = rot(normal, elong, s_p)
    k_new = e * max(math.cos(elong), 0.0) ** 2
    if k_new > 0.0:
        o = add(cam, centre, -1.0)                               # camera->sun ray meets the orbit sphere
        b = dot(o, s)
        disc = b * b - (dot(o, o) - MOON_ORBIT * MOON_ORBIT)
        if disc >= 0.0:
            topo = norm(add(o, s, -b + math.sqrt(disc)))
            w = norm(add(scale(w, 1.0 - k_new), topo, k_new))
    return add(centre, w, MOON_ORBIT), normal


def smoothstep(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3.0 - 2.0 * x)


def view_up(centre, cam, space):
    """The up the Sun Height is measured from: the camera's own (radial) at rt_space 0, POLE_UP at 1, turned
    between them along the great circle (a slerp) over smoothstep(rt_space). Switched at rt_space > 0, the sun
    jumped as a camera rose through 2 km. A camera exactly opposite POLE_UP turns about AXIS."""
    k = smoothstep(space)
    radial = norm(add(cam, centre, -1.0))
    if k <= 0.0:
        return radial
    if k >= 1.0:
        return POLE_UP
    c = min(max(dot(radial, POLE_UP), -1.0), 1.0)
    axis = cross(radial, POLE_UP)
    axis = norm(axis) if dot(axis, axis) > 1e-12 else AXIS
    return norm(rot(axis, k * math.acos(c), radial))


def solve(centre, radius, cam, space, night, phase, eclipse, beta):
    """Pure: everything sync() writes, from the On-Air Camera position and the controls."""
    up = view_up(centre, cam, space)
    h = night_to_height(night)
    theta = solve_theta(h, up)
    s = sun_dir(theta)
    k = smoothstep(space)                  # the moon's parallax viewpoint moves the same way, camera to pole
    pole = add(centre, POLE_UP, radius)
    view = cam if k <= 0.0 else pole if k >= 1.0 else add(scale(cam, 1.0 - k), pole, k)
    moon, normal = moon_centre(centre, s, phase, eclipse, view)
    return {"up": up, "h": h, "theta": theta, "sun": s, "moon": moon, "moon_normal": normal, "star": theta + beta}


def aim_point(cam, up, body):
    """Where a tracking camera looks: at the body, but never lower than AIM_MIN above its horizon, so a moon
    below the horizon keeps the shot on the sky where it will rise instead of on the ground."""
    v = add(body, cam, -1.0)
    dist = math.sqrt(dot(v, v))
    v = scale(v, 1.0 / dist)
    el = math.asin(min(max(dot(v, up), -1.0), 1.0))
    if el >= AIM_MIN:
        return body
    flat = add(v, up, -dot(v, up))
    flat = norm(flat) if dot(flat, flat) > 1e-12 else norm(cross(up, AXIS))
    return add(cam, add(scale(flat, math.cos(AIM_MIN)), up, math.sin(AIM_MIN)), dist)


def basis(z, y):
    """A rotation matrix (rows) with local Z along z and local Y as close to y as possible."""
    from mathutils import Matrix, Vector
    z = Vector(z).normalized()
    y = (Vector(y) - z * Vector(y).dot(z)).normalized()
    return Matrix((y.cross(z), y, z)).transposed()


def sync(scene, dt):
    centre_ob = scene.objects.get(PLANET_CENTRE)
    cam = scene.camera
    if centre_ob is None or cam is None:
        return
    from mathutils import Matrix, Vector
    centre = tuple(centre_ob.matrix_world.translation)
    cam_p = tuple(cam.matrix_world.translation)
    _state["beta"] = (_state["beta"] + dt * scene.get("vj_star_speed", 0.0) * STAR_RATE) % (2.0 * math.pi)
    r = solve(centre, scene.get(RADIUS_KEY, DEFAULT_RADIUS), cam_p, scene.get("rt_space", 0.0),
              scene.get("vj_night", 0.0), scene.get("vj_moon_phase", 1.0), scene.get("vj_eclipse", 0.0),
              _state["beta"])
    s, moon = r["sun"], r["moon"]
    scene["rt_sun_x"], scene["rt_sun_y"], scene["rt_sun_z"] = s
    scene["rt_moon_x"], scene["rt_moon_y"], scene["rt_moon_z"] = moon
    scene["rt_sun_h"], scene["rt_sky_ang"] = r["h"], r["theta"]
    scene["rt_star_ang"] = r["star"] % (2.0 * math.pi)
    sun_up = add(r["up"], s, -dot(r["up"], s))                   # the camera's up, perpendicular to the sun line
    bodies, trackers = {}, []
    for ob in scene.objects:
        if ob.type == "CAMERA" and ob.get("vj_track") in ("sun", "moon"):
            trackers.append(ob)
        kind = ob.get("vj_body")
        if kind == "sun":
            p = add(cam_p, s, ob.get("vj_dist", 150000.0))
            ob.matrix_world = Matrix.Translation(Vector(p)) @ basis(sun_up, s).to_4x4() @ Matrix.Diagonal(ob.matrix_world.to_scale()).to_4x4()
            bodies["sun"] = p
        elif kind == "moon":
            face = add(centre, moon, -1.0)                       # -Y faces the planet centre: Y points away
            ob.matrix_world = Matrix.Translation(Vector(moon)) @ basis(r["moon_normal"], face).to_4x4() @ Matrix.Diagonal(ob.matrix_world.to_scale()).to_4x4()
            bodies["moon"] = moon
    # every tracking camera, each from its own place (no depsgraph update: only their targets move). Off air
    # they are ground shots: their up is their own radial
    for tc in trackers:
        target = tc["vj_track"]
        if tc == cam:
            p_, up_ = cam_p, r["up"]
            body = bodies.get(target) or (add(cam_p, s, 150000.0) if target == "sun" else moon)
        else:
            p_ = tuple(tc.matrix_world.translation)
            up_ = norm(add(p_, centre, -1.0))
            body = add(p_, s, 150000.0) if target == "sun" else moon
        p = aim_point(p_, up_, body)
        for con in tc.constraints:
            if con.type == "TRACK_TO" and con.target is not None:
                con.target.matrix_world.translation = Vector(p)
