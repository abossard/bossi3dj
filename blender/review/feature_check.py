#!/usr/bin/env python3
"""Feature check of the running Blender scene, from the shell: `make blender-check`.

    python3 blender/review/feature_check.py [--only vj_fog,vj_night] [--out FILE] [--wait SECONDS]

1. waits until the scene page (http 9210) answers and Syphon draws frames (a cold `make blender-open` takes minutes);
2. contract cross-check: every row of osc/contract.json with a Blender column exists on the page with the same scene
   range, the scene value of its wire default and the same trigger flag, and the page exposes nothing without a row;
3. sends every address once over udp 9201 and counts what the bridge applied, then the six messages of
   docs/handover/osc-contract.md with their expected property values (bridge_check.py);
4. starts the check inside Blender (POST /api/check, the same code the page's "Check all" runs), prints one row per
   control as it finishes and writes everything to a JSON file;
5. compares /api/state with the defaults afterwards.

Exit code 0: every control has an effect, no mismatch. 1: something failed the check. 2: Blender or the check did
not run. Standard library only.
"""
import argparse
import json
import os
import socket
import struct
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "osc"))
import contract  # noqa: E402
BASE = "http://127.0.0.1:9210"
OSC = ("127.0.0.1", 9201)


def http(path, body=None, timeout=10):
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def pad(b):
    return b + b"\0" * (-len(b) % 4)


def osc_message(address, value):
    return pad(address.encode() + b"\0") + pad(b",f\0") + struct.pack(">f", value)


def wait_ready(limit):
    """Page answers with controls, and the Syphon frame counter moves."""
    t0, last = time.time(), None
    while time.time() - t0 < limit:
        try:
            s = http("/api/state", timeout=3)
            frames = (s.get("syphon") or {}).get("frames")
            if s.get("controls") and frames is not None:
                if last is not None and frames > last:
                    return s
                last = frames
        except (OSError, ValueError):
            pass
        time.sleep(2.0)
    return None


def contract_rows():
    """Address -> what the page must show for it, from osc/contract.json (the one source of the table in CONTROLS.md):
    kind, the scene range, the scene value of the wire default, and whether Blender uses the row at all."""
    rows = {}
    for r in contract.load():
        scene = r.get("blender")
        rows[r["address"]] = {"kind": r["kind"], "used": scene is not None, "wire": [r["min"], r["max"]],
                              "range": None if scene is None or r["kind"] != "float" else [scene["min"], scene["max"]],
                              "default": None if scene is None else contract.scene_value(r, "blender", r["default"])}
    return rows


def cross_check(controls):
    """Every difference between the contract rows and the page's controls is a failure: a missing or extra address,
    a range, a default that is not the wire default's scene value (half a percent of the range of slack, as in
    osc/tests/test_contract.py), a trigger that is not one. An index (`/vj/cam`) starts at the wire minimum and
    stops at or below the wire maximum: the page ends it at the scene's last camera."""
    page = {"/" + c["key"].replace("_", "/", 1): c for c in controls}
    rows = contract_rows()
    out = []
    for address, r in sorted(rows.items()):
        if not r["used"]:
            continue
        c = page.get(address)
        if c is None:
            out.append({"address": address, "kind": "missing on page", "detail": "contract row, no control"})
            continue
        span = c["max"] - c["min"]
        if r["kind"] == "float" and (abs(r["range"][0] - c["min"]) > 1e-9 or abs(r["range"][1] - c["max"]) > 1e-9):
            out.append({"address": address, "kind": "range", "detail": "contract %g..%g, page %g..%g" % (*r["range"], c["min"], c["max"])})
        if r["kind"] == "int" and not (c["min"] == r["wire"][0] and c["max"] <= r["wire"][1]):
            out.append({"address": address, "kind": "range", "detail": "contract index %g..%g, page %g..%g" % (*r["wire"], c["min"], c["max"])})
        if r["kind"] == "trigger" and (not c["trigger"] or abs(c["max"] - r["wire"][1]) > 1e-9):
            out.append({"address": address, "kind": "trigger", "detail": "contract trigger up to %g, page %s up to %g" % (
                r["wire"][1], "trigger" if c["trigger"] else "not a trigger", c["max"])})
        if r["kind"] != "trigger" and c["trigger"]:
            out.append({"address": address, "kind": "trigger", "detail": "page has a trigger, contract says %s" % r["kind"]})
        if abs(r["default"] - c["default"]) > 0.005 * span:
            out.append({"address": address, "kind": "default", "detail": "contract wire default is %g in the scene, page %g" % (r["default"], c["default"])})
    for address in sorted(set(page) - {a for a, r in rows.items() if r["used"]}):
        out.append({"address": address, "kind": "not in contract" if address not in rows else "not used but on page",
                    "detail": "page exposes it, osc/contract.json has no Blender column for it"})
    return out


def osc_probe(controls):
    """Every address once, with its default, 15 ms apart; counts what the bridge received and applied."""
    before = http("/api/state")["osc"]
    time.sleep(0.4)
    before = http("/api/state")["osc"]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for c in controls:
        sock.sendto(osc_message("/" + c["key"].replace("_", "/", 1), float(c["default"])), OSC)
        time.sleep(0.015)
    time.sleep(0.6)
    http("/api/state")
    time.sleep(0.3)
    after = http("/api/state")["osc"]
    seen = {a for a, st in after["addresses"].items() if st["n"] > (before["addresses"].get(a, {"n": 0})["n"])}
    missing = sorted(set("/" + c["key"].replace("_", "/", 1) for c in controls) - seen)
    return {"sent": len(controls), "received": after["received"] - before["received"],
            "applied": after["applied"] - before["applied"], "missing": missing, "errors": after["errors"] - before["errors"]}


BRIDGE_MESSAGES = (("/vj/intensity", 0.5), ("/vj/fog_height", 0.42), ("/vj/fog_scale", 0.26), ("/vj/cam", 12), ("/vj/shock", 1.4),
                   ("/vj/cam_auto", 0))     # docs/handover/osc-contract.md: the live check of the 0..1 wire


def bridge_check(controls):
    """The six messages of docs/handover/osc-contract.md over udp 9201, each read back from the scene: the property is the
    contract's scene value of the wire value (kept inside the property's own range), `/vj/cam 12` cuts to the
    highest CAM_k of the scene, `/vj/cam_auto` writes no property and counts in the bridge's `ignored`.
    Returns one row per message; the scene is put back on its defaults."""
    page = {c["key"]: c for c in controls}
    rows = contract.by_address()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    out = []
    for address, wire in BRIDGE_MESSAGES:
        key = "vj_" + address[len("/vj/"):]
        before = http("/api/state")
        sock.sendto(osc_message(address, float(wire)), OSC)
        time.sleep(0.5)
        http("/api/state")
        time.sleep(0.3)
        after = http("/api/state")
        row = {"address": address, "wire": wire}
        if key in page:
            want = contract.scene_value(rows[address], "blender", wire)
            want = min(max(want, page[key]["min"]), page[key]["max"])
            got = after["values"].get(key)
            row.update(property=key, expected=round(want, 4), got=None if got is None else round(got, 4),
                       ok=got is not None and abs(got - want) < 1e-3)
            if address == "/vj/cam":
                row["camera"] = after["camera"]
                row["ok"] = row["ok"] and after["camera"] == "CAM_%d" % int(want)
        else:
            ignored = after["osc"]["ignored"] - before["osc"]["ignored"]
            row.update(property=None, ignored=ignored, ok=key not in after["values"] and ignored == 1)
        out.append(row)
    http("/api/defaults", {})
    time.sleep(0.5)
    return out


def fmt_row(r):
    eff = "%.3f" % r["effect_mad"] if "effect_mad" in r else "-"
    bias = "%.3f" % r["effect_bias"] if "effect_bias" in r else "-"
    ratio = ("%gx" % r["ratio"]) if "ratio" in r else "-"
    return "%-16s %-12s %-9s mad %8s bias %7s  %7s floor  cam %-3s %s" % (
        r["key"], "%g..%g" % (r["min"], r["max"]), r["verdict"], eff, bias, ratio, r.get("cam", "-"), r.get("note", ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", default="", help="comma separated vj_ keys, default every control")
    ap.add_argument("--out", help="JSON file (default blender/review/out/feature_check_<scene>.json)")
    ap.add_argument("--wait", type=float, default=900.0, help="seconds to wait for a cold start")
    ap.add_argument("--no-fallback", action="store_true", help="do not look through other cameras when a control shows nothing")
    ap.add_argument("--no-probe", action="store_true", help="skip the udp 9201 probe")
    args = ap.parse_args()

    print("waiting for the scene page and Syphon frames (up to %.0f s) ..." % args.wait, flush=True)
    state = wait_ready(args.wait)
    if state is None:
        print("Blender is not answering on %s with a drawing Syphon sender: make blender-open, camera view, wait" % BASE)
        return 2
    controls = state["controls"]
    scene = state["scene"]
    print("scene %s, camera %s, %d controls, %.1f fps" % (scene, state["camera"], len(controls), state["fps"]))
    out_path = os.path.abspath(args.out) if args.out else os.path.join(ROOT, "blender", "review", "out", "feature_check_%s.json" % scene)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    report = {"scene": scene, "time": time.strftime("%Y-%m-%d %H:%M:%S"), "controls": len(controls)}

    report["contract"] = mismatches = cross_check(controls)
    print("\ncontract: %d mismatch(es)" % len(mismatches))
    for m in mismatches:
        print("  %-16s %-18s %s" % (m["address"], m["kind"], m["detail"]))

    if not args.no_probe:
        report["osc_probe"] = probe = osc_probe(controls)
        print("\nudp 9201: sent %d, received %d, applied %d, errors %d%s" % (
            probe["sent"], probe["received"], probe["applied"], probe["errors"],
            ", not seen: " + " ".join(probe["missing"]) if probe["missing"] else ""))

        report["bridge_check"] = bridge = bridge_check(controls)
        print("\nbridge, six messages: %d of %d as expected" % (sum(1 for b in bridge if b["ok"]), len(bridge)))
        for b in bridge:
            print("  %-3s %-14s %-6g %s" % ("ok" if b["ok"] else "BAD", b["address"], b["wire"], {k: v for k, v in b.items() if k not in ("address", "wire", "ok")}))

    frames_dir = os.path.join(os.path.dirname(out_path), "feature_check_%s_frames" % scene)
    http("/api/check", {"only": [k for k in args.only.split(",") if k], "frames_dir": frames_dir,
                              "fallback": not args.no_fallback})
    print("\ncheck running (page: %s, press Abort there or Ctrl-C here to stop)" % BASE, flush=True)
    shown, result = 0, {}
    try:
        while True:
            time.sleep(2.0)
            result = http("/api/check")
            for r in result.get("rows", [])[shown:]:
                print(fmt_row(r), flush=True)
            shown = len(result.get("rows", []))
            if result.get("state") in ("done", "aborted", "failed"):
                break
            if result.get("state") == "idle" and shown == 0 and time.time() % 60 < 2.0:
                print("  (starting)", flush=True)
    except KeyboardInterrupt:
        http("/api/check/abort", {})
        time.sleep(3.0)
        result = http("/api/check")
    report["check"] = result

    time.sleep(0.5)
    http("/api/state")
    time.sleep(0.4)
    after = http("/api/state")
    off = {c["key"]: [after["values"].get(c["key"]), c["default"]] for c in controls
           if abs(after["values"].get(c["key"], 1e9) - c["default"]) > 1e-6}
    report["state_equals_defaults"] = not off
    report["off_default"] = off
    report["holds_released"] = not (after.get("osc") or {}).get("hold")

    counts = result.get("counts", {})
    print("\n%s: %s; noise floor %s; defaults restored: %s; holds released: %s" % (
        result.get("state"), ", ".join("%d %s" % (n, k) for k, n in sorted(counts.items())) or "no rows",
        result.get("noise_floor"), report["state_equals_defaults"], report["holds_released"]))
    if result.get("error"):
        print(result["error"])
    with open(out_path, "w") as f:
        json.dump(report, f, indent=1)
    print("written", out_path)
    bad = counts.get("no effect", 0) + counts.get("error", 0) + len(mismatches) + sum(1 for b in report.get("bridge_check", []) if not b["ok"])
    if result.get("state") != "done":
        return 2
    return 1 if bad or not report["state_equals_defaults"] else 0


if __name__ == "__main__":
    sys.exit(main())
