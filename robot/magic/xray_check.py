"""Live check of xray.py in Magic: a synthetic track at 124 BPM plays into Source 0 and the Globals come back as OSC.

    python3 robot/magic/xray_check.py [--port 19408] [--keep DIR]

The track (4 beats a bar): bars 0-3 kick only, 4-11 kick and sub-bass (drop), 12-15 a pad (breakdown), 16-19 pad and snare roll
(buildup), 20-23 kick and sub-bass (drop). Magic sends Beats, BeatFrac, Bpm, State, Section, Tier and Move to 127.0.0.1:PORT (a spare
port, never 9201 or 9202). The check prints when each value changes and tests: the tempo, a bar line every multiple of 4 beats, the
sections in order, and the Tier changing only on a bar line, one section behind State. Needs the project to be loaded and played by
this script (magicproj load, then play, which brings Magic to the front): the user dismisses a "Save Changes?" sheet if it shows.
"""
import argparse
import math
import os
import random
import socket
import struct
import subprocess
import sys
import tempfile
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "osc"))
import robot_magic as rm  # noqa: E402
from lab import parse_packet  # noqa: E402
from manifest import load  # noqa: E402

BPM, RATE, BARS = 124, 44100, 24
SPB = 60.0 / BPM
PROBE = ["Beats", "BeatFrac", "Bpm", "State", "Section", "Tier", "Move", "Playing", "PlayT", "Volume", "KickRaw", "Kick", "KickPulse", "BpmFold", "KickRate"]
SECTIONS = [(0, 4, 0), (4, 12, 3), (12, 16, 4), (16, 20, 2), (20, 24, 3)]     # bar from, bar to, State expected
MAGICPROJ = os.path.join(HERE, "..", "..", "magic", "magicproj.py")


def track(path):
    rnd = random.Random(1)
    n = int(BARS * 4 * SPB * RATE)
    frames = bytearray()
    for i in range(n):
        t = i / RATE
        beat, bar = t / SPB, int(t / SPB / 4)
        into = (beat - math.floor(beat)) * SPB
        v = 0.0
        kick_bar = bar < 12 or bar >= 20
        if kick_bar:
            v += 1.0 * math.exp(-into * 9) * math.sin(2 * math.pi * (120 + 60 * math.exp(-into * 30)) * t)
        if bar >= 4 and bar < 12 or bar >= 20:
            v += 0.25 * math.sin(2 * math.pi * 50 * t)
        if 12 <= bar < 20:
            v += 0.15 * math.sin(2 * math.pi * 440 * t)
        if 16 <= bar < 20:
            into8 = (t % (SPB * 4 / 8))
            v += 0.35 * math.exp(-into8 * 40) * (rnd.random() * 2 - 1)
        frames += struct.pack("<h", int(max(-1, min(1, v)) * 30000))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))


def make_project(folder, port, wav):
    pkg = os.path.join(HERE, "..", "package", "fixture", "manifest.json")
    m = load(pkg)
    b = rm.build(m, osc_in=port + 1)
    b.glob("Playing", 0, "internal:Audio/MIDI Playing")
    b.glob("PlayT", 0, "internal:Playback Time")
    probe = b.scene("Probe")
    probe.output(*[probe.node("OSCSender", {"IP Addr.": "127.0.0.1", "Port": port, "Message": "/probe/" + n,
                                            "Value": ("global:" + n, [], 0)}) for n in PROBE])
    b._scenes[0].outputs.append(b._scenes[0].scene_module(probe))
    root = b.build()
    root = rm.mp.add_audio(root, wav, source="Source 0", loop=False)
    path = os.path.join(folder, "xray_check.magic")
    rm.mp.write(path, root)
    return path


def check(events):
    """events: (t, name, value) with t in s from the first Beats value. Returns (lines, ok)."""
    lines, ok = [], True
    by = {n: [(t, v) for t, name, v in events if name == n] for n in PROBE}
    bpm = by["Bpm"][-1][1] if by["Bpm"] else 0
    good = abs(bpm - BPM) < 3
    lines.append("tempo at the end (sent on change): %.1f (want %d +-3): %s" % (bpm, BPM, good))
    lines.append("audio: Playing events %s, peak Volume %.2f, peak KickRaw %.2f" % (
        [(round(t, 1), v) for t, v in by["Playing"]][:4], max([v for _t, v in by["Volume"]] or [0]), max([v for _t, v in by["KickRaw"]] or [0])))
    ok &= good
    beats = by["Beats"]
    steps = [(t1, v1 - v0) for (t0, v0), (t1, v1) in zip(beats, beats[1:])]
    big = [(round(t, 2), d) for t, d in steps if d != 1]
    lines.append("Beats: %d changes, steps that are not +1: %s" % (len(steps), big[:8]))
    ok &= len(steps) > 60 and all(d >= 1 for _t, d in steps)
    states = []
    for t, v in by["State"]:
        if not states or states[-1][1] != v:
            states.append((t, v))
    seq = [int(v) for _t, v in states]
    lines.append("State changes (s, State): %s" % [(round(t, 1), int(v)) for t, v in states])
    good = [s for s in seq if s != 0][:4] == [3, 4, 2, 3]
    lines.append("sections in order drop, breakdown, buildup, drop: %s" % good)
    ok &= good
    tiers, last = [], None
    for t, v in by["Tier"]:
        if v != last:
            tiers.append((t, v))
            last = v
    beat_at = lambda t: next((v for tb, v in reversed(beats) if tb <= t), 0)
    lines.append("Tier changes (s, beat, Tier): %s" % [(round(t, 1), int(beat_at(t)), int(v)) for t, v in tiers])
    off_bar = [(round(t, 1), beat_at(t)) for t, v in tiers[1:] if beat_at(t) % 4 != 0]
    lines.append("Tier changes off a bar line: %s" % off_bar)
    ok &= not off_bar
    want = {0: 0, 2: 1, 3: 2, 4: 0}
    tier_after = lambda t: next((v for tt, v in reversed(tiers) if tt <= t), 0)
    for (t, v) in states[1:]:
        later = tier_after(t + 2 * 4 * SPB)
        good = later == want[int(v)]
        lines.append("State %d at %.1f s: Tier two bars later %d (want %d): %s" % (int(v), t, later, want[int(v)], good))
        ok &= good
    return lines, ok


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", type=int, default=19408)
    ap.add_argument("--keep")
    a = ap.parse_args()
    tmp = tempfile.TemporaryDirectory()
    folder = a.keep or tmp.name
    os.makedirs(folder, exist_ok=True)
    wav = os.path.join(folder, "xray_track.wav")
    track(wav)
    project = make_project(folder, a.port, wav)
    print("check:", subprocess.run([sys.executable, MAGICPROJ, "check", project], capture_output=True, text=True).stdout.strip().splitlines()[-1])
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", a.port))
    sock.settimeout(0.2)
    subprocess.run([sys.executable, MAGICPROJ, "load", project], check=True)
    time.sleep(3)
    subprocess.run([sys.executable, MAGICPROJ, "play"], check=True)
    t0, events, end = None, [], time.time() + BARS * 4 * SPB + 6
    while time.time() < end:
        try:
            data, _ = sock.recvfrom(65535)
        except socket.timeout:
            continue
        now = time.time()
        for addr, _tags, args, _b in parse_packet(data):
            name = addr.rsplit("/", 1)[1]
            if t0 is None and name == "Playing" and args[0] > 0.5:
                t0 = now
            if name in PROBE:
                events.append((now - (t0 if t0 is not None else now), name, args[0]))
    subprocess.run([sys.executable, MAGICPROJ, "play"])
    with open(os.path.join(folder, "xray_events.txt"), "w") as f:
        f.write("".join("%.3f %s %s\n" % e for e in events))
    lines, ok = check(events)
    print("\n".join(lines))
    print("RESULT:", "pass" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
