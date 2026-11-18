"""The live test track's kick band as X-Ray's KickRaw would see it, for a replay without Magic. Stdlib only.

    python3 robot/magic/kick_band.py [--out robot/magic/tests/data/kickband-live-track.txt]

Renders live_test.py's track in memory, filters it with a band-pass of 80-320 Hz (RBJ biquad, centre 160 Hz, Q 0.67: like Magic's
80-320 Hz range, it lets some of the drop's 50 Hz sub-bass through) and writes the RMS over 23 ms (a 1024-sample window) every 10 ms,
one "t value" line per frame, t in s from the track's first sample. Magic's band values have another scale; the replay test fits it.
"""
import argparse
import math
import os
import struct
import sys
import tempfile
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import live_test  # noqa: E402

OUT = os.path.join(HERE, "tests", "data", "kickband-live-track.txt")
FPS, WINDOW = 100, 1024


def bandpass(samples, rate, lo=80.0, hi=320.0):
    f0 = math.sqrt(lo * hi)
    q = f0 / (hi - lo)
    w = 2 * math.pi * f0 / rate
    alpha = math.sin(w) / (2 * q)
    a0 = 1 + alpha
    b0, b2, a1, a2 = alpha / a0, -alpha / a0, -2 * math.cos(w) / a0, (1 - alpha) / a0
    x1 = x2 = y1 = y2 = 0.0
    out = []
    for x in samples:
        y = b0 * x + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, x, y1, y
        out.append(y)
    return out


def band_series(path):
    with wave.open(path) as w:
        rate, n = w.getframerate(), w.getnframes()
        samples = [v / 32768.0 for v in struct.unpack("<%dh" % n, w.readframes(n))]
    y = bandpass(samples, rate)
    sq = [0.0]
    for v in y:
        sq.append(sq[-1] + v * v)
    hop = rate // FPS
    return [(i / FPS, math.sqrt(max(0.0, sq[min(len(y), i * hop + WINDOW)] - sq[i * hop]) / WINDOW)) for i in range(len(y) // hop)]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "track.wav")
        live_test.track(wav)
        rows = band_series(wav)
    with open(a.out, "w") as f:
        f.write("".join("%.2f %.5f\n" % r for r in rows))
    print("wrote %s (%d frames)" % (a.out, len(rows)))


if __name__ == "__main__":
    main()
