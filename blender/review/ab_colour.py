"""Where and how an A/B pair from ridge_check.py differs, in numbers (issue #11's colour shift).
    .venv/bin/python blender/review/ab_colour.py <dir> <shot>
Per block of 20 rows holding changed pixels (luminance change over CHANGE of 255): the changed pixel count and the mean
RGB of those pixels in _before and _after.
"""
import sys

import numpy as np
from PIL import Image

CHANGE = 8.0
LUM = np.array([0.2126, 0.7152, 0.0722], np.float32)


def main(d, shot):
    a = np.asarray(Image.open("%s/%s_after.png" % (d, shot)).convert("RGB"), np.float32)
    b = np.asarray(Image.open("%s/%s_before.png" % (d, shot)).convert("RGB"), np.float32)
    ch = np.abs((a - b) @ LUM) > CHANGE
    print("changed share %.5f" % ch.mean())
    for y in range(0, a.shape[0], 20):
        m = ch[y:y + 20]
        if m.sum() < 20:
            continue
        print("rows %4d-%4d  n %6d  before %s  after %s" % (y, y + 19, m.sum(),
              np.round(b[y:y + 20][m].mean(0)).astype(int), np.round(a[y:y + 20][m].mean(0)).astype(int)))


if __name__ == "__main__":
    main(*sys.argv[1:3])
