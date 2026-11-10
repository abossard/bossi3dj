#!/usr/bin/env python3
"""Frame rate and process time of the live Colossus Scene across one Arc, from its control page.

    python3 tools/godot_frame_log.py [--dwell 15] [--every 0.5] [--port 9211]

Releases the page's holds, jumps Approach, Climb, Fall (Reset follows by itself) and samples
GET /api/state, `fps` (Engine fps, a 1 s window) and `frame_ms` (CPU process time, not GPU time),
for `--dwell` seconds in each Phase. Prints min, median, p95 and max per Phase as JSON. Numbers are
context only: `make status` says whether anything else loads the machine. Standard library only.
"""
import argparse
import json
import statistics
import time
import urllib.request

PHASES = ["Approach", "Climb", "Fall", "Reset"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dwell", type=float, default=15.0)
    ap.add_argument("--every", type=float, default=0.5)
    ap.add_argument("--port", type=int, default=9211)
    a = ap.parse_args()
    base = "http://127.0.0.1:%d" % a.port

    def get(path):
        return json.load(urllib.request.urlopen(base + path, timeout=5))

    def post(path, body):
        req = urllib.request.Request(base + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        return json.load(urllib.request.urlopen(req, timeout=5))

    post("/api/hold", {"addresses": [], "on": False})
    post("/api/defaults", {})
    out = {}
    for p in PHASES[:3] + ["Reset"]:
        if p != "Reset":
            post("/api/phase", {"phase": p})
        end = time.time() + a.dwell
        fps, ms, seen = [], [], set()
        while time.time() < end:
            s = get("/api/state")
            fps.append(s["fps"])
            ms.append(s["frame_ms"])
            seen.add(s["phase"])
            time.sleep(a.every)
        q = lambda v, f: sorted(v)[min(len(v) - 1, int(f * len(v)))]  # noqa: E731
        out[p] = {"samples": len(fps), "phases_seen": sorted(seen),
                  "fps": {"min": min(fps), "median": statistics.median(fps), "p05": q(fps, 0.05), "max": max(fps)},
                  "frame_ms": {"median": statistics.median(ms), "p95": q(ms, 0.95), "max": max(ms)}}
    post("/api/phase", {"phase": "Approach"})
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
