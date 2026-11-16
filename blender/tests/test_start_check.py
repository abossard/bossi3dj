"""The start check's exit code from its rows (blender/review/start_check.verdict, issue #18), without Blender.
Run: python3 -m unittest discover blender/tests"""
import ast
import inspect
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "review"))
import start_check as sc  # noqa: E402


def row_names():
    """The names main() gives its rows: the first argument of every row(...) call, a literal or a module constant."""
    out = []
    for n in ast.walk(ast.parse(inspect.getsource(sc.main))):
        if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "row":
            a = n.args[0]
            out.append(a.value if isinstance(a, ast.Constant) else getattr(sc, a.id))
    return tuple(dict.fromkeys(out))


ROWS = row_names()


def rows(*failed):
    return {n: n not in failed for n in ROWS}


class VerdictTests(unittest.TestCase):
    def test_rows_hold_the_drawing(self):
        self.assertTrue(set(sc.DRAWING) <= set(ROWS))
        self.assertGreater(len(ROWS), len(sc.DRAWING))

    def test_verdict(self):
        drawing = tuple(sc.DRAWING)
        other = next(n for n in ROWS if n not in drawing)
        cases = [
            ((), True, False, 0),
            (drawing, True, False, 3),                  # the window that does not draw (#18)
            (drawing, False, False, 1),                 # the counter moved on its second sample: a stall
            (drawing, True, True, 1),                   # the screen is locked: a reopen cannot fix it
            ((sc.SENDER,), True, False, 1),             # pixels and grab pass: a GPU stall, not a dead window
            ((sc.PREVIEW, sc.GRAB), True, False, 1),    # frames move, the picture is wrong
            (drawing + (other,), True, False, 1),       # something else failed too
        ]
        for failed, still, locked, code in cases:
            with self.subTest(failed=failed, still_stuck=still, locked=locked):
                self.assertEqual(sc.verdict(rows(*failed), still, locked), code)


if __name__ == "__main__":
    unittest.main()
