"""clip_graph.py: the Clip Graph model. Run: python3 -m unittest discover robot/magic/tests"""
import copy
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import clip_graph as cg  # noqa: E402
import manifest as mf  # noqa: E402

with open(os.path.join(HERE, "..", "..", "package", "fixture", "manifest.json")) as _f:
    FIXTURE = json.load(_f)


with open(os.path.join(HERE, "..", "..", "package", "many", "manifest.json")) as _f:
    MANY = json.load(_f)


def many():
    """3 Key Poses, 6 Moves per tier of 4, 8 and 16 beats, an Idle Clip per Key Pose (package/many)."""
    assert mf.validate(MANY) == [], mf.validate(MANY)
    return mf.Manifest(MANY)


def manifest(mutate=None):
    d = copy.deepcopy(FIXTURE)
    if mutate:
        mutate(d)
    assert mf.validate(d) == [], mf.validate(d)
    return mf.Manifest(d)


def with_poses(d):
    """A second Key Pose, `crouch`, with its Idle Clip: jab_cross goes guard to crouch, take_hit crouch to guard. The rest is guard to guard."""
    d["key_poses"] = ["guard", "crouch"]
    for c in list(d["clips"]):
        if c["move"] == "jab_cross":
            c["key_out"] = "crouch"
        if c["move"] == "take_hit":
            c["key_in"] = "crouch"
        if c["move"] == "idle":
            d["clips"].append(dict(c, id="crouch_idle__" + c["angle"], move="crouch_idle", key_in="crouch", key_out="crouch"))


def no_calm(d):
    for c in d["clips"]:
        if c["tier"] == "calm":
            c["tier"] = "build"
            c["idle"] = c["idle"]


def long_moves(d):
    for c in d["clips"]:
        if c["move"] == "front_kick":
            c.update(beats=8, frames=116)


class TierTests(unittest.TestCase):
    def test_tier_of_section(self):
        for section, tier in [(0, "calm"), (1, "calm"), (2, "build"), (3, "drop"), (4, "calm")]:
            with self.subTest(section=section):
                self.assertEqual(cg.ClipGraph.tier(section), tier)

    def test_tier_changes_only_on_a_bar_boundary(self):
        g = cg.ClipGraph(manifest(), seed=3)
        for name, sections in [("every section in turn", [0, 2, 3, 4, 2, 3, 0] * 12), ("a change every beat", [3, 0, 2, 4] * 20),
                               ("a change just after a bar", [0] * 5 + [3] * 7 + [2] * 6 + [0] * 6)]:
            with self.subTest(name):
                prev = g.start()
                for beat, s in enumerate(g.walk(sections), 1):
                    if s.tier != prev.tier:
                        self.assertEqual(beat % 4, 0, beat)
                        self.assertEqual(s.tier, g.tier(sections[beat - 1]))
                    prev = s

    def test_a_section_change_mid_bar_waits_for_the_next_bar(self):
        walk = cg.ClipGraph(manifest()).walk([0] * 5 + [3] * 7)
        self.assertEqual([s.tier for s in walk], ["calm"] * 7 + ["drop"] * 5)


class CandidateTests(unittest.TestCase):
    def test_candidates_and_pool(self):
        cases = [("all guard, calm: no Move Clip fits", None, "idle", "calm", [], ["idle"]),
                 ("all guard, build: either build Move", None, "idle", "build", ["jab_cross", "take_hit"], ["jab_cross", "take_hit"]),
                 ("all guard, build, from jab_cross: not jab_cross", None, "jab_cross", "build", ["take_hit"], ["take_hit"]),
                 ("all guard, drop from front_kick: alone, so itself", None, "front_kick", "drop", ["front_kick"], ["front_kick"]),
                 ("a Move with no pick in its tier goes to the Idle Clip", None, "jab_cross", "calm", [], ["idle"]),
                 ("jab_cross ends in crouch: build picks take_hit", with_poses, "jab_cross", "build", ["take_hit"], ["take_hit"]),
                 ("jab_cross ends in crouch: drop has no Move there, so crouch_idle", with_poses, "jab_cross", "drop", [], ["crouch_idle"]),
                 ("crouch_idle in build: take_hit starts in crouch", with_poses, "crouch_idle", "build", ["take_hit"], ["take_hit"]),
                 ("crouch_idle in calm: stays", with_poses, "crouch_idle", "calm", [], ["crouch_idle"]),
                 ("take_hit ends in guard: calm goes to idle", with_poses, "take_hit", "calm", [], ["idle"])]
        for name, mutate, move, tier, cands, pool in cases:
            with self.subTest(name):
                g = cg.ClipGraph(manifest(mutate))
                self.assertEqual(g.candidates(move, tier), cands)
                self.assertEqual(g.pool(move, tier), pool)

    def test_every_pick_follows_the_key_pose(self):
        m = manifest(with_poses)
        g = cg.ClipGraph(m, seed=3)
        for move in m.moves:
            for tier in ("calm", "build", "drop"):
                for bar in range(40):
                    with self.subTest(move=move.name, tier=tier, bar=bar):
                        nxt = m.move(g.next_move(move.name, bar, tier))
                        self.assertEqual(nxt.key_in, move.key_out)
                        self.assertFalse(nxt.idle and nxt.name != move.name and g.candidates(move.name, tier))


with open(os.path.join(HERE, "..", "..", "package", "duel", "manifest.json")) as _f:
    DUEL = json.load(_f)


def duel(mutate=None):
    """package/duel: solo Moves on front and side, Exchanges with the giant machine on duel_wide and duel_low (#23)."""
    d = copy.deepcopy(DUEL)
    if mutate:
        mutate(d)
    assert mf.validate(d) == [], mf.validate(d)
    return mf.Manifest(d)


class DuelTests(unittest.TestCase):
    SEEDS = (0, 1, 2.5, 7, 42)
    SECTIONS = ([0] * 16 + [2] * 16 + [3] * 32 + [4] * 16 + [3] * 24 + [0] * 16) * 2

    def walk(self, m, seed, sections=None):
        g = cg.ClipGraph(m, seed=seed)
        return g, g.walk(sections or self.SECTIONS)

    def test_moves_and_angles_stay_of_one_kind(self):
        m = duel()
        for seed in self.SEEDS:
            with self.subTest(seed=seed):
                g, walk = self.walk(m, seed)
                for beat, s in enumerate(walk, 1):
                    self.assertEqual(m.angle_duel(s.angle), m.move(s.move).opponent, (beat, s))
                kinds = {m.move(s.move).opponent for s in walk}
                self.assertEqual(kinds, {False, True})

    def test_the_kind_changes_only_from_an_idle_clip_on_a_bar_line_into_the_same_key_pose(self):
        m = duel()
        for seed in self.SEEDS:
            with self.subTest(seed=seed):
                g, walk = self.walk(m, seed)
                prev = g.start()
                for beat, s in enumerate(walk, 1):
                    a, b = m.move(prev.move), m.move(s.move)
                    if a.opponent != b.opponent:
                        self.assertEqual(beat % 4, 0, beat)
                        self.assertTrue(a.idle and b.idle, (beat, prev, s))
                        self.assertEqual(a.key_in, b.key_in)
                        self.assertEqual(s.angle, m.group(b.opponent)[0])
                    prev = s

    def test_duel_in_the_drop_solo_otherwise(self):
        """Once the tier settles, the kind follows it within 3 bars: the Move's end, its Idle Clip, the other kind's Idle Clip."""
        m = duel()
        for seed in self.SEEDS:
            with self.subTest(seed=seed):
                g, walk = self.walk(m, seed)
                for beat in range(1, len(walk) + 1):
                    s, settled = walk[beat - 1], walk[max(0, beat - 1 - 12 - 16):beat]
                    if len({x.tier for x in settled}) == 1 and len(settled) == 29:
                        self.assertEqual(m.move(s.move).opponent, s.tier == "drop", (beat, s))

    def test_cuts_stay_within_the_kind(self):
        m = duel()
        for seed in self.SEEDS:
            with self.subTest(seed=seed):
                g, walk = self.walk(m, seed)
                prev = g.start()
                cuts = 0
                for s in walk:
                    if s.angle != prev.angle and m.move(s.move).opponent == m.move(prev.move).opponent:
                        cuts += 1
                        self.assertEqual(m.angle_duel(s.angle), m.angle_duel(prev.angle))
                    prev = s
                self.assertGreater(cuts, 10)

    def test_picks_follow_the_key_pose(self):
        m = duel()
        g, walk = self.walk(m, 3)
        prev = g.start()
        for beat, s in enumerate(walk, 1):
            if s.start != prev.start:
                self.assertEqual(m.move(s.move).key_in, m.move(prev.move).key_out, beat)
            prev = s

    def test_a_key_pose_without_a_duel_idle_stays_solo(self):
        def guard_only(d):
            d["clips"] = [c for c in d["clips"] if c["move"] not in ("duel_idle_crouch", "hammer_dodge", "claw_counter", "stomp_block")]
        m = duel(guard_only)
        g = cg.ClipGraph(m)
        self.assertEqual(g.pool("idle_crouch", "drop"), ["uppercut_rise", "sweep"])
        self.assertEqual(g.pool("sweep", "drop"), ["uppercut_rise"])
        self.assertEqual(g.pool("idle_guard", "drop"), ["duel_idle_guard"])
        self.assertEqual(g.pool("front_kick", "drop"), ["idle_guard"])

    def test_pools(self):
        m = duel()
        g = cg.ClipGraph(m)
        cases = [("a solo Move in the drop goes to its Idle Clip", "front_kick", "drop", ["idle_guard"]),
                 ("the solo Idle Clip hands over to the duel one", "idle_guard", "drop", ["duel_idle_guard"]),
                 ("the duel Idle Clip picks Exchanges", "duel_idle_guard", "drop", ["clash", "hammer_dodge"]),
                 ("an Exchange picks Exchanges, not itself", "clash", "drop", ["hammer_dodge"]),
                 ("an Exchange after the drop goes to its duel Idle Clip", "hammer_dodge", "calm", ["duel_idle_crouch"]),
                 ("the duel Idle Clip hands back to the solo one", "duel_idle_crouch", "build", ["idle_crouch"]),
                 ("solo in build picks solo Moves", "idle_guard", "build", ["jab_cross", "feint_duck"])]
        for name, move, tier, pool in cases:
            with self.subTest(name):
                self.assertEqual(g.pool(move, tier), pool)

    def test_a_solo_manifest_never_wants_the_duel(self):
        g = cg.ClipGraph(many())
        self.assertFalse(any(g.wants_duel(t) for t in ("calm", "build", "drop")))


class NoRepeatTests(unittest.TestCase):
    SEEDS = (0, 1, 2.5, 7, 42)

    def others(self, m, move, tier):
        key = m.move(move).key_out
        return [x.name for x in m.moves if not x.idle and x.key_in == key and x.tier == tier and x.name != move]

    def test_the_pick_is_never_the_same_move_when_another_fits(self):
        for name, m in [("3 Key Poses", many()), ("two Key Poses", manifest(with_poses)), ("one Key Pose", manifest())]:
            for seed in self.SEEDS:
                with self.subTest(name, seed=seed):
                    g = cg.ClipGraph(m, seed=seed)
                    for mv in m.moves:
                        for tier in ("calm", "build", "drop"):
                            for bar in range(60):
                                if mv.idle or not self.others(m, mv.name, tier):
                                    continue
                                self.assertNotEqual(g.next_move(mv.name, bar, tier), mv.name, (mv.name, tier, bar))

    def test_a_walk_never_plays_the_same_move_twice_in_a_row_when_another_fits(self):
        m = many()
        for seed in self.SEEDS:
            for sections in ([2] * 400, [3] * 400, [0, 2, 3, 4] * 100, [3, 3, 3, 3, 2, 2, 2, 2] * 50):
                with self.subTest(seed=seed, sections=sections[:4]):
                    g = cg.ClipGraph(m, seed=seed)
                    walk, prev = g.walk(sections), g.start()
                    for beat, s in enumerate(walk, 1):
                        if s.start != prev.start and not m.move(prev.move).idle and not m.move(s.move).idle:
                            self.assertNotEqual(s.move, prev.move, beat)
                        prev = s

    def test_a_pool_of_one_repeats_itself(self):
        g = cg.ClipGraph(manifest())
        self.assertEqual(g.pool("front_kick", "drop"), ["front_kick"])


class KeyPoseTests(unittest.TestCase):
    SEEDS = (0, 1, 2.5, 7, 42, 99)

    def sections(self, seed, n=480):
        import random
        r, out, cur = random.Random(seed), [], 0
        for _ in range(n // 4):
            cur = r.choice([0, 2, 3, 4]) if r.random() < 0.4 else cur
            out += [cur] * 4
        return out

    def test_every_key_pose_has_a_way_out_in_every_tier(self):
        self.assertEqual(cg.ClipGraph(many()).dead_ends(), [])
        g = cg.ClipGraph(manifest())
        self.assertEqual(g.dead_ends(), [("guard", "calm")])
        self.assertEqual(sorted(g.exits()[("guard", "build")]), ["jab_cross", "take_hit"])

    def test_dead_ends_name_the_missing_pair(self):
        def no_crouch_drop(d):
            d["clips"] = [c for c in d["clips"] if c["move"] not in ("sweep", "uppercut_rise")]
        self.assertEqual(cg.ClipGraph(mf.Manifest(self.mutated(no_crouch_drop))).dead_ends(), [("crouch", "drop")])

    def mutated(self, f):
        import copy
        d = copy.deepcopy(MANY)
        f(d)
        return d

    def test_the_walk_visits_every_key_pose_and_follows_key_out_to_key_in(self):
        m = many()
        for seed in self.SEEDS:
            with self.subTest(seed=seed):
                g = cg.ClipGraph(m, seed=seed)
                walk = g.walk(self.sections(seed))
                poses = {m.move(s.move).key_in for s in walk}
                self.assertEqual(poses, {"guard", "crouch", "stance"})
                prev = g.start()
                for beat, s in enumerate(walk, 1):
                    if s.start != prev.start:
                        self.assertEqual(m.move(s.move).key_in, m.move(prev.move).key_out, beat)
                    prev = s

    def test_the_walk_never_waits_in_an_idle_clip_longer_than_a_bar(self):
        """With a way out in every tier an Idle Clip is left at the first bar line after it has played."""
        m = many()
        for seed in self.SEEDS:
            with self.subTest(seed=seed):
                walk = cg.ClipGraph(m, seed=seed).walk(self.sections(seed))
                run = 0
                for s in walk:
                    run = run + 1 if m.move(s.move).idle else 0
                    self.assertLessEqual(run, 4)

    def test_without_a_way_out_the_walk_waits_in_the_idle_clip_and_leaves_on_a_bar_when_there_is_one(self):
        """The fixture has no calm Move: a Move that ends in calm goes to the Idle Clip, which waits; when build comes it leaves on a bar line."""
        m = manifest()
        g = cg.ClipGraph(m, seed=1)
        walk = g.walk([2] * 4 + [0] * 12 + [2] * 8)
        self.assertTrue(m.move(walk[11].move).idle)
        left = [beat + 1 for beat, (a, b) in enumerate(zip(walk, walk[1:]), 1) if m.move(a.move).idle and not m.move(b.move).idle]
        self.assertTrue(left and all(beat % 4 == 0 for beat in left), left)


class WalkTests(unittest.TestCase):
    SECTIONS = {"calm": 0, "build": 2, "drop": 3}

    def test_deterministic_with_a_seed(self):
        sections = [0, 2, 3, 4] * 20
        for seed in (0, 1, 42.5):
            with self.subTest(seed=seed):
                m = manifest()
                self.assertEqual(cg.ClipGraph(m, seed=seed).walk(sections), cg.ClipGraph(m, seed=seed).walk(sections))

    def test_seeds_differ(self):
        m = manifest()
        runs = {tuple(cg.ClipGraph(m, seed=s, cut_rate=0.5).walk([2] * 80)) for s in range(6)}
        self.assertGreater(len(runs), 3)

    def test_moves_change_only_on_a_bar_and_after_their_beats(self):
        for name, build in [("4 beat Clips", manifest), ("an 8 beat Clip", lambda: manifest(long_moves)), ("4, 8 and 16 beat Clips", many)]:
            with self.subTest(name):
                m = build()
                g = cg.ClipGraph(m, seed=5)
                prev = g.start()
                for beat, s in enumerate(g.walk([0, 2, 3] * 120), 1):
                    if s.move != prev.move or s.start != prev.start:
                        self.assertEqual(beat % 4, 0)
                        self.assertEqual(s.start, beat)
                        if m.move(prev.move).idle:
                            self.assertGreaterEqual(beat - prev.start, 4)
                        else:
                            self.assertEqual(beat - prev.start, m.move(prev.move).beats)
                    prev = s

    def test_tier_picks_a_move_of_that_tier(self):
        m = manifest()
        for tier, section in self.SECTIONS.items():
            with self.subTest(tier=tier):
                g = cg.ClipGraph(m, seed=2)
                moves = {s.move for s in g.walk([section] * 64)[4:]}
                self.assertTrue(all(m.move(x).tier == tier for x in moves), moves)

    def test_a_move_with_no_next_pick_goes_to_the_idle_clip_and_leaves_on_a_bar(self):
        cases = [
            ("build Move, then calm: idle from the bar the Move ends", [2] * 7 + [0] * 13,
             {7: "build", 8: "idle", 12: "idle", 19: "idle"}),
            ("calm all along: idle never leaves", [0] * 40, {1: "idle", 20: "idle", 39: "idle"}),
            ("build arrives mid-bar: the Idle Clip is left on the next bar", [0] * 5 + [2] * 11,
             {5: "idle", 6: "idle", 7: "idle", 8: "build", 11: "build"}),
            ("build is there at the start: left on the first bar after it began", [2] * 12, {3: "idle", 4: "build"}),
            ("drop Move repeats itself (alone in its tier), calm then idles", [3] * 8 + [0] * 8,
             {8: "drop", 11: "drop", 12: "idle", 16: "idle"}),
        ]
        m = manifest()
        for name, sections, expect in cases:
            with self.subTest(name):
                walk = cg.ClipGraph(m, seed=1).walk(sections)
                for beat, kind in expect.items():
                    mv = m.move(walk[beat - 1].move)
                    self.assertEqual("idle" if mv.idle else mv.tier, kind, (beat, walk[beat - 1]))

    def test_an_idle_clip_is_left_only_into_a_move_that_starts_in_its_pose(self):
        m = manifest(with_poses)
        g = cg.ClipGraph(m, seed=2)
        # build section from the start: idle (guard) leaves to jab_cross (guard to crouch), which has no build Move to go on with
        # but take_hit (starts in crouch); at calm the pose's Idle Clip is crouch_idle, left again once build returns
        walk = g.walk([2] * 8 + [0] * 8 + [2] * 8)
        names = [s.move for s in walk]
        self.assertEqual((names[2], names[3]), ("idle", "jab_cross"))
        self.assertEqual(names[7], "take_hit")
        for prev, s in zip(walk, walk[1:]):
            if s.move != prev.move:
                self.assertEqual(m.move(s.move).key_in, m.move(prev.move).key_out)

    def test_angle_changes_only_at_cut_points(self):
        m = manifest()
        g = cg.ClipGraph(m, seed=9)
        prev = g.start()
        changes = 0
        for beat, s in enumerate(g.walk([2] * 64), 1):
            if s.angle != prev.angle:
                changes += 1
                self.assertIn((beat - s.start) % m.move(s.move).beats, m.move(s.move).cut_points)
            prev = s
        self.assertGreater(changes, 4)

    def test_cut_rate(self):
        """32 Cut Points in 64 beats; each pick's chance is cut_rate x (0.4 + 1.2 x its Flavor), 0.85 on average at 1."""
        m = manifest()
        for rate, expect in [(0.0, lambda n: n == 0), (1.0, lambda n: 22 <= n <= 32), (0.5, lambda n: 8 <= n <= 28)]:
            with self.subTest(cut_rate=rate):
                walk = cg.ClipGraph(m, seed=4, cut_rate=rate).walk([2] * 64)
                changes = sum(1 for a, b in zip(walk, walk[1:]) if a.angle != b.angle)
                self.assertTrue(expect(changes), changes)

    def test_a_single_angle_never_cuts(self):
        def one_angle(d):
            d["angles"] = d["angles"][:1]
            d["clips"] = [c for c in d["clips"] if c["angle"] == "front"]
        walk = cg.ClipGraph(manifest(one_angle)).walk([2] * 32)
        self.assertEqual({s.angle for s in walk}, {"front"})

    def test_first_state(self):
        s = cg.ClipGraph(manifest()).start()
        self.assertEqual(s, cg.State("idle", "front", 0))


with open(os.path.join(HERE, "..", "..", "package", "variants", "manifest.json")) as _f:
    VARIANTS = json.load(_f)


def variants(mutate=None):
    """package/variants: package/duel with 4 variants of every Move and 3 of every Idle Clip (#32)."""
    d = copy.deepcopy(VARIANTS)
    if mutate:
        mutate(d)
    assert mf.validate(d) == [], mf.validate(d)
    return mf.Manifest(d)


def without(*families):
    """Drop whole families (a base Move and its variants)."""
    return lambda d: d.update(clips=[c for c in d["clips"] if c.get("variant_of", c["move"]) not in families])


def picks(g, walk):
    """(beat, Move) of every pick in a walk."""
    out, prev = [], g.start()
    for beat, s in enumerate(walk, 1):
        if s.start != prev.start:
            out.append((beat, s.move))
        prev = s
    return out


class VariantTests(unittest.TestCase):
    SEEDS = (0, 1, 2.5, 7, 42)
    MINUTE = 124          # beats in 60 s at the fixture's 124 BPM
    SHOW = [0] * 32 + [2] * 64 + [3] * 96 + [4] * 32 + [2] * 32 + [3] * 64 + [0] * 52      # 372 beats: 3 minutes

    def test_three_minutes_never_pick_the_same_clip_twice_within_a_minute(self):
        m = variants()
        for seed in self.SEEDS:
            with self.subTest(seed=seed):
                g = cg.ClipGraph(m, seed=seed)
                last, used = {}, set()
                for beat, move in picks(g, g.walk(self.SHOW)):
                    if move in last:
                        self.assertGreaterEqual(beat - last[move], self.MINUTE, (move, last[move], beat))
                    last[move] = beat
                    used.add(move)
                self.assertGreater(len(used), 40)

    def test_each_family_is_as_likely_however_many_variants_it_has(self):
        """sway has 4 variants, duck 1: from idle_guard in calm, with nothing played yet, each family wins about half the bars."""
        m = variants(lambda d: d.update(clips=[c for c in d["clips"] if not c["move"].startswith("duck_v")]))
        for seed in self.SEEDS:
            with self.subTest(seed=seed):
                g = cg.ClipGraph(m, seed=seed)
                fams = [m.move(g.next_move("idle_guard", bar, "calm")).family for bar in range(400)]
                self.assertTrue(150 <= fams.count("duck") <= 250, fams.count("duck"))

    def test_fresh_before_stale_and_the_oldest_when_none_is_fresh(self):
        m = variants()
        g = cg.ClipGraph(m, seed=3)
        bar = 100
        beat = 4 * bar
        sways = ["sway", "sway_v2", "sway_v3", "sway_v4"]
        cases = [
            ("sway played 2 bars ago: duck", {"sway_v2": beat - 8}, lambda p: m.move(p).family == "duck"),
            ("both families recent: the older family, duck", {"sway_v2": beat - 8, "duck": beat - 16}, lambda p: m.move(p).family == "duck"),
            ("duck just played, sway 8 bars ago: sway is fresh again", {"duck": beat - 4, "sway": beat - 32}, lambda p: p in sways[1:]),
            ("every variant of both within the window: the oldest sway", dict({v: beat - 20 - i for i, v in enumerate(sways)},
                                                                                  **{v: beat - 4 for v in m.variants("duck")}), lambda p: p == "sway_v4"),
        ]
        for name, used, ok in cases:
            with self.subTest(name):
                p = g.next_move("idle_guard", bar, "calm", tuple(used.items()))
                self.assertTrue(ok(p), p)

    def test_an_idle_chain_walks_its_variants_at_their_length_never_one_after_itself(self):
        """No calm Move leaves guard: the Idle Clip plays its whole length, then another variant of its family."""
        m = variants(without("sway", "duck"))
        for seed in self.SEEDS:
            with self.subTest(seed=seed):
                g = cg.ClipGraph(m, seed=seed)
                walk = g.walk([0] * 96)
                chain = [(beat, move) for beat, move in picks(g, walk) if beat > 4]
                self.assertTrue(all(m.move(mv).idle and m.move(mv).key_in == "guard" for _b, mv in chain), chain)
                self.assertEqual({mv for _b, mv in chain}, set(m.idle_family("guard")))
                for (b1, a), (b2, c) in zip(chain, chain[1:]):
                    self.assertNotEqual(a, c)
                    self.assertEqual(b2 - b1, m.move(a).beats)

    def test_an_idle_chain_leaves_into_a_move_on_the_next_bar(self):
        m = variants(without("sway", "duck"))
        g = cg.ClipGraph(m, seed=1)
        walk = g.walk([0] * 30 + [2] * 10)
        first = next(beat for beat, s in enumerate(walk, 1) if not m.move(s.move).idle)
        self.assertEqual(first, 32)

    def test_each_pick_cuts_with_its_own_chance(self):
        """At cut_rate 1 a pick with Flavor 0.5 or more cuts at every Cut Point; one with less skips some."""
        m = variants()
        full = some = 0
        for seed in self.SEEDS:
            g = cg.ClipGraph(m, seed=seed)
            walk = g.walk(self.SHOW)
            prev = g.start()
            per_pick = {}
            for beat, s in enumerate(walk, 1):
                mv = m.move(s.move)
                if (beat - s.start) % mv.beats in mv.cut_points and m.angle_duel(s.angle) == m.angle_duel(prev.angle) and s.start != beat:
                    per_pick.setdefault(s.start, []).append(s.angle != prev.angle)
                prev = s
            for start, cuts in per_pick.items():
                if g.flavor(start) >= 0.5:
                    self.assertTrue(all(cuts), (seed, start))
                    full += 1
                elif not all(cuts):
                    some += 1
        self.assertGreater(full, 20)
        self.assertGreater(some, 10)


class OutputTests(unittest.TestCase):
    def test_clip_index_and_frame(self):
        m = manifest()
        g = cg.ClipGraph(m)
        s = cg.State("front_kick", "side", 8)
        self.assertEqual(g.clip_index(s), 5)
        for beat, phase, frame in [(8, 0, 0), (9, 0, 14), (10, 0.5, 36), (11, 0.99, 57), (12, 0, 57), (30, 0, 57)]:
            with self.subTest(beat=beat, phase=phase):
                self.assertEqual(g.frame(s, beat, phase), frame)

    def test_idle_clip_frames_wrap(self):
        g = cg.ClipGraph(manifest())
        s = cg.State("idle", "front", 4)
        for beat, phase, frame in [(4, 0, 0), (7, 0.99, 57), (8, 0, 0), (9, 0, 14), (12, 0.5, 7)]:
            with self.subTest(beat=beat, phase=phase):
                self.assertEqual(g.frame(s, beat, phase), frame)

    def test_hash_is_the_documented_formula(self):
        for n, seed, salt in [(1, 0, 0), (4, 0, 1), (7, 2.5, 2), (100, 9, 0)]:
            with self.subTest(n=n, seed=seed, salt=salt):
                import math
                v = math.sin(n * 12.9898 + seed * 78.233 + salt * 37.719) * 43758.5453
                self.assertEqual(cg.hash01(n, seed, salt), v - math.floor(v))
                self.assertTrue(0 <= cg.hash01(n, seed, salt) < 1)


if __name__ == "__main__":
    unittest.main()
