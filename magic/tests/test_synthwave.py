"""synthwave_magic and show_magic tests: the generators follow osc/contract.json. Run: python3 -m unittest discover magic/tests"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import magic_manual as manual  # noqa: E402
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


class ControlTests(unittest.TestCase):
    """Every address has a control Global named like it, holding the contract's default, so a person finds it by the address."""

    def setUp(self):
        self.root = sm.ET.fromstring(built("show.magic"))
        self.controls = {g.get("name"): g for g in mp.global_ivs(self.root)}

    def test_every_address_has_an_unlinked_control_with_the_contract_default(self):
        for address, row in sm.CONTRACT.items():
            name = manual.control_name(address)
            with self.subTest(address=address, control=name):
                self.assertIn(name, self.controls)
                self.assertEqual(self.controls[name].get("linked"), "0")
                self.assertAlmostEqual(float(self.controls[name].get("value")), row["default"], places=6)

    def test_control_names_follow_the_addresses(self):
        for address, expected in (("/vj/fog_height", "FogHeight"), ("/vj/cam_auto", "CamAuto"), ("/vj/moon_phase", "MoonPhase"), ("/vj/level", "Level")):
            with self.subTest(address=address):
                self.assertEqual(manual.control_name(address), expected)

    def test_the_music_follows_exactly_the_addresses_named_in_MUSIC(self):
        self.assertEqual({r[0] for r in manual.rows(self.root) if r[3]}, set(sm.MUSIC))

    def test_no_music_means_the_controls(self):
        """The music enters every address through Follow = Live x React, and Live is 0 without sound."""
        follow = self.controls["Follow"]
        self.assertEqual([e for _k, _p, e, _b in mp.modifiers(follow)], ["Live*React"])
        live = " ".join(e for _k, _p, e, _b in mp.modifiers(self.controls["Live"]) if e)
        self.assertIn("EnergyNow >", live)

    def test_cam_is_manual_and_for_godot_only(self):
        expr = [e for _k, _p, e, _b in mp.modifiers(self.controls["OutCam"]) if e][0]
        self.assertEqual(expr, "floor(Cam*11.999)")
        for gone in ("CamCount", "Flight", "Boost", "OutFlight", "OutBoost"):
            with self.subTest(gone=gone):
                self.assertNotIn(gone, self.controls)

    def test_path_and_target_step_with_the_music_hold_through_a_gap_or_take_the_control(self):
        cases = [("OutPath", "Path", "Moves % 4", 4), ("OutTarget", "Target", "(Moves*3) % 7", 7)]
        for out, name, music, stops in cases:
            with self.subTest(out=out):
                expr = [e for _k, _p, e, _b in mp.modifiers(self.controls[out]) if e][0]
                self.assertEqual(expr, "if(%sFollow > 0.5, %s, if(%sFree*React > 0.5, y, floor(%s*%d.999)))" % (name, music, name, name, stops - 1))

    def test_every_steered_control_has_takeover(self):
        """A touched control is the user's for Takeover x 60 s: <Name>Touch keeps the clock of its last change, <Name>Follow is 0 meanwhile."""
        for name in sm.STEERED:
            with self.subTest(control=name):
                touch = [e for _k, _p, e, _b in mp.modifiers(self.controls[name + "Touch"]) if e][0]
                free = [e for _k, _p, e, _b in mp.modifiers(self.controls[name + "Free"]) if e][0]
                follow = [e for _k, _p, e, _b in mp.modifiers(self.controls[name + "Follow"]) if e][0]
                self.assertEqual(touch, "if(Clock > 1 and abs(%s - %sPrev) > 0.0001, Clock, y)" % (name, name))
                self.assertEqual(free, "if(%sTouch > 0 and Clock - %sTouch < Takeover*60, 0, 1)" % (name, name))
                self.assertEqual(follow, "Follow*%sFree" % name)

    def test_every_music_address_reads_its_own_takeover(self):
        outs = dict(sm.OSC_OUT)
        for address in sm.MUSIC:
            if address == "/vj/shock":
                continue
            name = manual.control_name(address)
            with self.subTest(address=address):
                exprs = " ".join(e for _k, _p, e, _b in mp.modifiers(self.controls[outs[address]]) if e)
                self.assertIn(name + "Follow", exprs)


class ProjectTests(unittest.TestCase):
    def test_show_project_publishes_its_own_syphon_output(self):
        root = sm.ET.fromstring(built("show.magic"))
        info = mp.summary(root)["syphon"]
        self.assertEqual((info["on"], info["name"], info["size"]), (True, show.SYPHON_OUT, "1920x1080"))
        self.assertNotIn(show.SYPHON_OUT, (show.SYPHON_BLENDER, show.SYPHON_GODOT))

    def test_synthwave_project_keeps_magics_output_off(self):
        self.assertFalse(mp.summary(sm.ET.fromstring(built("synthwave_pyramids.magic")))["syphon"]["on"])

    def test_synthetic_show_build_is_clean_and_keeps_every_sender(self):
        root = sm.ET.fromstring(show.build(globals_=show.show_synthetic()))
        self.assertEqual([m for level, m in mp.check(root) if level == "error"], [])
        self.assertEqual(sorted(senders(root)), sorted(sm.CONTRACT))

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

    def test_show_project_drives_both_scenes_on_one_port(self):
        root = sm.ET.fromstring(built("show.magic"))
        sent = senders(root)
        self.assertEqual({s["port"] for s in sent.values()}, {"9201"})
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

    def test_the_mix_is_bypassed_while_the_fader_is_down(self):
        """A Mix draws black while its second server is missing, even at Amount 0: with Godot parked the program must skip it."""
        root = sm.ET.fromstring(built("show.magic"))
        mix = next(n for n in root.iter("Node") if n.get("pluginName") == "Mix")
        bypass = mp.param(mix, "Bypass")
        self.assertEqual(mp.global_names(root)[bypass.get("feature")], show.MIX)
        self.assertIn("if(x < 0.01, 1, 0)", [e for _k, _p, e, _b in mp.modifiers(bypass) if e])

    def test_synthwave_project_has_no_mix(self):
        root = sm.ET.fromstring(built("synthwave_pyramids.magic"))
        self.assertEqual([n for n in root.iter("Node") if n.get("pluginName") == "Mix"], [])


if __name__ == "__main__":
    unittest.main()
