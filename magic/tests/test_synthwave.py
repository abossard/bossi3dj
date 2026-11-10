"""synthwave_magic and show_magic tests: the generators follow osc/contract.json. Run: python3 -m unittest discover magic/tests"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import magicproj as mp  # noqa: E402
import show_magic as show  # noqa: E402
import synthwave_magic as sm  # noqa: E402

PROJECTS = os.path.join(HERE, "..", "projects")


def senders(root):
    return {s["message"]: s for s in mp.osc_senders(root)}


def built(name):
    return {"synthwave_pyramids.magic": lambda: sm.build(9201, "127.0.0.1", "CAM_OUT - Blender"),
            "show.magic": show.build}[name]()


class ContractTests(unittest.TestCase):
    def test_one_sender_per_contract_row(self):
        self.assertEqual(sorted(a for a, _ in sm.OSC_OUT), sorted(sm.CONTRACT))

    def test_out_globals_start_at_the_wire_default(self):
        seeds = {g[0]: g[2] for g in sm.GLOBALS}
        for address, name in sm.OSC_OUT:
            with self.subTest(address=address):
                self.assertAlmostEqual(seeds[name], sm.CONTRACT[address]["default"], places=6)

    def test_every_sender_clamps_to_the_wire_range(self):
        root = sm.ET.fromstring(built("synthwave_pyramids.magic"))
        for address, sender in senders(root).items():
            with self.subTest(address=address):
                top = sm.CONTRACT[address]["max"]
                expr = sender["modifiers"][0]
                self.assertIn("min(%g, max(0, x + " % top, str(expr))

    def test_no_continuous_control_is_scaled_beyond_the_wire(self):
        """The Out Globals carry 0..1 already: no expression multiplies by a scene unit (x60 m, x520 m, x40 m/s, x10)."""
        scene_units = ("x*60", "x*520", "x*40", "x*10")
        for name, _src, _value, ops in sm.GLOBALS:
            if not name.startswith("Out"):
                continue
            for _kind, _param, expr in ops:
                with self.subTest(out=name):
                    self.assertFalse(any(u in expr for u in scene_units), expr)


class ProjectTests(unittest.TestCase):
    def test_projects_have_no_errors(self):
        for name in ("synthwave_pyramids.magic", "show.magic"):
            with self.subTest(project=name):
                root = sm.ET.fromstring(built(name))
                self.assertEqual([m for level, m in mp.check(root) if level == "error"], [])

    def test_committed_projects_are_what_the_generators_build(self):
        for name in ("synthwave_pyramids.magic", "show.magic"):
            with self.subTest(project=name):
                committed = mp.read(os.path.join(PROJECTS, name))
                self.assertEqual(mp.diff(committed, sm.ET.fromstring(built(name))), [])

    def test_show_project_drives_both_scenes_through_the_relay(self):
        root = sm.ET.fromstring(built("show.magic"))
        sent = senders(root)
        self.assertEqual({s["port"] for s in sent.values()}, {"9200"})
        self.assertEqual(sorted(sent), sorted(sm.CONTRACT))
        servers = [mp.param(n, "Server").get("value") for n in root.iter("Node") if n.get("pluginName") == "SyphonClient"]
        self.assertEqual(servers, [show.SYPHON_BLENDER, show.SYPHON_GODOT])

    def test_show_project_mixes_the_two_sources(self):
        root = sm.ET.fromstring(built("show.magic"))
        program = next(s for s in mp.scenes(root) if s.get("name") == "Program")
        nodes = {n.get("id"): n for n in program.iter("Node")}
        mix = next(n for n in nodes.values() if n.get("pluginName") == "Mix")
        inputs = [nodes[c.get("id")].get("pluginName") for c in mix.find("Children")]
        self.assertEqual(inputs, ["SyphonClient", "SyphonClient"])
        amount = mp.param(mix, "Amount")
        self.assertEqual(mp.global_names(root)[amount.get("feature")], show.MIX)

    def test_synthwave_project_has_no_mix(self):
        root = sm.ET.fromstring(built("synthwave_pyramids.magic"))
        self.assertEqual([n for n in root.iter("Node") if n.get("pluginName") == "Mix"], [])


if __name__ == "__main__":
    unittest.main()
