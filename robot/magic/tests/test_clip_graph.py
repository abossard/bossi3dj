"""clip_graph.py: the Clip Graph model. Run: python3 -m unittest discover robot/magic/tests"""
import copy
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import clip_graph as cg  # noqa: E402
import manifest as mf  # noqa: E402

with open(os.path.join(HERE, "..", "..", "package", "fixture", "manifest.json")) as _f:
    FIXTURE = json.load(_f)


def manifest(mutate=None):
    d = copy.deepcopy(FIXTURE)
    if mutate:
        mutate(d)
    assert mf.validate(d) == [], mf.validate(d)
    return mf.Manifest(d)


def with_poses(d):
    """Idle and take_hit end in `crouch`; only take_hit starts there. Everything else guard to guard."""
    d["key_poses"] = ["guard", "crouch"]
    for c in d["clips"]:
        if c["move"] == "take_hit":
            c["key_in"], c["key_out"] = "crouch", "guard"
        if c["move"] == "idle":
            c["key_out"] = "crouch"


def no_calm(d):
    for c in d["clips"]:
        if c["tier"] == "calm":
            c["tier"] = "build"


def long_moves(d):
    for c in d["clips"]:
        if c["move"] == "front_kick":
            c.update(beats=8, frames=116)


class TierTests(unittest.TestCase):
    def test_tier_of_energy(self):
        g = cg.ClipGraph(manifest())
        for energy, tier in [(0, "calm"), (0.24, "calm"), (0.25, "build"), (0.54, "build"), (0.55, "drop"), (1, "drop")]:
            with self.subTest(energy=energy):
                self.assertEqual(g.tier(energy), tier)


class CandidateTests(unittest.TestCase):
    def test_candidates(self):
        cases = [("all guard, calm: only idle, so idle again", None, "idle", "calm", ["idle"]),
                 ("all guard, build: either build Move, the other if current", None, "idle", "build", ["jab_cross", "take_hit"]),
                 ("all guard, build, from jab_cross: not jab_cross", None, "jab_cross", "build", ["take_hit"]),
                 ("all guard, drop from front_kick: alone, so itself", None, "front_kick", "drop", ["front_kick"]),
                 ("tier without a fitting Move: any tier, not the current", no_calm, "jab_cross", "calm", ["idle", "front_kick", "take_hit"]),
                 ("key out crouch: only what starts in crouch", with_poses, "idle", "calm", ["take_hit"]),
                 ("key out crouch, any tier", with_poses, "idle", "drop", ["take_hit"])]
        for name, mutate, move, tier, expect in cases:
            with self.subTest(name):
                self.assertEqual(cg.ClipGraph(manifest(mutate)).candidates(move, tier), expect)

    def test_every_pick_follows_the_key_pose(self):
        m = manifest(with_poses)
        g = cg.ClipGraph(m, seed=3)
        for move in m.moves:
            for tier in ("calm", "build", "drop"):
                for bar in range(40):
                    with self.subTest(move=move.name, tier=tier, bar=bar):
                        self.assertEqual(m.move(g.next_move(move.name, bar, tier)).key_in, move.key_out)


class WalkTests(unittest.TestCase):
    ENERGIES = {"calm": 0.1, "build": 0.4, "drop": 0.9}

    def test_deterministic_with_a_seed(self):
        energies = [0.1, 0.4, 0.9, 0.3] * 20
        for seed in (0, 1, 42.5):
            with self.subTest(seed=seed):
                m = manifest()
                self.assertEqual(cg.ClipGraph(m, seed=seed).walk(energies), cg.ClipGraph(m, seed=seed).walk(energies))

    def test_seeds_differ(self):
        m = manifest()
        runs = {tuple(cg.ClipGraph(m, seed=s, cut_rate=0.5).walk([0.4] * 80)) for s in range(6)}
        self.assertGreater(len(runs), 3)

    def test_moves_change_only_on_a_bar_and_after_their_beats(self):
        for name, mutate in [("4 beat Clips", None), ("an 8 beat Clip", long_moves)]:
            with self.subTest(name):
                m = manifest(mutate)
                g = cg.ClipGraph(m, seed=5)
                prev = g.start()
                for beat, s in enumerate(g.walk([0.1, 0.4, 0.9] * 30), 1):
                    if s.move != prev.move or s.start != prev.start:
                        self.assertEqual(beat % 4, 0)
                        self.assertEqual(beat - prev.start, m.move(prev.move).beats)
                        self.assertEqual(s.start, beat)
                    prev = s

    def test_tier_picks_a_move_of_that_tier(self):
        m = manifest()
        for tier, energy in self.ENERGIES.items():
            with self.subTest(tier=tier):
                g = cg.ClipGraph(m, seed=2)
                moves = {s.move for s in g.walk([energy] * 64)[4:]}
                self.assertTrue(all(m.move(x).tier == tier for x in moves), moves)

    def test_angle_changes_only_at_cut_points(self):
        m = manifest()
        g = cg.ClipGraph(m, seed=9)
        prev = g.start()
        changes = 0
        for beat, s in enumerate(g.walk([0.4] * 64), 1):
            if s.angle != prev.angle:
                changes += 1
                self.assertIn(beat - s.start, m.move(s.move).cut_points)
            prev = s
        self.assertGreater(changes, 4)

    def test_cut_rate(self):
        m = manifest()
        for rate, expect in [(0.0, lambda n: n == 0), (1.0, lambda n: n >= 30), (0.5, lambda n: 8 <= n <= 28)]:
            with self.subTest(cut_rate=rate):
                walk = cg.ClipGraph(m, seed=4, cut_rate=rate).walk([0.4] * 64)
                changes = sum(1 for a, b in zip(walk, walk[1:]) if a.angle != b.angle)
                self.assertTrue(expect(changes), changes)

    def test_a_single_angle_never_cuts(self):
        def one_angle(d):
            d["angles"] = d["angles"][:1]
            d["clips"] = [c for c in d["clips"] if c["angle"] == "front"]
        walk = cg.ClipGraph(manifest(one_angle)).walk([0.4] * 32)
        self.assertEqual({s.angle for s in walk}, {"front"})

    def test_first_state(self):
        s = cg.ClipGraph(manifest()).start()
        self.assertEqual(s, cg.State("idle", "front", 0))


class OutputTests(unittest.TestCase):
    def test_clip_index_and_frame(self):
        m = manifest()
        g = cg.ClipGraph(m)
        s = cg.State("front_kick", "side", 8)
        self.assertEqual(g.clip_index(s), 5)
        for beat, phase, frame in [(8, 0, 0), (9, 0, 14), (10, 0.5, 36), (11, 0.99, 57), (12, 0, 57), (30, 0, 57)]:
            with self.subTest(beat=beat, phase=phase):
                self.assertEqual(g.frame(s, beat, phase), frame)

    def test_hash_is_the_documented_formula(self):
        for n, seed, salt in [(1, 0, 0), (4, 0, 1), (7, 2.5, 2), (100, 9, 0)]:
            with self.subTest(n=n, seed=seed, salt=salt):
                import math
                v = math.sin(n * 12.9898 + seed * 78.233 + salt * 37.719) * 43758.5453
                self.assertEqual(cg.hash01(n, seed, salt), v - math.floor(v))
                self.assertTrue(0 <= cg.hash01(n, seed, salt) < 1)


if __name__ == "__main__":
    unittest.main()
