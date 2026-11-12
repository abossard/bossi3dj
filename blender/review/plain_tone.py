"""How much light and shade the day plain shows: .venv/bin/python blender/review/plain_tone.py FRAME... [--rows 0.62:0.98]
Per frame (.ppm or .png, any size), over the band of rows given as fractions of the height (the foreground plain):
the mean luminance, the spread across the band after each row's mean is taken out (distance haze and the horizon
gradient run by row, the swells' light and shade across them), its 5 to 95 percentile range, and the mean RGB."""
import subprocess
import sys

import numpy as np


def load(path):
    w, h = map(int, subprocess.run(["magick", "identify", "-format", "%w %h", path], capture_output=True, text=True, check=True).stdout.split())
    raw = subprocess.run(["magick", path, "-depth", "8", "rgb:-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(h, w, 3).astype(np.float32)


args = [a for a in sys.argv[1:] if not a.startswith("--")]
rows = sys.argv[sys.argv.index("--rows") + 1] if "--rows" in sys.argv else "0.62:0.98"
a0, a1 = (float(x) for x in rows.split(":"))
for p in args:
    if p == rows:
        continue
    a = load(p)
    band = a[int(a0 * a.shape[0]):int(a1 * a.shape[0])]
    lum = band @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    res = lum - lum.mean(axis=1, keepdims=True)
    print("%-60s mean %6.1f  across sd %5.2f  p5-p95 %6.2f  rgb %s" % (p[-60:], lum.mean(), res.std(), np.percentile(res, 95) - np.percentile(res, 5),
                                                                    np.round(band.reshape(-1, 3).mean(axis=0), 1).tolist()))
