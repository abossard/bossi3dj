"""clip_complete.py PACKAGE CLIP FRAMES: exit 0 when the Clip is fully rendered and encoded (beauty, shadow and
depth movies with FRAMES frames, and FRAMES Shadow and Depth frames on disk), else 1. Standard library and ffprobe."""
import os
import subprocess
import sys


def frames(path):
    if not os.path.isfile(path):
        return -1
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
                          "stream=nb_read_packets", "-of", "csv=p=0", path], capture_output=True, text=True).stdout
    return int(out.strip() or -1)


def main():
    pkg, clip, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
    ok = all(frames(os.path.join(pkg, p, clip + ".mov")) == n for p in ("beauty", "shadow", "depth"))
    for p, ext in (("shadow", ".png"), ("depth", ".exr")):
        folder = os.path.join(pkg, p, clip)
        ok = ok and os.path.isdir(folder) and len([f for f in os.listdir(folder) if f.endswith(ext)]) == n
    sys.exit(0 if ok else 1)


main()
