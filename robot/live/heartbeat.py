"""Heartbeat of the Robot's live layer: /vj/live_layer, an int toggling 0/1, sent to Magic's OSC input. Stdlib only.

Blender's timer calls `Heartbeat.beat()` at 2 Hz while ROBOT_LIVE draws; Magic's LiveOn follows it (robot/magic/robot_magic.py).

    python3 robot/live/heartbeat.py --port 19402 [--rate 2] [--seconds 10]
"""
import argparse
import socket
import struct
import time

ADDRESS = "/vj/live_layer"
MAGIC_HOST, MAGIC_PORT = "127.0.0.1", 9202


def message(value, address=ADDRESS):
    """OSC message with one int32 argument."""
    pad = lambda b: b + b"\0" * (4 - len(b) % 4)
    return pad(address.encode()) + pad(b",i") + struct.pack(">i", value)


class Heartbeat:
    def __init__(self, host=MAGIC_HOST, port=MAGIC_PORT):
        self.target, self.value = (host, port), 0
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def beat(self):
        """Toggle the value and send it; returns the value sent."""
        self.value = 1 - self.value
        self.sock.sendto(message(self.value), self.target)
        return self.value

    def close(self):
        self.sock.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=MAGIC_HOST)
    ap.add_argument("--port", type=int, default=MAGIC_PORT)
    ap.add_argument("--rate", type=float, default=2.0, help="beats per second")
    ap.add_argument("--seconds", type=float, default=0, help="stop after this long (0: until interrupted)")
    a = ap.parse_args(argv)
    hb = Heartbeat(a.host, a.port)
    end = time.time() + a.seconds if a.seconds else None
    try:
        while end is None or time.time() < end:
            hb.beat()
            time.sleep(1.0 / a.rate)
    except KeyboardInterrupt:
        pass
    finally:
        hb.close()


if __name__ == "__main__":
    main()
