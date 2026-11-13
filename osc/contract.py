"""The /vj/* contract as data. contract.json is the one source; this module reads it and
writes its three copies that cannot import it:

    python3 osc/contract.py sync     rewrite the table in CONTROLS.md, the SCALES block in blender/blender_osc_bridge.py and
                                     the manual for viewers in README.md (between the osc-manual markers)
    python3 osc/contract.py check    exit 1 when a copy is out of step (tests/test_contract.py does the same)
    python3 osc/contract.py table    print the table
    python3 osc/contract.py manual   print the README manual

The manual is made from each row's `group` and `plain` fields (one everyday sentence on what a viewer sees change) and
from the pictures that exist in docs/images/readme/osc/: <name>-blender.jpg and <name>-godot.jpg, name = the address
without /vj/. A cell without a file stays empty.

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
README_MD = os.path.join(ROOT, "README.md")
MANUAL_IMAGES = os.path.join("docs", "images", "readme", "osc")      # relative to ROOT, as the README links it

TABLE_BEGIN, TABLE_END = "<!-- contract-table:begin -->", "<!-- contract-table:end -->"
MANUAL_BEGIN, MANUAL_END = "<!-- osc-manual:begin -->", "<!-- osc-manual:end -->"
GROUPS = ["Light and colour", "Sky, sun and moon", "Ground, water and things on it", "Fog", "Camera", "Triggers", "Godot only"]
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


def _scenes(row):
    return {(True, True): "both", (True, False): "Blender", (False, True): "Godot"}[(bool(row["blender"]), bool(row["godot"]))]


def _pictures(row, root=ROOT):
    """The picture cell: one image per scene that has a file, a pair low | high (before | during for a trigger, the shots for /vj/cam)."""
    name = row["address"][len("/vj/"):]
    what = "before | during" if row["kind"] == "trigger" else "the shots" if row["address"] == "/vj/cam" else "low | high"
    out = []
    for who, label in (("blender", "Blender"), ("godot", "Godot")):
        rel = os.path.join(MANUAL_IMAGES, "%s-%s.jpg" % (name, who)).replace(os.sep, "/")
        if row[who] and os.path.exists(os.path.join(root, rel)):
            out.append('<img src="%s" width="360" alt="%s, %s: %s"><br><sub>%s, %s</sub>' % (rel, row["address"], label, what, label, what))
    return "<br>".join(out)


SHOT_SCENES = [("godot", "Godot, Colossus")]


def shot_picture(scene, index, root=ROOT):
    rel = os.path.join(MANUAL_IMAGES, "cam-%s-%d.jpg" % (scene, index)).replace(os.sep, "/")
    if os.path.exists(os.path.join(root, rel)):
        return '<img src="%s" width="200" alt="%s, shot %d">' % (rel, scene, index)
    return ""


def render_shots(row, root=ROOT):
    """The cameras part under /vj/cam: per scene one table of number, name, what it shows and a small picture."""
    out = ["", "**Cameras for `/vj/cam`**: the number picks the shot.", ""]
    for key, label in SHOT_SCENES:
        shots = row.get("shots", {}).get(key) or []
        if not shots:
            out += ["*%s*: the shots are not listed yet." % label, ""]
            continue
        out += ["*%s*" % label, "", "| Number | Name | What it shows | Picture |", "|---|---|---|---|"]
        out += ["| %d | %s | %s | %s |" % (s["index"], s["name"], s["shows"], shot_picture(key, s["index"], root)) for s in shots]
        out.append("")
    return out


def render_manual(rows=None, root=ROOT):
    """The README manual: one small table per group, the first group open, the others folded."""
    rows = rows or load()
    out = []
    for i, group in enumerate(GROUPS):
        members = [r for r in rows if r["group"] == group]
        out += ["<details%s>" % (" open" if i == 0 else ""), "<summary><b>%s</b> (%d)</summary>" % (group, len(members)), "",
                "| Address | What you see | Wire | Scene | Picture |", "|---|---|---|---|---|"]
        for r in members:
            out.append("| `%s` | %s | %s | %s | %s |" % (r["address"], r["plain"], _wire(r), _scenes(r), _pictures(r, root)))
        for r in members:
            if r.get("shots") is not None:
                out += render_shots(r, root)
        out += ["", "</details>", ""]
    return "\n".join(out).rstrip("\n")


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


def current_manual(text):
    i, j = _between(text, MANUAL_BEGIN, MANUAL_END)
    return text[i:j].strip("\n")


def current_scales(text):
    return text[text.index(SCALES_BEGIN):text.index(SCALES_END) + len(SCALES_END)]


def sync():
    rows = load()
    for path, begin, end, body, keep in ((CONTROLS_MD, TABLE_BEGIN, TABLE_END, render_table(rows), True),
                                         (BRIDGE_PY, SCALES_BEGIN, SCALES_END, render_scales(rows), False),
                                         (README_MD, MANUAL_BEGIN, MANUAL_END, render_manual(rows), True)):
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
    with open(README_MD) as f:
        if current_manual(f.read()) != render_manual(rows):
            out.append("README.md manual")
    return out


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "check"
    if cmd == "sync":
        sync()
    elif cmd == "table":
        print(render_table())
    elif cmd == "manual":
        print(render_manual())
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
