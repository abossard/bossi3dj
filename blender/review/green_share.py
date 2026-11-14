"""Share of strongly green pixels in frames: .venv/bin/python blender/review/green_share.py FRAME...
A pixel counts when its green is more than 60 (of 255) above both red and blue: no material of the planet is that green;
the hole test of terrain_test_flight.py paints the sea's underside pure green (0, 255, 0)."""
import subprocess
import sys

import numpy as np

for p in sys.argv[1:]:
    w, h = map(int, subprocess.run(["magick", "identify", "-format", "%w %h", p], capture_output=True, text=True, check=True).stdout.split())
    a = np.frombuffer(subprocess.run(["magick", p, "-depth", "8", "rgb:-"], capture_output=True, check=True).stdout, np.uint8)
    a = a.reshape(h, w, 3).astype(np.int16)
    g = (a[..., 1] - a[..., 0] > 60) & (a[..., 1] - a[..., 2] > 60)
    print("%-70s green %.5f (%d px)" % (p[-70:], g.mean(), int(g.sum())))
