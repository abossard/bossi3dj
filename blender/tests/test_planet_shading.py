"""The planet's shading rules that build_planet.py applies (issue #25), without Blender: which materials keep /vj/hue
(is_sky) and the haze's distance from height (FOG_D, FOG_D_RISE, planetize_fog). build_planet imports bpy and builds on
import, so its constants and is_sky are read from its source.
Run: python3 -m unittest discover blender/tests"""
import ast
import math
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "..", "scenes", "planet_proto", "build_planet.py")).read()
TREE = ast.parse(SRC)
NS = {}
for node in TREE.body:
    if isinstance(node, ast.Assign) and any(getattr(t, "id", None) in ("SKY_MATERIALS", "SKY_PARTS", "FOG_D", "FOG_D_RISE")
                                            for t in node.targets):
        exec(compile(ast.Module([node], []), "build_planet.py", "exec"), NS)
    if isinstance(node, ast.FunctionDef) and node.name == "is_sky":
        exec(compile(ast.Module([node], []), "build_planet.py", "exec"), NS)
FUNCS = {n.name: n for n in TREE.body if isinstance(n, ast.FunctionDef)}


def haze(dist, eye):
    """VJ_Fog's haze share at view distance dist m from a camera eye m over the sea, as planetize_fog wires it."""
    d = NS["FOG_D"] + NS["FOG_D_RISE"][1] * max(eye - NS["FOG_D_RISE"][0], 0.0)
    return 1.0 - math.exp(-(dist / d) ** 2)


class SkyTests(unittest.TestCase):
    def test_is_sky(self):
        cases = [("world-less sky bodies", n, True) for n in ("Atmosphere", "Sun", "Moon", "Stars", "Nebula", "Meteor Trail")]
        cases += [("land, water and props keep /vj/hue", n, False) for n in
                  ("Terrain", "Sea", "Sea Backdrop", "Pyramid", "Pyramid Body", "Pyramid Edge", "Globe", "Palm", "Flamingo",
                   "Fog")]
        for why, name, sky in cases:
            with self.subTest(name=name, why=why):
                self.assertEqual(NS["is_sky"](name), sky)


class HazeTests(unittest.TestCase):
    def test_haze(self):
        cases = [  # dist m, eye m, least, most
            (6500.0, 300.0, 1.0 - math.exp(-1.0) - 1e-9, 1.0 - math.exp(-1.0) + 1e-9),   # on the ground: as before
            (5500.0 / math.sin(math.radians(35.0)), 5500.0, 0.0, 0.2),                   # 5.5 km up at 35 deg: was 0.89
            (4000.0 / math.sin(math.radians(20.0)), 4000.0, 0.0, 0.5),                   # 4 km up at 20 deg: was 0.96
        ]
        for dist, eye, lo, hi in cases:
            with self.subTest(dist=round(dist), eye=eye):
                self.assertGreaterEqual(haze(dist, eye), lo)
                self.assertLessEqual(haze(dist, eye), hi)

    def test_planetize_fog_wires_it(self):
        calls = {n.func.id for n in ast.walk(FUNCS["planetize_fog"]) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name)}
        self.assertIn("fog_distance", calls)


if __name__ == "__main__":
    unittest.main()
