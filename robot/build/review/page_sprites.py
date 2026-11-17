"""Pack brochure page renders (e.g. a Geo-Scatter biome PDF, one preview per page) into one sprite sheet for the
Robot Asset Lab page, cutting the branding strip off the left edge.

    python -I robot/build/review/page_sprites.py PAGE_DIR OUT_PREFIX --pages 2-9 [--crop-left 32] [--width 668]
        [--cols 2]

Reads PAGE_DIR/page_NN.jpg as images. Every tile keeps the page's aspect after the crop and is scaled to --width.
Writes OUT_PREFIX.jpg (tiles in page order, left to right) and OUT_PREFIX.json ({tw, th, cols, pages})."""
import json
import math
import os
import sys

from PIL import Image


def main():
    args = sys.argv[1:]
    src, out = args[0], args[1]
    opt = {args[i][2:]: args[i + 1] for i in range(2, len(args) - 1, 2)}
    a, b = (int(v) for v in opt["pages"].split("-"))
    crop, width, cols = int(opt.get("crop-left", 32)), int(opt.get("width", 668)), int(opt.get("cols", 2))
    pages = list(range(a, b + 1))
    tiles = []
    for p in pages:
        im = Image.open(os.path.join(src, f"page_{p:02d}.jpg")).convert("RGB")
        im = im.crop((crop, 0, im.width, im.height))
        tiles.append(im.resize((width, round(im.height * width / im.width)), Image.Resampling.LANCZOS))
    tw, th = tiles[0].size
    rows = math.ceil(len(tiles) / cols)
    sheet = Image.new("RGB", (cols * tw, rows * th))
    for k, t in enumerate(tiles):
        sheet.paste(t.resize((tw, th)), ((k % cols) * tw, (k // cols) * th))
    sheet.save(out + ".jpg", quality=84, optimize=True, progressive=True)
    with open(out + ".json", "w") as f:
        json.dump({"tw": tw, "th": th, "cols": cols, "pages": pages}, f)
    print(json.dumps({"out": out, "tiles": len(tiles), "sheet": list(sheet.size)}))


if __name__ == "__main__":
    main()
