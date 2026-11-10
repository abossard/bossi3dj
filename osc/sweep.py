#!/usr/bin/env python3
"""Walks every /vj/* address of the contract through its minimum, default and maximum.

    python3 osc/sweep.py [--target relay|blender|godot|HOST:PORT] [--seconds 3] [--only REGEX] [--dry-run]

Floats and indices hold each of the three wire values for a third of --seconds, then go back to the default.
A trigger fires once (0, then --strength, then 0) and waits --seconds. The script prints what it sends and
only sends: it listens on nothing, so it never takes a show port. Targets: relay = udp 9200 (lab.py hands the packets
to both scenes), blender = 9201, godot = 9202. --dry-run prints the whole walk without a socket or a wait.

Standard library only. The rows come from osc/contract.json, the same table as CONTROLS.md.
"""
import argparse
import re
import socket
import struct
import sys
import time
from collections import namedtuple

import contract

TARGETS = {"relay": 9200, "blender": 9201, "godot": 9202}
Step = namedtuple("Step", "address label value hold trigger")


def osc_message(address, value):
    """One OSC message with a float32 argument, the way Magic sends it."""
    def pad(b):
        b += b"\0"
        return b + b"\0" * (-len(b) % 4)
    return pad(address.encode()) + pad(b",f") + struct.pack(">f", value)


def plan(rows, seconds=3.0, strength=1.0):
    """The walk as steps: min, default, max for a float or an index, one fire for a trigger."""
    steps = []
    for r in rows:
        a = r["address"]
        if r["kind"] == "trigger":
            steps.append(Step(a, "fire", min(strength, r["max"]), seconds, True))
        else:
            for label, v in (("min", r["min"]), ("default", r["default"]), ("max", r["max"])):
                steps.append(Step(a, label, v, seconds / 3, False))
    return steps


def parse_target(text, host):
    if text in TARGETS:
        return host, TARGETS[text]
    h, _, port = text.rpartition(":")
    if not port.isdigit():
        raise argparse.ArgumentTypeError("target is relay, blender, godot or HOST:PORT")
    return h or host, int(port)


def run(steps, defaults, send, sleep, say, rate=10.0):
    """Executes the steps. send(address, value) and sleep(seconds) are injected, so a dry run passes no-ops."""
    last = None
    try:
        for s in steps:
            if last is not None and last != s.address:
                send(last, defaults[last])
            last = s.address
            say("%-16s %-8s %g" % (s.address, s.label, s.value))
            if s.trigger:
                send(s.address, 0.0)
                sleep(0.05)
                send(s.address, s.value)
                sleep(0.1)
                send(s.address, 0.0)
                sleep(max(s.hold - 0.15, 0.0))
            else:
                for _ in range(max(int(s.hold * rate), 1)):
                    send(s.address, s.value)
                    sleep(1.0 / rate)
    finally:
        if last is not None:
            send(last, defaults[last])     # leave the scene at the default, also after Ctrl-C


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--target", default="relay", help="relay (9200), blender (9201), godot (9202) or HOST:PORT")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--seconds", type=float, default=3.0, help="per address (default 3)")
    ap.add_argument("--rate", type=float, default=10.0, help="packets per second while a value is held (default 10)")
    ap.add_argument("--strength", type=float, default=1.0, help="value a trigger fires with (default 1, a drop is 1.4 and above)")
    ap.add_argument("--only", help="regex: only the addresses it matches")
    ap.add_argument("--dry-run", action="store_true", help="print the walk, send nothing, wait for nothing")
    a = ap.parse_args(argv)
    host, port = parse_target(a.target, a.host)
    rows = [r for r in contract.load() if not a.only or re.search(a.only, r["address"])]
    if not rows:
        ap.error("no address matches %r" % a.only)
    steps = plan(rows, a.seconds, a.strength)
    defaults = {r["address"]: r["default"] for r in rows}
    total = a.seconds * len(rows)
    print("sweep: %d addresses, %d values, about %d s, %s udp %s:%d" % (
        len(rows), len(steps), total, "dry run, nothing sent to" if a.dry_run else "sending to", host, port), flush=True)
    if a.dry_run:
        run(steps, defaults, lambda *_: None, lambda _: None, print, a.rate)
        return 0
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    run(steps, defaults, lambda addr, v: sock.sendto(osc_message(addr, v), (host, port)), time.sleep,
        lambda line: print(line, flush=True), a.rate)
    print("sweep: done", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
