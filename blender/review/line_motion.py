"""Do the night edges move between two frames, or only pulse? python line_motion.py DIR BASE A B
BASE is the /vj/grid 0 frame, A and B the /vj/grid 1 frames 1 s apart (file names without extension, as grid_diff.py).
Line masks = pixels over BASE by more than T in a channel, for T 24 (grid_diff.py's) and 8 (catches the dark part of a
pulse). Printed per T: line share of A and B, overlap (intersection over union) at shift 0, and the best overlap over
shifts of up to 2 px (a line that only moved a pixel or two). A pulse changes the share at T 24 and not the overlap at
T 8; moving lines lower the overlap at every T and every shift."""
import itertools
import os
import subprocess
import sys

import numpy as np


def load(path):
    raw = subprocess.run(["magick", path, "-depth", "8", "rgb:-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(540, 960, 3).astype(np.float32)


def find(d, n):
    return next(os.path.join(d, n + e) for e in (".ppm", ".png") if os.path.exists(os.path.join(d, n + e)))


def iou(a, b):
    return float((a & b).sum() / max((a | b).sum(), 1))


d, base, a, b = sys.argv[1:5]
base, a, b = (load(find(d, n)) for n in (base, a, b))
for t in (24, 8):
    ma, mb = ((x - base).max(axis=2) > t for x in (a, b))
    best = max(iou(ma, np.roll(mb, (dy, dx), (0, 1))) for dy, dx in itertools.product(range(-2, 3), repeat=2))
    print("T %2d: share A %.4f B %.4f, overlap %.3f, best within 2 px %.3f" % (t, ma.mean(), mb.mean(), iou(ma, mb), best))
