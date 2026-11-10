#!/usr/bin/env python3
"""Pixel statistics of PNG files, numbers only, no image is looked at.

    python3 tools/png_stats.py a.png [b.png ...]

Per file: size, mean RGB, luma mean and variance, share of lit pixels (luma above 30/255 of the
sum rule used by `magicproj.py grab`: r+g+b > 30), share of near-black and blown-out pixels, and the
3x3 grid of mean luma (rows top first, as stored in the file), and `flat_black_bottom`: the share of
the lowest 30% of rows where every channel is 2 or less (the ground; a frame passes below 0.02). With two or more files it adds the
largest difference of the 3x3 grids against the first, and the same with the grid rows reversed, so
a flipped frame shows. Reads 8-bit grey, RGB and RGBA PNGs, standard library only.
"""
import json
import struct
import sys
import zlib


def read_png(path):
    with open(path, "rb") as f:
        data = f.read()
    pos, idat, w, h, ct = 8, b"", 0, 0, 2
    while pos < len(data):
        n, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        if kind == b"IHDR":
            w, h, depth, ct = struct.unpack(">IIBB", body[:10])
            assert depth == 8, "only 8-bit PNGs"
        elif kind == b"IDAT":
            idat += body
        pos += 12 + n
    ch = {0: 1, 2: 3, 6: 4}[ct]
    raw = zlib.decompress(idat)
    stride = w * ch
    rows, prev = [], bytearray(stride)
    for y in range(h):
        o = y * (stride + 1)
        f, line = raw[o], bytearray(raw[o + 1:o + 1 + stride])
        for i in range(stride):
            a = line[i - ch] if i >= ch else 0
            b = prev[i]
            c = prev[i - ch] if i >= ch else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line)
        prev = line
    return w, h, ch, rows


def stats(path):
    w, h, ch, rows = read_png(path)
    step = max(1, int((w * h / 90000) ** 0.5))
    n = lit = dark = blown = low = low_black = 0
    acc, s1, s2 = [0, 0, 0], 0.0, 0.0
    grid = [[[0.0, 0] for _ in range(3)] for _ in range(3)]
    for y in range(0, h, step):
        row = rows[y]
        for x in range(0, w, step):
            if ch == 1:
                r = g = b = row[x]
            else:
                r, g, b = row[x * ch], row[x * ch + 1], row[x * ch + 2]
            l = 0.2126 * r + 0.7152 * g + 0.0722 * b
            n += 1
            acc[0] += r
            acc[1] += g
            acc[2] += b
            s1 += l
            s2 += l * l
            lit += (r + g + b) > 30
            dark += l < 8
            blown += l > 247
            if y >= h * 0.7:
                low += 1
                low_black += max(r, g, b) <= 2
            cell = grid[min(2, 3 * y // h)][min(2, 3 * x // w)]
            cell[0] += l
            cell[1] += 1
    mean = s1 / n
    return {
        "file": path, "size": [w, h],
        "mean_rgb": [round(a / n, 1) for a in acc],
        "luma_mean": round(mean, 1), "luma_variance": round(s2 / n - mean * mean, 1),
        "lit": round(lit / n, 3), "near_black": round(dark / n, 3), "blown_out": round(blown / n, 3),
        "flat_black_bottom": round(low_black / max(low, 1), 3),
        "grid_luma": [[round(c[0] / c[1], 1) for c in row] for row in grid],
    }


def grid_diff(a, b):
    return round(max(abs(x - y) for ra, rb in zip(a, b) for x, y in zip(ra, rb)), 1)


def main(paths):
    out = [stats(p) for p in paths]
    for o in out[1:]:
        o["max_grid_diff_vs_first"] = grid_diff(out[0]["grid_luma"], o["grid_luma"])
        o["max_grid_diff_vs_first_rows_reversed"] = grid_diff(out[0]["grid_luma"][::-1], o["grid_luma"])
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
