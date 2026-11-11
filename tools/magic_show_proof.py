#!/usr/bin/env python3
"""Numbers for the live chain Magic -> Blender -> Magic. Run with the scene open (`make blender-open`) and show.magic open in Magic.

    python3 tools/magic_show_proof.py osc                       every address of the contract reached the bridge
    python3 tools/magic_show_proof.py picture [--app NAME]      Magic's published frame holds Blender's picture, upright
    python3 tools/magic_show_proof.py global GLOBAL VALUE       set a Global in a copy of the project, load it, read the scene value, load the project back

`osc`: reads the page's OSC state (http 9210) and lists every contract address with its count; exit 1 when one never arrived.
`picture`: grabs `CAM_OUT - Blender` and Magic's `MAGIC_OUT` (magicproj.py grab), reduces both to a 16x9 grid of luma and prints the
correlation upright and with the rows reversed, and the mean difference. The camera is held on the still shot 0 meanwhile and put back.
`global`: `magicproj.py set --value`, `load` (it replaces the project open in Magic: say so first), waits, prints the scene value of the
control that follows the Global, then loads the original again. Standard library only.
"""
import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "osc"))
sys.path.insert(0, os.path.join(ROOT, "magic"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import contract  # noqa: E402
import magic_manual  # noqa: E402
import png_stats  # noqa: E402

BASE = "http://127.0.0.1:9210"
MAGICPROJ = os.path.join(ROOT, "magic", "magicproj.py")
SHOW = os.path.join(ROOT, "magic", "projects", "show.magic")


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=15) as r:
        return json.loads(r.read())


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10).read()


def state():
    get("/api/state")
    time.sleep(0.4)
    return get("/api/state")


def cmd_osc(a):
    s = state()
    seen = (s.get("osc") or {}).get("addresses", {})
    rows = contract.load()
    missing = []
    for r in rows:
        st = seen.get(r["address"])
        print("%-18s %s" % (r["address"], "n=%d %.1f Hz from %s" % (st["n"], st["hz"], st["src"]) if st else "NEVER"))
        if not st:
            missing.append(r["address"])
    print("%d of %d addresses reached the bridge; %d received in all" % (len(rows) - len(missing), len(rows), s["osc"]["received"]))
    return 1 if missing else 0


def grab(app, server, out):
    run = subprocess.run([sys.executable, MAGICPROJ, "grab", "--app", app, "--server", server, "--out", out, "--wait", "10"], capture_output=True, text=True, timeout=180)
    try:
        return json.loads(run.stdout)
    except ValueError:
        return {"error": (run.stderr or run.stdout).strip()[-300:]}


def grid(path, cols=16, rows=9):
    """Mean luma of a cols x rows grid, rows top first as the file stores them."""
    w, h, ch, px = png_stats.read_png(path)
    out = []
    for j in range(rows):
        row = []
        for i in range(cols):
            tot = n = 0
            for y in range(j * h // rows, (j + 1) * h // rows, 8):
                line = px[y]
                for x in range(i * w // cols, (i + 1) * w // cols, 8):
                    tot += 0.2126 * line[x * ch] + 0.7152 * line[x * ch + 1] + 0.0722 * line[x * ch + 2]
                    n += 1
            row.append(tot / n)
        out.append(row)
    return out


def corr(a, b):
    fa, fb = [v for r in a for v in r], [v for r in b for v in r]
    ma, mb = sum(fa) / len(fa), sum(fb) / len(fb)
    num = sum((x - ma) * (y - mb) for x, y in zip(fa, fb))
    den = math.sqrt(sum((x - ma) ** 2 for x in fa) * sum((y - mb) ** 2 for y in fb))
    return num / den if den else 0.0


def cmd_picture(a):
    out = tempfile.mkdtemp(prefix="magic-proof-")
    if a.no_hold:        # the scene belongs to someone else: write nothing to it, grab as it stands
        blender = grab("Blender", "CAM_OUT", os.path.join(out, "blender.png"))
        magic = grab(a.app, "MAGIC_OUT", os.path.join(out, "magic.png"))
        blender2 = grab("Blender", "CAM_OUT", os.path.join(out, "blender2.png"))
    else:
        held = list(state()["osc"]["hold"])
        cam = state()["values"]["vj_cam"]
        try:
            post("/api/set", {"vj_cam": 0, "vj_cam_speed": 0})
            post("/api/hold", {"keys": ["vj_cam", "vj_cam_speed"], "on": True})
            time.sleep(1.5)
            blender = grab("Blender", "CAM_OUT", os.path.join(out, "blender.png"))
            magic = grab(a.app, "MAGIC_OUT", os.path.join(out, "magic.png"))
            blender2 = grab("Blender", "CAM_OUT", os.path.join(out, "blender2.png"))
        finally:
            post("/api/hold", {"keys": ["vj_cam", "vj_cam_speed"], "on": False})
            post("/api/set", {"vj_cam": cam, "vj_cam_speed": contract_default("vj_cam_speed")})
            if held:
                post("/api/hold", {"keys": held, "on": True})
    for name, g in (("blender", blender), ("magic", magic), ("blender2", blender2)):
        print(name, json.dumps(g))
    if "error" in blender or "error" in magic or "error" in blender2:
        return 2
    gb, gm = grid(os.path.join(out, "blender.png")), grid(os.path.join(out, "magic.png"))
    up, flipped = corr(gb, gm), corr(gb, gm[::-1])
    mad = sum(abs(x - y) for rb, rm in zip(gb, gm) for x, y in zip(rb, rm)) / (16 * 9)
    print("correlation of the 16x9 luma grids: upright %.3f, rows reversed %.3f, mean difference %.1f of 255" % (up, flipped, mad))
    g2 = grid(os.path.join(out, "blender2.png"))
    print("Blender against itself a moment later (how far the scene moved): correlation %.3f, rows reversed %.3f" % (corr(gb, g2), corr(gb, g2[::-1])))
    print("frames in %s" % out)
    ok = up > 0.9 and up > flipped
    print("Magic's frame is %s" % ("Blender's picture, upright" if ok else "NOT Blender's picture upright"))
    return 0 if ok else 1


def contract_default(key):
    row = next(r for r in contract.load() if r["address"] == "/" + key.replace("_", "/", 1))
    b = row["blender"]
    return b["min"] + (row["default"] - row["min"]) / (row["max"] - row["min"]) * (b["max"] - b["min"])


def cmd_global(a):
    address = next(r["address"] for r in contract.load() if magic_manual.control_name(r["address"]) == a.name)
    key = address.strip("/").replace("/", "_")
    tmp = os.path.join(tempfile.mkdtemp(prefix="magic-proof-"), "show-%s.magic" % a.name)
    subprocess.run([sys.executable, MAGICPROJ, "set", SHOW, "-o", tmp, "--value", a.name, a.value], check=True)
    before = state()["values"][key]
    subprocess.run([sys.executable, MAGICPROJ, "load", tmp], check=True)
    time.sleep(a.wait)
    after = state()["values"][key]
    held = key in state()["osc"]["hold"]
    subprocess.run([sys.executable, MAGICPROJ, "load", SHOW], check=True)
    time.sleep(a.wait)
    back = state()["values"][key]
    print("%s %s: scene %s was %.4f, with the Global at %s %.4f, after loading the project back %.4f (held: %s)" % (address, key, "value", before, a.value, after, back, held))
    return 0 if abs(after - before) > 1e-3 and not held else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("osc")
    p = sub.add_parser("picture")
    p.add_argument("--app", default="Magic", help="app name Magic's Syphon server reports")
    p.add_argument("--no-hold", action="store_true", help="write nothing to the scene: no camera hold")
    p = sub.add_parser("global")
    p.add_argument("name")
    p.add_argument("value")
    p.add_argument("--wait", type=float, default=8.0)
    a = ap.parse_args()
    sys.exit({"osc": cmd_osc, "picture": cmd_picture, "global": cmd_global}[a.cmd](a))


if __name__ == "__main__":
    main()
