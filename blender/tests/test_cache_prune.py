"""Which bakes tools/cache_prune.py drops (issue #17), without touching the cache.
Run: python3 -m unittest discover blender/tests"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
import cache_prune as cp  # noqa: E402

CURRENT = {"synthwave_planet": 1794776634, "synthwave_pyramids": 1794337584}


class StaleTests(unittest.TestCase):
    def test_stale(self):
        cases = [
            ("synthwave_planet-1794776634-512.npz", False),                 # the live clearance map
            ("gt2-synthwave_planet-1794776634-8192.npz", False),            # the live GPU map
            ("gt2-synthwave_planet-1794776634-region3700x6000.npz", False),  # the live regional map
            ("synthwave_planet-1794773552-512.npz", True),                  # an older .blend
            ("gt2-synthwave_planet-1794773552-8192.npz", True),
            ("gt-synthwave_planet-1794776634-8192.npz", True),              # an older CACHE_V
            ("_resave_probe-1794404057-512.npz", True),                     # no such .blend
            ("notes.txt", False),                                           # not a bake: left alone
            ("synthwave_pyramids-1794337584-512.npz", False),
        ]
        for name, dropped in cases:
            with self.subTest(name=name):
                self.assertEqual(name in cp.stale([name], CURRENT, "gt2"), dropped)

    def test_cache_v_is_read(self):
        self.assertRegex(cp.cache_v(), r"^gt\d*$")


if __name__ == "__main__":
    unittest.main()
