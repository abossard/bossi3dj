"""Moves as key tables: Key Pose at both ends, no jump between frames, Hits for Clip Data. No Blender.
Run: python3 -m unittest discover robot/build/tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import moves  # noqa: E402

STEP_LIMIT_DEG = 20.0   # per frame at 30 fps
STEP_LIMIT_M = 0.25     # per frame at 30 fps, about 7.5 m/s: a fast kick

HITS = {
    "idle": [],
    "jab_cross": [{"f": 15, "limb": "hand_l", "strength": 0.6}, {"f": 29, "limb": "hand_r", "strength": 1.0}],
    "front_kick": [{"f": 29, "limb": "foot_l", "strength": 1.0}],
    "take_hit": [{"f": 15, "limb": "head", "strength": 1.0}],
}


class MoveTests(unittest.TestCase):
    def test_clip_is_58_frames(self):
        self.assertEqual(moves.clip_frames(), 58)

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

    def test_hits_listed_for_clip_data(self):
        for name, expected in HITS.items():
            with self.subTest(move=name):
                self.assertEqual(moves.hit_frames(moves.MOVES[name]), expected)

    def test_unknown_channel_raises(self):
        with self.assertRaises(KeyError):
            moves.pose(moves.GUARD, elbow_l=(0, 0, 0))


if __name__ == "__main__":
    unittest.main()
