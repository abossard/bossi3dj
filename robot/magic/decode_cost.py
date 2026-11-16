"""Decode cost of the Robot's Angles in Magic: Clip formats and Angle counts at 1920x1080, 30 fps, alternating runs.

    python3 robot/magic/decode_cost.py --configs prores,raw --angles 4 [--rounds 2] [--seconds 15] [--keep DIR]

Work files go to robot/magic/decode/ (git-ignored, about 2 GB), never to a temp folder.
    python3 robot/magic/decode_cost.py --list

A config is the format of the Passes: beauty (colour and alpha), shadow, and an optional own matte. The fixture Moves run on a
free-running clock (Section 2, 124 BPM); every Angle is drawn all the time, so N Angles decode N streams per Pass. Magic sends its
Graphics FPS to a spare port (19412, never 9201 or 9202). CPU is the Magic process (top, second sample), GPU is the "Device
Utilization %" of ioreg (the whole GPU). Each run records load_1m before and after: a number taken under a high load is not
trustworthy, the ratio between runs is. Magic is loaded with `magicproj load` (the user's open project is replaced).
The Clip content is a noisy disc on transparent black (about a quarter of the frame lit), so alpha and run-length codecs see
something like an Android on an empty background.
"""
import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "osc"))
import manifest as mf  # noqa: E402
import robot_magic as rm  # noqa: E402
from lab import parse_packet  # noqa: E402

PORT = 19412
MAGICPROJ = os.path.join(HERE, "..", "..", "magic", "magicproj.py")
FIXTURE = os.path.join(HERE, "..", "package", "fixture")
PROBE = ["Fps"]
W, H = 1920, 1080
DISC = "geq=lum='if(lt(hypot(X-%d,Y-%d),400),lum(X,Y),0)':cb='128':cr='128':a='if(lt(hypot(X-%d,Y-%d),400),255,0)'" % (W // 2, H // 2, W // 2, H // 2)
SRC = "testsrc2=s=%dx%d:r=30,noise=alls=40:allf=t,format=yuva444p,%s" % (W, H, DISC)

# format name: (ffmpeg filter tail, output codec options). The tail starts from the yuva444p disc stream.
FORMATS = {
    "prores4444": ("format=yuva444p10le", ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le"]),
    "prores4444lq": ("format=yuva444p10le", ["-c:v", "prores_ks", "-profile:v", "4444", "-qscale:v", "20", "-pix_fmt", "yuva444p10le"]),
    "prores422": ("format=yuv422p10le", ["-c:v", "prores_ks", "-profile:v", "2", "-pix_fmt", "yuv422p10le"]),
    "qtrle": ("format=argb", ["-c:v", "qtrle", "-pix_fmt", "argb"]),
    "raw": ("format=argb", ["-c:v", "rawvideo", "-pix_fmt", "argb"]),
    "h264": ("format=yuv420p", ["-c:v", "h264_videotoolbox", "-g", "1", "-b:v", "60M", "-pix_fmt", "yuv420p"]),
    "h264half": ("scale=%d:%d,format=yuv420p" % (W // 2, H // 2), ["-c:v", "h264_videotoolbox", "-g", "1", "-b:v", "20M", "-pix_fmt", "yuv420p"]),
    "grey": ("alphaextract,format=yuv420p", ["-c:v", "h264_videotoolbox", "-g", "1", "-b:v", "20M", "-pix_fmt", "yuv420p"]),
}
# config name: (beauty format, shadow format, matte format or None)
CONFIGS = {
    "prores": ("prores4444", "prores422", None),                    # the baseline of 4be1f12
    "prores_lq": ("prores4444lq", "prores422", None),
    "qtrle": ("qtrle", "prores422", None),
    "raw": ("raw", "prores422", None),
    "prores_h264shadow": ("prores4444", "h264", None),
    "prores_halfshadow": ("prores4444", "h264half", None),
    "h264_matte": ("h264", "h264", "grey"),                          # colour, matte and shadow all planar 4:2:0 H.264
    "raw_h264shadow": ("raw", "h264", None),
    "raw_halfshadow": ("raw", "h264half", None),
}


def encode(path, fmt, frames):
    tail, codec = FORMATS[fmt]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", SRC, "-vf", tail, "-frames:v", str(frames)] + codec + [path], check=True)


def make_manifest(folder, angles, config):
    """A 1080p copy of the fixture with `angles` Angles, passes hard linked from one encoded file per format."""
    with open(os.path.join(FIXTURE, "manifest.json")) as f:
        d = json.load(f)
    base = [c for c in d["clips"] if c["angle"] == d["angles"][0]["id"]]
    d["angles"] = [{"id": "a%d" % i, "camera": "CAM_%d" % i} for i in range(angles)]
    d["clips"] = [dict(c, id="%s__a%d" % (c["move"], i), angle="a%d" % i, passes=dict(c["passes"])) for c in base for i in range(angles)]
    d["size"] = [W, H]
    frames = max(c["frames"] for c in d["clips"])
    beauty, shadow, matte = CONFIGS[config]
    kinds = {"beauty": beauty, "shadow": shadow, "depth": shadow}
    if matte:
        kinds["matte"] = matte
    cache = {}
    for kind, fmt in kinds.items():
        if fmt not in cache:
            ext = ".mov"
            cache[fmt] = os.path.join(folder, "_enc_%s%s" % (fmt, ext))
            if not os.path.isfile(cache[fmt]):
                encode(cache[fmt], fmt, frames)
    for c in d["clips"]:
        for kind, fmt in kinds.items():
            dst = os.path.join(folder, "clips", "%s_%s.mov" % (c["id"], kind))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.exists(dst):
                os.remove(dst)
            os.link(cache[fmt], dst)
            c["passes"][kind] = os.path.relpath(dst, folder)
    problems = mf.validate(d)
    assert not problems, problems
    return mf.Manifest(d, folder), bool(matte)


def make_project(folder, m, matte_pass):
    clock = [("Time", 0, "calc", [("Increase", 1)]), ("TimeLag", 0, "calc", [("Expression", "Time")]),
             ("Dt", 0.016, "calc", [("Expression", "max(0.001, min(0.05, Time - TimeLag))")]),
             ("Bpm", 124, None, []), ("Section", 2, None, []),
             ("Beats", 0, "calc", [("Expression", "floor(Time*Bpm/60)")]), ("BeatFrac", 0, "calc", [("Expression", "Time*Bpm/60 - floor(Time*Bpm/60)")])]
    b = rm.build(m, live="ROBOT_TEST", osc_port=PORT + 1, osc_in=PORT + 2, clock=clock, matte_pass=matte_pass, project_dir=folder)
    b.glob("Fps", 0, "internal:Graphics FPS")
    probe = b.scene("Probe")
    probe.output(*[probe.node("OSCSender", {"IP Addr.": "127.0.0.1", "Port": PORT, "Message": "/probe/" + n, "Value": ("global:" + n, [], 0)})
                   for n in PROBE])
    b._scenes[0].outputs.append(b._scenes[0].scene_module(probe))
    root = b.build()
    for iv in root.iter("InputValue"):
        if iv.get("name") == "File" and iv.get("value"):
            iv.set("absoluteFilename", os.path.normpath(os.path.join(folder, iv.get("value"))))
    path = os.path.join(folder, "decode_cost.magic")
    rm.mp.write(path, root)
    return path


def magic_pid():
    return subprocess.run(["pgrep", "-f", "Magic(Beta)?.app/Contents/MacOS/Magic$"], capture_output=True, text=True).stdout.split()[0]


def cpu(pid):
    return float(subprocess.run(["top", "-l", "2", "-s", "1", "-pid", pid, "-stats", "cpu"], capture_output=True, text=True).stdout.split()[-1])


def gpu():
    m = re.search(r'"Device Utilization %"=(\d+)', subprocess.run(["ioreg", "-r", "-c", "IOAccelerator"], capture_output=True, text=True).stdout)
    return int(m.group(1)) if m else -1


def run(root, config, angles, seconds, sock):
    folder = os.path.join(root, "%s_%d" % (config, angles))
    os.makedirs(folder, exist_ok=True)
    m, matte_pass = make_manifest(folder, angles, config)
    project = make_project(folder, m, matte_pass)
    load1 = os.getloadavg()[0]
    subprocess.run([sys.executable, MAGICPROJ, "load", project], check=True, capture_output=True)
    pid = magic_pid()
    time.sleep(5)
    while True:
        try:
            sock.recvfrom(65535)
        except socket.timeout:
            break
    fps, cpus, gpus, end = [], [], [], time.time() + seconds
    while time.time() < end:
        cpus.append(cpu(pid))
        gpus.append(gpu())
        t = time.time() + 0.3
        while time.time() < t:
            try:
                data, _ = sock.recvfrom(65535)
            except socket.timeout:
                continue
            for _a, _t, args, _b in parse_packet(data):
                fps.append(args[0])
    mean = lambda v: sum(v) / len(v) if v else float("nan")
    size = sum(os.path.getsize(os.path.join(folder, "clips", f)) for f in os.listdir(os.path.join(folder, "clips"))
               if f.startswith(m.clips[0]["id"].split("__")[0] + "__a0")) / 1e6
    return {"config": config, "angles": angles, "load_before": load1, "load_after": os.getloadavg()[0], "fps": mean(fps),
            "fps_min": min(fps) if fps else float("nan"), "cpu": mean(cpus), "gpu": mean(gpus), "mb_per_move_angle": size}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--configs", default="prores")
    ap.add_argument("--angles", default="1,2")
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--seconds", type=int, default=15)
    ap.add_argument("--keep", default=os.path.join(HERE, "decode"), help="work folder (clips, projects, results), git-ignored; default robot/magic/decode")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        for k, v in CONFIGS.items():
            print("%-18s beauty %s, shadow %s, matte %s" % ((k,) + v))
        return
    root = a.keep
    os.makedirs(root, exist_ok=True)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", PORT))
    sock.settimeout(0.1)
    configs, angles = a.configs.split(","), [int(v) for v in a.angles.split(",")]
    rows = []
    for r in range(a.rounds):
        for config in configs if r % 2 == 0 else configs[::-1]:
            for n in angles if r % 2 == 0 else angles[::-1]:
                row = run(root, config, n, a.seconds, sock)
                rows.append(row)
                print("%-18s %d Angle(s): fps %5.1f (min %4.1f), Magic CPU %3.0f %%, GPU %2.0f %%, %5.1f MB per Move and Angle, load_1m %.1f -> %.1f" % (
                    config, n, row["fps"], row["fps_min"], row["cpu"], row["gpu"], row["mb_per_move_angle"], row["load_before"], row["load_after"]), flush=True)
                with open(os.path.join(root, "decode_cost.json"), "w") as f:
                    json.dump(rows, f, indent=1)
    print("\nmean over %d rounds (fps, CPU %%): " % a.rounds)
    for config in configs:
        cells = []
        for n in angles:
            rs = [x for x in rows if x["config"] == config and x["angles"] == n]
            cells.append("%dA %.1f fps %.0f%%" % (n, sum(x["fps"] for x in rs) / len(rs), sum(x["cpu"] for x in rs) / len(rs)))
        print("  %-18s %s" % (config, ", ".join(cells)))
    print("load_1m during the runs: %.0f to %.0f%s" % (min(r["load_before"] for r in rows), max(r["load_before"] for r in rows),
                                                      " (not trustworthy)" if max(r["load_before"] for r in rows) > 8 else ""))


if __name__ == "__main__":
    main()
