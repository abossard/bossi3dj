#!/usr/bin/env python3.13
"""Records a Syphon server to an H.264 file, as a viewer gets it: the newest frame every 1/fps s of wall time (a slow
sender shows as repeated frames), raw BGRA piped into ffmpeg, scaled and encoded there.

    PYTHONPATH=~/.local/lib/python3.13/site-packages python3.13 tools/syphon_record.py \\
        --app Blender --server CAM_OUT --seconds 90 --fps 30 --size 960x540 --out docs/video/x.mp4 [--flag FILE] [--vflip]

--flag waits until FILE exists and starts recording then (a scene job writes it when its flight starts). The client
reads with the same calls as magicproj.py grab. Prints one JSON line: frames written, new frames seen, repeats."""
import argparse
import json
import os
import subprocess
import sys
import time

import syphon
from Foundation import NSDate, NSRunLoop
from syphon.utils.raw import copy_mtl_texture_to_bytes

FFMPEG = "/opt/homebrew/bin/ffmpeg"


def pump(s):
    NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(s))


def find(app, server, timeout=15.0):
    d = syphon.SyphonServerDirectory()
    end = time.time() + timeout
    while time.time() < end:
        pump(0.2)
        for desc in d.servers:
            if desc.app_name == app and (not server or desc.name == server):
                return desc
    raise SystemExit("no Syphon server %s / %s" % (app, server))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default="Blender")
    ap.add_argument("--server", default="CAM_OUT")
    ap.add_argument("--seconds", type=float, default=90.0)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--size", default="960x540")
    ap.add_argument("--out", required=True)
    ap.add_argument("--flag")
    ap.add_argument("--vflip", action="store_true")
    ap.add_argument("--crf", default="23")
    a = ap.parse_args()
    c = syphon.SyphonMetalClient(find(a.app, a.server))
    t = time.time()
    while not c.has_new_frame and time.time() - t < 5.0:
        pump(0.01)
    tex = c.new_frame_image
    w, h = tex.width(), tex.height()
    raw = copy_mtl_texture_to_bytes(tex)
    stride = len(raw) // h
    if a.flag:
        while not os.path.exists(a.flag):
            pump(0.01)
            if c.has_new_frame:
                raw = copy_mtl_texture_to_bytes(c.new_frame_image)
    vf = ("crop=%d:%d:0:0," % (w, h) if stride // 4 != w else "") + ("vflip," if a.vflip else "") \
        + "scale=%s:flags=bicubic" % a.size.replace("x", ":")      # rows may carry padding: cropped first
    ff = subprocess.Popen([FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra",
                           "-s", "%dx%d" % (stride // 4, h), "-r", "%g" % a.fps, "-i", "-", "-vf", vf,
                           "-c:v", "libx264", "-preset", "medium", "-crf", a.crf, "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                           a.out], stdin=subprocess.PIPE)
    n = int(round(a.seconds * a.fps))
    start = time.perf_counter()
    new = rep = 0
    for i in range(n):
        due = start + i / a.fps
        while time.perf_counter() < due:
            pump(min(0.004, max(due - time.perf_counter(), 0.0)))
        if c.has_new_frame:
            raw = copy_mtl_texture_to_bytes(c.new_frame_image)
            new += 1
        else:
            rep += 1
        ff.stdin.write(raw)
    ff.stdin.close()
    ff.wait()
    c.stop()
    print(json.dumps({"out": a.out, "frames": n, "new_frames": new, "repeats": rep, "size": a.size,
                      "seconds_wall": round(time.perf_counter() - start, 2), "bytes": os.path.getsize(a.out)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
