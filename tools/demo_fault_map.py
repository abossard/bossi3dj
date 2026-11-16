"""The demo check's picture faults joined with the scene's state, per second (#25).

    .venv/bin/python tools/demo_fault_map.py OUT_DIR

Reads OUT_DIR/unheld.mp4 (tools/live_demo_check.sh record) and OUT_DIR/state.jsonl (tools/scene_state_log.py, t 0 = the
recording's first frame). Per second of video: mean luminance, spatial spread (std of luminance: near 0 is a flat frame),
mean rgb, the frames whose luminance jumps by more than WHITE over the previous one (a flash), then the logged values at
that second. A fault column names what the second shows: black (luminance under BLACK), flat (spread under FLAT) or the
flash count. Prints one table and writes OUT_DIR/fault_map.json. The state is sampled once a second, so a one-frame
strobe spike can fall between samples."""
import json
import os
import subprocess
import sys

import numpy as np

W, H = 160, 90
BLACK, FLAT, WHITE = 15.0, 15.0, 60.0
KEYS = ("vj_night", "vj_target", "vj_path", "vj_height", "vj_blend", "vj_strobe", "vj_hue", "vj_intensity", "vj_fog",
        "vj_fog_hue", "vj_sun")
RT = ("rt_sun_h", "rt_space")


def frames(video):
    raw = subprocess.run(["ffmpeg", "-v", "0", "-i", video, "-vf", "scale=%d:%d" % (W, H), "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3).astype(float)


def main(out):
    f = frames(os.path.join(out, "unheld.mp4"))
    lum = f.mean(axis=3)
    mean, spread = lum.mean(axis=(1, 2)), lum.std(axis=(1, 2))
    jump = np.concatenate([[0.0], np.diff(mean)])
    states = [json.loads(line) for line in open(os.path.join(out, "state.jsonl"))]
    rows = []
    for s in range(len(f) // 30):
        sl = slice(s * 30, (s + 1) * 30)
        st = min((x for x in states if "values" in x), key=lambda x: abs(x["t"] - (s + 0.5)), default={})
        v, rt = st.get("values", {}), st.get("rt", {})
        flashes = int((jump[sl] > WHITE).sum())
        fault = "black" if mean[sl].mean() < BLACK else "flat" if spread[sl].mean() < FLAT else ""
        if flashes:
            fault = (fault + " " if fault else "") + "flash%d" % flashes
        rows.append({"s": s, "fault": fault, "lum": round(float(mean[sl].mean()), 1), "spread": round(float(spread[sl].mean()), 1),
                     "rgb": [round(float(c)) for c in f[sl].mean(axis=(0, 1, 2))], "camera": st.get("camera"),
                     **{k: round(v[k], 3) for k in KEYS if k in v}, **{k: round(rt[k], 3) for k in RT if k in rt}})
    with open(os.path.join(out, "fault_map.json"), "w") as fh:
        json.dump(rows, fh, indent=1)
    cols = ["s", "fault", "lum", "spread", "rgb", "camera"] + [k[3:] for k in KEYS] + list(RT)
    print("\t".join(cols))
    for r in rows:
        print("\t".join(str(r.get(c if c in r else "vj_" + c, "")) for c in cols))


if __name__ == "__main__":
    main(sys.argv[1])
