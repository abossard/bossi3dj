#!/usr/bin/env python3
"""The QLC+ fixture for the Blender scene's Art-Net input, made from osc/contract.json.

    python3 osc/qlc_fixture.py sync    write qlc/bossi3dj-Synthwave-Planet.qxf and the channel table in docs/artnet-qlc.md
    python3 osc/qlc_fixture.py check   exit 1 when either is out of step with the contract (tests/test_qlc_fixture.py does the same)
    python3 osc/qlc_fixture.py table   print the channel table

One fixture, one mode, one DMX channel per address the Blender scene reacts to, in contract order (the order of
blender/blender_osc_bridge.py's SCALES and of blender/artnet_input.py's channel map). The channel's capabilities carry the
rows' plain sentences; /vj/cam has one range per shot of the planet scene (the island has 7 shots: its ranges are in the
doc). Standard library only. The format is QLC+ 4.12's fixture definition (a copy of the shape of the .qxf files that
ship in /Applications/QLC+.app/Contents/Resources/Fixtures).
"""
import os
import sys
from xml.sax.saxutils import escape, quoteattr

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import contract  # noqa: E402

QLC_DIR = os.path.join(ROOT, "qlc")
FIXTURE = os.path.join(QLC_DIR, "bossi3dj-Synthwave-Planet.qxf")
DOC = os.path.join(ROOT, "docs", "artnet-qlc.md")
TABLE_BEGIN, TABLE_END = "<!-- artnet-channels:begin -->", "<!-- artnet-channels:end -->"
MANUFACTURER, MODEL, MODE = "bossi3dj", "Synthwave Planet", "Synthwave"
TRIGGER_AT = 128


def blender_rows(rows=None):
    return [r for r in (rows or contract.load()) if r.get("blender")]


def shot_ranges(n):
    """[(first DMX value, last DMX value)] of n equal ranges of 0..255, the split blender/artnet_input.py decodes (v * n // 256)."""
    out = []
    for i in range(n):
        lo = -(-i * 256 // n)
        hi = -(-(i + 1) * 256 // n) - 1
        out.append((lo, hi))
    return out


def planet_shots(row):
    return row["shots"]["planet"]


def default_dmx(row):
    if row["kind"] != "float":
        return 0
    return int(round((row["default"] - row["min"]) / (row["max"] - row["min"]) * 255))


def _group(row):
    if row["address"] == "/vj/hue":
        return "Colour"
    return "Intensity" if row["group"] == "Light and colour" else "Effect"


def capabilities(row):
    """[(min, max, text)] of one channel."""
    if row["kind"] == "trigger":
        return [(0, TRIGGER_AT - 1, "off"), (TRIGGER_AT, 255, "fire once, harder the higher: " + row["plain"])]
    if row["address"] == "/vj/cam":
        shots = planet_shots(row)
        return [(lo, hi, "%d %s" % (s["index"], s["name"])) for (lo, hi), s in zip(shot_ranges(len(shots)), shots)]
    return [(0, 255, row["plain"])]


def render_fixture(rows=None):
    rows = blender_rows(rows)
    out = ['<?xml version="1.0" encoding="UTF-8"?>', "<!DOCTYPE FixtureDefinition>",
           '<FixtureDefinition xmlns="http://www.qlcplus.org/FixtureDefinition">',
           " <Creator>", "  <Name>bossi3dj osc/qlc_fixture.py</Name>", "  <Version>1</Version>", "  <Author>bossi3dj</Author>", " </Creator>",
           " <Manufacturer>%s</Manufacturer>" % escape(MANUFACTURER), " <Model>%s</Model>" % escape(MODEL), " <Type>Other</Type>"]
    for r in rows:
        out.append(" <Channel Name=%s Default=%s>" % (quoteattr(r["address"]), quoteattr(str(default_dmx(r)))))
        out.append('  <Group Byte="0">%s</Group>' % _group(r))
        for lo, hi, text in capabilities(r):
            out.append('  <Capability Min="%d" Max="%d">%s</Capability>' % (lo, hi, escape(text)))
        out.append(" </Channel>")
    out.append(" <Mode Name=%s>" % quoteattr(MODE))
    out += ['  <Channel Number="%d">%s</Channel>' % (i, escape(r["address"])) for i, r in enumerate(rows)]
    out += [" </Mode>", " <Physical>", '  <Bulb Type="" Lumens="0" ColourTemperature="0"/>',
            '  <Dimensions Weight="0" Width="0" Height="0" Depth="0"/>', '  <Lens Name="Other" DegreesMin="0" DegreesMax="0"/>',
            '  <Focus Type="Fixed" PanMax="0" TiltMax="0"/>', '  <Technical PowerConsumption="0" DmxConnector="Other"/>', " </Physical>",
            "</FixtureDefinition>", ""]
    return "\n".join(out)


def _wire(row):
    if row["kind"] == "trigger":
        return "below 128 off; from 128 fires once, strength 0.5 at 128 up to %g at 255, back below 128 re-arms" % row["max"]
    if row["address"] == "/vj/cam":
        return "split into equal ranges, one per shot (below)"
    return "0..255 = 0..1" if (row["min"], row["max"]) == (0, 1) else "0..255 = %g..%g" % (row["min"], row["max"])


def render_table(rows=None):
    rows = blender_rows(rows)
    lines = ["| DMX channel | Address | What you see | DMX to wire value |", "|---|---|---|---|"]
    for i, r in enumerate(rows):
        lines.append("| %d | `%s` | %s | %s |" % (i + 1, r["address"], r["plain"], _wire(r)))
    cam = next(r for r in rows if r["address"] == "/vj/cam")
    lines += ["", "`/vj/cam` ranges (channel %d), one per shot of the scene that runs:" % (rows.index(cam) + 1), "",
              "| Scene | DMX value | Shot |", "|---|---|---|"]
    for key, label in (("planet", "Planet"), ("island", "Island")):
        shots = cam["shots"][key]
        for (lo, hi), s in zip(shot_ranges(len(shots)), shots):
            lines.append("| %s | %d to %d | %d %s |" % (label, lo, hi, s["index"], s["name"]))
    return "\n".join(lines)


def current_table(text):
    i, j = text.index(TABLE_BEGIN) + len(TABLE_BEGIN), text.index(TABLE_END)
    return text[i:j].strip("\n")


def sync():
    rows = contract.load()
    os.makedirs(QLC_DIR, exist_ok=True)
    new = render_fixture(rows)
    if not os.path.exists(FIXTURE) or open(FIXTURE).read() != new:
        with open(FIXTURE, "w") as f:
            f.write(new)
        print("wrote", os.path.relpath(FIXTURE, ROOT))
    with open(DOC) as f:
        text = f.read()
    i, j = text.index(TABLE_BEGIN) + len(TABLE_BEGIN), text.index(TABLE_END)
    body = text[:i] + "\n" + render_table(rows) + "\n" + text[j:]
    if body != text:
        with open(DOC, "w") as f:
            f.write(body)
        print("wrote", os.path.relpath(DOC, ROOT))


def stale():
    rows = contract.load()
    out = []
    if not os.path.exists(FIXTURE) or open(FIXTURE).read() != render_fixture(rows):
        out.append(os.path.relpath(FIXTURE, ROOT))
    if not os.path.exists(DOC) or current_table(open(DOC).read()) != render_table(rows):
        out.append(os.path.relpath(DOC, ROOT) + " channel table")
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
