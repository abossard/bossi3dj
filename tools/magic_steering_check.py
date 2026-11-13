#!/usr/bin/env python3
"""Magic's music steering and the takeover, read from the Blender scene page. Run with the scene open (`make blender-open`),
show.magic open in Magic and music playing into Magic's audio input.

    python3 tools/magic_steering_check.py [--observe 180] [--key vj_height] [--base http://127.0.0.1:9210]

observe: samples /api/state every half second. Passes when /vj/path and /vj/target each change at least once (drops, every 16 bars)
         and /vj/height moves by at least 2 % of its range, all from OSC. Prints each change with its time.
touch:   sets `--key` from the page to a value far from Magic's, like a hand on the fader. Passes when the scene keeps that value for
         the takeover pause while Magic still sends the address, and Magic's value is back (source osc) within 5 s after the pause.
         When Magic sent nothing during the pause there is nothing to return: reported as "no music", not as a failure.
The touched control is left to Magic. Reads only http; binds no port. Standard library only.
"""
import argparse
import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:9210"
STEERED = ("vj_path", "vj_target", "vj_height")
STEP = 0.5
BACK_WITHIN = 5.0


def call(base, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def address(key):
    return "/" + key.replace("_", "/", 1)


def sample(base):
    s = call(base, "/api/state")
    osc = s.get("osc") or {}
    return {"t": time.time(), "values": s["values"], "source": osc.get("source", {}),
            "n": {a: x["n"] for a, x in (osc.get("addresses") or {}).items()}, "controls": s["controls"]}


def changes(samples, key):
    """[(seconds from start, old, new, source)] for every change of the scene value of `key`."""
    out = []
    for a, b in zip(samples, samples[1:]):
        if abs(b["values"].get(key, 0.0) - a["values"].get(key, 0.0)) > 1e-6:
            out.append((round(b["t"] - samples[0]["t"], 1), a["values"].get(key), b["values"].get(key), b["source"].get(key)))
    return out


def observe(base, seconds):
    samples = []
    end = time.time() + seconds
    while time.time() < end:
        samples.append(sample(base))
        time.sleep(STEP)
    rng = {c["key"]: c["max"] - c["min"] for c in samples[-1]["controls"]}
    ok = True
    for key in STEERED:
        ch = changes(samples, key)
        sent = samples[-1]["n"].get(address(key), 0) - samples[0]["n"].get(address(key), 0)
        vals = [s["values"].get(key, 0.0) for s in samples]
        span = max(vals) - min(vals)
        if key == "vj_height":
            good = span >= 0.02 * rng.get(key, 1.0) and any(c[3] == "osc" for c in ch)
        else:
            good = any(c[3] == "osc" for c in ch)
        ok &= good
        print("%s %-10s %d changes, %d OSC messages, span %.3f" % ("ok  " if good else "FAIL", key, len(ch), sent, span))
        for c in ch[:12] if key != "vj_height" else []:
            print("       t=%6.1f s  %s -> %s  (%s)" % c)
    return ok


def touch(base, key):
    s = sample(base)
    c = next(x for x in s["controls"] if x["key"] == key)
    pause = s["values"].get("vj_takeover", 20.0)
    now_v = s["values"][key]
    mine = c["min"] + (0.1 if now_v - c["min"] > (c["max"] - c["min"]) / 2 else 0.9) * (c["max"] - c["min"])
    n0 = s["n"].get(address(key), 0)
    call(base, "/api/set", {key: mine})
    t0 = time.time()
    print("touch %s: Magic's %.3f -> page %.3f, takeover pause %.1f s" % (key, now_v, mine, pause))
    held, back_at, last = True, None, None
    while time.time() - t0 < pause + BACK_WITHIN + 2:
        time.sleep(STEP)
        last = sample(base)
        dt = time.time() - t0
        v = last["values"][key]
        if dt < pause - 1 and abs(v - mine) > 1e-6:
            held = False
            print("       t=%5.1f s  value %.3f (%s) during the pause" % (dt, v, last["source"].get(key)))
        if dt >= pause and back_at is None and abs(v - mine) > 1e-6 and last["source"].get(key) == "osc":
            back_at = dt
    sent = last["n"].get(address(key), 0) - n0
    print("%s held for the pause" % ("ok  " if held else "FAIL"))
    if back_at is not None:
        good = back_at <= pause + BACK_WITHIN
        print("%s Magic's value back after %.1f s (%.3f), %d OSC messages meanwhile" % ("ok  " if good else "FAIL", back_at, last["values"][key], sent))
        return held and good
    if sent == 0:
        print("no music: Magic sent %s nothing during the pause, so nothing returns (is music playing?)" % address(key))
        return held
    print("FAIL Magic sent %d messages but the value is still the page's %.1f s after the pause" % (sent, BACK_WITHIN + 2))
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", default=BASE)
    ap.add_argument("--observe", type=float, default=180.0, help="seconds of music to watch")
    ap.add_argument("--key", default="vj_height", help="the control a page touch takes over")
    a = ap.parse_args()
    ok = observe(a.base, a.observe)
    ok &= touch(a.base, a.key)
    print("steering check: %s" % ("passed" if ok else "failed"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
