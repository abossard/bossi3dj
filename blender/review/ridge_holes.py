"""Issue #10, holes and a pale ring on mountain ridges, offline on the cached GT_Map (no Blender):
    .venv/bin/python blender/review/ridge_holes.py [cache.npz] [out.json]
The land material hides a pixel where zw = alt - pl_w < -SHALLOW (build_planet.terrain_build: "visible above its own
water level"). On the GPU terrain alt is the drawn triangle's height (the ring's lattice, linear between its vertices)
and pl_w the map's water level read per pixel; on dry land the bake puts the water 15 m under the land. Where a ring's
cells are much wider than the map's texels the triangles cut under a peak by more than that: the pixel is hidden (a
hole) or drawn as the wet bed (-SHALLOW < zw < 0, the pale ring).
Per ring cell (24 to 384 m, and the morph band's twice that) over the box of the camera targets with a margin: the
share of dry land hidden and wet-drawn, the chord's largest cut under the land, and the worst places in map metres.
Both sides use the map B-spline prefiltered ([1 4 1] / 6, what EEVEE's Cubic gives at a texel centre)."""
import json
import os
import sys

import numpy as np

R = 16000.0
W = 8192
SHALLOW = 1.0
BOX = ((-14000.0, 12000.0), (-16000.0, 14000.0))      # m along longitude, latitude: the targets and 4 km round them
CELLS = (24.0, 48.0, 96.0, 192.0, 384.0)
TARGETS = {"pyramids": (138, -150), "lake": (-2307, 4920), "river": (-8073, -11939), "coast": (2562, 8029)}


def bspline(a):
    a = (np.roll(a, 1, 1) + 4.0 * a + np.roll(a, -1, 1)) / 6.0
    return (np.roll(a, 1, 0) + 4.0 * a + np.roll(a, -1, 0)) / 6.0


def window(a):
    """a's texels over BOX with one cell of margin, and their lam, phi (rad)."""
    dl, dp = 2.0 * np.pi / W, np.pi / (W // 2)
    x0, x1 = (int((BOX[0][k] / R + np.pi) / dl) for k in (0, 1))
    y0, y1 = (int((BOX[1][k] / R + np.pi / 2) / dp) for k in (0, 1))
    m = int(400.0 / R / dl) + 2
    xs, ys = np.arange(x0 - m, x1 + m), np.arange(y0 - m, y1 + m)
    return a[np.ix_(ys, xs % W)], -np.pi + (xs + 0.5) * dl, -np.pi / 2 + (ys + 0.5) * dp


def chord(h, lam, phi, cell):
    """h at its texels as a ring of cell (m) draws it: sampled on the ring's lattice (step cell / R in lam and phi, the
    map's own coordinates) and linear over each cell's two triangles (split along the diagonal i + j)."""
    s = cell / R
    li, pj = np.floor(lam / s), np.floor(phi / s)
    fx, fy = lam / s - li, phi / s - pj

    def at(a, b):           # bilinear on the prefiltered map at lattice point (a, b)
        x = ((a * s) - lam[0]) / (lam[1] - lam[0])
        y = ((b * s) - phi[0]) / (phi[1] - phi[0])
        x0, y0 = np.clip(np.floor(x).astype(int), 0, len(lam) - 2), np.clip(np.floor(y).astype(int), 0, len(phi) - 2)
        tx, ty = x - x0, y - y0
        return ((h[y0, x0] * (1 - tx) + h[y0, x0 + 1] * tx) * (1 - ty) + (h[y0 + 1, x0] * (1 - tx) + h[y0 + 1, x0 + 1] * tx) * ty)

    LI, PJ = np.meshgrid(li, pj)
    FX, FY = np.meshgrid(fx, fy)
    h00, h10, h01, h11 = at(LI, PJ), at(LI + 1, PJ), at(LI, PJ + 1), at(LI + 1, PJ + 1)
    lo = FX + FY <= 1.0
    return np.where(lo, h00 + (h10 - h00) * FX + (h01 - h00) * FY,
                    h11 + (h01 - h11) * (1 - FX) + (h10 - h11) * (1 - FY))


def run(path, out):
    d = np.load(path)
    hs, ws = bspline(d["h"].astype(np.float64)), bspline(d["w"].astype(np.float64))
    h, lam, phi = window(hs)
    w, _, _ = window(ws)
    inb = ((lam * R >= BOX[0][0]) & (lam * R <= BOX[0][1]))[None, :] & ((phi * R >= BOX[1][0]) & (phi * R <= BOX[1][1]))[:, None]
    dry = (w - h < 0.0) & inb
    land = dry.sum()
    res = {"cache": os.path.basename(path), "box_m": BOX, "dry_texels": int(land),
           "w_minus_h_on_dry_pct_1_50_99": [round(float(x), 2) for x in np.percentile((w - h)[dry], [1, 50, 99])], "cells": {}}
    for cell in CELLS:
        alt = chord(h, lam, phi, cell)
        zw = alt - w
        hole = dry & (zw < -SHALLOW)
        wetd = dry & (zw >= -SHALLOW) & (zw < 0.0)
        cut = np.where(dry, h - alt, -np.inf)
        ys, xs = np.nonzero(hole)
        worst = []
        if len(ys):
            order = np.argsort(-cut[ys, xs])
            seen = []
            for k in order:
                p = (float(lam[xs[k]] * R), float(phi[ys[k]] * R))
                if all(np.hypot(p[0] - q[0], p[1] - q[1]) > 600.0 for q in seen):
                    seen.append(p)
                    near = min(TARGETS, key=lambda t: np.hypot(p[0] - TARGETS[t][0], p[1] - TARGETS[t][1]))
                    worst.append({"lon_m": round(p[0]), "lat_m": round(p[1]), "h": round(float(h[ys[k], xs[k]]), 1),
                                  "cut_m": round(float(cut[ys[k], xs[k]]), 1), "near": near,
                                  "km": round(float(np.hypot(p[0] - TARGETS[near][0], p[1] - TARGETS[near][1])) / 1000.0, 2)})
                if len(worst) == 8:
                    break
        res["cells"]["%g" % cell] = {"hidden_share": round(float(hole.sum() / land), 5),
                                     "wet_drawn_share": round(float(wetd.sum() / land), 5),
                                     "cut_max_m": round(float(cut.max()), 1),
                                     "cut_p999_m": round(float(np.percentile(cut[dry], 99.9)), 2),
                                     "worst": worst}
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(res, open(out, "w"), indent=1)
    return res


if __name__ == "__main__":
    cache = sys.argv[1] if len(sys.argv) > 1 else "~/Library/Caches/swiftvj-flight/gt2-synthwave_planet-1794776634-8192.npz"
    o = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), "out", "issue10", "ridge_holes.json")
    r = run(os.path.expanduser(cache), o)
    print(json.dumps({k: {kk: v[kk] for kk in ("hidden_share", "wet_drawn_share", "cut_max_m", "cut_p999_m")}
                      for k, v in r["cells"].items()}, indent=1))
