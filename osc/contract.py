"""The /vj/* contract as data. contract.json is the one source; this module reads it and
writes its two copies that cannot import it:

    python3 osc/contract.py sync     rewrite the table in CONTROLS.md and the SCALES block in blender/blender_osc_bridge.py
    python3 osc/contract.py check    exit 1 when either copy is out of step (tests/test_contract.py does the same)
    python3 osc/contract.py table    print the table

Standard library only. Wire units: a continuous control is 0..1, an index is an integer, a trigger keeps its strength.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONTRACT_JSON = os.path.join(HERE, "contract.json")
CONTROLS_MD = os.path.join(HERE, "CONTROLS.md")
BRIDGE_PY = os.path.join(ROOT, "blender", "blender_osc_bridge.py")

TABLE_BEGIN, TABLE_END = "<!-- contract-table:begin -->", "<!-- contract-table:end -->"
SCALES_BEGIN = "# --- contract:begin (generated from osc/contract.json by `python3 osc/contract.py sync`, do not edit) ---"
SCALES_END = "# --- contract:end ---"


def load(path=CONTRACT_JSON):
    with open(path) as f:
        return json.load(f)["controls"]


def by_address(rows=None):
    return {r["address"]: r for r in (rows or load())}


def scene_value(row, who, wire):
    """The value `who` ("blender" or "godot") works with for a wire value. Floats scale linearly
    onto the scene range, an index rounds to an integer inside the wire range, a trigger passes through.
    None when the scene does not use the address."""
    scene = row.get(who)
    if scene is None:
        return None
    if row["kind"] == "trigger":
        return float(wire)
    wire = min(max(float(wire), row["min"]), row["max"])
    if row["kind"] == "int":
        return int(round(wire))
    u = (wire - row["min"]) / (row["max"] - row["min"])
    return scene["min"] + u * (scene["max"] - scene["min"])


# ---------------------------------------------------------------- renderings

def _g(v):
    return "%g" % v


def _wire(row):
    if row["kind"] == "float":
        return "0..1, default %s" % _g(row["default"])
    if row["kind"] == "int":
        return "integer %s..%s, default %s" % (_g(row["min"]), _g(row["max"]), _g(row["default"]))
    return "trigger 0..%s, default %s" % (_g(row["max"]), _g(row["default"]))


def _cell(row, who):
    scene = row.get(who)
    if scene is None:
        return "not used"
    if "min" in scene and row["kind"] == "float":
        unit = (" " + scene["unit"]) if scene.get("unit") else ""
        at = scene_value(row, who, row["default"])
        head = "%s..%s%s, default %s. " % (_g(scene["min"]), _g(scene["max"]), unit, "%.4g" % at)
        if scene["min"] == 0 and scene["max"] == 1 and not unit:
            head = ""
        return head + scene["effect"]
    return scene["effect"]


def render_table(rows=None):
    lines = ["| Address | Wire | Blender (`blender/scenes`) | Godot (`godot/colossus`) |", "|---|---|---|---|"]
    for r in rows or load():
        lines.append("| `%s` | %s | %s | %s |" % (r["address"], _wire(r), _cell(r, "blender"), _cell(r, "godot")))
    return "\n".join(lines)


def render_scales(rows=None):
    """The SCALES dict the bridge embeds: address -> (kind, wire min, wire max, scene min, scene max), Blender rows only."""
    out = [SCALES_BEGIN, "SCALES = {"]
    for r in rows or load():
        b = r.get("blender")
        if b is None:
            continue
        smin, smax = (b.get("min"), b.get("max")) if r["kind"] == "float" else (None, None)
        out.append("    %r: (%r, %r, %r, %r, %r)," % (r["address"], r["kind"], r["min"], r["max"], smin, smax))
    out += ["}", SCALES_END]
    return "\n".join(out)


def _between(text, begin, end):
    i, j = text.index(begin), text.index(end)
    return i + len(begin), j


def spliced(text, begin, end, body, keep_markers):
    i, j = _between(text, begin, end)
    if keep_markers:
        return text[:i] + "\n" + body + "\n" + text[j:]
    return text[:text.index(begin)] + body + text[j + len(end):]


def current_table(text):
    i, j = _between(text, TABLE_BEGIN, TABLE_END)
    return text[i:j].strip("\n")


def current_scales(text):
    return text[text.index(SCALES_BEGIN):text.index(SCALES_END) + len(SCALES_END)]


def sync():
    rows = load()
    for path, begin, end, body, keep in ((CONTROLS_MD, TABLE_BEGIN, TABLE_END, render_table(rows), True),
                                         (BRIDGE_PY, SCALES_BEGIN, SCALES_END, render_scales(rows), False)):
        with open(path) as f:
            text = f.read()
        new = spliced(text, begin, end, body, keep)
        if new != text:
            with open(path, "w") as f:
                f.write(new)
            print("wrote", os.path.relpath(path, ROOT))


def stale():
    rows = load()
    out = []
    with open(CONTROLS_MD) as f:
        if current_table(f.read()) != render_table(rows):
            out.append("osc/CONTROLS.md table")
    with open(BRIDGE_PY) as f:
        if current_scales(f.read()) != render_scales(rows):
            out.append("blender/blender_osc_bridge.py SCALES")
    return out


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "check"
    if cmd == "sync":
        sync()
    elif cmd == "table":
        print(render_table())
    elif cmd == "check":
        s = stale()
        for name in s:
            print("out of step with contract.json:", name)
        return 1 if s else 0
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
