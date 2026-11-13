"""Art-Net input of the OSC bridge, without Blender and without udp 6454 or 9201. Run: python3 -m unittest discover blender/tests"""
import os
import socket
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "osc"))
import artnet_input as an  # noqa: E402
import blender_osc_bridge as bridge  # noqa: E402  (bpy is None outside Blender)
import contract  # noqa: E402

ROWS = an.channel_map((a, v[0], v[1], v[2]) for a, v in bridge.SCALES.items())
ADDR = {a: i for i, (a, *_rest) in enumerate(ROWS)}


def dmx(values, start=1):
    """A 512 byte frame with the given values at the channels of these addresses, for a fixture at `start`."""
    d = bytearray(512)
    for address, v in values.items():
        d[start - 1 + ADDR[address]] = v
    return bytes(d)


def decoder(**kw):
    return an.DmxDecoder(ROWS, **kw)


class PacketTests(unittest.TestCase):
    def test_round_trip(self):
        cases = [(0, b"\x01\x02"), (5, bytes(range(10))), (0x1234, bytes(512)), (3, b"\x07")]
        for universe, data in cases:
            with self.subTest(universe=universe, n=len(data)):
                u, _seq, got = an.parse_artdmx(an.encode_artdmx(universe, data, 7))
                self.assertEqual((u, got[:len(data)]), (universe, data))

    def test_not_artdmx(self):
        good = an.encode_artdmx(0, bytes(10))
        cases = {
            "short": good[:17], "empty": b"", "wrong id": b"Art-Nex\x00" + good[8:],
            "wrong opcode": good[:8] + b"\x00\x21" + good[10:], "length over data": good[:16] + b"\x02\x00" + good[18:],
            "length zero": good[:16] + b"\x00\x00" + good[18:], "length over 512": good[:16] + b"\x02\x02" + bytes(600),
        }
        for name, data in cases.items():
            with self.subTest(case=name):
                self.assertIsNone(an.parse_artdmx(data))


class ChannelMapTests(unittest.TestCase):
    def test_one_channel_per_scales_row_in_contract_order(self):
        rows = [r["address"] for r in contract.load() if r["blender"]]
        self.assertEqual([c[0] for c in ROWS], rows)
        self.assertEqual(len(ROWS), len(bridge.SCALES))

    def test_float_maps_linearly_onto_the_wire_range(self):
        d = decoder()
        d.feed(0, dmx({}))
        cases = [(0, 0.0), (255, 1.0), (51, 0.2), (128, 128 / 255.0)]
        for v, want in cases:
            with self.subTest(v=v):
                d.feed(0, dmx({"/vj/fog": 1 if v == 0 else 0}))      # move away so the next frame is a change
                out = dict(d.feed(0, dmx({"/vj/fog": v})))
                self.assertAlmostEqual(out["/vj/fog"], want, places=6)


class ChangeOnlyTests(unittest.TestCase):
    def test_first_frame_is_the_baseline(self):
        d = decoder()
        self.assertEqual(d.feed(0, dmx({"/vj/fog": 200})), [])
        self.assertEqual(d.feed(0, dmx({"/vj/fog": 200})), [])

    def test_only_changed_channels_apply(self):
        d = decoder()
        d.feed(0, dmx({"/vj/fog": 10, "/vj/level": 50}))
        out = d.feed(0, dmx({"/vj/fog": 10, "/vj/level": 60, "/vj/hue": 5}))
        self.assertEqual(sorted(a for a, _ in out), ["/vj/hue", "/vj/level"])

    def test_other_universe_is_ignored_and_counted(self):
        cases = [(0, 1), (0, 0x100), (0, 7), (3, 0), (0x100, 0)]       # (our universe, the frame's universe)
        for ours, theirs in cases:
            with self.subTest(ours=ours, theirs=theirs):
                d = decoder(universe=ours)
                d.feed(ours, dmx({}))
                self.assertEqual(d.feed(theirs, dmx({"/vj/fog": 99})), [])
                self.assertEqual((d.other, d.frames), (1, 1))

    def test_a_new_setting_makes_the_next_frame_a_baseline_again(self):
        d = decoder()
        d.feed(0, dmx({}))
        d.configure(address=11)
        self.assertEqual(d.feed(0, dmx({"/vj/fog": 77}, start=11)), [])
        self.assertEqual(dict(d.feed(0, dmx({"/vj/fog": 78}, start=11)))["/vj/fog"], 78 / 255.0)

    def test_start_address_offsets_the_channels(self):
        for start in (1, 2, 100, 400):
            with self.subTest(start=start):
                d = decoder(address=start)
                d.feed(0, dmx({}, start))
                out = d.feed(0, dmx({"/vj/fog": 255, "/vj/level": 255}, start))
                self.assertEqual(sorted(a for a, _ in out), ["/vj/fog", "/vj/level"])

    def test_a_frame_too_short_for_the_fixture_applies_what_it_holds(self):
        d = decoder()
        d.feed(0, dmx({})[:3])
        out = d.feed(0, bytes([0, 0, 9]))
        self.assertEqual([a for a, _ in out], [ROWS[2][0]])


class TriggerTests(unittest.TestCase):
    TRIGGERS = [("/vj/shock", 1.5), ("/vj/meteor", 1.0), ("/vj/hit", 1.0)]

    def test_rise_through_128_fires_once_with_a_strength(self):
        for address, wmax in self.TRIGGERS:
            with self.subTest(address=address):
                d = decoder()
                d.feed(0, dmx({}))
                self.assertEqual(d.feed(0, dmx({address: 127})), [])                                   # below: nothing
                self.assertAlmostEqual(dict(d.feed(0, dmx({address: 128})))[address], 0.5)
                self.assertEqual(d.feed(0, dmx({address: 128})), [])                                   # held: no second fire
                self.assertEqual(d.feed(0, dmx({address: 200})), [])                                   # louder while held: no fire
                self.assertAlmostEqual(dict(d.feed(0, dmx({address: 0})))[address], 0.0)               # falls: re-armed
                self.assertAlmostEqual(dict(d.feed(0, dmx({address: 255})))[address], wmax)

    def test_a_trigger_below_the_threshold_never_fires(self):
        d = decoder()
        d.feed(0, dmx({}))
        for v in (1, 50, 127):
            with self.subTest(v=v):
                self.assertEqual([a for a, x in d.feed(0, dmx({"/vj/shock": v})) if x > 0], [])


class IndexTests(unittest.TestCase):
    def test_equal_ranges_one_per_index(self):
        for address, n in (("/vj/path", 4), ("/vj/target", 7)):
            with self.subTest(address=address):
                d = decoder()
                d.feed(0, dmx({address: 0}))
                seen = {}
                for v in range(256):
                    d.previous = {ADDR[address]: (v + 1) % 256}      # force a change from any other value
                    out = dict(d.feed(0, dmx({address: v})))
                    seen.setdefault(out[address], []).append(v)
                self.assertEqual(sorted(seen), [float(i) for i in range(n)])
                sizes = {len(v) for v in seen.values()}
                self.assertLessEqual(max(sizes) - min(sizes), 1)
                self.assertEqual(seen[0.0][0], 0)
                self.assertEqual(seen[float(n - 1)][-1], 255)


class BridgeWiringTests(unittest.TestCase):
    """The bridge with its OSC socket on an ephemeral port and Art-Net on another one; bpy is replaced by plain functions."""

    def make(self, hold=()):
        b = bridge.Bridge("127.0.0.1", 0, artnet_port=0, artnet_host="127.0.0.1")
        self.addCleanup(lambda: (b.sock.close(), b.artnet.close()))
        applied = []
        b.fit = lambda addr, args: args
        b.is_trigger = lambda k: k in ("vj_shock", "vj_meteor", "vj_hit")
        b.apply = lambda latest, source="osc": applied.append((dict(latest), source))
        b.hold = set(hold)
        return b, applied

    def send(self, b, frame_bytes):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(s.close)
        s.sendto(an.encode_artdmx(0, frame_bytes), ("127.0.0.1", b.artnet.bound_port()))
        time.sleep(0.05)

    def test_changes_reach_apply_with_the_source_artnet(self):
        b, applied = self.make()
        self.send(b, dmx({"/vj/fog": 10}))
        b.tick()
        self.assertEqual(applied, [])                                        # the baseline
        self.send(b, dmx({"/vj/fog": 255}))
        b.tick()
        self.assertEqual(len(applied), 1)
        latest, source = applied[0]
        self.assertEqual(source, "artnet")
        self.assertAlmostEqual(latest["/vj/fog"][0], 1.0)
        self.assertEqual(b.stats["/vj/fog"]["src"].split(":")[0], "127.0.0.1")

    def test_a_held_property_is_skipped(self):
        b, applied = self.make(hold={"vj_fog"})
        self.send(b, dmx({}))
        b.tick()
        self.send(b, dmx({"/vj/fog": 255, "/vj/level": 255}))
        b.tick()
        self.assertEqual(list(applied[0][0]), ["/vj/level"])
        self.assertEqual(b.held, 1)

    def test_state_reports_a_failed_bind_and_never_raises(self):
        inp = an.ArtNetInput(decoder(), "203.0.113.1", 6454)       # an address no interface of this machine has: the bind fails
        self.addCleanup(inp.close)
        self.assertIsNone(inp.sock)
        state = inp.state()
        self.assertFalse(state["bound"])
        self.assertIn("udp 6454", state["error"])
        self.assertEqual(inp.poll(), [])

    def test_off_means_no_socket(self):
        inp = an.ArtNetInput(decoder(), "127.0.0.1", 0, enabled=False)
        self.assertIsNone(inp.sock)
        inp.set_enabled(True)
        self.addCleanup(inp.close)
        self.assertIsNotNone(inp.sock)
        inp.set_enabled(False)
        self.assertIsNone(inp.sock)


if __name__ == "__main__":
    unittest.main()
