"""Do the two halves of each README pair differ by more than the noise? python readme_pair_check.py DIR [--min-mad 0.5]
Reads DIR/plan.json and the frames readme_pairs.py wrote (.ppm, 960x540). Per pair: mean absolute difference (0..255) of
lo against hi, and of lo against lo2 (the same state again: the noise floor), the share of pixels moved by more than 8.
A pair counts when mad(lo, hi) >= max(min-mad, 2 x mad(lo, lo2)), more than 1 % of the pixels moved, and the floor is under 2 (a larger one
means the two frames of one state differ already, for instance a new Flight seed). Also prints luminance mean and spread of every camera frame
(cam__N__pK), to pick the phase that shows something. Exit 0; the verdict is printed and written to DIR/pairs.json."""
import json
import os
import subprocess
import sys

import numpy as np


def load(path):
    raw = subprocess.run(["magick", path, "-depth", "8", "rgb:-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(540, 960, 3).astype(np.float32)


d = sys.argv[1]
min_mad = float(sys.argv[sys.argv.index("--min-mad") + 1]) if "--min-mad" in sys.argv else 0.5
plan = json.load(open(os.path.join(d, "plan.json")))
out = []
for p in plan["pairs"]:
    f = lambda t: os.path.join(d, "%s__%s.ppm" % (p["base"], t))
    if not all(os.path.exists(f(t)) for t in ("lo", "lo2", "hi")):
        out.append(dict(p, verdict="missing"))
        continue
    lo, lo2, hi = (load(f(t)) for t in ("lo", "lo2", "hi"))
    mad, floor = float(np.abs(lo - hi).mean()), float(np.abs(lo - lo2).mean())
    frac = float((np.abs(lo - hi).max(axis=2) > 8).mean())
    ok = mad >= max(min_mad, 2.0 * floor) and frac > 0.01 and floor < 2.0
    out.append(dict(p, mad=round(mad, 3), floor=round(floor, 3), changed=round(frac, 4), verdict="pair" if ok else "no pair"))
    print("%-16s cam %2d  mad %7.3f  floor %6.3f  changed %.4f  %s" % (p["key"], p["cam"], mad, floor, frac, out[-1]["verdict"]))
cams = []
for name in sorted(n for n in os.listdir(d) if n.startswith(("cam__", "extra__")) and n.endswith(".ppm")):
    a = load(os.path.join(d, name))
    lum = a.mean(axis=2)
    cams.append({"file": name, "mean": round(float(lum.mean()), 1), "sd": round(float(lum.std()), 1), "lower_sd": round(float(lum[270:].std()), 1)})
    print("%-28s mean %5.1f sd %5.1f lower-half sd %5.1f" % (name, cams[-1]["mean"], cams[-1]["sd"], cams[-1]["lower_sd"]))
json.dump({"pairs": out, "frames": cams}, open(os.path.join(d, "pairs.json"), "w"), indent=1)
