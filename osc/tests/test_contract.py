"""osc/contract.json and its copies. Run: python3 -m unittest discover osc/tests"""
import ast
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import contract  # noqa: E402

RUNTIME = os.path.join(contract.ROOT, "blender", "scenes", "synthwave_runtime.py")


def runtime_tables():
    """DEFAULTS, RANGES and TRIGGERS of the Blender runtime, read without importing bpy."""
    with open(RUNTIME) as f:
        tree = ast.parse(f.read())
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in ("DEFAULTS", "RANGES", "TRIGGERS"):
            out[node.targets[0].id] = ast.literal_eval(node.value)
    return out


ROWS = contract.load()
RT = runtime_tables()


def prop(row):
    return "vj_" + row["address"][len("/vj/"):]


class TableTests(unittest.TestCase):
    def test_addresses_are_unique_vj_addresses(self):
        addresses = [r["address"] for r in ROWS]
        self.assertEqual(len(addresses), len(set(addresses)))
        for a in addresses:
            with self.subTest(address=a):
                self.assertRegex(a, r"^/vj/[a-z_]+$")

    def test_rows_are_well_formed(self):
        for r in ROWS:
            with self.subTest(address=r["address"]):
                self.assertIn(r["kind"], ("float", "int", "trigger"))
                self.assertLess(r["min"], r["max"])
                self.assertTrue(r["min"] <= r["default"] <= r["max"])
                if r["kind"] == "float":
                    self.assertEqual((r["min"], r["max"]), (0, 1), "a continuous control is 0..1 on the wire")
                for who in ("blender", "godot"):
                    scene = r[who]
                    self.assertTrue(scene is None or scene.get("effect"))
                    if scene is not None and r["kind"] == "float":
                        self.assertLess(scene["min"], scene["max"])

    def test_every_row_is_used_by_a_scene(self):
        for r in ROWS:
            with self.subTest(address=r["address"]):
                self.assertTrue(r["blender"] or r["godot"])

    def test_controls_md_table_is_the_rendering_of_the_json(self):
        with open(contract.CONTROLS_MD) as f:
            self.assertEqual(contract.current_table(f.read()), contract.render_table(ROWS))

    def test_readme_manual_is_the_rendering_of_the_json(self):
        with open(contract.README_MD) as f:
            self.assertEqual(contract.current_manual(f.read()), contract.render_manual(ROWS))

    def test_every_address_is_in_the_readme_manual_once(self):
        with open(contract.README_MD) as f:
            block = contract.current_manual(f.read())
        for r in ROWS:
            with self.subTest(address=r["address"]):
                self.assertEqual(block.count("| `%s` |" % r["address"]), 1)

    def test_rows_have_a_group_and_a_plain_sentence(self):
        for r in ROWS:
            with self.subTest(address=r["address"]):
                self.assertIn(r["group"], contract.GROUPS)
                self.assertTrue(r["plain"].strip() and r["plain"].endswith("."))
                self.assertNotIn("|", r["plain"])

    def test_shots_are_listed_gapless_and_fit_the_wire_range(self):
        cam = contract.by_address(ROWS)["/vj/cam"]
        for scene, shots in cam["shots"].items():
            with self.subTest(scene=scene):
                self.assertEqual([s["index"] for s in shots], list(range(len(shots))))
                self.assertEqual(len({s["name"] for s in shots}), len(shots))
                for s in shots:
                    self.assertTrue(s["name"] and s["shows"].endswith("."))
        self.assertLessEqual(len(cam["shots"]["godot"]), int(cam["max"]) + 1)

    def test_godot_shots_are_the_director_shots(self):
        """godot/colossus/director/shots.gd is the source of the Godot shot names and sentences (wire 0 is Shot value 1)."""
        with open(os.path.join(contract.ROOT, "godot", "colossus", "director", "shots.gd")) as f:
            src = f.read()

        def text(fn, key):
            body = re.search(r"static func %s\(.*?(?=\n\nstatic func|\Z)" % fn, src, re.S).group(0)
            m = re.search(r"Shot\.%s:\s*return (.*?)(?=\n\t\tShot\.|\n\treturn)" % key, body, re.S)
            if m is None:                           # the last shot is the function's final return
                return re.findall(r'return "(.*?)"', body)[-1]
            return "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1)))

        keys = ["SCALE_WIDE", "LOW_HERO", "OVER_SHOULDER", "CLOSE_GRIP", "AERIAL"]
        want = [{"index": i, "name": text("shot_name", k), "shows": text("shot_shows", k)} for i, k in enumerate(keys)]
        self.assertEqual(contract.by_address(ROWS)["/vj/cam"]["shots"]["godot"], want)

    def test_labels_are_short_unique_and_avoid_no_glossary_word(self):
        with open(os.path.join(contract.ROOT, "GLOSSARY.md")) as f:
            avoid = [w.strip().lower() for line in f if line.startswith("_Avoid_:") for w in line[len("_Avoid_:"):].split(",")]
        labels = [r["label"] for r in ROWS]
        self.assertEqual(len(labels), len(set(labels)))
        for r in ROWS:
            with self.subTest(address=r["address"]):
                self.assertTrue(1 <= len(r["label"].split()) <= 3)
                for word in avoid:
                    self.assertNotIn(word, r["label"].lower().split())

    def test_stops_are_ordered_inside_the_wire_range_and_named(self):
        for r in ROWS:
            stops = r.get("stops")
            if not stops:
                continue
            with self.subTest(address=r["address"]):
                self.assertGreaterEqual(len(stops), 2)
                self.assertEqual([s["wire"] for s in stops], sorted(s["wire"] for s in stops))
                self.assertTrue(all(r["min"] <= s["wire"] <= r["max"] and s["name"] for s in stops))

    def test_manual_pictures_exist(self):
        with open(contract.README_MD) as f:
            block = contract.current_manual(f.read())
        for path in re.findall(r'src="([^"]+)"', block):
            with self.subTest(path=path):
                self.assertTrue(os.path.exists(os.path.join(contract.ROOT, path)))

    def test_bridge_scales_block_is_the_rendering_of_the_json(self):
        with open(contract.BRIDGE_PY) as f:
            self.assertEqual(contract.current_scales(f.read()), contract.render_scales(ROWS))


class BlenderRuntimeTests(unittest.TestCase):
    blender_rows = [r for r in ROWS if r["blender"]]

    def test_rows_and_runtime_properties_are_the_same_set(self):
        self.assertEqual({prop(r) for r in self.blender_rows}, set(RT["DEFAULTS"]))

    def test_wire_default_maps_to_the_runtime_default(self):
        """The scene's tuned look is its DEFAULTS value; a wire default may be 0.5 % of the range off it (25.2 m for 25 m)."""
        for r in self.blender_rows:
            if r["kind"] == "int":
                continue
            lo, hi = r["blender"].get("min", 0), r["blender"].get("max", r["max"])
            with self.subTest(address=r["address"]):
                got = contract.scene_value(r, "blender", r["default"])
                self.assertAlmostEqual(got, RT["DEFAULTS"][prop(r)], delta=0.005 * (hi - lo))

    def test_scene_range_fits_inside_the_property_range(self):
        for r in self.blender_rows:
            if r["kind"] != "float":
                continue
            with self.subTest(address=r["address"]):
                hi = RT["RANGES"].get(prop(r), (0, 1, 0))[1]
                self.assertLessEqual(r["blender"]["max"], hi)

    def test_triggers_are_the_runtime_triggers(self):
        self.assertEqual({prop(r) for r in ROWS if r["kind"] == "trigger"}, set(RT["TRIGGERS"]))
        for r in ROWS:
            if r["kind"] == "trigger":
                with self.subTest(address=r["address"]):
                    self.assertEqual(r["max"], RT["RANGES"].get(prop(r), (0, 1, 0))[1])


class ScaleTests(unittest.TestCase):
    rows = contract.by_address()

    def test_scene_value(self):
        cases = [
            ("/vj/level", "blender", 0.5, 0.5), ("/vj/intensity", "blender", 0.5, 1.0), ("/vj/intensity", "blender", 2.0, 2.0),
            ("/vj/intensity", "blender", -1, 0.0), ("/vj/fog_height", "blender", 0.41, 25.19), ("/vj/fog_height", "godot", 1, 95.0),
            ("/vj/cam", "blender", 3.4, None), ("/vj/cam", "godot", 99, 11), ("/vj/cam_auto", "godot", 0.2, 0),
            ("/vj/shock", "blender", 1.4, 1.4), ("/vj/shock", "godot", 1.5, 1.5), ("/vj/hue", "godot", 0.5, None),
            ("/vj/cam_auto", "blender", 1, None),
        ]
        for address, who, wire, want in cases:
            with self.subTest(address=address, who=who, wire=wire):
                got = contract.scene_value(self.rows[address], who, wire)
                if want is None:
                    self.assertIsNone(got)
                else:
                    self.assertAlmostEqual(got, want)


class BlenderScenesTests(unittest.TestCase):
    """blender.scenes: which Blender scenes read a row."""

    def row(self, scenes="absent", godot=None):
        b = {"min": 0, "max": 1, "effect": "x"}
        if scenes != "absent":
            b["scenes"] = scenes
        return {"address": "/vj/x", "blender": b, "godot": godot}

    def test_the_contract_has_no_problems(self):
        self.assertEqual(contract.problems(ROWS), [])

    def test_problems(self):
        cases = [("absent", True), (None, True), ([], True), ("planet", True), (["moon"], True), (["planet", "planet"], True),
                 (["planet"], False), (["island"], False), (["planet", "island"], False), (["island", "planet"], False)]
        for scenes, bad in cases:
            with self.subTest(scenes=scenes):
                self.assertEqual(bool(contract.problems([self.row(scenes)])), bad)

    def test_a_godot_only_row_needs_no_scenes(self):
        self.assertEqual(contract.problems([{"address": "/vj/x", "blender": None, "godot": {"effect": "x"}}]), [])

    def test_manual_scene_column(self):
        godot = {"effect": "x"}
        cases = [(["planet", "island"], None, "Blender"), (["planet"], None, "Blender planet"), (["island"], None, "Blender island"),
                 (["planet", "island"], godot, "both"), (["planet"], godot, "Godot, Blender planet")]
        for scenes, g, want in cases:
            with self.subTest(scenes=scenes, godot=bool(g)):
                self.assertEqual(contract._scenes(self.row(scenes, g)), want)
        self.assertEqual(contract._scenes({"blender": None, "godot": godot}), "Godot")

    def test_island_and_planet_only_rows(self):
        cases = [("/vj/grid", ["island"]), ("/vj/grid_speed", ["island"]), ("/vj/path", ["planet"]), ("/vj/target", ["planet"]),
                 ("/vj/height", ["planet"]), ("/vj/blend", ["planet"]), ("/vj/fog", ["planet", "island"]), ("/vj/takeover", ["planet", "island"])]
        rows = contract.by_address(ROWS)
        for address, want in cases:
            with self.subTest(address=address):
                self.assertEqual(rows[address]["blender"]["scenes"], want)


if __name__ == "__main__":
    unittest.main()
