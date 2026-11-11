"""Mean absolute difference (0..255) and changed-pixel share (> 8) between pairs of grabs: python grid_diff.py DIR A:B ...
Each pair is two file names in DIR without extension (.ppm or .png).
A:B@BASE also compares the line masks (pixels over BASE by more than 24 in a channel) of A and B: their share of the
frame, the share in each third of the rows, and their overlap (intersection over union; 1 when no line moved).
A brightness pulse keeps the overlap and scales the lines by one factor; a line that moves against the terrain lowers
the overlap."""
import os
import subprocess
import sys

import numpy as np


def load(path):
    raw = subprocess.run(["magick", path, "-depth", "8", "rgb:-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(540, 960, 3).astype(np.float32)


def find(d, n):
    return next(os.path.join(d, n + e) for e in (".ppm", ".png") if os.path.exists(os.path.join(d, n + e)))


d = sys.argv[1]
for pair in sys.argv[2:]:
    pair, _, base = pair.partition("@")
    a, b = pair.split(":")
    fa, fb = load(find(d, a)), load(find(d, b))
    diff = np.abs(fa - fb)
    print("%-34s %-34s mad %.3f changed %.5f" % (a, b, diff.mean(), (diff.max(axis=2) > 8).mean()))
    if base:
        f0 = load(find(d, base))
        ma, mb = (fa - f0).max(axis=2) > 24, (fb - f0).max(axis=2) > 24
        thirds = " ".join("%.3f" % ma[i * 180:(i + 1) * 180].mean() for i in range(3))
        print("    lines over %s: share %.4f %.4f, rows top/mid/bottom %s, overlap %.3f" % (
            base, ma.mean(), mb.mean(), thirds, (ma & mb).sum() / max((ma | mb).sum(), 1)))
        both = ma & mb       # a pulse scales every line by one factor: B's line brightness over A's, its spread small
        ra = ((fb - f0).max(axis=2)[both]) / np.maximum((fa - f0).max(axis=2)[both], 1.0)
        print("    line brightness B/A on the overlap: median %.3f, p10 %.3f, p90 %.3f" % tuple(np.percentile(ra, [50, 10, 90])))
