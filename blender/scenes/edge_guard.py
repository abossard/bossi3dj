"""Night-edge guard of the planet scene: does the Terrain draw its real triangle edges at night?

Loaded by synthwave_runtime.py next to the .blend (start()), also run on demand through blender/review/edge_probe.py.
Two builds of the same code once opened with almost no night edge (line share 0.01 on CAM_0 against 0.12) until the
Triangulate node of `PL_Land` was muted and unmuted; nothing noticed. This module is the notice:

- probe: night 1, /vj/grid 1, wait a few Syphon frames, read the Syphon texture, /vj/grid 0, again; the line share is
  the fraction of pixels brighter with the grid than without by more than LINE_DELTA (as net_regularity.py counts it).
  The clocks are frozen while it runs, every control it touched is put back, held controls are released.
- guard: after the start, once the frame has a picture, probe once. Under MIN_SHARE: re-evaluate the land (mute and
  unmute the Triangulate node of PL_Land, a frame apart) and probe again. The result lands in
  driver_namespace["edge_guard"]; health.py reports status "missing" as a problem, start_check.py prints it.

No cost between probes: the module registers a draw handler and a timer only while it runs.
"""
import time

try:
    import bpy
except ImportError:                  # the decision logic is tested without Blender
    bpy = None

KEY = "edge_guard"
SENDER_KEY, BRIDGE_KEY, RUNTIME_KEY = "syphon_out", "vj_osc_bridge", "vj_runtime"
MIN_SHARE = 0.03        # line share of a night frame with the edges drawn (CAM_0 0.12, CAM_1 0.13); blank builds had 0.01
LINE_DELTA = 24         # a pixel is a line where the grid frame is brighter than the grid-off frame by more than this
SETTLE_FRAMES = 3       # Syphon frames drawn after a change before a frame is read
PICTURE_VARIANCE = 50.0  # luminance variance below which EEVEE is still compiling shaders (start_check.py uses the same)
PICTURE_TIMEOUT = 180.0  # s the guard waits for a picture before it gives up
PROBE_TIMEOUT = 40.0     # s one probe may run before it aborts and puts the controls back
TOUCHED = ("vj_night", "vj_grid")
TICK = 0.05
LAND_GROUP, TERRAIN_MATERIAL = "PL_Land", "Terrain"


def next_step(share_first, share_after=None):
    """What the guard does after a probe. share_first is the line share before any repair, share_after the one after
    the repair (None while it was not tried). Returns "present", "repair", "repaired" or "missing"."""
    if share_first >= MIN_SHARE:
        return "present"
    if share_after is None:
        return "repair"
    return "repaired" if share_after >= MIN_SHARE else "missing"


def line_share(on, off):
    """Fraction of pixels where `on` (grid 1) is brighter than `off` (grid 0) by more than LINE_DELTA in a channel."""
    import numpy as np
    d = on[:, :, :3].astype(np.int16) - off[:, :, :3].astype(np.int16)
    return float((d.max(axis=2) > LINE_DELTA).mean())


def luminance_variance(frame):
    import numpy as np
    lum = frame[::8, ::8, :3].astype(np.float32) @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    return float(lum.var())


def applicable():
    """Only a scene whose Terrain material holds a Wireframe node has night edges to guard."""
    mat = bpy.data.materials.get(TERRAIN_MATERIAL)
    return bool(mat and mat.node_tree and any(n.bl_idname == "ShaderNodeWireframe" for n in mat.node_tree.nodes))


def read(sender):
    import numpy as np
    a = np.asarray(sender.offscreen.texture_color.read())
    if a.dtype != np.uint8:
        a = np.clip(a * 255.0, 0, 255).astype(np.uint8)
    return a


class Guard:
    """One probe or guard run, stepped by a timer; a draw handler reads the Syphon texture on request."""

    def __init__(self, repair=True, force_blank=0, on_done=None):
        self.ns = bpy.app.driver_namespace
        self.repair, self.force_blank, self.on_done = repair, force_blank, on_done
        self.step, self.frame, self.want, self.got = "picture", None, False, None
        self.t_start = time.perf_counter()
        self.t_probe = None
        self.saved = None
        self.shares, self.on, self.cost = [], None, 0.0
        self.log = []
        self.result = self.ns[KEY] = {"status": "running", "shares": [], "repaired": False}
        self.handle = bpy.types.SpaceView3D.draw_handler_add(self.draw, (), "WINDOW", "POST_PIXEL")
        bpy.app.timers.register(self.tick, first_interval=1.0)

    # --- frames
    def sender(self):
        s = self.ns.get(SENDER_KEY)
        return s if s is not None and s.offscreen is not None and not s.failed else None

    def draw(self):
        if not self.want:
            return
        sender = self.sender()
        if sender is None or bpy.context.region_data is None or bpy.context.region_data.view_perspective != "CAMERA":
            return
        self.want = False
        try:
            self.got = read(sender)
        except Exception as e:
            self.got = e

    def request(self):
        self.got, self.want = None, True

    # --- controls
    def hold(self, values):
        bridge = self.ns[BRIDGE_KEY]
        bridge.hold = bridge.hold | set(values)
        bridge.apply({"/" + k.replace("_", "/", 1): [float(v)] for k, v in values.items()}, "web")

    def begin_probe(self):
        bridge, scene = self.ns[BRIDGE_KEY], bpy.context.scene
        self.saved = {"values": {k: scene.get(k) for k in TOUCHED}, "hold": set(bridge.hold),
                      "source": {k: bridge.source.get(k) for k in TOUCHED}}
        self.t_probe = time.perf_counter()
        self.hold({"vj_night": 1.0, "vj_grid": 1.0})
        self.settle("on")

    def settle(self, step):
        self.step, self.frame = step, self.ns[SENDER_KEY].frames

    def end_probe(self):
        """Puts back what the probe touched; safe to call twice."""
        if self.saved is None:
            return
        bridge, scene = self.ns[BRIDGE_KEY], bpy.context.scene
        for k, v in self.saved["values"].items():
            if v is not None:
                scene[k] = v
            if self.saved["source"][k] is None:
                bridge.source.pop(k, None)
            else:
                bridge.source[k] = self.saved["source"][k]
        bridge.hold = self.saved["hold"]
        scene.update_tag()
        self.saved = None
        rt = self.ns.get(RUNTIME_KEY)
        if rt is not None:
            rt.freeze(False)

    # --- the machine
    def tick(self):
        try:
            return self.advance()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.finish("error", str(e))
            return None

    def advance(self):
        now, sender = time.perf_counter(), self.sender()
        if self.saved is not None:
            rt = self.ns.get(RUNTIME_KEY)
            if rt is not None:
                rt.freeze(True)                  # renewed every tick: it lapses by itself after 4 s
            if now - self.t_probe > PROBE_TIMEOUT:
                self.finish("error", "probe timed out")
                return None
        if self.step == "picture":
            return self.wait_picture(now, sender)
        if sender is None:
            self.finish("error", "Syphon sender is gone")
            return None
        if self.step in ("on", "off", "mute", "unmute", "eval") and sender.frames < self.frame + SETTLE_FRAMES:
            return TICK
        if self.step in ("on", "off"):
            self.request()
            self.step += "_read"
            return TICK
        if self.step in ("on_read", "off_read"):
            if self.got is None:
                return TICK
            if isinstance(self.got, Exception):
                self.finish("error", "texture read failed: %s" % self.got)
                return None
            if self.step == "on_read":
                self.on = self.got
                self.hold({"vj_grid": 0.0})
                self.settle("off")
                return TICK
            share = line_share(self.on, self.got)
            self.on = None
            if self.force_blank > 0:
                self.force_blank -= 1
                self.result["forced"] = True
                share = 0.0
            self.shares.append(round(share, 4))
            self.cost += time.perf_counter() - self.t_probe
            self.end_probe()
            what = next_step(self.shares[0], self.shares[1] if len(self.shares) > 1 else None)
            if what == "repair" and self.repair:
                self.step = "mute"
                self.mute_triangulate(True)
                self.settle("mute")
                return TICK
            self.finish("missing" if what == "repair" else what)
            return None
        if self.step == "mute":
            self.mute_triangulate(False)
            self.settle("unmute")
            return TICK
        if self.step == "unmute":
            self.settle("eval")
            return TICK
        if self.step == "eval":                  # the land's evaluation is a frame behind the unmute
            self.begin_probe()
            return TICK
        return None

    def wait_picture(self, now, sender):
        if now - self.t_start > PICTURE_TIMEOUT:
            self.finish("no_picture", "no frame with a picture in %.0f s" % PICTURE_TIMEOUT)
            return None
        if sender is None:
            return 0.5
        if self.frame is None:
            self.frame = sender.frames
            self.request()
            return 0.5
        if self.got is None or sender.frames < self.frame + SETTLE_FRAMES:
            return 0.2
        if isinstance(self.got, Exception) or luminance_variance(self.got) < PICTURE_VARIANCE:
            self.frame = None
            return 1.0                           # still compiling shaders: ask again
        self.got = None
        self.begin_probe()
        return TICK

    def mute_triangulate(self, mute):
        group = bpy.data.node_groups.get(LAND_GROUP)
        nodes = [n for n in group.nodes if n.bl_idname == "GeometryNodeTriangulate"] if group else []
        for n in nodes:
            n.mute = mute
        if group:
            group.update_tag()
        self.result["repaired"] = True
        self.result["triangulate_nodes"] = len(nodes)

    def finish(self, status, note=None):
        self.end_probe()
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self.handle, "WINDOW")
        except Exception:
            pass
        r = self.result
        r.update(status=status, shares=self.shares, probe_ms=round(1000 * self.cost), min_share=MIN_SHARE,
                 total_s=round(time.perf_counter() - self.t_start, 1))
        if note:
            r["note"] = note
        print("edge_guard: %s" % r)
        if self.on_done:
            self.on_done(r)


def start(repair=True, force_blank=0, on_done=None):
    """Probe once the frame has a picture; `repair` re-evaluates the land when the edges are missing. force_blank=n
    makes the first n measurements read as blank (a test of the repair path, off by default). None if not applicable."""
    old = bpy.app.driver_namespace.get(KEY)
    if bpy.app.background or not applicable():
        bpy.app.driver_namespace[KEY] = {"status": "not_applicable"}
        return None
    if isinstance(old, dict) and old.get("status") == "running":
        return None
    return Guard(repair, force_blank, on_done)
