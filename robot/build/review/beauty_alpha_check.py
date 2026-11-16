"""Beauty Pass alpha check: decode a rendered movie with ffmpeg and compare it, frame by frame, to the PNG render of
the same frames (the reference: 16-bit straight alpha, reduced to 8 bit). Standard library and ffmpeg only.

    python3 robot/build/review/beauty_alpha_check.py --ref robot/build/probe/png/beauty/jab_cross__side \\
        --first 13 robot/build/probe/qtrle/beauty/jab_cross__side.mov robot/build/probe/prores/beauty/jab_cross__side.mov

Per movie and frame: alpha where the reference is 0 (off the Android) and 255 (on it), edge pixel count and the
largest alpha difference there, and the mean and max RGB difference on covered pixels (alpha > 0)."""
import argparse
import json
import os
import subprocess

W, H = 1920, 1080


def decode(path):
    """RGBA bytes of every frame in a movie, or of one image; straight alpha, 8 bit."""
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-f", "rawvideo", "-pix_fmt", "rgba", "-"]
    return subprocess.run(cmd, check=True, capture_output=True).stdout


def compare(ref, got):
    alpha = {"ref_0": [0, 0], "ref_255": [255, 0], "edge": [0, 0]}   # [min or count, max]
    rgb_sum = rgb_max = covered = 0
    for i in range(0, len(ref), 4):
        ra, ga = ref[i + 3], got[i + 3]
        if ra == 0:
            alpha["ref_0"][1] = max(alpha["ref_0"][1], ga)
        elif ra == 255:
            alpha["ref_255"][0] = min(alpha["ref_255"][0], ga)
        else:
            alpha["edge"][0] += 1
            alpha["edge"][1] = max(alpha["edge"][1], abs(ra - ga))
        if ra > 0:
            d = max(abs(ref[i + c] - got[i + c]) for c in range(3))
            rgb_sum += d
            rgb_max = max(rgb_max, d)
            covered += 1
    return {"alpha_max_where_ref_0": alpha["ref_0"][1], "alpha_min_where_ref_255": alpha["ref_255"][0],
            "edge_pixels": alpha["edge"][0], "edge_alpha_max_diff": alpha["edge"][1],
            "covered_pixels": covered, "rgb_mean_diff": round(rgb_sum / max(covered, 1), 3), "rgb_max_diff": rgb_max}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True, help="folder of NNNN.png reference frames")
    ap.add_argument("--first", type=int, required=True, help="frame number of the movie's first frame")
    ap.add_argument("movies", nargs="+")
    a = ap.parse_args()
    out = {}
    for movie in a.movies:
        data, size = decode(movie), W * H * 4
        frames = [data[i:i + size] for i in range(0, len(data), size)]
        out[movie] = {"bytes": os.path.getsize(movie), "frames": {}}
        for k, got in enumerate(frames):
            ref = decode(os.path.join(a.ref, "%04d.png" % (a.first + k)))
            out[movie]["frames"][a.first + k] = compare(ref, got)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
