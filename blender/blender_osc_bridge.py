"""OSC bridge for Blender 5.x. Pairs with osc/lab.py.

Run it inside Blender (Text Editor > Run Script, or
`blender --python blender_osc_bridge.py`). It then:

- listens for OSC on UDP 127.0.0.1:9201 without threads: a non-blocking
  socket drained from one bpy.app.timers callback;
- takes the contract's wire values (osc/CONTROLS.md: continuous controls 0..1,
  indices integers, triggers keep their strength), scales them to the scene
  units of the property with SCALES, and ignores addresses that are not rows;
- writes the first numeric argument of every message to a custom property
  on the scene: /vj/level -> scene["vj_level"]. Drivers read it as
  ["vj_level"] (Simple Expression, no Python needed);
- optionally routes addresses to RNA paths through MAPPING below;
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

- also listens for Art-Net (ArtDmx on udp 6454, blender/artnet_input.py) from a DMX desk or QLC+: one DMX channel per
  address of SCALES in contract order, only channels that changed are applied (source "artnet"), the first frame is a
  baseline, triggers fire on a rise through 128. Settings through `configure_artnet()` (universe 0, DMX start address 1, on);
  a failed bind is reported in artnet_state(), never fatal. docs/artnet-qlc.md.

Re-running the script replaces the previous instance. The scaling functions
(scale_wire, wire_to_scene) need no bpy and are unit tested in
blender/tests/test_bridge_scaling.py.
"""
import os
import socket
import struct
import sys
import time
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)            # artnet_input.py sits next to this file
import artnet_input  # noqa: E402

try:
    import bpy
except ImportError:      # the tests import this file outside Blender
    bpy = None

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

# address -> (kind, wire min, wire max, scene min, scene max) for the rows Blender uses.
# Written from osc/contract.json, so the three copies of the contract cannot drift.
# --- contract:begin (generated from osc/contract.json by `python3 osc/contract.py sync`, do not edit) ---
SCALES = {
    '/vj/level': ('float', 0, 1, 0, 1),
    '/vj/bass': ('float', 0, 1, 0, 1),
    '/vj/beat': ('float', 0, 1, 0, 1),
    '/vj/hue': ('float', 0, 1, 0, 1),
    '/vj/intensity': ('float', 0, 1, 0, 2),
    '/vj/strobe': ('float', 0, 1, 0, 1),
    '/vj/grid_speed': ('float', 0, 1, 0, 4),
    '/vj/cam_speed': ('float', 0, 1, 0, 4),
    '/vj/path': ('int', 0, 3, None, None),
    '/vj/target': ('int', 0, 6, None, None),
    '/vj/height': ('float', 0, 1, 0, 1),
    '/vj/sun': ('float', 0, 1, 0, 1),
    '/vj/moon': ('float', 0, 1, 0, 1),
    '/vj/moon_phase': ('float', 0, 1, 0, 1),
    '/vj/pyramids': ('float', 0, 1, 0, 1),
    '/vj/grid': ('float', 0, 1, 0, 1),
    '/vj/stars': ('float', 0, 1, 0, 1),
    '/vj/water': ('float', 0, 1, 0, 1),
    '/vj/night': ('float', 0, 1, 0, 1),
    '/vj/nebula': ('float', 0, 1, 0, 1),
    '/vj/shock': ('trigger', 0, 1.5, None, None),
    '/vj/meteor': ('trigger', 0, 1, None, None),
    '/vj/flamingos': ('float', 0, 1, 0, 1),
    '/vj/fog': ('float', 0, 1, 0, 1),
    '/vj/fog_height': ('float', 0, 1, 1, 60),
    '/vj/fog_glow': ('float', 0, 1, 0, 2),
    '/vj/fog_hue': ('float', 0, 1, 0, 1),
    '/vj/fog_noise': ('float', 0, 1, 0, 1),
    '/vj/fog_scale': ('float', 0, 1, 10, 1000),
    '/vj/fog_speed': ('float', 0, 1, 0, 40),
    '/vj/fog_beat': ('float', 0, 1, 0, 1),
    '/vj/haze': ('float', 0, 1, 0, 1),
    '/vj/eclipse': ('float', 0, 1, 0, 1),
    '/vj/star_speed': ('float', 0, 1, 0, 10),
    '/vj/blend': ('float', 0, 1, 0, 60),
    '/vj/takeover': ('float', 0, 1, 0, 60),
    '/vj/energy': ('float', 0, 1, 0, 1),
    '/vj/hit': ('trigger', 0, 1, None, None),
}
# --- contract:end ---

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


def scale_wire(address, value):
    """The scene value for a wire value, or None when the address is not a row Blender uses.
    Floats are clamped to the wire range and scaled linearly, an index is rounded inside its
    range, a trigger passes through with its strength."""
    row = SCALES.get(address)
    if row is None:
        return None
    kind, wmin, wmax, smin, smax = row
    if kind == "trigger":
        return float(value)
    v = min(max(float(value), wmin), wmax)
    if kind == "int":
        return float(int(round(v)))
    return smin + (v - wmin) / (wmax - wmin) * (smax - smin)


def wire_to_scene(address, args):
    """The message arguments with the first numeric one scaled to scene units, or None to ignore the message."""
    v = next((a for a in args if isinstance(a, (int, float)) and not isinstance(a, bool)), None)
    scaled = None if v is None else scale_wire(address, v)
    return None if scaled is None else [scaled]


def high(args):
    v = next((a for a in args if isinstance(a, (int, float)) and not isinstance(a, bool)), 0.0)
    return v >= 0.5


class Bridge:
    def __init__(self, host=HOST, port=PORT, artnet_port=artnet_input.ARTNET_PORT, artnet_host="", artnet_enabled=True):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)
        self.sock.bind((host, port))
        self.host, self.port = host, port
        self.received = 0
        self.applied = 0
        self.dropped = 0
        self.errors = 0
        self.ignored = 0          # messages whose address is not a contract row Blender uses
        self.limits = {}          # property name -> (min, max) from its UI data
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
        self.latest_art = {}      # address -> args from Art-Net, latest wins within a tick
        rows = artnet_input.channel_map((a, v[0], v[1], v[2]) for a, v in SCALES.items())
        self.artnet = artnet_input.ArtNetInput(artnet_input.DmxDecoder(rows), artnet_host, artnet_port, artnet_enabled)

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
                    continue
                args = wire_to_scene(addr, args)
                if args is None:
                    self.ignored += 1
                    continue
                args = self.fit(addr, args)
                if prop_name(addr) in self.hold:
                    self.held += 1
                elif addr in self.latest and self.is_trigger(prop_name(addr)) and high(self.latest[addr]) and not high(args):
                    self.pending[addr] = (args, "osc")     # a whole pulse within one tick: the fall waits for a frame
                elif addr in self.latest:
                    self.dropped += 1   # superseded within one tick
                    self.latest[addr] = args
                else:
                    self.latest[addr] = args
        self.drain_artnet(now)
        self.release()
        if self.latest:
            self.apply(self.latest)
            self.latest = {}
        if self.latest_art:
            self.apply(self.latest_art, "artnet")
            self.latest_art = {}
        for src, args in pings:
            self.pong(src, args)
        return TICK

    def drain_artnet(self, now):
        """Changed Art-Net channels take the same way as an OSC message: scaled, fitted, skipped when held."""
        for src, changes in self.artnet.poll():
            for addr, wire in changes:
                self.received += 1
                self.record(now, src, addr, [wire])
                args = wire_to_scene(addr, [wire])
                if args is None:
                    self.ignored += 1
                    continue
                args = self.fit(addr, args)
                if prop_name(addr) in self.hold:
                    self.held += 1
                elif addr in self.latest_art and self.is_trigger(prop_name(addr)) and high(self.latest_art[addr]) and not high(args):
                    self.pending[addr] = (args, "artnet")      # a whole pulse within one tick: the fall waits for a frame
                else:
                    if addr in self.latest_art:
                        self.dropped += 1
                    self.latest_art[addr] = args

    def artnet_state(self):
        return self.artnet.state()

    def configure_artnet(self, enabled=None, universe=None, address=None):
        """The settings the scene page can show: Art-Net on or off, the universe and the DMX start address."""
        if universe is not None or address is not None:
            self.artnet.decoder.configure(universe=universe, address=address)
        if enabled is not None:
            self.artnet.set_enabled(enabled)
        return self.artnet_state()

    def fit(self, addr, args):
        """Keeps a scaled float or index inside the property's own min and max, which can be narrower than the contract's range."""
        k = prop_name(addr)
        if SCALES[addr][0] == "trigger":
            return args
        lim = self.limits.get(k)
        if lim is None:
            try:
                ui = bpy.context.scene.id_properties_ui(k).as_dict()
            except (KeyError, TypeError):
                return args              # not a property yet: ask again once it exists
            lim = self.limits[k] = (ui.get("min"), ui.get("max"))
        lo, hi = lim
        v = args[0]
        if lo is not None:
            v = max(v, lo)
        if hi is not None:
            v = min(v, hi)
        return [v]

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
        self.artnet.close()


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
