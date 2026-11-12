#!/usr/bin/env python3
"""What is running right now, as JSON: Blender, its OSC bridge and Syphon sender, Godot, Magic,
the relay, the Blender lock, and the machine load that makes fps numbers trustworthy or not.

    python3 tools/vj_status.py

Reads only: the Blender scene's and the Godot scene's own state pages (http 9210, 9211), `pgrep`,
`lsof` (who listens on udp 6454, Art-Net), the lock file, `uptime`.
"""
import json
import os
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blender_lock  # noqa: E402

LOAD_LIMIT = 10.0   # above this, fps readings were noise in every measured session


def running(pattern):
    out = subprocess.run(["pgrep", "-lf", pattern], capture_output=True, text=True).stdout
    return [line.split(" ", 1)[0] for line in out.splitlines() if line]


ARTNET_PORT = 6454


def udp_listeners(port):
    """[{command, pid}] of the processes bound to a udp port (lsof; empty when nothing is, or lsof says nothing)."""
    out = subprocess.run(["lsof", "-nP", "-iUDP:%d" % port], capture_output=True, text=True).stdout
    return [{"command": f[0], "pid": f[1]} for f in (line.split() for line in out.splitlines()[1:]) if len(f) > 1]


def blender_state():
    try:
        with urllib.request.urlopen("http://127.0.0.1:9210/api/state", timeout=1.5) as r:
            s = json.load(r)
    except (OSError, ValueError):
        return None
    osc = s.get("osc") or {}
    return {"scene": s.get("scene"), "camera": s.get("camera"), "fps": s.get("fps"), "playing": s.get("playing"),
            "syphon": s.get("syphon"), "osc_received": osc.get("received"), "osc_hold": osc.get("hold"),
            "artnet": (s.get("artnet") or {}).get("state")}


def godot_state():
    port = os.environ.get("GODOT_PAGE_PORT", "9211")
    try:
        with urllib.request.urlopen("http://127.0.0.1:%s/api/state" % port, timeout=1.5) as r:
            s = json.load(r)
    except (OSError, ValueError):
        return None
    osc = s.get("osc") or {}
    check = (s.get("check") or {}).get("summary") or None
    return {"phase": s.get("phase"), "shot": s.get("shot"), "pinned": s.get("pinned"), "fps": s.get("fps"),
            "frame_ms": s.get("frame_ms"), "display": s.get("display"), "syphon": s.get("syphon"),
            "osc_received": osc.get("packets"), "osc_live": osc.get("live"), "osc_hold": osc.get("holds"),
            "check": check}


def main():
    load = os.getloadavg()[0]
    lock = blender_lock.read_lock()
    status = {
        "blender_pids": running("Blender.app/Contents/MacOS/Blender"),
        "blender_scene": blender_state(),
        "blender_lock": lock and {"session": lock["session"], "cwd": lock.get("cwd")},
        "godot_pids": running("Godot_mono.app/Contents/MacOS/Godot"),
        "godot_scene": godot_state(),
        "magic_pids": running("Magic.*\\.app/Contents/MacOS"),
        "relay_pids": running("osc/lab.py"),
        "qlc_pids": running("QLC\\+.app/Contents/MacOS"),
        "artnet_listeners": udp_listeners(ARTNET_PORT),
        "load_1m": round(load, 1),
        "fps_trustworthy": load < LOAD_LIMIT,
    }
    notes = []
    if len(status["blender_pids"]) > 1:
        notes.append("more than one Blender is running: only one may run (it halves fps and collides on udp 9201)")
    if status["blender_pids"] and status["blender_scene"] is None:
        notes.append("Blender runs without the scene runtime (no answer on http 9210): open it with `make blender-open`")
    if status["blender_pids"] and status["godot_pids"]:
        notes.append("Blender and Godot share the GPU: fps numbers of either are context, not a verdict")
    if status["godot_pids"] and status["godot_scene"] is None:
        notes.append("Godot runs without an answer on http 9211 (a headless test run, or an older scene)")
    art = status["artnet_listeners"]
    if status["blender_pids"] and not any(l["command"].startswith("Blender") for l in art):
        notes.append("Blender runs but nothing of it listens on udp 6454 (Art-Net): opened before the Art-Net input, or the bind failed (docs/artnet-qlc.md)")
    if status["qlc_pids"] and any(l["command"].startswith("Blender") for l in art) and any(l["command"].startswith("QLC") for l in art):
        notes.append("QLC+ and Blender both listen on udp 6454: a unicast frame reaches only one of them, send Art-Net to the broadcast address")
    if status["qlc_pids"] and not art:
        notes.append("QLC+ runs and nothing listens on udp 6454: its Art-Net output is not set (Inputs/Outputs tab)")
    if not status["fps_trustworthy"]:
        notes.append("load %.0f: do not record fps numbers now" % load)
    status["notes"] = notes
    print(json.dumps(status, indent=1))


main()
