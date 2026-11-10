"""Frame-difference trace over an altitude sweep: python frame_diff.py DIR TAG TIME
Reads DIR/<TAG>_<TIME>_<alt>.ppm (or .png) in altitude order and writes DIR/<TAG>_<TIME>_diff.csv with the mean
absolute difference (0..255) between each frame and the one before, then prints the largest step and the median."""
import os
import subprocess
import sys

import numpy as np

d, tag, tn = sys.argv[1], sys.argv[2], sys.argv[3]
names = sorted(f for f in os.listdir(d) if f.startswith("%s_%s_" % (tag, tn)) and f.endswith((".ppm", ".png")) and "diff" not in f)


def load(path):
    raw = subprocess.run(["magick", path, "-depth", "8", "rgb:-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(540, 960, 3).astype(np.float32)


rows, prev = [], None
for f in names:
    alt = int(f.rsplit("_", 1)[1].split(".")[0])
    a = load(os.path.join(d, f))
    if prev is not None:
        rows.append((alt, float(np.abs(a - prev).mean())))
    prev = a
with open(os.path.join(d, "%s_%s_diff.csv" % (tag, tn)), "w") as fo:
    fo.write("alt_m,mean_abs_diff\n" + "".join("%d,%.3f\n" % r for r in rows))
steps = np.array([r[1] for r in rows])
k = int(steps.argmax())
print("%s %s: %d steps, median %.2f, largest %.2f at %d m (x%.1f the median)" % (
    tag, tn, len(rows), np.median(steps), steps[k], rows[k][0], steps[k] / max(np.median(steps), 1e-6)))
