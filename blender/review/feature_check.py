#!/usr/bin/env python3
"""Feature check of the running Blender scene, from the shell: `make blender-check`.

    python3 blender/review/feature_check.py [--only vj_fog,vj_night] [--out FILE] [--wait SECONDS]

1. waits until the scene page (http 9210) answers and Syphon draws frames (a cold `make blender-open` takes minutes);
2. contract cross-check: every row of osc/CONTROLS.md whose Blender column is not "not used" exists on the page with
   the same range and default, and the page exposes nothing without a row;
3. sends every address once over udp 9201 and counts what the bridge applied;
4. starts the check inside Blender (POST /api/check, the same code the page's "Check all" runs), prints one row per
   control as it finishes and writes everything to a JSON file;
5. compares /api/state with the defaults afterwards.

Exit code 0: every control has an effect, no mismatch. 1: something failed the check. 2: Blender or the check did
not run. Standard library only.
"""
import argparse
import json
import os
import re
import socket
import struct
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONTRACT = os.path.join(ROOT, "osc", "CONTROLS.md")
BASE = "http://127.0.0.1:9210"
OSC = ("127.0.0.1", 9201)
NUMBER = r"-?\d+(?:\.\d+)?"


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
    """Address -> {range, default, blender, trigger} from the Addresses table of osc/CONTROLS.md."""
    rows = {}
    for line in open(CONTRACT, encoding="utf-8"):
        if not line.startswith("| `/vj/"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        rng, default, blender = cells[1], cells[2], cells[3]
        m = re.fullmatch(r"(%s)\.\.(%s)" % (NUMBER, NUMBER), rng)
        for address in re.findall(r"`(/vj/[a-z_0-9]+)`", cells[0]):
            rows[address] = {"range": [float(m.group(1)), float(m.group(2))] if m else None, "range_text": rng,
                             "default": float(default) if re.fullmatch(NUMBER, default) else None,
                             "trigger": rng == "trigger", "used": not blender.lower().startswith("not used")}
    return rows


INFO_KINDS = ("range", "range not numeric", "default", "trigger")   # until the contract is 0..1 on the wire: information, not failures


def cross_check(controls):
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
        if r["range"] is not None and (abs(r["range"][0] - c["min"]) > 1e-9 or abs(r["range"][1] - c["max"]) > 1e-9):
            out.append({"address": address, "kind": "range", "detail": "contract %s, page %g..%g" % (r["range_text"], c["min"], c["max"])})
        elif r["range"] is None and not r["trigger"]:
            out.append({"address": address, "kind": "range not numeric", "detail": "contract '%s', page %g..%g" % (r["range_text"], c["min"], c["max"])})
        if r["trigger"] != bool(c["trigger"]):
            out.append({"address": address, "kind": "trigger", "detail": "contract %s, page %s" % (r["trigger"], bool(c["trigger"]))})
        if r["default"] is not None and abs(r["default"] - c["default"]) > 1e-9:
            out.append({"address": address, "kind": "default", "detail": "contract %g, page %g" % (r["default"], c["default"])})
    for address in sorted(set(page) - set(rows)):
        out.append({"address": address, "kind": "no contract row", "detail": "page exposes it, osc/CONTROLS.md does not list it"})
    for address in sorted(a for a, r in rows.items() if not r["used"] and a in page):
        out.append({"address": address, "kind": "not used but on page", "detail": "contract says Blender does not use it"})
    for m in out:
        m["level"] = "info" if m["kind"] in INFO_KINDS else "fail"
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
    failing = [m for m in mismatches if m["level"] == "fail"]
    print("\ncontract: %d missing or extra address(es), %d range or default difference(s) as information" % (
        len(failing), len(mismatches) - len(failing)))
    for m in sorted(mismatches, key=lambda m: m["level"] != "fail"):
        print("  %-5s %-16s %-18s %s" % (m["level"], m["address"], m["kind"], m["detail"]))

    if not args.no_probe:
        report["osc_probe"] = probe = osc_probe(controls)
        print("\nudp 9201: sent %d, received %d, applied %d, errors %d%s" % (
            probe["sent"], probe["received"], probe["applied"], probe["errors"],
            ", not seen: " + " ".join(probe["missing"]) if probe["missing"] else ""))

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
    bad = counts.get("no effect", 0) + counts.get("error", 0) + len(failing)
    if result.get("state") != "done":
        return 2
    return 1 if bad or not report["state_equals_defaults"] else 0


if __name__ == "__main__":
    sys.exit(main())
