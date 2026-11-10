"""Sums up recorder.py energy runs (docs/research/synthwave-flight.md, "Energy controls"): python3 energy_report.py RUN...

For each run: the frames where the On-Air Camera stood still (EN1) after the first SETTLE s, the camera's speed
(m/s) and turn (deg/s) per energy band (EN2, EN4), the widest lens within 2 s of each hit against the lens just
before it and how much of that it took on its first frame (EN3), and fps. Prints a Markdown table and writes energy_summary.json next to the runs.
"""
import json
import os
import sys

SETTLE = 8.0           # s: the cut and its first draw; the program's energy steps start here


def band(e):
    return "low" if e < 0.15 else "default" if e < 0.45 else "high" if e > 0.85 else "mid"


def energy_at(t, grabs):
    g = min(grabs, key=lambda g: abs(g["t"] - t))
    return g.get("energy", 0.3)


rows = []
for run in sys.argv[1:]:
    d = json.load(open(os.path.join(run, "trace.json")))
    draws = [x for x in d["draws"] if len(x) > 5]
    grabs = [g for g in d["grabs"] if "err" not in g]
    live = [x for x in draws if x[0] >= SETTLE]
    still = [x for x in live if x[5]]
    hits = [t for t, v in d["program"] if v.get("vj_hit", 0.0) >= 0.5]
    speed = {}
    for x in live:
        if any(0.0 <= x[0] - t < 2.5 for t in hits):        # the hit's swoop is no energy band
            continue
        b = band(energy_at(x[0], grabs))
        s = speed.setdefault(b, [0.0, 0.0, 0])
        s[0] += x[2] / max(x[1], 1e-3)          # mm per ms = m/s
        s[1] += x[3] / max(x[1], 1e-3)          # mdeg per ms = deg/s
        s[2] += 1
    kicks = []
    for t in hits:                         # the lens on every drawn frame, against the last frame before the hit
        before = [x[4] for x in draws if t - 1.0 <= x[0] < t]
        after = [x for x in draws if t <= x[0] < t + 2.0]
        if before and after:
            # after[0] is the frame drawn as the hit was applied; the runtime reads it on the next frame change
            first = after[1] if len(after) > 1 else after[0]
            kicks.append((round(min(x[4] for x in after) / before[-1], 3), round((1.0 - first[4] / before[-1]) / 0.3, 3)))
    ms = sorted(x[1] for x in live)
    first = max((x[1] for x in draws if x[0] < SETTLE), default=None)
    rows.append({"run": os.path.basename(run.rstrip("/")), "frames": len(live), "still": len(still),
                 "speed_ms": {k: round(v[0] / v[2], 3) for k, v in speed.items()},
                 "turn_degs": {k: round(v[1] / v[2], 3) for k, v in speed.items()},
                 "hit_lens": kicks, "fps": round(len(live) / max(live[-1][0] - live[0][0], 1e-9), 1) if live else None,
                 "ms_p50": ms[len(ms) // 2] if ms else None, "ms_p95": ms[int(0.95 * len(ms))] if ms else None,
                 "worst_cut_frame_ms": first})
json.dump(rows, open(os.path.join(os.path.dirname(sys.argv[1].rstrip("/")), "energy_summary.json"), "w"), indent=1)
print("| Run | Still frames | Speed m/s low / default / high | Turn deg/s low / default / high | Lens at hits | fps | p50 / p95 ms | Cut frame ms |")
print("|---|---|---|---|---|---|---|---|")
for r in rows:
    sp, tu = r["speed_ms"], r["turn_degs"]
    print("| %s | %d of %d | %s / %s / %s | %s / %s / %s | %s | %s | %s / %s | %s |" % (
        r["run"], r["still"], r["frames"], sp.get("low"), sp.get("default"), sp.get("high"), tu.get("low"), tu.get("default"),
        tu.get("high"), ", ".join("%.2fx (%.0f%% of the kick on its first frame)" % (k, 100 * f) for k, f in r["hit_lens"]), r["fps"], r["ms_p50"], r["ms_p95"], r["worst_cut_frame_ms"]))
