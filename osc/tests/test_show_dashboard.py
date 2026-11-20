"""Show commands are atomic and independent of Magic and Blender."""

from http.client import HTTPConnection
import json
from pathlib import Path
import socket
import sys
from threading import Thread
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lab import encode_message, parse_message  # noqa: E402
from show_dashboard import Dashboard, ShowState  # noqa: E402
from show_protocol import CUES, SCENES, REACTIVITY, SELECTION  # noqa: E402


class ShowCommandTests(unittest.TestCase):
    def test_starts_with_safe_and_refreshes_explicit_state(self):
        state = ShowState()
        self.assertEqual(state.scene, "safe")
        self.assertEqual(dict(state.commands())[SELECTION], 0)
        self.assertEqual(state.snapshot()["readiness"], {"program": "unknown"})

    def test_cue_and_scene_travel_in_one_packet(self):
        state = ShowState()
        for index, (cue, expected_scene) in enumerate(CUES.items()):
            address, value = state.set_cue({"cue": cue})
            self.assertEqual(state.scene, expected_scene)
            address, kind, args = parse_message(encode_message(address, [value]))
            self.assertEqual((address, kind), (SELECTION, "i"))
            self.assertEqual(divmod(args[0], len(SCENES)), (index, SCENES.index(expected_scene)))

    def test_direct_scene_and_safe_keep_phase(self):
        state = ShowState()
        state.set_cue({"cue": "peak"})
        state.set_cue({"scene": "safe"})
        self.assertEqual((state.cue, state.scene), ("peak", "safe"))
        self.assertEqual(dict(state.commands())[SELECTION], 6)
        state.set_reactivity({"value": 0.5})
        self.assertEqual(state.scene, "safe")
        state.set_cue({"scene": "planet"})
        self.assertEqual((state.cue, state.scene), ("peak", "planet"))

    def test_reactivity_is_numeric_and_refreshes_last_value(self):
        state = ShowState()
        self.assertEqual(state.set_reactivity({"value": 0.5}), (REACTIVITY, 0.5))
        for value in (False, "0", -1, 2, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                state.set_reactivity({"value": value})
        self.assertEqual(dict(state.commands())[REACTIVITY], 0.5)

    def test_bad_cues_leave_the_program_alone(self):
        state = ShowState()
        for body in ({"cue": "auto"}, {"scene": "blender"}, {"cue": ["arrive"]}, {"cue": "arrive", "scene": "safe"}):
            with self.subTest(body=body), self.assertRaises(ValueError):
                state.set_cue(body)
        self.assertEqual(state.scene, "safe")


class DashboardHTTPTests(unittest.TestCase):
    def test_a_partial_request_does_not_block_the_next_client(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as osc:
            osc.bind(("127.0.0.1", 0))
            with Dashboard(0, osc.getsockname()[1]) as server:
                worker = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05})
                worker.start()
                try:
                    with socket.create_connection(("127.0.0.1", server.server_port), timeout=2) as stalled:
                        stalled.sendall(b"GET /api/show HTTP/1.1\r\n")
                        http = HTTPConnection("127.0.0.1", server.server_port, timeout=1)
                        try:
                            http.request("GET", "/api/show")
                            response = http.getresponse()
                            self.assertEqual(response.status, 200)
                            self.assertEqual(json.load(response)["requested"]["scene"], "safe")
                        finally:
                            http.close()
                finally:
                    server.shutdown()
                    worker.join()

    def test_http_phase_and_safe_reach_an_ephemeral_osc_listener(self):
        with (socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as osc,
              socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as blender):
            osc.bind(("127.0.0.1", 0))
            osc.settimeout(2)
            blender.bind(("127.0.0.1", 0))
            blender.settimeout(2)
            with Dashboard(0, osc.getsockname()[1], blender.getsockname()[1]) as server:
                thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05})
                thread.start()
                http = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
                try:
                    http.request("GET", "/api/show")
                    response = http.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.load(response)["requested"]["scene"], "safe")
                    for body, scene, value in (({"cue": "peak"}, "robot", 8), ({"scene": "safe"}, "safe", 6)):
                        http.request("PUT", "/api/show/cue", json.dumps(body), {"Content-Type": "application/json"})
                        response = http.getresponse()
                        self.assertEqual(response.status, 200)
                        self.assertEqual(json.load(response)["requested"]["scene"], scene)
                        for listener in (osc, blender):
                            for _ in range(6):
                                if parse_message(listener.recv(1024)) == (SELECTION, "i", [value]):
                                    break
                            else:
                                self.fail(f"OSC value {value} did not arrive for {body}")
                finally:
                    http.close()
                    server.shutdown()
                    thread.join()
