"""What the regional water map adds (docs/handover/gpu-terrain.md, regional water map). In the live planet Blender with
gpu_terrain started (both maps cached): DN["wm_job"] = {"out": "/abs/water_map.json"}; exec this file.
Over the region's box, inland water only (water level over INLAND m, so the sea is left out): the wet share at 4 m
(the regional bake) and at 12 m (the 12 m map, bilinear at the same points); the channel width per wet texel (the
shorter of its wet runs along longitude and latitude, in m) as a histogram for both; the wet texels the 12 m map
misses and how many of them lie in channels under 25 m; and the share of wet texels whose flow is set (the flow as
spread, both maps, at their half resolution).
"""
import json
import sys

import bpy
import numpy as np

DN = bpy.app.driver_namespace
JOB = DN["wm_job"]
gt = sys.modules.get("gpu_terrain") or next(h for h in bpy.app.handlers.frame_change_pre
                                            if h.__name__ == "frame" and "gpu_terrain" in h.__globals__).__globals__["gpu_terrain"]
INLAND = 3.0
BINS = (0, 8, 16, 25, 50, 100, 200, 1e9)


def runs(wet, axis):
    """Per wet texel the length of the wet run along axis it belongs to."""
    a = np.moveaxis(wet, axis, -1)
    out = np.zeros(a.shape, np.int32)
    for i in range(a.shape[0]):
        row = a[i]
        d = np.diff(np.concatenate([[0], row.astype(np.int8), [0]]))
        st, en = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
        for s, e in zip(st, en):
            out[i, s:e] = e - s
    return np.moveaxis(out, -1, axis)


def width(wet, m_lam, m_phi):
    return np.minimum(runs(wet, 1) * m_lam, runs(wet, 0) * m_phi)


def hist(wd, wet):
    c, _ = np.histogram(wd[wet], bins=BINS)
    return {"%g-%g" % (BINS[i], BINS[i + 1]): int(c[i]) for i in range(len(c))}


S = bpy.context.scene
hr, wr, fr = gt.bake(S, None, True)          # cached: probe_group is not called
hg, wg, fg = gt.bake(S, None, False)
lam0, dl, cols, phi0, dp, rows, _ = gt.grid(True)
G = gt.grid(False)
lam = lam0 + (np.arange(cols) + 0.5) * dl
phi = phi0 + (np.arange(rows) + 0.5) * dp
x = (lam - G[0]) / G[1] - 0.5
y = (phi - G[3]) / G[4] - 0.5
x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
fx, fy = (x - x0)[None, :], (y - y0)[:, None]


def bil(a):
    a00, a10 = a[np.ix_(y0, x0 % G[2])], a[np.ix_(y0, (x0 + 1) % G[2])]
    a01, a11 = a[np.ix_(y0 + 1, x0 % G[2])], a[np.ix_(y0 + 1, (x0 + 1) % G[2])]
    return (a00 * (1 - fx) + a10 * fx) * (1 - fy) + (a01 * (1 - fx) + a11 * fx) * fy


wet_r = (wr - hr > 0.0) & (wr > INLAND)
wg_at, hg_at = bil(wg), bil(hg)
wet_g = (wg_at - hg_at > 0.0) & (wg_at > INLAND)
R = gt.fl.R
coslat = np.cos(phi)[:, None]
m_lam, m_phi = dl * R * coslat, dp * R
wd_r = width(wet_r, m_lam, m_phi)
# the 12 m map's own channel widths, on its own texels inside the box
gx = np.arange(int(x.min()), int(x.max()) + 1) % G[2]
gy = np.arange(int(y.min()), int(y.max()) + 1)
wet_gg = (wg[np.ix_(gy, gx)] - hg[np.ix_(gy, gx)] > 0.0) & (wg[np.ix_(gy, gx)] > INLAND)
phig = G[3] + (gy + 0.5) * G[4]
wd_g = width(wet_gg, G[1] * R * np.cos(phig)[:, None], G[4] * R)
missed = wet_r & ~wet_g
fl_r = np.abs(fr.astype(np.float32)).sum(-1) > 1e-6
wet_rh = gt.half((wr - hr)[..., None])[..., 0] > 0.0
wet_rh &= gt.half(wr[..., None])[..., 0] > INLAND
gyh, gxh = np.unique(gy // 2), np.unique(gx // 2)
wet_gh = (gt.half((wg - hg)[..., None])[..., 0] > 0.0) & (gt.half(wg[..., None])[..., 0] > INLAND)
fl_g = np.abs(fg.astype(np.float32)).sum(-1) > 1e-6
sub = np.ix_(gyh, gxh)
res = {
    "region_texels": [cols, rows], "region_m": gt.REGION, "inland_over_m": INLAND,
    "wet_share_4m": round(float(wet_r.mean()), 5), "wet_share_12m": round(float(wet_g.mean()), 5),
    "wet_km2_4m": round(float((wet_r * m_lam * m_phi).sum()) / 1e6, 3),
    "wet_km2_12m": round(float((wet_g * m_lam * m_phi).sum()) / 1e6, 3),
    "missed_by_12m_km2": round(float((missed * m_lam * m_phi).sum()) / 1e6, 3),
    "missed_under_25m_km2": round(float((missed * (wd_r < 25.0) * m_lam * m_phi).sum()) / 1e6, 3),
    "width_hist_4m_texels": hist(wd_r, wet_r), "width_hist_12m_texels": hist(wd_g, wet_gg),
    "flow_set_share_of_wet_region": round(float((fl_r & wet_rh).sum() / max(wet_rh.sum(), 1)), 4),
    "flow_set_share_of_wet_12m_box": round(float((fl_g[sub] & wet_gh[sub]).sum() / max(wet_gh[sub].sum(), 1)), 4),
}
json.dump(res, open(JOB["out"], "w"), indent=1)
DN["wm_result"] = res
