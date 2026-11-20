#!/usr/bin/env python3
"""Local performer dashboard. Sends show commands to Magic without relaying scene OSC."""

import argparse
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
from threading import Lock
import time

from lab import encode_message
from show_protocol import CUES, DEFAULT_REACTIVITY, MAGIC_PORT, REACTIVITY, SCENES, SELECTION, selection

HOST = "127.0.0.1"
PORT = 8766
PAGE = Path(__file__).with_name("show_dashboard.html")


@dataclass
class ShowState:
    cue: str = "arrive"
    scene: str = "safe"
    reactivity: float = DEFAULT_REACTIVITY

    def set_cue(self, body):
        if set(body) == {"cue"} and isinstance(body["cue"], str) and body["cue"] in CUES:
            self.cue = body["cue"]
            self.scene = CUES[self.cue]
        elif set(body) == {"scene"} and body["scene"] in SCENES:
            self.scene = body["scene"]
        else:
            raise ValueError("Send one cue (arrive, build, peak, release) or one scene (planet, robot, safe).")
        return SELECTION, selection(self.cue, self.scene)

    def set_reactivity(self, body):
        value = body.get("value")
        if set(body) != {"value"} or type(value) not in (float, int) or not 0 <= value <= 1:
            raise ValueError("Send a numeric reactivity from 0 to 1.")
        self.reactivity = float(value)
        return REACTIVITY, self.reactivity

    def snapshot(self):
        return {
            "requested": {"cue": self.cue, "scene": self.scene, "reactivity": self.reactivity},
            "readiness": {"program": "unknown"},
        }

    def commands(self):
        return ((SELECTION, selection(self.cue, self.scene)), (REACTIVITY, self.reactivity))


class Dashboard(ThreadingHTTPServer):
    daemon_threads = False

    def __init__(self, port, magic_port, blender_port=None):
        super().__init__((HOST, port), Handler)
        self.show = ShowState()
        self.show_lock = Lock()
        self.destination = (HOST, magic_port)
        self.blender_destination = (HOST, blender_port) if blender_port is not None else None
        self.sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.refresh_at = 0

    def get_request(self):
        client, address = super().get_request()
        client.settimeout(2)
        return client, address

    def snapshot(self):
        with self.show_lock:
            return self.show.snapshot()

    def apply(self, setter, body):
        with self.show_lock:
            self.send(*setter(body))
            return self.show.snapshot()

    def send(self, address, value):
        packet = encode_message(address, [value])
        self.sender.sendto(packet, self.destination)
        if address == SELECTION and self.blender_destination is not None:
            self.sender.sendto(packet, self.blender_destination)

    def service_actions(self):
        # Replay set values so the project receives state even if Magic opened later.
        now = time.monotonic()
        if now >= self.refresh_at:
            with self.show_lock:
                for address, value in self.show.commands():
                    self.send(address, value)
            self.refresh_at = now + 0.5

    def server_close(self):
        super().server_close()
        sender = getattr(self, "sender", None)
        if sender is not None:
            sender.close()


class Handler(BaseHTTPRequestHandler):
    def reply(self, code, content, content_type="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def json_reply(self, code, body):
        self.reply(code, json.dumps(body, allow_nan=False).encode())

    def local_host(self):
        names = {HOST, "localhost"}
        allowed = names | {f"{name}:{self.server.server_port}" for name in names}
        if self.headers.get("Host") in allowed:
            return True
        self.json_reply(403, {"error": "Use the local dashboard address."})
        return False

    def do_GET(self):
        if not self.local_host():
            return
        if self.path == "/":
            self.reply(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/show":
            self.json_reply(200, self.server.snapshot())
        else:
            self.json_reply(404, {"error": "Not found."})

    def do_PUT(self):
        if not self.local_host():
            return
        show = self.server.show
        commands = {"/api/show/cue": show.set_cue, "/api/show/reactivity": show.set_reactivity}
        if self.path not in commands:
            self.json_reply(404, {"error": "Not found."})
            return
        if self.headers.get_content_type() != "application/json":
            self.json_reply(415, {"error": "Send an application/json body."})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 1024:
                raise ValueError("Send a JSON object up to 1024 bytes.")
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError("Send a JSON object.")
            state = self.server.apply(commands[self.path], body)
        except ValueError as exc:
            self.json_reply(400, {"error": str(exc)})
            return
        self.json_reply(200, state)

    def log_message(self, _format, *_args):
        pass


def port_number(value):
    port = int(value)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be from 1 to 65535")
    return port


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=port_number, default=PORT, help="local dashboard HTTP port")
    parser.add_argument("--magic-port", type=port_number, default=MAGIC_PORT, help="Magic's OSC input")
    parser.add_argument("--blender-port", type=port_number, help="optional Blender world switch socket")
    args = parser.parse_args()
    with Dashboard(args.port, args.magic_port, args.blender_port) as server:
        target = f" · Blender switch {HOST}:{args.blender_port}" if args.blender_port else ""
        print(f"Dashboard http://{HOST}:{server.server_port}/ · Magic OSC {HOST}:{args.magic_port}{target}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
