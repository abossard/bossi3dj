#!/usr/bin/env python3
"""Sends timed /vj/shock packets to a Godot scene's OSC port, the way Magic does.

    python3 tools/godot_shock_send.py --port 19202 0.5:1.0 4.0:1.5

Each `seconds:strength` pair fires a trigger at that time: strength for 0.2 s, then 0. Time counts from
the start of the script. Port 9201 is the show's: tests use 19202 (tests/shake_osc.gd starts this script).
Standard library only; the packet encoder is osc/sweep.py's.
"""
import argparse
import os
import socket
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "osc"))
from sweep import osc_message  # noqa: E402

PULSE_SECONDS = 0.2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("shocks", nargs="+", help="seconds:strength")
    a = ap.parse_args()
    steps = []
    for s in a.shocks:
        at, strength = s.split(":")
        steps.append((float(at), float(strength)))
        steps.append((float(at) + PULSE_SECONDS, 0.0))
    steps.sort()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    start = time.time()
    for at, strength in steps:
        time.sleep(max(0.0, start + at - time.time()))
        sock.sendto(osc_message("/vj/shock", strength), ("127.0.0.1", a.port))
        print("%.2f s  /vj/shock %.2f" % (time.time() - start, strength), flush=True)


if __name__ == "__main__":
    main()
