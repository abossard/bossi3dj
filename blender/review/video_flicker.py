"""Flicker numbers of a recording, per stage: .venv/bin/python blender/review/video_flicker.py VIDEO [STAGE_S]
Decodes VIDEO with ffmpeg as luminance at 960x540, drops repeated frames (a slow sender's repeats, mean change under
0.05), and per pair of new frames takes the mean absolute luminance difference (0..255) and the toggle share (pixels
that step over 16 one way and back the next frame). Prints JSON: overall mean, p95, toggles and frames over 30, then
the same per STAGE_S (default 15) seconds of the video."""
import json
import subprocess
import sys

import numpy as np

W, H = 960, 540
video = sys.argv[1]
stage = float(sys.argv[2]) if len(sys.argv) > 2 else 15.0
fps = float(subprocess.run(["ffprobe", "-v", "0", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                            "-of", "csv=p=0", video], capture_output=True, text=True).stdout.strip().split("/")[0]) or 30.0
raw = subprocess.run(["ffmpeg", "-v", "0", "-i", video, "-vf", "scale=%d:%d" % (W, H), "-pix_fmt", "gray", "-f", "rawvideo", "-"],
                     capture_output=True).stdout
frames = np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype(np.int16)
new, times = [frames[0]], [0.0]
for i in range(1, len(frames)):
    if np.abs(frames[i] - new[-1]).mean() >= 0.05:
        new.append(frames[i])
        times.append(i / fps)
rows = []
for k in range(1, len(new)):
    d = new[k] - new[k - 1]
    tog = 0.0
    if k + 1 < len(new):
        e = new[k + 1] - new[k]
        tog = float(((np.abs(d) > 16) & (np.abs(e) > 16) & (np.sign(d) != np.sign(e))).mean())
    rows.append((times[k], float(np.abs(d).mean()), tog))
t, m, g = (np.array(x) for x in zip(*rows))


def summary(sel):
    return {"mean": round(float(m[sel].mean()), 2), "p95": round(float(np.percentile(m[sel], 95)), 2),
            "toggles": round(float(g[sel].mean()), 4), "over30": int((m[sel] > 30).sum()), "new_frames": int(sel.sum())}


out = {"video": video, "frames": len(frames), "new_frames": len(new), "all": summary(np.ones(len(t), bool)), "stages": []}
for s0 in np.arange(0.0, t.max() + 1e-6, stage):
    sel = (t >= s0) & (t < s0 + stage)
    if sel.any():
        out["stages"].append(dict({"from_s": float(s0)}, **summary(sel)))
print(json.dumps(out))
