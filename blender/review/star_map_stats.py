"""Where the star map's light sits: the share of the sky's drawn light (the build's lum^2 gain) that comes from faint
texels (the Milky Way's diffuse glow and the faint field) against bright points, for a few luminance thresholds.
Sizes the /vj/nebula reader (round 9). Headless, no scene:

    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python blender/review/star_map_stats.py

Prints one JSON line starting with STAR_STATS."""
import json
import os

import bpy
import numpy as np

STAR_BLACK, STAR_K = 0.002, 3.0          # as in build_planet.py
HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "..", "scenes", "planet_proto", "starmaps", "starmap_2020_8k.exr")

img = bpy.data.images.load(PATH)
w, h = img.size
px = np.empty(w * h * 4, dtype=np.float32)
img.pixels.foreach_get(px)
rgb = np.maximum(px.reshape(h, w, 4)[:, :, :3] - STAR_BLACK, 0.0)
lum = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
drawn = lum * lum * STAR_K                    # luminance of v_ * gain
total = float(drawn.sum())
out = {"size": [w, h], "lum_percentiles": {str(p): float(np.percentile(lum, p)) for p in (50, 90, 99, 99.9)},
       "drawn_mean": total / lum.size, "faint_share": {}}
for t in (0.01, 0.02, 0.05, 0.1, 0.2):
    out["faint_share"][str(t)] = float(drawn[lum < t].sum()) / total
# the galactic band against the sky beside it: rows of the map sorted by their mean, top tenth vs bottom half
col_mean = drawn.mean(axis=0)
out["column_mean_max_over_median"] = float(col_mean.max() / np.median(col_mean))
print("STAR_STATS " + json.dumps(out))
