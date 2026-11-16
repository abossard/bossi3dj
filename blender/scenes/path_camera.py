"""The Path Camera: one camera on paths, steered by /vj/path, /vj/target, /vj/height, /vj/cam_speed and /vj/blend.

Pure Python (no bpy), checked by blender/review/verify_paths.py (`make verify`). The design is in
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
import energy as en
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
BAND_CATCH = 3.0                    # e-folds/s at most while a held eye catches up with the blend outside the band
PLANET_HALF = math.radians(32.0)    # the planet target's half field near the ground
PUSH_PERIOD = 80.0                 # s at /vj/cam_speed 1: the vantage pushes in over half of it, out over the other
BLEND_LAND = 0.35                   # share of the frame's centre column a blend keeps on the planet (0: off). The planet is
#                                     small: the horizon dips 23 deg at 1.3 km, 52 at 10 km, and a blend's view stays near
#                                     the end shots' level while the hump lifts it (issue #25: flat sky, black space)
BLEND_LAND_MAX = 0.8                # and at most this share, so the horizon stays in frame (run 4: 95 % land, straight down)
BLEND_LAND_TURN = math.radians(25.0)   # rad/s the keep may add to the view's own turn (over the zenith, at a far blend's
#                                     end the kept view's heading or pitch can swing faster than that)
BLEND_TURN_MAX = math.radians(59.0)    # rad/s at /vj/blend DUR_MAX: a blend's view turns no faster with the keep (the
#                                     Director's pace scales with DUR_MAX / blend; verify_paths 2c)
BLEND_BY_HEIGHT = True              # a blend's fog and clip from its clearance (by_height); False: the Director's lerp
SKY_FRAME = True                    # (the user, 2026-11-16, issue #25: "On, incl. rise") sky targets on orbit, vantage and rise frame
#                                     the body on the upper third line and the horizon on the lower one (sky_frame)
SKY_FRAME_HALF = math.radians(40.0)  # widest vertical half field it opens to
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


def sky_frame(p, look):
    """A view (fwd, up, lens) of a sky body at look with land in frame: the horizon on the lower third line, the body
    on the upper one, the field opened to fit both (up to SKY_FRAME_HALF; wider gaps keep the horizon there and the
    body inside the top tenth). Without it a body high over the horizon filled the frame with sky and nothing in it
    moved (issue #25: vantage moon held still for 27 s)."""
    u = fl.norm(fl.sub(p, fl.CENTRE))
    to = fl.norm(fl.sub(look, p))
    el = math.asin(fl.clamp(fl.dot(to, u), -1.0, 1.0))
    dip = math.acos(fl.clamp(fl.R / max(fl.length(fl.sub(p, fl.CENTRE)), fl.R), -1.0, 1.0))
    hv = fl.clamp(1.5 * (el + dip), math.radians(12.0), SKY_FRAME_HALF)
    c = max(-dip + hv / 3.0, el - 0.8 * hv)
    head = fl.tangent(u, to)
    fwd = fl.add(fl.scale(head, math.cos(c)), u, math.sin(c))
    return fwd, fl.tangent(fwd, u), fl.clamp(fl.lens_for(hv), 14.0, 85.0)


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
        framed = SKY_FRAME and target.kind == "sky" and path in ("orbit", "vantage", "rise")
        if framed:
            fwd, up, lens = sky_frame(p, look)
        if path == "vantage" and not framed:      # framed: the push alone moves it (the zoom lost the body off the top)
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
        self.le = None                      # log of the eye's height over the sea, as last given out
        self.views = None                   # (the view before the keep, the view shown) last frame, for the turn limit

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
        changed = (path, target_name) != self.D.shot
        if changed:      # a change: how fast the new view turns by itself, for the blend's length
            later = pose(path, t, self.targets[HOME], self.phase + r * 0.5, h, self.terrain)
            turn = fl.angle(target_pose[1], later[1]) / 0.5
        out = self.D.step(dt, (path, target_name), target_pose, blend_s / dr.DUR_MAX, self.terrain, None, turn)
        if self.D.blending():
            out = self.floored(out)
        cut = changed and not self.D.blending()
        out = self.banded(out, dt, cut)
        base = out
        tr = self.D.tr
        if tr is not None:
            out = self.by_height(out) if BLEND_BY_HEIGHT else out
            out = self.on_land(out, fl.add(tr.a[1], target_pose[1]), min(tr.t, max(tr.d - tr.t, 0.0)))
        out = self.turn_limited(base, out, dt, cut, max(tr.d - tr.t, 0.0) if tr is not None else None, blend_s, changed)
        if tr is not None:
            self.D.pose = (self.D.pose[0],) + tuple(out[1:])     # a change mid-blend starts from the view shown
        return en.accent(out, drive) if drive is not None else out

    def turn_limited(self, base, out, dt, cut, left, blend_s, changed):
        """While blending (left: the blend's seconds to go), the shown view turns no faster than the view before the keep
        did this frame plus BLEND_LAND_TURN, plus what empties a lag by the blend's end, and never faster than
        BLEND_TURN_MAX at /vj/blend blend_s unless the view before the keep does. Outside blends, a cut and the first
        frame pass. On a change the Director starts from the view shown, so its own turn is measured from that."""
        prev, self.views = self.views, (base[1], out[1])
        if prev is None or cut or dt <= 0.0 or left is None or left <= dt:
            return out
        own = fl.angle(prev[1] if changed else prev[0], base[1])
        allowed = own + BLEND_LAND_TURN * dt + fl.angle(prev[1], prev[0]) * dt / left
        allowed = min(allowed, max(own, BLEND_TURN_MAX * dr.DUR_MAX / max(blend_s, 1e-3) * dt))
        d = fl.angle(prev[1], out[1])
        if d <= allowed:
            return out
        fwd = fl.slerp(prev[1], out[1], allowed / d)
        self.views = (base[1], fwd)
        return (out[0], fwd, fl.tangent(fwd, out[2])) + tuple(out[3:])

    def by_height(self, pose_):
        """A blend pose's fog and clip from its clearance, as a live pose has them (issue #25: the Director's lerp of
        the end shots' ground fog fogged the land out from kilometres up)."""
        u, hp = dr.spherical(pose_[0])
        clear = max(hp - self.terrain.surface(u), 0.0)
        props = dict(pose_[4])
        props.update(props_at(clear), clip=clip_at(clear))
        return tuple(pose_[:4]) + (props,)

    def on_land(self, pose_, ends, near_end):
        """The pose turned toward the kept view: pitched so BLEND_LAND to BLEND_LAND_MAX of the frame's centre column see
        the planet at this eye's dip, its heading the view's own steadied by the end shots' (ends: the sum of their
        forwards; a view over the zenith flipped its heading in under a second), the roll carried over. The turn toward
        it is at most BLEND_LAND_TURN x near_end (the blend's seconds from its nearer end): none at either end."""
        p, fwd, up = pose_[0], pose_[1], pose_[2]
        u, hp = dr.spherical(p)
        if near_end <= 0.0 or BLEND_LAND <= 0.0:
            return pose_
        pitch = math.asin(fl.clamp(fl.dot(fwd, u), -1.0, 1.0))
        dip = math.acos(fl.clamp(fl.R / (fl.R + max(hp, 0.0)), -1.0, 1.0))
        hv = math.atan(fl.SENSOR / 2.0 / fl.ASPECT / pose_[3])
        pf = fl.clamp(pitch, -dip - hv * (1.0 - 2.0 * (1.0 - BLEND_LAND_MAX)), -dip + hv * (1.0 - 2.0 * BLEND_LAND))
        head = fl.tangent(u, fl.add(fwd, ends, 0.25))
        kept = fl.add(fl.scale(head, math.cos(pf)), u, math.sin(pf))
        gap = fl.angle(fwd, kept)
        if gap < 1e-6:
            return pose_
        new = fl.slerp(fwd, kept, min(1.0, BLEND_LAND_TURN * near_end / gap))
        level = fl.tangent(fwd, u)
        roll = math.atan2(fl.dot(fl.cross(level, up), fwd), fl.dot(level, up))
        return (p, new, fl.rot(new, roll, fl.tangent(new, u))) + tuple(pose_[3:])

    def banded(self, pose_, dt, cut=False):
        """A blend crosses the hand-over band at BAND_RATE at most, like the rise: a fall from space took it in 3 to 4
        frames, and the far skin's trade of the pixels changed the whole frame at once (round 16: 45 of 255 in a
        frame at 11 km). Outside the band the held eye catches up at BAND_CATCH; a cut and the live shots pass."""
        u, hp = dr.spherical(pose_[0])
        want = math.log(max(hp, 1.0))
        if self.le is None or not self.D.blending() and abs(want - self.le) < 1e-3 or cut:
            self.le = want
            return pose_
        lo, hi = math.log(BAND[0] * 0.85), math.log(BAND[1] * 1.15)
        cap = (BAND_RATE if lo <= self.le <= hi else BAND_CATCH) * dt
        self.le += fl.clamp(want - self.le, -cap, cap)
        if abs(want - self.le) < 1e-3:
            return pose_
        return (fl.add(fl.CENTRE, u, fl.R + math.exp(self.le)),) + tuple(pose_[1:])

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
