"""score.py <version> -> per-query trigger rate and train/test accuracy (threshold 0.5)."""
import glob, json, sys, os
here = os.path.dirname(os.path.abspath(__file__))
v = sys.argv[1]
q = {str(x["id"]): x for x in json.load(open(os.path.join(here, "queries.json")))}
runs = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(here, "%s_run*.json" % v)))]
acc = {"train": [0, 0], "test": [0, 0]}
rows = []
for i, x in q.items():
    rate = sum(r.get(i) == "magic-projects" for r in runs) / len(runs)
    ok = (rate >= 0.5) == x["should_trigger"]
    acc[x["split"]][0] += ok; acc[x["split"]][1] += 1
    rows.append({"id": int(i), "split": x["split"], "should": x["should_trigger"], "rate": round(rate, 2), "ok": ok,
                 "picks": [r.get(i) for r in runs], "query": x["query"]})
out = {"version": v, "runs": len(runs), "train": "%d/%d" % tuple(acc["train"]), "test": "%d/%d" % tuple(acc["test"]),
       "queries": sorted(rows, key=lambda r: r["id"])}
json.dump(out, open(os.path.join(here, "%s_score.json" % v), "w"), indent=1)
print(v, "runs", len(runs), "train", out["train"], "test", out["test"])
for r in out["queries"]:
    if not r["ok"]:
        print("  MISS", r["split"], "should" if r["should"] else "should-not", r["rate"], r["picks"], r["query"][:90])
