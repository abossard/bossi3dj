#!/usr/bin/env python3
"""The QLC+ fixture for the Blender scene's Art-Net input, made from osc/contract.json.

    python3 osc/qlc_fixture.py sync    write qlc/bossi3dj-Synthwave-Planet.qxf, the workspace qlc/bossi3dj-Synthwave-Planet.qxw and the
                                       channel table in docs/artnet-qlc.md
    python3 osc/qlc_fixture.py check   exit 1 when one of them is out of step with the contract (tests/test_qlc_fixture.py does the same)
    python3 osc/qlc_fixture.py table   print the channel table

One fixture, one mode, one DMX channel per address the Blender scene reacts to, in contract order (the order of
blender/blender_osc_bridge.py's SCALES and of blender/artnet_input.py's channel map). The channel's capabilities carry the
rows' plain sentences; a row with `stops` gets named ranges (an index row like /vj/path or /vj/target one equal range per
index, the split blender/artnet_input.py decodes). The workspace patches the fixture once (universe 1, address 1) and holds a
virtual console: one slider per slider channel in the manual's groups, a Flash button per trigger, a row of buttons per
channel with named stops (docs/artnet-qlc.md says which
parts of the format were checked against a workspace QLC+ 5.3.0 wrote and which are from memory). Standard library only. The format is QLC+ 4.12's fixture definition (a copy of the shape of the .qxf files that
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
WORKSPACE = os.path.join(QLC_DIR, "bossi3dj-Synthwave-Planet.qxw")
DOC = os.path.join(ROOT, "docs", "artnet-qlc.md")
TABLE_BEGIN, TABLE_END = "<!-- artnet-channels:begin -->", "<!-- artnet-channels:end -->"
MANUFACTURER, MODEL, MODE = "bossi3dj", "Synthwave Planet", "Synthwave"
TRIGGER_AT = 128


def blender_rows(rows=None):
    return [r for r in (rows or contract.load()) if r.get("blender")]


def index_ranges(n):
    """[(first DMX value, last DMX value)] of n equal ranges of 0..255, the split blender/artnet_input.py decodes (v * n // 256)."""
    out = []
    for i in range(n):
        lo = -(-i * 256 // n)
        hi = -(-(i + 1) * 256 // n) - 1
        out.append((lo, hi))
    return out


def default_dmx(row):
    if row["kind"] != "float":
        return 0
    return int(round((row["default"] - row["min"]) / (row["max"] - row["min"]) * 255))


SPEED_ROWS = {"/vj/grid_speed", "/vj/cam_speed", "/vj/fog_speed", "/vj/star_speed"}


def channel_name(row):
    """What QLC+ shows: the short name with the address kept in it, for example `Fog (/vj/fog)`."""
    return "%s (%s)" % (row["label"], row["address"])


def _group(row):
    """The QLC+ channel group. Intensity only for the overall brightness: QLC+'s grand master scales every Intensity channel and
    its HTP merge applies to them, which the scene means for /vj/intensity and for nothing else."""
    a = row["address"]
    if a == "/vj/intensity":
        return "Intensity"
    if a in ("/vj/hue", "/vj/fog_hue"):
        return "Colour"
    if a == "/vj/strobe":
        return "Shutter"
    if a in SPEED_ROWS:
        return "Speed"
    return "Effect"


def only_ends(row):
    """True for stops that are just the two ends of the range (fog: None and Dense autumn fog): a split in halves would call a fog of 100 None."""
    stops = row.get("stops") or []
    return len(stops) == 2 and [s["wire"] for s in stops] == [row["min"], row["max"]]


def ranged(row):
    """True when the stops have one in between, so each gets its own range (and a stop button in the workspace)."""
    return bool(row.get("stops")) and not only_ends(row)


def stop_ranges(row):
    """[(min, max, stop)] of a row with stops: ranges centred on the stops, no gaps, 0 to 255. A stop's DMX value is wire * 255."""
    stops = row["stops"]
    if row["kind"] == "int":                    # an index: one equal range per index, named by the stop at that index
        ranges = index_ranges(int(row["max"] - row["min"]) + 1)
        return [(ranges[int(s["wire"] - row["min"])][0], ranges[int(s["wire"] - row["min"])][1], s) for s in stops]
    dmx = [int(round(s["wire"] * 255)) for s in stops]
    edges = [(a + b) // 2 for a, b in zip(dmx, dmx[1:])]
    lo = [0] + [e + 1 for e in edges]
    hi = edges + [255]
    return [(a, b, s) for a, b, s in zip(lo, hi, stops)]


def capabilities(row):
    """[(min, max, text, attributes)] of one channel; the plain sentence is the text where QLC+ shows a capability."""
    if row["kind"] == "trigger":
        return [(0, TRIGGER_AT - 1, "off", {}), (TRIGGER_AT, 255, "fire once, harder the higher: " + row["plain"], {})]
    if only_ends(row):
        a, b = row["stops"]
        return [(0, 255, "from %s (0) to %s (255): %s" % (a["name"], b["name"], row["plain"]), {})]
    if row.get("stops"):
        out = []
        for lo, hi, s in stop_ranges(row):
            attrs = {"Preset": "ColorMacro", "Res1": s["colour"]} if s.get("colour") else {}
            out.append((lo, hi, "%s: %s" % (s["name"], row["plain"]), attrs))
        return out
    return [(0, 255, row["plain"], {"Preset": "SlowToFast"} if row["address"] in SPEED_ROWS else {})]


def render_fixture(rows=None):
    rows = blender_rows(rows)
    out = ['<?xml version="1.0" encoding="UTF-8"?>', "<!DOCTYPE FixtureDefinition>",
           '<FixtureDefinition xmlns="http://www.qlcplus.org/FixtureDefinition">',
           " <Creator>", "  <Name>bossi3dj osc/qlc_fixture.py</Name>", "  <Version>1</Version>", "  <Author>bossi3dj</Author>", " </Creator>",
           " <Manufacturer>%s</Manufacturer>" % escape(MANUFACTURER), " <Model>%s</Model>" % escape(MODEL), " <Type>Other</Type>"]
    for r in rows:
        out.append(" <Channel Name=%s Default=%s>" % (quoteattr(channel_name(r)), quoteattr(str(default_dmx(r)))))
        out.append('  <Group Byte="0">%s</Group>' % _group(r))
        for lo, hi, text, attrs in capabilities(r):
            extra = "".join(" %s=%s" % (k, quoteattr(v)) for k, v in attrs.items())
            out.append('  <Capability Min="%d" Max="%d"%s>%s</Capability>' % (lo, hi, extra, escape(text)))
        out.append(" </Channel>")
    out.append(" <Mode Name=%s>" % quoteattr(MODE))
    out += ['  <Channel Number="%d">%s</Channel>' % (i, escape(channel_name(r))) for i, r in enumerate(rows)]
    out += [" </Mode>", " <Physical>", '  <Bulb Type="" Lumens="0" ColourTemperature="0"/>',
            '  <Dimensions Weight="0" Width="0" Height="0" Depth="0"/>', '  <Lens Name="Other" DegreesMin="0" DegreesMax="0"/>',
            '  <Focus Type="Fixed" PanMax="0" TiltMax="0"/>', '  <Technical PowerConsumption="0" DmxConnector="Other"/>', " </Physical>",
            "</FixtureDefinition>", ""]
    return "\n".join(out)


# ---------------------------------------------------------------- workspace (.qxw)

ART_IP = "255.255.255.255"          # the broadcast first; 127.0.0.1 is the second try (docs/artnet-qlc.md)
SLIDER_W, SLIDER_H, PAD = 64, 230, 12


class _Ids:
    """Ids for virtual console widgets and functions, handed out in order."""

    def __init__(self):
        self.widget, self.function = 0, 0

    def w(self):
        self.widget += 1
        return self.widget

    def f(self):
        self.function += 1
        return self.function - 1


def _state(x, y, w, h):
    return '<WindowState Visible="True" X="%d" Y="%d" Width="%d" Height="%d"/>' % (x, y, w, h)


def _group_height(members):
    sliders = [r for r in members if r["kind"] != "trigger"]
    stops = [r for r in members if ranged(r) and r["kind"] != "trigger"]
    return (SLIDER_H + 2 * PAD + 20 if sliders else 120) + 52 * len(stops)


def _group_order(rows):
    """The manual's groups (osc/contract.py GROUPS) that hold a Blender row, in the manual's order."""
    return [g for g in contract.GROUPS if any(r["group"] == g for r in rows)]


def render_workspace(rows=None):
    rows = blender_rows(rows)
    ids = _Ids()
    n = len(rows)
    out = ['<?xml version="1.0" encoding="UTF-8"?>', "<!DOCTYPE Workspace>",
           '<Workspace xmlns="http://www.qlcplus.org/Workspace" CurrentWindow="VirtualConsole">',
           " <Creator>", "  <Name>Q Light Controller Plus</Name>", "  <Version>5.3.0 GIT</Version>", "  <Author>bossi3dj osc/qlc_fixture.py</Author>", " </Creator>",
           ' <Engine Autostart="0">', "  <InputOutputMap>", '   <Universe Name="Synthwave (Art-Net)" ID="0">',
           '    <Output Plugin="ArtNet" Name="127.0.0.1" UID="" Line="0">',
           '     <PluginParameters UniverseChannels="512" outputIP="%s" outputUni="0" transmitMode="Full"/>' % ART_IP,
           "    </Output>", "   </Universe>", "  </InputOutputMap>",
           "  <Fixture>", "   <Manufacturer>%s</Manufacturer>" % escape(MANUFACTURER), "   <Model>%s</Model>" % escape(MODEL), "   <Mode>%s</Mode>" % escape(MODE),
           "   <ID>0</ID>", "   <Name>%s</Name>" % escape(MODEL), "   <Universe>0</Universe>", "   <Address>0</Address>", "   <Channels>%d</Channels>" % n, "  </Fixture>"]
    scenes = []                                   # (function id, name, channel, value)
    triggers = [(i, r) for i, r in enumerate(rows) if r["kind"] == "trigger"]
    for i, r in triggers:
        scenes.append((ids.f(), "fire " + r["address"], i, 255))
    stop_scenes = []                              # one scene per labelled stop: the channel at that stop's DMX value
    for i, r in enumerate(rows):
        if ranged(r) and r["kind"] != "trigger":
            for lo, hi, st in stop_ranges(r):
                val = (lo + hi) // 2 if r["kind"] == "int" else int(round(st["wire"] * 255))     # an index: the middle of its range
                stop_scenes.append((ids.f(), "%s = %s" % (r["label"], st["name"]), i, val, r, st))
    for fid, name, ch, val, *_ in scenes + stop_scenes:
        out += ['  <Function ID="%d" Type="Scene" Name=%s Path="Synthwave">' % (fid, quoteattr(name)), '   <Speed FadeIn="0" FadeOut="0" Duration="0"/>',
                '   <FixtureVal ID="0">%d,%d</FixtureVal>' % (ch, val), "  </Function>"]
    # channel groups (from memory of QLC+'s ChannelsGroup element, not seen in a shipped file): one per manual group
    for gi, group in enumerate(_group_order(rows)):
        members = ",".join("0,%d" % i for i, r in enumerate(rows) if r["group"] == group)
        out.append('  <ChannelsGroup ID="%d" Name=%s Value="0">%s</ChannelsGroup>' % (gi, quoteattr(group), members))
    out.append(" </Engine>")
    total = PAD + sum(_group_height([r for r in rows if r["group"] == g]) + PAD for g in _group_order(rows))
    out += [" <VirtualConsole>", '  <Frame Caption="Synthwave Planet" ID="%d">' % ids.w(), '   ' + _state(0, 0, 1200, total),
            "   <AllowResize>False</AllowResize>", "   <ShowHeader>False</ShowHeader>", "   <ShowEnableButton>False</ShowEnableButton>"]
    y = PAD
    for group in _group_order(rows):
        members = [(i, r) for i, r in enumerate(rows) if r["group"] == group]
        sliders = [(i, r) for i, r in members if r["kind"] != "trigger"]
        buttons = [(i, r) for i, r in members if r["kind"] == "trigger"]
        width = max(len(sliders) * (SLIDER_W + 4), len(buttons) * 124, max([len(r["stops"]) * 100 + 12 for _i, r in sliders if ranged(r)] or [0]), 8) + 2 * PAD
        height = _group_height([r for _i, r in members])
        out += ['   <Frame Caption=%s ID="%d">' % (quoteattr(group), ids.w()), '    ' + _state(PAD, y, width, height),
                "    <AllowResize>False</AllowResize>", "    <ShowHeader>True</ShowHeader>", "    <ShowEnableButton>False</ShowEnableButton>"]
        x = PAD
        for i, r in sliders:
            out += ['    <Slider Caption=%s ID="%d" WidgetStyle="Slider" InvertedAppearance="false">' % (quoteattr(r["label"]), ids.w()),
                    "     " + _state(x, 28, SLIDER_W, SLIDER_H), '     <SliderMode ValueDisplayStyle="Exact">Level</SliderMode>',
                    '     <Level LowLimit="0" HighLimit="255" Value="%d">' % default_dmx(r), '      <Channel Fixture="0">%d</Channel>' % i, "     </Level>", "    </Slider>"]
            x += SLIDER_W + 4
        x = PAD
        fire = {ch: fid for fid, _name, ch, _v in scenes}
        for fid, r in ((fire[i], r) for i, r in buttons):
            out += ['    <Button Caption=%s ID="%d">' % (quoteattr(r["label"]), ids.w()), "     " + _state(x, 28, 120, 60),
                    '     <Function ID="%d"/>' % fid, "     <Action>Flash</Action>", "    </Button>"]
            x += 124
        row_y = SLIDER_H + 40
        by_row = {}
        for fid, name, ch, val, r, st in stop_scenes:
            by_row.setdefault(ch, []).append((fid, r, st))
        for i, r in members:
            if i not in by_row:
                continue
            out += ['    <SoloFrame Caption=%s ID="%d">' % (quoteattr(r["label"]), ids.w()), "     " + _state(PAD, row_y, width - 2 * PAD, 46),
                    "     <AllowResize>False</AllowResize>", "     <ShowHeader>True</ShowHeader>", "     <ShowEnableButton>False</ShowEnableButton>"]
            bx = 4
            for fid, _r, st in by_row[i]:
                out += ['     <Button Caption=%s ID="%d">' % (quoteattr(st["name"]), ids.w()), "      " + _state(bx, 18, 96, 24),
                        '      <Function ID="%d"/>' % fid, "      <Action>Toggle</Action>", "     </Button>"]
                bx += 100
            out.append("    </SoloFrame>")
            row_y += 52
        out.append("   </Frame>")
        y += height + PAD
    out += ["  </Frame>", " </VirtualConsole>", " <FlowConsole>", '  <FlowPage Name="Page 1"/>', " </FlowConsole>", "</Workspace>", ""]
    return "\n".join(out)


def _wire(row):
    if row["kind"] == "trigger":
        return "below 128 off; from 128 fires once, strength 0.5 at 128 up to %g at 255, back below 128 re-arms" % row["max"]
    if row["kind"] == "int":
        return "split into %d equal ranges, one per index" % (int(row["max"] - row["min"]) + 1)
    return "0..255 = 0..1" if (row["min"], row["max"]) == (0, 1) else "0..255 = %g..%g" % (row["min"], row["max"])


def _stops_text(row):
    if not ranged(row) or row["kind"] == "trigger":
        return ""
    return "; ranges: " + ", ".join("%s %d to %d" % (st["name"], lo, hi) for lo, hi, st in stop_ranges(row))


def render_table(rows=None):
    rows = blender_rows(rows)
    lines = ["| DMX channel | Name in QLC+ | What you see | DMX to wire value |", "|---|---|---|---|"]
    for i, r in enumerate(rows):
        lines.append("| %d | %s | %s | %s |" % (i + 1, channel_name(r).replace("(", "(`").replace(")", "`)"), r["plain"], _wire(r) + _stops_text(r)))
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
    new = render_workspace(rows)
    if not os.path.exists(WORKSPACE) or open(WORKSPACE).read() != new:
        with open(WORKSPACE, "w") as f:
            f.write(new)
        print("wrote", os.path.relpath(WORKSPACE, ROOT))
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
    if not os.path.exists(WORKSPACE) or open(WORKSPACE).read() != render_workspace(rows):
        out.append(os.path.relpath(WORKSPACE, ROOT))
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
