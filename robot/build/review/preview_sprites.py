"""Pack the previews that blend_previews.py pulled from a .blend into one sprite sheet for the Robot Asset Lab page.

    python -I robot/build/review/preview_sprites.py PREVIEW_DIR OUT_PREFIX [--match TEXT] [--code OB] [--tile 160]
        [--cols 10] [--strip TEXT]

PREVIEW_DIR holds index.json from blend_previews.py. Entries whose ID code equals --code and whose name contains
--match are packed in name order (natural sort) onto a black sheet. Writes OUT_PREFIX.jpg and OUT_PREFIX.json
({tile, cols, items: [names]})."""
import json
import math
import os
import re
import sys

from PIL import Image


def natural(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def main():
    args = sys.argv[1:]
    src, out = args[0], args[1]
    opt = {args[i][2:]: args[i + 1] for i in range(2, len(args) - 1, 2)}
    tile, cols = int(opt.get("tile", 160)), int(opt.get("cols", 10))
    match, code, strip = opt.get("match", ""), opt.get("code", "OB"), opt.get("strip", "")
    with open(os.path.join(src, "index.json")) as f:
        idx = [i for i in json.load(f) if i["id_code"] == code and match in i["name"]]
    idx.sort(key=lambda i: natural(i["name"]))
    rows = math.ceil(len(idx) / cols)
    sheet = Image.new("RGB", (cols * tile, rows * tile), (0, 0, 0))
    for k, it in enumerate(idx):
        im = Image.open(os.path.join(src, it["file"])).convert("RGBA")
        bg = Image.new("RGBA", im.size, (0, 0, 0, 255))
        im = Image.alpha_composite(bg, im).convert("RGB").resize((tile, tile), Image.Resampling.LANCZOS)
        sheet.paste(im, ((k % cols) * tile, (k // cols) * tile))
    sheet.save(out + ".jpg", quality=84, optimize=True, progressive=True)
    with open(out + ".json", "w") as f:
        json.dump({"tile": tile, "cols": cols, "items": [i["name"].replace(strip, "").strip() for i in idx]}, f, indent=1)
    print(json.dumps({"out": out, "items": len(idx), "sheet": list(sheet.size)}))


if __name__ == "__main__":
    main()
