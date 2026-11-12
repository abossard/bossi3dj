"""Turns the frames of readme_pairs.py into the README's pictures. python readme_assemble.py PAIRS_DIR [--scene planet|island]
Reads PAIRS_DIR/pairs.json (readme_pair_check.py). Writes into docs/images/readme/osc/ (JPEG, quality 88):
  <name>-blender.jpg    low | high side by side, 2 x 480 px wide, for every pair that counted (name = address without /vj/)
  cam-<scene>-<N>.jpg   one 480 px picture per camera: of its phases the one with the most picture in the lower half
  cam-blender.jpg       a 4 x 3 strip of the planet's cameras (the /vj/cam row)
and the hero frames docs/images/readme/planet-*.jpg when PAIRS_DIR has extras. Needs ImageMagick.
With --flight FRAME instead of PAIRS_DIR: a Flight frame of flight_grabs.py as the gallery picture, cam-planet-11 and the strip."""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OSC = os.path.join(ROOT, "docs", "images", "readme", "osc")
HERO = os.path.join(ROOT, "docs", "images", "readme")
if "--flight" in sys.argv:       # python readme_assemble.py --flight FRAME: a full-size Flight frame (flight_grabs.py) as the
    # gallery picture planet-flight-<stage>.jpg (960 px), the Flight shot's camera picture cam-planet-11.jpg and the strip
    src = sys.argv[sys.argv.index("--flight") + 1]
    stage = os.path.basename(src).split("_")[0]
    subprocess.run(["magick", src, "-resize", "960x", "-quality", "88", os.path.join(HERO, "planet-flight-%s.jpg" % stage)], check=True)
    subprocess.run(["magick", src, "-resize", "480x", "-quality", "88", os.path.join(OSC, "cam-planet-11.jpg")], check=True)
    subprocess.run(["magick", "montage", *[os.path.join(OSC, "cam-planet-%d.jpg" % n) for n in range(12)], "-tile", "4x3",
                    "-geometry", "240x135+2+2", "-background", "black", "-quality", "88", os.path.join(OSC, "cam-blender.jpg")], check=True)
    print("wrote planet-flight-%s.jpg, cam-planet-11.jpg, cam-blender.jpg" % stage)
    sys.exit(0)
d = sys.argv[1]
scene = sys.argv[sys.argv.index("--scene") + 1] if "--scene" in sys.argv else "planet"
res = json.load(open(os.path.join(d, "pairs.json")))
os.makedirs(OSC, exist_ok=True)


def magick(*args):
    subprocess.run(["magick", *args], check=True)


made = []
for p in res["pairs"]:
    if p["verdict"] != "pair":
        continue
    name = p["key"][len("vj_"):]
    f = lambda t: os.path.join(d, "%s__%s.ppm" % (p["base"], t))
    out = os.path.join(OSC, "%s-blender.jpg" % name)
    magick(f("lo"), "-resize", "480x", f("hi"), "-resize", "480x", "+append", "-quality", "88", out)
    made.append(out)
# phases picked by the shot-reviewer on the contact sheets (otherwise the frame with the most picture in its lower half)
PICKED = {"planet": {4: 3, 11: 0}, "island": {4: 1, 5: 2, 6: 2}}.get(scene, {})
best = {}
for fr in res["frames"]:
    m = re.match(r"cam__(\d+)__p(\d+)\.ppm", fr["file"])
    if m and int(m.group(1)) in PICKED:
        if PICKED[int(m.group(1))] == int(m.group(2)):
            best[int(m.group(1))] = dict(fr, phase=int(m.group(2)))
        continue
    if m and (int(m.group(1)) not in best or fr["lower_sd"] > best[int(m.group(1))]["lower_sd"]):
        best[int(m.group(1))] = dict(fr, phase=int(m.group(2)))
for n, fr in sorted(best.items()):
    out = os.path.join(OSC, "cam-%s-%d.jpg" % (scene, n))
    magick(os.path.join(d, fr["file"]), "-resize", "480x", "-quality", "88", out)
    made.append(out)
if scene == "planet" and len(best) == 12:
    tiles = [os.path.join(OSC, "cam-planet-%d.jpg" % n) for n in range(12)]
    out = os.path.join(OSC, "cam-blender.jpg")
    magick("montage", *tiles, "-tile", "4x3", "-geometry", "240x135+2+2", "-background", "black", "-quality", "88", out)
    made.append(out)
print("wrote %d pictures" % len(made))
print("cameras:", {n: "p%d" % fr["phase"] for n, fr in sorted(best.items())})
