"""manifest_complete.py PACKAGE: keep in the Manifest only the Moves whose Clips are complete on every Angle
(review/clip_complete.py), so a render cut short still yields a valid package, and record each Clip's quality
(<package>/quality/<clip>, "high" when missing) and the package's ("low", "high" or "mixed"). Prints what it dropped."""
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
for c in man["clips"]:
    q = os.path.join(pkg, "quality", c["id"])
    c["quality"] = open(q).read().strip() if os.path.isfile(q) else "high"
qs = {c["quality"] for c in man["clips"]}
man["quality"] = qs.pop() if len(qs) == 1 else "mixed"
json.dump(man, open(path, "w"), indent=1)
print("manifest: kept %d Moves, dropped %s" % (len(keep), ", ".join(sorted(moves - keep)) or "none"))
