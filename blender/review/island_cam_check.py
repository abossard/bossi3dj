#!/usr/bin/env python3
"""Live check of /vj/cam in the open Blender scene: OSC cuts, page cuts, pixels per cut. Standard library only.

    python3 blender/review/island_cam_check.py [--cams 0,1,2,3,4,5,6,11,0] [--page 3,5] [--grab]

Sends /vj/cam N to the bridge on udp 9201 (sending only, nothing binds a port) and reads back the camera on air from the
page (/api/state "camera") and the scene preview (/api/frame.bmp, the composite the Syphon texture holds). Per cut: the
camera, vj_cam, the mean absolute luminance difference to the previous cut's frame and, as a floor, between two frames
of the same cut 0.5 s apart (the island's cameras drift). With --grab also the mean colour of one `CAM_OUT - Blender`
frame per cut (magicproj.py grab). Then the page's control: POST /api/set {"vj_cam": N}. The page is a touch (Takeover),
so it runs after the OSC cuts, and a run that finds vj_cam last set by a touch first waits /vj/takeover out. At the end vj_cam goes back to its first value through the page. Prints a Markdown table;
exit 0 when every row is ok. In the planet scene the expected result is the reverse: the camera never changes.
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "blender"))
import blender_osc_bridge as bridge  # noqa: E402

BASE = "http://127.0.0.1:9210"
SETTLE = 1.2           # s after a cut: the bridge tick, the frame change and the preview
W, H = 640, 360


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=15) as r:
        return r.read()


def post(path, body):
    req = urllib.request.Request(BASE + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=15).read()


def state():
    """A fresh snapshot: the page publishes only while it is polled."""
    get("/api/state")
    time.sleep(0.3)
    return json.loads(get("/api/state"))


def frame():
    """Luminance of the preview, every 4th pixel of every 4th row."""
    for _ in range(20):
        bmp = get("/api/frame.bmp")
        if len(bmp) >= 54 + W * H * 3:
            break
        time.sleep(0.5)
    else:
        return None
    px = bmp[54:54 + W * H * 3]
    return [0.0722 * px[i] + 0.7152 * px[i + 1] + 0.2126 * px[i + 2]
            for y in range(0, H, 4) for i in range(y * W * 3, (y + 1) * W * 3, 12)]


def diff(a, b):
    return round(sum(abs(x - y) for x, y in zip(a, b)) / len(a), 2) if a and b else None


def grab():
    run = subprocess.run([sys.executable, os.path.join(ROOT, "magic", "magicproj.py"), "grab", "--app", "Blender", "--server", "CAM_OUT"],
                         capture_output=True, text=True, timeout=120)
    try:
        g = json.loads(run.stdout)
        return g.get("mean_rgb") or g.get("mean")
    except ValueError:
        return "error"


def send(n):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.sendto(bridge.encode_message("/vj/cam", [float(n)]), ("127.0.0.1", bridge.PORT))
    s.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cams", default="0,1,2,3,4,5,6,11,0")
    ap.add_argument("--page", default="3,5")
    ap.add_argument("--grab", action="store_true")
    ap.add_argument("--planet", action="store_true", help="expect no cut (the planet ignores /vj/cam)")
    a = ap.parse_args()
    s0 = state()
    v0 = s0["values"].get("vj_cam")
    others = sorted({m[1] for m in s0["osc"]["log"] if m[2] == "/vj/cam"})
    print("start: camera %s, vj_cam %s, earlier /vj/cam senders %s" % (s0["camera"], v0, others or "none"), file=sys.stderr)
    if s0["osc"]["source"].get("vj_cam") in ("web", "artnet"):     # a touch may still own vj_cam (Takeover): OSC would be kept
        pause = float(s0["values"].get("vj_takeover", 20.0)) + 1.0
        print("vj_cam was last set by %s: waiting %.0f s for the Takeover pause" % (s0["osc"]["source"]["vj_cam"], pause), file=sys.stderr)
        time.sleep(pause)
    rows, prev, prev_cam = [], frame(), s0["camera"]

    def cut(how, n, do):
        nonlocal prev, prev_cam
        do(n)
        time.sleep(SETTLE)
        st = state()
        f1 = frame()
        time.sleep(0.5)
        f2 = frame()
        cam = st["camera"]
        want = s0["camera"] if a.planet else "CAM_%d" % min(n, 6)
        d, floor = diff(prev, f1), diff(f1, f2)
        changed = d is not None and floor is not None and (d > 2 * floor + 1.0)
        same_as_before = cam == prev_cam      # no cut asked for: the picture only drifts
        ok = cam == want and (a.planet or same_as_before or changed)
        g = grab() if a.grab else ""
        rows.append((how, n, st["values"].get("vj_cam"), cam, d, floor, g, "ok" if ok else "FAIL"))
        print("%-5s %-3s %-6s camera %-8s diff %-6s floor %-6s %s %s" % (how, n, st["values"].get("vj_cam"), cam, d, floor, g, rows[-1][-1]), file=sys.stderr, flush=True)
        prev, prev_cam = f1, cam

    for n in [int(c) for c in a.cams.split(",")]:
        cut("osc", n, send)
    for n in [int(c) for c in a.page.split(",")]:
        cut("page", n, lambda n: post("/api/set", {"vj_cam": float(n)}))
    if v0 is not None:
        post("/api/set", {"vj_cam": float(v0)})
    print("\n| Via | N | vj_cam | Camera on air | Diff to previous cut | Floor (same cut) | Syphon mean | Result |\n|---|---|---|---|---|---|---|---|")
    for r in rows:
        print("| %s | %s | %s | %s | %s | %s | %s | %s |" % r)
    return 0 if all(r[-1] == "ok" for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
