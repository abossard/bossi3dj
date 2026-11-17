"""Make a browsable material library of a texture pack: one sprite sheet of every base-colour map, plus each
material's mean colour, brightest-tenth colour and an emissive guess, for the Robot Asset Lab page.

    python -I robot/build/review/material_library.py PACK_TEXTURE_DIR OUT_PREFIX [--tile 128] [--cols 10]
        [--suffix _basecolor] [--strip KB3D_MTM_]

Reads PNG/TIF files as images and nothing else. Writes OUT_PREFIX.jpg (tiles in name order, left to right) and
OUT_PREFIX.json ({tile, cols, materials: [{name, mean, bright, emissive}]}). A material counts as emissive when the
pack ships an emission map for it or its name says light, neon, emis, holo, glow or screen."""
import json
import math
import os
import re
import sys

from PIL import Image, ImageStat

EMISSIVE = re.compile(r"(light|neon|emis|holo|glow|screen)", re.I)


def main():
    args = sys.argv[1:]
    src, out = args[0], args[1]
    opt = {args[i][2:]: args[i + 1] for i in range(2, len(args) - 1, 2)}
    tile, cols = int(opt.get("tile", 128)), int(opt.get("cols", 10))
    suffix, strip = opt.get("suffix", "_basecolor"), opt.get("strip", "")
    files = sorted(f for f in os.listdir(src) if os.path.splitext(f)[0].lower().endswith(suffix.lower()))
    names = set(os.listdir(src))
    rows = math.ceil(len(files) / cols)
    sheet = Image.new("RGB", (cols * tile, rows * tile), (12, 12, 14))
    mats = []
    for i, f in enumerate(files):
        im = Image.open(os.path.join(src, f))
        im.draft("RGB", (tile * 2, tile * 2))
        im = im.convert("RGB")
        im.thumbnail((tile * 4, tile * 4))
        stat = ImageStat.Stat(im)
        small = im.resize((tile, tile), Image.Resampling.LANCZOS)
        px = sorted(small.getdata(), key=sum)
        top = px[int(len(px) * 0.9):]
        bright = [round(sum(p[k] for p in top) / len(top)) for k in range(3)]
        sheet.paste(small, ((i % cols) * tile, (i // cols) * tile))
        stem = os.path.splitext(f)[0]
        base = stem[: len(stem) - len(suffix)]
        has_emit = any(n.startswith(base) and "emission" in n.lower() for n in names)
        mats.append({"name": base.replace(strip, "").strip(" _"), "mean": [round(c) for c in stat.mean[:3]],
                     "bright": bright, "emissive": bool(has_emit or EMISSIVE.search(base))})
    sheet.save(out + ".jpg", quality=84, optimize=True, progressive=True)
    with open(out + ".json", "w") as fo:
        json.dump({"tile": tile, "cols": cols, "materials": mats}, fo, indent=1)
    print(json.dumps({"src": src, "materials": len(mats), "sheet": list(sheet.size)}))


if __name__ == "__main__":
    main()
