"""Mocap Clips: the time map puts Anchors and Hits on beats, the ends blend into Key Poses or loop, travel comes out,
planted feet hold still on the floor. No Blender.
Run: python3 -m unittest discover robot/build/tests"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import mocap  # noqa: E402
import moves  # noqa: E402
import weight  # noqa: E402

FPB = moves.frames_per_beat()


class TimeMapTests(unittest.TestCase):
    def test_anchors_land_on_their_beat(self):
        for clip in mocap.CLIPS.values():
            for beat, src in clip.anchors:
                with self.subTest(clip=clip.name, beat=beat):
                    self.assertAlmostEqual(mocap.src_frame(clip, beat * FPB), src)

    def test_time_runs_forward(self):
        for clip in mocap.CLIPS.values():
            seq = [mocap.src_frame(clip, f) for f in range(mocap.frames(clip))]
            with self.subTest(clip=clip.name):
                self.assertTrue(all(b > a for a, b in zip(seq, seq[1:])))

    def test_hits_on_the_beat_of_their_anchor(self):
        cases = [("mocap_flip_uppercut", 0, 5.0, 73), ("mocap_flip_uppercut", 1, 6.0, 87)]
        for name, i, beat, frame in cases:
            clip = mocap.CLIPS[name]
            with self.subTest(clip=name, hit=i):
                self.assertAlmostEqual(mocap.hits(clip)[i].beat, beat)
                self.assertEqual(moves.beat_frame(mocap.hits(clip)[i].beat), frame)

    def test_hits_hold_then_catch_up(self):
        for clip in mocap.CLIPS.values():
            src = mocap.warp(clip)
            for h, limb, strength in mocap.stops(clip):
                with self.subTest(clip=clip.name, frame=h):
                    hold = src[h:h + weight.hold_frames(strength, limb) + 1]
                    self.assertEqual(hold, [mocap.src_frame(clip, h)] * len(hold))
            with self.subTest(clip=clip.name, end="last"):
                self.assertAlmostEqual(src[-1], mocap.src_frame(clip, mocap.frames(clip) - 1))

    def test_clips_last_whole_bars(self):
        for clip in mocap.CLIPS.values():
            with self.subTest(clip=clip.name):
                self.assertIn(clip.beats, (4, 8, 16))
                self.assertEqual(clip.anchors[0][0], 0)
                self.assertEqual(clip.anchors[-1][0], clip.beats)


class EndTests(unittest.TestCase):
    def test_key_weights(self):
        clip = mocap.CLIPS["mocap_flip_uppercut"]
        last = mocap.frames(clip) - 1
        cases = [(0, (1.0, 0.0)), (round(FPB), (0.0, 0.0)), (last // 2, (0.0, 0.0)), (last, (0.0, 1.0))]
        for frame, expected in cases:
            with self.subTest(frame=frame):
                for got, want in zip(mocap.key_weight(clip, frame), expected):
                    self.assertAlmostEqual(got, want)

    def test_loop_weights(self):
        clip = mocap.CLIPS["mocap_idle"]
        last = mocap.frames(clip) - 1
        cases = [(0, 0.0), (last - mocap.LOOP_FRAMES, 0.0), (last, 1.0)]
        for frame, want in cases:
            with self.subTest(frame=frame):
                self.assertAlmostEqual(mocap.loop_weight(clip, frame), want)


def _walk(n, speed):
    return [(0.0, -speed * f) for f in range(n)]


class TravelTests(unittest.TestCase):
    def test_travel_comes_out(self):
        cases = [("straight", _walk(30, 0.02)), ("still", [(0.1, 0.2)] * 10),
                 ("there and back", [(0.0, -0.05 * min(f, 20 - f)) for f in range(21)])]
        for name, path in cases:
            off = mocap.travel_offsets(path)
            with self.subTest(path=name):
                self.assertEqual(len(off), len(path))
                self.assertEqual(off[0], (0.0, 0.0))
                end = (path[-1][0] + off[-1][0], path[-1][1] + off[-1][1])
                self.assertAlmostEqual(math.dist(end, path[0]), 0.0)


class FootLockTests(unittest.TestCase):
    def test_plants(self):
        z = moves.ANKLE_Z
        cases = [("standing", [(0.1, 0.0, z + 0.01)] * 8, [True] * 8),
                 ("lifted", [(0.1, 0.0, z + 0.2)] * 8, [False] * 8),
                 ("sliding", [(0.1, -0.05 * f, z) for f in range(8)], [False] * 8),
                 ("too short", [(0.1, 0.0, z + 0.3)] * 3 + [(0.1, 0.0, z)] * 2 + [(0.1, 0.0, z + 0.3)] * 3,
                  [False] * 8)]
        for name, ankles, want in cases:
            with self.subTest(case=name):
                self.assertEqual(mocap.plants(ankles), want)

    def test_locked_run_holds_on_the_floor(self):
        z = moves.ANKLE_Z
        jitter = [(0.1 + 0.003 * (f % 2), 0.002 * f, z + 0.02) for f in range(10)]
        step = [(0.1, 0.02 + 0.08 * f, z + 0.15) for f in range(1, 6)]
        ankles, weights = mocap.lock_feet(jitter + step)
        for f in range(10):
            with self.subTest(frame=f):
                self.assertEqual(weights[f], 1.0)
                self.assertEqual(ankles[f], ankles[0])
                self.assertAlmostEqual(ankles[f][2], z)
        self.assertEqual(weights[-1], 0.0)
        self.assertEqual(ankles[-1], step[-1])


if __name__ == "__main__":
    unittest.main()
