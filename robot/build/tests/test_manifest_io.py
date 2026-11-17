"""The Manifest export keeps top-level keys the build does not own. No Blender.
Run: python3 -m unittest discover robot/build/tests"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import manifest_io  # noqa: E402

OURS = {"version": 1, "bpm": 124, "clips": [{"id": "a__front"}]}


class MergeTests(unittest.TestCase):
    def test_merge(self):
        cases = [("no Manifest yet", None, OURS),
                 ("keeps backdrops", {"version": 1, "clips": [], "backdrops": {"front": "x.png"}},
                  dict(OURS, backdrops={"front": "x.png"})),
                 ("our keys win", {"version": 0, "bpm": 90, "clips": [{"id": "old"}]}, OURS)]
        for name, old, want in cases:
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "manifest.json")
                if old is not None:
                    with open(path, "w") as fh:
                        json.dump(old, fh)
                self.assertEqual(manifest_io.merged(path, OURS), want)


if __name__ == "__main__":
    unittest.main()
