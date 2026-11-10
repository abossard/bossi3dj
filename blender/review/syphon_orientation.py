#!/usr/bin/env python3
"""Which way up is the Syphon frame `CAM_OUT - Blender`? Evidence only, no image is read by a person.

    python3 blender/review/syphon_orientation.py

Takes the scene's own preview (http 9210 /api/frame.bmp: the same composite as the Syphon texture, stored
bottom-up by the BMP format, so flipped here to top-down) and one Syphon frame from `magicproj.py grab --app
Blender --server CAM_OUT`, whose rows are in the order Syphon delivers them (magicproj reverses only Magic's).
Both are reduced to the 3x3 grid of mean luminance that grab reports, and the order of the rows is compared:
the grab matches the preview either top-down or reversed. The scene is held still (vj_cam_speed 0) meanwhile
and put back afterwards. Standard library only; `grab` needs the Syphon Python that magicproj finds itself.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = "http://127.0.0.1:9210"


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10).read()


def lum(r, g, b):
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def preview_grid():
    bmp = urllib.request.urlopen(BASE + "/api/frame.bmp", timeout=10).read()
    w, h = 640, 360
    px = bmp[54:]
    out = []
    for j in range(3):
        row = []
        for i in range(3):
            y_top = int(h * (j + 0.5) / 3)               # row counted from the top of the picture
            y_mem = h - 1 - y_top                         # the BMP stores the bottom row first
            o = (y_mem * w + int(w * (i + 0.5) / 3)) * 3
            row.append(round(lum(px[o + 2], px[o + 1], px[o]), 1))
        out.append(row)
    return out


def main():
    state = json.load(urllib.request.urlopen(BASE + "/api/state", timeout=5))
    keep = {k: state["values"][k] for k in ("vj_cam_speed",)}
    post("/api/hold", {"keys": list(keep), "on": True})
    post("/api/set", {"vj_cam_speed": 0.0})
    urllib.request.urlopen(BASE + "/api/frame.bmp", timeout=5).read()    # ask for previews
    time.sleep(3.0)
    try:
        preview = preview_grid()
        grab = json.loads(subprocess.run([sys.executable, os.path.join(ROOT, "magic", "magicproj.py"), "grab", "--app", "Blender",
                                          "--server", "CAM_OUT"], capture_output=True, text=True, timeout=120).stdout)
        again = preview_grid()
    finally:
        post("/api/set", keep)
        post("/api/hold", {"keys": list(keep), "on": False})
    g = [[round(lum(*c), 1) for c in row] for row in grab["grid"]]
    rowmean = lambda m: [round(sum(r) / 3, 1) for r in m]       # noqa: E731
    p, q = rowmean(preview), rowmean(g)
    err = lambda a, b: sum(abs(x - y) for x, y in zip(a, b))    # noqa: E731
    print(json.dumps({"preview_rows_top_to_bottom": p, "preview_after": rowmean(again), "grab_rows_top_to_bottom": q,
                      "grab_size": grab["size"], "error_same_order": round(err(p, q), 1), "error_reversed": round(err(p, q[::-1]), 1),
                      "grab_is_flipped_against_preview": err(p, q[::-1]) < err(p, q)}, indent=1))


if __name__ == "__main__":
    main()
