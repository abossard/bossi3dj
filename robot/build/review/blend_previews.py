"""Pull the preview images out of a .blend without Blender: the file thumbnail (TEST block) and every 256 px ID
preview (asset-browser previews of objects, collections, materials), named after the ID that owns them.

    python -I robot/build/review/blend_previews.py FILE.blend OUT_DIR [--max N]

Reads block headers as data and nothing else; a zstd-compressed .blend (Blender 3.0+) is streamed through `zstd -dc`.
Only 64-bit little-endian files with the classic 12-byte header (Blender 2.80 to 4.x) are handled. OUT_DIR gets
thumb.png, prev_NNN.png and index.json ([{file, id_code, name}])."""
import json
import os
import re
import struct
import subprocess
import sys

from PIL import Image

PREV_SIZES = {256 * 256 * 4: 256, 128 * 128 * 4: 128}
ID_NAME = re.compile(rb"(OB|GR|MA|ME|NT|WO|SC|IM|AC)([\x20-\x7e]{1,63})\x00")


def open_blend(path):
    with open(path, "rb") as f:
        magic = f.read(4)
    if magic == b"\x28\xb5\x2f\xfd":
        proc = subprocess.Popen(["zstd", "-dc", "--", path], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        return proc.stdout, False
    return open(path, "rb"), True


def skip(f, n, seekable):
    if seekable:
        f.seek(n, 1)
        return
    while n > 0:
        chunk = f.read(min(n, 1 << 20))
        if not chunk:
            raise EOFError
        n -= len(chunk)


def rgba_image(buf, w, h):
    img = Image.frombytes("RGBA", (w, h), buf).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    return img


def informative(img):
    lo, hi = img.convert("L").getextrema()
    return hi - lo > 12


def main():
    path, out = sys.argv[1], sys.argv[2]
    limit = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 400
    os.makedirs(out, exist_ok=True)
    f, seekable = open_blend(path)
    head = f.read(12)
    if not head.startswith(b"BLENDER-v"):
        sys.exit(f"unsupported header {head!r}")
    owner, index, n = ("", ""), [], 0
    while True:
        bh = f.read(24)
        if len(bh) < 24:
            break
        code, size = bh[:4], struct.unpack("<i", bh[4:8])[0]
        if code == b"ENDB":
            break
        if code[2:] == b"\x00\x00" and code[:2].isalpha():
            data = f.read(min(size, 160))
            m = ID_NAME.search(data)
            if m:
                owner = (m.group(1).decode(), m.group(2).decode("ascii", "replace"))
            skip(f, size - len(data), seekable)
            continue
        if code == b"TEST":
            data = f.read(size)
            w, h = struct.unpack("<ii", data[:8])
            if w * h * 4 == size - 8:
                rgba_image(data[8:], w, h).save(os.path.join(out, "thumb.png"))
                index.append({"file": "thumb.png", "id_code": "TEST", "name": "file thumbnail"})
            continue
        if code == b"DATA" and size in PREV_SIZES and n < limit:
            data = f.read(size)
            s = PREV_SIZES[size]
            img = rgba_image(data, s, s)
            if informative(img):
                name = f"prev_{n:03d}.png"
                img.save(os.path.join(out, name))
                index.append({"file": name, "id_code": owner[0], "name": owner[1]})
                n += 1
            continue
        skip(f, size, seekable)
    with open(os.path.join(out, "index.json"), "w") as fo:
        json.dump(index, fo, indent=1)
    print(json.dumps({"blend": path, "previews": n, "thumb": any(i["id_code"] == "TEST" for i in index)}))


if __name__ == "__main__":
    main()
