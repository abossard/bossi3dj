"""Encode step: the Shadow and Depth Pass frames of each rendered Clip into the Pass files of robot/CONTRACTS.md.
No Blender; ffmpeg and numpy (.venv, `make venv`).

    nice .venv/bin/python robot/build/encode_passes.py --package robot/package/v1 [--clip jab_cross__side ...]

- shadow/<clip>.mov: ProRes 422, grey = Shadow Pass coverage (the alpha of shadow/<clip>/NNNN.png), 0 = no shadow.
- depth/<clip>.mov: ProRes 422 HQ, 10-bit grey = metres / 20 clamped to 0..1, and 1 where the beauty alpha is 0
  (the Android is absent). Depth frames are depth/<clip>/NNNN.exr as build_robot.py writes them: uncompressed
  scanlines, one FLOAT channel. Beauty alpha comes from beauty/<clip>.mov.
Clips run one at a time; the frame folders stay next to the movies."""
import argparse
import os
import struct
import subprocess

import numpy as np

W, H, FPS, DEPTH_RANGE_M = 1920, 1080, 30, 20.0


def read_exr_depth(path):
    """One-channel FLOAT, uncompressed scanline EXR (Blender's Depth Pass as build_robot.py writes it)."""
    d = open(path, "rb").read()
    i, attrs = 8, {}
    while d[i] != 0:
        n = d.index(b"\0", i)
        t = d.index(b"\0", n + 1)
        size = struct.unpack("<i", d[t + 1:t + 5])[0]
        attrs[d[i:n].decode()] = d[t + 5:t + 5 + size]
        i = t + 5 + size
    if attrs["compression"] != b"\0" or attrs["channels"][2:6] != struct.pack("<i", 2):
        raise ValueError("%s: expected an uncompressed FLOAT channel" % path)
    x0, y0, x1, y1 = struct.unpack("<4i", attrs["dataWindow"])
    w, h = x1 - x0 + 1, y1 - y0 + 1
    offsets = np.frombuffer(d, dtype="<u8", count=h, offset=i + 1)
    img = np.empty((h, w), dtype=np.float32)
    for off in offsets:
        y = struct.unpack("<i", d[off:off + 4])[0] - y0
        img[y] = np.frombuffer(d, dtype="<f4", count=w, offset=off + 8)
    return img


def beauty_alpha(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "rawvideo", "-pix_fmt", "rgba", "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, H, W, 4)[..., 3]


def prores(out, profile, src_args):
    return ["ffmpeg", "-v", "error", "-y"] + src_args + ["-c:v", "prores_ks", "-profile:v", profile,
                                                       "-pix_fmt", "yuv422p10le", "-r", str(FPS), out]


def encode_shadow(package, clip):
    src = ["-framerate", str(FPS), "-start_number", "0", "-i", os.path.join(package, "shadow", clip, "%04d.png"),
           "-vf", "alphaextract,format=gray16le"]
    subprocess.run(prores(os.path.join(package, "shadow", clip + ".mov"), "2", src), check=True)


def encode_depth(package, clip):
    folder = os.path.join(package, "depth", clip)
    frames = sorted(f for f in os.listdir(folder) if f.endswith(".exr"))
    alpha = beauty_alpha(os.path.join(package, "beauty", clip + ".mov"))
    if len(alpha) != len(frames):
        raise ValueError("%s: %d depth frames, %d beauty frames" % (clip, len(frames), len(alpha)))
    src = ["-f", "rawvideo", "-pix_fmt", "gray16le", "-s", "%dx%d" % (W, H), "-framerate", str(FPS), "-i", "-"]
    enc = subprocess.Popen(prores(os.path.join(package, "depth", clip + ".mov"), "3", src), stdin=subprocess.PIPE)
    for fn, a in zip(frames, alpha):
        v = np.clip(read_exr_depth(os.path.join(folder, fn)) / DEPTH_RANGE_M, 0.0, 1.0)
        v[a == 0] = 1.0
        enc.stdin.write(np.round(v * 65535).astype("<u2").tobytes())
    enc.stdin.close()
    if enc.wait():
        raise RuntimeError("ffmpeg failed on depth of " + clip)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--clip", action="append", default=[])
    a = ap.parse_args()
    clips = a.clip or sorted(f[:-4] for f in os.listdir(os.path.join(a.package, "beauty")) if f.endswith(".mov"))
    for clip in clips:
        encode_shadow(a.package, clip)
        encode_depth(a.package, clip)
        print("encoded", clip, flush=True)


if __name__ == "__main__":
    main()
