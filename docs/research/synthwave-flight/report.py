"""Turns a recorder.py run into proof files: python3 report.py RUN_DIR [TITLE]

Writes into RUN_DIR:
- trace.svg / trace.png: frame time (every drawn frame) and frame difference (between 15 Hz grabs) over time, with
  the Flight stage, the blends and the detected spikes marked;
- sheet.png: a contact sheet of every 15th grab, labelled with time, stage and height;
- run.mp4: the grabs as a video (15 fps);
- summary.json: fps (p50 / p95 / worst frame), frame-difference spikes (a grab over 3x the rolling median of its
  neighbours and over 3 levels), stage times, and the motion trace: drawn frames where the On-Air Camera neither
  moved nor turned (EN1), the smallest move and turn between frames.
"""
import json
import os
import subprocess
import sys

run = sys.argv[1]
title = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(run)
d = json.load(open(os.path.join(run, "trace.json")))
draws, grabs = d["draws"], [g for g in d["grabs"] if "err" not in g]
STAGES = ("Orbit", "Approach", "Skim", "Hover")


def pct(vals, q):
    v = sorted(vals)
    return v[min(len(v) - 1, int(q * len(v)))] if v else None


ms = [x[1] for x in draws]
spikes = []
for k, g in enumerate(grabs):
    win = [x["diff"] for x in grabs[max(1, k - 7):k + 8] if x is not g]
    med = sorted(win)[len(win) // 2] if win else 0.0
    if k > 0 and g["diff"] > 3.0 * med and g["diff"] > 3.0 and not g.get("blend"):
        spikes.append({"t": g["t"], "diff": g["diff"], "median": med, "stage": g.get("stage"), "alt": g.get("alt")})
still = [x for x in draws if len(x) > 5 and x[5]]
moved = [x for x in draws if len(x) > 3]
summary = {"title": title, "seconds": draws[-1][0] if draws else 0, "frames": len(draws),
           "fps_mean": round(len(draws) / max(draws[-1][0] - draws[0][0], 1e-9), 1) if draws else None,
           "frame_ms_p50": pct(ms, 0.5), "frame_ms_p95": pct(ms, 0.95), "frame_ms_max": max(ms) if ms else None,
           "grabs": len(grabs), "diff_spikes": spikes,
           "still_frames": len(still), "still_at": [x[0] for x in still[:20]],
           "move_mm_min": min((x[2] for x in moved), default=None), "turn_mdeg_min": min((x[3] for x in moved), default=None),
           "motion_min": min((max(x[2], x[3]) for x in moved), default=None), "program": d["program"]}
json.dump(summary, open(os.path.join(run, "summary.json"), "w"), indent=1)

# the trace plot
W, H, M = 1400, 520, 60
t1 = max(draws[-1][0] if draws else 1.0, grabs[-1]["t"] if grabs else 1.0)
X = lambda t: M + (W - 2 * M) * t / t1
top_h = (H - 3 * M) / 2


def Y1(v):
    return M + top_h * (1.0 - min(v, 100.0) / 100.0)


dmax = max([g["diff"] for g in grabs] + [10.0])


def Y2(v):
    return 2 * M + top_h + top_h * (1.0 - v / dmax)


svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" font-family="Helvetica" font-size="12">' % (W, H),
       '<rect width="100%" height="100%" fill="#14101f"/>',
       '<text x="%d" y="24" fill="#f4e9ff" font-size="16">%s</text>' % (M, title)]
cols = ("#3a2a5a", "#2a3a5a", "#3a2a3a", "#1f3a40")
prev = None
for g in grabs:                                  # stage bands
    st = int(g.get("stage", -1))
    if st >= 0 and st != prev:
        svg.append('<text x="%.1f" y="%d" fill="#c9b8ff">%s</text>' % (X(g["t"]) + 3, M - 6, STAGES[st]))
        svg.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="#5c4a8a" stroke-dasharray="3,3"/>' % (X(g["t"]), M, X(g["t"]), H - M))
        prev = st
    if g.get("blend"):
        svg.append('<rect x="%.1f" y="%d" width="3" height="%d" fill="#ff7ad9" opacity="0.25"/>' % (X(g["t"]), M, H - 2 * M))
for lv, lab in ((16.7, "60 fps"), (33.3, "30 fps")):
    svg.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#8a7cff" stroke-dasharray="4,4"/>' % (M, Y1(lv), W - M, Y1(lv)))
    svg.append('<text x="%d" y="%.1f" fill="#8a7cff">%s</text>' % (W - M + 4, Y1(lv) + 4, lab))
svg.append('<polyline fill="none" stroke="#5ef2ff" stroke-width="1" points="%s"/>' % " ".join("%.1f,%.1f" % (X(x[0]), Y1(x[1])) for x in draws))
svg.append('<text x="%d" y="%d" fill="#5ef2ff">frame time (ms, 0-100)</text>' % (M, M + 14))
svg.append('<polyline fill="none" stroke="#ff9e5e" stroke-width="1.5" points="%s"/>' % " ".join("%.1f,%.1f" % (X(g["t"]), Y2(g["diff"])) for g in grabs))
svg.append('<text x="%d" y="%.1f" fill="#ff9e5e">frame difference between grabs (mean |delta|, 0-%.0f)</text>' % (M, 2 * M + top_h + 14, dmax))
for s in spikes:
    svg.append('<circle cx="%.1f" cy="%.1f" r="5" fill="none" stroke="#ff3b6b" stroke-width="2"/>' % (X(s["t"]), Y2(s["diff"])))
for x in still:
    svg.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="#ff3b6b"/>' % (X(x[0]), M, X(x[0]), M + 8))
svg.append('<text x="%d" y="%d" fill="#f4e9ff">fps mean %s, frame ms p50 %s, p95 %s, worst %s; %d frame-difference spikes outside blends; %d still frames</text>'
           % (M, H - 18, summary["fps_mean"], summary["frame_ms_p50"], summary["frame_ms_p95"], summary["frame_ms_max"], len(spikes), len(still)))
svg.append("</svg>")
open(os.path.join(run, "trace.svg"), "w").write("\n".join(svg))
subprocess.run(["magick", os.path.join(run, "trace.svg"), os.path.join(run, "trace.png")], check=False)

# contact sheet and video
pick = grabs[::max(1, len(grabs) // 24)]
args = ["magick", "montage"]
for g in pick:
    st = int(g.get("stage", -1))
    args += ["-label", "%.0fs %s %.0fm" % (g["t"], STAGES[st] if st >= 0 else "", g.get("alt", 0)), os.path.join(run, "f%05d.ppm" % g["i"])]
args += ["-tile", "6x", "-geometry", "320x180+4+4", "-background", "#14101f", "-fill", "#f4e9ff", os.path.join(run, "sheet.png")]
subprocess.run(args, check=False)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "15", "-i", os.path.join(run, "f%05d.ppm"),
                "-pix_fmt", "yuv420p", "-vf", "scale=960:540", os.path.join(run, "run.mp4")], check=False)
print(json.dumps({k: v for k, v in summary.items() if k != "program"}, indent=1)[:1500])
