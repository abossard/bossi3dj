"""Weight layers (weight.py): hit-stop warp holds and lands the next beat, flight is ballistic, Hits keep their
frame and limb, touch-downs dip, the spring and its pins behave, the floor only pushes. Also keeps the research's measurement of the key tables (docs/research/
weighted-animation.md, section 1) as a check. No Blender.
Run: python3 -m unittest discover robot/build/tests"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import exchanges as X  # noqa: E402
import moves  # noqa: E402
import weight  # noqa: E402

AIR_TOL = 1.5          # m/s² around -g
HIT_TOL_M = 0.02
HOLD_DRIFT_M = 0.02     # recoils and dips of earlier events still fade during a hold


def _sequences():
    """(name, weighted Android Poses, its stops and dodge frames) for every Move and Exchange."""
    out = [(n, moves.frames(m), moves.stops(m), ()) for n, m in moves.MOVES.items()]
    for n, ex in X.EXCHANGES.items():
        stops = sorted({(moves.beat_frame(s.beat), s.point, s.strength) for s in ex.hits} | set(moves.stops(ex.android)))
        out.append((n, [a for a, _g in X.frames(ex)], stops, [moves.beat_frame(d.beat) for d in ex.dodges]))
    return out


SEQS = _sequences()


class TimeWarpTests(unittest.TestCase):
    def test_hold_then_catch_up_to_the_beat(self):
        beats = [0, 15, 29, 44, 58]
        cases = [("one hit", 59, [(15, 1.0)], 15, 3, 29), ("light hit", 59, [(29, 0.2)], 29, 1, 44),
                 ("two hits", 59, [(15, 0.6), (29, 1.0)], 29, 3, 44)]
        for name, n, stops, h, hold, b in cases:
            s = weight.time_warp(n, stops, beats)
            with self.subTest(case=name):
                self.assertEqual(s[0], 0.0)
                self.assertEqual(s[-1], n - 1)
                self.assertEqual(s[h:h + hold + 1], [float(h)] * (hold + 1))
                self.assertEqual(s[b], float(b))
                self.assertTrue(all(y >= x for x, y in zip(s, s[1:])))

    def test_no_room_no_hold(self):
        s = weight.time_warp(20, [(18, 1.0)], [0, 19])
        self.assertEqual(s, [float(f) for f in range(20)])


class FlightTests(unittest.TestCase):
    def test_key_tables_measured_in_the_research(self):
        """Section 1: the key tables brake and speed up in the air, far from -g."""
        for name, low, high in (("leap_slam", -60.0, 40.0), ("burst_rise", -40.0, 40.0)):
            lo, hi = weight.measure(moves.frames(moves.MOVES[name], weighted=False), moves.hip_joint)["air_acc"]
            with self.subTest(move=name):
                self.assertLess(lo, low)
                self.assertGreater(hi, high)

    def test_flight_is_ballistic(self):
        flown = 0
        for name, seq, stops, dodges in SEQS:
            acc = weight.measure(seq, moves.hip_joint, weight.pins(stops, dodges))["air_acc"]
            if acc is None:
                continue
            flown += 1
            with self.subTest(clip=name):
                self.assertLessEqual(abs(acc[0] + weight.G), AIR_TOL)
                self.assertLessEqual(abs(acc[1] + weight.G), AIR_TOL)
        self.assertGreater(flown, 0)


class HitTests(unittest.TestCase):
    def test_hits_hold_their_limb(self):
        for name, seq, stops, _d in SEQS:
            for h, limb, strength in stops:
                if limb not in seq[0]:
                    continue
                with self.subTest(clip=name, frame=h, limb=limb):
                    hold = seq[h:h + weight.hold_frames(strength) + 1]
                    self.assertLessEqual(max(math.dist(p[limb], hold[0][limb]) for p in hold), HOLD_DRIFT_M)

    def test_hits_keep_their_place(self):
        for name, move in moves.MOVES.items():
            seq = moves.frames(move)
            for h, limb, _s in moves.stops(move):
                if limb not in seq[h]:
                    continue
                with self.subTest(move=name, frame=h, limb=limb):
                    self.assertLessEqual(math.dist(seq[h][limb], moves.sample(move, h)[limb]), HIT_TOL_M)


class GroundTests(unittest.TestCase):
    def test_floor_only_pushes(self):
        """Standing, the hips (the research's stand-in for the centre of mass) never fall faster than g: the floor
        pushes, it cannot pull. Not inside the pin windows around Hits nor around flights (research 4: ground
        test). The stomp rebound of the key tables broke this (power_stomp about -97 m/s² at f76f78c)."""
        for name, seq, stops, _d in SEQS:
            skip = weight.hit_windows(stops, weight.PIN_HIT) | {f for t0, t1 in weight.flights(seq)
                                                                for f in range(t0 - 1, t1 + 2)}
            z = [p["hips"][2] for p in seq]
            for f in range(1, len(seq) - 1):
                if f in skip:
                    continue
                with self.subTest(clip=name, frame=f):
                    self.assertGreaterEqual((z[f + 1] - 2 * z[f] + z[f - 1]) * weight.FPS ** 2, -weight.G)


class SpringTests(unittest.TestCase):
    def test_step_response(self):
        """A step from 0 to 1: critically damped settles without overshoot, under-damped overshoots, a positive
        initial response jumps ahead, a negative one starts the wrong way (anticipation)."""
        step = [(0.0,)] * 3 + [(1.0,)] * 57
        cases = [("critical", (3.0, 1.0, 0.0), lambda y: max(y) <= 1.0 + 1e-9 and abs(y[-1] - 1.0) < 0.01),
                 ("under-damped", (3.0, 0.4, 0.0), lambda y: max(y) > 1.05),
                 ("anticipation", (3.0, 0.5, -2.0), lambda y: min(y) < -0.01)]
        for name, (hz, zeta, r), ok in cases:
            y = [v[0] for v in weight.second_order(step, hz, zeta, r)]
            with self.subTest(case=name):
                self.assertTrue(ok(y))

    def test_pins_meet_their_target(self):
        ys = [(0.1 * f,) for f in range(30)]
        target = [(0.0,)] * 30
        out = weight.pin(ys, target, weight._windows([12], 30))
        for f in (0, 12, 29):
            with self.subTest(frame=f):
                self.assertAlmostEqual(out[f][0], 0.0)
        self.assertEqual(out[19], ys[19])

    def test_spring_spares_idles_and_planted_feet(self):
        for name, move in moves.MOVES.items():
            seq, raw = moves.frames(move), moves.frames(move, weighted=False)
            with self.subTest(move=name):
                if move.idle:
                    self.assertEqual(seq, raw)
                for f, (p, q) in enumerate(zip(seq, raw)):
                    for foot in ("foot_l", "foot_r"):
                        if q[foot][2] <= moves.ANKLE_Z + weight.AIR_M and p[foot][2] <= moves.ANKLE_Z + weight.AIR_M:
                            self.assertEqual(p[foot][2], q[foot][2])


class DipTests(unittest.TestCase):
    def test_touch_downs_and_stomps_sink(self):
        for name in ("leap_slam", "burst_rise", "power_stomp"):
            move = moves.MOVES[name]
            seq = moves.frames(move)
            dz = [d[2] for _f, ch, d in weight.dip(seq, lambda f: moves.sample(move, f), moves.stops(move))
                  if ch == "hips"]
            with self.subTest(move=name):
                self.assertLess(min(dz), -0.01)
                self.assertLessEqual(-min(dz), weight.DIP_M[1])


if __name__ == "__main__":
    unittest.main()
