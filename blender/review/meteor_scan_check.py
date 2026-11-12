"""Numbers of meteor_scan.py: .venv/bin/python blender/review/meteor_scan_check.py DIR. Per camera the mean absolute
difference of before against after the trigger (0..255) and the share of pixels moved by more than 8, best first."""
import os
import subprocess
import sys

import numpy as np

d = sys.argv[1]


def load(p):
    raw = subprocess.run(["magick", p, "-depth", "8", "rgb:-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(540, 960, 3).astype(np.float32)


rows = []
for c in range(11):
    lo, hi = (os.path.join(d, "m__cam%d__%s.ppm" % (c, t)) for t in ("lo", "hi"))
    if os.path.exists(lo) and os.path.exists(hi):
        a, b = load(lo), load(hi)
        diff = np.abs(a - b)
        rows.append((float((diff.max(axis=2) > 8).mean()), float(diff.mean()), c))
for frac, mad, c in sorted(rows, reverse=True):
    print("CAM_%-2d mad %.3f changed %.5f" % (c, mad, frac))
