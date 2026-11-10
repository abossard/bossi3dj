"""Numerical checks for the planet / sun / moon vector math. Pure numpy, no Blender.

Frames (right-handed, z up):
  I  inertial: ecliptic plane = xy, sun direction s fixed (distant light).
  B  planet body: spin axis = +z_B, prime meridian = +x_B. B = Rz(theta) . I-tilt.
  A planet point at latitude phi, longitude L (east positive) has body position R*u(phi, L).
"""
import numpy as np

rng = np.random.default_rng(7)
D = np.pi / 180.0
fails = []


def check(name, err, tol):
    ok = err <= tol
    print("%-58s max err %.3e  (tol %.0e)  %s" % (name, err, tol, "ok" if ok else "FAIL"))
    if not ok:
        fails.append(name)


def Rx(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def Rz(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def unit(phi, lon):
    return np.array([np.cos(phi) * np.cos(lon), np.cos(phi) * np.sin(lon), np.sin(phi)])


def enu(up):
    """East, north, up at a surface point (body frame). East = z x up, north = up x east."""
    e = np.cross([0.0, 0.0, 1.0], up)
    e /= np.linalg.norm(e)
    return e, np.cross(up, e), up


def alt_az(v, up):
    """Elevation and azimuth (clockwise from north, 0..360) of direction v seen from up."""
    e, n, u = enu(up)
    v = v / np.linalg.norm(v)
    return np.arcsin(np.clip(v @ u, -1, 1)), np.arctan2(v @ e, v @ n) % (2 * np.pi)


# 1. vector elevation/azimuth == NOAA spherical formulas
# NOAA: cos z = sin lat sin decl + cos lat cos decl cos ha ;
#       cos(180 - az) = -(sin lat cos z - sin decl) / (cos lat sin z), az > 180 when ha > 0 (afternoon).
# Sun in body frame at hour angle ha: the sun sits at longitude L - ha (west of the site by ha).
e_alt = e_az = e_noaa = 0.0
for _ in range(20000):
    lat, decl, ha = rng.uniform(-80, 80) * D, rng.uniform(-23.44, 23.44) * D, rng.uniform(-179, 179) * D
    lon = rng.uniform(-180, 180) * D
    s_b = unit(decl, lon - ha)
    alt, az = alt_az(s_b, unit(lat, lon))
    cz = np.sin(lat) * np.sin(decl) + np.cos(lat) * np.cos(decl) * np.cos(ha)
    z = np.arccos(cz)
    e_alt = max(e_alt, abs(alt - (np.pi / 2 - z)))
    if np.sin(z) > 1e-3 and abs(np.cos(lat)) > 1e-3:
        x = (np.sin(decl) - np.sin(lat) * np.cos(z)) / (np.cos(lat) * np.sin(z))
        a = np.arccos(np.clip(x, -1, 1))                      # standard: cos az = (sin d - sin lat cos z) / (cos lat sin z)
        a = 2 * np.pi - a if ha > 0 else a
        e_az = max(e_az, abs((az - a + np.pi) % (2 * np.pi) - np.pi) if abs(ha) > 1e-3 else 0.0)
        noaa = np.pi - np.arccos(np.clip(-(np.sin(lat) * np.cos(z) - np.sin(decl)) / (np.cos(lat) * np.sin(z)), -1, 1))
        e_noaa = max(e_noaa, abs(noaa - (np.pi - a if ha <= 0 else a - np.pi)) if abs(ha) > 1e-3 else 0.0)
check("1a elevation: up.s vs NOAA zenith formula", e_alt / D, 1e-9)
check("1b azimuth: atan2(s.e, s.n) vs standard azimuth + quadrant rule", e_az / D, 1e-6)
check("1c NOAA PDF azimuth as printed == 180 - az (north-south mirror)", e_noaa / D, 1e-6)

# 2. tilt + spin: declination of the sun == obliquity-driven, and hour angle == theta-driven
#    Sun at ecliptic longitude lam: s_I = (cos lam, sin lam, 0). Body axis tilted by eps about x_I,
#    then spun by theta: s_B = Rz(-theta) Rx(+eps) s_I (ecliptic -> equator). Expect sin(decl) = sin eps sin lam.
eps = 23.44 * D
err = 0.0
for _ in range(5000):
    lam, th = rng.uniform(0, 2 * np.pi), rng.uniform(0, 2 * np.pi)
    s_b = Rz(-th) @ Rx(eps) @ np.array([np.cos(lam), np.sin(lam), 0.0])
    err = max(err, abs(np.arcsin(s_b[2]) - np.arcsin(np.sin(eps) * np.sin(lam))))
check("2  decl from tilt: asin(s_B.z) == asin(sin eps sin lam)", err / D, 1e-9)

# 3. spinning the planet == counter-spinning the sky (what the scene would do: planet static, sky rotates)
#    Observer world position with planet spun: p_W = M p_B, sun s_W. Sky-rotation version keeps p_B and
#    uses s' = M^T s_W. Elevation/azimuth must agree because ENU rotates with M.
err = 0.0
for _ in range(5000):
    M = Rz(rng.uniform(0, 6.3)) @ Rx(eps)
    up_b = unit(rng.uniform(-1.4, 1.4), rng.uniform(-3.1, 3.1))
    s_w = unit(rng.uniform(-1.5, 1.5), rng.uniform(-3.1, 3.1))
    up_w = M @ up_b
    # ENU of the spun planet: east = (M z) x up_w
    e_w = np.cross(M @ [0, 0, 1.0], up_w); e_w /= np.linalg.norm(e_w)
    n_w = np.cross(up_w, e_w)
    a1 = (np.arcsin(s_w @ up_w), np.arctan2(s_w @ e_w, s_w @ n_w) % (2 * np.pi))
    a2 = alt_az(M.T @ s_w, up_b)
    err = max(err, abs(a1[0] - a2[0]), abs((a1[1] - a2[1] + np.pi) % (2 * np.pi) - np.pi))
check("3  spin planet == counter-spin sky (alt, az)", err / D, 1e-9)

# 4. inverse: spin angle theta that puts the sun at elevation h for a site (morning or evening)
#    cos H = (sin h - sin phi sin d) / (cos phi cos d); H < 0 morning, H > 0 evening; sun longitude = L - H.
#    With the sun fixed in the inertial frame at body longitude lon_s(theta) = lon_s0 - theta.
err, unreachable = 0.0, 0
for _ in range(20000):
    phi, d, h = rng.uniform(-70, 70) * D, rng.uniform(-23.44, 23.44) * D, rng.uniform(-18, 60) * D
    L, lon_s0 = rng.uniform(-3.1, 3.1), rng.uniform(-3.1, 3.1)
    c = (np.sin(h) - np.sin(phi) * np.sin(d)) / (np.cos(phi) * np.cos(d))
    if abs(c) > 1:
        unreachable += 1          # polar day / night: that elevation never happens on this date
        continue
    for sign in (-1, 1):
        H = sign * np.arccos(c)
        theta = lon_s0 - (L - H)
        s_b = unit(d, lon_s0 - theta)
        err = max(err, abs(alt_az(s_b, unit(phi, L))[0] - h))
check("4  inverse spin for a target elevation (forward re-check)", err / D, 1e-9)
print("   (%d of 20000 targets unreachable: polar day/night, must be clamped)" % unreachable)

# 5. periods: solar day from sidereal day, synodic month from sidereal month (NASA fact sheets)
year, sid_day, sid_month = 365.256363, 23.9345 / 24.0, 27.3217
solar = 1 / (1 / sid_day - 1 / year)
synodic = 1 / (1 / sid_month - 1 / year)
check("5a solar day from sidereal day [h] vs 24.0000", abs(solar * 24 - 24.0), 2e-3)
check("5b synodic month from sidereal [d] vs 29.53", abs(synodic - 29.53), 6e-3)

# 6. moon illuminated fraction: (1 + cos i)/2 with i = angle at the moon between sun and observer,
#    checked against a lit sphere: fraction of the visible disc area where n.s > 0 (orthographic).
def lit_fraction(s_m, view, n=400):
    """view: unit vector moon -> observer. Sample the visible disc, count lit points."""
    w = view
    a = np.cross(w, [0.0, 0.0, 1.0] if abs(w[2]) < 0.9 else [1.0, 0.0, 0.0]); a /= np.linalg.norm(a)
    b = np.cross(w, a)
    g = np.linspace(-1, 1, n)
    X, Y = np.meshgrid(g, g)
    inside = X**2 + Y**2 < 1
    Z = np.sqrt(np.clip(1 - X**2 - Y**2, 0, 1))
    N = X[..., None] * a + Y[..., None] * b + Z[..., None] * w
    return ((N @ s_m > 0) & inside).sum() / inside.sum()

err = 0.0
for _ in range(60):
    s_m, view = unit(rng.uniform(-1.5, 1.5), rng.uniform(-3.1, 3.1)), unit(rng.uniform(-1.5, 1.5), rng.uniform(-3.1, 3.1))
    i = np.arccos(np.clip(s_m @ view, -1, 1))
    err = max(err, abs(lit_fraction(s_m, view) - (1 + np.cos(i)) / 2))
check("6  lit-sphere disc fraction vs (1+cos i)/2 (Meeus 48.1)", err, 1e-2)

# 7. topocentric parallax of a close toy moon: angle between geocentric and topocentric direction
#    max parallax = asin(R / d). Real Earth: R/d = 6378/384400 -> ~0.95 deg.
for name, ratio in (("real Earth-Moon", 6378.137 / 384400.0), ("toy, moon at 8 R", 1 / 8.0), ("toy, moon at 4 R", 1 / 4.0)):
    print("7  parallax %-18s max %.2f deg" % (name, np.degrees(np.arcsin(ratio))))

# 8. twilight band width on the ground: civil 0..-6, nautical ..-12, astro ..-18 deg of sun elevation
#    == the same arc of the planet surface along the sun meridian (great-circle distance R * angle).
for R in (6378.137e3, 5000.0, 20000.0):
    print("8  R=%-10g civil band %.0f m, night starts %.0f m past the terminator" % (R, R * 6 * D, R * 18 * D))

# 9. float32: position error of world coordinates at planet and sun distances (Blender stores float32)
for x in (5000.0, 20000.0, 1e5, 1e6):
    print("9  float32 ulp at %-9g m = %.4f m" % (x, np.spacing(np.float32(x))))

print("FAILED: " + ", ".join(fails) if fails else "all checks passed")


# ---------------------------------------------------------------- the scene's star system (decided Q1-Q14)
# World: planet centre C = (0, 0, -R), camera area at the mesh pole (0, 0, 0) on the EQUATOR of the spin
# axis A = +x (so the sun sets toward +y, like today). Sun = a direction s (at infinity); moon = a point on
# an orbit sphere |m - C| = a; stars = directions.
R = 16000.0
C = np.array([0.0, 0.0, -R])
A = np.array([1.0, 0.0, 0.0])
A_MOON, R_MOON = 50000.0, 11500.0          # Q12: closer, smaller moon
SUN_TRUE = 0.2667 * D                       # true-size sun angular radius, used only to cast the planet shadow
TILT = 40.0 * D                             # moon orbit tilt (derived below: 25 deg is not enough at 50 km)


def rot(axis, ang, v):
    """Rodrigues rotation of v about unit axis."""
    axis = axis / np.linalg.norm(axis)
    return v * np.cos(ang) + np.cross(axis, v) * np.sin(ang) + axis * (axis @ v) * (1 - np.cos(ang))


def night_to_height(n):
    """Q7: 0 -> +20, 0.5 -> 0, 1 -> -18 deg (linear in each half)."""
    return np.where(n < 0.5, (20.0 - 40.0 * n), (-36.0 * (n - 0.5))) * D


def sun_dir(theta):
    """The sun at spin angle theta: starts at the zenith of the pole point (+z), turns about A toward +y."""
    return rot(A, -theta, np.array([0.0, 0.0, 1.0]))


def solve_theta(h, cam):
    """Q4 + Q13: the spin angle that puts the sun at height h for the on-air camera, always on the west
    (+y-side, evening) branch, so a scrub in either direction is continuous."""
    up = (cam - C) / np.linalg.norm(cam - C)
    # elevation as a function of theta is sin h = up . sun_dir(theta) = a cos theta + b sin theta
    a_ = up @ np.array([0.0, 0.0, 1.0])
    b_ = up @ rot(A, -np.pi / 2, np.array([0.0, 0.0, 1.0]))      # sun_dir(theta) = z cos theta + sun_dir(90) sin theta
    r_ = np.hypot(a_, b_)
    phase = np.arctan2(b_, a_)
    return phase + np.arccos(np.clip(np.sin(h) / r_, -1, 1))    # the larger root: sun past the camera's noon, going down


# 10. solver: every camera of the area (within 9 km arc of the pole), every night value, lands the sun at the
#     requested height, on the evening branch (d height / d theta < 0), and is continuous in n.
err, bad_branch, max_jump = 0.0, 0, 0.0
for _ in range(300):
    ang, az = rng.uniform(0, 9000.0 / R), rng.uniform(0, 2 * np.pi)
    cam = C + R * np.array([np.sin(ang) * np.cos(az), np.sin(ang) * np.sin(az), np.cos(ang)]) + np.array([0, 0, rng.uniform(5, 150)])
    up = (cam - C) / np.linalg.norm(cam - C)
    prev = None
    for n in np.linspace(0, 1, 201):
        h = night_to_height(n)
        th = solve_theta(h, cam)
        got = np.arcsin(up @ sun_dir(th))
        err = max(err, abs(got - h))
        if (up @ sun_dir(th + 1e-4)) - (up @ sun_dir(th)) > 0:
            bad_branch += 1
        if prev is not None:
            max_jump = max(max_jump, abs(th - prev))
        prev = th
check("10a solver: sun height == night mapping, all area cameras", err / D, 1e-9)
check("10b solver: always the setting branch (no flips)", float(bad_branch), 0)
check("10c solver: spin angle continuous (max step per 1/200 of night) [deg]", max_jump / D, 1.0)

# 11. moon from phase: elongation E from the sun around the tilted orbit. E = 0 new, pi full.
#     The orbit is tilted by TILT about its line of nodes; the eclipse knob turns that line onto the sun line.
def moon_pos(s, E, node):
    """The moon at elongation E (0 new, pi full) on an orbit tilted by TILT to the sun's path plane.
    The tilt turns about the line of nodes. Knob node in [0, 1] turns that line from across the sun line
    (node 0: full and new moon pass TILT beside the shadow and the sun) onto it (node 1: eclipses)."""
    n0 = A.copy()                                             # the sun path plane (no seasons) is normal to the spin axis
    nodes = rot(n0, (1 - node) * np.pi / 2, s)               # line of nodes, in the sun path plane
    n_ = rot(nodes, TILT, n0)                                 # tilted orbit normal
    s_p = s - (s @ n_) * n_; s_p /= np.linalg.norm(s_p)       # the sun projected into the orbit plane
    w = rot(n_, E, s_p)
    return C + A_MOON * w


def in_shadow(p, s):
    """0 = full sun, 1 = umbra. Distance of p to the shadow axis, against umbra / penumbra radii at that depth."""
    q = p - C
    t = -(q @ s)
    if t <= 0:
        return 0.0
    d = np.linalg.norm(q + t * s)
    r_um, r_pen = R - t * np.tan(SUN_TRUE), R + t * np.tan(SUN_TRUE)
    return float(np.clip((r_pen - d) / (r_pen - r_um), 0, 1))


s0 = sun_dir(0.3)
# 11a full moon, knob 1: centre on the axis, whole disc inside the umbra (total eclipse)
m = moon_pos(s0, np.pi, 1.0)
rim = [m + R_MOON * rot(-s0, k, np.cross(s0, A) / np.linalg.norm(np.cross(s0, A))) for k in np.linspace(0, 2 * np.pi, 72)]
check("11a knob 1 at full: every moon rim point in umbra (1 - shadow)", max(1 - in_shadow(p, s0) for p in rim), 1e-9)
# 11b full moon, knob 0: no point of the moon in the penumbra
pts = [m2 + R_MOON * v for m2 in [moon_pos(s0, np.pi, 0.0)] for v in [unit(a, b) for a in np.linspace(-1.5, 1.5, 13) for b in np.linspace(-3.1, 3.1, 25)]]
check("11b knob 0 at full: no moon point shadowed", max(in_shadow(p, s0) for p in pts), 0.0)
# 11c minimum tilt for 11b: offset a sin(i) > penumbra radius + moon radius
need = np.degrees(np.arcsin((R + A_MOON * np.tan(SUN_TRUE) + R_MOON) / A_MOON))
print("11c min orbit tilt for no eclipse at knob 0: %.1f deg (25 deg is not enough; using %.0f)" % (need, TILT / D))
# 11d moon phase from vectors: lit fraction seen from the camera == (1 + cos i)/2, i from the real geometry,
#     and at E = pi (full) seen from the pole point i stays small (moon looks full) as long as it is above the horizon
cam0 = np.array([0.0, 0.0, 10.0])
for E_ in (0.0, np.pi / 2, np.pi):
    m_ = moon_pos(s0, E_, 0.0)
    i_ = np.arccos(np.clip(s0 @ ((cam0 - m_) / np.linalg.norm(cam0 - m_)), -1, 1))
    print("11d E=%3.0f deg: phase angle %5.1f deg, lit %.2f" % (np.degrees(E_), np.degrees(i_), (1 + np.cos(i_)) / 2))

# 12. solar eclipse is topocentric: with the moon ~35-47 km from the camera, geocentric alignment misses the
#     sun by the parallax. The aligned position for the on-air camera is where the camera->sun ray meets the
#     orbit sphere: |cam + t s - C| = a.
def ray_sphere(o, d, c, r):
    oc = o - c
    b = oc @ d
    disc = b * b - (oc @ oc - r * r)
    return -b + np.sqrt(disc)

err = err_a = 0.0
for _ in range(500):
    cam = C + (R + rng.uniform(5, 150)) * unit(rng.uniform(1.0, np.pi / 2), rng.uniform(0, 2 * np.pi))
    s_ = unit(rng.uniform(-0.2, 1.2), rng.uniform(0, 2 * np.pi))
    t = ray_sphere(cam, s_, C, A_MOON)
    p = cam + t * s_
    err = max(err, abs(np.linalg.norm(p - C) - A_MOON))
    v_ = (p - cam) / t
    err_a = max(err_a, np.degrees(np.arctan2(np.linalg.norm(np.cross(v_, s_)), v_ @ s_)))   # atan2: arccos loses precision near 0
check("12a topocentric solar alignment: on the orbit sphere [m]", err, 1e-4)
check("12b topocentric solar alignment: on the camera->sun line [deg]", err_a, 1e-6)
par = np.degrees(np.arcsin(R / A_MOON))
print("12c moon parallax at a = 50 km: up to %.1f deg; geocentric alignment would miss the sun by that much" % par)
for h_ in (90.0, 30.0, 0.0):
    hh = h_ * D
    dist = -R * np.sin(hh) + np.sqrt((R * np.sin(hh)) ** 2 + A_MOON ** 2 - R ** 2)
    print("12d moon at height %4.0f deg: %5.1f km away, angular radius %.1f deg" % (h_, dist / 1000, np.degrees(np.arctan(R_MOON / dist))))

# 13. star drift (Q14): stars turn by theta + beta about A, sun by theta. The sun height is untouched by beta,
#     and with no tilt (Q6) the drift never changes the sun's path.
err = 0.0
for _ in range(1000):
    th, beta = rng.uniform(0, 6.3), rng.uniform(0, 6.3)
    star = unit(rng.uniform(-1.5, 1.5), rng.uniform(0, 6.3))
    # sun height from the camera depends only on theta
    err = max(err, abs(sun_dir(th) @ np.array([0, 0, 1.0]) - rot(A, -th, np.array([0, 0, 1.0])) @ np.array([0, 0, 1.0])))
    # star seen = rot(A, -(th + beta)) star: drifting beta is a pure turn about the spin axis (stays on its circle)
    v1, v2 = rot(A, -th, star), rot(A, -(th + beta), star)
    err = max(err, abs(v1 @ A - v2 @ A))
check("13 star drift keeps each star on its circle about the axis", err, 1e-12)


# 14. the runtime module (blender/scenes/star_system.py) against the reference math above
import importlib.util
import os
_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "blender", "scenes", "star_system.py")
_spec = importlib.util.spec_from_file_location("star_system", _path)
ss = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ss)          # bpy and mathutils are only imported inside sync(), so this runs without Blender
assert np.allclose(ss.AXIS, A) and ss.MOON_ORBIT == A_MOON and abs(ss.MOON_TILT - TILT) < 1e-12

e_h = e_th = e_sun = e_moon = 0.0
for _ in range(400):
    ang, az = rng.uniform(0, 9000.0 / R), rng.uniform(0, 2 * np.pi)
    cam = C + R * np.array([np.sin(ang) * np.cos(az), np.sin(ang) * np.sin(az), np.cos(ang)]) + np.array([0, 0, rng.uniform(5, 150)])
    n, phase, ecl = rng.uniform(0, 1), rng.uniform(0, 1), rng.uniform(0, 1)
    r = ss.solve(tuple(C), R, tuple(cam), 0.0, n, phase, ecl, 0.0)
    up = (cam - C) / np.linalg.norm(cam - C)
    e_h = max(e_h, abs(r["h"] - night_to_height(n)))
    e_th = max(e_th, abs(r["theta"] - solve_theta(night_to_height(n), cam)))
    e_sun = max(e_sun, abs(np.arcsin(up @ np.array(r["sun"])) - night_to_height(n)))
    if ecl * max(np.cos(np.pi * phase), 0) ** 2 == 0:       # without the solar pull the module equals moon_pos
        e_moon = max(e_moon, np.linalg.norm(np.array(r["moon"]) - moon_pos(np.array(r["sun"]), np.pi * phase, ecl)))
check("14a module: Sun Height mapping == reference", e_h / D, 1e-12)
check("14b module: spin angle == reference solver", e_th / D, 1e-9)
check("14c module: sun lands at the Sun Height for the camera", e_sun / D, 1e-9)
check("14g module: moon on its tilted orbit == reference moon_pos [m]", e_moon, 1e-6)

# 14d-f the eclipse knob end to end through the module, parametrized over cameras and night values
cases = [(n, k) for n in (0.0, 0.25, 0.5, 0.75, 1.0) for k in range(8)]
e_full_dark = e_full_clear = e_new_line = 0.0
for n, k in cases:
    ang, az = 9000.0 / R * k / 8, 2 * np.pi * k / 8
    cam = C + R * np.array([np.sin(ang) * np.cos(az), np.sin(ang) * np.sin(az), np.cos(ang)]) + np.array([0, 0, 20.0])
    full = ss.solve(tuple(C), R, tuple(cam), 0.0, n, 1.0, 1.0, 0.0)
    s_ = np.array(full["sun"]); m_ = np.array(full["moon"])
    perp = np.cross(s_, A); perp /= np.linalg.norm(perp)
    rim_ = [m_ + R_MOON * rot(s_, a_, perp) for a_ in np.linspace(0, 2 * np.pi, 36)]
    e_full_dark = max(e_full_dark, max(1 - in_shadow(p, s_) for p in rim_ + [m_]))
    clear = ss.solve(tuple(C), R, tuple(cam), 0.0, n, 1.0, 0.0, 0.0)
    s_ = np.array(clear["sun"]); m_ = np.array(clear["moon"])
    e_full_clear = max(e_full_clear, max(in_shadow(m_ + R_MOON * v, s_) for v in [unit(a, b) for a in np.linspace(-1.5, 1.5, 7) for b in np.linspace(-3.1, 3.1, 13)]))
    new = ss.solve(tuple(C), R, tuple(cam), 0.0, n, 0.0, 1.0, 0.0)
    v_ = (np.array(new["moon"]) - cam); v_ /= np.linalg.norm(v_)
    e_new_line = max(e_new_line, np.degrees(np.arctan2(np.linalg.norm(np.cross(v_, new["sun"])), v_ @ np.array(new["sun"]))))
check("14d module: eclipse 1 at full -> whole moon in the umbra", e_full_dark, 1e-9)
check("14e module: eclipse 0 at full -> no moon point shadowed", e_full_clear, 0.0)
check("14f module: eclipse 1 at new -> moon on the camera->sun line [deg]", e_new_line, 1e-9)

# 14h the tracking aim: bodies above AIM_MIN are aimed at exactly; below it the aim keeps the body's azimuth
#     at AIM_MIN elevation and the same distance, parametrized over body heights and azimuths
e_above = e_below = 0.0
cam = np.array([0.0, 0.0, 30.0])
up = (cam - C) / np.linalg.norm(cam - C)
for el_deg in (-60.0, -18.0, -1.0, 0.0, 4.9, 5.0, 5.1, 30.0, 89.0):
    for az_deg in (0.0, 90.0, 200.0):
        e_, n_ = np.array([1.0, 0, 0]), np.array([0, 1.0, 0])
        d_ = np.cos(el_deg * D) * (np.cos(az_deg * D) * n_ + np.sin(az_deg * D) * e_) + np.sin(el_deg * D) * up
        body = cam + 40000.0 * d_
        aim = np.array(ss.aim_point(tuple(cam), tuple(up), tuple(body)))
        v = (aim - cam) / np.linalg.norm(aim - cam)
        if el_deg * D >= ss.AIM_MIN:
            e_above = max(e_above, np.linalg.norm(aim - body))
        else:
            flat_b = d_ - (d_ @ up) * up; flat_a = v - (v @ up) * up
            e_below = max(e_below, abs(np.arcsin(v @ up) - ss.AIM_MIN) / D,
                          np.degrees(np.arctan2(np.linalg.norm(np.cross(flat_a, flat_b)), flat_a @ flat_b)),
                          abs(np.linalg.norm(aim - cam) - 40000.0))
check("14h aim: body at or above 5 deg is aimed at exactly [m]", e_above, 1e-6)
check("14i aim: body below 5 deg -> same azimuth, 5 deg up, same distance", e_below, 1e-6)

# 14j-l the space blend: the sun's up turns from the camera's radial (rt_space 0, 2 km up) to POLE_UP (rt_space 1,
#     12 km up), parametrized over rt_space 0, 0.5 and 1, nights, and cameras near the pole, far out and nearly
#     opposite it. At 0 and 1 the module equals the old ground and orbit solutions; at every rt_space the sun sits at
#     the Sun Height over the blended up; and the sun direction is continuous across the band (no jump at 2 km)
pole = np.array(ss.POLE_UP)
e_ends = e_height = max_step = 0.0
for ang in (0.2, 1.0, 2.5, np.pi - 1e-4):
    dvec = np.array([np.sin(ang) * np.cos(0.7), np.sin(ang) * np.sin(0.7), np.cos(ang)])
    for n in (0.0, 0.25, 0.5, 0.75, 1.0):
        h = night_to_height(n)
        for space in (0.0, 0.5, 1.0):
            cam = C + dvec * (R + 2000.0 + 10000.0 * space)
            r = ss.solve(tuple(C), R, tuple(cam), space, n, 1.0, 0.0, 0.0)
            e_height = max(e_height, abs(np.arcsin(np.clip(np.array(r["up"]) @ np.array(r["sun"]), -1, 1)) - h))
            if space in (0.0, 1.0):
                up_old = pole if space > 0.0 else (cam - C) / np.linalg.norm(cam - C)
                s_old = np.array(ss.sun_dir(ss.solve_theta(h, tuple(up_old))))
                view_old = C + pole * R if space > 0.0 else cam
                m_old = np.array(ss.moon_centre(tuple(C), tuple(s_old), 1.0, 0.0, tuple(view_old))[0])
                e_ends = max(e_ends, np.degrees(np.linalg.norm(s_old - np.array(r["sun"]))),     # small-angle: no arccos noise
                             np.linalg.norm(m_old - np.array(r["moon"])) * 1e-3)
        steps = []
        for count in (441, 881):                                 # 25 m and 12.5 m steps across the band
            prev, worst = None, 0.0
            for alt in np.linspace(1500.0, 12500.0, count):
                cam = C + dvec * (R + alt)
                sun = np.array(ss.solve(tuple(C), R, tuple(cam), min(max((alt - 2000.0) / 10000.0, 0.0), 1.0), n, 1.0, 0.0, 0.0)["sun"])
                if prev is not None:
                    worst = max(worst, np.degrees(2.0 * np.arcsin(min(np.linalg.norm(prev - sun) / 2.0, 1.0))))
                prev = sun
            steps.append(worst)
        if steps[0] > 1e-9:                                      # a jump keeps its size at half the step; a smooth turn halves
            max_step = max(max_step, steps[1] / steps[0])
check("14j space blend: rt_space 0 and 1 == the old ground and orbit solutions [deg]", e_ends, 1e-9)
check("14k space blend: sun at the Sun Height over the blended up, rt_space 0/0.5/1", e_height / D, 1e-9)
check("14l space blend: continuous over 2-12 km (largest sun step at 12.5 m / at 25 m)", max_step, 0.55)

print("FAILED: " + ", ".join(fails) if fails else "all checks passed")
