"""manifest.py: the Manifest validator follows robot/CONTRACTS.md. Run: python3 -m unittest discover robot/magic/tests"""
import copy
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import manifest as mf  # noqa: E402

FIXTURE = os.path.join(HERE, "..", "..", "package", "fixture")


def fixture_data():
    with open(os.path.join(FIXTURE, "manifest.json")) as f:
        return json.load(f)


def package_with_media(tmp):
    """The committed package in `tmp`, with empty files where the git-ignored Clips would be."""
    root = os.path.join(tmp, "pkg")
    shutil.copytree(FIXTURE, root, ignore=shutil.ignore_patterns("beauty", "shadow", "depth", "*.mov", "*.magic"))
    for c in fixture_data()["clips"]:
        for rel in c["passes"].values():
            os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
            open(os.path.join(root, rel), "w").close()
    return root


def edit(path, value):
    """A mutation: set `value` at a path like ('clips', 0, 'frames'); `None` value deletes the key."""
    def apply(d):
        node = d
        for k in path[:-1]:
            node = node[k]
        if value is None:
            del node[path[-1]]
        else:
            node[path[-1]] = value
    return apply


def all_clips(key, value):
    def apply(d):
        for c in d["clips"]:
            c[key] = value
    return apply


class FixtureTests(unittest.TestCase):
    def test_the_fixture_is_valid(self):
        self.assertEqual(mf.validate(fixture_data()), [])

    def test_fixture_with_files_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = package_with_media(tmp)
            m = mf.load(os.path.join(root, "manifest.json"))
            self.assertEqual([x.name for x in m.moves], ["idle", "jab_cross", "front_kick", "take_hit"])
            self.assertEqual(m.angle_ids, ["front", "side"])
            self.assertEqual(m.clip_index("front_kick", "side"), 5)

    def test_frames_follow_beats_bpm_and_fps(self):
        for beats, bpm, fps, frames in [(4, 124, 30, 58), (8, 124, 30, 116), (16, 124, 30, 232), (4, 120, 30, 60), (4, 120, 60, 120)]:
            with self.subTest(beats=beats, bpm=bpm, fps=fps):
                self.assertEqual(mf.frames_for(beats, bpm, fps), frames)


class RejectTests(unittest.TestCase):
    CASES = [
        ("frames differ from beats", edit(("clips", 0, "frames"), 59), "frames 59"),
        ("bpm changed under the frames", edit(("bpm",), 120), "frames 58"),
        ("beats not 4, 8 or 16", edit(("clips", 0, "beats"), 5), "beats must be"),
        ("key pose not listed", edit(("clips", 0, "key_in"), "crouch"), "key_in 'crouch'"),
        ("unknown tier", edit(("clips", 0, "tier"), "mega"), "tier must be"),
        ("cut points without 0", edit(("clips", 0, "cut_points"), [1, 2]), "cut_points"),
        ("cut point past the end", edit(("clips", 0, "cut_points"), [0, 4]), "cut_points"),
        ("angle not listed", edit(("clips", 0, "angle"), "back"), "is not in angles"),
        ("id not move__angle", edit(("clips", 0, "id"), "idle_front"), "id must be"),
        ("pass missing", edit(("clips", 0, "passes", "shadow"), None), "passes needs"),
        ("version 2", edit(("version",), 2), "version must be 1"),
        ("size not a pair", edit(("size",), [1920]), "size must be"),
        ("field missing", edit(("clips", 0, "clip_data"), None), "missing clip_data"),
        ("tier differs across Angles", edit(("clips", 1, "tier"), "drop"), "tier differs across Angles"),
        ("beats differ across Angles", lambda d: d["clips"][1].update(beats=8, frames=116), "beats differs across Angles"),
        ("cut points differ across Angles", edit(("clips", 1, "cut_points"), [0]), "cut_points differs across Angles"),
        ("a Move lacks an Angle", lambda d: d["clips"].pop(1), "no Clip for Angle side"),
        ("duplicate id", lambda d: d["clips"].append(copy.deepcopy(d["clips"][0])), "duplicate id"),
        ("more angles than the wire", lambda d: d.update(angles=[{"id": "a%d" % i, "camera": "c"} for i in range(9)]), "/vj/angle holds 8"),
    ]

    def test_problem_found(self):
        for name, mutate, expect in self.CASES:
            with self.subTest(name):
                d = fixture_data()
                mutate(d)
                problems = mf.validate(d)
                self.assertTrue(any(expect in p for p in problems), problems)

    def test_load_raises_with_every_problem(self):
        d = fixture_data()
        d["bpm"], d["version"] = 100, 3
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "manifest.json")
            with open(path, "w") as f:
                json.dump(d, f)
            with self.assertRaises(mf.ManifestError) as cm:
                mf.load(path, check_files=False)
            self.assertGreater(len(cm.exception.problems), 8)


class FileTests(unittest.TestCase):
    def test_missing_and_wrong_files_are_found(self):
        cases = [("a pass is missing", lambda root, c: os.remove(os.path.join(root, c["passes"]["depth"])), "file missing"),
                 ("clip data is missing", lambda root, c: os.remove(os.path.join(root, c["clip_data"])), "file missing"),
                 ("camera track is missing", lambda root, c: os.remove(os.path.join(root, c["camera_track"])), "file missing"),
                 ("clip data has too few frames", lambda root, c: _shorten(os.path.join(root, c["clip_data"])), "clip data has 57 frames"),
                 ("a hit is past the end", lambda root, c: _late_hit(os.path.join(root, c["clip_data"])), "hit outside the Clip")]
        for name, damage, expect in cases:
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                root = package_with_media(tmp)
                damage(root, fixture_data()["clips"][2])
                problems = mf.validate(fixture_data(), root)
                self.assertTrue(any(expect in p for p in problems), problems)


def _rewrite(path, fn):
    with open(path) as f:
        d = json.load(f)
    fn(d)
    with open(path, "w") as f:
        json.dump(d, f)


def _shorten(path):
    _rewrite(path, lambda d: d["frames"].pop())


def _late_hit(path):
    _rewrite(path, lambda d: d["hits"].append({"f": 999, "point": [0, 0, 0], "strength": 1, "limb": "hand_r"}))


if __name__ == "__main__":
    unittest.main()
