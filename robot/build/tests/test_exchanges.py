"""Exchanges: both fighters at their Key Poses at both ends, one length, no jump, planted ankles, and contact: a Hit
lands on its target, a dodge misses. No Blender.
Run: python3 -m unittest discover robot/build/tests"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import exchanges as X  # noqa: E402
import moves  # noqa: E402

CONTACT_TOL_M = 0.15
DODGE_GAP_M = 0.40
FLOOR_TOL_M = 0.02
# per frame at 30 fps: the Android as in test_moves.py; the giant about 3x larger, heavier, slower to turn
STEP = {"android": (20.0, 0.33), "giant": (12.0, 0.60)}
FEET = {"android": (("foot_l", "l"), ("foot_r", "r")), "giant": (("g_foot_l", "l"), ("g_foot_r", "r"))}
ANKLE = {"android": moves.ANKLE_Z, "giant": X.G_ANKLE_Z}


def _sides(ex):
    return (("android", ex.android, moves.KEY_POSES), ("giant", ex.giant, {"loom": X.LOOM}))


def _reach(who, p, side):
    if who == "android":
        return math.dist(moves.hip_joint(p, side), p["foot_" + side]), moves.LEG_M
    return math.dist(X.g_hip_joint(p, side), p["g_foot_" + side]), X.G_THIGH + X.G_SHIN


class ExchangeTests(unittest.TestCase):
    def test_one_length_and_tier(self):
        for name, ex in X.EXCHANGES.items():
            with self.subTest(exchange=name):
                self.assertEqual({ex.android.beats, ex.giant.beats}, {ex.beats})
                self.assertIn(ex.beats, (4, 8, 16))
                self.assertEqual(len(X.frames(ex)), moves.clip_frames(ex.beats))
                self.assertEqual(ex.android.tier, ex.tier)

    def test_both_at_their_key_poses_at_both_ends(self):
        for name, ex in X.EXCHANGES.items():
            for who, move, keys in _sides(ex):
                seq = moves.frames(move)
                for end, key, f in (("first", move.key_in, 0), ("last", move.key_out, len(seq) - 1)):
                    with self.subTest(exchange=name, fighter=who, end=end):
                        self.assertEqual(moves.pose_distance(seq[f], keys[key]), (0.0, 0.0))

    def test_no_jump_between_frames(self):
        for name, ex in X.EXCHANGES.items():
            for who, move, _ in _sides(ex):
                seq = moves.frames(move)
                for f in range(1, len(seq)):
                    with self.subTest(exchange=name, fighter=who, frame=f):
                        rot, pos = moves.pose_distance(seq[f - 1], seq[f])
                        self.assertLessEqual(rot, STEP[who][0])
                        self.assertLessEqual(pos, STEP[who][1])

    def test_ankles_planted(self):
        for name, ex in X.EXCHANGES.items():
            for who, move, _ in _sides(ex):
                seq = moves.frames(move)
                for foot, side in FEET[who]:
                    for f, p in enumerate(seq):
                        with self.subTest(exchange=name, fighter=who, foot=foot, frame=f):
                            self.assertGreaterEqual(p[foot][2], ANKLE[who] - 1e-9)
                            if p[foot][2] <= ANKLE[who] + 1e-9:
                                dist, leg = _reach(who, p, side)
                                self.assertLessEqual(dist, leg + 0.005)
                                if f and seq[f - 1][foot][2] <= ANKLE[who] + 1e-9:
                                    self.assertLessEqual(math.dist(p[foot], seq[f - 1][foot]), 1e-6)

    def test_hits_land_on_their_target(self):
        for name, ex in X.EXCHANGES.items():
            fr = X.frames(ex)
            for s in ex.hits:
                f = moves.beat_frame(s.beat)
                with self.subTest(exchange=name, hit=s.point, beat=s.beat):
                    if s.target == "floor":
                        low = min(X.points(*fr[g])[s.point][2] for g in range(max(f - 1, 0), min(f + 2, len(fr))))
                        floor = {"g_hammer": X.RADIUS["g_hammer"], "g_foot_l": X.G_ANKLE_Z,
                                 "g_foot_r": X.G_ANKLE_Z}.get(s.point, moves.ANKLE_Z)
                        self.assertLessEqual(low, floor + FLOOR_TOL_M + 0.05 * (s.point == "g_hammer"))
                    else:
                        p = X.points(*fr[f])
                        gap = math.dist(p[s.point], p[s.target]) - X.RADIUS[s.point] - X.RADIUS[s.target]
                        self.assertLessEqual(abs(gap), CONTACT_TOL_M)

    def test_dodges_miss_the_android(self):
        for name, ex in X.EXCHANGES.items():
            fr = X.frames(ex)
            for d in ex.dodges:
                p = X.points(*fr[moves.beat_frame(d.beat)])
                for b in X.ANDROID_BODY:
                    with self.subTest(exchange=name, dodge=d.point, body=b):
                        gap = math.dist(p[d.point], p[b]) - X.RADIUS[d.point] - X.RADIUS[b]
                        self.assertGreater(gap, DODGE_GAP_M)

    def test_idle_exchange_loops(self):
        for name, ex in ((n, e) for n, e in X.EXCHANGES.items() if e.idle):
            for who, move, _ in _sides(ex):
                seq = moves.frames(move)
                with self.subTest(exchange=name, fighter=who):
                    self.assertEqual(moves.pose_distance(seq[0], seq[-1]), (0.0, 0.0))

    def test_every_tier_has_exchanges(self):
        for tier in ("calm", "build", "drop"):
            with self.subTest(tier=tier):
                self.assertTrue(any(e.tier == tier and not e.idle for e in X.EXCHANGES.values()))

    def test_unknown_giant_channel_raises(self):
        with self.assertRaises(KeyError):
            X.gpose(X.LOOM, g_tail=(0, 0, 0))


if __name__ == "__main__":
    unittest.main()
