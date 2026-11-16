"""live_test.py: the numbers of the live run come out right on synthetic event logs. Run: python3 -m unittest discover robot/magic/tests"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "magic"))
import live_test as lt  # noqa: E402
import manifest as mf  # noqa: E402

FIXTURE = os.path.join(HERE, "..", "..", "package", "fixture", "manifest.json")
F = 1.0 / lt.FPS


def ev(name, pairs):
    return [(t, name, float(v)) for t, v in pairs]


class LayersTests(unittest.TestCase):
    def test_layers_at(self):
        for bar, name, layers in [(0, "intro", "k"), (3, "intro", "k"), (4, "drop", "ks"), (12, "breakdown", "p"), (16, "buildup", "pr"),
                                  (20, "drop", "ks"), (47, "drop", "ks"), (99, "drop", "ks")]:
            with self.subTest(bar=bar):
                self.assertEqual(lt.layers_at(bar), (name, layers))

    def test_the_plan_fills_the_run(self):
        self.assertGreaterEqual(sum(p[0] for p in lt.PLAN) * 4 * lt.SPB, lt.SECONDS)

    def test_tier_of_section(self):
        for section, tier in [(0, 0), (2, 1), (3, 2), (4, 0), (2.9, 2)]:
            with self.subTest(section=section):
                self.assertEqual(lt.tier_of_section(section), tier)

    def test_the_track_has_every_layer_in_its_bars(self):
        with tempfile.TemporaryDirectory() as tmp:
            short = [(1, "intro", "k"), (1, "drop", "ks")]
            path = os.path.join(tmp, "t.wav")
            lt.track(path, short)
            self.assertGreater(os.path.getsize(path), int(2 * 4 * lt.SPB * lt.RATE) * 2)


class CutTests(unittest.TestCase):
    def events(self):
        e = ev("Beats", [(1.0, 4), (1.5, 5), (2.0, 6)]) + ev("Move", [(0.5, 0), (1.0 + 4 * F, 2)]) + ev("Angle", [(0.5, 0), (1.0 + 4 * F, 1), (1.5 + 5 * F, 2)])
        return sorted(e)

    def test_move_change_after_a_bar_line_in_frames(self):
        cuts = lt.cut_times(self.events())
        kinds = [(c[1], round(c[2]), c[3]) for c in cuts]
        self.assertEqual(kinds, [("move", 4, 4), ("cut", 5, 5)])

    def test_cut_off_cut_points(self):
        m = mf.load(FIXTURE)
        name = m.moves[0]
        good, bad = name.cut_points[0], (name.cut_points[0] + 1) % name.beats
        while bad in name.cut_points:
            bad = (bad + 1) % name.beats
        for off, n_bad in [(good, 0), (bad, 1)]:
            with self.subTest(off=off):
                cuts = [(1.0, "cut", 5.0, off, 0, 1)]
                self.assertEqual(len(lt.cuts_off_cut_points(cuts, m)), n_bad)


class TierTests(unittest.TestCase):
    def test_tier_follows_the_section_on_bar_lines(self):
        e = sorted(ev("Beats", [(1.0, 4), (1.5, 5), (3.0, 8)]) + ev("Section", [(0.0, 0), (2.0, 3)]) + ev("Tier", [(0.0, 0), (1.0 + F, 0), (3.0, 2)]))
        checked, bad = lt.tier_vs_state(e)
        self.assertEqual((checked, bad), (2, []))

    def test_a_tier_that_ignores_the_section_is_reported(self):
        e = sorted(ev("Beats", [(1.0, 4), (3.0, 8)]) + ev("Section", [(0.0, 3)]) + ev("Tier", [(0.0, 0)]))
        checked, bad = lt.tier_vs_state(e)
        self.assertEqual(checked, 2)
        self.assertEqual(len(bad), 2)

    def test_tier_changes_off_a_bar_line(self):
        for beat, off in [(8, []), (9, [(3.0, 9)])]:
            with self.subTest(beat=beat):
                e = sorted(ev("Beats", [(1.0, 4), (3.0 - 0.01, beat)]) + ev("Tier", [(0.0, 0), (3.0, 2)]))
                self.assertEqual(lt.tier_off_bar(e), off)

    def test_per_tier_counts_changes_per_bar(self):
        bar = 4 * lt.SPB
        e = sorted(ev("Tier", [(0.0, 0), (2 * bar, 2)]) + ev("Beats", [(4 * bar, 0)]))
        cuts = [(0.5, "move", 4, 4, 1, 0), (bar * 2.5, "move", 4, 4, 2, 0), (bar * 3, "cut", 5, 5, 2, 1)]
        out = lt.per_tier(e, cuts)
        self.assertEqual((out[0]["moves"], out[0]["cuts"], out[0]["bars"]), (1, 0, 2.0))
        self.assertEqual((out[2]["moves"], out[2]["cuts"], out[2]["moves_per_bar"]), (1, 1, 0.5))


class ClockTests(unittest.TestCase):
    def test_bar_offset_against_the_true_bar_lines(self):
        bar = 4 * lt.SPB
        e = ev("Beats", [((k + 10) * bar + 0.05, 4 * (k + 10)) for k in range(5)])
        out = lt.bar_offset_ms(e, 0.0)
        self.assertEqual(out["n"], 5)
        self.assertLess(abs(out["median_ms"] - 50), 5)

    def test_idle_seams(self):
        e = sorted(ev("IsIdle", [(0, 1)]) + ev("OutFrame", [(0.1 * i, i) for i in range(10)] + [(1.0, 0), (1.1, 1)]))
        self.assertEqual([(round(t, 2), a, b) for t, a, b in lt.idle_seams(e, 8)], [(1.0, 9.0, 0.0)])

    def test_a_move_that_is_not_idle_has_no_seam(self):
        e = sorted(ev("IsIdle", [(0, 0)]) + ev("OutFrame", [(0.1 * i, i) for i in range(10)] + [(1.0, 0)]))
        self.assertEqual(lt.idle_seams(e, 8), [])

    def test_fps_numbers(self):
        self.assertEqual(lt.fps_numbers(ev("Fps", [(i, v) for i, v in enumerate([30, 31, 29, 30, 0.5])]))["min"], 29)


class DeviceTests(unittest.TestCase):
    LISTING = """[AudioToolbox @ 0x1] CoreAudio devices:
[AudioToolbox @ 0x1] [0]                    LG TV SSCR2, 1E6D
[AudioToolbox @ 0x1] [1]                  BlackHole 2ch, BlackHole2ch_UID
[AudioToolbox @ 0x1] [2]            External Headphones, BuiltIn"""

    def test_device_index(self):
        for name, want in [("BlackHole 2ch", 1), ("LG TV SSCR2", 0), ("Nope", None)]:
            with self.subTest(name=name):
                self.assertEqual(lt.device_index(self.LISTING, name), want)


class HeldProjectTests(unittest.TestCase):
    def test_editor_title(self):
        for wins, want in [(["show.magic - Editor", "Main"], "show.magic"), (["Main"], None), (None, None), ([], None)]:
            with self.subTest(wins=wins):
                self.assertEqual(lt.editor_title(wins), want)

    def test_find_project_needs_exactly_one_file(self):
        self.assertTrue(lt.find_project("show.magic").endswith(os.path.join("magic", "projects", "show.magic")))
        self.assertIsNone(lt.find_project("no_such_project.magic"))


class PictureTests(unittest.TestCase):
    def test_black_stale_and_spikes(self):
        v = [(10, 0.2, 0.0)] + [(10, 0.2, 1.0)] * 20 + [(0, 0.0, 9.0), (10, 0.2, 0.0), (10, 0.2, 1.0)]
        p = lt.picture_numbers(v)
        self.assertEqual((p["black"], p["stale"], p["spikes_over_5x_median"]), (1, 1, 1))
        self.assertEqual(lt.picture_numbers(v, [21 * F])["spikes_unexplained"], [])
        self.assertEqual(len(lt.picture_numbers(v, [5.0])["spikes_unexplained"]), 1)

    def test_seam_peak_against_the_video(self):
        v = [(10, 0.2, 1.0)] * 60
        v[31] = (10, 0.2, 8.0)
        out = lt.seam_numbers(v, [(1.0, 9, 0)])
        self.assertEqual((out["seams"], out["peak_max"], out["video_median"]), (1, 8.0, 1.0))


if __name__ == "__main__":
    unittest.main()
