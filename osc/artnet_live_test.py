#!/usr/bin/env python3
"""Sender-only live test of the Blender bridge's Art-Net input (no QLC+). Run with a Blender open on the planet scene:

    python3 osc/artnet_live_test.py [--page http://127.0.0.1:9210]

Sends ArtDmx frames to 127.0.0.1:6454 with osc/artnet_send.py's frame builder and one OSC packet to udp 9201 (sending is allowed,
binding is not), and reads every result back from the page's API (/api/state: values, osc.source, osc.log, camera). Writes the
table to stdout as Markdown. It touches vj_fog_glow, vj_target, vj_shock and the holds, and puts them back at the end. Standard library."""
import argparse
import json
import os
import socket
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "blender"))
import artnet_input  # noqa: E402
import artnet_send  # noqa: E402
import blender_osc_bridge as bridge  # noqa: E402
import qlc_fixture  # noqa: E402

PAGE = "http://127.0.0.1:9210"
ORDER = [r["address"] for r in qlc_fixture.blender_rows()]
TARGET_CHANNEL = ORDER.index("/vj/target") + 1
SETTLE = 0.4


def get(path):
    with urllib.request.urlopen(PAGE + path, timeout=10) as r:
        return json.loads(r.read())


def post(path, body):
    req = urllib.request.Request(PAGE + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10).read()


def state():
    s = get("/api/state")
    return s["values"], s["osc"], s["camera"]


def send_frames(sets, baseline=False, frames=3, universe=0, raw=None):
    """Frames to the bridge like a desk: all channels at the fixture defaults, the sets on top, repeated."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    base, _ = artnet_send.build([], 1)
    frame, triggers = artnet_send.build(sets, 1)
    if raw:
        frame = bytearray(frame)
        for ch, v in raw.items():
            frame[ch - 1] = v
        frame = bytes(frame)
    seq = 0
    seq_frames = ([base] if baseline else []) + [frame] * frames
    if triggers:
        rel = bytearray(frame)
        for t in triggers:
            rel[t] = 0
        seq_frames.append(bytes(rel))
    for f in seq_frames:
        seq = seq % 255 + 1
        sock.sendto(artnet_input.encode_artdmx(universe, f, seq), ("127.0.0.1", artnet_input.ARTNET_PORT))
        time.sleep(0.05)
    time.sleep(SETTLE)
    sock.close()


def send_osc(address, value):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.sendto(bridge.encode_message(address, [float(value)]), ("127.0.0.1", bridge.PORT))
    s.close()
    time.sleep(SETTLE)


def main():
    global PAGE
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", default=PAGE)
    PAGE = ap.parse_args().page
    values0, osc0, camera0 = state()
    hold0 = list(osc0["hold"])
    rows = []

    def row(name, ok, detail):
        rows.append((name, "ok" if ok else "FAIL", detail))
        print("%-4s %-46s %s" % ("ok" if ok else "FAIL", name, detail), file=sys.stderr, flush=True)

    # (a) the first frame is the baseline, the frames after it hold the same values: nothing changes
    v_before, osc_b, _ = state()
    send_frames([], baseline=True, frames=4)
    v, osc, _ = state()
    row("a baseline and equal frames change nothing", v == v_before and osc["applied"] == osc_b["applied"],
        "values equal, applied %d -> %d" % (osc_b["applied"], osc["applied"]))

    # (b) a changed slider channel sets its control to the scaled value, source artnet
    send_frames(["/vj/fog_glow=0.25"], frames=3)
    v, osc, _ = state()
    row("b changed channel sets the control (source artnet)", abs(v["vj_fog_glow"] - 0.5) < 0.01 and osc["source"].get("vj_fog_glow") == "artnet",
        "vj_fog_glow %.3f (wire 0.25 = scene 0.5), source %s" % (v["vj_fog_glow"], osc["source"].get("vj_fog_glow")))

    # (c) Takeover: after an Art-Net touch, Magic's OSC value is kept, not applied, until /vj/takeover has passed; then it is
    # applied, and frames that repeat the touched value (a resting fader) do not take it back
    send_osc("/vj/fog_glow", 0.75)
    v1, osc1, _ = state()
    pause = float(v1.get("vj_takeover", 20.0))
    time.sleep(pause + 1.0)
    v2, osc2, _ = state()
    send_frames(["/vj/fog_glow=0.25"], frames=4)
    v3, osc3, _ = state()
    row("c takeover: Magic waits for the pause, a resting channel does not take it back",
        abs(v1["vj_fog_glow"] - 0.5) < 0.01 and osc1["source"].get("vj_fog_glow") == "artnet"
        and abs(v2["vj_fog_glow"] - 1.5) < 0.01 and osc2["source"].get("vj_fog_glow") == "osc" and abs(v3["vj_fog_glow"] - 1.5) < 0.01,
        "OSC 0.75 right after the touch: %.3f (source %s); after the %.0f s pause: %.3f (source %s); after 4 equal frames %.3f" % (
            v1["vj_fog_glow"], osc1["source"].get("vj_fog_glow"), pause, v2["vj_fog_glow"], osc2["source"].get("vj_fog_glow"), v3["vj_fog_glow"]))

    # (d) a trigger rising through 128 fires once: the log has one rise (strength 0.5 or more) and then one fall to 0 for /vj/shock
    t0 = time.time()
    send_frames(["/vj/shock=1"], frames=6)
    log = get("/api/state")["osc"]["log"]
    args = [m[3][0] for m in log if m[2] == "/vj/shock" and m[0] >= t0]
    row("d trigger fires once on the rise through 128", len([a for a in args if a >= 0.5]) == 1 and args.count(0.0) == 1,
        "/vj/shock in the log: %s" % ", ".join("%.2f" % a for a in args))

    # (e) an index channel picks by equal ranges: /vj/target, 7 targets
    cases = [(0, 0), (36, 0), (37, 1), (146, 3), (147, 4), (219, 5), (220, 6), (255, 6)]
    bad, seen = [], {}
    send_frames([], frames=1, raw={TARGET_CHANNEL: 128})
    for dmx, want in cases:
        send_frames([], frames=2, raw={TARGET_CHANNEL: dmx})
        got = state()[0]["vj_target"]
        seen[dmx] = got
        if int(round(got)) != want:
            bad.append((dmx, want, got))
    row("e index channel picks /vj/target by range (7 targets)", not bad,
        "DMX -> vj_target: " + ", ".join("%d -> %d" % (k, v) for k, v in seen.items()) + (" MISMATCH %s" % bad if bad else ""))

    # (f) a held control ignores Art-Net
    post("/api/hold", {"keys": ["vj_fog_glow"], "on": True})
    time.sleep(0.2)
    before = state()[0]["vj_fog_glow"]
    send_frames(["/vj/fog_glow=0.9"], frames=3)
    after, osc, _ = state()
    row("f held control ignores Art-Net", abs(after["vj_fog_glow"] - before) < 1e-6 and osc["held"] > 0,
        "vj_fog_glow %.3f -> %.3f, held counter %d" % (before, after["vj_fog_glow"], osc["held"]))
    post("/api/hold", {"keys": ["vj_fog_glow"], "on": False})

    # (g) another universe is ignored
    before = state()[0]["vj_fog_glow"]
    send_frames([], baseline=True, frames=1, universe=1)
    send_frames(["/vj/fog_glow=0.0"], frames=3, universe=1)
    after = state()[0]["vj_fog_glow"]
    row("g other universe is ignored", abs(after - before) < 1e-6, "vj_fog_glow %.3f -> %.3f with frames to universe 1" % (before, after))

    # the baseline again, then every touched value back to what it was
    send_frames([], baseline=True, frames=2)
    post("/api/set", {k: values0[k] for k in ("vj_fog_glow", "vj_target", "vj_shock") if k in values0})
    post("/api/hold", {"keys": [k for k in ("vj_fog_glow",) if k not in hold0], "on": False})
    time.sleep(SETTLE)
    values_end, osc_end, camera_end = state()
    diff = {k: (values0[k], values_end[k]) for k in values0 if abs(values0[k] - values_end[k]) > 1e-6}
    row("restore: every value as it was", not diff and sorted(osc_end["hold"]) == sorted(hold0),
        "camera %s -> %s%s" % (camera0, camera_end, ", differences: %s" % diff if diff else ""))
    print("\n| Row | Result | What was read back |\n|---|---|---|")
    for r in rows:
        print("| %s | %s | %s |" % r)
    return 0 if all(r[1] == "ok" for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
