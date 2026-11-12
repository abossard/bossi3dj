"""Numbers of round 13 on a grab folder of round13_jobs.py (960x540 frames): .venv/bin/python blender/review/round13_numbers.py DIR
- plain: CAM_0 and CAM_3 by day, rows 62 to 98 %: the spread across the band once each row's mean is out (plain_tone.py)
- CAM_5 top band: mean luminance of rows 0 to 5 against rows 8 to 13, by day and night, fog 0.5 and 1
- CAM_4 night haze: per band of 90 rows from the top, luminance and star points over 40, fog 1 against fog 0
- CAM_10 nebula 0: the sky patch x 300 to 700, y 0 to 120 (round 9's): mean, sd, and pixels over 50 (star points)"""
import os
import subprocess
import sys

import numpy as np

D = sys.argv[1].rstrip("/")


def load(name):
    names = [name, name.replace("_f00_", "_f0_").replace("_f10_", "_f1_")]     # earlier rounds wrote f0, f1
    paths = [os.path.join(D, n + ext) for n in names for ext in (".ppm", ".png")]
    p = next((q for q in paths if os.path.exists(q)), None)
    if p is None:
        return None
    raw = subprocess.run(["magick", p, "-depth", "8", "rgb:-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(540, 960, 3).astype(np.float32) @ np.array([0.2126, 0.7152, 0.0722], np.float32)


out = {}
for c in (0, 3):
    a = load("CAM_%d_day_f00_e0" % c)
    if a is not None:
        band = a[int(0.62 * 540):int(0.98 * 540)]
        res = band - band.mean(axis=1, keepdims=True)
        out["plain CAM_%d" % c] = "mean %.1f across sd %.2f p5-p95 %.2f" % (band.mean(), res.std(), np.percentile(res, 95) - np.percentile(res, 5))
for t in ("day", "night"):
    for f in ("05", "10"):
        a = load("CAM_5_%s_f%s_e0" % (t, f))
        if a is not None:
            out["CAM_5 %s f%s" % (t, f)] = "rows 0-5 %.1f rows 8-13 %.1f ratio %.3f" % (a[:6].mean(), a[8:14].mean(), a[:6].mean() / max(a[8:14].mean(), 1e-3))
a0, a1 = load("CAM_4_night_f00_e0"), load("CAM_4_night_f10_e0")
if a0 is not None and a1 is not None:      # per band of 90 rows from the top: luminance and star points over 40
    for r0 in (0, 90, 180, 270):
        out["CAM_4 night rows %d-%d" % (r0, r0 + 90)] = "f0 %.2f (%d stars) f1 %.2f (%d stars)" % (
            a0[r0:r0 + 90].mean(), int((a0[r0:r0 + 90] > 40).sum()), a1[r0:r0 + 90].mean(), int((a1[r0:r0 + 90] > 40).sum()))
for tag, name in (("neb1", "CAM_10_night_f00_e0"), ("neb0", "CAM_10_night_f00_e0_neb0")):
    a = load(name)
    if a is not None:
        p = a[0:120, 300:700]
        out["CAM_10 %s sky patch" % tag] = "mean %.2f sd %.2f over50 %d" % (p.mean(), p.std(), int((p > 50).sum()))
for k, v in out.items():
    print("%-24s %s" % (k, v))
