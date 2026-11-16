#!/usr/bin/env python3
"""Is the Blender scene in its show start state? Run by `make blender-open` after it opens the scene, or alone.

    python3 blender/review/start_check.py [--wait SECONDS]

Waits for the page (http 9210), then checks, one line each: runtime and bridge up, bridge on udp 9201, camera view in
Rendered shading, playing, the GPU terrain shown with its height map, values on their defaults (all through blender/review/health.py, GET /api/health: its
`problems` list is empty), Syphon frames moving, and pixels: mean and variance of the scene's preview frame (the same
composite the Syphon texture holds) and mean colour and lit share of one frame grabbed from `CAM_OUT - Blender`
(`magicproj.py grab`, the way Magic would get it). A black or flat frame fails. Exit 0: all ok, 1: something failed,
2: Blender did not answer, 3: only the drawing is stuck (issue #18, once after a rebuild): every drawing row fails,
the rest passes, the Syphon frame counter still stands STUCK_WAIT s later and the screen is not locked. A minimized
window, another Space or a sleeping display look the same and a reopen does not fix those, so nothing is killed: it
prints what to check and how to reopen. Standard library only.
"""
import argparse
import json
import os
import plistlib
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = "http://127.0.0.1:9210"
BRIDGE_PORT = 9201
MIN_VARIANCE = 50.0      # luminance variance of a frame with a picture in it (a flat or black frame has none)
MIN_LIT = 0.05           # share of the grabbed frame that is not black
SENDER, PREVIEW, GRAB = DRAWING = ("Syphon sender", "preview pixels", "Syphon grab")   # a dead window fails all
STUCK_WAIT = 10.0       # s: the counter's second sample before calling the drawing stuck (a GPU stall passes by then)


def verdict(rows, still_stuck=True, locked=False):
    """Exit code from the rows {name: ok}: 0 all ok; 3 every drawing row failed and nothing else, the counter still
    stuck after STUCK_WAIT and the screen not locked; 1 anything else."""
    failed = {n for n, ok in rows.items() if not ok}
    if not failed:
        return 0
    return 3 if failed == set(DRAWING) and still_stuck and not locked else 1


def screen_locked():
    """True when the screen is locked or this user's session is not on the console (ioreg's IOConsoleUsers)."""
    try:
        out = subprocess.run(["ioreg", "-n", "Root", "-d1", "-a"], capture_output=True, timeout=10).stdout
        users = plistlib.loads(out).get("IOConsoleUsers", [])
    except (OSError, ValueError, subprocess.SubprocessError):
        return False
    return any(u.get("CGSSessionScreenIsLocked") or not u.get("kCGSSessionOnConsoleKey", True) for u in users)


def counter():
    return (json.loads(get("/api/state")).get("syphon") or {}).get("frames")


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
    """health.py clean, playing and the Syphon frame counter moving: the runtime, view and sender finish a few seconds
    after the page (the terrain's height map loads or bakes first), and the first draws wait for the shader compile."""
    t0, last = time.time(), None
    while True:
        h, s = json.loads(get("/api/health")), json.loads(get("/api/state"))
        frames = (s.get("syphon") or {}).get("frames")
        moving = frames is not None and last is not None and frames > last
        if (not h.get("problems", ["no health"]) and s["playing"] and moving) or time.time() - t0 > limit:
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
    health, state = wait_started(300.0)
    rows = {}

    def row(name, ok, detail):
        rows[name] = bool(ok)
        print("%-4s %-24s %s" % ("ok" if ok else "FAIL", name, detail))

    row("scene", True, "%s, camera %s" % (state["scene"], state["camera"]))
    row("health.py", "problems" in health and not health["problems"], "; ".join(health.get("problems") or [health.get("error", "clean")]))
    row("runtime and playback", state["playing"] and "synthwave_tick" in health.get("tick_handlers", []), "playing %s, handlers %s" % (state["playing"], health.get("tick_handlers")))
    row("bridge", (state.get("osc") or {}).get("port") == BRIDGE_PORT, "udp %s" % (state.get("osc") or {}).get("port"))
    terrain = health.get("terrain")
    if terrain is None:
        row("terrain", True, "no planet in this scene")
    else:
        row("terrain", terrain["shown"], "GPU terrain %s" % terrain)
    f0 = state["syphon"]["frames"] if state.get("syphon") else None
    time.sleep(2.0)
    f1 = counter()
    row(SENDER, f0 is not None and f1 is not None and f1 > f0, "frames %s -> %s in 2 s" % (f0, f1))
    t0 = time.time()                # EEVEE draws flat frames while it compiles the shaders: wait for a picture
    stats = frame_stats()
    while stats is not None and stats["variance"] <= MIN_VARIANCE and time.time() - t0 < 90.0:
        time.sleep(3.0)
        stats = frame_stats()
    row(PREVIEW, stats is not None and stats["variance"] > MIN_VARIANCE, "luminance mean %(mean)s, variance %(variance)s" % stats if stats else "no preview frame")
    grab = syphon_grab()
    row(GRAB, "error" not in grab and grab.get("lit", 0) > MIN_LIT,
        grab.get("error") or "%s, mean rgb %s, lit %s" % (grab["size"], grab["mean_rgb"], grab["lit"]))
    still, locked = True, False
    if {n for n, ok in rows.items() if not ok} == set(DRAWING):
        f2 = counter()
        time.sleep(STUCK_WAIT)
        f3 = counter()
        still, locked = f2 is None or f3 is None or f3 <= f2, screen_locked()
        print("     Syphon counter %s -> %s in %.0f s more%s" % (f2, f3, STUCK_WAIT,
                                                                ", screen locked" if locked else ""))
    code = verdict(rows, still, locked)
    print("start state: %s" % ("ready" if code == 0 else "NOT ready"))
    if code == 3:
        print("the Blender window does not draw. If it is minimized, on another Space or the display sleeps, "
              "bring it to the front. Otherwise: make blender-kill && make blender-open (issue #18)")
    return code


if __name__ == "__main__":
    sys.exit(main())
