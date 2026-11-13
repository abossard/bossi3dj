"""Takeover in the bridge: a page or Art-Net touch claims an address, Magic waits for the pause. A fake clock, no Blender.
Run: python3 -m unittest discover blender/tests"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "osc"))
import blender_osc_bridge as bridge  # noqa: E402  (bpy is None outside Blender)

PAUSE = 20.0
TRIGGERS = {"/vj/shock", "/vj/meteor", "/vj/hit"}


def is_trigger(addr):
    return addr in TRIGGERS


class TakeoverTests(unittest.TestCase):
    def test_a_touch_claims_and_music_waits_for_the_pause(self):
        for source in bridge.TOUCH_SOURCES:
            with self.subTest(source=source):
                t = bridge.Takeover()
                self.assertEqual(t.admit({"/vj/height": [0.8]}, source, 0.0, PAUSE), {"/vj/height": [0.8]})
                self.assertEqual(t.admit({"/vj/height": [0.2]}, "osc", 5.0, PAUSE), {})
                self.assertEqual(t.admit({"/vj/height": [0.3]}, "osc", 19.9, PAUSE), {})
                self.assertEqual(t.release(19.9, PAUSE), {})
                self.assertEqual(t.release(20.0, PAUSE), {"/vj/height": [0.3]})      # Magic's latest, not its first
                self.assertEqual(t.admit({"/vj/height": [0.4]}, "osc", 21.0, PAUSE), {"/vj/height": [0.4]})

    def test_music_alone_passes(self):
        for source in ("osc", "sim", "check"):
            with self.subTest(source=source):
                t = bridge.Takeover()
                self.assertEqual(t.admit({"/vj/path": [2.0]}, source, 0.0, PAUSE), {"/vj/path": [2.0]})
                self.assertEqual(t.touched, {})

    def test_a_new_touch_restarts_the_pause(self):
        t = bridge.Takeover()
        t.admit({"/vj/target": [1.0]}, "web", 0.0, PAUSE)
        t.admit({"/vj/target": [4.0]}, "osc", 2.0, PAUSE)
        t.admit({"/vj/target": [5.0]}, "artnet", 15.0, PAUSE)
        self.assertEqual(t.release(25.0, PAUSE), {})
        self.assertEqual(t.release(35.0, PAUSE), {"/vj/target": [4.0]})

    def test_no_music_while_claimed_releases_nothing_but_frees_the_address(self):
        t = bridge.Takeover()
        t.admit({"/vj/fog": [0.9]}, "web", 0.0, PAUSE)
        self.assertEqual(t.release(30.0, PAUSE), {})
        self.assertEqual(t.touched, {})
        self.assertEqual(t.admit({"/vj/fog": [0.1]}, "osc", 31.0, PAUSE), {"/vj/fog": [0.1]})

    def test_addresses_are_independent(self):
        t = bridge.Takeover()
        t.admit({"/vj/fog": [0.9]}, "web", 0.0, PAUSE)
        out = t.admit({"/vj/fog": [0.1], "/vj/night": [1.0]}, "osc", 1.0, PAUSE)
        self.assertEqual(out, {"/vj/night": [1.0]})

    def test_triggers_always_pass(self):
        for addr in sorted(TRIGGERS):
            with self.subTest(address=addr):
                t = bridge.Takeover()
                t.admit({addr: [1.0]}, "web", 0.0, PAUSE, is_trigger)
                self.assertEqual(t.admit({addr: [1.0]}, "osc", 1.0, PAUSE, is_trigger), {addr: [1.0]})
                self.assertEqual(t.touched, {})

    def test_the_pause_length(self):
        """Music arriving `after` s after a touch is applied at once when the pause has passed, else kept."""
        cases = [(0.0, 0.0, True), (5.0, 4.9, False), (5.0, 5.0, True), (60.0, 59.0, False), (60.0, 61.0, True)]
        for pause, after, applied in cases:
            with self.subTest(pause=pause, after=after):
                t = bridge.Takeover()
                t.admit({"/vj/height": [0.8]}, "artnet", 0.0, pause)
                self.assertEqual(bool(t.admit({"/vj/height": [0.2]}, "osc", after, pause)), applied)

    def test_state_says_how_long_an_address_stays_the_users(self):
        t = bridge.Takeover()
        t.admit({"/vj/height": [0.8]}, "web", 10.0, PAUSE)
        self.assertEqual(t.state(15.0, PAUSE), {"/vj/height": 15.0})


class BridgeTakeoverWiringTests(unittest.TestCase):
    """Bridge.apply and tick with a fake clock; the scene write is replaced by a list."""

    def make(self):
        b = bridge.Bridge("127.0.0.1", 0, artnet_port=0, artnet_host="127.0.0.1")
        self.addCleanup(lambda: (b.sock.close(), b.artnet.close()))
        self.now = [0.0]
        b.clock = lambda: self.now[0]
        b.takeover_pause = lambda: PAUSE
        b.is_trigger = lambda k: ("/vj/" + k[3:]) in TRIGGERS
        written = []
        b.write = lambda latest, source="osc": written.append((dict(latest), source))
        return b, written

    def test_page_touch_then_magic_then_pause(self):
        b, written = self.make()
        b.apply({"/vj/height": [0.9]}, "web")
        self.now[0] = 3.0
        b.apply({"/vj/height": [0.1]}, "osc")
        self.now[0] = 25.0
        b.tick()
        self.assertEqual(written, [({"/vj/height": [0.9]}, "web"), ({"/vj/height": [0.1]}, "osc")])


if __name__ == "__main__":
    unittest.main()
