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
       "frac": lambda v: v - math.floor(v), "abs": abs, "min": min, "max": max}


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
