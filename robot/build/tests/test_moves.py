"""Moves as key tables: Key Poses at both ends, no jump between frames, planted feet, Hits for Clip Data, a
Clip Library that reaches every Key Pose in every Intensity Tier. No Blender.
Run: python3 -m unittest discover robot/build/tests"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import moves  # noqa: E402

STEP_LIMIT_DEG = 20.0   # per frame at 30 fps
STEP_LIMIT_M = 0.25     # per frame at 30 fps, about 7.5 m/s: a fast kick
REACH_SLACK_M = 0.005
LIMBS = {"head", "hand_l", "hand_r", "foot_l", "foot_r"}
TIERS = ("calm", "build", "drop")

HITS = {
    "idle_guard": [],
    "jab_cross": [{"f": 15, "limb": "hand_l", "strength": 0.6}, {"f": 29, "limb": "hand_r", "strength": 1.0}],
    "front_kick": [{"f": 29, "limb": "foot_l", "strength": 1.0}],
    "take_hit": [{"f": 15, "limb": "head", "strength": 1.0}],
}
FRAMES_PER_BEATS = {4: 58, 8: 116, 16: 232}


def _moves(idle):
    return [m for m in moves.MOVES.values() if m.idle == idle]


def _planted(p, foot):
    return p[foot][2] <= moves.ANKLE_Z + 1e-9


class MoveTests(unittest.TestCase):
    def test_frame_count_per_bars(self):
        for beats, n in FRAMES_PER_BEATS.items():
            with self.subTest(beats=beats):
                self.assertEqual(moves.clip_frames(beats), n)
        for name, move in moves.MOVES.items():
            with self.subTest(move=name):
                self.assertIn(move.beats, FRAMES_PER_BEATS)
                self.assertEqual(len(moves.frames(move)), FRAMES_PER_BEATS[move.beats])

    def test_first_and_last_frame_are_the_key_pose(self):
        for name, move in moves.MOVES.items():
            seq = moves.frames(move)
            for end, key, f in (("first", move.key_in, 0), ("last", move.key_out, len(seq) - 1)):
                with self.subTest(move=name, end=end):
                    self.assertEqual(moves.pose_distance(seq[f], moves.KEY_POSES[key]), (0.0, 0.0))

    def test_no_jump_between_frames(self):
        for name, move in moves.MOVES.items():
            seq = moves.frames(move)
            for f in range(1, len(seq)):
                with self.subTest(move=name, frame=f):
                    rot, pos = moves.pose_distance(seq[f - 1], seq[f])
                    self.assertLessEqual(rot, STEP_LIMIT_DEG)
                    self.assertLessEqual(pos, STEP_LIMIT_M)

    def test_key_poses_stand_on_both_feet(self):
        for key, p in moves.KEY_POSES.items():
            for foot in ("foot_l", "foot_r"):
                with self.subTest(key_pose=key, foot=foot):
                    self.assertAlmostEqual(p[foot][2], moves.ANKLE_Z)

    def test_ankles_planted(self):
        """A foot on the ground in two frames in a row holds still, never sinks, and its leg reaches it."""
        for name, move in moves.MOVES.items():
            seq = moves.frames(move)
            for foot, side in (("foot_l", "l"), ("foot_r", "r")):
                for f, p in enumerate(seq):
                    with self.subTest(move=name, foot=foot, frame=f):
                        self.assertGreaterEqual(p[foot][2], moves.ANKLE_Z - 1e-9)
                        if _planted(p, foot):
                            self.assertLessEqual(math.dist(moves.hip_joint(p, side), p[foot]),
                                                 moves.LEG_M + REACH_SLACK_M)
                        if f and _planted(p, foot) and _planted(seq[f - 1], foot):
                            q = seq[f - 1]
                            self.assertLessEqual(max(abs(a - b) for a, b in zip(p[foot], q[foot])), 1e-6)
                            self.assertLessEqual(max(abs(a - b) for a, b in zip(p[foot + "_rot"], q[foot + "_rot"])),
                                                 1e-6)

    def test_hits_listed_for_clip_data(self):
        for name, expected in HITS.items():
            with self.subTest(move=name):
                self.assertEqual(moves.hit_frames(moves.MOVES[name]), expected)
        for name, move in moves.MOVES.items():
            for h in moves.hit_frames(move):
                with self.subTest(move=name, hit=h["f"]):
                    self.assertIn(h["limb"], LIMBS)
                    self.assertLess(h["f"], moves.move_frames(move))
                    self.assertTrue(0.0 < h["strength"] <= 1.0)

    def test_one_idle_clip_per_key_pose(self):
        for key in moves.KEY_POSES:
            with self.subTest(key_pose=key):
                idles = [m for m in _moves(True) if m.key_in == key]
                self.assertEqual(len(idles), 1)
                self.assertEqual(idles[0].key_out, key)

    def test_idle_loops_without_a_jump(self):
        for move in _moves(True):
            seq = moves.frames(move)
            steps = [moves.pose_distance(seq[f - 1], seq[f]) for f in range(1, len(seq))]
            biggest = (max(s[0] for s in steps), max(s[1] for s in steps))
            seam = {"last_to_first": moves.pose_distance(seq[-1], seq[0]),
                    "into_last": steps[-1], "out_of_first": steps[0]}
            for where, (rot, pos) in seam.items():
                with self.subTest(move=move.name, where=where):
                    self.assertLessEqual(rot, biggest[0])
                    self.assertLessEqual(pos, biggest[1])
            with self.subTest(move=move.name, where="alive"):
                self.assertGreater(biggest[0], 0.0)
                self.assertGreater(biggest[1], 0.0)

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
        self.assertEqual({m.beats for m in _moves(False)}, set(FRAMES_PER_BEATS))

    def test_unknown_channel_raises(self):
        with self.assertRaises(KeyError):
            moves.pose(moves.GUARD, elbow_l=(0, 0, 0))


if __name__ == "__main__":
    unittest.main()
