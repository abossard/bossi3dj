"""The bridge's wire-to-scene scaling, without Blender. Run: python3 -m unittest discover blender/tests"""
import os
import sys
import types
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
            ("/vj/grid_speed", 0.15, 0.6), ("/vj/cam_speed", 0.25, 1.0), ("/vj/blend", 0.5, 30.0), ("/vj/takeover", 0.33, 19.8), ("/vj/height", 0.3, 0.3),
            ("/vj/fog_height", 0.41, 25.19), ("/vj/fog_scale", 0.25, 257.5), ("/vj/fog_speed", 0.25, 10.0),
            ("/vj/fog_glow", 0.3, 0.6), ("/vj/star_speed", 1.0, 10.0),
            ("/vj/cam", 3.0, 3.0), ("/vj/cam", 3.4, 3.0), ("/vj/cam", 3.6, 4.0), ("/vj/cam", 42, 11.0), ("/vj/cam", -1, 0.0),
            ("/vj/path", 2.0, 2.0), ("/vj/path", 2.4, 2.0), ("/vj/path", 2.6, 3.0), ("/vj/path", 42, 3.0), ("/vj/target", -1, 0.0), ("/vj/target", 6, 6.0),
            ("/vj/shock", 0.0, 0.0), ("/vj/shock", 0.6, 0.6), ("/vj/shock", 1.4, 1.4), ("/vj/meteor", 1.0, 1.0), ("/vj/hit", 1.0, 1.0),
        ]
        for address, wire, want in cases:
            with self.subTest(address=address, wire=wire):
                self.assertAlmostEqual(bridge.scale_wire(address, wire), want, places=6)

    def test_addresses_that_are_not_blender_rows_are_ignored(self):
        for address in ("/vj/cam_auto", "/vj/flight", "/vj/boost", "/vj/unknown", "/audio/beat/onbeat", "/lab/ping", "vj/level", ""):
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
            (3, range(7), 3), (9, range(7), 6), (11, range(7), 6), (4, [0, 2, 5], 2), (0, [1, 2], 1), (2, [], None), (0, [0], 0),
        ]
        for n, available, want in cases:
            with self.subTest(n=n, available=list(available)):
                self.assertEqual(bridge.camera_index(n, available), want)


class FakeScene(dict):
    frame_current = 1
    camera = None

    def update_tag(self):
        pass


class FakeObjects(list):
    def get(self, name):
        return next((o for o in self if o.name == name), None)


class CameraCutTests(unittest.TestCase):
    """Bridge.write with a fake bpy: the island cuts scene.camera on /vj/cam, the planet ignores the address."""

    def run_write(self, names, wire):
        objects = FakeObjects(types.SimpleNamespace(name=n, type="CAMERA" if n.startswith("CAM") else "EMPTY") for n in names)
        scene = FakeScene()
        scene.camera = objects.get("CAM_0")
        fake = types.SimpleNamespace(context=types.SimpleNamespace(scene=scene, window_manager=None), data=types.SimpleNamespace(objects=objects))
        old, bridge.bpy = bridge.bpy, fake
        self.addCleanup(setattr, bridge, "bpy", old)
        b = bridge.Bridge("127.0.0.1", 0, artnet_enabled=False)
        self.addCleanup(b.sock.close)
        b.is_trigger = lambda k: False
        b.write({"/vj/cam": bridge.wire_to_scene("/vj/cam", [wire])})
        return scene, b

    def test_cut(self):
        island = ["CAM_%d" % i for i in range(7)]
        cases = [(island, 3, "CAM_3", 3.0, 0), (island, 11, "CAM_6", 11.0, 0), (island, 0, "CAM_0", 0.0, 0),
                 (["CAM_0", "CAM_2"], 1, "CAM_0", 1.0, 0), (["Planet_Centre", "CAM_0", "CAM_3"], 3, "CAM_0", None, 1)]
        for names, wire, camera, prop, ignored in cases:
            with self.subTest(names=names, wire=wire):
                scene, b = self.run_write(names, wire)
                self.assertEqual(scene.camera.name, camera)
                self.assertEqual(scene.get("vj_cam"), prop)
                self.assertEqual(b.ignored, ignored)


if __name__ == "__main__":
    unittest.main()
