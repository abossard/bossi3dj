"""manifest_complete.py PACKAGE: keep in the Manifest only the Moves whose Clips are complete on every Angle
(review/clip_complete.py), so a render cut short still yields a valid package. Prints what it dropped."""
import json
import os
import subprocess
import sys

pkg = sys.argv[1]
path = os.path.join(pkg, "manifest.json")
man = json.load(open(path))
here = os.path.dirname(os.path.abspath(__file__))
done = {c["id"] for c in man["clips"] if subprocess.run(
    [sys.executable, os.path.join(here, "clip_complete.py"), pkg, c["id"], str(c["frames"])]).returncode == 0}
moves = {c["move"] for c in man["clips"]}
keep = {m for m in moves if all(c["id"] in done for c in man["clips"] if c["move"] == m)}
man["clips"] = [c for c in man["clips"] if c["move"] in keep]
json.dump(man, open(path, "w"), indent=1)
print("manifest: kept %d Moves, dropped %s" % (len(keep), ", ".join(sorted(moves - keep)) or "none"))
