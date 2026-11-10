"""edm_analysis_magic tests. Run: python3 -m unittest discover magic/tests"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import edm_analysis_magic as edm  # noqa: E402
import magicproj as mp  # noqa: E402


def kicks(bpm, seconds, rate=94.0):
    """Raw tap input: a four-on-the-floor kick with an offbeat hat, sampled
    at Magic's audio-analysis rate."""
    period = 60.0 / bpm
    raw = {n: [] for n in edm.RAW}
    for i in range(int(seconds * rate)):
        t = i / rate
        since = t % period
        hat = (t + period / 2) % period
        kick = 0.45 * math.exp(-since / 0.08)
        v = {"L0": 0.03 + kick, "L1": 0.04 + 0.6 * kick, "L2": 0.08, "L3": 0.08 + 0.05 * math.exp(-hat / 0.03),
             "L4": 0.05 + 0.25 * math.exp(-hat / 0.03), "LV": 0.4 + kick, "VocL": 0.1, "Tone": 0.5, "Pitch": 0.3}
        for name in edm.RAW:
            raw[name].append((t, v.get(name, v.get("L" + name[1:], v.get(name[:-1] + "L", 0.0)))))
    return raw


class BuildTests(unittest.TestCase):
    root = edm.build()

    def test_project_has_no_errors(self):
        self.assertEqual([m for level, m in mp.check(self.root) if level == "error"], [])

    def test_every_variant_has_every_signal(self):
        names = set(mp.global_names(self.root).values())
        for p in edm.VARIANTS:
            for sig, _, _ in edm.SIGNALS:
                with self.subTest(variant=p, signal=sig):
                    self.assertIn(p + sig, names)

    def test_every_meter_scene_shows_every_signal(self):
        ids = {v: k for k, v in mp.global_names(self.root).items()}
        for p in edm.VARIANTS:
            scene = next(s for s in mp.scenes(self.root) if s.get("name").startswith(p.upper() + " "))
            linked = {iv.get("feature") for iv in scene.iter("InputValue") if iv.get("layerID") == str(mp.GLOBAL_LAYER)}
            for sig, _, _ in edm.SIGNALS:
                with self.subTest(variant=p, signal=sig):
                    self.assertIn(ids[p + sig], linked)

    def test_tap_is_off_unless_asked(self):
        for tap, power in ((False, "0"), (True, "1")):
            with self.subTest(tap=tap):
                node = next(n for n in edm.build(tap).iter("Node") if n.get("pluginName") == "OSC Tap")
                self.assertEqual(mp.param(node, "Power").get("value"), power)


class ExpressionTests(unittest.TestCase):
    def test_exprtk_subset(self):
        cases = [("var a := 2; var b := a*3; a + b", 8), ("if(3 != 4 and not(2 > 3), 1, 0)", 1), ("2^3 + 7 % 4", 11),
                 ("round(2.5) + round(-2.5)", 0), ("round(-0.4)", 0), ("frac(2.75)", 0.75), ("x*2 + y", 7)]
        for expr, want in cases:
            with self.subTest(expr):
                env = dict(edm.FUNCS, x=3.0, y=1.0)
                exec(edm.py_code(expr), env)
                self.assertAlmostEqual(env["__r"], want)


class SimulationTests(unittest.TestCase):
    def test_beat_clock_finds_the_tempo(self):
        for bpm in (124, 140):
            with self.subTest(bpm=bpm):
                out, times = edm.simulate(edm.all_globals(), kicks(bpm, 30), 120, ["aBPM", "aConf", "aKickOn"])
                end = [i for i, t in enumerate(times) if t > 20]
                self.assertAlmostEqual(sum(out["aBPM"][i] for i in end) / len(end), bpm, delta=bpm * 0.02)
                self.assertGreater(min(out["aConf"][i] for i in end), 0.5)
                kicks_per_s = sum(out["aKickOn"][i] for i in end) / (times[-1] - 20)
                self.assertAlmostEqual(kicks_per_s, bpm / 60, delta=0.3)


if __name__ == "__main__":
    unittest.main()
