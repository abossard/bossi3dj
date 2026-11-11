"""Numbers for terrain_equality.py: .venv/bin/python blender/review/terrain_equality_diff.py DIR
Per case the mean absolute difference (0..255) and the share of pixels off by more than 8 for the noise floor
(A1-A2, B1-B2) and for started against stopped (A1-B1, A2-B2). Equal: started-stopped within the noise floor."""
import os
import sys

import numpy as np

d = sys.argv[1]


def load(path):
    with open(path, "rb") as f:
        data = f.read()
    parts = data.split(maxsplit=4)          # P6 width height maxval pixels
    w, h = int(parts[1]), int(parts[2])
    return np.frombuffer(parts[4][: w * h * 3], np.uint8).reshape(h, w, 3).astype(np.float32)


def diff(a, b):
    x = np.abs(load(a) - load(b))
    return round(float(x.mean()), 3), round(float((x.max(axis=2) > 8).mean()), 5)


cases = sorted({f[:-7] for f in os.listdir(d) if f.endswith("_A1.ppm")})
print("case            floor A1-A2       floor B1-B2       A1-B1             A2-B2")
for c in cases:
    p = {k: os.path.join(d, "%s_%s.ppm" % (c, k)) for k in ("A1", "A2", "B1", "B2")}
    row = [diff(p["A1"], p["A2"]), diff(p["B1"], p["B2"]), diff(p["A1"], p["B1"]), diff(p["A2"], p["B2"])]
    print("%-15s " % c + " ".join("mad %-6g fr %-7g" % r for r in row))
