"""The Path Camera: one camera on paths, steered by /vj/path, /vj/target, /vj/height, /vj/cam_speed and /vj/blend.

Pure Python (no bpy), checked by docs/research/path-camera/verify_paths.py (`make verify`). The design is in
docs/handover/path-camera.md.

- A path type (orbit, follow the land, rise and descend, vantage with a slow push) works with any target. A target
  is a look point and a home on the ground: a ground target (pyramids, lake, river, coast) is both; the moon and the
  sun are looked at from the pyramids' home; the planet is looked at as land ahead near the ground and as the whole
  sphere from space.
- The live pose is a function of the path, the target, the phase and the height: pose(). The phase is the one
  integrated number (radians along the path, advanced at the ground flow the speed asks for); the height glides in
  log space at H_RATE e-folds a second at most.
- A change of path or target is a Director blend from the current pose to the new live pose (director.py: rise,
  traverse, descend, quintic ease, carried velocity). /vj/blend is the time the longest change takes; 0 cuts.
- Never under ground: the camera stays H_MIN over the highest ground from WINDOW[0] behind to WINDOW[1] ahead on
  live paths, and over the ground under it in blends.
- The ground never flows past faster than FLOW_MAX (speed over clearance + H0), so the terrain stream keeps up.

A terrain gives surface(u): metres over R of land or water at the unit direction u from the centre.
"""
import math

import director as dr
import flight as fl

H_MIN, H_MAX = 10.0, 64000.0        # m over the ground at /vj/height 0 and 1, log scale between
H_RATE = 0.5                        # e-folds/s: how fast the height glides to a new fader value
WINDOW = (20.0, 80.0)               # m behind and ahead whose highest ground the camera keeps H_MIN over
WINDOW_N = 6
FLOW = 0.25                         # rad/s of ground flow (speed over clearance + H0) at /vj/cam_speed 1
FLOW_MAX = 0.9                      # rad/s the speed control can ask for at most
BAND = (8000.0, 12000.0)            # m eye height where the Planet's far skin takes the pixels over (GLOBE_BAND)
CLIP = (0.5, 400.0, 0.05)           # near clip: at least, at most, share of the clearance
CLIP_FAR = 600000.0
SKY_MIN = math.radians(4.0)         # a body is looked at no lower than this over the horizon (else the view hits ground)
TURN = math.radians(6.0)            # rad/s: orbit and follow turn round their home no faster at /vj/cam_speed 1
RISE_SHARE = 0.8                    # rise and descend: the climb's share of the flow (the sway takes the rest)
BAND_RATE = 0.3                     # e-folds/s at most through the hand-over band: a crossing takes over 1 s
PLANET_HALF = math.radians(32.0)    # the planet target's half field near the ground
PUSH_PERIOD = 80.0                 # s at /vj/cam_speed 1: the vantage pushes in over half of it, out over the other
RISE_DEPTH = 0.75                   # rise and descend: the share of the log height span it travels down from the top
PATHS = ("orbit", "follow", "rise", "vantage")
TARGETS = ("pyramids", "lake", "river", "coast", "moon", "sun", "planet")
HOME = "pyramids"                   # the ground the moon, the sun and the planet are seen from
FOG = ((10.0, 1.5, 150.0), (60.0, 2.0, 250.0), (3000.0, 1.0, 600.0), (64000.0, 1.0, 180.0))   # m, fog_k, fog_clear


def height(w):
    """Metres over the ground at fader value w (0..1)."""
    return H_MIN * (H_MAX / H_MIN) ** fl.clamp(w, 0.0, 1.0)


def fader(h):
    return fl.clamp(math.log(max(h, H_MIN) / H_MIN) / math.log(H_MAX / H_MIN), 0.0, 1.0)


def band_weight(eye):
    """How much the far skin has taken over at this eye height (0 below the band, 1 above)."""
    return fl.smootherstep((eye - BAND[0]) / (BAND[1] - BAND[0]))


class Target:
    """kind: "ground" (point on the surface), "sky" (a body: point and radius) or "planet". size: m to frame."""

    def __init__(self, name, kind, point, size):
        self.name, self.kind, self.point, self.size = name, kind, point, size

    def ground_dir(self):
        return fl.norm(fl.sub(self.point, fl.CENTRE))


def ground_target(name, u, terrain, size, lift=0.0):
    return Target(name, "ground", fl.add(fl.CENTRE, u, fl.R + terrain.surface(u) + lift), size)


def interp_log(h, keys, col):
    h = fl.clamp(h, keys[0][0], keys[-1][0])
    for (h0, *a), (h1, *b) in zip(keys, keys[1:]):
        if h <= h1:
            e = math.log(h / h0) / math.log(h1 / h0)
            return a[col] + (b[col] - a[col]) * e
    return keys[-1][1 + col]


def props_at(h):
    return {"fog_k": interp_log(h, FOG, 0), "fog_clear": interp_log(h, FOG, 1),
            "fog_dip": math.sqrt(2.0 * max(h, 5.0) / fl.R)}


def clip_at(h):
    return fl.clamp(CLIP[2] * h, CLIP[0], CLIP[1])


def lift(terrain, u, heading, h):
    """Radius of a camera h over the highest ground from WINDOW[0] behind to WINDOW[1] ahead along heading."""
    top = terrain.surface(u)
    if heading is not None:
        for i in range(WINDOW_N + 1):
            d = -WINDOW[0] + (WINDOW[0] + WINDOW[1]) * i / WINDOW_N
            top = max(top, terrain.surface(fl.at_distance(u, heading, d)))
    return fl.R + top + h


def look_frame(p, look, lens, roll_up=None):
    fwd = fl.norm(fl.sub(look, p))
    radial = fl.norm(fl.sub(p, fl.CENTRE))
    up = fl.tangent(fwd, fl.add(radial, roll_up or radial, 0.05))
    return fwd, up, lens


def lens_to_fit(p, look, size, least=0.12):
    """Lens that shows size (m) around look with margin, never a narrower half field than least (rad)."""
    d = max(fl.length(fl.sub(look, p)), 1.0)
    half = max(math.atan2(1.6 * size, d), least)
    return fl.clamp(fl.lens_for(min(half, math.radians(40.0))), 14.0, 85.0)


def reach(h, size):
    """Ground distance (m) the camera keeps from its home at clearance h: a stand-off that grows with height, at
    most 0.7 rad round the Planet."""
    return min(max(2.5 * h, 4.0 * size, 120.0), 0.7 * fl.R)


def home_frame(home):
    u = home.ground_dir()
    e, n = fl.local_frame(u)
    return u, e, n


def look_point(target, p, travel):
    """Where the camera looks for a target from p. The planet: land ahead near the ground, the whole sphere from
    space (blend from 2 to 20 km)."""
    if target.kind == "ground":
        return target.point
    if target.kind == "sky":        # a body under the horizon: look at the horizon toward it
        radial = fl.norm(fl.sub(p, fl.CENTRE))
        d = fl.norm(fl.sub(target.point, p))
        r = fl.length(fl.sub(p, fl.CENTRE))
        least = -math.acos(min(fl.R / r, 1.0)) + SKY_MIN
        el = math.asin(fl.clamp(fl.dot(d, radial), -1.0, 1.0))
        if el >= least:
            return target.point
        level = fl.tangent(radial, d)
        return fl.add(p, fl.add(fl.scale(level, math.cos(least)), radial, math.sin(least)), 1000.0)
    u = fl.norm(fl.sub(p, fl.CENTRE))
    clear = fl.length(fl.sub(p, fl.CENTRE)) - fl.R
    ahead = fl.add(fl.CENTRE, fl.at_distance(u, travel, max(6.0 * clear, 300.0)), fl.R)
    w = fl.smootherstep(math.log(max(clear, 1.0) / 2000.0) / math.log(10.0))
    return fl.add(fl.scale(ahead, 1.0 - w), fl.CENTRE, w)


def planet_lens(p):
    """A wide view of the land near the ground, the whole sphere with margin from space (blend from 2 to 20 km)."""
    r = fl.length(fl.sub(p, fl.CENTRE))
    w = fl.smootherstep(math.log(max(r - fl.R, 1.0) / 2000.0) / math.log(10.0))
    half = PLANET_HALF * (1.0 - w) + 1.15 * math.asin(min(fl.R / r, 1.0)) * w
    return fl.clamp(fl.lens_for(min(half, math.radians(40.0))), 14.0, 85.0)


def pose(path, target, home, phase, h, terrain):
    """The live pose (p, fwd, up, lens, props) of a path for a target at phase (rad) and clearance h (m).
    home: the Target ground paths of sky and planet targets centre on."""
    centre = target if target.kind == "ground" else home
    u0, e, n = home_frame(centre)
    size = target.size if target.kind == "ground" else home.size
    if path == "orbit" or path == "follow":
        rho = reach(h, size) * (1.0 if path == "orbit" else 1.6)
        sign = 1.0 if path == "orbit" else -1.0
        az = sign * phase
        radial_dir = fl.norm(fl.add(fl.scale(e, math.cos(az)), n, math.sin(az)))
        u = fl.at_distance(u0, radial_dir, rho)
        travel = fl.tangent(u, fl.norm(fl.add(fl.scale(e, -math.sin(az) * sign), n, math.cos(az) * sign)))
    elif path == "rise":
        rho = reach(H_MIN, size) + 0.3 * reach(h, size)
        az = min(0.15, 2.0 * (h + dr.H0) / rho) * math.sin(0.25 * phase)     # a sway at half the flow at most
        radial_dir = fl.norm(fl.add(fl.scale(e, math.cos(az + 0.6)), n, math.sin(az + 0.6)))
        u = fl.at_distance(u0, radial_dir, rho)
        travel = fl.tangent(u, fl.sub(u0, u))
        h = rise_height(h, phase)
    else:   # vantage: stands off, pushes in slowly and back, no faster than the ground flow allows
        push = fl.smootherstep(0.5 * (1.0 - math.cos(phase)))
        rho = 1.4 * reach(h, size) - push_depth(h, size) * push
        radial_dir = fl.norm(fl.add(fl.scale(e, math.cos(-2.2)), n, math.sin(-2.2)))
        u = fl.at_distance(u0, radial_dir, rho)
        travel = fl.tangent(u, fl.sub(u0, u))
    p = fl.add(fl.CENTRE, u, lift(terrain, u, travel, h))
    clear = fl.length(fl.sub(p, fl.CENTRE)) - fl.R - terrain.surface(u)
    if path == "follow":
        down = math.atan2(min(clear, 3000.0), 8.0 * clear + 200.0)      # looks ahead, down toward the land
        ahead = fl.norm(fl.add(travel, u, -math.tan(down)))
        look = look_point(target, p, travel)
        to_t = fl.norm(fl.sub(look, p))
        fwd = fl.slerp(ahead, to_t, 0.25 if target.kind != "planet" else 0.0)
        lens = 24.0
        up = fl.tangent(fwd, fl.add(u, u, 0.05))
    else:
        look = look_point(target, p, travel)
        fwd, up, _ = look_frame(p, look, 0.0)
        lens = planet_lens(p) if target.kind == "planet" else lens_to_fit(p, look, target.size)
        if path == "vantage":
            lens *= 1.0 + 0.35 * fl.smootherstep(0.5 * (1.0 - math.cos(phase)))
    props = props_at(clear)
    props["clip"] = clip_at(clear)
    return p, fwd, up, lens, props


def push_depth(h, size):
    """How far (m) the vantage pushes in: half its stand-off, at most what keeps the push at FLOW at the default speed
    (smootherstep's top slope 1.875 on a half-cosine)."""
    return min(0.5 * reach(h, size), FLOW * (h + dr.H0) * PUSH_PERIOD / (1.875 * math.pi))


def rise_span(h):
    return (math.log(h + dr.H0) - math.log(H_MIN + dr.H0)) * RISE_DEPTH


def rise_height(h, phase):
    """Rise and descend: from the fader's height h down by rise_span and back, a half cosine in log height."""
    return math.exp(math.log(h + dr.H0) - rise_span(h) * 0.5 * (1.0 - math.cos(phase))) - dr.H0


def rate(path, h, size, speed, phase=0.0):
    """Phase rate (rad/s) at clearance h for /vj/cam_speed in scene units (1 = default): the camera moves at
    flow * (clearance + H0), flow = FLOW * speed, at most FLOW_MAX."""
    flow = min(FLOW * max(speed, 0.0), FLOW_MAX)
    if path in ("orbit", "follow"):
        rho = reach(h, size) * (1.0 if path == "orbit" else 1.6)
        own = flow * (h + dr.H0) / ((fl.R + h) * math.sin(rho / fl.R))     # the camera's own circle, not the ground's
        return min(own, TURN * flow / FLOW)
    if path == "rise":      # log height changes at RISE_SHARE of the flow, slower through the hand-over band
        lograte = RISE_SHARE * flow
        if BAND[0] * 0.85 < rise_height(h, phase) < BAND[1] * 1.15:
            lograte = min(lograte, BAND_RATE)
        return min(lograte / max(0.5 * rise_span(h), 1e-6), flow)
    return 2.0 * math.pi / PUSH_PERIOD * flow / FLOW


class PathCamera:
    """The On-Air rig of the Planet: holds phase and height, blends changes through a Director."""

    def __init__(self, targets, terrain):
        self.targets = targets              # name -> Target
        self.terrain = terrain
        self.phase = 0.0
        self.lh = None                      # log of the gliding height
        self.D = dr.Director()
        self.key = None

    def target(self, name):
        return self.targets.get(name) or self.targets[HOME]

    def live(self, path, target_name, h):
        return pose(path, self.target(target_name), self.targets[HOME], self.phase, h, self.terrain)

    def step(self, dt, path, target_name, w, speed=1.0, blend_s=30.0, drive=None):
        """dt s; path and target names; w the /vj/height fader; speed /vj/cam_speed in scene units; blend_s the time
        the longest change takes (0 cuts). Returns the rig's pose."""
        want = math.log(height(w))
        if self.lh is None:
            self.lh = want
        else:
            self.lh += fl.clamp(want - self.lh, -H_RATE * dt, H_RATE * dt)
        h = math.exp(self.lh)
        t = self.target(target_name)
        size = t.size if t.kind == "ground" else self.targets[HOME].size
        r = rate(path, h, size, speed, self.phase)
        self.phase += r * dt
        target_pose = self.live(path, target_name, h)
        turn = 0.0
        if (path, target_name) != self.D.shot:      # a change: how fast the new view turns by itself, for the blend's length
            later = pose(path, t, self.targets[HOME], self.phase + r * 0.5, h, self.terrain)
            turn = fl.angle(target_pose[1], later[1]) / 0.5
        out = self.D.step(dt, (path, target_name), target_pose, blend_s / dr.DUR_MAX, self.terrain, drive, turn)
        if self.D.blending():
            out = self.floored(out)
        return out

    def floored(self, pose_):
        """A blend pose kept H_MIN over the ground under it."""
        p = pose_[0]
        u, hp = dr.spherical(p)
        floor = self.terrain.surface(u) + H_MIN
        if hp >= floor:
            return pose_
        return (fl.add(fl.CENTRE, u, fl.R + floor),) + tuple(pose_[1:])

    def blending(self):
        return self.D.blending()
