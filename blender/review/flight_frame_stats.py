"""Numbers on the full-size Flight grabs of flight_grabs.py: .venv/bin/python blender/review/flight_frame_stats.py DIR
Per stage: day luminance mean and spread (whole frame and lower half), near-black share by day (a hole shows as black or
sky), the night mean, and /vj/grid 1 against 0 at night (mean abs diff and share of pixels off by more than 8: the edges)."""
import subprocess
import sys

import numpy as np


def load(p):
    raw = subprocess.run(["magick", p, "-depth", "8", "rgb:-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(1080, 1920, 3).astype(np.float32)


d = sys.argv[1].rstrip("/")
for s in ("orbit", "approach", "skim", "hover"):
    try:
        day, g1, g0 = (load("%s/%s_%s.ppm" % (d, s, look)) for look in ("day", "night_grid1", "night_grid0"))
    except Exception:
        continue
    lum = day.mean(axis=2)
    diff = np.abs(g1 - g0).max(axis=2)
    print("%-9s day mean %5.1f sd %5.1f lower sd %5.1f black %.4f | night mean %5.1f | grid1-grid0 mad %5.2f share>8 %.4f"
          % (s, lum.mean(), lum.std(), lum[540:].std(), (day.max(axis=2) < 3).mean(), g1.mean(), np.abs(g1 - g0).mean(), (diff > 8).mean()))
