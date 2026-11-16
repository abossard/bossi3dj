"""Which bakes tools/cache_prune.py drops (issue #17), without touching the cache.
Run: python3 -m unittest discover blender/tests"""
import ast
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCENES = os.path.join(HERE, "..", "scenes")
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
import cache_prune as cp  # noqa: E402

CURRENT = {"synthwave_planet": 1794776634, "synthwave_pyramids": 1794337584}


def key_format(path, func):
    """The format string of `key = "..." % (...)` in func of the writer at path (they import bpy)."""
    tree = ast.parse(open(path).read())
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == func)
    asg = next(n for n in ast.walk(fn) if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "key")
    return asg.value.left.value


CLEAR = key_format(os.path.join(SCENES, "flight_rt.py"), "load_map")             # stem, mtime, MAP_RES
GPU = key_format(os.path.join(SCENES, "planet_proto", "gpu_terrain.py"), "bake")  # CACHE_V, stem, mtime, grid


class StaleTests(unittest.TestCase):
    def test_stale(self):
        cases = [
            (CLEAR % ("synthwave_planet", 1794776634, 512), False),             # the live clearance map
            (GPU % ("gt2", "synthwave_planet", 1794776634, "8192"), False),     # the live GPU map
            (GPU % ("gt2", "synthwave_planet", 1794776634, "region3700x6000"), False),
            (CLEAR % ("synthwave_pyramids", 1794337584, 512), False),
            (CLEAR % ("synthwave_planet", 1794773552, 512), True),              # an older .blend
            (GPU % ("gt2", "synthwave_planet", 1794773552, "8192"), True),
            (GPU % ("gt", "synthwave_planet", 1794776634, "8192"), True),       # an older CACHE_V
            (CLEAR % ("_resave_probe", 1794404057, 512), True),                 # no such .blend
            ("fl2-synthwave_planet-1794776634-512.npz", False),                 # an unknown prefix: kept
            ("v3-synthwave_planet-1794773552-8192.npz", False),
            ("notes.txt", False),                                               # not a bake: left alone
        ]
        for name, dropped in cases:
            with self.subTest(name=name):
                self.assertEqual(name in cp.stale([name], CURRENT, "gt2"), dropped)

    def test_cache_v_is_read(self):
        self.assertRegex(cp.cache_v(), r"^gt\d*$")


class MainTests(unittest.TestCase):
    def test_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            scenes, cache = os.path.join(tmp, "scenes"), os.path.join(tmp, "cache")
            os.makedirs(os.path.join(scenes, "planet_proto"))
            os.makedirs(os.path.join(cache, CLEAR % ("old", 1, 512)))            # a directory matching the pattern
            open(os.path.join(scenes, "planet_proto", "gpu_terrain.py"), "w").write('CACHE_V = "gt2"\n')
            blend = os.path.join(scenes, "a.blend")
            open(blend, "w").close()
            os.utime(blend, (1000, 1000))
            names = {CLEAR % ("a", 1000, 512): False, GPU % ("gt2", "a", 1000, "8192"): False,
                     CLEAR % ("a", 999, 512): True, GPU % ("gt", "a", 1000, "8192"): True, "x.txt": False}
            for n in names:
                open(os.path.join(cache, n), "w").write("x")
            for dry in (True, False):
                with self.subTest(dry_run=dry), mock.patch.object(cp, "CACHE", cache), \
                        mock.patch.object(cp, "SCENES", scenes), redirect_stdout(io.StringIO()):
                    self.assertEqual(cp.main(["--dry-run"] if dry else []), 0)
                    for n, dropped in names.items():
                        self.assertEqual(os.path.exists(os.path.join(cache, n)), dry or not dropped, n)
            self.assertTrue(os.path.isdir(os.path.join(cache, CLEAR % ("old", 1, 512))))


if __name__ == "__main__":
    unittest.main()
