"""The handbook's generated blocks follow the show project and the contract. Run: python3 -m unittest discover magic/tests"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import magic_manual as manual  # noqa: E402
import synthwave_magic as sm  # noqa: E402


class HandbookTests(unittest.TestCase):
    def test_generated_blocks_are_current(self):
        self.assertEqual(manual.stale(), [], "run: python3 magic/magic_manual.py sync")

    def test_one_table_row_per_address(self):
        rows = manual.render().splitlines()[2:]
        self.assertEqual(len(rows), len(sm.CONTRACT))
        for line, address in zip(rows, sm.CONTRACT):
            with self.subTest(address=address):
                self.assertTrue(line.startswith("| `%s` |" % address))

    def test_every_path_and_target_is_listed_by_value_and_name(self):
        text = manual.render_camera()
        for address in ("/vj/path", "/vj/target", "/vj/height"):
            for stop in sm.CONTRACT[address]["stops"]:
                with self.subTest(address=address, stop=stop["name"]):
                    self.assertIn("| %g | %s |" % (stop["wire"], stop["name"]), text)


if __name__ == "__main__":
    unittest.main()
