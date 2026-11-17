"""The Clip Library (library.py): key-table and Mocap Moves together reach every Key Pose, cover every tier in mixed
lengths, and Mocap Moves meet the Clip Graph contract. No Blender.
Run: python3 -m unittest discover robot/build/tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import library  # noqa: E402
import moves  # noqa: E402

TIERS = ("calm", "build", "drop")
BEATS = {4, 8, 16}
GONE = ("jab_cross", "jab_jab_hook", "uppercut_combo")
LIMBS = {"head", "hand_l", "hand_r", "foot_l", "foot_r"}


def _moves(idle):
    return [m for m in library.LIBRARY.values() if m.idle == idle]


class LibraryTests(unittest.TestCase):
    def test_every_key_pose_reaches_every_other_within_two_moves(self):
        edges = {(m.key_in, m.key_out) for m in _moves(False)}
        for a in moves.KEY_POSES:
            one = {b for x, b in edges if x == a}
            two = one | {c for x, c in edges if x in one}
            for b in moves.KEY_POSES:
                if a != b:
                    with self.subTest(start=a, end=b):
                        self.assertIn(b, two)

    def test_every_key_pose_has_a_move_in_every_tier(self):
        for key in moves.KEY_POSES:
            for tier in TIERS:
                with self.subTest(key_pose=key, tier=tier):
                    self.assertTrue(any(m.key_in == key and m.tier == tier for m in _moves(False)))

    def test_four_moves_per_tier_in_mixed_lengths(self):
        for tier in TIERS:
            with self.subTest(tier=tier):
                self.assertGreaterEqual(len([m for m in _moves(False) if m.tier == tier]), 4)
        self.assertEqual({m.beats for m in _moves(False)}, BEATS)

    def test_hand_keyed_strikes_replaced(self):
        for name in GONE:
            with self.subTest(move=name):
                self.assertNotIn(name, library.LIBRARY)
        self.assertTrue(any(library.is_mocap(m) for m in library.LIBRARY.values()))

    def test_mocap_moves_keep_the_contract(self):
        for name, m in library.LIBRARY.items():
            if not library.is_mocap(m):
                continue
            n = moves.move_frames(m)
            with self.subTest(move=name):
                self.assertIn(m.beats, BEATS)
                self.assertIn(m.key_in, moves.KEY_POSES)
                self.assertIn(m.key_out, moves.KEY_POSES)
                self.assertEqual(library.cut_points(m), [0])
                if m.variant_of:
                    base = library.LIBRARY[m.variant_of]
                    self.assertEqual((m.key_in, m.key_out, m.tier, m.idle), (base.key_in, base.key_out, base.tier,
                                                                                base.idle))
                for h in moves.hit_frames(m):
                    self.assertIn(h["limb"], LIMBS)
                    self.assertLess(h["f"], n)
                    self.assertTrue(0.0 < h["strength"] <= 1.0)


if __name__ == "__main__":
    unittest.main()
