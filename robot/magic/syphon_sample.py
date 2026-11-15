"""Samples a Syphon server at a fixed rate and prints, per sample, the wall clock, lit share and mean RGB (lit: a pixel with a channel above 8).

    PYTHONPATH=~/.local/lib/python3.13/site-packages python3.13 robot/magic/syphon_sample.py --seconds 8 [--hz 10] [--app Magic] [--server "Main Server"]
"""
import argparse
import time

import syphon
from Foundation import NSDate, NSRunLoop
from syphon.utils.raw import copy_mtl_texture_to_bytes


def pump(s):
    NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(s))


def stats(raw, w, h):
    stride = len(raw) // h
    lit = n = 0
    sums = [0, 0, 0]
    for y in range(0, h, 2):
        row = raw[y * stride:y * stride + w * 4]
        b, g, r = row[0::4], row[1::4], row[2::4]
        sums[0] += sum(r)
        sums[1] += sum(g)
        sums[2] += sum(b)
        lit += sum(1 for i in range(w) if max(r[i], g[i], b[i]) > 8)
        n += w
    return lit / n, [round(s / n, 1) for s in sums]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default="Magic")
    ap.add_argument("--server", default="Main Server")
    ap.add_argument("--seconds", type=float, default=8)
    ap.add_argument("--hz", type=float, default=10)
    a = ap.parse_args()
    d = syphon.SyphonServerDirectory()
    desc = None
    end = time.time() + 15
    while desc is None and time.time() < end:
        pump(0.2)
        desc = next((x for x in d.servers if x.app_name == a.app and x.name == a.server), None)
    if desc is None:
        raise SystemExit("no Syphon server %s / %s" % (a.app, a.server))
    c = syphon.SyphonMetalClient(desc)
    t0 = time.time()
    while not c.has_new_frame and time.time() - t0 < 5:
        pump(0.01)
    raw = copy_mtl_texture_to_bytes(c.new_frame_image)
    w, h = c.new_frame_image.width(), c.new_frame_image.height()
    start = time.perf_counter()
    for i in range(int(a.seconds * a.hz)):
        while time.perf_counter() < start + i / a.hz:
            pump(0.004)
        if c.has_new_frame:
            raw = copy_mtl_texture_to_bytes(c.new_frame_image)
        lit, mean = stats(raw, w, h)
        print("%.3f lit %.3f mean %s" % (time.time(), lit, mean), flush=True)


if __name__ == "__main__":
    main()
