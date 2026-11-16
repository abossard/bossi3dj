"""R8, the Robot's live test in Magic: 90 s of the show project on a fixed 124 BPM track, recorded and logged.

    python3 robot/magic/live_test.py prepare MANIFEST          # track + project (robot_live_test.magic), nothing touches Magic
    python3 robot/magic/live_test.py run                      # Magic has the project loaded by the user; 90 s run, recording, event log
    python3 robot/magic/live_test.py analyze MANIFEST          # numbers from the last run
    python3 robot/magic/live_test.py note                     # BEFORE the user loads the test project: records what Magic holds now (read-only)
    python3 robot/magic/live_test.py restore                  # AFTER the run: loads that project back with magicproj load and confirms it

The project is the show's robot.magic (generator defaults: auto cuts on, every Angle playing, Live World off through the heartbeat
fallback) plus a Probe scene that sends the Globals below to 127.0.0.1:PROBE_PORT. The track is played with afplay to the default output
(BlackHole 2ch, as B11's full test did); Magic's audio input is the user's setting, a restart may need it picked again. The run never
loads, never drives Magic's UI and never binds 9201, 9202 or 6454. Work files: robot/magic/live/ (git-ignored); the video goes to
docs/video/robot-live-test.mp4 (git-ignored).
"""
import argparse
import json
import math
import os
import random
import socket
import statistics
import struct
import subprocess
import sys
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "osc"))
sys.path.insert(0, os.path.join(ROOT, "magic"))
LIVE = os.path.join(HERE, "live")
EVENTS = os.path.join(LIVE, "events.txt")
TRACK = os.path.join(LIVE, "robot_live_track.wav")
PROJECT = os.path.join(LIVE, "robot_live_test.magic")
VIDEO = os.path.join(ROOT, "docs", "video", "robot-live-test.mp4")
FLAG = os.path.join(LIVE, "go.flag")
HELD = os.path.join(LIVE, "held_project.txt")
SYPHON_RECORD = os.path.join(ROOT, "tools", "syphon_record.py")
FLICKER = os.path.join(ROOT, "blender", "review", "video_flicker.py")
FFMPEG = "/opt/homebrew/bin/ffmpeg"
PY313 = {"PYTHONPATH": os.path.expanduser("~/.local/lib/python3.13/site-packages")}

PROBE_PORT, BPM, RATE, FPS, SECONDS = 19420, 124, 44100, 30, 90
SPB = 60.0 / BPM
PROBE = ["Beats", "Bpm", "State", "Section", "Tier", "Move", "Angle", "OutClip", "OutFrame", "IsIdle", "MoveStart", "Volume", "Fps"]
# bars, layers: kick on every beat, sub-bass, pad, snare roll (eighth notes). The section names are what the track means, not what X-Ray reads.
PLAN = [(4, "intro", "k"), (8, "drop", "ks"), (4, "breakdown", "p"), (4, "buildup", "pr"), (8, "drop", "ks"),
        (4, "breakdown", "p"), (4, "buildup", "pr"), (12, "drop", "ks")]
TIER_OF_SECTION = {3: 2, 2: 1}       # Music X-Ray State: 3 drop is drop (2), 2 buildup is build (1), the rest calm (0)


# ------------------------------------------------------------ track

def layers_at(bar, plan=PLAN):
    start = 0
    for bars, name, layers in plan:
        if bar < start + bars:
            return name, layers
        start += bars
    return plan[-1][1], plan[-1][2]


def track(path, plan=PLAN):
    rnd = random.Random(1)
    bars = sum(p[0] for p in plan)
    frames = bytearray()
    for i in range(int(bars * 4 * SPB * RATE)):
        t = i / RATE
        beat = t / SPB
        bar = int(beat / 4)
        into = (beat - math.floor(beat)) * SPB
        layers = layers_at(bar, plan)[1]
        v = 0.0
        if "k" in layers:
            v += math.exp(-into * 9) * math.sin(2 * math.pi * (120 + 60 * math.exp(-into * 30)) * t)
        if "s" in layers:
            v += 0.25 * math.sin(2 * math.pi * 50 * t)
        if "p" in layers:
            v += 0.15 * math.sin(2 * math.pi * 440 * t)
        if "r" in layers:
            v += 0.35 * math.exp(-(t % (SPB / 2)) * 40) * (rnd.random() * 2 - 1)
        frames += struct.pack("<h", int(max(-1, min(1, v)) * 30000))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))


# ------------------------------------------------------------ project

def make_project(manifest_path, out=PROJECT, port=PROBE_PORT):
    import robot_magic as rm
    from manifest import load
    m = load(manifest_path)
    folder = os.path.dirname(os.path.abspath(out))
    b = rm.build(m, project_dir=folder)
    probe = b.scene("Probe")
    b.glob("Fps", 0, "internal:Graphics FPS")
    probe.output(*[probe.node("OSCSender", {"IP Addr.": "127.0.0.1", "Port": port, "Message": "/probe/" + n, "Value": ("global:" + n, [], 0)})
                   for n in PROBE])
    b._scenes[0].outputs.append(b._scenes[0].scene_module(probe))
    root = b.build()
    for iv in root.iter("InputValue"):
        if iv.get("name") == "File" and iv.get("value"):
            iv.set("absoluteFilename", os.path.normpath(os.path.join(folder, iv.get("value"))))
    rm.mp.write(out, root)
    return out


# ------------------------------------------------------------ numbers (pure)

def series(events, name):
    """[(t, v)] of one probe name, as received."""
    return [(t, v) for t, n, v in events if n == name]


def value_at(ser, t, default=0.0):
    last = default
    for ts, v in ser:
        if ts > t:
            break
        last = v
    return last


def changes(ser):
    out, last = [], None
    for t, v in ser:
        if v != last:
            out.append((t, v))
            last = v
    return out


def pct(values, p):
    s = sorted(values)
    return s[min(len(s) - 1, int(p / 100.0 * len(s)))] if s else None


def tier_of_section(section):
    return TIER_OF_SECTION.get(int(round(section)), 0)


def fps_numbers(events):
    v = [x for _t, x in series(events, "Fps") if x > 1]
    return {"median": round(statistics.median(v), 1), "p5": round(pct(v, 5), 1), "min": round(min(v), 1)} if v else {}


def cut_times(events, fps=FPS):
    """Move changes and Angle cuts: (t, kind, frames after the latest Beats event, Beats at that event, Move index, Angle). The Clip changes
    when OutClip does; a Move change moves Move, a cut moves only Angle."""
    beats = series(events, "Beats")
    moves, angles = changes(series(events, "Move")), changes(series(events, "Angle"))
    out = []
    move_ts = [t for t, _ in moves[1:]]
    for t, v in moves[1:]:
        tb, b = max(((tb, b) for tb, b in beats if tb <= t), default=(t, 0))
        out.append((t, "move", (t - tb) * fps, b, int(v), int(value_at(series(events, "Angle"), t))))
    for t, v in angles[1:]:
        if any(abs(t - tm) < 0.1 for tm in move_ts):
            continue
        tb, b = max(((tb, b) for tb, b in beats if tb <= t), default=(t, 0))
        out.append((t, "cut", (t - tb) * fps, b, int(value_at(series(events, "Move"), t)), int(v)))
    return sorted(out)


def per_tier(events, cuts):
    """Per tier interval: bars, Move changes, cuts. Totals per tier with changes per bar."""
    tiers = changes(series(events, "Tier"))
    if not tiers:
        return {}
    end = max(t for t, _n, _v in events)
    spans = [(t, tiers[i + 1][0] if i + 1 < len(tiers) else end, int(v)) for i, (t, v) in enumerate(tiers)]
    out = {}
    for a, b, tier in spans:
        row = out.setdefault(tier, {"seconds": 0.0, "moves": 0, "cuts": 0})
        row["seconds"] += b - a
        row["moves"] += sum(1 for c in cuts if a <= c[0] < b and c[1] == "move")
        row["cuts"] += sum(1 for c in cuts if a <= c[0] < b and c[1] == "cut")
    for row in out.values():
        bars = row["seconds"] / (SPB * 4)
        row.update(bars=round(bars, 1), moves_per_bar=round(row["moves"] / bars, 2) if bars else 0, cuts_per_bar=round(row["cuts"] / bars, 2) if bars else 0)
        row["seconds"] = round(row["seconds"], 1)
    return out


def tier_vs_state(events, fps=FPS):
    """At each bar line the Tier must be the section's tier a frame earlier (latched in the frame of the Beats event). Returns (checked, mismatches [(t, beat, section, tier)])."""
    beats, section, tier = series(events, "Beats"), series(events, "Section"), series(events, "Tier")
    checked, bad = 0, []
    for t, b in changes(beats):
        if int(b) % 4:
            continue
        want = tier_of_section(value_at(section, t - 2.0 / fps))
        got = value_at(tier, t + 3.0 / fps)
        checked += 1
        if int(got) != want:
            bad.append((round(t, 2), int(b), value_at(section, t - 2.0 / fps), got))
    return checked, bad


def tier_off_bar(events):
    """Tier changes that do not happen at a Beats multiple of 4: [(t, beat)]."""
    beats = series(events, "Beats")
    return [(round(t, 2), int(value_at(beats, t))) for t, _v in changes(series(events, "Tier"))[1:] if int(value_at(beats, t)) % 4]


def bar_offset_ms(events, t_audio):
    """Magic's bar lines (Beats multiple of 4) against the track's true bar lines (the first kick at t_audio): ms, median and max abs."""
    off = []
    for t, b in changes(series(events, "Beats")):
        if int(b) % 4 or t < t_audio + 12:
            continue
        k = round((t - t_audio) / (SPB * 4))
        off.append((t - t_audio - k * SPB * 4) * 1000)
    return {"n": len(off), "median_ms": round(statistics.median(off)), "max_abs_ms": round(max(abs(x) for x in off))} if off else {}


def idle_seams(events, move_frames):
    """Times where an Idle Move's OutFrame wraps (drops by more than half its length): [(t, from, to)]."""
    frames, idle = series(events, "OutFrame"), series(events, "IsIdle")
    out, last = [], None
    for t, f in frames:
        if last is not None and f < last - move_frames / 2 and value_at(idle, t) > 0.5:
            out.append((t, last, f))
        last = f
    return out


def video_series(path, fps=FPS, w=192, h=108):
    """Per decoded frame of VIDEO: (mean luma, lit share over 16, mean abs difference to the previous frame), from ffmpeg gray frames."""
    raw = subprocess.run([FFMPEG, "-v", "0", "-i", path, "-vf", "scale=%d:%d" % (w, h), "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    n, prev, out = w * h, None, []
    for i in range(len(raw) // n):
        f = raw[i * n:(i + 1) * n]
        d = sum(abs(a - b) for a, b in zip(f, prev)) / n if prev is not None else 0.0
        out.append((sum(f) / n, sum(1 for p in f if p > 16) / n, d))
        prev = f
    return out


def picture_numbers(v, cut_ts=(), fps=FPS, black_lit=0.001, stale_diff=0.02):
    """Black frames (no lit pixel above the threshold share), stale frames (no change to the one before) and diff spikes of a video series.
    A spike within 0.15 s of a cut or Move change (cut_ts, s on the video clock) is expected; the others count as unexplained."""
    lit = [x[1] for x in v]
    diffs = [x[2] for x in v[1:]]
    black = sum(1 for x in lit if x < black_lit)
    stale = sum(1 for x in diffs if x < stale_diff)
    med = statistics.median(diffs) if diffs else 0
    spikes = [(i + 1) / fps for i, d in enumerate(diffs) if med and d > 5 * med and d > 1.0]
    return {"frames": len(v), "black": black, "stale": stale, "lit_median": round(statistics.median(lit), 3), "diff_median": round(med, 3),
            "diff_p95": round(pct(diffs, 95), 2), "diff_max": round(max(diffs), 2), "spikes_over_5x_median": len(spikes),
            "spikes_unexplained": [round(t, 2) for t in spikes if not any(abs(t - c) < 0.15 for c in cut_ts)][:12]}


def seam_numbers(v, seams, fps=FPS):
    """Frame difference in the 3 frames around each Idle seam against the median difference of the video."""
    diffs = [x[2] for x in v]
    med = statistics.median(diffs[1:]) if len(diffs) > 1 else 0
    peaks = []
    for t, _a, _b in seams:
        i = int(t * fps)
        win = diffs[max(1, i - 3):i + 4]
        peaks.append(max(win) if win else 0)
    return {"seams": len(seams), "peak_median": round(statistics.median(peaks), 2) if peaks else None, "peak_max": round(max(peaks), 2) if peaks else None,
            "video_median": round(med, 2)}


def analyze(events, m, t_audio=0.0, video=None):
    cuts = cut_times(events)
    moves = [c for c in cuts if c[1] == "move"]
    checked, bad = tier_vs_state(events)
    out = {
        "fps": fps_numbers(events),
        "move_changes": len(moves), "cuts": len(cuts) - len(moves),
        "move_latency_frames": {"median": round(statistics.median([c[2] for c in moves]), 1), "max": round(max(c[2] for c in moves), 1)} if moves else {},
        "moves_on_bar_line": sum(1 for c in moves if c[3] % 4 == 0), "moves_off_bar_line": [(round(c[0], 2), c[3]) for c in moves if c[3] % 4],
        "cuts_off_cut_points": cuts_off_cut_points(cuts, m),
        "per_tier": per_tier(events, cuts),
        "tier_vs_state": {"bar_lines": checked, "mismatches": bad[:8], "n_mismatch": len(bad), "tier_changes_off_bar": tier_off_bar(events)},
        "bar_offset": bar_offset_ms(events, t_audio),
        "bpm_end": series(events, "Bpm")[-1][1] if series(events, "Bpm") else None,
        "states": [(round(t, 1), int(v)) for t, v in changes(series(events, "State"))],
    }
    idle_frames = max((mv.frames for mv in m.moves if mv.idle), default=0)
    seams = idle_seams(events, idle_frames) if idle_frames else []
    if video is not None:
        out["picture"] = picture_numbers(video, [c[0] for c in cuts])
        out["seams"] = seam_numbers(video, seams)
    else:
        out["seams"] = {"seams": len(seams)}
    return out


def cuts_off_cut_points(cuts, m):
    """Angle cuts whose beat offset inside the Move is not one of the Move's cut_points: [(t, move, offset)]. The offset comes from the latest Beats event and
    MoveStart is not logged per cut, so it is Beats modulo the Move's length."""
    bad = []
    for t, kind, _lat, beats, move, _angle in cuts:
        if kind != "cut" or move >= len(m.moves):
            continue
        mv = m.moves[move]
        off = int(beats) % max(1, mv.beats)
        if off not in mv.cut_points:
            bad.append((round(t, 2), mv.name, off))
    return bad


# ------------------------------------------------------------ the project Magic holds before the test

def editor_title(windows):
    """The project file name of the editor window ("show.magic - Editor"), or None."""
    return next((w[:-len(" - Editor")] for w in windows or [] if w.endswith(" - Editor")), None)


def find_project(name):
    """The one file of that name under the repo's magic/ folder, else None."""
    hits = [os.path.join(d, name) for d, _dirs, files in os.walk(os.path.join(ROOT, "magic")) if name in files]
    return hits[0] if len(hits) == 1 else None


def note_held():
    """Read-only: the project in Magic's editor window title, resolved to its path, written to HELD."""
    import magicproj
    wins = magicproj.magic_windows()
    name = editor_title(wins)
    path = find_project(name) if name else None
    if not path:
        raise SystemExit("cannot resolve Magic's project from its windows %s (Magic running? one file of that name under magic/?)" % wins)
    os.makedirs(LIVE, exist_ok=True)
    with open(HELD, "w") as f:
        f.write(path + "\n")
    print("Magic holds", path)


def restore_held():
    """Loads the noted project back with magicproj load: ok only when the editor title names it and no Error window is open."""
    import magicproj
    with open(HELD) as f:
        path = f.read().strip()
    ok, wins = magicproj.load(path)
    errors = [w for w in wins if w.startswith("Error")]
    print("restore %s: editor title %s, error windows %s, windows %s" % (path, "ok" if ok else "NOT confirmed", errors or "none", wins))
    return 0 if ok and not errors else 1


# ------------------------------------------------------------ run

def parse_events(path):
    out = []
    with open(path) as f:
        for line in f:
            t, n, v = line.split()
            out.append((float(t), n, float(v)))
    return out


def audio_onset(events, level=0.05):
    for t, v in series(events, "Volume"):
        if v > level:
            return t
    return 0.0


def collect(sock, seconds, t0, events):
    end = time.time() + seconds
    from lab import parse_packet
    while time.time() < end:
        try:
            data, _ = sock.recvfrom(65535)
        except socket.timeout:
            continue
        now = time.time()
        for addr, _tags, args, _b in parse_packet(data):
            name = addr.rsplit("/", 1)[1]
            if name in PROBE:
                events.append((now - t0, name, float(args[0])))


def preflight(sock):
    """The project must be loaded and running: the probe answers with a Fps above 1."""
    events = []
    collect(sock, 3, time.time(), events)
    fps = [v for _t, n, v in events if n == "Fps"]
    if not fps or max(fps) <= 1:
        raise SystemExit("no probe from Magic on %d (project not loaded, or not the live-test project)" % PROBE_PORT)
    print("probe ok: Fps %.1f, %d messages in 3 s" % (statistics.median(fps), len(events)))


def audio_check(sock):
    """Magic must hear the track: 6 s of it, then peak Volume above 0.1, then silence."""
    p = subprocess.Popen(["afplay", TRACK])
    events = []
    collect(sock, 6, time.time(), events)
    p.terminate()
    peak = max([v for _t, n, v in events if n == "Volume"] or [0])
    print("audio check: peak Volume %.2f" % peak)
    if peak < 0.1:
        raise SystemExit("Magic does not hear the track (peak Volume %.2f): pick BlackHole 2ch as Magic's audio input and the default output" % peak)
    quiet = time.time() + 15
    while time.time() < quiet:
        ev = []
        collect(sock, 1, time.time(), ev)
        if max([v for _t, n, v in ev if n == "Volume"] or [0]) < 0.01:
            return
    raise SystemExit("Magic's Volume did not fall to silence after the audio check")


def run():
    os.makedirs(LIVE, exist_ok=True)
    os.makedirs(os.path.dirname(VIDEO), exist_ok=True)
    if not os.path.exists(TRACK):
        raise SystemExit("no track: run prepare first")
    if not os.path.exists(HELD):
        raise SystemExit("no noted project to restore afterwards: run note while Magic still holds it, before the load")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", PROBE_PORT))
    sock.settimeout(0.2)
    preflight(sock)
    audio_check(sock)
    if os.path.exists(FLAG):
        os.remove(FLAG)
    rec = subprocess.Popen(["python3.13", SYPHON_RECORD, "--app", "Magic", "--server", "Main Server",
                            "--seconds", str(SECONDS), "--fps", str(FPS), "--size", "960x540", "--flag", FLAG, "--out", VIDEO],
                           env=dict(os.environ, **PY313), stdout=subprocess.PIPE, text=True)
    time.sleep(4)          # the recorder finds the server and waits for the flag
    events = []
    t0 = time.time()
    open(FLAG, "w").close()
    audio = subprocess.Popen(["afplay", TRACK])
    collect(sock, SECONDS + 2, t0, events)
    audio.terminate()
    out = rec.communicate()[0]
    os.remove(FLAG)
    with open(EVENTS, "w") as f:
        f.write("".join("%.4f %s %s\n" % e for e in events))
    print("recorder:", out.strip())
    print("events:", len(events), "->", EVENTS)


def sheet(video=VIDEO, out=os.path.join(LIVE, "sheet.png")):
    """One contact sheet for the shot-reviewer: 36 tiles of 480 px, one every SECONDS/36 s, left to right, top to bottom (6x6)."""
    subprocess.run([FFMPEG, "-y", "-v", "error", "-i", video, "-vf", "fps=36/%d,scale=480:270,tile=6x6" % SECONDS, "-frames:v", "1", out], check=True)
    return out


def analyze_cmd(manifest_path):
    from manifest import load
    m = load(manifest_path)
    events = parse_events(EVENTS)
    video = video_series(VIDEO) if os.path.exists(VIDEO) else None
    result = analyze(events, m, audio_onset(events), video)
    if os.path.exists(VIDEO):
        flick = subprocess.run([os.path.join(ROOT, ".venv", "bin", "python"), FLICKER, VIDEO, "15"], capture_output=True, text=True).stdout
        result["flicker"] = json.loads(flick) if flick.strip().startswith("{") else flick.strip()
        result["sheet"] = sheet()
    print(json.dumps(result, indent=1))
    with open(os.path.join(LIVE, "numbers.json"), "w") as f:
        json.dump(result, f, indent=1)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("command", choices=["prepare", "run", "analyze", "note", "restore"])
    ap.add_argument("manifest", nargs="?")
    a = ap.parse_args()
    if a.command == "run":
        return run()
    if a.command == "note":
        return note_held()
    if a.command == "restore":
        return restore_held()
    if not a.manifest:
        raise SystemExit("%s needs the MANIFEST" % a.command)
    if a.command == "prepare":
        os.makedirs(LIVE, exist_ok=True)
        track(TRACK)
        print("track:", TRACK, "(%d bars, %.1f s)" % (sum(p[0] for p in PLAN), sum(p[0] for p in PLAN) * 4 * SPB))
        project = make_project(a.manifest)
        print("check:", subprocess.run([sys.executable, os.path.join(ROOT, "magic", "magicproj.py"), "check", project], capture_output=True, text=True).stdout.strip().splitlines()[-1])
        return 0
    analyze_cmd(a.manifest)


if __name__ == "__main__":
    sys.exit(main())
