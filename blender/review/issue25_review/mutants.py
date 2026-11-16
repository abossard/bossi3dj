"""Issue #25: mutants of path_camera.py that test_path_blends.py must catch (the Opus review of 5367861..0de533f).
    python3 blender/review/issue25_review/mutants.py      Each prints caught or SURVIVED.
The guard's change branch was removed instead: redundant.py found no program where it mattered."""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
PC = os.path.join(ROOT, "blender", "scenes", "path_camera.py")
MUTANTS = {
    "land max 1.0": ("BLEND_LAND_MAX = 0.8", "BLEND_LAND_MAX = 1.0"),
    "no ramp at the start": ("min(tr.t, max(tr.d - tr.t, 0.0))", "max(tr.d - tr.t, 0.0)"),
    "heading without the ends": ("head = fl.tangent(u, fl.add(fwd, ends, 0.25))", "head = fl.tangent(u, fwd)"),
}
src = open(PC).read()
try:
    for name, (a, b) in MUTANTS.items():
        assert src.count(a) == 1, name
        open(PC, "w").write(src.replace(a, b))
        r = subprocess.run([sys.executable, "-B", "-m", "unittest", "blender/tests/test_path_blends.py"], cwd=ROOT,
                           capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        print("%-34s %s" % (name, "caught" if r.returncode else "SURVIVED"))
finally:
    open(PC, "w").write(src)
