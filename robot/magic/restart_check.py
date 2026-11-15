"""Magic check: does a VideoFile restart exactly once per StartPulse, and hold its last frame at Looping 0?

A 60-frame counter clip (ProRes 4444, grey level 4 x frame number) plays in a one-module project whose `Goto Start` is linked to a
2-frame pulse built like the Robot's StartPulse (max(change, last frame's change)) from an OSC value on a 19xxx port. The script loads
it into Magic (replacing the open project), toggles the OSC value, samples Magic's Syphon output at 30 Hz and prints frame estimate against time.
Needs ffmpeg, Magic Beta with Syphon output and syphon-python under python3.13. Nothing touches 9201, 9202 or ROBOT_LIVE.

    python3 robot/magic/restart_check.py [--port 19405] [--keep DIR]
"""
import argparse
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "magic"))
sys.path.insert(0, os.path.join(HERE, "..", "live"))
import heartbeat  # noqa: E402
import magicproj as mp  # noqa: E402

FRAMES, FPS, STEP = 60, 30, 4          # grey level = STEP x frame number
ADDRESS = "/test/go"
PULSES = (2.0, 3.0, 8.0)               # s after sampling starts; a 2 s clip, so the 2nd and 3rd land mid-clip even when it loops
PY313 = {"PYTHONPATH": os.path.expanduser("~/.local/lib/python3.13/site-packages")}


def make_clip(path):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=480x270:r=%d:d=%g" % (FPS, FRAMES / FPS),
                    "-vf", "format=gbrp,geq=r='%d*N':g='%d*N':b='%d*N',format=yuva444p10le" % (STEP, STEP, STEP),
                    "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", path], check=True)


def make_project(path, port, end_time=0, looping=0):
    b = mp.Builder(syphon="Main Server", size=(480, 270), fps=FPS, osc_in=port)
    for name, value, source, mods in [
        ("Go", 0, "osc:%s" % ADDRESS, []),
        ("GoPrev", 0, "calc", [("Expression", "Go")]),
        ("Change", 0, "calc", [("Expression", "if(Go != GoPrev, 1, 0)")]),
        ("ChangePrev", 0, "calc", [("Expression", "Change")]),
        ("StartPulse", 0, "calc", [("Expression", "max(Change, ChangePrev)")]),
    ]:
        b.glob(name, value, source, mods)
    scene = b.scene("Test")
    vf = scene.node("VideoFile", {"File": "counter.mov", "Speed": 1, "Goto Start": ("global:StartPulse", [], 0), "Looping": looping, "End Time": end_time})
    scene.output(vf)
    root = b.build()
    for iv in root.iter("InputValue"):
        if iv.get("name") == "File":
            iv.set("absoluteFilename", os.path.join(os.path.dirname(os.path.abspath(path)), "counter.mov"))
    mp.write(path, root)


def sample(seconds, hz):
    """Runs under python3.13: prints wall time and the mean green, red and blue level of Magic's output per sample."""
    import syphon
    from Foundation import NSDate, NSRunLoop
    from syphon.utils.raw import copy_mtl_texture_to_bytes

    def pump(s):
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(s))
    d, desc, end = syphon.SyphonServerDirectory(), None, time.time() + 15
    while desc is None and time.time() < end:
        pump(0.2)
        desc = next((x for x in d.servers if x.app_name == "Magic" and x.name == "Main Server"), None)
    if desc is None:
        raise SystemExit("no Syphon server Magic / Main Server")
    c = syphon.SyphonMetalClient(desc)
    while not c.has_new_frame:
        pump(0.01)
    raw = copy_mtl_texture_to_bytes(c.new_frame_image)
    start = time.perf_counter()
    for i in range(int(seconds * hz)):
        while time.perf_counter() < start + i / hz:
            pump(0.002)
        if c.has_new_frame:
            raw = copy_mtl_texture_to_bytes(c.new_frame_image)
        g, r, b = raw[1::4], raw[2::4], raw[0::4]
        print("%.3f %.2f %.2f %.2f" % (time.time(), sum(g) / len(g), sum(r) / len(r), sum(b) / len(b)), flush=True)


def analyse(rows, sent):
    """(lines, ok): per pulse the lowest level within 0.6 s after it, whether the ramp then rises monotonically, and the hold at the end."""
    scale = STEP * (FRAMES - 1)
    out, ok = [], True
    for k, t_pulse in enumerate(sent):
        after = [(t, v) for t, v in rows if t_pulse <= t < t_pulse + 0.6]
        low = min(v for _t, v in after)
        t_low = next(t for t, v in after if v == low)
        until = min([t_low + 1.5] + [p - 0.1 for p in sent[k + 1:]])      # up to the next pulse
        ramp = [v for t, v in rows if t_low <= t < until]
        mono = all(b >= a - 1.5 for a, b in zip(ramp, ramp[1:]))
        restarted = low <= STEP * 3 + 1
        out.append("pulse %d at %.2f s: lowest %.1f (frame %.1f) at %.2f s, restarted=%s, rises monotonically until the next pulse or 1.5 s=%s"
                   % (k + 1, t_pulse, low, low / STEP, t_low, restarted, mono))
        ok &= restarted and mono
    tail = [v for t, v in rows if t > sent[-1] + 2.5]
    kind = "holds" if min(tail) > scale * 0.8 and max(tail) - min(tail) <= 1.5 else \
        "black" if max(tail) <= STEP else "loops" if min(tail) < scale * 0.1 and max(tail) > scale * 0.9 else "other"
    out.append("after the last pulse and the clip end: %d samples, min %.1f max %.1f (last frame %.0f): %s" % (len(tail), min(tail), max(tail), scale, kind))
    return out, ok and kind in ("holds", "loops")


def main():
    if "--sample" in sys.argv:
        i = sys.argv.index("--sample")
        return sample(float(sys.argv[i + 1]), float(sys.argv[i + 2]))
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", type=int, default=19405)
    ap.add_argument("--end-time", type=float, default=0, help="VideoFile End Time in s (0: the natural end)")
    ap.add_argument("--looping", type=int, default=1, choices=(0, 1))
    ap.add_argument("--keep", help="write the clip and project here instead of a temp folder")
    a = ap.parse_args()
    if a.port in (9201, 9202, 6454):
        raise SystemExit("port reserved")
    tmp = tempfile.TemporaryDirectory()
    folder = a.keep or tmp.name
    os.makedirs(folder, exist_ok=True)
    make_clip(os.path.join(folder, "counter.mov"))
    project = os.path.join(folder, "restart_check.magic")
    make_project(project, a.port, a.end_time, a.looping)
    print("check:", subprocess.run([sys.executable, os.path.join(HERE, "..", "..", "magic", "magicproj.py"), "check", project],
                                   capture_output=True, text=True).stdout.strip().splitlines()[-1])
    subprocess.run([sys.executable, os.path.join(HERE, "..", "..", "magic", "magicproj.py"), "load", project], check=True)
    time.sleep(5)                                   # the clip has played once and ended: the hold is on screen
    seconds, hz = PULSES[-1] + 6, 30
    proc = subprocess.Popen(["python3.13", os.path.abspath(__file__), "--sample", str(seconds), str(hz)],
                            stdout=subprocess.PIPE, text=True, env=dict(os.environ, **PY313))
    first = proc.stdout.readline()
    t0 = float(first.split()[0])
    sock_value, sent = 0, []
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for p in PULSES:
        time.sleep(max(0, t0 + p - time.time()))
        sock_value = 1 - sock_value
        sock.sendto(heartbeat.message(sock_value, ADDRESS), ("127.0.0.1", a.port))
        sent.append(time.time())
    rows = [(float(l.split()[0]), float(l.split()[1])) for l in [first] + proc.stdout.read().splitlines() if l.strip()]
    proc.wait()
    rows_rel = [(t - t0, v) for t, v in rows]
    sent_rel = [t - t0 for t in sent]
    for t, v in rows_rel:
        print("%.3f %.1f frame~%.1f" % (t, v, v / STEP))
    lines, ok = analyse(rows_rel, sent_rel)
    print("\n".join(lines))
    print("RESULT:", "pass" if ok else "fail")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
