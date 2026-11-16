"""Pixel check of the encoded Shadow and Depth Pass files against their source frames, one frame of one Clip.

    .venv/bin/python robot/build/review/pass_check.py --package robot/package/v1 --clip jab_cross__side --frame 29
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import encode_passes as ep  # noqa: E402


def frame(path, n, fmt="gray16le"):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", "select=eq(n\\,%d)" % n, "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", fmt, "-"], check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype="<u2" if fmt in ("gray16le", "rgba64le") else np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--clip", required=True)
    ap.add_argument("--frame", type=int, required=True)
    a = ap.parse_args()
    p, c, n = a.package, a.clip, a.frame
    src_cov = frame(os.path.join(p, "shadow", c, "%04d.png" % n), 0, "rgba64le").reshape(-1, 4)[:, 3] / 65535.0
    got_cov = frame(os.path.join(p, "shadow", c + ".mov"), n) / 65535.0
    depth_m = ep.read_exr_depth(os.path.join(p, "depth", c, "%04d.exr" % n)).ravel()
    alpha = frame(os.path.join(p, "beauty", c + ".mov"), n, "rgba").reshape(-1, 4)[:, 3]
    want = np.where(alpha == 0, 1.0, np.clip(depth_m / ep.DEPTH_RANGE_M, 0, 1))
    got = frame(os.path.join(p, "depth", c + ".mov"), n) / 65535.0
    on = alpha > 0
    print(json.dumps({
        "shadow": {"src_max": round(float(src_cov.max()), 4), "got_max": round(float(got_cov.max()), 4),
                   "got_where_src_0_max": round(float(got_cov[src_cov == 0].max()), 4),
                   "abs_diff_mean": round(float(np.abs(got_cov - src_cov).mean()), 5),
                   "abs_diff_max": round(float(np.abs(got_cov - src_cov).max()), 4)},
        "depth": {"android_pixels": int(on.sum()),
                  "android_metres_min_max": [round(float(depth_m[on].min()), 3), round(float(depth_m[on].max()), 3)],
                  "got_android_min_max": [round(float(got[on].min()), 4), round(float(got[on].max()), 4)],
                  "got_where_absent_min": round(float(got[~on].min()), 4),
                  "abs_diff_mean": round(float(np.abs(got - want).mean()), 5),
                  "abs_diff_max_android": round(float(np.abs(got - want)[on].max()), 4)}}, indent=1))


if __name__ == "__main__":
    main()
