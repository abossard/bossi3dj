"""robot_magic.py: the generated project is valid, has the planned modules and links, and its Globals run the Clip Graph of
clip_graph.py. Run: python3 -m unittest discover robot/magic/tests

The Globals are run by a small interpreter of the ExprTk subset the graph uses, with Magic's rule that every Global reads the
previous frame's values (magic-projects skill, Semantics). It is not Magic: whether Magic runs them the same way is the user's check.
"""
import json
import math
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "magic"))
import clip_graph as cg  # noqa: E402
import magicproj as mp  # noqa: E402
import manifest as mf  # noqa: E402
import robot_magic as rm  # noqa: E402
from test_manifest import package_with_media  # noqa: E402


def generated(tmp, **kw):
    root = package_with_media(tmp)
    out = os.path.join(root, "robot.magic")
    return rm.build_project(os.path.join(root, "manifest.json"), out, audio_device="TestDevice", **kw), out, root


# ------------------------------------------------------------ the interpreter

def _translate(expr):
    return re.sub(r"\bif\(", "_if(", expr)


ENV = {"_if": lambda c, a, b: a if c else b, "floor": math.floor, "sin": math.sin, "min": min, "max": max, "abs": abs}


def simulate(globals_, drive, frames):
    """Yield the value dict of each frame. `drive(frame)` gives the externally driven Globals (Beats, Bars, Phase, EnergyAvg, BPM)."""
    code = {}
    for name, value, source, mods in globals_:
        code[name] = [compile(_translate(e), name, "eval") for kind, e in mods]
    prev = {name: value for name, value, _s, _m in globals_}
    prev.update(drive(0))
    for f in range(frames):
        cur = {}
        for name, value, source, mods in globals_:
            if source is None:
                cur[name] = prev[name]
                continue
            x = prev[source.split(":", 1)[1]] if source.startswith("global:") else 0
            for c in code[name]:
                x = eval(c, ENV, dict(prev, x=x, y=prev[name]))
            cur[name] = x
        cur.update(drive(f + 1))
        prev = cur
        yield cur


class Run:
    """A simulated walk: beats at a fixed frame interval, one energy per beat, graph Globals only."""
    FRAMES_PER_BEAT = 29

    def __init__(self, m, energies, **graph):
        self.m, self.energies = m, energies
        self.globals = rm.graph_globals(m, **graph)
        self.frames = list(simulate(self.globals, self.drive, self.FRAMES_PER_BEAT * (len(energies) + 1)))

    def beat_of(self, f):
        return f // self.FRAMES_PER_BEAT

    def drive(self, f):
        beat = self.beat_of(f)
        e = self.energies[min(max(0, beat - 1), len(self.energies) - 1)]
        return {"Beats": beat, "Bars": beat // 4, "Phase": (f % self.FRAMES_PER_BEAT) / self.FRAMES_PER_BEAT, "EnergyAvg": e, "BPM": 124}

    def settled(self, beat):
        """Values just before the next beat: the pipeline has run."""
        return self.frames[(beat + 1) * self.FRAMES_PER_BEAT - 2]


class GraphGlobalsTests(unittest.TestCase):
    def setUp(self):
        self.m = mf.Manifest(json.load(open(os.path.join(HERE, "..", "..", "package", "fixture", "manifest.json"))))

    def test_globals_match_the_model(self):
        energies = ([0.1] * 8 + [0.4] * 8 + [0.9] * 8 + [0.4, 0.1, 0.9, 0.3] * 4) * 2
        for seed, rate in [(0, 1.0), (1, 1.0), (7.5, 0.5), (3, 0.0)]:
            with self.subTest(seed=seed, cut_rate=rate):
                run = Run(self.m, energies, seed=seed, cut_rate=rate)
                model = cg.ClipGraph(self.m, seed=seed, cut_rate=rate)
                walk = model.walk(energies)
                for beat in range(1, len(energies) + 1):
                    v, s = run.settled(beat), walk[beat - 1]
                    self.assertEqual((v["Move"], v["Angle"], v["MoveStart"]),
                                     (self.m.moves.index(self.m.move(s.move)), self.m.angle_ids.index(s.angle), s.start), "beat %d" % beat)
                    self.assertEqual(v["Sel"], v["Move"] * 2 + v["Angle"])
                    self.assertEqual(v["OutClip"], model.clip_index(s), "beat %d" % beat)

    def test_energy_steers_the_tier(self):
        for energy, tier in [(0.1, "calm"), (0.4, "build"), (0.9, "drop")]:
            with self.subTest(tier=tier):
                run = Run(self.m, [energy] * 20)
                moves = {self.m.moves[int(v["Move"])].name for v in run.frames[4 * 29 * 2:]}
                self.assertTrue(all(self.m.move(x).tier == tier for x in moves), moves)

    def test_start_pulse_is_two_frames_at_each_move_change(self):
        run = Run(self.m, [0.4] * 24, seed=2)
        pulses = [i for i, v in enumerate(run.frames) if v["StartPulse"] > 0.5]
        changes = [i for i in range(1, len(run.frames)) if run.frames[i]["MoveStart"] != run.frames[i - 1]["MoveStart"]]
        self.assertEqual(len(changes), 6)
        for c in changes:
            with self.subTest(change_frame=c):
                self.assertIn(c, pulses)
                self.assertIn(c + 1, pulses)
                self.assertNotIn(c + 2, pulses)
        self.assertEqual(len(pulses), 2 * len(changes))

    def test_pipeline_latency_is_under_six_frames(self):
        """From the frame the beat count changes to the frame Move and Angle are latched."""
        run = Run(self.m, [0.4] * 24, seed=2)
        for beat in (4, 8, 12, 16):
            f0 = beat * run.FRAMES_PER_BEAT
            changed = next(i for i in range(f0, f0 + 20) if run.frames[i]["MoveStart"] == beat) - f0
            with self.subTest(beat=beat):
                self.assertLessEqual(changed, 5)

    def test_clip_frame_counts_from_the_clip_start(self):
        energies = [0.4] * 12
        run = Run(self.m, energies, seed=2)
        model = cg.ClipGraph(self.m, seed=2)
        walk = model.walk(energies)
        for beat in range(1, 12):
            for f in range(beat * run.FRAMES_PER_BEAT + 6, (beat + 1) * run.FRAMES_PER_BEAT - 1):
                with self.subTest(frame=f):
                    expect = model.frame(walk[beat - 1], beat, (f % run.FRAMES_PER_BEAT) / run.FRAMES_PER_BEAT)
                    self.assertLessEqual(abs(run.frames[f]["OutFrame"] - expect), 1)

    def test_speed_ratio_is_bpm_over_manifest_bpm(self):
        run = Run(self.m, [0.4] * 4)
        self.assertAlmostEqual(run.settled(2)["SpeedRatio"], 1.0)


class ProjectTests(unittest.TestCase):
    def test_check_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, out, _ = generated(tmp)
            problems = mp.check(mp.read(out), os.path.dirname(out))
            self.assertEqual(problems, [])

    def test_semantic_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, out, _ = generated(tmp)
            self.assertEqual(snapshot(mp.read(out)), SNAPSHOT)

    def test_osc_rows_are_one_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, out, _ = generated(tmp, osc_port=9999)
            senders = {s["message"]: s for s in mp.osc_senders(mp.read(out))}
            self.assertEqual(sorted(senders), sorted(a for a, _g, _t in rm.OSC_ROWS))
            for s in senders.values():
                self.assertEqual((s["ip"], s["port"]), ("127.0.0.1", "9999"))

    def test_default_osc_target_is_the_scene_port(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, out, _ = generated(tmp)
            self.assertEqual({s["port"] for s in mp.osc_senders(mp.read(out))}, {"9201"})

    def test_every_video_file_is_a_manifest_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, out, pkg = generated(tmp)
            m = mf.load(os.path.join(pkg, "manifest.json"))
            files = [iv.get("value") for iv in root.iter("InputValue") if iv.get("name") == "File"]
            expect = [c["passes"][k] for k in ("shadow", "beauty") for mv in m.moves for a in m.angle_ids
                      for c in [m.clips[m.clip_index(mv.name, a)]]]
            self.assertEqual(files, expect)

    def test_syphon_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, out, _ = generated(tmp, live="ROBOT_TEST - Blender")
            servers = [iv.get("value") for iv in root.iter("InputValue") if iv.get("name") == "Server"]
            self.assertEqual(servers, ["ROBOT_TEST - Blender"])
        self.assertEqual(rm.LIVE_SERVER, "ROBOT_LIVE - Blender")

    def test_android_draws_without_the_live_source(self):
        """A missing Syphon server blacks out whatever is wired to it, so the gate picks the Android alone at LiveOn 0 and the live branch hangs off input 1 only."""
        with tempfile.TemporaryDirectory() as tmp:
            root, _, _ = generated(tmp)
            scene = next(s for s in mp.scenes(root) if s.get("name") == "Robot")
            nodes = {n.get("id"): n for n in mp.scene_nodes(scene)[1:]}
            plug = {i: n.get("pluginName") for i, n in nodes.items()}

            def reaches(i, plugin):
                return plug[i] == plugin or any(reaches(c.get("id"), plugin) for c in nodes[i].iter("Child") if c.get("id") in nodes)

            gate = next(n for n in nodes.values() if [c.get("id") for c in n.iter("Child")] and plug[[c.get("id") for c in n.iter("Child")][0]] == "Mask"
                        and plug[n.get("id")] == "InputSelector")
            first, second = [c.get("id") for c in gate.iter("Child")]
            self.assertFalse(reaches(first, "SyphonClient"))
            self.assertTrue(reaches(second, "SyphonClient"))
            self.assertEqual(float(mp.find_global(root, rm.LIVE_GATE).get("value")), 0)

    def test_clock_globals_exist_in_the_audio_source(self):
        names = {g[0] for g in rm.sm.GLOBALS}
        self.assertEqual([n for n in rm.CLOCK_GLOBALS if n not in names], [])


def snapshot(root):
    """Per scene: each module's plugin and the plugins of its inputs, plus the Globals its params link to."""
    out = {}
    globals_by_id = mp.global_names(root)
    for scene in mp.scenes(root):
        nodes = mp.scene_nodes(scene)[1:]
        plug = {n.get("id"): n.get("pluginName") for n in nodes}
        rows = []
        for n in nodes:
            links = sorted("%s<-%s" % (iv.get("name"), globals_by_id.get(iv.get("feature"))) for iv in mp.params(n)
                           if iv.get("linked") == "1" and iv.get("layerID") == str(mp.GLOBAL_LAYER))
            rows.append((plug[n.get("id")], [plug[c.get("id")] for c in n.iter("Child")], links))
        out[scene.get("name")] = rows
    return out


VIDEO = ("VideoFile", [], ["Goto Start<-StartPulse", "Speed<-SpeedRatio"])
SNAPSHOT = {
    "Robot": [("SyphonClient", [], [])] + [VIDEO] * 8 + [("InputSelector", ["VideoFile"] * 8, ["Input #<-Sel"]),
                                                            ("Blend", ["SyphonClient", "InputSelector"], [])] + [VIDEO] * 8
    + [("InputSelector", ["VideoFile"] * 8, ["Input #<-Sel"]), ("Mask", ["InputSelector", "InputSelector"], []),
       ("Transparency", ["Mask", "Blend"], []), ("OSC Out", [], []), ("InputSelector", ["Mask", "Transparency"], ["Input #<-LiveOn"])],
    "OSC Out": [("OSCSender", [], ["Value<-OutClip"]), ("OSCSender", [], ["Value<-OutFrame"]), ("OSCSender", [], ["Value<-OutAngle"])],
}

if __name__ == "__main__":
    unittest.main()
