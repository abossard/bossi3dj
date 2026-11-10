#!/usr/bin/env python3
"""Talk to the Godot scene's control page over HTTP, the way a browser and `make status` do.

    python3 tools/godot_page_test.py

Starts the scene headless on the test ports (http 19211, udp 19202), checks that the page loads and
that its controls answer, runs the page's "Check all" and waits for the verdicts, then ends the
scene. Standard library only.
"""
import http.client
import json
import os
import subprocess
import sys
import time

GODOT = os.environ.get("GODOT", "/Applications/Godot_mono.app/Contents/MacOS/Godot")
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PORT = 19211
RUN_SECONDS = 150
failed = []


def call(method, path, body=None, headers=None, host=None):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=10)
    h = dict(headers if headers is not None else ({"Content-Type": "application/json"} if method == "POST" else {}))
    if host:
        h["Host"] = host
    c.request(method, path, body=json.dumps(body or {}) if method == "POST" else None, headers=h)
    r = c.getresponse()
    data = r.read()
    c.close()
    return r.status, data


def api(method, path, body=None):
    status, data = call(method, path, body)
    return status, json.loads(data)


def check(name, ok, detail=""):
    print("%s %s %s" % ("ok  " if ok else "FAIL", name, detail))
    if not ok:
        failed.append(name)


def state():
    return api("GET", "/api/state")[1]


def wait_for(cond, seconds, what):
    end = time.time() + seconds
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.2)
    return False


def main():
    proc = subprocess.Popen(
        [GODOT, "--headless", "--path", os.path.join(ROOT, "godot/colossus"), "--script", "res://tests/serve.gd", "--", str(RUN_SECONDS)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        up = wait_for(lambda: _up(), 90, "page")
        check("page answers on %d" % PORT, up)
        if not up:
            return
        status, html = call("GET", "/")
        check("GET / is the page", status == 200 and b"Colossus Control" in html and b"/api/state" in html, "%d bytes" % len(html))
        s = state()
        addresses = [c["address"] for c in s["controls"]]
        check("state lists every address", len(addresses) == 10 and "/vj/fog_height" in addresses, str(len(addresses)))
        check("state has Phase, shot, fps, OSC, Syphon",
              s["phase"] == "Approach" and "shot" in s and "fps" in s and "packets" in s["osc"] and s["syphon"]["server"] == "COLOSSUS_OUT")

        check("POST without JSON type is refused", call("POST", "/api/defaults", headers={"Content-Type": "text/plain"})[0] == 415)
        check("foreign Host is refused", call("GET", "/api/state", host="evil.example")[0] == 403)
        check("unknown path is 404", call("GET", "/nope")[0] == 404)
        check("bad address is 400", api("POST", "/api/set", {"values": {"/vj/nope": 1}})[0] == 400)

        api("POST", "/api/set", {"values": {"/vj/fog": 0.9}, "hold": True})
        time.sleep(0.5)
        s = state()
        check("set takes effect in the scene", abs(s["probe"]["fog_density"] - 0.010615) < 0.0003, str(s["probe"]["fog_density"]))
        check("set holds the value", s["values"]["/vj/fog"]["held"] and s["values"]["/vj/fog"]["source"] == "page")

        api("POST", "/api/set", {"values": {"/vj/cam": 3, "/vj/cam_auto": 0}, "hold": True})
        time.sleep(0.5)
        check("pin changes the director shot", state()["shot"] == 4 and state()["pinned"] == 4)
        api("POST", "/api/set", {"values": {"/vj/cam_auto": 1}})
        api("POST", "/api/phase", {"phase": "Climb"})
        check("phase jump reaches Climb", wait_for(lambda: state()["phase"] == "Climb", 10, "climb"))
        shocks = state()["probe"]["shocks"]
        api("POST", "/api/fire", {"address": "/vj/shock", "strength": 1.0})
        time.sleep(0.5)
        check("fire reaches the scene", state()["probe"]["shocks"] == shocks + 1)
        api("POST", "/api/sim", {"on": True, "bpm": 240, "shock_every": 0})
        beats = state()["probe"]["beats"]
        time.sleep(1.5)
        check("simulator beats", state()["probe"]["beats"] > beats + 2 and state()["sim"]["on"])
        api("POST", "/api/sim", {"on": False})
        api("POST", "/api/defaults")
        time.sleep(0.5)
        s = state()
        check("defaults restore values and release holds",
              s["values"]["/vj/fog"]["value"] == 0.35 and s["osc"]["holds"] == [])
        api("POST", "/api/phase", {"phase": "Approach"})
        wait_for(lambda: state()["phase"] == "Approach", 20, "approach")

        status, _ = api("POST", "/api/check")
        check("Check all starts", status == 200)
        check("a second Check all is refused while one runs", api("POST", "/api/check")[0] == 409)
        done = wait_for(lambda: not api("GET", "/api/check")[1]["running"], 120, "check")
        result = api("GET", "/api/check")[1]
        rows = result["results"]
        check("Check all finishes", done and len(rows) == 22, "%d rows" % len(rows))
        for r in rows:
            if r["verdict"] != "effect":
                check("control %s" % r["id"], False, "%s: %s" % (r["verdict"], r["detail"]))
        check("every control has an effect", result["summary"].get("effect") == len(rows) == 22, json.dumps(result["summary"]))
        check("status page carries the check summary", state()["check"]["summary"].get("effect") == 22)
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
    print("page test: %s" % ("passed" if not failed else "%d failed" % len(failed)))
    sys.exit(1 if failed else 0)


def _up():
    try:
        return call("GET", "/api/state")[0] == 200
    except OSError:
        return False


main()
