#!/usr/bin/env python3
"""The Blender scene's control page without Blender: the real page and page model on a test port, fed with fake scene values.

    python3 tools/blender_page_mock.py [--port 19210] [--lan]

For looking at the layout (phone width in the browser pane) and for the unit tests of the page JSON, while Blender is not free.
Serves blender/scenes/synthwave_control.html and the /api/state shape of synthwave_web.py: controls from osc/contract.json at the
Blender scene ranges, values that move, a counter that stands in for the Syphon frames. Presets go to a temp file. Standard library only.
"""
import argparse
import json
import os
import sys
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "blender", "scenes"))
sys.path.insert(0, os.path.join(ROOT, "osc"))
import contract  # noqa: E402
import page_model  # noqa: E402


def scene_controls(rows):
    """What synthwave_web.controls() reads from the planet scene's properties: key, range, step, default, trigger flag."""
    out = []
    for r in page_model.blender_rows(rows):
        b, key = r["blender"], page_model.key_of(r["address"])
        if r["kind"] == "int":
            c = {"key": key, "min": 0, "max": r["max"], "step": 1.0, "default": r["default"], "trigger": False}
            c["shots"] = r["shots"]["planet"]
        elif r["kind"] == "trigger":
            c = {"key": key, "min": 0.0, "max": r["max"], "step": 0.01, "default": 0.0, "trigger": True}
        else:
            lo, hi = b["min"], b["max"]
            c = {"key": key, "min": lo, "max": hi, "step": 0.01 if hi - lo <= 4 else 1.0 if hi - lo > 40 else 0.1,
                 "default": lo + (r["default"] - r["min"]) / (r["max"] - r["min"]) * (hi - lo), "trigger": False}
        out.append(c)
    return out


class Mock:
    def __init__(self):
        self.rows = contract.load()
        self.controls = scene_controls(self.rows)
        self.values = {c["key"]: c["default"] for c in self.controls}
        self.hold, self.source = set(), {}
        self.t0 = time.time()
        self.presets = page_model.Presets(os.path.join(tempfile.mkdtemp(prefix="page-mock-"), "presets.json"))
        self.lan = False

    def state(self):
        n = time.time() - self.t0
        return {"scene": "Synthwave Planet (mock)", "camera": "CAM_%d" % round(self.values["vj_cam"]), "fps": 59.8, "scene_fps": 60.0, "playing": True,
                "sim": {"on": False, "bpm": 124.0, "shock_every": 8}, "edge_guard": {"status": "present", "repaired": False}, "lan": self.lan,
                **page_model.page_state(self.controls, self.rows, contract.GROUPS), "values": self.values,
                "syphon": {"frames": int(n * 60), "failed": False},
                "osc": {"port": 9201, "received": int(n * 400), "applied": int(n * 400), "dropped": 0, "held": 0, "ignored": 0, "errors": 0,
                        "ticks_hz": 120, "hold": sorted(self.hold), "source": self.source, "addresses": {}, "log": [], "now": time.time()}}


def handler(mock):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, body, ctype="application/json", status=200):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/":
                with open(os.path.join(ROOT, "blender", "scenes", "synthwave_control.html"), "rb") as f:
                    self.send(f.read(), "text/html; charset=utf-8")
            elif path == "/api/state":
                self.send(json.dumps(mock.state()).encode())
            elif path == "/api/check":
                self.send(b'{"state": "idle"}')
            elif path == "/api/presets":
                self.send(json.dumps({"presets": mock.presets.all()}).encode())
            else:
                self.send(b'{"error": "not found"}', status=404)

        def do_POST(self):
            path = self.path.split("?")[0]
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            try:
                if path == "/api/set":
                    for k, v in body.items():
                        mock.values[k] = float(v)
                        mock.source[k] = "web"
                elif path == "/api/hold":
                    keys = set(body.get("keys") or mock.values)
                    mock.hold = mock.hold | keys if body.get("on") else mock.hold - keys
                elif path == "/api/defaults":
                    mock.values.update({c["key"]: c["default"] for c in mock.controls})
                elif path == "/api/presets":
                    known = {c["key"] for c in mock.controls if not c["trigger"]}
                    mock.presets.save(body.get("name"), {k: v for k, v in mock.values.items() if k in known}, known)
                elif path == "/api/presets/delete":
                    mock.presets.delete(str(body.get("name", "")))
                self.send(b'{"ok": true}')
            except Exception as e:
                self.send(json.dumps({"error": str(e)}).encode(), status=400)
    return H


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", type=int, default=19210)
    ap.add_argument("--lan", action="store_true", help="listen on every interface")
    a = ap.parse_args()
    mock = Mock()
    server = ThreadingHTTPServer(("0.0.0.0" if a.lan else "127.0.0.1", a.port), handler(mock))
    print("page mock on http://127.0.0.1:%d" % a.port)
    server.serve_forever()


if __name__ == "__main__":
    main()
