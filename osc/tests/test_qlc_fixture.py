"""The QLC+ fixture, its channel table and the Art-Net sender, against the contract. Run: python3 -m unittest discover osc/tests"""
import os
import sys
import unittest
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "blender"))
import artnet_input as an  # noqa: E402
import artnet_send  # noqa: E402
import blender_osc_bridge as bridge  # noqa: E402
import contract  # noqa: E402
import qlc_fixture as qf  # noqa: E402

NS = "{http://www.qlcplus.org/FixtureDefinition}"
W = "{http://www.qlcplus.org/Workspace}"
ROWS = qf.blender_rows()
QLC_TYPES = {"Color Changer", "Moving Head", "Scanner", "Flower", "LED Bar (Beams)", "LED Bar (Pixels)", "Strobe", "Laser",
             "Smoke", "Effect", "Dimmer", "Other", "Hazer", "Fan"}
QLC_GROUPS = {"Effect", "Colour", "Shutter", "Speed", "Gobo", "Intensity", "Maintenance", "Beam", "Prism", "Pan", "Tilt", "Nothing"}


def parsed():
    return ET.parse(qf.FIXTURE).getroot()


class DriftTests(unittest.TestCase):
    def test_fixture_file_is_what_the_generator_makes(self):
        with open(qf.FIXTURE) as f:
            self.assertEqual(f.read(), qf.render_fixture(contract.load()))

    def test_doc_channel_table_is_what_the_generator_makes(self):
        with open(qf.DOC) as f:
            self.assertEqual(qf.current_table(f.read()), qf.render_table(contract.load()))


class WorkspaceTests(unittest.TestCase):
    """qlc/bossi3dj-Synthwave-Planet.qxw: the shape of a QLC+ 5.3.0 workspace, with the console built from the contract."""

    @staticmethod
    def root():
        return ET.parse(qf.WORKSPACE).getroot()

    def test_file_is_what_the_generator_makes(self):
        with open(qf.WORKSPACE) as f:
            self.assertEqual(f.read(), qf.render_workspace(contract.load()))

    def test_fixture_is_patched_once_at_universe_1_address_1(self):
        engine = self.root().find(W + "Engine")
        fixtures = engine.findall(W + "Fixture")
        self.assertEqual(len(fixtures), 1)
        f = fixtures[0]
        got = {t: f.find(W + t).text for t in ("Manufacturer", "Model", "Mode", "ID", "Universe", "Address", "Channels")}
        self.assertEqual(got, {"Manufacturer": qf.MANUFACTURER, "Model": qf.MODEL, "Mode": qf.MODE, "ID": "0", "Universe": "0", "Address": "0", "Channels": str(len(ROWS))})

    def test_the_universe_outputs_to_art_net_universe_0(self):
        out = self.root().find(W + "Engine/" + W + "InputOutputMap/" + W + "Universe/" + W + "Output")
        self.assertEqual(out.get("Plugin"), "ArtNet")
        params = out.find(W + "PluginParameters").attrib
        self.assertEqual((params["outputUni"], params["outputIP"], params["transmitMode"]), ("0", qf.ART_IP, "Full"))

    def test_one_slider_per_slider_channel_and_a_flash_button_per_trigger(self):
        root = self.root()
        sliders = [int(s.find(W + "Level/" + W + "Channel").text) for s in root.iter(W + "Slider")]
        want = [i for i, r in enumerate(ROWS) if r["kind"] != "trigger"]
        self.assertEqual(sorted(sliders), want)
        scenes = {f.get("ID"): f for f in root.iter(W + "Function") if f.get("Type")}
        flash = [b for b in root.iter(W + "Button") if b.find(W + "Action").text == "Flash"]
        self.assertEqual(len(flash), sum(1 for r in ROWS if r["kind"] == "trigger"))
        for b in flash:
            vals = scenes[b.find(W + "Function").get("ID")].find(W + "FixtureVal").text.split(",")
            with self.subTest(button=b.get("Caption")):
                self.assertEqual(ROWS[int(vals[0])]["kind"], "trigger")
                self.assertEqual(ROWS[int(vals[0])]["address"], "/vj/" + b.get("Caption"))
                self.assertEqual(vals[1], "255")

    def test_one_camera_button_per_named_shot_cutting_to_that_shot(self):
        root = self.root()
        scenes = {f.get("ID"): f for f in root.iter(W + "Function") if f.get("Type")}
        solo = next(root.iter(W + "SoloFrame"))
        buttons = solo.findall(W + "Button")
        cam = next(r for r in ROWS if r["address"] == "/vj/cam")
        self.assertEqual([b.get("Caption") for b in buttons], ["%d %s" % (s["index"], s["name"]) for s in cam["shots"]["planet"]])
        d = an.DmxDecoder(an.channel_map((a, v[0], v[1], v[2]) for a, v in bridge.SCALES.items()), shots=len(buttons))
        cam_channel = [r["address"] for r in ROWS].index("/vj/cam")
        for i, b in enumerate(buttons):
            ch, val = (int(x) for x in scenes[b.find(W + "Function").get("ID")].find(W + "FixtureVal").text.split(","))
            with self.subTest(shot=b.get("Caption")):
                self.assertEqual(ch, cam_channel)
                self.assertEqual(d.wire(("/vj/cam", "int", 0, 11), val), float(i))

    def test_ids_are_unique_and_every_button_function_exists(self):
        root = self.root()
        widgets = [w.get("ID") for w in root.iter() if w.tag in (W + "Frame", W + "SoloFrame", W + "Slider", W + "Button")]
        self.assertEqual(len(widgets), len(set(widgets)))
        functions = [f.get("ID") for f in root.iter(W + "Function") if f.get("Type")]
        self.assertEqual(len(functions), len(set(functions)))
        for b in root.iter(W + "Button"):
            self.assertIn(b.find(W + "Function").get("ID"), functions)

    def test_groups_are_the_manuals_groups(self):
        frames = [f.get("Caption") for f in self.root().find(W + "VirtualConsole/" + W + "Frame").findall(W + "Frame")]
        self.assertEqual(frames, [g for g in contract.GROUPS if any(r["group"] == g for r in ROWS)])


class FixtureFormatTests(unittest.TestCase):
    """What QLC+ 4.12 needs of a .qxf, checked against the shape of the files in QLC+.app's Fixtures folder."""

    def test_header(self):
        root = parsed()
        self.assertEqual(root.tag, NS + "FixtureDefinition")
        self.assertTrue(root.find(NS + "Creator/" + NS + "Name").text)
        self.assertEqual(root.find(NS + "Manufacturer").text, qf.MANUFACTURER)
        self.assertEqual(root.find(NS + "Model").text, qf.MODEL)
        self.assertIn(root.find(NS + "Type").text, QLC_TYPES)
        self.assertEqual(os.path.basename(qf.FIXTURE), "%s-%s.qxf" % (qf.MANUFACTURER, qf.MODEL.replace(" ", "-")))

    def test_one_channel_per_blender_row_in_contract_order(self):
        names = [c.get("Name") for c in parsed().findall(NS + "Channel")]
        self.assertEqual(names, [r["address"] for r in ROWS])
        self.assertEqual(names, list(bridge.SCALES))
        self.assertEqual(len(set(names)), len(names))

    def test_one_mode_with_every_channel_numbered_in_order(self):
        modes = parsed().findall(NS + "Mode")
        self.assertEqual(len(modes), 1)
        listed = [(int(c.get("Number")), c.text) for c in modes[0].findall(NS + "Channel")]
        self.assertEqual(listed, list(enumerate(r["address"] for r in ROWS)))

    def test_capabilities_cover_0_to_255_without_gaps(self):
        for ch in parsed().findall(NS + "Channel"):
            with self.subTest(channel=ch.get("Name")):
                self.assertIn(ch.find(NS + "Group").text, QLC_GROUPS)
                caps = [(int(c.get("Min")), int(c.get("Max")), c.text) for c in ch.findall(NS + "Capability")]
                self.assertEqual(caps[0][0], 0)
                self.assertEqual(caps[-1][1], 255)
                for (_, hi, _), (lo, _, _) in zip(caps, caps[1:]):
                    self.assertEqual(lo, hi + 1)
                self.assertTrue(all(t.strip() for _, _, t in caps))
                self.assertTrue(0 <= int(ch.get("Default")) <= 255)

    def test_capabilities_by_kind(self):
        by = {c.get("Name"): [(int(x.get("Min")), int(x.get("Max")), x.text) for x in c.findall(NS + "Capability")] for c in parsed().findall(NS + "Channel")}
        for r in ROWS:
            with self.subTest(address=r["address"]):
                caps = by[r["address"]]
                if r["kind"] == "trigger":
                    self.assertEqual([(lo, hi) for lo, hi, _ in caps], [(0, 127), (128, 255)])
                    self.assertEqual(caps[0][2], "off")
                elif r["address"] == "/vj/cam":
                    shots = r["shots"]["planet"]
                    self.assertEqual(len(caps), len(shots))
                    self.assertEqual([t for _, _, t in caps], ["%d %s" % (s["index"], s["name"]) for s in shots])
                else:
                    self.assertEqual([(lo, hi, t) for lo, hi, t in caps], [(0, 255, r["plain"])])

    def test_defaults_are_the_contract_defaults(self):
        cases = {"/vj/level": 128, "/vj/fog": 89, "/vj/intensity": 128, "/vj/shock": 0, "/vj/cam": 0, "/vj/night": 0, "/vj/pyramids": 255}
        by = {c.get("Name"): int(c.get("Default")) for c in parsed().findall(NS + "Channel")}
        for address, want in cases.items():
            with self.subTest(address=address):
                self.assertEqual(by[address], want)


class ShotRangeTests(unittest.TestCase):
    def test_ranges_are_what_the_decoder_decodes(self):
        for n in (12, 7, 1, 5):
            with self.subTest(shots=n):
                d = an.DmxDecoder(an.channel_map((a, v[0], v[1], v[2]) for a, v in bridge.SCALES.items()), shots=n)
                for i, (lo, hi) in enumerate(qf.shot_ranges(n)):
                    for v in (lo, hi):
                        self.assertEqual(d.wire(("/vj/cam", "int", 0, 11), v), float(i))
                self.assertEqual(qf.shot_ranges(n)[0][0], 0)
                self.assertEqual(qf.shot_ranges(n)[-1][1], 255)


class SenderTests(unittest.TestCase):
    def test_build_puts_defaults_then_the_sets(self):
        base, _ = artnet_send.build([], 1)
        changed, triggers = artnet_send.build(["/vj/fog=0.8", "/vj/shock=1", "/vj/cam=3", "500=7"], 1)
        order = [r["address"] for r in ROWS]
        at = lambda a, start=1: start - 1 + order.index(a)
        self.assertEqual(changed[at("/vj/fog")], 204)
        self.assertEqual(changed[at("/vj/shock")], 255)
        self.assertEqual(changed[499], 7)
        self.assertEqual(triggers, [at("/vj/shock")])
        self.assertEqual(base[at("/vj/fog")], qf.default_dmx(next(r for r in ROWS if r["address"] == "/vj/fog")))
        self.assertEqual(sum(1 for a, b in zip(base, changed) if a != b), 4)

    def test_start_address_offsets_the_whole_fixture(self):
        for start in (1, 20, 300):
            with self.subTest(start=start):
                changed, _ = artnet_send.build(["/vj/level=0"], start)
                self.assertEqual(changed[start - 1], 0)

    def test_what_the_sender_sends_the_decoder_reads_back(self):
        """A frame of defaults, then the sets: the decoder sees exactly the sets as changes."""
        cases = [(["/vj/fog=0.8"], {"/vj/fog": 0.8}), (["/vj/cam=3"], {"/vj/cam": 3.0}), (["/vj/shock=1"], {"/vj/shock": 1.5}),
                 (["/vj/intensity=2"], {"/vj/intensity": 1.0})]
        for sets, want in cases:
            for start in (1, 33):
                with self.subTest(sets=sets, start=start):
                    d = an.DmxDecoder(an.channel_map((a, v[0], v[1], v[2]) for a, v in bridge.SCALES.items()), shots=12, address=start)
                    base, _ = artnet_send.build([], start)
                    changed, _ = artnet_send.build(sets, start)
                    d.feed(0, base)
                    got = dict(d.feed(0, changed))
                    self.assertEqual(sorted(got), sorted(want))
                    for a, w in want.items():
                        self.assertAlmostEqual(got[a], w, places=2)

    def test_a_non_blender_address_is_refused(self):
        with self.assertRaises(SystemExit):
            artnet_send.build(["/vj/cam_auto=1"], 1)


if __name__ == "__main__":
    unittest.main()
