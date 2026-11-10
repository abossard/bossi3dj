"""OSC bridge for Blender 5.x. Pairs with osc/lab.py.

Run it inside Blender (Text Editor > Run Script, or
`blender --python blender_osc_bridge.py`). It then:

- listens for OSC on UDP 127.0.0.1:9201 without threads: a non-blocking
  socket drained from one bpy.app.timers callback;
- writes the first numeric argument of every message to a custom property
  on the scene: /vj/level -> scene["vj_level"]. Drivers read it as
  ["vj_level"] (Simple Expression, no Python needed);
- optionally routes addresses to RNA paths through MAPPING below;
- switches scene.camera on /vj/cam N to the camera named CAM_N;
- after each batch calls scene.update_tag() and redraws 3D views, which
  custom-property writes from Python otherwise skip;
- answers /lab/ping with /lab/pong so the lab page can show round-trip
  time and bridge stats;
- keeps per-address stats (count, rate, last value, sender) and the last
  LOG_SIZE messages for debug pages, and skips addresses whose property is
  in `hold` (a page that wants to own those values sets it);
- holds a trigger (a property whose UI description is "trigger") high for
  at least one frame change: a pulse that rises and falls within one tick or
  one frame (a 50 ms pulse at 15 fps) is otherwise never seen by the runtime.

Re-running the script replaces the previous instance.
"""
import socket
import struct
import sys
import time
from collections import deque

import bpy

HOST, PORT = "127.0.0.1", 9201
TICK = 0.0            # timer interval; 0.0 = every main-loop pass (~100-170 Hz measured on 5.2)
MAX_PER_TICK = 500    # datagrams drained per tick
HOLD_MAX = 0.5        # s a trigger is held high at most when no frame changes (playback stopped)

# Optional explicit routes: address -> (ID name, attribute, index or None).
# Only IDs found in bpy.data.objects are resolved. The default custom-property
# write happens as well, so drivers keep working.
MAPPING = {
    # "/vj/level": ("Cube", "scale", 2),
    # "/vj/hue":   ("Cube", "rotation_euler", 2),
}

# /vj/cam N makes the camera object named CAMERA_PREFIX + N the scene camera
# (drivers cannot set scene.camera).
CAMERA_ADDRESS = "/vj/cam"
CAMERA_PREFIX = "CAM_"

LOG_SIZE = 300       # recent messages kept for debug pages

REGISTRY_KEY = "vj_osc_bridge"


def _pad(n):
    return (n + 3) & ~3


def _read_str(d, i):
    e = d.index(b"\0", i)
    return d[i:e].decode("utf-8", "replace"), _pad(e + 1)


def parse_message(d):
    addr, i = _read_str(d, 0)
    if i >= len(d) or d[i:i + 1] != b",":
        return addr, "", []
    tags, i = _read_str(d, i)
    args = []
    for t in tags[1:]:
        if t == "f":
            args.append(struct.unpack(">f", d[i:i + 4])[0]); i += 4
        elif t == "i":
            args.append(struct.unpack(">i", d[i:i + 4])[0]); i += 4
        elif t == "d":
            args.append(struct.unpack(">d", d[i:i + 8])[0]); i += 8
        elif t == "s":
            s, i = _read_str(d, i); args.append(s)
        elif t == "T":
            args.append(True)
        elif t == "F":
            args.append(False)
        else:
            raise ValueError("typetag %r" % t)
    return addr, tags[1:], args


def parse_packet(d):
    if d.startswith(b"#bundle\0"):
        out, i = [], 16
        while i + 4 <= len(d):
            n = struct.unpack(">i", d[i:i + 4])[0]; i += 4
            out.extend(parse_packet(d[i:i + n])); i += n
        return out
    return [parse_message(d)]


def _enc_str(s):
    b = s.encode("utf-8") + b"\0"
    return b + b"\0" * (_pad(len(b)) - len(b))


def encode_message(address, args):
    tags, body = ",", b""
    for v in args:
        if isinstance(v, bool):
            tags += "T" if v else "F"
        elif isinstance(v, int):
            tags += "i"; body += struct.pack(">i", v)
        elif isinstance(v, float):
            tags += "f"; body += struct.pack(">f", v)
        else:
            tags += "s"; body += _enc_str(str(v))
    return _enc_str(address) + _enc_str(tags) + body


def prop_name(address):
    return address.strip("/").replace("/", "_")


def high(args):
    v = next((a for a in args if isinstance(a, (int, float)) and not isinstance(a, bool)), 0.0)
    return v >= 0.5


class Bridge:
    def __init__(self, host=HOST, port=PORT):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)
        self.sock.bind((host, port))
        self.host, self.port = host, port
        self.received = 0
        self.applied = 0
        self.dropped = 0
        self.errors = 0
        self.latest = {}          # address -> args, latest wins within a tick
        self.ticks = 0
        self.tick_window = []     # tick timestamps of the last second
        self.started = time.time()
        self.stats = {}           # address -> {"n", "hz", "t", "v", "src", "held"}
        self.log = deque(maxlen=LOG_SIZE)   # (time, source, address, args)
        self.hold = set()         # property names whose OSC messages are skipped
        self.held = 0
        self.source = {}          # property name -> "osc" or what apply() was given
        self.raised = {}          # trigger property -> (frame, time) it went high
        self.pending = {}         # trigger address -> (args, source): the fall, applied after a frame change
        self.triggers = {}        # property name -> is it a trigger

    # One timer callback. Returns the next delay (keeps the timer alive).
    def tick(self):
        now = time.time()
        self.ticks += 1
        self.tick_window.append(now)
        while self.tick_window and now - self.tick_window[0] > 1.0:
            self.tick_window.pop(0)
        pings = []
        for _ in range(MAX_PER_TICK):
            try:
                data, src = self.sock.recvfrom(65535)
            except BlockingIOError:
                break
            except OSError:
                self.errors += 1
                break
            try:
                msgs = parse_packet(data)
            except Exception:
                self.errors += 1
                continue
            for addr, _tags, args in msgs:
                self.received += 1
                self.record(now, src, addr, args)
                if addr == "/lab/ping":
                    pings.append((src, args))
                elif prop_name(addr) in self.hold:
                    self.held += 1
                elif addr in self.latest and self.is_trigger(prop_name(addr)) and high(self.latest[addr]) and not high(args):
                    self.pending[addr] = (args, "osc")     # a whole pulse within one tick: the fall waits for a frame
                elif addr in self.latest:
                    self.dropped += 1   # superseded within one tick
                    self.latest[addr] = args
                else:
                    self.latest[addr] = args
        self.release()
        if self.latest:
            self.apply(self.latest)
            self.latest = {}
        for src, args in pings:
            self.pong(src, args)
        return TICK

    def record(self, now, src, addr, args):
        st = self.stats.get(addr)
        if st is None:
            st = self.stats[addr] = {"n": 0, "hz": 0.0, "t": now}
        elif now > st["t"]:
            st["hz"] += (1.0 / (now - st["t"]) - st["hz"]) * 0.1   # smoothed message rate
        st.update(n=st["n"] + 1, t=now, v=args, src="%s:%d" % src[:2], held=prop_name(addr) in self.hold)
        self.log.append((now, st["src"], addr, args))

    def is_trigger(self, k):
        t = self.triggers.get(k)
        if t is None:
            try:
                t = bpy.context.scene.id_properties_ui(k).as_dict().get("description") == "trigger"
            except (KeyError, TypeError):
                return False                 # not a property yet: ask again once it exists
            self.triggers[k] = t
        return t

    def release(self):
        """Applies the held falls of triggers that have been high over a frame change (or for HOLD_MAX s)."""
        if not self.pending:
            return
        frame, now = bpy.context.scene.frame_current, time.time()
        due = [a for a in self.pending if self.raised.get(prop_name(a), (None, 0.0))[0] != frame
               or now - self.raised[prop_name(a)][1] > HOLD_MAX]
        for addr in due:
            args, source = self.pending.pop(addr)
            self.apply({addr: args}, source)

    def apply(self, latest, source="osc"):
        scene = bpy.context.scene
        for addr, args in latest.items():
            v = next((a for a in args if isinstance(a, (int, float)) and not isinstance(a, bool)), None)
            if v is None:
                continue
            k = prop_name(addr)
            if self.is_trigger(k):
                if v >= 0.5 > scene.get(k, 0.0):
                    self.raised[k] = (scene.frame_current, time.time())
                elif v < 0.5 <= scene.get(k, 0.0) and self.raised.get(k, (None,))[0] == scene.frame_current:
                    self.pending[addr] = (args, source)     # not seen by a frame yet: fall after the next one
                    continue
            scene[prop_name(addr)] = float(v)
            self.source[prop_name(addr)] = source
            self.applied += 1
            if addr == CAMERA_ADDRESS:
                cam = bpy.data.objects.get("%s%d" % (CAMERA_PREFIX, int(round(v))))
                if cam is not None and cam.type == "CAMERA" and scene.camera != cam:
                    scene.camera = cam
            route = MAPPING.get(addr)
            if route:
                ob = bpy.data.objects.get(route[0])
                if ob is not None:
                    attr = getattr(ob, route[1])
                    if route[2] is None:
                        setattr(ob, route[1], v)
                    else:
                        attr[route[2]] = v
        scene.update_tag()
        wm = bpy.context.window_manager
        if wm:
            for win in wm.windows:
                for area in win.screen.areas:
                    if area.type == "VIEW_3D":
                        area.tag_redraw()

    def pong(self, src, args):
        seq = args[0] if args else 0
        sent_t = args[1] if len(args) > 1 else 0.0
        ticks_hz = float(len(self.tick_window))
        msg = encode_message("/lab/pong", [
            int(seq), float(sent_t), bpy.app.version_string, bpy.context.scene.name,
            ticks_hz, int(self.received), int(self.applied), int(self.dropped),
            "%d.%d" % sys.version_info[:2],
        ])
        try:
            self.sock.sendto(msg, src)
        except OSError:
            self.errors += 1

    def close(self):
        try:
            bpy.app.timers.unregister(self.tick)
        except Exception:
            pass
        self.sock.close()


def start(host=HOST, port=PORT, register_timer=True):
    old = bpy.app.driver_namespace.get(REGISTRY_KEY)
    if old is not None:
        old.close()
    bridge = Bridge(host, port)
    bpy.app.driver_namespace[REGISTRY_KEY] = bridge
    if register_timer:
        bpy.app.timers.register(bridge.tick, persistent=True)
    print("vj_osc_bridge: listening on udp %s:%d, props on scene %r" % (host, port, bpy.context.scene.name))
    return bridge


if __name__ == "__main__":
    start()
