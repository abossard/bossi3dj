"""The night-edge guard's decision logic, without Blender. Run: python3 -m unittest discover blender/tests"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scenes"))
import edge_guard as eg  # noqa: E402  (bpy is None outside Blender)


class NextStepTests(unittest.TestCase):
    def test_next_step(self):
        cases = [
            (0.12, None, "present"), (eg.MIN_SHARE, None, "present"), (0.133, 0.0, "present"),
            (0.011, None, "repair"), (0.0, None, "repair"),
            (0.011, 0.12, "repaired"), (0.008, eg.MIN_SHARE, "repaired"),
            (0.011, 0.012, "missing"), (0.0, 0.0, "missing"),
        ]
        for first, after, want in cases:
            with self.subTest(first=first, after=after):
                self.assertEqual(eg.next_step(first, after), want)


class LineShareTests(unittest.TestCase):
    def test_line_share(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy not installed (make venv)")
        off = np.full((10, 20, 4), 40, np.uint8)
        cases = [(0, 0.0), (eg.LINE_DELTA, 0.0), (eg.LINE_DELTA + 1, 0.1), (-30, 0.0)]    # grid frame brighter by `delta` on one row
        for delta, want in cases:
            with self.subTest(delta=delta):
                on = off.copy()
                on[3, :, 1] = off[3, :, 1].astype(int) + delta
                self.assertAlmostEqual(eg.line_share(on, off), want)


if __name__ == "__main__":
    unittest.main()
