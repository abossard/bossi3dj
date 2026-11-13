"""Web control and debug page for synthwave_pyramids.blend, served by Blender itself.

Started by synthwave_runtime on file load; run it again to replace the
previous instance. Open http://127.0.0.1:9210 to drive the scene without Magic.

- The controls come from the scene: every vj_* custom property with its
  min, max, step and default (set by synthwave_runtime.ensure_props), so a
  new property shows up on the page without touching it. page_model.py (no bpy,
  unit tested) adds each control's address, group and plain sentence from
  osc/contract.json, orders them like the README manual and reports the
  addresses Blender reads that have no control ("coverage" in /api/state).
- Writes go through the OSC bridge's apply() (blender_osc_bridge.py), the
  same path as an OSC message, so /vj/cam cuts and redraws behave the same.
  Held properties are owned by the page: the bridge skips their OSC.
- Presets (named sets of values) live in blender/local/presets.json, shared by every
  device that opens the page: GET /api/presets, POST /api/presets {"name"} saves the current
  values, POST /api/presets/delete {"name"}. Recalling is the page's two calls, /api/set and /api/hold.
- The page listens on 127.0.0.1. For a phone on the same network, blender/local/page.json
  {"host": "lan"} (tools/blender_page_lan.py on) makes it listen on every interface, which lets any
  device on that network drive the scene. A POST needs a JSON content type, and on loopback the
  Host header must name loopback.
- A beat simulator stands in for Magic: vj_beat, vj_bass and vj_level at a
  BPM, and a shockwave every few beats.
- The preview is the Syphon frame, read back small by syphon_out.py only
  while this page asks for it.
- The feature check (synthwave_check.py, "Check all" on the page, `make blender-check`):
  POST /api/check starts it (body: {"only": [...], "frames_dir": "..."}), GET /api/check
  returns its progress and rows, POST /api/check/abort stops it. GET /api/health runs
  blender/review/health.py and returns its dict. The module is loaded
  again for every check, and nothing of it runs while no check runs.
- The HTTP server runs in a daemon thread and never touches bpy. One
  bpy.app.timers callback applies the queued writes on the main thread and
  publishes a snapshot (values, OSC stats and log, fps) for the page to poll.
"""
import importlib.util
import json
import math
import os
import queue
import threading
import time
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import bpy


def _load(path, name):
    """A module next to this file or in osc/, read from its file every start (a rebuilt scene never runs a stale copy)."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_HERE = os.path.dirname(os.path.abspath(__file__))
page_model = _load(os.path.join(_HERE, "page_model.py"), "page_model")
HOST, PORT = page_model.bind_host(), 9210
PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "synthwave_control.html")
TICK = 0.02           # s between write drains and simulator steps
PUBLISH_EVERY = 0.1   # s between snapshots, built only while a page polls
PAGE_IDLE = 2.0       # s after the last poll before snapshots stop
PULSE = 0.1           # s a trigger stays high, longer than one frame so the runtime sees the edge
LOG_SENT = 80         # newest OSC log lines in each snapshot
CONTRACT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "osc", "contract.json")
CHECK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "synthwave_check.py")
HEALTH_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "review", "health.py")
PREFIX = "vj_"
REGISTRY_KEY = "synthwave_web"
BRIDGE_KEY = "vj_osc_bridge"
SENDER_KEY = "syphon_out"
PREVIEW_KEY, PREVIEW_WANTED = "syphon_preview", "syphon_preview_wanted"   # shared with syphon_out.py


_contract = {"mtime": None, "rows": [], "groups": []}


def contract():
    """(rows, group order) of osc/contract.json, read again when the file changes."""
    try:
        mtime = os.stat(CONTRACT_FILE).st_mtime
        if mtime != _contract["mtime"]:
            with open(CONTRACT_FILE) as f:
                rows = json.load(f)["controls"]
            groups = _load(os.path.join(os.path.dirname(CONTRACT_FILE), "contract.py"), "vj_contract").GROUPS
            _contract.update(mtime=mtime, rows=rows, groups=list(groups))
    except (OSError, ValueError, AttributeError):
        pass
    return _contract["rows"], _contract["groups"]


def scene_kind(scene):
    """The scene's name in contract.BLENDER_SCENES, "planet" or "island": the planet scene has a Planet_Centre object."""
    return "planet" if scene.objects.get("Planet_Centre") else "island"


def shots(scene):
    """The names and sentences of this scene's cameras, from the /vj/cam row of osc/contract.json."""
    row = next((r for r in contract()[0] if r["address"] == "/vj/cam"), None)
    return [] if row is None else row.get("shots", {}).get(scene_kind(scene), [])


def controls(scene):
    out = []
    for k in sorted(k for k in scene.keys() if k.startswith(PREFIX)):
        if not isinstance(scene[k], (int, float)):
            continue
        ui = scene.id_properties_ui(k).as_dict()
        out.append({"key": k, "min": ui.get("min", 0.0), "max": ui.get("max", 1.0),
                    "step": ui.get("step", 1.0) / 100.0, "default": ui.get("default", 0.0),
                    "trigger": ui.get("description") == "trigger"})
        if k == "vj_cam":
            out[-1]["shots"] = shots(scene)
    return out


def load_check():
    import importlib.util
    spec = importlib.util.spec_from_file_location("synthwave_check", CHECK_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def shot_name(scene):
    """The shot on air: flight_rt keeps the rig in scene.camera and names the shot asked for in driver_namespace."""
    shot = bpy.app.driver_namespace.get("vj_shot")
    if shot is not None:
        return shot()
    return scene.camera.name if scene.camera else None


def address(key):
    return "/" + key.replace("_", "/", 1)   # vj_fog_height -> /vj/fog_height, which the bridge maps back


class Sim:
    """Fake music: a kick envelope at bpm, bass on the kick, a slow level swell, a shockwave every shock_every beats."""

    def __init__(self):
        self.on, self.bpm, self.shock_every = False, 124.0, 8
        self.t0 = time.time()

    def config(self, body):
        if "on" in body and bool(body["on"]) != self.on:
            self.on, self.t0 = bool(body["on"]), time.time()
        self.bpm = min(max(float(body.get("bpm", self.bpm)), 40.0), 220.0)
        self.shock_every = max(int(body.get("shock_every", self.shock_every)), 0)

    def step(self, now):
        beats = (now - self.t0) * self.bpm / 60.0
        beat, phase = int(beats), beats % 1.0
        out = {"vj_beat": math.exp(-6.0 * phase), "vj_bass": math.exp(-4.0 * phase) * 0.9,
               "vj_level": 0.55 + 0.25 * math.sin(beats * math.pi / 16.0)}
        if self.shock_every:
            out["vj_shock"] = 1.0 if beat % self.shock_every == 0 and phase * 60.0 / self.bpm < PULSE else 0.0
        return out

    def state(self):
        return {"on": self.on, "bpm": self.bpm, "shock_every": self.shock_every}


class Web:
    def __init__(self):
        self.writes = queue.Queue()
        self.snapshot = {}
        self.frames = []          # (time, scene frame, drawn frames) of the last second, for fps
        self.polled = 0.0         # last /api/state request, set by the HTTP thread
        self.published = 0.0
        self.sim = Sim()
        self.presets = page_model.Presets()
        self.art_prev = None      # (time, frames) of the Art-Net counter, for its rate
        self.lan = HOST != "127.0.0.1"
        self.check = None
        self.health = '{"error": "not run"}'
        self.server = ThreadingHTTPServer((HOST, PORT), self.handler())
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, name=REGISTRY_KEY, daemon=True)
        self.thread.start()
        bpy.app.timers.register(self.tick, persistent=True)

    def handler(self):
        web = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, body, ctype, status=200):
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def _host_ok(self):
                if page_model.host_allowed(self.headers.get("Host"), web.lan, PORT):
                    return True
                self._send(b'{"error": "host not allowed"}', "application/json", 403)
                return False

            def do_GET(self):
                path = self.path.split("?")[0]
                if not self._host_ok():
                    return
                if path in ("/", "/index.html"):
                    with open(PAGE, "rb") as f:
                        self._send(f.read(), "text/html; charset=utf-8")
                elif path == "/api/state":
                    web.polled = time.time()
                    self._send(json.dumps(web.snapshot).encode(), "application/json")
                elif path == "/api/check":
                    self._send((web.check.public if web.check else '{"state": "idle"}').encode(), "application/json")
                elif path == "/api/presets":
                    self._send(json.dumps({"presets": web.presets.all()}).encode(), "application/json")
                elif path == "/api/health":     # blender/review/health.py, run on the main thread
                    done = threading.Event()
                    web.writes.put((path, done))
                    done.wait(10)
                    self._send(web.health.encode(), "application/json")
                elif path == "/api/frame.bmp":
                    bpy.app.driver_namespace[PREVIEW_WANTED] = time.time()
                    frame = bpy.app.driver_namespace.get(PREVIEW_KEY)
                    self._send(frame, "image/bmp") if frame else self._send(b"", "image/bmp", 204)
                else:
                    self._send(b'{"error": "not found"}', "application/json", 404)

            def do_POST(self):
                path = self.path.split("?")[0]
                if not self._host_ok():
                    return
                if not (self.headers.get("Content-Type") or "").startswith("application/json"):
                    return self._send(b'{"error": "POST needs Content-Type: application/json"}', "application/json", 415)
                try:
                    body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                    if path in ("/api/set", "/api/defaults", "/api/hold", "/api/check"):
                        web.writes.put((path, body))
                    elif path == "/api/check/abort":
                        web.check and web.check.abort()
                    elif path == "/api/sim":
                        web.sim.config(body)
                    elif path == "/api/presets":
                        web.save_preset(body)
                    elif path == "/api/presets/delete":
                        web.presets.delete(str(body.get("name", "")))
                    else:
                        return self._send(b'{"error": "not found"}', "application/json", 404)
                    self._send(b'{"ok": true}', "application/json")
                except Exception as e:
                    self._send(json.dumps({"error": str(e)}).encode(), "application/json", 400)

        return Handler

    def tick(self):
        scene = bpy.context.scene
        bridge = bpy.app.driver_namespace.get(BRIDGE_KEY)
        while True:
            try:
                path, body = self.writes.get_nowait()
            except queue.Empty:
                break
            if path == "/api/set":
                self.apply(scene, bridge, {str(k): float(v) for k, v in body.items()}, "web")
            elif path == "/api/defaults":
                self.apply(scene, bridge, {c["key"]: c["default"] for c in controls(scene)}, "web")
            elif path == "/api/check":
                self.start_check(body)
            elif path == "/api/health":
                self.run_health(body)
            elif path == "/api/hold" and bridge is not None:
                keys = set(body.get("keys") or [c["key"] for c in page_model.page_controls(controls(scene), contract()[0], scene_kind(scene))])
                bridge.hold = bridge.hold | keys if body.get("on") else bridge.hold - keys
        now = time.time()
        if self.sim.on:
            self.apply(scene, bridge, self.sim.step(now), "sim")
        sender = bpy.app.driver_namespace.get(SENDER_KEY)
        self.frames.append((now, scene.frame_current, sender.frames if sender is not None else 0))
        while now - self.frames[0][0] > 1.0:
            self.frames.pop(0)
        if now - self.polled < PAGE_IDLE and now - self.published >= PUBLISH_EVERY:
            self.published = now
            self.publish(scene, bridge, now)
        return TICK

    def save_preset(self, body):
        """The current values of every control that is not a trigger, from the last snapshot (the page polls while it is open)."""
        controls_ = self.snapshot.get("controls") or []
        known = {c["key"] for c in controls_ if not c["trigger"]}
        values = {k: v for k, v in (self.snapshot.get("values") or {}).items() if k in known}
        if not values:
            raise page_model.PresetError("no values yet: open the page and try again")
        self.presets.save(body.get("name"), values, known)

    def start_check(self, opts):
        if self.check is not None and self.check.result["state"] == "running":
            return
        try:
            self.check = load_check().Check(self, controls, opts)
            self.check.start()
        except Exception as e:
            import traceback
            traceback.print_exc()
            err = json.dumps({"state": "failed", "error": "check not started: %s" % e, "rows": []})
            self.check = types.SimpleNamespace(public=err, result={"state": "failed"}, abort=lambda: None)

    def run_health(self, done):
        try:
            ns = {}
            with open(HEALTH_FILE) as f:
                exec(compile(f.read(), HEALTH_FILE, "exec"), ns)
            self.health = json.dumps(ns["result"])
        except Exception as e:
            self.health = json.dumps({"error": str(e)})
        done.set()

    def apply(self, scene, bridge, values, source):
        values = {k: v for k, v in values.items() if k.startswith(PREFIX) and k in scene}
        if not values:
            return
        if bridge is not None:
            bridge.apply({address(k): [v] for k, v in values.items()}, source)
        else:
            for k, v in values.items():
                scene[k] = v
            scene.update_tag()

    def publish(self, scene, bridge, now):
        (t0, f0, d0), (t1, f1, d1) = self.frames[0], self.frames[-1]
        rate = lambda a, b: round((b - a) / (t1 - t0), 1) if t1 > t0 and b >= a else 0.0
        snap = {
            "scene": scene.name, "camera": shot_name(scene),
            "fps": rate(d0, d1), "scene_fps": rate(f0, f1),   # drawn frames (what Syphon gets) vs frame counter, which skips
            "playing": bool(bpy.context.screen and bpy.context.screen.is_animation_playing),
            "sim": self.sim.state(), "edge_guard": bpy.app.driver_namespace.get("edge_guard"), "lan": self.lan,
            **page_model.page_state(controls(scene), *contract(), scene_kind(scene)),
            "values": {k: float(scene[k]) for k in scene.keys() if k.startswith(PREFIX)
                       and isinstance(scene[k], (int, float))},
        }
        sender = bpy.app.driver_namespace.get(SENDER_KEY)
        snap["syphon"] = {"frames": sender.frames, "failed": sender.failed} if sender is not None else None
        art = bridge.artnet_state() if bridge is not None and hasattr(bridge, "artnet_state") else None
        snap["artnet"] = {"state": art, "chip": page_model.artnet_chip(art, page_model.rate(self.art_prev, now, art["frames"]) if art else 0.0)}
        self.art_prev = (now, art["frames"]) if art else None
        if bridge is not None:
            snap["osc"] = {
                "port": bridge.port, "received": bridge.received, "applied": bridge.applied,
                "dropped": bridge.dropped, "held": bridge.held, "ignored": bridge.ignored, "errors": bridge.errors,
                "ticks_hz": len(bridge.tick_window), "hold": sorted(bridge.hold), "source": dict(bridge.source),
                "addresses": {a: {"n": s["n"], "hz": round(s["hz"], 1), "age": round(now - s["t"], 2),
                                  "v": [x if isinstance(x, (int, float, str)) else str(x) for x in s["v"]],
                                  "src": s["src"], "held": s["held"]} for a, s in bridge.stats.items()},
                "log": [[round(t, 3), src, a, list(args)] for t, src, a, args in list(bridge.log)[-LOG_SENT:]],
                "now": now,
            }
        self.snapshot = snap

    def close(self):
        if self.check is not None and self.check.result["state"] == "running":
            self.check.abort()
        try:
            bpy.app.timers.unregister(self.tick)
        except Exception:
            pass
        self.server.shutdown()
        self.server.server_close()


def start():
    old = bpy.app.driver_namespace.pop(REGISTRY_KEY, None)
    if old is not None:
        old.close()
    web = Web()
    bpy.app.driver_namespace[REGISTRY_KEY] = web
    print("synthwave_web: control page on http://%s:%d" % (HOST, PORT))
    return web


if __name__ == "__main__":
    start()
