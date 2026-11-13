#!/usr/bin/env python3
"""Talk to the live Blender scene's control page over HTTP, the way a browser (or a phone) does.

    python3 tools/blender_page_test.py [--check] [--base http://127.0.0.1:9210]

The scene must be open (`make blender-open`). Checks what the page is told (every Blender address has a control, grouped and
described from the contract, the Path Camera's named paths and targets, the start state), what the page may and may not do (JSON only,
loopback Host only), that sets, holds, the camera and the presets take effect in the scene, and leaves every value as it was.
`--check` also runs the page's "Check all" and waits for the verdicts (minutes). Standard library only.
"""
import argparse
import http.client
import json
import os
import sys
import time
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "blender", "scenes"))
sys.path.insert(0, os.path.join(ROOT, "osc"))
import contract  # noqa: E402
import page_model  # noqa: E402

failed = []
BASE = "http://127.0.0.1:9210"


def call(method, path, body=None, headers=None, host=None):
    u = urllib.parse.urlparse(BASE)
    c = http.client.HTTPConnection(u.hostname, u.port, timeout=15)
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
    # the page publishes snapshots only while it is polled: the first call after a pause can be stale
    api("GET", "/api/state")
    time.sleep(0.35)
    return api("GET", "/api/state")[1]


def wait_for(cond, seconds):
    end = time.time() + seconds
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.2)
    return False


def main():
    global BASE
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="also run Check all (minutes)")
    ap.add_argument("--base", default=BASE)
    a = ap.parse_args()
    BASE = a.base
    try:
        status, html = call("GET", "/")
    except OSError:
        print("no answer on %s: open the scene with `make blender-open`" % BASE)
        sys.exit(2)
    check("GET / is the page", status == 200 and b"Synthwave Control" in html and b"/api/state" in html, "%d bytes" % len(html))
    s = state()
    rows = contract.load()
    want = [page_model.key_of(r["address"]) for r in page_model.scene_rows(rows, s["kind"])]
    keys = [c["key"] for c in s["controls"]]
    check("a control for every address the %s reads" % s["kind"], sorted(keys) == sorted(want) and s["coverage"] == {"missing": [], "extra": []},
          "%d of %d" % (len(keys), len(want)))
    check("sections follow the manual groups", [x["title"] for x in s["sections"]] == [g for g in contract.GROUPS if g != "Godot only"],
          ", ".join(x["title"] for x in s["sections"]))
    check("every control has its sentence", all(c["plain"] for c in s["controls"]))
    by_key = {c["key"]: c for c in s["controls"]}
    check("the Path Camera comes first", s["path_camera"] == page_model.CAMERA, json.dumps(s["path_camera"]))
    check("path and target buttons carry the contract names",
          all(len(by_key[k]["stops"]) == by_key[k]["max"] - by_key[k]["min"] + 1 and all(x["name"] for x in by_key[k]["stops"]) for k in ("vj_path", "vj_target")))
    check("state has scene, Path Camera, fps, Syphon, OSC, no failed edge guard",
          s["scene"] and s["path_camera"] and "fps" in s and s["syphon"] is not None and s["osc"] is not None and (s.get("edge_guard") or {}).get("status") in (None, "present", "repaired", "not_applicable"),
          json.dumps({"scene": s["scene"], "path": s["values"].get("vj_path"), "target": s["values"].get("vj_target"), "fps": s["fps"], "edges": (s.get("edge_guard") or {}).get("status")}))
    art = (s.get("artnet") or {})
    check("the state has the Art-Net chip", art.get("chip", {}).get("text", "").startswith("Art-Net"), json.dumps(art.get("chip")))
    check("Art-Net listens on 6454 for the bridge's universe", (art.get("state") or {}).get("bound") is True and (art.get("state") or {}).get("port") == 6454,
          json.dumps({k: (art.get("state") or {}).get(k) for k in ("enabled", "bound", "port", "universe", "address", "error")}))
    frames = s["syphon"]["frames"]
    time.sleep(1.0)
    check("Syphon frames advance", state()["syphon"]["frames"] > frames)

    check("POST without a JSON type is refused", call("POST", "/api/defaults", headers={"Content-Type": "text/plain"})[0] == 415)
    if s["lan"]:
        check("LAN mode: a foreign Host is served (the phone calls the Mac by its address)", call("GET", "/api/state", host="evil.example")[0] == 200)
    else:
        check("a foreign Host is refused", call("GET", "/api/state", host="evil.example")[0] == 403)
    check("unknown path is 404", call("GET", "/nope")[0] == 404)

    before = {k: v for k, v in s["values"].items()}
    held_before = list(s["osc"]["hold"])
    try:
        api("POST", "/api/set", {"vj_fog": 0.8})
        time.sleep(0.4)
        s = state()
        check("a set reaches the scene", abs(s["values"]["vj_fog"] - 0.8) < 1e-6 and s["osc"]["source"]["vj_fog"] == "web", str(s["values"]["vj_fog"]))
        api("POST", "/api/hold", {"keys": ["vj_fog"], "on": True})
        time.sleep(0.3)
        check("hold shows in the state", "vj_fog" in state()["osc"]["hold"])
        api("POST", "/api/hold", {"keys": ["vj_fog"], "on": False})
        time.sleep(0.3)
        check("release shows in the state", "vj_fog" not in state()["osc"]["hold"])

        api("POST", "/api/set", {"vj_path": 2, "vj_target": 4})
        check("a path and a target button reach the scene", wait_for(lambda: (state()["values"]["vj_path"], state()["values"]["vj_target"]) == (2, 4), 5),
              json.dumps([state()["values"]["vj_path"], state()["values"]["vj_target"]]))
        api("POST", "/api/set", {"vj_path": before["vj_path"], "vj_target": before["vj_target"]})

        name = "page-test-%d" % int(time.time())
        r = api("POST", "/api/presets", {"name": name})
        check("save a preset", r[0] == 200)
        saved = api("GET", "/api/presets")[1]["presets"].get(name)
        check("the preset holds the current values and no trigger", saved is not None and "vj_fog" in saved["values"] and "vj_shock" not in saved["values"])
        api("POST", "/api/set", {"vj_fog": 0.1})
        time.sleep(0.3)
        api("POST", "/api/set", saved["values"])
        time.sleep(0.4)
        check("recalling it sets the values again", abs(state()["values"]["vj_fog"] - 0.8) < 1e-6, str(state()["values"]["vj_fog"]))
        check("deleting an unknown preset is refused", api("POST", "/api/presets/delete", {"name": "no such preset"})[0] == 400)
        api("POST", "/api/presets/delete", {"name": name})
        check("delete a preset", name not in api("GET", "/api/presets")[1]["presets"])

        api("POST", "/api/hold", {"on": True})
        time.sleep(0.3)
        check("Hold all holds every control", len(state()["osc"]["hold"]) == len(keys))
        api("POST", "/api/hold", {"on": False})
        time.sleep(0.3)
        check("Release all clears the holds", state()["osc"]["hold"] == [])
    finally:
        api("POST", "/api/defaults")
        time.sleep(0.4)
        api("POST", "/api/hold", {"on": False})
        if held_before:
            api("POST", "/api/hold", {"keys": held_before, "on": True})

    if a.check:
        check("Check all starts", api("POST", "/api/check")[0] == 200)
        done = wait_for(lambda: api("GET", "/api/check")[1].get("state") in ("done", "failed", "aborted"), 1800)
        result = api("GET", "/api/check")[1]
        counts = result.get("counts", {})
        check("Check all finishes", done and result.get("state") == "done", json.dumps(counts))
        check("no control errored", not counts.get("error"), json.dumps(counts))
        check("defaults were restored", result.get("defaults_restored") is True)
    print("page test: %s" % ("passed" if not failed else "%d failed" % len(failed)))
    sys.exit(1 if failed else 0)


main()
