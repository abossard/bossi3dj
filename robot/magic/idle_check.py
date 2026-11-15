"""Magic check of the Idle Clip: a Move ends, the Idle Clip plays and loops without a seam, and the Android leaves it on a bar.

Counter Clips of the fixture Manifest (480x270, ProRes 4444): green is the frame counter, blue names the Move (idle 40, jab_cross 80,
front_kick 120, take_hit 160), red the Angle (front 0, side 120). A Move counts 4 per frame from 0; the Idle Clip is a triangle,
20 + 4 x min(n, 57 - n), so its first and last frames are equal and a black or stuck frame at the loop point shows as 0 or a flat run.
The generated project is the Robot's (graph, selectors, gate) with the audio clock replaced by OSC Globals on a 19xxx port, driven here at
124 BPM through calm, build, calm, build. It replaces the project open in Magic. No Blender, no ROBOT_LIVE, no 9201 or 9202.

    python3 robot/magic/idle_check.py [--port 19406] [--keep DIR] [--cut-rate 1]
"""
import argparse
import json
import math
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "magic"))
import magicproj as mp  # noqa: E402
import robot_magic as rm  # noqa: E402

BPM, FPS = 124, 30
SPB = 60.0 / BPM                                   # seconds per beat
SECONDS = 17.5
MOVE_MARK = {"idle": 40, "jab_cross": 80, "front_kick": 120, "take_hit": 160}
ANGLE_MARK = {"front": 0, "side": 120}
PY313 = {"PYTHONPATH": os.path.expanduser("~/.local/lib/python3.13/site-packages")}


def energy(beat):
    """Calm, build from beat 13, calm from 19, build from 29: idle to a Move on bar 16, the Move ends on 20, idle again, out on 32."""
    return 0.4 if 13 <= beat < 19 or beat >= 29 else 0.1


def counter_clip(path, clip):
    n = clip["frames"]
    g = "20+4*min(N,%d-N)" % (n - 1) if clip["idle"] else "4*N"
    vf = "format=gbrp,geq=r='%d':g='%s':b='%d',format=yuva444p10le" % (ANGLE_MARK[clip["angle"]], g, MOVE_MARK[clip["move"]])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=480x270:r=%d" % FPS, "-vf", vf,
                    "-frames:v", str(n), "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", path], check=True)


def make_package(folder):
    src = os.path.join(HERE, "..", "package", "fixture")
    for rel in ("manifest.json", "clip_data", "camera"):
        a, b = os.path.join(src, rel), os.path.join(folder, rel)
        shutil.copytree(a, b, dirs_exist_ok=True) if os.path.isdir(a) else shutil.copy(a, b)
    with open(os.path.join(folder, "manifest.json")) as f:
        clips = json.load(f)["clips"]
    for c in clips:
        first = os.path.join(folder, c["passes"]["beauty"])
        counter_clip(first, c)
        for k in ("shadow", "depth"):
            dst = os.path.join(folder, c["passes"][k])
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy(first, dst)


def make_project(folder, port, cut_rate):
    clock = [("Beats", 0, "osc:/test/beats", []), ("Phase", 0, "osc:/test/phase", []), ("EnergyAvg", 0.1, "osc:/test/energy", []),
             ("BPM", BPM, "osc:/test/bpm", []), ("Dt", 1.0 / FPS, None, [])]
    path = os.path.join(folder, "idle_check.magic")
    rm.build_project(os.path.join(folder, "manifest.json"), path, osc_in=port, clock=clock, cut_rate=cut_rate)
    return path


def osc_float(address, value):
    pad = lambda b: b + b"\0" * (4 - len(b) % 4)
    return pad(address.encode()) + pad(b",f") + struct.pack(">f", value)


def decode(v):
    """Magic's output darkens the card levels by v^2 / 255 through its Mask and Transparency; back to the level in the file."""
    return math.sqrt(255.0 * v)


def classify(g, r, b):
    kind = min(MOVE_MARK, key=lambda k: abs(MOVE_MARK[k] - b))
    return kind if abs(MOVE_MARK[kind] - b) < 12 else "?"


def analyse(rows, t0_beat):
    """rows: (t, g, r, b) with t in s since beat 0. Returns (report lines, ok)."""
    segs = []
    for t, g, r, b in rows:
        kind = classify(g, r, b)
        if kind == "?":
            continue
        if not segs or segs[-1][0] != kind:
            segs.append([kind, t, t])
        segs[-1][2] = t
    lines = ["segments (clip, from beat, to beat):"] + ["  %-10s %5.2f to %5.2f" % (k, a / SPB, z / SPB) for k, a, z in segs]
    kinds = [k for k, _a, _z in segs]
    ok = kinds[0] == "idle" and kinds[1] != "idle" and kinds[2] == "idle" and kinds[3] != "idle" and len(kinds) >= 4
    lines.append("order idle, Move, idle, Move: %s (%s)" % (ok, " ".join(kinds)))
    black = [t for t, g, r, b in rows if max(g, r, b) < 3]
    lines.append("black samples (every channel under 3 of 255): %d" % len(black))
    ok &= not black
    # the Moves restart at frame 0 and the exits happen just after a bar line (the pipeline is about 5 frames)
    for (k, a, z), (want_beat, what) in zip(segs[1:4], [(16, "idle to Move"), (20, "Move to idle"), (32, "idle to Move")]):
        late = a - want_beat * SPB
        good = 0 <= late <= 0.3
        lines.append("%s at beat %d: switch %.3f s after the bar line, in time=%s" % (what, want_beat, late, good))
        ok &= good
    first_move = next(rows_after(rows, segs[1][1]))
    lines.append("first Move sample level %.1f (frame %.1f), starts at frame 0 to 3=%s" % (first_move[1], first_move[1] / 4, first_move[1] <= 12))
    ok &= first_move[1] <= 12
    # the loop point: the triangle's minimum 20 is the seam; count passes through it and look for a jump or a flat run
    idle_rows = [(t, g) for t, g, r, b in rows if classify(g, r, b) == "idle" and 20.5 * SPB < t < 31.5 * SPB]
    seams = [i for i in range(1, len(idle_rows) - 1) if idle_rows[i][1] <= 28 and idle_rows[i - 1][1] > idle_rows[i][1] <= idle_rows[i + 1][1]]
    jumps = max(abs(a[1] - b[1]) for a, b in zip(idle_rows, idle_rows[1:]))
    flat = _longest_flat(idle_rows)
    lines.append("idle beats 20.5 to 31.5: %d loop seams (levels there %s), largest step between samples %.1f, longest flat run %.2f s"
                 % (len(seams), [round(idle_rows[i][1], 1) for i in seams], jumps, flat))
    seam_ok = len(seams) >= 2 and jumps <= 30 and flat <= 0.25
    lines.append("seamless loop: %s" % seam_ok)
    return lines, ok and seam_ok


def rows_after(rows, t):
    return (r for r in rows if r[0] >= t)


def _longest_flat(rows):
    best = run = 0.0
    for a, b in zip(rows, rows[1:]):
        run = run + (b[0] - a[0]) if abs(a[1] - b[1]) < 0.5 else 0.0
        best = max(best, run)
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", type=int, default=19406)
    ap.add_argument("--cut-rate", type=float, default=1.0)
    ap.add_argument("--keep")
    a = ap.parse_args()
    if a.port in (9201, 9202, 6454):
        raise SystemExit("port reserved")
    tmp = tempfile.TemporaryDirectory()
    folder = a.keep or tmp.name
    os.makedirs(folder, exist_ok=True)
    make_package(folder)
    project = make_project(folder, a.port, a.cut_rate)
    magicproj = os.path.join(HERE, "..", "..", "magic", "magicproj.py")
    print("check:", subprocess.run([sys.executable, magicproj, "check", project], capture_output=True, text=True).stdout.strip().splitlines()[-1])
    subprocess.run([sys.executable, magicproj, "load", project], check=True)
    time.sleep(4)
    proc = subprocess.Popen(["python3.13", os.path.join(HERE, "restart_check.py"), "--sample", str(SECONDS), "30"],
                            stdout=subprocess.PIPE, text=True, env=dict(os.environ, **PY313))
    first = proc.stdout.readline()
    t0 = float(first.split()[0])
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    while True:                                  # the beat clock: 60 Hz, 124 BPM from the first sample on
        t = time.time() - t0
        if t > SECONDS:
            break
        beats = t / SPB
        for addr, v in (("/test/beats", math.floor(beats)), ("/test/phase", beats - math.floor(beats)),
                        ("/test/energy", energy(int(beats))), ("/test/bpm", BPM)):
            sock.sendto(osc_float(addr, v), ("127.0.0.1", a.port))
        time.sleep(1 / 60)
    lines = [first] + proc.stdout.read().splitlines()
    proc.wait()
    rows = []
    for l in lines:
        p = l.split()
        if len(p) >= 4:
            rows.append((float(p[0]) - t0, decode(float(p[1])), decode(float(p[2])), decode(float(p[3]))))
    with open(os.path.join(folder, "idle_rows.txt"), "w") as f:
        f.write("".join("%.3f %.2f %.2f %.2f\n" % row for row in rows))
    for t, g, r, b in rows[::3]:
        print("beat %6.2f  %-10s angle %-5s  level %6.1f" % (t / SPB, classify(g, r, b), "side" if r > 60 else "front", g))
    try:
        out, ok = analyse(rows, 0)
    except IndexError:
        out, ok = ["too few segments to analyse"], False
    print("\n".join(out))
    print("RESULT:", "pass" if ok else "fail")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
