"""The control page's data without Blender: grouping, coverage, the preset file, the page settings. Run: python3 -m unittest discover blender/tests"""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scenes"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "osc"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
import blender_page_mock as mock  # noqa: E402  (the scene's controls as synthwave_web.controls() reads them)
import contract  # noqa: E402
import page_model as pm  # noqa: E402

ROWS = contract.load()
CONTROLS = mock.scene_controls(ROWS)


class DescribeTests(unittest.TestCase):
    def setUp(self):
        self.page = pm.page_state(CONTROLS, ROWS, contract.GROUPS)

    def test_every_blender_address_has_a_control(self):
        self.assertEqual(self.page["coverage"], {"missing": [], "extra": []})
        self.assertEqual(len(self.page["controls"]), len(pm.blender_rows(ROWS)))

    def test_sections_follow_the_manual_groups(self):
        titles = [s["title"] for s in self.page["sections"]]
        self.assertEqual(titles, [g for g in contract.GROUPS if g != "Godot only"])

    def test_each_control_carries_its_sentence_and_address_from_the_contract(self):
        by_key = {c["key"]: c for c in self.page["controls"]}
        for row in pm.blender_rows(ROWS):
            with self.subTest(address=row["address"]):
                c = by_key[pm.key_of(row["address"])]
                self.assertEqual((c["address"], c["group"], c["plain"]), (row["address"], row["group"], row["plain"]))
                self.assertTrue(c["plain"])

    def test_order_inside_a_group_is_the_contract_order(self):
        for sec in self.page["sections"]:
            with self.subTest(group=sec["title"]):
                want = [pm.key_of(r["address"]) for r in ROWS if r["group"] == sec["title"] and r.get("blender") and pm.key_of(r["address"]) not in pm.CAMERA]
                self.assertEqual(sec["keys"], want)

    def test_the_path_camera_comes_first_and_only_once(self):
        self.assertEqual(self.page["path_camera"], ["vj_path", "vj_target", "vj_height", "vj_blend"])
        below = [k for sec in self.page["sections"] for k in sec["keys"]]
        self.assertFalse(set(self.page["path_camera"]) & set(below))
        self.assertEqual(sorted(below + self.page["path_camera"]), sorted(c["key"] for c in self.page["controls"]))

    def test_path_and_target_buttons_carry_the_contract_names(self):
        by_key = {c["key"]: c for c in self.page["controls"]}
        cases = [("vj_path", ["Orbit", "Follow the land", "Rise and descend", "Vantage"]),
                 ("vj_target", ["Pyramids", "Lake", "River", "Coast", "Moon", "Sun", "Planet"])]
        for key, names in cases:
            with self.subTest(key=key):
                c = by_key[key]
                self.assertEqual([x["name"] for x in c["stops"]], names)
                self.assertEqual([x["wire"] for x in c["stops"]], list(range(c["min"], c["max"] + 1)))

    def test_labels_come_from_the_contract(self):
        by_key = {c["key"]: c for c in self.page["controls"]}
        for key, label in (("vj_blend", "Fade Time"), ("vj_height", "Height"), ("vj_takeover", "Takeover Pause")):
            with self.subTest(key=key):
                self.assertEqual(by_key[key]["label"], label)

    def test_no_shot_control_on_the_planet(self):
        keys = {c["key"] for c in self.page["controls"]}
        self.assertFalse(keys & {"vj_cam", "vj_cam_auto", "vj_flight", "vj_boost"})

    def test_triggers_are_their_own_section_of_buttons(self):
        trig = next(s for s in self.page["sections"] if s["title"] == "Triggers")
        self.assertEqual(trig["keys"], ["vj_shock", "vj_meteor", "vj_hit"])
        self.assertTrue(all(c["trigger"] for c in self.page["controls"] if c["key"] in trig["keys"]))

    def test_a_property_the_contract_lacks_is_shown_last_and_reported(self):
        page = pm.page_state(CONTROLS + [{"key": "vj_new_thing", "min": 0, "max": 1, "step": 0.01, "default": 0, "trigger": False}], ROWS, contract.GROUPS)
        self.assertEqual(page["sections"][-1], {"title": pm.OTHER, "keys": ["vj_new_thing"]})
        self.assertEqual(page["coverage"]["extra"], ["vj_new_thing"])

    def test_a_godot_only_property_of_the_scene_is_left_off_the_page(self):
        for key in ("vj_cam", "vj_cam_auto"):
            with self.subTest(key=key):
                page = pm.page_state(CONTROLS + [{"key": key, "min": 0, "max": 11, "step": 1, "default": 0, "trigger": False}], ROWS, contract.GROUPS)
                self.assertNotIn(key, [c["key"] for c in page["controls"]])
                self.assertEqual(page["coverage"], {"missing": [], "extra": []})
                self.assertNotIn("Godot only", [s["title"] for s in page["sections"]])

    def test_hold_all_takes_the_page_controls_only(self):
        scene = CONTROLS + [{"key": "vj_cam", "min": 0, "max": 11, "step": 1, "default": 0, "trigger": False}]
        held = [c["key"] for c in pm.page_controls(scene, ROWS)]
        self.assertEqual(sorted(held), sorted(c["key"] for c in pm.page_state(scene, ROWS, contract.GROUPS)["controls"]))
        self.assertNotIn("vj_cam", held)

    def test_a_missing_control_is_reported_by_address(self):
        page = pm.page_state([c for c in CONTROLS if c["key"] != "vj_fog"], ROWS, contract.GROUPS)
        self.assertEqual(page["coverage"]["missing"], ["/vj/fog"])

    def test_the_godot_only_address_is_not_expected(self):
        self.assertNotIn("/vj/cam_auto", [r["address"] for r in pm.blender_rows(ROWS)])


class ArtNetTests(unittest.TestCase):
    BOUND = {"enabled": True, "bound": True, "error": None, "universe": 0, "address": 1, "frames": 0, "other_universe": 0}

    def test_chip(self):
        cases = [
            (None, 0, "off", "Art-Net -"),
            (dict(self.BOUND, enabled=False), 0, "off", "Art-Net off"),
            (dict(self.BOUND, bound=False, error="Address already in use"), 0, "bad", "Art-Net not listening (Address already in use)"),
            (dict(self.BOUND, bound=False), 0, "bad", "Art-Net not listening (port busy)"),
            (self.BOUND, 0, "warn", "Art-Net u0 a1, no frames yet"),
            (dict(self.BOUND, other_universe=12), 0, "warn", "Art-Net u0 a1, frames for another universe"),
            (dict(self.BOUND, frames=500), 0, "warn", "Art-Net u0 a1, no frames now"),
            (dict(self.BOUND, frames=500, universe=2, address=17), 43.6, "ok", "Art-Net u2 a17, 44 fps"),
        ]
        for state, fps, level, text in cases:
            with self.subTest(text=text):
                self.assertEqual(pm.artnet_chip(state, fps), {"level": level, "text": text})

    def test_rate(self):
        for prev, now, frames, want in ((None, 5.0, 10, 0.0), ((4.0, 0), 5.0, 44, 44.0), ((4.0, 100), 5.0, 50, 0.0), ((5.0, 0), 5.0, 9, 0.0)):
            with self.subTest(prev=prev, frames=frames):
                self.assertEqual(pm.rate(prev, now, frames), want)


class SourceTests(unittest.TestCase):
    def test_counts_by_source_and_held(self):
        got = pm.source_counts({"vj_fog": "osc", "vj_cam": "web", "vj_hue": "osc"}, {"vj_cam"}, ["vj_fog", "vj_cam", "vj_hue", "vj_sun"])
        self.assertEqual(got, {"osc": 2, "web": 1, "held": 1})


class PresetTests(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "local", "presets.json")
        self.presets = pm.Presets(self.path)
        self.known = {"vj_fog", "vj_night"}

    def test_save_recall_delete(self):
        self.presets.save("dusk", {"vj_fog": 0.8, "vj_night": 0.3}, self.known)
        self.assertEqual(self.presets.all()["dusk"]["values"], {"vj_fog": 0.8, "vj_night": 0.3})
        self.presets.save("dusk", {"vj_fog": 0.1}, self.known)
        self.assertEqual(self.presets.all()["dusk"]["values"], {"vj_fog": 0.1})
        self.presets.delete("dusk")
        self.assertEqual(self.presets.all(), {})

    def test_the_file_is_json_a_person_can_read(self):
        self.presets.save("a", {"vj_fog": 0.5}, self.known)
        with open(self.path) as f:
            self.assertEqual(json.load(f), {"a": {"values": {"vj_fog": 0.5}}})

    def test_bad_input_is_refused_and_nothing_is_written(self):
        cases = [("", {"vj_fog": 1}), ("x" * 41, {"vj_fog": 1}), ("a", {"vj_nope": 1}), ("a", {"vj_fog": "high"}), ("a", {"vj_fog": True})]
        for name, values in cases:
            with self.subTest(name=name[:6], values=values):
                with self.assertRaises(pm.PresetError):
                    self.presets.save(name, values, self.known)
        self.assertEqual(self.presets.all(), {})

    def test_delete_of_an_unknown_name_is_refused(self):
        with self.assertRaises(pm.PresetError):
            self.presets.delete("nothing")

    def test_a_broken_file_reads_as_empty(self):
        os.makedirs(os.path.dirname(self.path))
        with open(self.path, "w") as f:
            f.write("{not json")
        self.assertEqual(self.presets.all(), {})


class SettingsTests(unittest.TestCase):
    def test_host_follows_the_settings_file(self):
        d = tempfile.mkdtemp()
        for content, want in ((None, "127.0.0.1"), ('{"host": "local"}', "127.0.0.1"), ('{"host": "lan"}', "0.0.0.0"), ('{"host": "evil"}', "127.0.0.1"), ("{bad", "127.0.0.1")):
            with self.subTest(content=content):
                path = os.path.join(d, "page.json")
                if content is None:
                    if os.path.exists(path):
                        os.remove(path)
                else:
                    with open(path, "w") as f:
                        f.write(content)
                self.assertEqual(pm.bind_host(path), want)

    def test_host_header(self):
        cases = [("127.0.0.1:9210", False, True), ("localhost:9210", False, True), ("[::1]:9210", False, True), ("evil.example", False, False),
                 ("evil.example:9210", False, False), ("192.168.1.5:9210", False, False), (None, False, False), ("192.168.1.5:9210", True, True)]
        for header, lan, want in cases:
            with self.subTest(header=header, lan=lan):
                self.assertEqual(pm.host_allowed(header, lan, 9210), want)


if __name__ == "__main__":
    unittest.main()
