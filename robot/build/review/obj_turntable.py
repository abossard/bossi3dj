"""Render turntable sprite sheets of a character OBJ without Blender: a numpy and Pillow painter's-algorithm renderer.

    python -I robot/build/review/obj_turntable.py MODEL.obj OUT_DIR --looks pack,foundry,parts [--frames 24]
        [--size 420x480] [--skip FLOOR,ENV] [--turn 180] [--alpha 1] [--mat body=ceramic,plastic=graphite,...]

The OBJ is read as data. Each look writes OUT_DIR/<look>.jpg, a sheet of FRAMES views turning 360 degrees
(6 columns; frame 0 faces the camera once --turn degrees fix a model that faces away), and OUT_DIR/info.json holds the frame size, grid, part groups with their
colours in the parts look, triangle counts and the model's height. Looks:
  pack     neutral studio light, materials as the pack's own thumbnail shows them
  foundry  the Chrome Foundry rules: brushed steel that keeps light, sodium key, molten rim from below, amber visor
  parts    every part group in its own colour, the parts pulled apart from the body centre (exploded view)
With --alpha 1 the sheets are transparent WebP (shadow kept) for compositing over other plates.
Materials are matched by the start of their MTL name to a preset with --mat; unknown names fall back to graphite."""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

PRESETS = {  # albedo, metal 0..1, gloss 0..1, emissive
    "ceramic": ((0.86, 0.86, 0.84), 0.05, 0.55, None),
    "graphite": ((0.11, 0.115, 0.125), 0.35, 0.5, None),
    "dark": ((0.05, 0.05, 0.055), 0.2, 0.35, None),
    "chrome": ((0.75, 0.76, 0.78), 1.0, 0.85, None),
    "gunmetal": ((0.30, 0.31, 0.33), 0.8, 0.6, None),
    "glow": ((0.1, 0.1, 0.1), 0.0, 0.2, (0.35, 0.85, 1.0)),
}
FOUNDRY = {"ceramic": "steel", "graphite": "iron", "dark": "iron", "chrome": "steel", "gunmetal": "steel", "glow": "visor"}
FOUNDRY_MATS = {
    "steel": ((0.80, 0.80, 0.81), 0.85, 0.6, None),
    "iron": ((0.24, 0.23, 0.22), 0.6, 0.4, None),
    "visor": ((0.1, 0.1, 0.1), 0.0, 0.2, (1.0, 0.62, 0.2)),
}
GROUP_COLOURS = ["#ffb04a", "#5fe0d2", "#ff5a4e", "#9fb8ff", "#f2e35b", "#c58bff", "#7be37b", "#ff8fc8",
                 "#4fa8ff", "#ffd6a0", "#3fd9ff", "#e0e0e0", "#ff7a22", "#a3ffcf", "#b7a0ff", "#ffa3a3"]


def load_obj(path, skip):
    verts, norms, faces, fnorm_idx, fmat, fpart = [], [], [], [], [], []
    mat, part, mats, parts = "", "", [], []
    skipping = False
    with open(path, "r", errors="replace") as f:
        for line in f:
            if line.startswith("v "):
                verts.append(line.split()[1:4])
            elif line.startswith("vn "):
                norms.append(line.split()[1:4])
            elif line.startswith("f ") and not skipping:
                idx = [p.split("/") for p in line.split()[1:]]
                faces.append([int(p[0]) - 1 for p in idx])
                fnorm_idx.append([int(p[2]) - 1 if len(p) > 2 and p[2] else -1 for p in idx])
                fmat.append(mats.index(mat))
                fpart.append(parts.index(part))
            elif line.startswith("o "):
                part = line[2:].strip()
                skipping = any(part.startswith(s) for s in skip)
                if part not in parts:
                    parts.append(part)
            elif line.startswith("usemtl "):
                mat = line[7:].strip()
                if mat not in mats:
                    mats.append(mat)
    V = np.array(verts, dtype=np.float64)
    N = np.array(norms, dtype=np.float64) if norms else None
    return V, N, faces, fnorm_idx, np.array(fmat), np.array(fpart), mats, parts


def triangulate(faces, fnorm_idx, fmat, fpart):
    tris, tn, tm, tp, tface = [], [], [], [], []
    for k, (fa, fn) in enumerate(zip(faces, fnorm_idx)):
        for i in range(1, len(fa) - 1):
            tris.append((fa[0], fa[i], fa[i + 1]))
            tn.append((fn[0], fn[i], fn[i + 1]))
            tface.append(k)
    tface = np.array(tface)
    return np.array(tris), np.array(tn), fmat[tface], fpart[tface]


def group_of(name):
    base = name.split("_")[0].split(".")[0].upper()
    return {"THUMP": "THUMB", "HANDS": "HAND", "WIRES": "WIRES", "NECK": "NECK"}.get(base, base)


def hexrgb(h):
    return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))


def env(r, look):
    """Reflection environment: a studio box (pack) or the foundry (sodium sky, molten floor)."""
    y = r[:, 1]
    if look == "foundry":
        sky = np.array([0.55, 0.57, 0.62]) * np.clip(y, 0, 1)[:, None] ** 1.2
        band = np.array([1.0, 0.62, 0.26]) * np.exp(-((y - 0.05) / 0.14) ** 2)[:, None] * 0.55
        floor = np.array([1.0, 0.32, 0.05]) * np.clip(-y, 0, 1)[:, None] ** 2 * 0.9
        return sky + band + floor + 0.04
    top = np.array([0.95, 0.97, 1.0]) * np.clip(y, 0, 1)[:, None] ** 1.5
    side = np.array([0.55, 0.6, 0.66]) * np.exp(-((y - 0.15) / 0.25) ** 2)[:, None]
    floor = np.array([0.06, 0.06, 0.07]) * np.clip(-y, 0, 1)[:, None]
    return top + side + floor + 0.02


def shade(n, look, alb, metal, gloss, emis):
    v = np.array([0.0, 0.0, 1.0])
    ndv = np.clip(n @ v, 0, 1)
    r = 2 * ndv[:, None] * n - v
    if look == "foundry":
        lights = [((-0.55, 0.55, 0.62), (1.0, 0.82, 0.62), 1.5), ((0.6, -0.35, -0.7), (1.0, 0.42, 0.1), 1.6),
                  ((0.7, 0.2, 0.4), (0.45, 0.55, 0.72), 0.5)]
        amb = np.array([0.09, 0.08, 0.075])
    else:
        lights = [((-0.5, 0.6, 0.62), (1.0, 0.98, 0.95), 1.15), ((0.65, 0.25, -0.7), (0.55, 0.85, 1.0), 0.9),
                  ((0.7, 0.0, 0.5), (0.6, 0.65, 0.75), 0.3)]
        amb = np.array([0.09, 0.095, 0.11])
    diff = np.zeros_like(n) + amb
    spec = np.zeros_like(n)
    power = 8 + gloss[:, None] * 120
    for d, c, k in lights:
        L = np.array(d) / np.linalg.norm(d)
        c = np.array(c) * k
        ndl = np.clip(n @ L, 0, 1)[:, None]
        diff += ndl * c
        h = (L + v) / np.linalg.norm(L + v)
        spec += (np.clip(n @ h, 0, 1)[:, None] ** power) * c * (0.3 + gloss[:, None])
    fres = 0.04 + 0.96 * (1 - ndv[:, None]) ** 5
    refl = env(r, look) * (metal[:, None] * 0.9 + fres * (1 - metal[:, None]) * gloss[:, None])
    tint = alb * metal[:, None] + (1 - metal[:, None])
    col = alb * (1 - metal[:, None]) * diff + tint * (spec + refl * (0.5 + gloss[:, None]))
    col = col + emis
    return col / (1 + col * 0.35)  # soft tone curve


def render(V, N, T, TN, mat_params, tri_mat, tri_part, look, frames, size, part_colour, explode, turn=0.0, alpha=False):
    W, H = size
    S = 2
    center = (V.min(0) + V.max(0)) / 2
    height = V[:, 1].max() - V[:, 1].min()
    floor_y = V[:, 1].min()
    alb, metal, gloss, emis = (np.array([mat_params[m][i] for m in tri_mat]) for i in range(4))
    if look == "parts":
        alb = np.array([part_colour[p] for p in tri_part]) * 0.85
        metal, gloss, emis = np.zeros(len(T)), np.full(len(T), 0.45), np.zeros((len(T), 3))
    P = V[T]  # tris x 3 x 3
    if explode:
        offs = np.zeros((tri_part.max() + 1, 3))
        for p in np.unique(tri_part):
            c = P[tri_part == p].reshape(-1, 3).mean(0)
            d = c - center
            d[1] *= 0.55
            offs[p] = d * 0.75
        P = P + offs[tri_part][:, None, :]
    if N is not None and (TN >= 0).all():
        n_obj = N[TN].mean(1)
    else:
        n_obj = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    n_obj /= np.linalg.norm(n_obj, axis=1, keepdims=True) + 1e-12
    g_obj = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    cols = 6
    rows = math.ceil(frames / cols)
    sheet = Image.new("RGBA" if alpha else "RGB", (cols * W, rows * H))
    span = (P[..., 1].max() - floor_y) if explode else height
    radius = np.sqrt((P[..., 0] - center[0]) ** 2 + (P[..., 2] - center[2]) ** 2).max()
    scale = min((H * S * 0.86) / span, (W * S * 0.92) / (2 * radius * 1.1))
    for fi in range(frames):
        a = 2 * math.pi * fi / frames + math.radians(turn)
        R = np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]])
        Q = (P - [center[0], floor_y, center[2]]) @ R.T
        n = n_obj @ R.T
        g = g_obj @ R.T
        cam_d = 4.2 * span
        zc = cam_d - Q[..., 2]
        f = scale * cam_d
        x = W * S / 2 + Q[..., 0] * f / zc
        y = H * S * 0.95 - Q[..., 1] * f / zc
        front = g[:, 2] > 0
        flip = (n[:, 2] < 0) & front
        n = np.where(flip[:, None], -n, n)
        col = shade(n, look, alb, metal, gloss, emis)
        col = np.clip(col * 255, 0, 255).astype(np.uint8)
        depth = Q[..., 2].mean(1)
        order = np.argsort(depth)
        if alpha:
            img = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
        else:
            img = Image.new("RGB", (W * S, H * S))
            img.paste(background(W * S, H * S, look))
        shadow = Image.new("L", (W * S, H * S), 0)
        sd = ImageDraw.Draw(shadow)
        sw = height * 0.28 * scale
        sd.ellipse([W * S / 2 - sw, H * S * 0.95 - sw * 0.12, W * S / 2 + sw, H * S * 0.95 + sw * 0.12], fill=170)
        shadow = shadow.filter(ImageFilter.GaussianBlur(14))
        img.paste((0, 0, 0, 150) if alpha else (0, 0, 0), mask=shadow)
        dr = ImageDraw.Draw(img)
        xs, ys = x[order], y[order]
        cs = col[order]
        for i in range(len(order)):
            c = tuple(cs[i])
            dr.polygon([(xs[i, 0], ys[i, 0]), (xs[i, 1], ys[i, 1]), (xs[i, 2], ys[i, 2])], fill=c, outline=c)
        if alpha:
            img = img.convert("RGBa").resize((W, H), Image.Resampling.LANCZOS).convert("RGBA")
        else:
            img = img.resize((W, H), Image.Resampling.LANCZOS)
        sheet.paste(img, ((fi % cols) * W, (fi // cols) * H))
    return sheet, cols, rows


def background(w, h, look):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / w) ** 2 + ((yy - h * 0.55) / h) ** 2)
    if look == "foundry":
        base, glow = np.array([12, 9, 8]), np.array([70, 34, 12])
    else:
        base, glow = np.array([10, 11, 13]), np.array([38, 42, 50])
    k = np.clip(1 - r * 1.6, 0, 1)[..., None] ** 1.5
    img = base + glow * k
    fl = yy > h * 0.95
    img[fl] *= 0.6
    return Image.fromarray(img.astype(np.uint8))


def main():
    args = sys.argv[1:]
    path, out = args[0], args[1]
    opt = {args[i][2:]: args[i + 1] for i in range(2, len(args) - 1, 2)}
    looks = opt.get("looks", "pack,foundry,parts").split(",")
    frames = int(opt.get("frames", 24))
    W, H = (int(v) for v in opt.get("size", "420x480").split("x"))
    skip = [s for s in opt.get("skip", "").split(",") if s]
    alpha = opt.get("alpha", "0") == "1"
    rules = dict(kv.split("=") for kv in opt.get("mat", "").split(",") if kv)
    os.makedirs(out, exist_ok=True)
    V, N, faces, fnorm_idx, fmat, fpart, mats, parts = load_obj(path, skip)
    T, TN, tri_mat, tri_part = triangulate(faces, fnorm_idx, fmat, fpart)
    used = np.unique(T)
    remap = np.full(len(V), -1)
    remap[used] = np.arange(len(used))
    V = V[used]
    T = remap[T]

    def preset(m):
        for k, p in rules.items():
            if m.lower().startswith(k.lower()):
                return p
        return "graphite"
    groups = []
    for p in parts:
        g = group_of(p)
        if g not in groups and not any(p.startswith(s) for s in skip):
            groups.append(g)
    part_group = [groups.index(group_of(p)) if group_of(p) in groups else 0 for p in parts]
    part_colour = [hexrgb(GROUP_COLOURS[part_group[i] % len(GROUP_COLOURS)]) for i in range(len(parts))]
    info = {"source": os.path.basename(path), "triangles": int(len(T)), "vertices": int(len(V)),
            "parts": sum(1 for p in parts if not any(p.startswith(s) for s in skip)),
            "height_units": round(float(V[:, 1].max() - V[:, 1].min()), 3), "frames": frames, "frame": [W, H],
            "groups": [{"name": g, "colour": GROUP_COLOURS[i % len(GROUP_COLOURS)],
                        "parts": sum(1 for j, p in enumerate(parts) if part_group[j] == i and not any(p.startswith(s) for s in skip))}
                       for i, g in enumerate(groups)],
            "materials": {m: preset(m) for m in mats}, "sheets": {}}
    for look in looks:
        if look == "foundry":
            mp = [FOUNDRY_MATS[FOUNDRY[preset(m)]] for m in mats]
        else:
            mp = [PRESETS[preset(m)] for m in mats]
        mp = [(np.array(a), m, g, np.array(e) if e else np.zeros(3)) for a, m, g, e in mp]
        sheet, cols, rows = render(V, N, T, TN, mp, tri_mat, tri_part, look, frames, (W, H), part_colour,
                                   explode=(look == "parts"), turn=float(opt.get("turn", 0)), alpha=alpha)
        if alpha:
            name = f"{look}.webp"
            sheet.save(os.path.join(out, name), quality=84, method=4)
        else:
            name = f"{look}.jpg"
            sheet.save(os.path.join(out, name), quality=82, optimize=True, progressive=True)
        info["sheets"][look] = {"file": name, "cols": cols, "rows": rows}
        print(look, "done", flush=True)
    with open(os.path.join(out, "info.json"), "w") as f:
        json.dump(info, f, indent=1)
    print(json.dumps({k: info[k] for k in ("triangles", "parts", "height_units")}))


if __name__ == "__main__":
    main()
