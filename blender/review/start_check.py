#!/usr/bin/env python3
"""Is the Blender scene in its show start state? Run by `make blender-open` after it opens the scene, or alone.

    python3 blender/review/start_check.py [--wait SECONDS]

Waits for the page (http 9210), then checks, one line each: runtime and bridge up, bridge on udp 9201, camera view in
Rendered shading, playing, values on their defaults (all through blender/review/health.py, GET /api/health: its
`problems` list is empty), Syphon frames moving, and pixels: mean and variance of the scene's preview frame (the same
composite the Syphon texture holds) and mean colour and lit share of one frame grabbed from `CAM_OUT - Blender`
(`magicproj.py grab`, the way Magic would get it). A black or flat frame fails. Exit 0: all ok, 1: something failed,
2: Blender did not answer. Standard library only.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = "http://127.0.0.1:9210"
BRIDGE_PORT = 9201
MIN_VARIANCE = 50.0      # luminance variance of a frame with a picture in it (a flat or black frame has none)
MIN_LIT = 0.05           # share of the grabbed frame that is not black


def get(path, timeout=15):
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        return r.read()


def frame_stats():
    """Mean and variance of the luminance of the 640x360 preview (BMP, 54 byte header, BGR rows)."""
    for _ in range(20):             # the first request only asks the sender for previews
        bmp = get("/api/frame.bmp")
        if len(bmp) >= 54 + 640 * 360 * 3:
            break
        time.sleep(0.5)
    else:
        return None
    px = bmp[54:54 + 640 * 360 * 3]
    lum = [0.0722 * px[i] + 0.7152 * px[i + 1] + 0.2126 * px[i + 2] for i in range(0, len(px), 3)]
    mean = sum(lum) / len(lum)
    return {"mean": round(mean, 2), "variance": round(sum((v - mean) ** 2 for v in lum) / len(lum), 1)}


def syphon_grab():
    run = subprocess.run([sys.executable, os.path.join(ROOT, "magic", "magicproj.py"), "grab", "--app", "Blender", "--server", "CAM_OUT"],
                         capture_output=True, text=True, timeout=120)
    try:
        return json.loads(run.stdout)
    except ValueError:
        return {"error": (run.stderr or run.stdout).strip()[-200:]}


def wait_page(limit):
    t0 = time.time()
    while time.time() - t0 < limit:
        try:
            s = json.loads(get("/api/state", 3))
            if s.get("controls"):
                return s
        except (OSError, ValueError):
            pass
        time.sleep(2.0)
    return None


def wait_started(limit):
    """health.py clean, playing and the Syphon frame counter moving: the runtime, view and sender finish a few seconds after
    the page, and the first draws wait for the shader compile."""
    t0, last = time.time(), None
    while True:
        h, s = json.loads(get("/api/health")), json.loads(get("/api/state"))
        frames = (s.get("syphon") or {}).get("frames")
        moving = frames is not None and last is not None and frames > last
        if ("problems" in h and not h["problems"] and s["playing"] and moving) or time.time() - t0 > limit:
            return h, s
        last = frames
        time.sleep(3.0)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--wait", type=float, default=600.0, help="seconds to wait for a cold start")
    args = ap.parse_args()
    print("waiting for the scene page (up to %.0f s) ..." % args.wait, flush=True)
    state = wait_page(args.wait)
    if state is None:
        print("no scene page on %s: make blender-open" % BASE)
        return 2
    health, state = wait_started(180.0)
    rows = []

    def row(name, ok, detail):
        rows.append(ok)
        print("%-4s %-24s %s" % ("ok" if ok else "FAIL", name, detail))

    row("scene", True, "%s, camera %s" % (state["scene"], state["camera"]))
    row("health.py", "problems" in health and not health["problems"], "; ".join(health.get("problems") or [health.get("error", "clean")]))
    row("runtime and playback", state["playing"] and "synthwave_tick" in health.get("tick_handlers", []), "playing %s, handlers %s" % (state["playing"], health.get("tick_handlers")))
    row("bridge", (state.get("osc") or {}).get("port") == BRIDGE_PORT, "udp %s" % (state.get("osc") or {}).get("port"))
    f0 = state["syphon"]["frames"] if state.get("syphon") else None
    time.sleep(2.0)
    f1 = (json.loads(get("/api/state")).get("syphon") or {}).get("frames")
    row("Syphon sender", f0 is not None and f1 is not None and f1 > f0, "frames %s -> %s in 2 s" % (f0, f1))
    t0 = time.time()                # EEVEE draws flat frames while it compiles the shaders: wait for a picture
    stats = frame_stats()
    while stats is not None and stats["variance"] <= MIN_VARIANCE and time.time() - t0 < 90.0:
        time.sleep(3.0)
        stats = frame_stats()
    row("preview pixels", stats is not None and stats["variance"] > MIN_VARIANCE, "luminance mean %(mean)s, variance %(variance)s" % stats if stats else "no preview frame")
    grab = syphon_grab()
    row("Syphon grab", "error" not in grab and grab.get("lit", 0) > MIN_LIT,
        grab.get("error") or "%s, mean rgb %s, lit %s" % (grab["size"], grab["mean_rgb"], grab["lit"]))
    ok = all(rows)
    print("start state: %s" % ("ready" if ok else "NOT ready"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
