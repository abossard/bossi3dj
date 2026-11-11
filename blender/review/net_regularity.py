"""How regular the night edges are, from a night pair /vj/grid 1 and 0 (round 12):
    .venv/bin/python blender/review/net_regularity.py DIR GRID1:GRID0 ...     (file names without extension, .ppm or .png)
    .venv/bin/python blender/review/net_regularity.py --sim JITTER FLIP OUT.png  (a synthetic CAM_0-like view of the patch
                                                                               mesh on flat ground, its edges only)
Lines = pixels where GRID1 is brighter than GRID0 by more than 24 in a channel (as grid_diff.py). The frame is scanned in
overlapping windows of a tenth of its area (the rubric's size); a window with under 2 % line pixels is skipped.
Per window:
- run: the longest straight line of line pixels (largest Hough bin, 0.5 deg, 1 px), in px. A lattice's edge rows span the
  window; an uneven net breaks at each vertex. This one separates: synthetic view (--sim, flat ground, the Terrain
  material's fade by cell size) lattice 275, jitter 0.25 to 0.33 with flipped diagonals 170 to 185; round 11 grabs
  (failed R11-BEND) CAM_0 264, CAM_3 109 (few plain lines in frame). Chance at the plains' 8 % density is about 25.
- dir2: share of the line pixels' orientation (gradient, weighted) within +-7.5 deg of the two strongest directions.
- peak: the strongest bin of the window's 2D power spectrum (Hann window, wavelengths 4 to 60 px) over the band's mean.
  dir2 and peak barely moved with the jitter in the synthetic view (foreshortened rows stay near horizontal at pixel
  scale); they are printed for context only.
Printed: the line share, then per measure the worst window (max, its top-left corner) and the median over windows."""
import math
import os
import sys

import numpy as np
from PIL import Image

W, H = 960, 540
WIN = (304, 171)            # a tenth of the frame
MIN_SHARE = 0.02


def load(path):
    return np.asarray(Image.open(path).convert("RGB").resize((W, H)), np.float32)


def find(d, n):
    return next(os.path.join(d, n + e) for e in (".ppm", ".png") if os.path.exists(os.path.join(d, n + e)))


def dir2(lum, mask):
    gy, gx = np.gradient(lum)
    mag = np.hypot(gx, gy)
    sel = mask & (mag > 1e-3)
    ang = (np.degrees(np.arctan2(gy[sel], gx[sel])) + 90.0) % 180.0     # line direction, perpendicular to the gradient
    hist = np.bincount((ang // 5).astype(int) % 36, weights=mag[sel], minlength=36)
    win = hist + np.roll(hist, 1) + np.roll(hist, -1)                     # +-7.5 deg around each bin
    total = hist.sum()
    if total <= 0:
        return 0.0
    a = int(np.argmax(win))
    win2 = win.copy()
    for k in range(-2, 3):                                                # the second peak may not overlap the first
        win2[(a + k) % 36] = 0.0
    return float((win[a] + win2.max()) / total)


def peak(mask):
    h, w = mask.shape
    m = mask.astype(np.float32)
    m = (m - m.mean()) * np.outer(np.hanning(h), np.hanning(w))
    p = np.abs(np.fft.fftshift(np.fft.fft2(m))) ** 2
    fy = (np.arange(h) - h // 2)[:, None] / h
    fx = (np.arange(w) - w // 2)[None, :] / w
    f = np.hypot(fx, fy)
    band = (f >= 1.0 / 60.0) & (f <= 1.0 / 4.0)
    return float(p[band].max() / max(p[band].mean(), 1e-12))


THETA = np.radians(np.arange(0.0, 180.0, 0.5))


def run(mask):
    """Longest straight line of line pixels in the window: the largest Hough bin (0.5 deg, 1 px) in pixels.
    A lattice edge row spans the window; an uneven net breaks at each vertex, so its runs are a few cells long."""
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return 0.0
    best = 0
    for k in range(0, len(THETA), 40):
        th = THETA[k:k + 40]
        rho = np.rint(xs[:, None] * np.cos(th)[None] + ys[:, None] * np.sin(th)[None]).astype(np.int64)
        rho -= rho.min()
        key = rho + (rho.max() + 1) * np.arange(len(th))[None]
        best = max(best, int(np.bincount(key.ravel()).max()))
    return float(best)


def measure(lines):
    """lines: float image (H, W) of line brightness over the base. Returns the numbers for one frame."""
    mask = lines > 24.0
    rows = []
    for y in range(0, H - WIN[1] + 1, WIN[1] // 2):
        for x in range(0, W - WIN[0] + 1, WIN[0] // 2):
            mk = mask[y:y + WIN[1], x:x + WIN[0]]
            if mk.mean() < MIN_SHARE:
                continue
            rows.append((dir2(lines[y:y + WIN[1], x:x + WIN[0]], mk), peak(mk), x, y, run(mk)))
    if not rows:
        return {"share": float(mask.mean()), "windows": 0}
    d, p = np.array([r[0] for r in rows]), np.array([r[1] for r in rows])
    rn = np.array([r[4] for r in rows])
    wd, wp, wr = rows[int(np.argmax(d))], rows[int(np.argmax(p))], rows[int(np.argmax(rn))]
    return {"share": float(mask.mean()), "windows": len(rows),
            "dir2_max": float(d.max()), "dir2_at": wd[2:4], "dir2_med": float(np.median(d)),
            "peak_max": float(p.max()), "peak_at": wp[2:4], "peak_med": float(np.median(p)),
            "run_max": float(rn.max()), "run_at": wr[2:4], "run_med": float(np.median(rn))}


# ---------------------------------------------------------------- synthetic view (no Blender): flat ground, patch LOD
PATCH_M = 16000.0 * math.pi / 2 / 32     # build_planet.py: R * pi / 2 / PATCHES
KP = PATCH_M / 0.03                       # its level-0 distance (Detail 0.03)
LMAX = 7


def hash3(*v):
    """Deterministic 0..1 from integer arrays (a stand-in for the build's white noise hash)."""
    h = np.zeros_like(v[0], dtype=np.uint64)
    for k, a in enumerate(v):
        h ^= (np.asarray(a, np.int64).astype(np.uint64) + np.uint64(0x9E3779B97F4A7C15 + k)) * np.uint64(0xBF58476D1CE4E5B9)
        h ^= h >> np.uint64(29)
        h *= np.uint64(0x94D049BB133111EB)
        h ^= h >> np.uint64(32)
    return (h & np.uint64(0xFFFFFF)).astype(np.float64) / float(0xFFFFFF)


def sim(jitter, flip, eye=80.0, pitch=-6.0, fov=50.0, yaw=17.0):
    img = np.zeros((H, W), np.float32)
    f_ = (W / 2) / math.tan(math.radians(fov / 2))
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))

    def project(x, y):
        fwd = x * sy + y * cy
        side = x * cy - y * sy
        z = -eye
        depth = fwd * cp + z * sp
        up = -fwd * sp + z * cp
        ok = depth > 1.0
        d = np.where(ok, depth, 1.0)
        return W / 2 + f_ * side / d, H / 2 - f_ * up / d, ok

    span = 6000.0
    n_p = int(span / PATCH_M) + 1
    for pi_ in range(-n_p, n_p):
        for pj in range(-n_p, n_p):
            x0, y0 = pi_ * PATCH_M, pj * PATCH_M
            dx = max(x0 - 0.0, 0.0 - (x0 + PATCH_M), 0.0)
            dy = max(y0 - 0.0, 0.0 - (y0 + PATCH_M), 0.0)
            dist = max(math.hypot(math.hypot(dx, dy), eye), 1.0)
            lv = int(min(max(math.floor(math.log2(KP / dist)), 0), LMAX))
            n = 2 ** lv
            ix, iy = np.meshgrid(np.arange(n + 1), np.arange(n + 1), indexing="ij")
            u = hash3(ix, iy, np.full_like(ix, lv), np.full_like(ix, pi_ * 1000 + pj))
            v = hash3(iy, ix, np.full_like(ix, lv + 50), np.full_like(ix, pi_ * 1000 + pj))
            inner = (ix > 0) & (ix < n) & (iy > 0) & (iy < n)
            r = np.sqrt(v) * jitter * inner
            gx = x0 + (ix + r * np.cos(2 * np.pi * u)) * PATCH_M / n
            gy = y0 + (iy + r * np.sin(2 * np.pi * u)) * PATCH_M / n
            px, py, ok = project(gx, gy)
            segs = [((slice(0, n), slice(0, n + 1)), (slice(1, n + 1), slice(0, n + 1))),
                    ((slice(0, n + 1), slice(0, n)), (slice(0, n + 1), slice(1, n + 1)))]
            cx, cyy = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
            fl = (hash3(cx, cyy, np.full_like(cx, lv + 100), np.full_like(cx, pi_ * 1000 + pj)) > 0.5) if flip else np.zeros_like(cx, bool)
            a00, a11 = (slice(0, n), slice(0, n)), (slice(1, n + 1), slice(1, n + 1))
            a10, a01 = (slice(1, n + 1), slice(0, n)), (slice(0, n), slice(1, n + 1))
            ends = [(a, b, None) for a, b in segs] + [(a00, a11, ~fl), (a10, a01, fl)]
            # the Terrain material fades edges where a cell's smaller side is under 4 to 10 px on screen (cell_px x ndv);
            # line pixels (over 24 of 120) start near 5.2 px
            dist_v = np.hypot(np.hypot(gx, gy), eye)
            dense = (PATCH_M / n) / (dist_v * 0.0011) * (eye / dist_v) > 5.2
            for a, b, sel in ends:
                xa, ya, oa = px[a], py[a], ok[a] & dense[a]
                xb, yb, ob = px[b], py[b], ok[b] & dense[b]
                keep = oa & ob if sel is None else oa & ob & sel
                draw(img, xa[keep], ya[keep], xb[keep], yb[keep])
    return img


def draw(img, xa, ya, xb, yb):
    vis = ((np.maximum(xa, xb) >= 0) & (np.minimum(xa, xb) < W) & (np.maximum(ya, yb) >= 0) & (np.minimum(ya, yb) < H))
    xa, ya, xb, yb = xa[vis], ya[vis], xb[vis], yb[vis]
    if not len(xa):
        return
    steps = np.clip(np.ceil(np.hypot(xb - xa, yb - ya)).astype(int), 1, 2000)
    rep = np.repeat(np.arange(len(xa)), steps)
    t = (np.arange(steps.sum()) - np.repeat(np.cumsum(steps) - steps, steps)) / np.repeat(steps, steps)
    x = np.rint(xa[rep] + (xb - xa)[rep] * t).astype(int)
    y = np.rint(ya[rep] + (yb - ya)[rep] * t).astype(int)
    ok = (x >= 0) & (x < W) & (y >= 0) & (y < H)
    img[y[ok], x[ok]] = 120.0


def show(name, m):
    if not m.get("windows"):
        print("%-40s share %.4f  no window with lines" % (name, m["share"]))
        return
    print("%-34s share %.4f win %2d | run max %4.0f %-10s med %4.0f | dir2 max %.3f med %.3f | peak max %5.0f med %5.0f" % (
        name, m["share"], m["windows"], m["run_max"], m["run_at"], m["run_med"], m["dir2_max"], m["dir2_med"],
        m["peak_max"], m["peak_med"]))


if __name__ == "__main__":
    if sys.argv[1] == "--sim":
        jit, flip = float(sys.argv[2]), sys.argv[3] == "1"
        lines = sim(jit, flip)
        if len(sys.argv) > 4:
            Image.fromarray(lines.astype(np.uint8)).save(sys.argv[4])
        show("sim jitter %.2f flip %d" % (jit, flip), measure(lines))
    else:
        d = sys.argv[1]
        for pair in sys.argv[2:]:
            a, b = pair.split(":")
            lines = (load(find(d, a)) - load(find(d, b))).max(axis=2)
            show(a, measure(lines))
