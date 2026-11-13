#!/usr/bin/env python3
"""Sends Art-Net (ArtDmx) frames to the Blender bridge, for tests and a first check without QLC+.

    python3 osc/artnet_send.py [HOST[:PORT]] [--universe 0] [--start 1] [--frames 5] [--rate 20] [--no-baseline] [--broadcast] SET ...

HOST defaults to 127.0.0.1, PORT to 6454. A SET is `/vj/fog=0.8` (the row's wire value: 0..1 for a float, 1 for a trigger at full
strength, the index for an index row such as /vj/target) or `N=V` (DMX channel N of the universe, value 0..255). Every frame holds all channels of the
fixture (qlc/bossi3dj-Synthwave-Planet.qxf) at their defaults from the DMX start address on, with the SETs on top, like a desk does.
The bridge takes the first frame it sees as its baseline and applies only what changes after it, so the sender first sends one
frame of defaults (--no-baseline skips it) and then --frames frames with the SETs. A trigger that was SET gets one last frame with
it back at 0, so the next send is a new rise. --dry-run prints the DMX values it would send. Standard library only."""
import argparse
import os
import socket
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "blender"))
import artnet_input  # noqa: E402
import qlc_fixture  # noqa: E402


def dmx_value(row, wire):
    """The DMX value a wire value stands for (the inverse of artnet_input's mapping; an index gives the middle of its range)."""
    if row["kind"] == "int":
        n = int(row["max"] - row["min"]) + 1
        lo, hi = qlc_fixture.index_ranges(n)[min(max(int(round(wire - row["min"])), 0), n - 1)]
        return (lo + hi) // 2
    if row["kind"] == "trigger":
        return 255 if wire >= 0.5 else 0
    return int(round(min(max((wire - row["min"]) / (row["max"] - row["min"]), 0.0), 1.0) * 255))


def build(sets, start=1, rows=None):
    """(frame bytes of 512, the trigger channels that were set) for the SETs on top of the fixture's defaults."""
    rows = rows or qlc_fixture.blender_rows()
    frame = bytearray(512)
    for i, r in enumerate(rows):
        if start - 1 + i < 512:
            frame[start - 1 + i] = qlc_fixture.default_dmx(r)
    triggers = []
    by_address = {r["address"]: i for i, r in enumerate(rows)}
    for token in sets:
        key, _, value = token.partition("=")
        if key.startswith("/"):
            if key not in by_address:
                raise SystemExit("not a Blender row: %s" % key)
            i = by_address[key]
            frame[start - 1 + i] = dmx_value(rows[i], float(value))
            if rows[i]["kind"] == "trigger":
                triggers.append(start - 1 + i)
        else:
            frame[int(key) - 1] = min(max(int(value), 0), 255)
    return bytes(frame), triggers


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("host", nargs="?", default="127.0.0.1")
    ap.add_argument("sets", nargs="*")
    ap.add_argument("--universe", type=int, default=0)
    ap.add_argument("--start", type=int, default=1, help="DMX start address of the fixture")
    ap.add_argument("--frames", type=int, default=5)
    ap.add_argument("--rate", type=float, default=20.0, help="frames per second")
    ap.add_argument("--no-baseline", action="store_true")
    ap.add_argument("--broadcast", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    host, _, port = args.host.partition(":")
    port = int(port or artnet_input.ARTNET_PORT)
    sets = [s for s in args.sets if "=" in s]
    host_is_set = "=" in args.host
    if host_is_set:                      # HOST left out: the first word is a SET
        sets.insert(0, args.host)
        host, port = "127.0.0.1", artnet_input.ARTNET_PORT
    base, _ = build([], args.start)
    changed, triggers = build(sets, args.start)
    if args.dry_run:
        rows = qlc_fixture.blender_rows()
        for i, r in enumerate(rows):
            at = args.start - 1 + i
            if changed[at] != base[at]:
                print("DMX %3d %-16s %3d (default %d)" % (at + 1, r["address"], changed[at], base[at]))
        return 0
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if args.broadcast:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    seq = 0

    def send(frame):
        nonlocal seq
        seq = seq % 255 + 1
        sock.sendto(artnet_input.encode_artdmx(args.universe, frame, seq), (host, port))

    if not args.no_baseline:
        send(base)
        time.sleep(1.0 / args.rate)
    for _ in range(args.frames):
        send(changed)
        time.sleep(1.0 / args.rate)
    if triggers:
        release = bytearray(changed)
        for t in triggers:
            release[t] = 0
        send(bytes(release))
    print("sent %d frame(s) to %s:%d, universe %d, start address %d" % (args.frames + (0 if args.no_baseline else 1) + bool(triggers), host, port, args.universe, args.start))
    return 0


if __name__ == "__main__":
    sys.exit(main())
