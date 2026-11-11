#!/usr/bin/env python3
"""Magic -> Blender OSC lab.

Sits between Magic Music Visuals (OSCSender) and Blender (blender_osc_bridge.py):

    Magic --OSC--> lab:LISTEN --relay--> Blender:BLENDER_PORT
                     ^                       |
                     +----- /lab/pong <------+

Serves a debug page on http://127.0.0.1:HTTP that shows every incoming
message (type tags, values, rate), relays packets to Blender, sends test
messages and generators, and pings the Blender bridge for round-trip time.

The page's sliders and generators work in wire units and start at the wire defaults of
contract.json (served at /api/contract), the one table of CONTROLS.md.

Standard library only. Run: python3 lab.py --help
"""
import argparse
import json
import math
import os
import random
import socket
import struct
import subprocess
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import contract  # noqa: E402  the /vj/* rows (contract.json) behind the page's sliders and generator ranges


# --- OSC encoding / decoding (calculations, no side effects) -----------------

def _pad(n):
    return (n + 3) & ~3


def _read_str(data, i):
    end = data.index(b"\0", i)
    return data[i:end].decode("utf-8", errors="replace"), _pad(end + 1)


def parse_message(data):
    """-> (address, typetags, args). Raises ValueError on malformed input."""
    addr, i = _read_str(data, 0)
    if i >= len(data) or data[i:i + 1] != b",":
        return addr, "", []
    tags, i = _read_str(data, i)
    tags = tags[1:]
    args = []
    for t in tags:
        if t == "f":
            args.append(struct.unpack(">f", data[i:i + 4])[0]); i += 4
        elif t == "i":
            args.append(struct.unpack(">i", data[i:i + 4])[0]); i += 4
        elif t == "d":
            args.append(struct.unpack(">d", data[i:i + 8])[0]); i += 8
        elif t == "h":
            args.append(struct.unpack(">q", data[i:i + 8])[0]); i += 8
        elif t == "s" or t == "S":
            s, i = _read_str(data, i); args.append(s)
        elif t == "b":
            n = struct.unpack(">i", data[i:i + 4])[0]; i += 4
            args.append({"blob": data[i:i + n].hex()}); i += _pad(n)
        elif t == "T":
            args.append(True)
        elif t == "F":
            args.append(False)
        elif t == "N":
            args.append(None)
        elif t == "I":
            args.append("impulse")
        elif t == "t":
            args.append({"timetag": struct.unpack(">Q", data[i:i + 8])[0]}); i += 8
        else:
            raise ValueError("unknown typetag %r" % t)
    return addr, tags, args


def parse_packet(data):
    """-> list of (address, typetags, args, bundled: bool)."""
    if data.startswith(b"#bundle\0"):
        out, i = [], 16
        while i + 4 <= len(data):
            n = struct.unpack(">i", data[i:i + 4])[0]; i += 4
            for m in parse_packet(data[i:i + n]):
                out.append((m[0], m[1], m[2], True))
            i += n
        return out
    a, t, g = parse_message(data)
    return [(a, t, g, False)]


def _enc_str(s):
    b = s.encode("utf-8") + b"\0"
    return b + b"\0" * (_pad(len(b)) - len(b))


def encode_message(address, args):
    """args: list of {"t": "f"|"i"|"s"|"T"|"F", "v": value} or plain python values."""
    tags, body = ",", b""
    for a in args:
        if isinstance(a, dict):
            t, v = a.get("t", "f"), a.get("v")
        elif isinstance(a, bool):
            t, v = ("T" if a else "F"), a
        elif isinstance(a, int):
            t, v = "i", a
        elif isinstance(a, float):
            t, v = "f", a
        else:
            t, v = "s", str(a)
        tags += t
        if t == "f":
            body += struct.pack(">f", float(v))
        elif t == "i":
            body += struct.pack(">i", int(v))
        elif t == "d":
            body += struct.pack(">d", float(v))
        elif t == "s":
            body += _enc_str(str(v))
    return _enc_str(address) + _enc_str(tags) + body


# --- Lab state ----------------------------------------------------------------

class AddressStats:
    __slots__ = ("count", "tags", "last", "vmin", "vmax", "times", "values", "last_t", "bundled")

    def __init__(self):
        self.count = 0
        self.tags = ""
        self.last = []
        self.vmin = None
        self.vmax = None
        self.times = deque(maxlen=256)
        self.values = deque(maxlen=120)
        self.last_t = 0.0
        self.bundled = False

    def add(self, t, tags, args, bundled):
        self.count += 1
        self.tags = tags
        self.last = args
        self.last_t = t
        self.bundled = self.bundled or bundled
        self.times.append(t)
        v = next((a for a in args if isinstance(a, (int, float)) and not isinstance(a, bool)), None)
        if v is not None:
            self.values.append(v)
            self.vmin = v if self.vmin is None else min(self.vmin, v)
            self.vmax = v if self.vmax is None else max(self.vmax, v)

    def hz(self, now):
        if len(self.times) < 2 or now - self.times[-1] > 2.0:
            return 0.0
        recent = [x for x in self.times if now - x <= 2.0]
        if len(recent) < 2:
            return 0.0
        return (len(recent) - 1) / max(recent[-1] - recent[0], 1e-6)

    def snapshot(self, now):
        return {
            "count": self.count, "tags": self.tags, "last": self.last,
            "min": self.vmin, "max": self.vmax, "hz": round(self.hz(now), 1),
            "age": round(now - self.last_t, 2), "bundled": self.bundled,
            "series": list(self.values),
        }


LOCAL_HOSTS = ("127.0.0.1", "localhost", "0.0.0.0")


def _port(value):
    port = int(value)
    if not 0 <= port <= 65535:
        raise ValueError("port %d is outside 0..65535" % port)
    return port


def _port_arg(value):
    try:
        return _port(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e))


class Lab:
    def __init__(self, args):
        self.lock = threading.Lock()
        self.listen = (args.bind, args.listen)
        self.config = {
            "relay": not args.no_relay,
            "blender_host": args.blender_host,
            "blender_port": args.blender_port,
            "godot_port": args.godot_port,
            "autoping": True,
        }
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(self.listen)
        self.addresses = {}
        self.log = deque(maxlen=1000)
        self.log_id = 0
        self.packets = 0
        self.packet_times = deque(maxlen=512)
        self.bundles = 0
        self.relayed = 0
        self.errors = 0
        self.started = time.time()
        self.logfile = open(args.log, "a", buffering=1) if args.log else None
        self.blender = {"pong_t": 0.0, "rtt_ms": None, "rtts": deque(maxlen=60), "info": {}, "seq": 0, "pending": {}}
        self.generators = {}
        self.processes = {"magic": False, "blender": False}
        self.sources = {}

    # -- incoming --------------------------------------------------------------
    def rx_loop(self):
        while True:
            data, src = self.sock.recvfrom(65535)
            self.handle_packet(data, src, time.time())

    def handle_packet(self, data, src, now):
        try:
            msgs = parse_packet(data)
        except Exception as e:  # malformed: still log it
            with self.lock:
                self.errors += 1
                self._log(now, "?", "", [], len(data), src, False, raw=data.hex(), error=str(e))
            return
        with self.lock:
            self.packets += 1
            self.packet_times.append(now)
            self.sources[src[0]] = now
            if data.startswith(b"#bundle\0"):
                self.bundles += 1
            for addr, tags, args, bundled in msgs:
                if addr.startswith("/lab/"):
                    self._handle_lab(addr, args, now, src)
                    continue
                st = self.addresses.get(addr)
                if st is None:
                    if len(self.addresses) >= 300:
                        continue
                    st = self.addresses[addr] = AddressStats()
                st.add(now, tags, args, bundled)
                self._log(now, addr, tags, args, len(data), src, bundled)
            relay = self.config["relay"] and not any(a.startswith("/lab/") for a, _, _, _ in msgs)
            targets = self.targets()
        if relay:
            sent = 0
            for target in targets:
                try:
                    self.sock.sendto(data, target)
                    sent += 1
                except (OSError, OverflowError):
                    with self.lock:
                        self.errors += 1
            if sent:
                with self.lock:
                    self.relayed += 1

    def _log(self, now, addr, tags, args, size, src, bundled, **extra):
        self.log_id += 1
        entry = {"id": self.log_id, "t": round(now, 6), "addr": addr, "tags": tags, "args": args,
                 "len": size, "src": "%s:%d" % src, "bundled": bundled}
        entry.update(extra)
        self.log.append(entry)
        if self.logfile:
            self.logfile.write(json.dumps(entry) + "\n")

    def _handle_lab(self, addr, args, now, src):
        if addr == "/lab/pong" and args:
            seq = args[0]
            sent = self.blender["pending"].pop(seq, None)
            if sent is not None:
                rtt = (now - sent) * 1000.0
                self.blender["rtt_ms"] = round(rtt, 2)
                self.blender["rtts"].append(round(rtt, 2))
            self.blender["pong_t"] = now
            keys = ["seq", "sent_t", "blender", "scene", "ticks_hz", "received", "applied", "dropped", "python"]
            self.blender["info"] = dict(zip(keys, args))
            self.blender["info"]["src"] = "%s:%d" % src
            self.blender["pending"] = {k: v for k, v in self.blender["pending"].items() if now - v < 5}

    # -- outgoing --------------------------------------------------------------
    def checked_port(self, key, value):
        """A relay port from the page: 0..65535 and never the lab's own listen port."""
        port = _port(value)
        if port and port == self.listen[1] and (key == "godot_port" or self.config["blender_host"] in LOCAL_HOSTS):
            raise ValueError("%s %d is the lab's own listen port" % (key, port))
        return port

    def targets(self):
        """Relay targets: the Blender bridge, plus the Godot Colossus Scene when its port is set.
        Call with the lock held."""
        out = [(self.config["blender_host"], int(self.config["blender_port"]))]
        if self.config["godot_port"] and not (self.config["blender_host"] in LOCAL_HOSTS and self.config["godot_port"] == self.config["blender_port"]):
            out.append(("127.0.0.1", int(self.config["godot_port"])))      # the same local port twice would double every packet
        return out

    def send(self, address, args, host=None, port=None, everywhere=False):
        """Send to host:port, else to the Blender target, or with everywhere to every relay target."""
        with self.lock:
            if host or port:
                targets = [(host or self.config["blender_host"], int(port or self.config["blender_port"]))]
            elif everywhere:
                targets = self.targets()
            else:
                targets = [(self.config["blender_host"], int(self.config["blender_port"]))]
        data = encode_message(address, args)
        for target in targets:
            self.sock.sendto(data, target)

    def ping(self):
        with self.lock:
            self.blender["seq"] += 1
            seq = self.blender["seq"]
            now = time.time()
            self.blender["pending"] = {k: v for k, v in self.blender["pending"].items() if now - v < 5}
            self.blender["pending"][seq] = now
        self.send("/lab/ping", [{"t": "i", "v": seq}, {"t": "d", "v": now}])
        return seq

    def autoping_loop(self):
        while True:
            if self.config["autoping"]:
                try:
                    self.ping()
                except OSError:
                    pass
            time.sleep(1.0)

    def process_loop(self):
        while True:
            self.processes = {
                "magic": _pgrep("-f", "/Applications/Magic"),
                "blender": _pgrep("-x", "Blender"),
            }
            time.sleep(2.0)

    # -- generators --------------------------------------------------------------
    def set_generator(self, g):
        gid = str(g.get("id") or ("g%d" % (len(self.generators) + 1)))
        if g.get("delete"):
            with self.lock:
                old = self.generators.pop(gid, None)
            if old:
                old["stop"].set()
            return gid
        spec = {
            "id": gid, "address": g.get("address", "/lab/gen"), "wave": g.get("wave", "sine"),
            "freq": float(g.get("freq", 0.5)), "rate": float(g.get("rate", 60)),
            "min": float(g.get("min", 0.0)), "max": float(g.get("max", 1.0)),
            "enabled": bool(g.get("enabled", True)), "sent": 0, "stop": threading.Event(),
        }
        with self.lock:
            old = self.generators.pop(gid, None)
            self.generators[gid] = spec
        if old:
            old["stop"].set()
        if spec["enabled"]:
            threading.Thread(target=self._generator_loop, args=(spec,), daemon=True).start()
        return gid

    def _generator_loop(self, spec):
        t0 = time.time()
        period = 1.0 / max(spec["rate"], 0.1)
        nxt = t0
        while not spec["stop"].is_set():
            now = time.time()
            if now < nxt:
                time.sleep(min(nxt - now, 0.01))
                continue
            nxt += period
            ph = (now - t0) * spec["freq"]
            if spec["wave"] == "sine":
                u = 0.5 + 0.5 * math.sin(2 * math.pi * ph)
            elif spec["wave"] == "square":
                u = 1.0 if (ph % 1.0) < 0.5 else 0.0
            elif spec["wave"] == "ramp":
                u = ph % 1.0
            elif spec["wave"] == "beat":  # decaying pulse on every beat, like a level follower
                u = math.exp(-6.0 * (ph % 1.0))
            else:
                u = random.random()
            v = spec["min"] + (spec["max"] - spec["min"]) * u
            try:
                self.send(spec["address"], [{"t": "f", "v": v}], everywhere=True)
                spec["sent"] += 1
            except (OSError, OverflowError):
                pass

    # -- snapshot -----------------------------------------------------------------
    def snapshot(self, since=0, max_log=200):
        now = time.time()
        with self.lock:
            recent = [t for t in self.packet_times if now - t <= 2.0]
            pps = (len(recent) - 1) / max(recent[-1] - recent[0], 1e-6) if len(recent) >= 2 else 0.0
            new = [e for e in self.log if e["id"] > since][-max_log:]
            b = self.blender
            return {
                "t": now,
                "listen": "%s:%d" % self.listen,
                "config": dict(self.config),
                "totals": {"packets": self.packets, "bundles": self.bundles, "relayed": self.relayed,
                           "errors": self.errors, "pps": round(pps, 1), "uptime": round(now - self.started)},
                "sources": {k: round(now - v, 1) for k, v in self.sources.items()},
                "addresses": {a: s.snapshot(now) for a, s in sorted(self.addresses.items())},
                "blender": {"alive": (now - b["pong_t"]) < 3.0, "pong_age": round(now - b["pong_t"], 1) if b["pong_t"] else None,
                            "rtt_ms": b["rtt_ms"], "rtts": list(b["rtts"]), "info": b["info"],
                            "pending": len(b["pending"])},
                "generators": [{k: v for k, v in g.items() if k != "stop"} for g in self.generators.values()],
                "processes": dict(self.processes),
                "log": new,
                "log_id": self.log_id,
            }

    def clear(self):
        with self.lock:
            self.addresses.clear()
            self.log.clear()
            self.packets = self.bundles = self.relayed = self.errors = 0
            self.packet_times.clear()
            self.sources.clear()
            self.blender["rtts"].clear()


def _pgrep(*args):
    try:
        return subprocess.run(["pgrep", *args], capture_output=True, timeout=2).returncode == 0
    except Exception:
        return False


# --- HTTP ---------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    lab = None

    def log_message(self, *a):  # quiet
        pass

    def _json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/contract":
            self._json(contract.load())
        elif path == "/api/state":
            self._json(self.lab.snapshot())
        elif path == "/api/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            since = 0
            try:
                while True:
                    snap = self.lab.snapshot(since)
                    since = snap["log_id"]
                    self.wfile.write(b"data: " + json.dumps(snap).encode() + b"\n\n")
                    self.wfile.flush()
                    time.sleep(0.1)
            except (BrokenPipeError, ConnectionResetError):
                return
        elif path == "/api/log.jsonl":
            with self.lab.lock:
                body = "".join(json.dumps(e) + "\n" for e in self.lab.log).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Content-Disposition", "attachment; filename=osc-log.jsonl")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            body = self._body()
            if path == "/api/config":
                with self.lab.lock:
                    for k in ("relay", "autoping"):
                        if k in body:
                            self.lab.config[k] = bool(body[k])
                    if "blender_host" in body:
                        self.lab.config["blender_host"] = str(body["blender_host"])
                    for k in ("blender_port", "godot_port"):
                        if k in body:
                            self.lab.config[k] = self.lab.checked_port(k, body[k])
                self._json({"ok": True, "config": self.lab.config})
            elif path == "/api/send":
                self.lab.send(body["address"], body.get("args", []), body.get("host"), body.get("port"),
                              everywhere=True)
                self._json({"ok": True})
            elif path == "/api/ping":
                self._json({"ok": True, "seq": self.lab.ping()})
            elif path == "/api/generators":
                self._json({"ok": True, "id": self.lab.set_generator(body)})
            elif path == "/api/clear":
                self.lab.clear()
                self._json({"ok": True})
            else:
                self._json({"error": "not found"}, 404)
        except Exception as e:
            self._json({"error": str(e)}, 400)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--http", type=int, default=8765, help="web page port (default 8765)")
    ap.add_argument("--bind", default="127.0.0.1", help="UDP bind address (default 127.0.0.1)")
    ap.add_argument("--listen", type=int, default=9200, help="UDP port Magic sends to (default 9200)")
    ap.add_argument("--blender-host", default="127.0.0.1")
    ap.add_argument("--blender-port", type=_port_arg, default=9201, help="port blender_osc_bridge.py listens on (default 9201)")
    ap.add_argument("--godot-port", type=_port_arg, default=0, help="second relay target on 127.0.0.1 for the Godot Colossus Scene (default 0 = off: Blender and Godot share udp 9201 and never run together)")
    ap.add_argument("--no-relay", action="store_true", help="start with relay to Blender and Godot off")
    ap.add_argument("--log", help="append every received message as JSON lines to this file")
    args = ap.parse_args()
    if args.godot_port == args.listen or (args.blender_port == args.listen and args.blender_host in LOCAL_HOSTS):
        ap.error("a relay port equals --listen %d; packets would loop back into the lab" % args.listen)

    lab = Lab(args)
    Handler.lab = lab
    for fn in (lab.rx_loop, lab.autoping_loop, lab.process_loop):
        threading.Thread(target=fn, daemon=True).start()
    httpd = ThreadingHTTPServer(("127.0.0.1", args.http), Handler)
    httpd.daemon_threads = True
    print("lab: page http://127.0.0.1:%d  Magic -> udp %s:%d  relay -> %s:%d" % (
        args.http, args.bind, args.listen, args.blender_host, args.blender_port), flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
