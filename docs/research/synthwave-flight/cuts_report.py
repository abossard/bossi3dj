"""Per-shot frame times of a recorder.py run that cuts through the shots: python3 cuts_report.py RUN

For each /vj/cam step of the program: the first frames after the change, the worst frame (M1: 70 ms or less on a
cut), and the rest frame time p50 / p95 after the first SETTLE frames. Prints a Markdown table.
"""
import json
import os
import sys

SETTLE = 5
d = json.load(open(os.path.join(sys.argv[1], "trace.json")))
draws = d["draws"]
steps = [(t, v["vj_cam"]) for t, v in d["program"] if "vj_cam" in v]
end = draws[-1][0] if draws else 0.0
print("| Shot | First frames ms | Worst ms | Rest p50 ms (fps) | Rest p95 ms | Still frames |")
print("|---|---|---|---|---|---|")
for i, (t, cam) in enumerate(steps):
    seg = [x for x in draws if t <= x[0] < (steps[i + 1][0] if i + 1 < len(steps) else end + 1)]
    if not seg:
        continue
    rest = sorted(x[1] for x in seg[SETTLE:]) or [float("nan")]
    p50 = rest[len(rest) // 2]
    print("| CAM_%d | %s | %.0f | %.1f (%.1f) | %.1f | %d |" % (int(cam), ", ".join("%.0f" % x[1] for x in seg[:4]), max(x[1] for x in seg),
                                                     p50, 1000.0 / p50, rest[int(0.95 * len(rest))], sum(x[5] for x in seg if len(x) > 5)))
