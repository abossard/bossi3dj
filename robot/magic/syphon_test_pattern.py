"""Publishes a known test pattern as a Syphon server, to prove the Robot Scene composites a live layer without Blender.

    PYTHONPATH=~/.local/lib/python3.13/site-packages python3.13 robot/magic/syphon_test_pattern.py [--name ROBOT_TEST] [--size 480x270]

Left half red (255,0,0), right half blue (0,0,255). Refuses ROBOT_LIVE, which only Blender publishes.
"""
import argparse
import time

import syphon
from Foundation import NSDate, NSRunLoop
from syphon.utils.raw import copy_bytes_to_mtl_texture, create_mtl_texture


def pattern(w, h):
    half = w // 2
    return (bytes((255, 0, 0, 255)) * half + bytes((0, 0, 255, 255)) * (w - half)) * h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="ROBOT_TEST")
    ap.add_argument("--size", default="480x270")
    ap.add_argument("--seconds", type=float, default=0, help="stop after this long (0: until interrupted)")
    a = ap.parse_args()
    if a.name.startswith("ROBOT_LIVE"):
        raise SystemExit("ROBOT_LIVE is Blender's name; use another")
    w, h = map(int, a.size.split("x"))
    server = syphon.SyphonMetalServer(a.name)
    tex = create_mtl_texture(server.device, w, h)
    copy_bytes_to_mtl_texture(pattern(w, h), tex)
    end = time.time() + a.seconds if a.seconds else None
    while end is None or time.time() < end:
        server.publish_frame_texture(tex)
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(1 / 30))
    server.stop()


if __name__ == "__main__":
    main()
