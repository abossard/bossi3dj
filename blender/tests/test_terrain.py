"""Which terrain the planet scene shows per shot and blend (director.streamed), without Blender.
Run: python3 -m unittest discover blender/tests"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scenes"))
import director as dr  # noqa: E402

FLIGHT = "CAM_11"
PROPS = {"fog_k": 1.0, "fog_clear": 180.0, "fog_dip": 0.005}


def pose(x):
    """A shot x m east of the planet's top, 50 m up, looking north."""
    return ((x, 0.0, 50.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), 35.0, PROPS)


POSES = {"CAM_0": pose(0.0), "CAM_1": pose(400.0), "CAM_2": pose(-600.0), FLIGHT: pose(900.0)}


class StreamedTests(unittest.TestCase):
    def test_streamed(self):
        cases = [
            ("CAM_0", frozenset(), False, False),
            ("CAM_0", frozenset({"CAM_1", "CAM_0"}), True, False),
            (FLIGHT, frozenset(), False, True),
            (FLIGHT, frozenset({"CAM_0", FLIGHT}), True, True),
            ("CAM_0", frozenset({FLIGHT, "CAM_0"}), True, True),
            ("CAM_0", frozenset({FLIGHT, "CAM_0"}), False, False),
            ("CAM_2", frozenset({"CAM_0", FLIGHT, "CAM_2"}), True, True),
        ]
        for shot, sides, blending, want in cases:
            with self.subTest(shot=shot, sides=sorted(sides), blending=blending):
                self.assertEqual(dr.streamed(FLIGHT, shot, sides, blending), want)


class DirectorTerrainTests(unittest.TestCase):
    """A Director stepped at 30 fps through a list of (seconds, shot, /vj/blend): the terrain of the first and the
    last frame of each step and whether any frame of it streamed."""

    def run_steps(self, steps):
        D = dr.Director()
        out = []
        for secs, shot, blend in steps:
            seen = []
            for _ in range(int(secs * 30)):
                D.step(1.0 / 30.0, shot, POSES[shot], blend)
                seen.append(dr.streamed(FLIGHT, shot, D.sides, D.blending()))
            out.append((seen[0], any(seen), seen[-1]))
        return out

    def test_sequences(self):
        cases = [
            ("cut between fixed shots", [(1, "CAM_0", 0.0), (1, "CAM_1", 0.0)],
             [(False, False, False), (False, False, False)]),
            ("blend between fixed shots", [(1, "CAM_0", 1.0), (60, "CAM_1", 1.0)],
             [(False, False, False), (False, False, False)]),
            ("cut into the Flight and out", [(1, "CAM_0", 0.0), (1, FLIGHT, 0.0), (1, "CAM_1", 0.0)],
             [(False, False, False), (True, True, True), (False, False, False)]),
            ("blend out of the Flight ends fixed", [(1, FLIGHT, 1.0), (60, "CAM_0", 1.0)],
             [(True, True, True), (True, True, False)]),
            ("change of mind mid-blend keeps the Flight a side", [(1, "CAM_0", 1.0), (0.5, FLIGHT, 1.0), (60, "CAM_2", 1.0)],
             [(False, False, False), (True, True, True), (True, True, False)]),
        ]
        for name, steps, want in cases:
            with self.subTest(name):
                self.assertEqual(self.run_steps(steps), want)


if __name__ == "__main__":
    unittest.main()
