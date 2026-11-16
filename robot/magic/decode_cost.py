"""Decode cost of the Robot's Angles in Magic: 1 Angle against 2 Angles of 1920x1080 Clips, alternating, fps, CPU and GPU.

    python3 robot/magic/decode_cost.py [--rounds 2] [--seconds 20] [--keep DIR]

Beauty Pass ProRes 4444 with alpha, Shadow Pass ProRes 422, 1920x1080, 30 fps, the fixture's Moves. The generator draws every Angle
all the time, so N Angles decode 2 streams each (beauty and shadow). The Moves run on a free-running clock (Section 2, buildup, 124 BPM),
Magic sends its Graphics FPS to a spare port (19412, never 9201 or 9202). CPU is the Magic process (top, second sample), GPU is the
"Device Utilization %" of ioreg (the whole GPU, not only Magic). Every run records load_1m before and after: a number taken under a
high load is not trustworthy, the ratio between the runs is the result. Magic is loaded with `magicproj load` (the user's open project
is replaced; reload it afterwards).
"""
import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "osc"))
import robot_magic as rm  # noqa: E402
from lab import parse_packet  # noqa: E402
from manifest import load  # noqa: E402

PORT = 19412
MAGICPROJ = os.path.join(HERE, "..", "..", "magic", "magicproj.py")
FIXTURE = os.path.join(HERE, "..", "package", "fixture")
PROBE = ["Fps"]


def encode(path, frames, profile, pix):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    vf = "noise=alls=40:allf=t,format=%s" % pix
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=1920x1080:r=30", "-vf", vf, "-frames:v", str(frames),
                    "-c:v", "prores_ks", "-profile:v", profile, "-pix_fmt", pix, path], check=True)


def make_package(folder, angles):
    """A 1080p copy of the fixture with the first `angles` Angles. One encoded file per Pass, hard linked for every Clip."""
    with open(os.path.join(FIXTURE, "manifest.json")) as f:
        d = json.load(f)
    keep = [a["id"] for a in d["angles"]][:angles]
    d["angles"] = [a for a in d["angles"] if a["id"] in keep]
    d["clips"] = [c for c in d["clips"] if c["angle"] in keep]
    d["size"] = [1920, 1080]
    for rel in ("clip_data", "camera"):
        shutil.copytree(os.path.join(FIXTURE, rel), os.path.join(folder, rel), dirs_exist_ok=True)
    frames = max(c["frames"] for c in d["clips"])
    base = {"beauty": os.path.join(folder, "_beauty.mov"), "shadow": os.path.join(folder, "_shadow.mov")}
    if not all(os.path.isfile(p) for p in base.values()):
        encode(base["beauty"], frames, "4444", "yuva444p10le")
        encode(base["shadow"], frames, "2", "yuv422p10le")
    for c in d["clips"]:
        for k in ("beauty", "shadow", "depth"):
            dst = os.path.join(folder, c["passes"][k])
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.exists(dst):
                os.remove(dst)
            os.link(base["shadow" if k != "beauty" else "beauty"], dst)
    with open(os.path.join(folder, "manifest.json"), "w") as f:
        json.dump(d, f, indent=1)


def make_project(folder):
    m = load(os.path.join(folder, "manifest.json"))
    clock = [("Time", 0, "calc", [("Increase", 1)]), ("TimeLag", 0, "calc", [("Expression", "Time")]),
             ("Dt", 0.016, "calc", [("Expression", "max(0.001, min(0.05, Time - TimeLag))")]),
             ("Bpm", 124, None, []), ("Section", 2, None, []),
             ("Beats", 0, "calc", [("Expression", "floor(Time*Bpm/60)")]), ("BeatFrac", 0, "calc", [("Expression", "Time*Bpm/60 - floor(Time*Bpm/60)")])]
    b = rm.build(m, live="ROBOT_TEST", osc_port=PORT + 1, osc_in=PORT + 2, clock=clock)
    b.glob("Fps", 0, "internal:Graphics FPS")
    probe = b.scene("Probe")
    probe.output(*[probe.node("OSCSender", {"IP Addr.": "127.0.0.1", "Port": PORT, "Message": "/probe/" + n, "Value": ("global:" + n, [], 0)})
                   for n in PROBE])
    b._scenes[0].outputs.append(b._scenes[0].scene_module(probe))
    path = os.path.join(folder, "decode_cost.magic")
    rm.mp.write(path, b.build())
    return path


def magic_pid():
    out = subprocess.run(["pgrep", "-f", "Magic(Beta)?.app/Contents/MacOS/Magic$"], capture_output=True, text=True).stdout.split()
    return out[0]


def cpu(pid):
    out = subprocess.run(["top", "-l", "2", "-s", "1", "-pid", pid, "-stats", "cpu"], capture_output=True, text=True).stdout.split()
    return float(out[-1])


def gpu():
    out = subprocess.run(["ioreg", "-r", "-c", "IOAccelerator"], capture_output=True, text=True).stdout
    m = re.search(r'"Device Utilization %"=(\d+)', out)
    return int(m.group(1)) if m else -1


def run(folder, angles, seconds, sock):
    make_package(folder, angles)
    project = make_project(folder)
    load1 = os.getloadavg()[0]
    subprocess.run([sys.executable, MAGICPROJ, "load", project], check=True, capture_output=True)
    pid = magic_pid()
    time.sleep(6)
    while True:
        try:
            sock.recvfrom(65535)
        except socket.timeout:
            break
    fps, cpus, gpus, end = [], [], [], time.time() + seconds
    while time.time() < end:
        c, g = cpu(pid), gpu()
        cpus.append(c)
        gpus.append(g)
        t = time.time() + 0.5
        while time.time() < t:
            try:
                data, _ = sock.recvfrom(65535)
            except socket.timeout:
                continue
            for _a, _t, args, _b in parse_packet(data):
                fps.append(args[0])
    mean = lambda v: sum(v) / len(v) if v else float("nan")
    return {"angles": angles, "load_before": load1, "load_after": os.getloadavg()[0], "fps": mean(fps), "fps_min": min(fps) if fps else float("nan"),
            "fps_samples": len(fps), "cpu": mean(cpus), "gpu": mean(gpus)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--seconds", type=int, default=20)
    ap.add_argument("--keep")
    a = ap.parse_args()
    tmp = tempfile.TemporaryDirectory()
    root = a.keep or tmp.name
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", PORT))
    sock.settimeout(0.1)
    rows = []
    for r in range(a.rounds):
        for n in (1, 2) if r % 2 == 0 else (2, 1):
            folder = os.path.join(root, "angles%d" % n)
            os.makedirs(folder, exist_ok=True)
            row = run(folder, n, a.seconds, sock)
            rows.append(row)
            print("%d Angle(s): fps %.1f (min %.1f, %d samples), Magic CPU %.0f %%, GPU %.0f %%, load_1m %.1f before, %.1f after" % (
                n, row["fps"], row["fps_min"], row["fps_samples"], row["cpu"], row["gpu"], row["load_before"], row["load_after"]), flush=True)
    with open(os.path.join(root, "decode_cost.json"), "w") as f:
        json.dump(rows, f, indent=1)
    for k in ("fps", "cpu", "gpu"):
        one = [r[k] for r in rows if r["angles"] == 1]
        two = [r[k] for r in rows if r["angles"] == 2]
        print("%s: 1 Angle %.1f, 2 Angles %.1f, ratio 2/1 %.2f" % (k, sum(one) / len(one), sum(two) / len(two), (sum(two) / len(two)) / (sum(one) / len(one))))
    print("all numbers taken under load %.0f (not trustworthy)" % max(r["load_before"] for r in rows))


if __name__ == "__main__":
    main()
