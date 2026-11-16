"""The start check's exit code from its rows (blender/review/start_check.verdict, issue #18), without Blender.
Run: python3 -m unittest discover blender/tests"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "review"))
import start_check as sc  # noqa: E402

ROWS = ("scene", "health.py", "runtime and playback", "bridge", "terrain", "Syphon sender", "preview pixels", "Syphon grab")


def rows(*failed):
    return {n: n not in failed for n in ROWS}


class VerdictTests(unittest.TestCase):
    def test_verdict(self):
        cases = [
            ((), 0),
            (("Syphon sender", "preview pixels", "Syphon grab"), 3),     # the window that does not draw (#18)
            (("Syphon sender",), 3),
            (("preview pixels", "Syphon grab"), 1),                       # frames move, the picture is wrong
            (("Syphon grab",), 1),
            (("Syphon sender", "health.py"), 1),                          # the runtime is not clean: no reopen
            (("Syphon sender", "runtime and playback"), 1),
            (("terrain",), 1),
        ]
        for failed, code in cases:
            with self.subTest(failed=failed):
                self.assertEqual(sc.verdict(rows(*failed)), code)


if __name__ == "__main__":
    unittest.main()
