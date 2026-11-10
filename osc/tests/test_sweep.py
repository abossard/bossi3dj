"""osc/sweep.py: the plan, the encoding and the walk, with no socket. Run: python3 -m unittest discover osc/tests"""
import io
import os
import socket
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import contract  # noqa: E402
import lab  # noqa: E402
import sweep  # noqa: E402

ROWS = contract.load()
BY = contract.by_address(ROWS)


class PlanTests(unittest.TestCase):
    def test_a_float_or_index_walks_min_default_max(self):
        for r in ROWS:
            if r["kind"] == "trigger":
                continue
            with self.subTest(address=r["address"]):
                steps = sweep.plan([r], 3.0)
                self.assertEqual([(s.label, s.value) for s in steps], [("min", r["min"]), ("default", r["default"]), ("max", r["max"])])
                self.assertAlmostEqual(sum(s.hold for s in steps), 3.0)

    def test_a_trigger_fires_once_with_its_strength(self):
        cases = [("/vj/shock", 1.0, 1.0), ("/vj/shock", 1.4, 1.4), ("/vj/shock", 9.0, 1.5), ("/vj/meteor", 1.4, 1.0), ("/vj/hit", 1.0, 1.0)]
        for address, strength, want in cases:
            with self.subTest(address=address, strength=strength):
                (step,) = sweep.plan([BY[address]], 3.0, strength)
                self.assertEqual((step.label, step.value, step.trigger), ("fire", want, True))

    def test_every_row_is_walked(self):
        self.assertEqual({s.address for s in sweep.plan(ROWS)}, set(BY))


class EncodingTests(unittest.TestCase):
    def test_message_decodes_to_one_float(self):
        for address, v in (("/vj/level", 0.5), ("/vj/fog_height", 0.42), ("/vj/shock", 1.4), ("/vj/cam", 10.0)):
            with self.subTest(address=address, v=v):
                data = sweep.osc_message(address, v)
                self.assertEqual(len(data) % 4, 0)
                a, tags, args = lab.parse_message(data)
                self.assertEqual((a, tags), (address, "f"))
                self.assertAlmostEqual(args[0], v, places=6)


class RunTests(unittest.TestCase):
    def walk(self, rows, rate=10.0, seconds=3.0):
        sent, waited, said = [], [], []
        defaults = {r["address"]: r["default"] for r in rows}
        sweep.run(sweep.plan(rows, seconds), defaults, lambda a, v: sent.append((a, v)), waited.append, said.append, rate)
        return sent, waited, said

    def test_values_are_held_at_the_rate_and_the_default_comes_back(self):
        sent, waited, said = self.walk([BY["/vj/fog_height"]])
        self.assertEqual(sent[0], ("/vj/fog_height", 0))
        self.assertEqual(sent[-1], ("/vj/fog_height", 0.42))
        self.assertEqual(sent.count(("/vj/fog_height", 1)), 10)
        self.assertEqual(len(said), 3)
        self.assertAlmostEqual(sum(waited), 3.0)

    def test_a_trigger_rises_and_falls(self):
        sent, waited, said = self.walk([BY["/vj/shock"]])
        self.assertEqual([v for _, v in sent], [0.0, 1.0, 0.0, 0.0])
        self.assertAlmostEqual(sum(waited), 3.0)

    def test_every_address_returns_to_its_default_before_the_next(self):
        sent, _, _ = self.walk(ROWS, rate=1.0, seconds=3.0)
        changes = [i for i in range(1, len(sent)) if sent[i][0] != sent[i - 1][0]]
        for i in changes:
            with self.subTest(address=sent[i - 1][0]):
                self.assertEqual(sent[i - 1][1], BY[sent[i - 1][0]]["default"])

    def test_interrupt_leaves_the_default(self):
        sent = []

        def boom(_):
            raise KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            sweep.run(sweep.plan([BY["/vj/level"]]), {"/vj/level": 0.5}, lambda a, v: sent.append((a, v)), boom, lambda _: None)
        self.assertEqual(sent[-1], ("/vj/level", 0.5))


class MainTests(unittest.TestCase):
    def test_dry_run_prints_the_whole_walk_and_opens_no_socket(self):
        out = io.StringIO()
        with mock.patch.object(socket, "socket", side_effect=AssertionError("a dry run opened a socket")), redirect_stdout(out):
            self.assertEqual(sweep.main(["--dry-run"]), 0)
        lines = out.getvalue().splitlines()
        walked = {line.split()[0] for line in lines[1:]}
        self.assertEqual(walked, set(BY))
        self.assertEqual(len(lines) - 1, len(sweep.plan(ROWS)))

    def test_only_filters_the_addresses(self):
        out = io.StringIO()
        with redirect_stdout(out):
            sweep.main(["--dry-run", "--only", "^/vj/fog"])
        walked = {line.split()[0] for line in out.getvalue().splitlines()[1:]}
        self.assertEqual(walked, {a for a in BY if a.startswith("/vj/fog")})

    def test_targets(self):
        cases = [("relay", ("127.0.0.1", 9200)), ("blender", ("127.0.0.1", 9201)), ("godot", ("127.0.0.1", 9202)),
                 ("127.0.0.1:19202", ("127.0.0.1", 19202)), (":19202", ("127.0.0.1", 19202))]
        for text, want in cases:
            with self.subTest(target=text):
                self.assertEqual(sweep.parse_target(text, "127.0.0.1"), want)


if __name__ == "__main__":
    unittest.main()
