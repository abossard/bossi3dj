"""xray.py: the beat clock Globals. Run: python3 -m unittest discover robot/magic/tests

The Globals run in a small interpreter of the ExprTk subset they use, with Magic's rule that every Global reads the previous frame's
values. Phase, DownSlot and Dt are driven from outside (the kick tracking that sets them is checked live by xray_check.py).
"""
import math
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import xray  # noqa: E402

CLOCK = ["BeatInBar", "BeatLag", "BeatPulse", "BarPulse", "Beats", "PhaseLag1", "PhaseLag2", "BeatFrac"]
ENV = {"_if": lambda c, a, b: a if c else b, "floor": math.floor, "ceil": math.ceil, "round": lambda v: math.floor(abs(v) + 0.5) * (1 if v >= 0 else -1),
       "frac": lambda v: v - math.floor(v), "abs": abs, "min": min, "max": max, "exp": math.exp}


def translate(expr):
    return re.sub(r"\bif\s*\(", "_if(", expr)


def run(drive, frames, rows=CLOCK):
    """Values per frame of the clock Globals; `drive(f)` gives Phase, DownSlot (and what else the rows read) for frame f."""
    spec = {name: (value, mods) for name, value, _s, mods in xray.globals_() if name in rows}
    prev = dict({n: v for n, (v, _m) in spec.items()}, **drive(0))
    out = []
    for f in range(1, frames + 1):
        cur = {}
        for name, (_v, mods) in spec.items():
            x = 0
            for _kind, e in mods:
                x = eval(translate(e), ENV, dict(prev, x=x, y=prev[name]))
            cur[name] = x
        cur.update(drive(f))
        prev = cur
        out.append(cur)
    return out


def steady(bpm, fps, shifts=()):
    """Phase advancing at `bpm` on a graphics clock of `fps`; DownSlot changes to the given values at the given frames: {frame: slot}."""
    def drive(f):
        slot = 0
        for at, s in sorted(shifts):
            if f >= at:
                slot = s
        return {"Phase": (f * bpm / 60.0 / fps) % 4, "DownSlot": slot, "Dt": 1.0 / fps}
    return drive


class BeatClockTests(unittest.TestCase):
    CASES = [("200 fps", 124, 200, ()), ("100 fps", 124, 100, ()), ("30 fps", 124, 30, ()), ("slow tempo at 200 fps", 90, 200, ()),
             ("bar grid shifts by 2", 124, 200, [(900, 2)]), ("bar grid shifts back", 124, 200, [(500, 1), (1100, 3)])]

    def test_beats_and_beat_fraction_step_in_the_same_frame(self):
        """Beats + BeatFrac is what /vj/clip_frame is made of: it must never fall back at a beat (the live test saw one beat back for 2 to 3 frames)."""
        for name, bpm, fps, shifts in self.CASES:
            with self.subTest(name):
                frames = run(steady(bpm, fps, shifts), int(fps * 20))
                pos = [v["Beats"] + v["BeatFrac"] for v in frames]
                dips = [(i, round(b - a, 2)) for i, (a, b) in enumerate(zip(pos, pos[1:])) if b < a - 0.5]
                self.assertEqual(dips, [])

    def test_beat_fraction_wraps_in_the_frame_beats_steps(self):
        for name, bpm, fps, shifts in self.CASES[:4]:
            with self.subTest(name):
                frames = run(steady(bpm, fps), int(fps * 20))
                step = [i for i in range(1, len(frames)) if frames[i]["Beats"] > frames[i - 1]["Beats"]]
                wrap = [i for i in range(1, len(frames)) if frames[i]["BeatFrac"] < frames[i - 1]["BeatFrac"] - 0.5]
                self.assertGreater(len(step), 20)
                self.assertEqual(step[3:], wrap[3:])

    def test_beats_count_the_tempo_and_bar_lines_are_multiples_of_four(self):
        frames = run(steady(124, 200), 200 * 30)
        beats = [v["Beats"] for v in frames]
        self.assertAlmostEqual(beats[-1] - beats[200 * 5], 124 / 60.0 * 25, delta=2)
        self.assertTrue(all(b >= a for a, b in zip(beats, beats[1:])))
        self.assertEqual({int(b) % 4 for a, b in zip(beats, beats[1:]) if frames[beats.index(b)]["BeatInBar"] == 0 and b > a}, {0})


if __name__ == "__main__":
    unittest.main()


# ------------------------------------------------------------ section start-up (#29)

SECTION_ROWS = ["SubLow", "SubHigh", "Quiet", "RiseMin", "VolSlow", "MusicBars", "SubOut", "DropPulse", "DownSlot", "ThinBars", "State"]
# The rules before #29, kept here to show the replay reproduces the live misread with them
LEGACY = {"SubOut": "if (BarPulse > 0.5, if (SubBar < SubLow, y + 1, 0), y)",
          "DropPulse": "if (SubFast > SubHigh and SubOut >= 2 and abs(State - 3) > 0.5 and y < 0.5, 1, 0)"}
LOG = os.path.join(HERE, "data", "live-2026-11-17-start.txt")
FPS = 100


def run_sections(drive, frames, legacy=False):
    """The section Globals of xray.py per frame (legacy: SubOut and DropPulse as before #29); `drive(f)` gives Volume, Dt, Phase, BarPulse,
    SubBar, SubFast, KickRate, ToneRise, SnareRate. Rows without modifiers keep their value."""
    spec = {}
    for name, value, _s, mods in xray.globals_():
        if name in SECTION_ROWS:
            if legacy and name in LEGACY:
                mods = [("Expression", LEGACY[name])]
            spec[name] = (value, mods)
    if legacy:
        spec.pop("MusicBars")
    prev = dict({n: v for n, (v, _m) in spec.items()}, MusicBars=99, **drive(0))
    out = []
    for f in range(1, frames + 1):
        cur = {}
        for name, (value, mods) in spec.items():
            x = value
            for _kind, e in mods:
                x = eval(translate(e), ENV, dict(prev, x=x, y=prev[name]))
            cur[name] = x
        cur.update(drive(f))
        if legacy:
            cur["MusicBars"] = 99
        prev = cur
        out.append(cur)
    return out


def bar_pulses(bpm, seconds, start=0.0):
    period = 4 * 60.0 / bpm
    return {int(round((start + k * period) * FPS)) for k in range(int(seconds / period) + 2)}


class StartUpReplayTests(unittest.TestCase):
    """Replays the start of the live run of 2026-11-17 (robot/magic/live_test.py probe log): Magic's Volume and bar lines as logged, after the
    15 s of silence the run waited for. What the log lacks (the bass bands) follows the misread's cause: the intro's kick read as full sub."""
    SILENCE = 16.0

    def drive(self):
        events = []
        with open(LOG) as f:
            for line in f:
                t, n, v = line.split()
                events.append((float(t) + self.SILENCE, n, float(v)))
        vol = sorted((t, v) for t, n, v in events if n == "Volume")
        beats = sorted((t, v) for t, n, v in events if n == "Beats" and t > self.SILENCE + 0.5)
        bars = {int(t * FPS) for t, v in beats if int(v) % 4 == 0} | bar_pulses(120, self.SILENCE)
        def volume(t):
            last = 0.0
            for tv, v in vol:
                if tv > t:
                    break
                last = v
            return last
        cache = {}

        def drive(f):
            t = f / FPS
            v = cache.setdefault(f, volume(t))
            loud = v > 0.05 or (t > self.SILENCE + 0.7)        # the track plays on from its first kick
            return {"Volume": v, "Dt": 1.0 / FPS, "Phase": (t * 2) % 4, "BarPulse": 1 if f in bars else 0, "SubBar": 0.6 if loud else 0.0,
                    "SubFast": 1.0 if loud else 0.0, "KickRate": 4 if loud else 0, "ToneRise": 0, "SnareRate": 0}
        return drive

    def logged_state(self):
        with open(LOG) as f:
            return next(float(t) + self.SILENCE for t, n, v in (line.split() for line in f) if n == "State" and float(v) == 3)

    def test_the_old_rules_reproduce_the_misread(self):
        frames = run_sections(self.drive(), int((self.SILENCE + 14) * FPS), legacy=True)
        first = next(i for i, v in enumerate(frames) if v["State"] == 3) / FPS
        self.assertLess(abs(first - self.logged_state()), 1.0, (first, self.logged_state()))

    def test_the_new_rules_wait_for_evidence(self):
        frames = run_sections(self.drive(), int((self.SILENCE + 14) * FPS))
        self.assertEqual({v["State"] for v in frames}, {0})
        self.assertFalse(any(v["DropPulse"] for v in frames))


class SectionRuleTests(unittest.TestCase):
    """The start-up and re-anchoring rules on made-up bars at 120 BPM (2 s a bar): (bars of silence, then per bar sub, kick)."""

    def scenario(self, bars, legacy=False):
        """bars: list of (volume, sub, kick) per bar; returns frames."""
        def drive(f):
            t = f / FPS
            b = min(int(t / 2.0), len(bars) - 1)
            vol, sub, kick = bars[b]
            lagged = bars[max(0, min(int((t - 0.5) / 2.0), len(bars) - 1))][1]     # SubBar averages 2 beats: at a bar line it still holds the bar before
            return {"Volume": vol, "Dt": 1.0 / FPS, "Phase": (t * 2 + 0.5) % 4, "BarPulse": 1 if f % 200 == 0 and f else 0,
                    "SubBar": 0.6 if lagged else 0.1, "SubFast": 1.0 if sub else 0.1, "KickRate": 4 if kick else 0, "ToneRise": 0, "SnareRate": 0}
        return run_sections(drive, len(bars) * 200, legacy)

    def first(self, frames, key, value):
        return next((i / FPS for i, v in enumerate(frames) if v[key] == value), None)

    def test_rules(self):
        silence, intro, drop, gap = (0, 0, 0), (0.3, 0, 1), (0.3, 1, 1), (0.3, 0, 1)
        cases = [
            # name, bars, first drop (s) new, first drop (s) legacy
            ("silence then a drop at once: no evidence, no drop", [silence] * 8 + [drop] * 6, None, 16.0),
            ("silence, 2 intro bars, then the drop", [silence] * 8 + [intro] * 2 + [drop] * 4, 20.0, 20.0),
            ("silence, 1 intro bar: still too little", [silence] * 8 + [intro] + [drop] * 4, None, 18.0),
        ]
        for name, bars, new, old in cases:
            with self.subTest(name):
                for legacy, want in ((False, new), (True, old)):
                    got = self.first(self.scenario(bars, legacy), "State", 3)
                    if want is None:
                        self.assertIsNone(got, (legacy, got))
                    else:
                        self.assertIsNotNone(got, legacy)
                        self.assertLess(abs(got - want), 0.1, (legacy, got))

    def test_a_drop_after_a_missed_breakdown_re_anchors_the_bar_grid(self):
        """In a drop the sub stops for 2 bars but the kick goes on (State stays 3), then the sub returns: the new rules re-anchor DownSlot, the old did not."""
        bars = [(0.3, 0, 1)] * 2 + [(0.3, 1, 1)] * 3 + [(0.3, 0, 1)] * 2 + [(0.3, 1, 1)] * 3
        for legacy, pulses in ((False, 2), (True, 1)):
            with self.subTest(legacy=legacy):
                frames = self.scenario(bars, legacy)
                n = sum(1 for a, b in zip(frames, frames[1:]) if b["DropPulse"] and not a["DropPulse"])
                self.assertEqual(n, pulses)
                self.assertEqual(frames[-1]["State"], 3)
