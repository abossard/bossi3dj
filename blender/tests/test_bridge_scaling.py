"""The bridge's wire-to-scene scaling, without Blender. Run: python3 -m unittest discover blender/tests"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "osc"))
import blender_osc_bridge as bridge  # noqa: E402  (bpy is None outside Blender)
import contract  # noqa: E402


class ScaleWireTests(unittest.TestCase):
    def test_known_messages(self):
        cases = [
            ("/vj/level", 0.5, 0.5), ("/vj/level", 1.7, 1.0), ("/vj/level", -0.2, 0.0),
            ("/vj/intensity", 0.0, 0.0), ("/vj/intensity", 0.5, 1.0), ("/vj/intensity", 1.0, 2.0),
            ("/vj/grid_speed", 0.15, 0.6), ("/vj/cam_speed", 0.25, 1.0), ("/vj/blend", 0.5, 1.0),
            ("/vj/fog_height", 0.42, 25.2), ("/vj/fog_scale", 0.26, 260.0), ("/vj/fog_speed", 0.25, 10.0),
            ("/vj/fog_glow", 0.3, 0.6), ("/vj/star_speed", 1.0, 10.0),
            ("/vj/cam", 3.0, 3.0), ("/vj/cam", 3.4, 3.0), ("/vj/cam", 3.6, 4.0), ("/vj/cam", 42, 10.0), ("/vj/cam", -1, 0.0),
            ("/vj/shock", 0.0, 0.0), ("/vj/shock", 0.6, 0.6), ("/vj/shock", 1.4, 1.4), ("/vj/meteor", 1.0, 1.0), ("/vj/hit", 1.0, 1.0),
        ]
        for address, wire, want in cases:
            with self.subTest(address=address, wire=wire):
                self.assertAlmostEqual(bridge.scale_wire(address, wire), want, places=6)

    def test_addresses_that_are_not_blender_rows_are_ignored(self):
        for address in ("/vj/cam_auto", "/vj/unknown", "/audio/beat/onbeat", "/lab/ping", "vj/level", ""):
            with self.subTest(address=address):
                self.assertIsNone(bridge.scale_wire(address, 0.5))
                self.assertIsNone(bridge.wire_to_scene(address, [0.5]))

    def test_wire_to_scene_takes_the_first_number(self):
        cases = [
            ("/vj/intensity", [0.5], [1.0]), ("/vj/intensity", [1], [2.0]), ("/vj/intensity", ["x", 0.25], [0.5]),
            ("/vj/intensity", [True, 0.25], [0.5]), ("/vj/intensity", ["x"], None), ("/vj/intensity", [], None),
        ]
        for address, args, want in cases:
            with self.subTest(address=address, args=args):
                self.assertEqual(bridge.wire_to_scene(address, args), want)

    def test_same_scaling_as_the_contract_module(self):
        rows = contract.load()
        for r in rows:
            for wire in (r["min"], r["default"], (r["min"] + r["max"]) / 2, r["max"], r["max"] + 1):
                with self.subTest(address=r["address"], wire=wire):
                    want = contract.scene_value(r, "blender", wire)
                    got = bridge.scale_wire(r["address"], wire)
                    if want is None:
                        self.assertIsNone(got)
                    else:
                        self.assertAlmostEqual(got, want, places=6)

    def test_every_blender_row_is_in_scales(self):
        self.assertEqual(set(bridge.SCALES), {r["address"] for r in contract.load() if r["blender"]})


class CameraIndexTests(unittest.TestCase):
    def test_cut_takes_the_highest_camera_not_above_n(self):
        cases = [
            (3, range(7), 3), (9, range(7), 6), (10, range(11), 10), (4, [0, 2, 5], 2), (0, [1, 2], 1), (2, [], None), (0, [0], 0),
        ]
        for n, available, want in cases:
            with self.subTest(n=n, available=list(available)):
                self.assertEqual(bridge.camera_index(n, available), want)


if __name__ == "__main__":
    unittest.main()
