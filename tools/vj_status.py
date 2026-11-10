#!/usr/bin/env python3
"""What is running right now, as JSON: Blender, its OSC bridge and Syphon sender, Godot, Magic,
the relay, the Blender lock, and the machine load that makes fps numbers trustworthy or not.

    python3 tools/vj_status.py

Reads only: the Blender scene's own state page (http 9210), `pgrep`, the lock file, `uptime`.
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


def blender_state():
    try:
        with urllib.request.urlopen("http://127.0.0.1:9210/api/state", timeout=1.5) as r:
            s = json.load(r)
    except (OSError, ValueError):
        return None
    osc = s.get("osc") or {}
    return {"scene": s.get("scene"), "camera": s.get("camera"), "fps": s.get("fps"), "playing": s.get("playing"),
            "syphon": s.get("syphon"), "osc_received": osc.get("received"), "osc_hold": osc.get("hold")}


def main():
    load = os.getloadavg()[0]
    lock = blender_lock.read_lock()
    status = {
        "blender_pids": running("Blender.app/Contents/MacOS/Blender"),
        "blender_scene": blender_state(),
        "blender_lock": lock and {"session": lock["session"], "cwd": lock.get("cwd")},
        "godot_pids": running("Godot_mono.app/Contents/MacOS/Godot"),
        "magic_pids": running("Magic.*\\.app/Contents/MacOS"),
        "relay_pids": running("osc/lab.py"),
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
    if not status["fps_trustworthy"]:
        notes.append("load %.0f: do not record fps numbers now" % load)
    status["notes"] = notes
    print(json.dumps(status, indent=1))


main()
