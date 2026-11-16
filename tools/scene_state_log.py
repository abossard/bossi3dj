#!/usr/bin/env python3
"""The scene's state once a second, timed against a recording: what Magic and the page set while the picture was made.

    python3 tools/scene_state_log.py --out LOG.jsonl --seconds 95 [--t0 EPOCH | --flag FILE] [--every 1] [--base http://127.0.0.1:9210]

--flag FILE writes FILE at the log's start: tools/syphon_record.py --flag FILE starts its recording on it, so t 0 is the
recording's start. One JSON line per sample of /api/state: t (s since --t0, else the log's start), every vj_
value, its source (osc, web, artnet), the runtime values the page reports (rt), the camera, the Path Camera, fps.
A failed request is a line with "error". Reads only http; binds no port. Standard library only.
"""
import argparse
import json
import time
import urllib.request

KEEP = ("camera", "path_camera", "fps", "scene_fps", "rt")


def sample(base):
    with urllib.request.urlopen(base + "/api/state", timeout=5) as r:
        s = json.loads(r.read())
    out = {k: s[k] for k in KEEP if k in s}
    out["values"] = s.get("values") or {}
    out["source"] = (s.get("osc") or {}).get("source") or {}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--seconds", type=float, default=95.0)
    ap.add_argument("--every", type=float, default=1.0)
    ap.add_argument("--t0", type=float, default=None, help="epoch seconds the recording started")
    ap.add_argument("--flag", help="file written at the log's start, for syphon_record.py --flag")
    ap.add_argument("--base", default="http://127.0.0.1:9210")
    a = ap.parse_args()
    t0 = a.t0 if a.t0 is not None else time.time()
    if a.flag:
        open(a.flag, "w").close()
    end = time.time() + a.seconds
    with open(a.out, "w") as f:
        while time.time() < end:
            tick = time.time()
            try:
                row = sample(a.base)
            except (OSError, ValueError) as e:
                row = {"error": str(e)}
            f.write(json.dumps({"t": round(tick - t0, 2), **row}) + "\n")
            f.flush()
            time.sleep(max(0.0, a.every - (time.time() - tick)))


if __name__ == "__main__":
    main()
