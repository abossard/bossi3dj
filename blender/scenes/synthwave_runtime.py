"""Runtime for synthwave_pyramids.blend.

Stored in the .blend as an external, registered text block, so it runs on
file load when Blender allows Auto Run Python Scripts. It then:

- sets defaults for the /vj/* scene properties the scene reads (see README);
- integrates clocks on every frame change, so speed controls never jump:
  rt_time, rt_grid_phase (vj_grid_speed), rt_cam_phase (vj_cam_speed),
  rt_fog_phase (vj_fog_speed, wind in m/s);
- writes rt_beat = max(vj_beat, idle pulse). The idle pulse fades in after
  IDLE_AFTER seconds without any /vj/* change, so the scene keeps moving
  when no OSC arrives;
- runs the shockwave, the shooting-star slots (rt_met<i>_*) and the flamingo
  flight clock rt_flock (counts up from twilight on, back down in daylight);
- keeps CAM_OUT on the active camera (transform via its Copy Transforms
  constraint, lens copied), so one Syphon sender follows every /vj/cam cut;
- starts the OSC bridge (blender_osc_bridge.py text block), playback,
  the zero-copy Syphon sender syphon_out.py (server CAM_OUT) and the web
  control page synthwave_web.py (http://127.0.0.1:9210). The page builds
  its controls from RANGES and TRIGGERS, stored on the props as UI data.

The feature check (synthwave_check.py, started from the page) drives the clocks through
driver_namespace["vj_runtime"]: freeze() stops them, advance(s) steps them a fixed
STEP at a time, quiesce() drops the events in flight. A freeze that is not renewed
within FREEZE_LAPSE seconds lapses by itself. Nothing here costs anything while no check runs.
"""
import math
import random
import re
import time
import types

import bpy

DEFAULTS = {
    "vj_level": 0.5, "vj_bass": 0.0, "vj_beat": 0.0,
    "vj_hue": 0.0, "vj_intensity": 1.0, "vj_strobe": 0.0,
    "vj_grid_speed": 0.6, "vj_cam": 0.0, "vj_cam_speed": 1.0,
    "vj_sun": 1.0, "vj_moon": 1.0, "vj_pyramids": 1.0,
    "vj_grid": 1.0, "vj_stars": 1.0, "vj_water": 1.0,
    "vj_night": 0.0, "vj_shock": 0.0,
    "vj_fog": 0.35, "vj_fog_height": 25.0, "vj_fog_glow": 0.6, "vj_fog_hue": 0.0,
    "vj_fog_noise": 0.6, "vj_fog_scale": 260.0, "vj_fog_speed": 10.0, "vj_fog_beat": 0.5,
    "vj_nebula": 1.0, "vj_meteor": 0.0, "vj_flamingos": 1.0, "vj_haze": 1.0, "vj_moon_phase": 1.0,
    "vj_eclipse": 0.0, "vj_star_speed": 0.0, "vj_flight": 0.0, "vj_boost": 0.0, "vj_blend": 1.0,
    "vj_energy": 0.3, "vj_hit": 0.0,
}
# (min, max, step) where it is not 0..1; stored on the props as UI data, so the web page and Blender's own UI share them.
# vj_cam stops at the scene's last camera (ensure_props), 10 being the planet's.
RANGES = {
    "vj_intensity": (0.0, 2.0, 0.01), "vj_grid_speed": (0.0, 4.0, 0.01), "vj_cam": (0.0, 10.0, 1.0),
    "vj_cam_speed": (0.0, 4.0, 0.01), "vj_shock": (0.0, 1.5, 0.01), "vj_fog_height": (1.0, 60.0, 1.0),
    "vj_fog_glow": (0.0, 2.0, 0.01), "vj_fog_scale": (10.0, 1000.0, 1.0), "vj_fog_speed": (0.0, 40.0, 0.1),
    "vj_star_speed": (0.0, 10.0, 0.1), "vj_blend": (0.0, 2.0, 0.01),
}
TRIGGERS = ("vj_shock", "vj_meteor", "vj_hit")   # rising edge above 0.5 fires; the page shows them as buttons
WEB_FILE = "//synthwave_web.py"
STAR_SYSTEM_FILE = "//star_system.py"   # one sun, moon and star sky for every camera (planet scenes only)
DAY_WORLD_FILE = "//day_world.py"   # swaps in a world without the night layers while they have no weight
PYRAMIDS = "Pyramids"   # collection whose objects ride the shockwaves
METEORS = 3
METEOR_FIELDS = ("ax", "ay", "az", "bx", "by", "bz", "s", "l", "a")
SHOCKS = 4            # shock waves that can run at once, so one per heavy kick overlaps
CLOCKS = ("rt_time", "rt_grid_phase", "rt_cam_phase", "rt_fog_phase", "rt_beat",
          *("rt_shock%d_%s" % (i, f) for i in range(SHOCKS) for f in "xyra"), "rt_shake", "rt_flock", "rt_flock_dir",
          *("rt_met%d_%s" % (i, f) for i in range(METEORS) for f in METEOR_FIELDS))
SHOCK_SPEED = 300.0   # m/s, a rolling ground wave
SHOCK_LIFE = 12.0     # s until the wave has died out (about 3.6 km out)
SHOCK_IDLE_EVERY = 16.0  # s between automatic shockwaves while idle
SHOCK_LAMBDA, SHOCK_LAND, SHOCK_FALLOFF = 170.0, 16.0, 2400.0   # m; the same wave the shaders draw
PYR_LIFT, PYR_TILT = 0.6, 0.3   # pyramids are heavy: they ride the wave damped
METEOR_IDLE = (60.0, 180.0)   # s between the rare automatic shooting stars at night while idle
FLOCK_LEAVE = 0.18    # vj_night above this (sunset): the flamingos take off
FLOCK_RETURN = 0.08   # below this they fly back and land
FLOCK_END = 30.0      # s of flight after which every bird has faded out
IDLE_AFTER = 2.0      # seconds without /vj/* changes before the idle pulse fades in
IDLE_BPM = 124.0
IDLE_DEPTH = 0.45     # idle pulse peak, 0..1
BRIDGE_FILE = "//../blender_osc_bridge.py"
CAMERA_NAME = re.compile(r"^CAM_(\d+)$")
OUTPUT_CAMERA = "CAM_OUT"
STEP = 0.1            # s of clock time per frame while a check steps the clocks (the cap on a frame's dt)
FREEZE_LAPSE = 4.0    # s after which a freeze that nobody renews ends by itself
RUNTIME_KEY = "vj_runtime"

_state = {"last": None, "changed": -1e9, "snapshot": None, "idle": 1.0,
          "shock_prev": 0.0, "shock_src": -1, "shock_idle": 0.0, "shock_slot": 0, "shocks": [None] * SHOCKS,
          "meteor_prev": 0.0, "meteor_wait": METEOR_IDLE[0], "meteor_slot": 0, "meteors": [None] * METEORS}
_clock = {"frozen": False, "steps": 0, "deadline": 0.0}


def freeze(on=True):
    """Stops the clocks (dt 0) until advance() steps them; renew every FREEZE_LAPSE s or it lapses."""
    _clock["frozen"] = bool(on)
    _clock["deadline"] = time.perf_counter() + FREEZE_LAPSE
    if not on:
        _clock["steps"] = 0


def advance(seconds):
    """While frozen: the next frames each run one STEP of clock time, `seconds` in all, whatever the frame rate."""
    _clock["steps"] += max(int(round(seconds / STEP)), 0)


def steps_left():
    return _clock["steps"]


def quiesce():
    """Drops what a past trigger left running (shock waves, shooting stars), the idle pulse and the star drift."""
    _state.update(idle=0.0, changed=time.perf_counter(), shock_prev=0.0, shock_src=-1, shock_idle=0.0, shock_slot=0,
                  shocks=[None] * SHOCKS, meteor_prev=0.0, meteor_wait=METEOR_IDLE[0], meteor_slot=0,
                  meteors=[None] * METEORS)
    if _state.get("star_system"):
        _state["star_system"]._state["beta"] = 0.0
    random.seed(1)     # the same shooting star every time


def clock_dt(now, dt):
    c = _clock
    if not c["frozen"]:
        return dt
    if now > c["deadline"]:
        c["frozen"] = False
        return dt
    if c["steps"] > 0:
        c["steps"] -= 1
        return STEP
    return 0.0


def camera_count(scene):
    return sum(1 for o in scene.objects if o.type == "CAMERA" and CAMERA_NAME.match(o.name))


def ensure_props(scene):
    for k, v in DEFAULTS.items():
        if k not in scene:
            scene[k] = v
        lo, hi, step = RANGES.get(k, (0.0, 1.0, 0.01))
        if k == "vj_cam":
            hi = max(camera_count(scene) - 1, 0)
        scene.id_properties_ui(k).update(min=lo, max=hi, soft_min=lo, soft_max=hi, step=step * 100.0, default=v,
                                         description="trigger" if k in TRIGGERS else "")
    for k in CLOCKS:
        if k not in scene:
            scene[k] = 0.0


def synthwave_tick(scene, depsgraph=None):
    now = time.perf_counter()
    dt = 0.0 if _state["last"] is None else min(max(now - _state["last"], 0.0), 0.1)
    _state["last"] = now
    dt = clock_dt(now, dt)

    snapshot = tuple(scene.get(k, 0.0) for k in DEFAULTS)
    if snapshot != _state["snapshot"]:
        _state["snapshot"] = snapshot
        _state["changed"] = now
    target = _state["idle"] if _clock["frozen"] else 1.0 if now - _state["changed"] > IDLE_AFTER else 0.0
    _state["idle"] += (target - _state["idle"]) * min(dt * 1.5, 1.0)

    t = scene.get("rt_time", 0.0) + dt
    scene["rt_time"] = t
    scene["rt_grid_phase"] = scene.get("rt_grid_phase", 0.0) + dt * scene.get("vj_grid_speed", 0.6)
    scene["rt_cam_phase"] = scene.get("rt_cam_phase", 0.0) + dt * scene.get("vj_cam_speed", 1.0)
    scene["rt_fog_phase"] = scene.get("rt_fog_phase", 0.0) + dt * scene.get("vj_fog_speed", 10.0)
    phase = (t * IDLE_BPM / 60.0) % 1.0
    idle_pulse = math.exp(-5.0 * phase) * IDLE_DEPTH * _state["idle"]
    scene["rt_beat"] = max(scene.get("vj_beat", 0.0), idle_pulse)
    shockwave(scene, t, dt)
    meteors(scene, t, dt)
    flock(scene, dt)
    if _state.get("star_system"):
        _state["star_system"].sync(scene, dt)
    sync_output(scene)
    if _state.get("day_world"):
        _state["day_world"].sync(scene)
    scene.update_tag()   # custom-property writes alone do not re-run drivers


def shockwave(scene, t, dt):
    """A rising edge of /vj/shock (or the idle timer) fires a rolling ground wave from the
    next pyramid into the next of SHOCKS slots, so waves from fast triggers overlap. A
    trigger value above 1 makes a stronger wave (up to 1.5). Shaders read rt_shock<i>_x/y
    (source), _r (front radius), _a (strength). Pyramids ride the waves here (delta
    transforms) and rt_shake shakes land and cameras while a front passes the camera."""
    v = scene.get("vj_shock", 0.0)
    fire = v >= 0.5 > _state["shock_prev"]
    _state["shock_prev"] = v
    _state["shock_idle"] = _state["shock_idle"] + dt if _state["idle"] > 0.9 else 0.0
    if _state["shock_idle"] >= SHOCK_IDLE_EVERY:
        _state["shock_idle"] = 0.0
        fire, v = True, 1.0
    coll = bpy.data.collections.get(PYRAMIDS)   # by collection, not name: a helper named Pyramid_* moved per frame re-runs its geometry nodes
    pyramids = sorted(coll.objects, key=lambda o: o.name) if coll else []
    if fire and pyramids:
        _state["shock_src"] = (_state["shock_src"] + 1) % len(pyramids)
        src = pyramids[_state["shock_src"]].location
        _state["shocks"][_state["shock_slot"]] = (t, src.x, src.y, min(max(v, 0.5), 1.5))
        _state["shock_slot"] = (_state["shock_slot"] + 1) % SHOCKS
    waves = []
    for i, sh in enumerate(_state["shocks"]):
        age = t - sh[0] if sh else SHOCK_LIFE
        a = max(0.0, 1.0 - age / SHOCK_LIFE) * sh[3] if sh and age >= 0.0 else 0.0
        r = age * SHOCK_SPEED if a > 0.0 else 0.0
        x, y = (sh[1], sh[2]) if sh else (0.0, 0.0)
        scene["rt_shock%d_x" % i], scene["rt_shock%d_y" % i] = x, y
        scene["rt_shock%d_r" % i], scene["rt_shock%d_a" % i] = r, a
        if a > 0.0:
            waves.append((x, y, r, a))
    shake = 0.0
    if scene.camera is not None:
        c = scene.camera.matrix_world.translation
        for x, y, r, a in waves:
            d = math.hypot(c.x - x, c.y - y)
            shake = max(shake, a * math.exp(-abs(d - r) / 260.0))
    scene["rt_shake"] = min(shake, 1.5)
    k = 2.0 * math.pi / SHOCK_LAMBDA
    for o in pyramids:
        p, lift, tx, ty = o.location, 0.0, 0.0, 0.0
        for x, y, r, a in waves:
            dx, dy = p.x - x, p.y - y
            d = math.hypot(dx, dy)
            q = (d - r + 0.6 * SHOCK_LAMBDA) / (0.9 * SHOCK_LAMBDA)
            env = a * math.exp(-q * q) / (1.0 + d / SHOCK_FALLOFF)
            lift += env * math.sin(k * (d - r))
            slope = SHOCK_LAND * k * PYR_TILT * env * math.cos(k * (d - r)) / max(d, 1.0)
            tx, ty = tx + slope * dy, ty - slope * dx
        o.delta_location.z = SHOCK_LAND * PYR_LIFT * math.tanh(lift) + scene["rt_shake"] * 0.9 * math.sin(t * 47.0)
        o.delta_rotation_euler.x, o.delta_rotation_euler.y = tx, ty


def meteors(scene, t, dt):
    """A rising edge of /vj/meteor (or a random timer at night while idle) launches a
    shooting star into the next slot: start direction A, motion direction B along the
    sky, head angle s, trail length l and brightness a, read by the VJ_Meteor shader."""
    v = scene.get("vj_meteor", 0.0)
    fire = v >= 0.5 > _state["meteor_prev"]
    _state["meteor_prev"] = v
    if _state["idle"] > 0.9 and scene.get("vj_night", 0.0) > 0.6:
        _state["meteor_wait"] -= dt
        if _state["meteor_wait"] <= 0.0:
            _state["meteor_wait"] = random.uniform(*METEOR_IDLE)
            fire = True
    if fire:
        az, el = random.gauss(0.0, math.radians(60.0)), math.radians(random.uniform(14.0, 50.0))
        a = (math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el))
        e = _norm((-a[1], a[0], 0.0))                        # east along the sky
        u = (a[1] * e[2] - a[2] * e[1], a[2] * e[0] - a[0] * e[2], a[0] * e[1] - a[1] * e[0])   # up along the sky
        side, beta = random.choice((-1.0, 1.0)), math.radians(random.uniform(20.0, 60.0))
        b = _norm(tuple(side * math.cos(beta) * e[k] - math.sin(beta) * u[k] for k in range(3)))
        _state["meteors"][_state["meteor_slot"]] = {"t0": t, "a": a, "b": b, "speed": random.uniform(0.7, 1.3),
                                                    "len": random.uniform(0.12, 0.30), "life": random.uniform(0.6, 1.1),
                                                    "gain": random.uniform(0.7, 1.2)}
        _state["meteor_slot"] = (_state["meteor_slot"] + 1) % METEORS
    for i, m in enumerate(_state["meteors"]):
        age = t - m["t0"] if m else -1.0
        if m is None or age > m["life"]:
            scene["rt_met%d_a" % i] = 0.0
            continue
        head = age * m["speed"]
        vals = (*m["a"], *m["b"], head, min(m["len"], head), m["gain"] * math.sin(math.pi * age / m["life"]) ** 0.8)
        for f, val in zip(METEOR_FIELDS, vals):
            scene["rt_met%d_%s" % (i, f)] = val


def _norm(v):
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / n for c in v)


def flock(scene, dt):
    """rt_flock is the flamingos' flight time: it counts up once the sun sets and back
    down in daylight (rt_flock_dir -1), so they fly the same path home and land.
    Between the two thresholds they keep going the way they were."""
    night, d = scene.get("vj_night", 0.0), scene.get("rt_flock_dir", 0.0)
    if night > FLOCK_LEAVE:
        d = 1.0
    elif night < FLOCK_RETURN:
        d = -1.0
    scene["rt_flock_dir"] = d
    scene["rt_flock"] = min(max(scene.get("rt_flock", 0.0) + d * dt, 0.0), FLOCK_END)


def sync_output(scene):
    out, cam = scene.objects.get(OUTPUT_CAMERA), scene.camera
    if out is None or cam is None or cam == out:
        return
    con = out.constraints.get("Copy Transforms")
    if con is not None and con.target != cam:
        con.target = cam
    if out.data.lens != cam.data.lens:
        out.data.lens = cam.data.lens


def install_handler():
    handlers = bpy.app.handlers.frame_change_pre
    for h in list(handlers):
        if getattr(h, "__name__", "") == synthwave_tick.__name__:
            handlers.remove(h)
    handlers.append(synthwave_tick)


def start_bridge():
    start_sibling(BRIDGE_FILE, "OSC bridge")


def start_syphon(win, area):
    """Starts the zero-copy viewport sender syphon_out.py (next to the .blend) on
    CAM_OUT. The TextureSharing sender on CAM_OUT is switched off first and stays off."""
    out = bpy.context.scene.objects.get(OUTPUT_CAMERA)
    if out is not None and hasattr(out.data, "TEXS_share") and out.data.TEXS_share.enable:
        region = next(r for r in area.regions if r.type == "WINDOW")
        with bpy.context.temp_override(window=win, area=area, region=region, space_data=area.spaces[0],
                                       camera=out.data, object=out):
            out.data.TEXS_share.enable = False   # never change its capture size while it is on: that segfaults Blender
    start_sibling("//syphon_out.py", "Syphon sender")


def load_sibling(path, what):
    """Loads a module file next to the .blend; None if it is missing or fails."""
    import importlib.util
    import os
    spec = importlib.util.spec_from_file_location(os.path.basename(path)[:-3], bpy.path.abspath(path))
    try:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        print("synthwave_runtime: %s not loaded: %s" % (what, e))
        return None


def start_sibling(path, what):
    """Loads a module file next to the .blend and calls its start()."""
    module = load_sibling(path, what)
    try:
        if module is not None:
            module.start()
    except Exception as e:
        print("synthwave_runtime: %s not started: %s" % (what, e))


def _play():
    wm = bpy.context.window_manager
    for win in wm.windows:
        win.screen.show_statusbar = False   # its UI state builds up over a long show and drags playback from ~22 to ~5 fps
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                view = area.spaces.active       # Blender opens every 3D view in Solid shading whatever the file stores
                view.shading.type = "RENDERED"
                view.region_3d.view_perspective = "CAMERA"
                with bpy.context.temp_override(window=win, area=area):
                    if not bpy.context.screen.is_animation_playing:
                        bpy.ops.screen.animation_play()
                start_syphon(win, area)
                return None
    return None


def main():
    ensure_props(bpy.context.scene)
    bpy.app.driver_namespace[RUNTIME_KEY] = types.SimpleNamespace(
        freeze=freeze, advance=advance, steps_left=steps_left, quiesce=quiesce, CLOCKS=CLOCKS, STEP=STEP)
    install_handler()
    start_bridge()
    _state["star_system"] = load_sibling(STAR_SYSTEM_FILE, "star system")
    _state["day_world"] = load_sibling(DAY_WORLD_FILE, "day world")
    if not bpy.app.background:
        start_sibling(WEB_FILE, "web control page")
        bpy.app.timers.register(_play, first_interval=0.5)


main()
