"""Heartbeat sender: wire format and toggling. Uses a 19xxx port, never Magic's 9202."""
import os
import socket
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import heartbeat as hb  # noqa: E402

PORT = 19403


class HeartbeatTests(unittest.TestCase):
    def test_message_is_an_osc_int(self):
        for value in (0, 1, 7):
            with self.subTest(value=value):
                self.assertEqual(hb.message(value), b"/vj/live_layer\0\0,i\0\0" + struct.pack(">i", value))

    def test_beats_toggle_over_udp(self):
        rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rx.bind(("127.0.0.1", PORT))
        rx.settimeout(2)
        self.addCleanup(rx.close)
        sender = hb.Heartbeat("127.0.0.1", PORT)
        self.addCleanup(sender.close)
        got = []
        for _ in range(4):
            sender.beat()
            got.append(struct.unpack(">i", rx.recv(64)[-4:])[0])
        self.assertEqual(got, [1, 0, 1, 0])

    def test_defaults_are_the_contract(self):
        self.assertEqual((hb.ADDRESS, hb.MAGIC_HOST, hb.MAGIC_PORT), ("/vj/live_layer", "127.0.0.1", 9202))


if __name__ == "__main__":
    unittest.main()
