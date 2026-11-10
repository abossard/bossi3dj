"""magicproj tests. Run: python3 -m unittest discover magic/tests

Unit tests use generated projects and Magic's bundled sample projects (skipped
without the app). LiveMagicTests drive the running app; they replace Magic's
current project, so they only run with MAGICPROJ_LIVE=1.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import wave
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import magicproj as mp  # noqa: E402

SAMPLES = sorted(os.path.join(mp.SAMPLES, f) for f in os.listdir(mp.SAMPLES) if f.endswith(".magic")) \
    if os.path.isdir(mp.SAMPLES) else []


def demo(syphon="magicproj-test", hue=0.0):
    b = mp.Builder(syphon=syphon, osc_in=11111)
    b.glob("Hue", hue)
    b.glob("Level", 0, "audio:Source 0:Freq. Range:20-80 Hz", [("Expression", "x*Gain*4"), ("Smooth", 0.6)])
    b.glob("Gain", 0.5)
    b.glob("Ext", 0, "osc:/ext/beat")
    b.glob("Width", 0, "internal:Graphics Width")
    s = b.scene("Main")
    poly = s.node("Polygon", {"Sides": 4})
    scale = s.node("Scale", {"X": 4, "Y": 4, "Z": 1, "X For All": 0}, inputs=[poly])
    col = s.node("ColorHSB", {"Hue": ("global:Hue", [], hue), "Saturation": 1, "Brightness": 1, "Alpha": 1, "Override": 1},
                 inputs=[scale], bypass=("global:Level", [("Expression", "if(x > 2, 1, 0)")]))
    osc = s.node("OSCSender", {"IP Addr.": "127.0.0.1", "Port": 9200, "Message": "/vj/level", "Value": ("global:Level",)})
    s.output(col, osc)
    return b.build()


def roundtrip(root):
    return mp.parse(mp.encode(mp.serialize(root)))


class CodecTests(unittest.TestCase):
    @unittest.skipUnless(SAMPLES, "Magic not installed")
    def test_magic_saves_roundtrip_semantically(self):
        for path in SAMPLES:
            with self.subTest(os.path.basename(path)):
                root = mp.read(path)
                self.assertEqual(mp.canonical(roundtrip(root)), mp.canonical(root))

    def test_header_is_ignored_on_decode(self):
        for header in (b"L*h", b"\x00\x00\x00", b"u6m"):
            with self.subTest(header=header):
                data = header + mp.encode(mp.serialize(demo()))[3:]
                self.assertEqual(mp.canonical(mp.parse(data)), mp.canonical(demo()))


class CheckTests(unittest.TestCase):
    @unittest.skipUnless(SAMPLES, "Magic not installed")
    def test_magic_saves_have_no_errors(self):
        for path in SAMPLES:
            with self.subTest(os.path.basename(path)):
                errors = [m for level, m in mp.check(mp.read(path)) if level == "error"]
                self.assertEqual(errors, [])

    def test_built_project_has_no_errors(self):
        self.assertEqual([p for p in mp.check(demo()) if p[0] == "error"], [])

    def test_detects(self):
        def break_link(r):
            mp.find_global(r, "Hue").set("id", "999999")

        def bad_expr(r):
            mp.set_modifiers(mp.find_global(r, "Level"), [("Expression", "x*Gian")])

        def missing_input(r):
            next(r.iter("Child")).set("id", "424242")

        def reserved_name(r):
            mp.find_global(r, "Gain").set("name", "x")

        def dup_global(r):
            mp.find_global(r, "Gain").set("name", "Hue")

        def bad_modifier(r):
            next(r.iter("ValueOperator")).set("type", "99")

        def dup_iv_id(r):
            ivs = list(r.iter("InputValue"))
            ivs[-1].set("id", ivs[-2].get("id"))

        cases = [(break_link, "missing Global id"), (bad_expr, "unknown names ['Gian']"),
                 (missing_input, "is not in the scene"), (reserved_name, "reserved"), (dup_global, "used twice"),
                 (bad_modifier, "unknown modifier type"), (dup_iv_id, "used 2 times")]
        for mutate, expected in cases:
            with self.subTest(mutate.__name__):
                root = demo()
                mutate(root)
                errors = [m for level, m in mp.check(root) if level == "error"]
                self.assertTrue(any(expected in m for m in errors), errors)

    def test_expression_identifiers(self):
        cases = [("x*Gain*4", {"x", "Gain"}), ("max(x, y*exp(-Dt*9))", {"max", "x", "y", "exp", "Dt"}),
                 ("1e-3 + .5*Kick", {"Kick"}), ("var a := Kick; a*2", {"var", "Kick"}), ("'str' + Foo", {"Foo"})]
        for expr, expected in cases:
            with self.subTest(expr):
                self.assertEqual(mp.expression_identifiers(expr), expected)


class QueryTests(unittest.TestCase):
    def test_describe_source(self):
        table = {g["name"]: g for g in mp.global_table(demo())}
        cases = [("Hue", "manual"), ("Level", "audio:Source 0:Freq. Range:20-80 Hz"), ("Ext", "osc:/ext/beat"),
                 ("Width", "internal:Graphics Width")]
        for name, source in cases:
            with self.subTest(name):
                self.assertEqual(table[name]["source"], source)

    def test_modifier_names(self):
        mods = mp.global_table(demo())[1]["modifiers"]
        self.assertEqual(mods, [("Expression", 0.0, "x*Gain*4", False), ("Smooth", 0.6, None, False)])

    def test_modifier_index_matches_magic(self):
        # Expression = 21 holds every multi-character expression in Magic's samples.
        cases = [("Gate", 0), ("Power", 3), ("Smooth", 4), ("Peak", 12), ("Increase", 16), ("Trigger", 17),
                 ("Expression", 21), ("RandomTrigger", 22)]
        for name, index in cases:
            with self.subTest(name):
                self.assertEqual(mp.MODIFIERS.index(name), index)

    def test_isf_param_names(self):
        # Names as Magic saves them (synthwave_pyramids.magic loads with these).
        cases = [({"NAME": "blurAmount", "TYPE": "float", "DEFAULT": 12.0}, {"BlurAmount": 12.0}),
                 ({"NAME": "mirrorEdges", "LABEL": "Fill Edges", "TYPE": "bool", "DEFAULT": True}, {"Fill Edges": True}),
                 ({"NAME": "center", "TYPE": "point2D", "DEFAULT": [0.5, 0.5]}, {"Center X": 0.5, "Center Y": 0.5}),
                 ({"NAME": "inputImage", "TYPE": "image"}, {})]
        # Magic's own headers have raw newlines in strings and trailing commas (Transparency.fs).
        lenient = '/*{"DESCRIPTION": "two\nlines", "INPUTS": [{"NAME": "amount", "TYPE": "float", "DEFAULT": 0.5},],}*/'
        with self.subTest("lenient"):
            self.assertEqual(mp.isf_params(lenient), {"Amount": 0.5})
        for inp, expected in cases:
            with self.subTest(inp["NAME"]):
                text = '/*{"ISFVSN": "2", "INPUTS": [%s]}*/\nvoid main() {}' % json.dumps(inp)
                self.assertEqual(mp.isf_params(text), expected)

    def test_osc_senders(self):
        self.assertEqual([(o["message"], o["ip"], o["port"], o["value_source"]) for o in mp.osc_senders(demo())],
                         [("/vj/level", "127.0.0.1", "9200", "global:Level")])

    def test_summary(self):
        s = mp.summary(demo())
        self.assertEqual((s["syphon"], s["globals"], s["osc_in_ports"], [x["name"] for x in s["scenes"]]),
                         ({"on": True, "name": "magicproj-test", "size": "1920x1080"}, 5, ["11111"], ["Main"]))


class EditTests(unittest.TestCase):
    def test_edits_show_in_diff(self):
        cases = [
            (lambda r: mp.edit_global(r, "Hue", value=0.33), [("global[Hue].value", "0", "0.33")]),
            (lambda r: mp.edit_global(r, "Gain", source="osc:/gain"), [("global[Gain].source", "manual", "osc:/gain")]),
            (lambda r: mp.edit_global(r, "Level", mods=[("Peak", 0.5)]),
             [("global[Level].modifiers", "Expression(x*Gain*4) -> Smooth 0.6", "Peak 0.5")]),
            (lambda r: mp.add_global(r, "New", 2), [("global[New].modifiers", None, ""), ("global[New].source", None, "manual"),
                                                    ("global[New].value", None, "2")]),
            (lambda r: mp.set_syphon(r, False), [("project.videoSharing", "1", "0")]),
            (lambda r: mp.set_osc_target(r, port=9300), [("scene[Main].node[OSCSender#1].Port", "9200", "9300")]),
            (lambda r: mp.set_osc_in(r, 8000), [("source[OSC In]", "Open Sound Control ch 11111", "Open Sound Control ch 8000"),
                                                  ("track[Open Sound Control ch 11111]", "deviceName= isInput=1 isOSC=1", None),
                                                  ("track[Open Sound Control ch 8000]", None, "deviceName= isInput=1 isOSC=1")]),
        ]
        for i, (edit, expected) in enumerate(cases):
            with self.subTest(i):
                before = demo()
                after = edit(before)
                self.assertEqual(mp.diff(before, after), expected)
                self.assertEqual(mp.canonical(before), mp.canonical(demo()), "edits must not mutate their input")

    def test_rename_rewrites_expressions(self):
        root = mp.edit_global(demo(), "Gain", rename="InGain")
        self.assertEqual(mp.global_table(root)[1]["modifiers"][0][2], "x*InGain*4")
        self.assertEqual([p for p in mp.check(root) if p[0] == "error"], [])

    def test_remove_global_unlinks_params(self):
        root = mp.remove_global(demo(), "Hue")
        hue = next(p for n in mp.node_table(root) for p in n["params"] if p["name"] == "Hue")
        self.assertEqual(hue["source"], "manual")
        self.assertEqual([p for p in mp.check(root) if p[0] == "error"], [])

    def test_add_audio_routes_sources(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "tone.wav")
            for channels in (1, 2):
                with self.subTest(channels=channels):
                    with wave.open(path, "wb") as w:
                        w.setnchannels(channels); w.setsampwidth(2); w.setframerate(44100); w.writeframes(b"\0\0" * channels * 441)
                    root = mp.add_audio(demo(), path)
                    s = mp.summary(root)
                    self.assertEqual(s["audio_files"], [path])
                    self.assertTrue(s["looping"])
                    file_tracks = {t.get("id") for t in root.iter("Track") if t.get("audioFileIndex") == "0"}
                    self.assertEqual(len(file_tracks), channels)
                    self.assertEqual(sum(1 for x in s["sources"] if x["track"] in file_tracks), channels)
                    self.assertEqual([p for p in mp.check(root, d) if p[0] == "error"], [])

    def test_cli_size_keeps_syphon_state(self):
        with tempfile.TemporaryDirectory() as d:
            for syphon, args, expected in ((None, ["--size", "1280x720"], "0"), ("x", ["--size", "1280x720"], "1"),
                                           (None, ["--syphon-name", "out"], "1"), ("x", ["--syphon", "off"], "0")):
                with self.subTest(args=args, syphon=syphon):
                    src, out = os.path.join(d, "p.magic"), os.path.join(d, "o.magic")
                    mp.write(src, demo(syphon=syphon))
                    mp.main(["set", src, "-o", out] + args)
                    root = mp.read(out)
                    self.assertEqual(root.get("videoSharing"), expected)
                    if "--size" in args:
                        self.assertEqual((root.get("videoSharingWidth"), root.get("fixedMagicSize")), ("1280", "1"))

    def test_cli_set_refuses_broken_result(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "p.magic")
            mp.write(path, demo())
            for args, code in ((["--value", "Hue", "0.5"], 0), (["--mods", "Hue", "x*Nope"], 1)):
                with self.subTest(args=args):
                    self.assertEqual(mp.main(["set", path, "-o", os.path.join(d, "o.magic")] + args), code)


class V3Tests(unittest.TestCase):
    def test_midi_sources(self):
        root = mp.add_midi_in(demo(), "IAC Driver Bus 1", 1, "Keys")
        self.assertEqual(sum(1 for t in root.iter("Track") if t.get("name") == "IAC Driver Bus 1"), 17)
        cases = [("midi:Keys:Control Change:7", "midi:Keys:Control Change:7"), ("midi:Keys:3:1", "midi:Keys:Control Change:1"),
                 ("midi:Keys:Note Velocity:60", "midi:Keys:Note Velocity:60"), ("midi:Keys:Beat Clock:/4", "midi:Keys:Beat Clock:/4"),
                 ("midi:Keys:Program Change", "midi:Keys:Program Change"), ("midi:Keys:Iterator Notes", "midi:Keys:Iterator Notes")]
        for source, shown in cases:
            with self.subTest(source):
                r = mp.edit_global(root, "Hue", source=source)
                self.assertEqual(mp.global_table(r)[0]["source"], shown)
                self.assertEqual([p for p in mp.check(r) if p[0] == "error"], [])

    def test_route_source(self):
        cases = [("Source 1", "MacBook Pro Microphone", 0), ("Drums", "Scarlett 18i20", 3)]
        for source, device, ch in cases:
            with self.subTest(source):
                root = mp.route_source(demo(), source, device, ch)
                layer = next(l for l in root.iter("Layer") if l.get("name") == source)
                track = next(t for t in root.iter("Track") if t.get("id") == layer.get("trackID"))
                self.assertEqual((track.get("deviceName"), track.get("channel")), (device, str(ch)))
                self.assertEqual([p for p in mp.check(root) if p[0] == "error"], [])

    def test_playlist(self):
        b = mp.Builder()
        for name in ("A", "B", "C"):
            b.scene(name).output()
        root = b.build()
        cases = [(dict(seconds=16, transition=3, style=1), ["0", "1", "2"], ("16", "3", "1")),
                 (dict(names=["C", "A"], seconds=8, style=0), ["2", "0"], ("8", "2", "0"))]
        for kwargs, ids, (secs, trans, style) in cases:
            with self.subTest(kwargs):
                entries = list(mp.set_playlist(root, **kwargs).iterfind("Playlists/Playlist/Scene"))
                self.assertEqual([e.get("id") for e in entries], ids)
                self.assertEqual({(e.get("sceneDuration"), e.get("duration"), e.get("style")) for e in entries}, {(secs, trans, style)})

    def test_playlist_keeps_existing_entry_settings(self):
        b = mp.Builder()
        b.scene("A").output()
        root = b.build()
        next(root.iterfind("Playlists/Playlist/Scene")).set("featureString", "/scene/a")
        entry = next(mp.set_playlist(root, seconds=5).iterfind("Playlists/Playlist/Scene"))
        self.assertEqual((entry.get("featureString"), entry.get("sceneDuration")), ("/scene/a", "5"))

    def test_connect(self):
        root = demo()
        nodes = {n["plugin"]: n["id"] for n in mp.node_table(root)}
        cases = [([nodes["Polygon"]], None), (["999"], KeyError)]
        for ids, error in cases:
            with self.subTest(ids=ids):
                if error:
                    with self.assertRaises(error):
                        mp.connect(root, "Main", nodes["ColorHSB"], ids)
                    continue
                r = mp.connect(root, "Main", nodes["ColorHSB"], ids)
                col = next(n for n in mp.node_table(r) if n["plugin"] == "ColorHSB")
                self.assertEqual(col["inputs"], ids)
                self.assertEqual([p for p in mp.check(r) if p[0] == "error"], [])

    def test_check_flags_pre_v3_and_unknown(self):
        def rename_image(r):
            next(n for n in r.iter("Node") if n.get("pluginName") == "Polygon").set("pluginName", "Image")

        def unknown_param(r):
            col = next(n for n in r.iter("Node") if n.get("pluginName") == "ColorHSB")
            mp.param(col, "Hue").set("name", "Premultiply")

        def unknown_module(r):
            next(n for n in r.iter("Node") if n.get("pluginName") == "Polygon").set("pluginName", "Polygonn")

        def removed_module(r):
            next(n for n in r.iter("Node") if n.get("pluginName") == "Polygon").set("pluginName", "AudioToImage")

        cases = [(rename_image, "pre-3.0 name"), (removed_module, "removed in 3.0"), (unknown_param, "not in Magic 3's ColorHSB"), (unknown_module, "not a Magic 3.0 module")]
        for mutate, expected in cases:
            with self.subTest(mutate.__name__):
                root = demo()
                mutate(root)
                self.assertTrue(any(expected in m for _, m in mp.check(root)))

    def test_bypass_follows_magic(self):
        cases = [("Polygon", False), ("Fractal", False), ("Text", False), ("ColorHSB", True), ("Bloom", True), ("Kaleidoscope", True)]
        for plugin, expected in cases:
            with self.subTest(plugin):
                self.assertEqual(mp.has_bypass(plugin), expected)

    def test_diff_ignores_renumbered_ids(self):
        root = demo()
        renumbered = mp.parse(mp.encode(mp.serialize(root)))
        old = {}
        for e in renumbered.iter():
            if e.tag in ("Node", "InputValue", "Track", "Layer") and e.get("id"):
                old[e.get("id")] = str(int(e.get("id")) + 10000)
        for e in renumbered.iter():
            for k in ("id", "feature", "trackID", "layerID"):
                if e.get(k) in old and (k != "feature" or e.get("layerID") == str(mp.GLOBAL_LAYER)) and \
                        (k != "id" or e.tag in ("Node", "InputValue", "Track", "Layer", "Child")):
                    e.set(k, old[e.get(k)])
        self.assertEqual(mp.diff(root, renumbered), [])


class ListenTests(unittest.TestCase):
    def test_listen_collects_messages(self):
        sys.path.insert(0, os.path.join(os.path.dirname(mp.__file__), "..", "osc"))
        from lab import encode_message
        import socket
        import threading
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        packets = [("/vj/beat", [0.5]), ("/vj/beat", [1.0]), ("/vj/level", [0.25])]

        def send():
            time.sleep(0.3)
            tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            for addr, args in packets:
                tx.sendto(encode_message(addr, args), ("127.0.0.1", port))
            tx.close()
        threading.Thread(target=send).start()
        got = mp.listen(port, 1.0)
        self.assertEqual(got, {"/vj/beat": [0.5, 1.0], "/vj/level": [0.25]})

    def test_listen_refuses_reserved_ports(self):
        self.assertIn(9201, mp.RESERVED_PORTS)  # the Blender bridge in this repo
        for port in sorted(mp.RESERVED_PORTS):
            with self.subTest(port=port), self.assertRaises(ValueError):
                mp.listen(port, 0.1)


def _osc_id(root):
    return next(n.get("id") for n in root.iter("Node") if n.get("pluginName") == "OSCSender")


@unittest.skipUnless(os.environ.get("MAGICPROJ_LIVE") == "1", "replaces Magic's project; set MAGICPROJ_LIVE=1")
class LiveMagicTests(unittest.TestCase):
    """Builds, loads and edits a project in the running Magic and reads the
    result over Syphon. Reloads MAGICPROJ_RESTORE (if set) afterwards."""

    @classmethod
    def tearDownClass(cls):
        restore = os.environ.get("MAGICPROJ_RESTORE")
        if restore:
            mp.load(restore)

    def grab(self, server):
        out = subprocess.run([mp.SYPHON_PYTHON, os.path.abspath(mp.__file__), "grab", "--server", server, "--wait", "2"],
                             env=dict(os.environ, PYTHONPATH=mp.SYPHON_PATH), capture_output=True, text=True, check=True)
        import json
        return json.loads(out.stdout)

    def test_build_edit_load_grab(self):
        server = "magicproj-e2e"
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "e2e.magic")
            # Hue 0 = red, 1/3 = green; full brightness proves Internals 0 = Graphics Width.
            root = demo(syphon=server)
            root = mp.add_global(root, "Bright", 0, "calc", [("Expression", "if(Width > 1900 and Width < 1940, 1, 0.3)")])
            col = next(n for n in mp.node_table(root) if n["plugin"] == "ColorHSB")
            root = mp.edit_param(root, "Main", col["id"], "Brightness", source="global:Bright")
            for hue, channel in ((0.0, 0), (1 / 3, 1)):
                with self.subTest(hue=hue):
                    mp.write(path, mp.edit_global(root, "Hue", value=hue))
                    ok, wins = mp.load(path)
                    self.assertTrue(ok, wins)
                    stats = self.grab(server)
                    centre = stats["grid"][1][1]
                    self.assertGreater(centre[channel], 200, stats)
                    self.assertLess(sum(centre) - centre[channel], 120, stats)
                time.sleep(0.5)


if __name__ == "__main__":
    unittest.main()
