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


PACKAGES = os.path.join(HERE, "..", "..", "package")


def package_with_media(tmp, src=FIXTURE):
    """The committed package `src` in `tmp`, with empty files where the git-ignored Clips would be."""
    root = os.path.join(tmp, "pkg")
    shutil.copytree(src, root, ignore=shutil.ignore_patterns("beauty", "shadow", "depth", "*.mov", "*.magic"))
    with open(os.path.join(src, "manifest.json")) as f:
        clips = json.load(f)["clips"]
    for c in clips:
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
        ("idle missing", edit(("clips", 0, "idle"), None), "missing idle"),
        ("idle not a bool", edit(("clips", 0, "idle"), "yes"), "idle must be true or false"),
        ("Idle Clip changes the pose", lambda d: d["clips"][0].update(key_out="crouch") or d["key_poses"].append("crouch"),
         "needs key_in equal to key_out"),
        ("no Idle Clip for a Key Pose", lambda d: [c.update(idle=False) for c in d["clips"][:2]], "0 Idle Clips"),
        ("two Idle Clips for a Key Pose", lambda d: [c.update(idle=True) for c in d["clips"][2:4]], "2 Idle Clips"),
        ("a Key Pose without any Clip", lambda d: d["key_poses"].append("crouch"), "Key Pose crouch, Angle front: 0 Idle Clips"),
        ("idle differs across Angles", edit(("clips", 1, "idle"), False), "idle differs across Angles"),
        ("a Move lacks an Angle", lambda d: d["clips"].pop(1), "no Clip for Angle side"),
        ("duplicate id", lambda d: d["clips"].append(copy.deepcopy(d["clips"][0])), "duplicate id"),
        ("opponent not a bool", edit(("clips", 2, "opponent"), "yes"), "opponent must be true or false"),
        ("opponent differs across Angles", edit(("clips", 2, "opponent"), True), "opponent differs across Angles"),
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
                 ("a hit is past the end", lambda root, c: _late_hit(os.path.join(root, c["clip_data"])), "hit outside the Clip"),
                 ("a hit target that is no point", lambda root, c: _hit(root, c, target="elbow"), "hit target 'elbow'"),
                 ("a giant target outside an Exchange", lambda root, c: _hit(root, c, target="g_core"), "hit target 'g_core' is the giant's"),
                 ("a giant limb outside an Exchange", lambda root, c: _hit(root, c, limb="g_hammer", target="head"), "hit limb 'g_hammer' is the giant's")]
        for name, damage, expect in cases:
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                root = package_with_media(tmp)
                damage(root, fixture_data()["clips"][2])
                problems = mf.validate(fixture_data(), root)
                self.assertTrue(any(expect in p for p in problems), problems)


class ExchangeTests(unittest.TestCase):
    """robot/CONTRACTS.md, the giant machine (#23): package/duel has Exchanges (opponent) on duel Angles; an Exchange carries the giant's points in
    every frame; a Hit may name a target."""
    DUEL = os.path.join(PACKAGES, "duel")

    def duel_data(self):
        with open(os.path.join(self.DUEL, "manifest.json")) as f:
            return json.load(f)

    def exchange(self, root, change_frame=None, hits=()):
        d = self.duel_data()
        c = next(c for c in d["clips"] if c["id"] == "clash__duel_wide")
        _rewrite(os.path.join(root, c["clip_data"]), lambda cd: ([change_frame(e) for e in cd["frames"]] if change_frame else None, cd["hits"].extend(hits)))
        return d

    def test_every_package_is_valid(self):
        for name in ("fixture", "many", "v1", "duel"):
            with self.subTest(name):
                with open(os.path.join(PACKAGES, name, "manifest.json")) as f:
                    self.assertEqual(mf.validate(json.load(f)), [])

    def test_accepted_with_files(self):
        cases = [("the duel package as written", ()),
                 ("the Android hits the giant", [{"f": 10, "point": [0.5, 0.4, 9], "strength": 1, "limb": "hand_r", "target": "g_knee_l"}]),
                 ("the giant hits the Android", [{"f": 20, "point": [0.5, 0.3, 3], "strength": 1, "limb": "g_hammer", "target": "head"}]),
                 ("a Hit on the floor", [{"f": 30, "point": [0.5, 0.9, 3], "strength": 0.5, "limb": "g_foot_l", "target": "floor"}]),
                 ("a Hit without target", [{"f": 40, "point": [0.5, 0.4, 3], "strength": 0.5, "limb": "foot_r"}])]
        for name, hits in cases:
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                root = package_with_media(tmp, self.DUEL)
                self.assertEqual(mf.validate(self.exchange(root, None, hits), root), [])

    def test_rejected_with_files(self):
        cases = [("an Exchange without the giant's points", lambda e: [e.pop(p) for p in mf.GIANT_POINTS], (), "lacks g_head"),
                 ("an Exchange without the knees", lambda e: e.pop("g_knee_r"), (), "lacks g_knee_r"),
                 ("a giant point that is no triple", lambda e: e.update(g_core=[0.5, 0.5]), (), "lacks g_core"),
                 ("an unknown target", None, [{"f": 1, "point": [0, 0, 0], "strength": 1, "limb": "hand_r", "target": "g_tail"}], "hit target 'g_tail'")]
        for name, change, hits, expect in cases:
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                root = package_with_media(tmp, self.DUEL)
                problems = mf.validate(self.exchange(root, change, hits), root)
                self.assertTrue(any(expect in p for p in problems), problems)

    def test_angles_of_a_kind(self):
        def drop_moves(*names):
            return lambda d: d.update(clips=[c for c in d["clips"] if c["move"] not in names])

        def add_clip(move, angle):
            def f(d):
                c = dict(next(c for c in d["clips"] if c["move"] == move), angle=angle, id="%s__%s" % (move, angle))
                d["clips"].append(c)
            return f
        cases = [
            ("an Exchange lacks a duel Angle", lambda d: d.update(clips=[c for c in d["clips"] if c["id"] != "clash__duel_low"]), "move clash: no Clip for Angle duel_low"),
            ("an Exchange on a solo Angle", add_clip("clash", "front"), "move clash: an Exchange on the solo Angle front"),
            ("a solo Move on a duel Angle", add_clip("sway", "duel_wide"), "move sway: a solo Move on the duel Angle duel_wide"),
            ("a duel Angle's opponent not a bool", lambda d: d["angles"][2].update(opponent="yes"), "angles[2]: opponent must be true or false"),
            ("a Key Pose an Exchange ends in has no duel Idle", drop_moves("duel_idle_crouch"), "Key Pose crouch, Angle duel_wide: 0 Idle Clips"),
            ("a solo Angle still needs every Key Pose's Idle", drop_moves("idle_crouch"), "Key Pose crouch, Angle front: 0 Idle Clips"),
            ("no Exchange touches crouch: no duel Idle needed", drop_moves("duel_idle_crouch", "hammer_dodge", "claw_counter", "stomp_block"), None),
        ]
        for name, mutate, expect in cases:
            with self.subTest(name):
                d = self.duel_data()
                mutate(d)
                problems = mf.validate(d)
                if expect is None:
                    self.assertEqual(problems, [])
                else:
                    self.assertTrue(any(expect in p for p in problems), problems)


def _hit(root, c, **fields):
    _rewrite(os.path.join(root, c["clip_data"]), lambda d: d["hits"].append(dict({"f": 3, "point": [0, 0, 0], "strength": 1, "limb": "hand_r"}, **fields)))


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
