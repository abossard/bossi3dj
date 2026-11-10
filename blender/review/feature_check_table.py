#!/usr/bin/env python3
"""Markdown tables from the JSON of `make blender-check`, for docs/reports/blender-feature-check.md.

    python3 blender/review/feature_check_table.py blender/review/out/feature_check_Scene.json
"""
import json
import sys


def main(path):
    report = json.load(open(path))
    check = report["check"]
    print("| control | range | default | verdict | cam | mad (floor) | bias (floor) | x floor | readers | note |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for r in check["rows"]:
        rd = r["readers"]
        readers = "%dn %dd%s" % (rd["nodes"], rd["drivers"], " py" if rd.get("python") else "")
        mad = "%.3f (%.3f)" % (r["effect_mad"], r["floor_mad"]) if "effect_mad" in r else "-"
        bias = "%.3f (%.3f)" % (r["effect_bias"], r["floor_bias"]) if "effect_bias" in r else "-"
        ratio = "%g" % r["ratio"] if "ratio" in r else "-"
        print("| `%s` | %g..%g | %g | %s | %s | %s | %s | %s | %s | %s |" % (
            r["address"], r["min"], r["max"], r["default"], r["verdict"], r.get("cam", "-"), mad, bias, ratio, readers,
            r.get("note", "").replace("|", "/")))
    print()
    print("counts: %s; noise floor %s; defaults restored: %s; state equals defaults: %s; holds released: %s" % (
        check.get("counts"), check.get("noise_floor"), check.get("defaults_restored"),
        report.get("state_equals_defaults"), report.get("holds_released")))
    print()
    print("| address | kind | detail |")
    print("|---|---|---|")
    for m in report.get("contract", []):
        print("| `%s` | %s | %s |" % (m["address"], m["kind"], m["detail"]))
    if report.get("bridge_check"):
        print("\n| message | property | expected | got | ok |")
        print("|---|---|---|---|---|")
        for b in report["bridge_check"]:
            print("| `%s %g` | %s | %s | %s | %s |" % (b["address"], b["wire"], b.get("property") or "none (ignored +%s)" % b.get("ignored"),
                                                 b.get("expected", "-"), b.get("got", "-"), "yes" if b["ok"] else "NO"))
    probe = report.get("osc_probe")
    if probe:
        print("\nudp 9201: sent %(sent)d, received %(received)d, applied %(applied)d, errors %(errors)d, not seen %(missing)s" % probe)


if __name__ == "__main__":
    main(sys.argv[1])
