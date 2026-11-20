"""Check the saved rehearsal graph without loading Magic."""

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import magicproj as mp  # noqa: E402
import rehearsal_magic as rehearsal  # noqa: E402


class RehearsalProjectTests(unittest.TestCase):
    def test_separate_media_have_one_lazy_program_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            media = folder / "media"
            media.mkdir()
            files = [media / f"{name}.mp4" for name in ("arrive", "build", "peak", "release")]
            for path in files:
                path.touch()
            project = rehearsal.build(folder, *files, osc_in=19802, server="MAGIC_REHEARSAL_TEST")
            output = folder / "rehearsal.magic"
            mp.write(output, project)
            root = mp.read(output)
            self.assertEqual(mp.check(root, folder), [])
            self.assertEqual((root.get("videoSharingWidth"), root.get("videoSharingHeight")), ("480", "270"))
            self.assertEqual(root.find(".//Track[@isOSC='1']").get("channel"), "19802")
            globals_by_name = {row["name"]: row for row in mp.global_table(root)}
            self.assertEqual(globals_by_name["ProgramSelection"]["source"], "osc:/show/selection")
            self.assertEqual(globals_by_name["Reactivity"]["source"], "osc:/show/reactivity")
            master = mp.node_table(root, "Master")
            by_id = {node["id"]: node for node in master}
            selector = next(node for node in master if node["plugin"] == "InputSelector")
            self.assertEqual([by_id[node]["scene_module"] for node in selector["inputs"]],
                             ["Safe", "Synthwave Planet", "Robot"])
            self.assertEqual([node["plugin"] for node in mp.node_table(root, "Safe")], ["Magic", "Linear Gradient"])
            self.assertEqual({value.get("value") for value in root.findall(".//InputValue[@name='File']")},
                             {str(path.relative_to(folder)) for path in files})

    def test_two_media_are_sufficient_for_all_four_cues(self):
        folder = Path("/tmp")
        root = rehearsal.build(folder, folder / "planet.mp4", folder / "robot.mp4")
        self.assertEqual([n["plugin"] for n in mp.node_table(root, "Synthwave Planet")], ["Magic", "VideoFile"])
        self.assertEqual([n["plugin"] for n in mp.node_table(root, "Robot")], ["Magic", "VideoFile"])

    def test_linked_live_world_sends_scene_controls_and_masks_over_robot_background(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            build = folder / "build.mov"
            peak = folder / "peak.mov"
            build.touch()
            peak.touch()
            root = rehearsal.build(folder, None, build, peak, osc_in=19802,
                                   server="MAGIC_REHEARSAL_TEST", planet_live=rehearsal.PLANET_SERVER,
                                   robot_live=rehearsal.ROBOT_SERVER, osc_out=19801, linked_world=True)
            self.assertEqual(mp.check(root, folder), [])
            planet = mp.node_table(root, "Synthwave Planet")
            self.assertEqual([n["plugin"] for n in planet], ["Magic", "SyphonClient"])
            robot = {n["id"]: n for n in mp.node_table(root, "Robot")}
            comp = next(n for n in robot.values() if n["plugin"] == "Transparency")
            self.assertEqual([robot[n]["plugin"] for n in comp["inputs"]], ["Mask", "SyphonClient"])
            globals_by_name = {row["name"]: row for row in mp.global_table(root)}
            self.assertEqual(globals_by_name["WorldReady"]["source"], "osc:/show/world_ready")
            self.assertEqual(globals_by_name["RobotHeartbeat"]["source"], "osc:/vj/live_layer")
            output = {row["message"]: row for row in mp.osc_senders(root)}
            self.assertEqual({row["port"] for row in output.values()}, {"19801"})
            self.assertEqual(output.keys(), {"/vj/angle", "/vj/bass", "/vj/beat", "/vj/energy", "/vj/level"})

    def test_standalone_planet_uses_cue_presets_and_no_strobe(self):
        root = rehearsal.build(Path("/tmp"), None, Path("/tmp/build.mov"), planet_live=rehearsal.PLANET_SERVER)
        output = {row["message"]: row for row in mp.osc_senders(root)}
        self.assertIn("if(x == 3, 0.025, 0.045)", [modifier[2] for modifier in output["/vj/cam_speed"]["modifiers"]])
        self.assertEqual([modifier[2] for modifier in output["/vj/strobe"]["modifiers"]], ["0"])

    def test_cinema_reframes_the_live_composite_and_accepts_hit_and_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            foreground = folder / "build.mov"
            foreground.touch()
            root = rehearsal.build(folder, None, foreground, osc_in=19802, server="MAGIC_REHEARSAL_TEST",
                                   planet_live=rehearsal.PLANET_SERVER, robot_live="CUSTOM_LIVE - Blender",
                                   osc_out=19801, linked_world=True, size=(960, 540), robot_cinema=True)
            self.assertEqual(mp.check(root, folder), [])
            self.assertEqual((root.get("videoSharingWidth"), root.get("videoSharingHeight")), ("960", "540"))
            globals_by_name = {row["name"]: row for row in mp.global_table(root)}
            self.assertEqual(globals_by_name["RobotCenterY"]["source"], "osc:/show/robot/framing 2")
            self.assertEqual(globals_by_name["RobotHitRaw"]["source"], "osc:/show/robot/hit 2")
            self.assertEqual(globals_by_name["RobotRestartToken"]["source"], "osc:/show/robot/restart")
            robot = {row["id"]: row for row in mp.node_table(root, "Robot")}
            program = next(row for row in robot.values() if row["plugin"] == "Magic")
            translation = robot[program["inputs"][0]]
            self.assertEqual(translation["plugin"], "Translate")
            scale = robot[translation["inputs"][0]]
            self.assertEqual(scale["plugin"], "Scale")
            gate = robot[scale["inputs"][0]]
            self.assertEqual(gate["plugin"], "InputSelector")
            composite, hit_overlay = [robot[node_id] for node_id in gate["inputs"]]
            self.assertEqual([robot[node_id]["plugin"] for node_id in composite["inputs"]], ["Mask", "SyphonClient"])
            self.assertEqual(hit_overlay["inputs"][1], composite["id"])
            foreground_node = next(row for row in robot.values() if row["plugin"] == "VideoFile")
            goto_start = next(param for param in foreground_node["params"] if param["name"] == "Goto Start")
            self.assertEqual(goto_start["source"], "global:RobotStartPulse")
