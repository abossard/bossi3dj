#!/usr/bin/env python3
"""How much two PNG frames differ, in numbers: mean absolute luma difference (0..255) and the share
of pixels whose luma differs by more than 12.

    python3 tools/png_pair_diff.py a.png b.png [c.png d.png ...]   (pairs in order)

Prints one JSON line per pair. Standard library only (uses png_stats.read_png).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import png_stats  # noqa: E402


def luma_rows(path, step=4):
    w, h, ch, rows = png_stats.read_png(path)
    return [[0.2126 * r[x * ch] + 0.7152 * r[x * ch + 1] + 0.0722 * r[x * ch + 2] for x in range(0, w, step)]
            for r in rows[::step]]


def diff(a, b):
    la, lb = luma_rows(a), luma_rows(b)
    n = total = big = 0
    for ra, rb in zip(la, lb):
        for x, y in zip(ra, rb):
            d = abs(x - y)
            total += d
            big += d > 12
            n += 1
    return {"a": os.path.basename(a), "b": os.path.basename(b),
            "mean_abs_luma_diff": round(total / n, 2), "share_over_12": round(big / n, 3)}


if __name__ == "__main__":
    paths = sys.argv[1:]
    for i in range(0, len(paths) - 1, 2):
        print(json.dumps(diff(paths[i], paths[i + 1])))
