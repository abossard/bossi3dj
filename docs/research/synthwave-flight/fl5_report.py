"""FL5 from recorder.py sweep runs (docs/research/synthwave-flight.md, "Perf budget"): python3 fl5_report.py RUN...

Each run starts on fixed shots (the baseline under the same load and grabs), then flies the Flight. Every drawn frame
takes the shot and the Flight stage of the grab before it; the first SETTLE s after a shot change are left out (the
cut). FL5 passes for a stage when its p50 frame time is within 10% of the fixed shots' mean p50 and its p95 within
20% of their mean p95. Prints a Markdown table.
"""
import json
import os
import sys

SETTLE = 2.0
STAGES = ("Orbit", "Approach", "Skim", "Hover")


def pct(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, int(q * len(v)))]


print("| Run | Segment | Frames | p50 ms (fps) | p95 ms | FL5 |")
print("|---|---|---|---|---|---|")
for run in sys.argv[1:]:
    d = json.load(open(os.path.join(run, "trace.json")))
    grabs = [g for g in d["grabs"] if "err" not in g]
    seg, changed, gi = {}, None, 0
    for x in d["draws"]:
        while gi + 1 < len(grabs) and grabs[gi + 1]["t"] <= x[0]:
            gi += 1
        g = grabs[gi]
        flight = g.get("shot") == "CAM_11"
        key = STAGES[int(g["stage"])] if flight and g.get("stage", -1) >= 0 else g.get("shot")
        if key != changed:
            changed, since = key, x[0]
        if x[0] - since >= SETTLE and key is not None:
            seg.setdefault(key, []).append(x[1])
    fixed = [v for k, v in seg.items() if k not in STAGES and len(v) > 20]
    base50 = sum(pct(v, 0.5) for v in fixed) / max(len(fixed), 1)
    base95 = sum(pct(v, 0.95) for v in fixed) / max(len(fixed), 1)
    for k, v in seg.items():
        if len(v) < 20:
            continue
        p50, p95 = pct(v, 0.5), pct(v, 0.95)
        verdict = ("pass" if p50 <= 1.1 * base50 and p95 <= 1.2 * base95 else "fail") if k in STAGES else "baseline"
        print("| %s | %s | %d | %.1f (%.1f) | %.1f | %s |" % (os.path.basename(run), k, len(v), p50, 1000.0 / p50, p95, verdict))
    print("| %s | fixed mean | | %.1f | %.1f | |" % (os.path.basename(run), base50, base95))
