"""robot_magic.py: the generated project is valid, has the planned modules and links, and its Globals run the Clip Graph of
clip_graph.py. Run: python3 -m unittest discover robot/magic/tests

The Globals are run by a small interpreter of the ExprTk subset the graph uses, with Magic's rule that every Global reads the
previous frame's values (magic-projects skill, Semantics). It is not Magic: whether Magic runs them the same way is the user's check.
"""
import json
import math
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "..", "..", "package", "fixture", "manifest.json")) as _f:
    FIXTURE_DATA = json.load(_f)
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "magic"))
import clip_graph as cg  # noqa: E402
import magicproj as mp  # noqa: E402
import manifest as mf  # noqa: E402
import robot_magic as rm  # noqa: E402
from test_manifest import package_with_media  # noqa: E402


def generated(tmp, **kw):
    root = package_with_media(tmp)
    out = os.path.join(root, "robot.magic")
    return rm.build_project(os.path.join(root, "manifest.json"), out, audio_device="TestDevice", **kw), out, root


# ------------------------------------------------------------ the interpreter

def _translate(expr):
    return re.sub(r"\bif\(", "_if(", expr)


ENV = {"_if": lambda c, a, b: a if c else b, "floor": math.floor, "sin": math.sin, "min": min, "max": max, "abs": abs, "exp": math.exp}


def simulate(globals_, drive, frames):
    """Yield the value dict of each frame. `drive(frame)` gives the externally driven Globals (Beats, BeatFrac, Section, Bpm)."""
    code = {}
    for name, value, source, mods in globals_:
        code[name] = [compile(_translate(e), name, "eval") for kind, e in mods]
    prev = {name: value for name, value, _s, _m in globals_}
    prev.update(drive(0))
    for f in range(frames):
        cur = {}
        for name, value, source, mods in globals_:
            if source is None:
                cur[name] = prev[name]
                continue
            x = prev[source.split(":", 1)[1]] if source.startswith("global:") else 0
            for c in code[name]:
                x = eval(c, ENV, dict(prev, x=x, y=prev[name]))
            cur[name] = x
        cur.update(drive(f + 1))
        prev = cur
        yield cur


class Run:
    """A simulated walk: beats at a fixed frame interval, one section per beat, graph Globals only."""
    FRAMES_PER_BEAT = 29

    def __init__(self, m, sections, **graph):
        self.m, self.sections = m, sections
        self.globals = rm.graph_globals(m, **graph)
        self.frames = list(simulate(self.globals, self.drive, self.FRAMES_PER_BEAT * (len(sections) + 1)))

    def beat_of(self, f):
        return f // self.FRAMES_PER_BEAT

    def drive(self, f):
        beat = self.beat_of(f)
        e = self.sections[min(max(0, beat - 1), len(self.sections) - 1)]
        return {"Beats": beat, "BeatFrac": (f % self.FRAMES_PER_BEAT) / self.FRAMES_PER_BEAT, "Section": e, "Bpm": 124}

    def settled(self, beat):
        """Values just before the next beat: the pipeline has run."""
        return self.frames[(beat + 1) * self.FRAMES_PER_BEAT - 2]


class GraphGlobalsTests(unittest.TestCase):
    def setUp(self):
        self.m = mf.Manifest(json.load(open(os.path.join(HERE, "..", "..", "package", "fixture", "manifest.json"))))

    def test_globals_match_the_model(self):
        sections = ([0] * 8 + [2] * 8 + [3] * 8 + [2, 0, 3, 4] * 4) * 2
        for seed, rate in [(0, 1.0), (1, 1.0), (7.5, 0.5), (3, 0.0)]:
            with self.subTest(seed=seed, cut_rate=rate):
                run = Run(self.m, sections, seed=seed, cut_rate=rate)
                model = cg.ClipGraph(self.m, seed=seed, cut_rate=rate)
                walk = model.walk(sections)
                for beat in range(1, len(sections) + 1):
                    v, s = run.settled(beat), walk[beat - 1]
                    self.assertEqual((v["Move"], v["Angle"], v["MoveStart"]),
                                     (self.m.moves.index(self.m.move(s.move)), self.m.angle_ids.index(s.angle), s.start), "beat %d" % beat)
                    self.assertEqual(v["Sel"], v["Move"] * 2 + v["Angle"])
                    self.assertEqual(v["OutClip"], model.clip_index(s), "beat %d" % beat)

    def test_globals_match_the_model_with_3_key_poses_and_mixed_lengths(self):
        """package/many: 21 Moves of 4, 8 and 16 beats over 3 Key Poses; every Move pick, Angle cut and Clip index of the Globals equals the model's."""
        m = mf.Manifest(json.load(open(os.path.join(HERE, "..", "..", "package", "many", "manifest.json"))))
        sections = ([0] * 8 + [2] * 24 + [3] * 32 + [4] * 8 + [2, 3] * 8 + [3] * 24 + [0] * 8) * 1
        for seed, rate in [(0, 1.0), (4.5, 0.5)]:
            with self.subTest(seed=seed, cut_rate=rate):
                run = Run(m, sections, seed=seed, cut_rate=rate)
                model = cg.ClipGraph(m, seed=seed, cut_rate=rate)
                walk = model.walk(sections)
                for beat in range(1, len(sections) + 1):
                    v, s = run.settled(beat), walk[beat - 1]
                    self.assertEqual((v["Move"], v["Angle"], v["MoveStart"]),
                                     (m.moves.index(m.move(s.move)), m.angle_ids.index(s.angle), s.start), "beat %d" % beat)
                    self.assertEqual(v["OutClip"], model.clip_index(s), "beat %d" % beat)
                self.assertEqual({m.move(s.move).beats for s in walk if not m.move(s.move).idle}, {4, 8, 16})

    def test_globals_match_the_model_with_duel_angles(self):
        """package/duel: solo and duel Angle groups, the switch through the Idle Clips in the drop; every Move, Angle and Clip index equals the model's."""
        m = mf.Manifest(json.load(open(os.path.join(HERE, "..", "..", "package", "duel", "manifest.json"))))
        sections = [0] * 8 + [2] * 16 + [3] * 32 + [4] * 12 + [3] * 20 + [0] * 16
        for seed, rate in [(0, 1.0), (2.5, 0.5)]:
            with self.subTest(seed=seed, cut_rate=rate):
                run = Run(m, sections, seed=seed, cut_rate=rate)
                model = cg.ClipGraph(m, seed=seed, cut_rate=rate)
                walk = model.walk(sections)
                for beat in range(1, len(sections) + 1):
                    v, s = run.settled(beat), walk[beat - 1]
                    self.assertEqual((v["Move"], v["Angle"], v["MoveStart"]),
                                     (m.moves.index(m.move(s.move)), m.angle_ids.index(s.angle), s.start), "beat %d" % beat)
                    self.assertEqual(v["OutClip"], model.clip_index(s), "beat %d" % beat)
                    duel = m.move(s.move).opponent
                    local = [mv.name for mv in m.moves if mv.opponent == duel].index(s.move)
                    self.assertEqual(v["MoveInDuel" if duel else "MoveInSolo"], local, "beat %d" % beat)
                self.assertEqual({m.move(s.move).opponent for s in walk}, {False, True})

    def test_globals_match_the_model_with_variants(self):
        """package/variants: scored picks over families and variants, Idle chains (no calm Move out of guard) and each pick's cut chance;
        every Move, Angle, Clip index and Used beat equals the model's over 200 beats (the variant window is 128)."""
        with open(os.path.join(HERE, "..", "..", "package", "variants", "manifest.json")) as f:
            data = json.load(f)
        chain = dict(data, clips=[c for c in data["clips"] if c.get("variant_of", c["move"]) not in ("sway", "duck")])
        sections = [0] * 24 + [2] * 40 + [3] * 56 + [0] * 32 + [3] * 48
        for name, d, seed, rate in [("variants", data, 0, 1.0), ("variants with an Idle chain", chain, 2.5, 0.5)]:
            with self.subTest(name):
                m = mf.Manifest(d)
                run = Run(m, sections, seed=seed, cut_rate=rate)
                model = cg.ClipGraph(m, seed=seed, cut_rate=rate)
                walk = model.walk(sections)
                for beat in range(1, len(sections) + 1):
                    v, s = run.settled(beat), walk[beat - 1]
                    self.assertEqual((v["Move"], v["Angle"], v["MoveStart"]),
                                     (m.moves.index(m.move(s.move)), m.angle_ids.index(s.angle), s.start), "beat %d" % beat)
                    self.assertEqual(v["OutClip"], model.clip_index(s), "beat %d" % beat)
                    self.assertEqual({i: v["Used%d" % i] for i in range(len(m.moves)) if v["Used%d" % i]},
                                     {m.moves.index(m.move(n)): b for n, b in s.used}, "beat %d" % beat)

    def test_backdrop_globals_match_the_model(self):
        with open(os.path.join(HERE, "..", "..", "package", "variants", "manifest.json")) as f:
            m = mf.Manifest(json.load(f))
        sections = [0] * 12 + [2] * 20 + [3] * 24 + [4] * 16 + [0] * 8 + [3] * 24
        for seed, rate in [(0, 1.0), (7, 0.0)]:
            with self.subTest(seed=seed, cut_rate=rate):
                run = Run(m, sections, seed=seed, cut_rate=rate)
                model = cg.ClipGraph(m, seed=seed, cut_rate=rate)
                walk = model.walk(sections)
                bds = model.backdrops(walk, sections)
                self.assertGreater(len(set(bds)), 1)
                for beat in range(1, len(sections) + 1):
                    self.assertEqual(run.settled(beat)["Backdrop"], bds[beat - 1], "beat %d" % beat)

    def test_backdrop_layer(self):
        """Each Angle has an InputSelector over the backdrops' plates of that Angle, hidden off air; the gate reads Ground over the Android
        alone, the Live World and the backdrop; the plates loop and take no clip pulse."""
        with tempfile.TemporaryDirectory() as tmp:
            root = package_with_media(tmp, os.path.join(HERE, "..", "..", "package", "variants"))
            m = mf.Manifest(json.load(open(os.path.join(root, "manifest.json"))), root)
            built = rm.build(m).build()
        self.assertEqual([p for p in mp.check(built) if p[0] == "error"], [])
        nodes = mp.node_table(built, "Robot")
        plates = [n for n in nodes if n["plugin"] == "InputSelector" and any(p["source"] == "global:Backdrop" for p in n["params"])]
        self.assertEqual([len(n["inputs"]) for n in plates], [4] * len(m.angle_ids))
        files = [iv.get("value") for iv in built.iter("InputValue") if iv.get("name") == "File" and "backdrop/" in (iv.get("value") or "")]
        self.assertEqual(len(files), 16)
        gate = [n for n in nodes if n["plugin"] == "InputSelector" and any(p["source"] == "global:Ground" for p in n["params"])]
        self.assertEqual([len(n["inputs"]) for n in gate], [3])
        names = {g[0] for g in rm.ground_globals()}
        self.assertEqual(names, {"Ground", "BackdropOn"})

    def test_duel_project_layers(self):
        """Each Angle's selector holds the Moves of its kind and reads that kind's input Global; the project checks clean."""
        m = mf.Manifest(json.load(open(os.path.join(HERE, "..", "..", "package", "duel", "manifest.json"))))
        root = rm.build(m).build()
        self.assertEqual([p for p in mp.check(root) if p[0] == "error"], [])     # warnings: the media are not rendered here
        selectors = [n for n in mp.node_table(root, "Robot") if n["plugin"] == "InputSelector" and n["params"][0]["source"] != "global:LiveOn"]
        reads = sorted({p["source"] for n in selectors for p in n["params"] if p["name"] == "Input #"})
        self.assertEqual(reads, ["global:MoveInDuel", "global:MoveInSolo"])
        sizes = sorted({len(n["inputs"]) for n in selectors})
        self.assertEqual(sizes, sorted({sum(1 for mv in m.moves if mv.opponent), sum(1 for mv in m.moves if not mv.opponent)}))

    def test_section_steers_the_tier(self):
        for section, tier in [(0, "calm"), (1, "calm"), (2, "build"), (3, "drop"), (4, "calm")]:
            with self.subTest(section=section):
                run = Run(self.m, [section] * 20)
                moves = {self.m.moves[int(v["Move"])].name for v in run.frames[4 * 29 * 2:]}
                self.assertTrue(all(self.m.move(x).tier == tier or self.m.move(x).idle for x in moves), moves)

    def test_start_pulse_is_two_frames_at_each_move_change(self):
        run = Run(self.m, [2] * 24, seed=2)
        pulses = [i for i, v in enumerate(run.frames) if v["StartPulse"] > 0.5]
        changes = [i for i in range(1, len(run.frames)) if run.frames[i]["MoveStart"] != run.frames[i - 1]["MoveStart"]]
        self.assertEqual(len(changes), 6)
        for c in changes:
            with self.subTest(change_frame=c):
                self.assertIn(c, pulses)
                self.assertIn(c + 1, pulses)
                self.assertNotIn(c + 2, pulses)
        self.assertEqual(len(pulses), 2 * len(changes))

    def test_pipeline_latency_is_under_six_frames(self):
        """From the frame the beat count changes to the frame Move and Angle are latched."""
        run = Run(self.m, [2] * 24, seed=2)
        for beat in (4, 8, 12, 16):
            f0 = beat * run.FRAMES_PER_BEAT
            changed = next(i for i in range(f0, f0 + 20) if run.frames[i]["MoveStart"] == beat) - f0
            with self.subTest(beat=beat):
                self.assertLessEqual(changed, 5)

    def test_idle_clip_stays_on_air_and_its_frame_wraps(self):
        """Calm music from the start: the Idle Clip runs on, Move never changes, OutFrame counts up and wraps every 4 beats."""
        run = Run(self.m, [0] * 20)
        idle = self.m.moves.index(self.m.move("idle"))
        self.assertEqual({int(v["Move"]) for v in run.frames}, {idle})
        self.assertEqual({v["StartPulse"] for v in run.frames}, {0})
        frames = [v["OutFrame"] for v in run.frames[4 * run.FRAMES_PER_BEAT:]]
        wraps = sum(1 for a, b in zip(frames, frames[1:]) if b < a)
        self.assertGreaterEqual(wraps, 3)
        self.assertEqual(max(frames), self.m.move("idle").frames - 1)

    def test_clip_frame_counts_from_the_clip_start(self):
        sections = [2] * 12
        run = Run(self.m, sections, seed=2)
        model = cg.ClipGraph(self.m, seed=2)
        walk = model.walk(sections)
        for beat in range(1, 12):
            for f in range(beat * run.FRAMES_PER_BEAT + 6, (beat + 1) * run.FRAMES_PER_BEAT - 1):
                with self.subTest(frame=f):
                    expect = model.frame(walk[beat - 1], beat, (f % run.FRAMES_PER_BEAT) / run.FRAMES_PER_BEAT)
                    self.assertLessEqual(abs(run.frames[f]["OutFrame"] - expect), 1)

    def test_tier_changes_only_on_a_bar_line(self):
        run = Run(self.m, [0] * 5 + [3] * 7 + [0] * 8)
        tiers = [(i // run.FRAMES_PER_BEAT, v["Tier"]) for i, v in enumerate(run.frames)]
        changes = {tiers[i][0] for i in range(1, len(tiers)) if tiers[i][1] != tiers[i - 1][1]}
        self.assertEqual(changes, {8, 16})
        self.assertEqual([t for b, t in tiers if b == 7][-1], 0)
        self.assertEqual([t for b, t in tiers if b == 10][-1], 2)

    def test_speed_ratio_is_bpm_over_manifest_bpm(self):
        run = Run(self.m, [2] * 4)
        self.assertAlmostEqual(run.settled(2)["SpeedRatio"], 1.0)


class LiveGateTests(unittest.TestCase):
    FPS = 30

    def run_gate(self, toggle_times, seconds):
        """LiveOn per frame when the heartbeat value flips at each time in toggle_times (s)."""
        def drive(f):
            t = f / self.FPS
            return {"LiveRaw": sum(1 for x in toggle_times if x <= t) % 2, "Dt": 1.0 / self.FPS}
        frames = list(simulate(rm.live_globals(), drive, int(seconds * self.FPS)))
        return [fr["LiveOn"] for fr in frames]

    def at(self, series, seconds):
        return series[int(seconds * self.FPS)]

    def test_no_heartbeat_stays_off(self):
        self.assertEqual(set(self.run_gate([], 5)), {0})

    def test_heartbeat_switches_on_and_times_out(self):
        beats = [1.0, 1.5, 2.0, 2.5, 3.0]
        series = self.run_gate(beats, 8)
        for seconds, want in ((0.9, 0), (1.3, 1), (2.0, 1), (3.0, 1), (4.3, 1), (4.7, 0), (7.5, 0)):
            with self.subTest(seconds=seconds):
                self.assertEqual(self.at(series, seconds), want)

    def test_returns_after_a_gap(self):
        series = self.run_gate([1.0, 1.5, 6.0, 6.5], 9)
        for seconds, want in ((3.5, 0), (6.2, 1), (7.9, 1), (8.5, 0)):
            with self.subTest(seconds=seconds):
                self.assertEqual(self.at(series, seconds), want)

    def test_falls_back_within_two_seconds_of_the_last_beat(self):
        series = self.run_gate([1.0, 1.5, 2.0], 6)
        last_on = max(i for i, v in enumerate(series) if v)
        self.assertLessEqual(last_on / self.FPS - 2.0, 2.0)

    def test_osc_input_port_and_address(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _, _ = generated(tmp, osc_in=19402)
            self.assertEqual(mp.summary(root)["osc_in_ports"], ["19402"])
        with tempfile.TemporaryDirectory() as tmp:
            root, _, _ = generated(tmp)
            self.assertEqual(mp.summary(root)["osc_in_ports"], [str(rm.OSC_IN_PORT)])
            raw = mp.find_global(root, "LiveRaw")
            self.assertEqual(raw.get("featureString"), rm.LIVE_ADDRESS)
        self.assertEqual((rm.OSC_IN_PORT, rm.LIVE_ADDRESS), (9202, "/vj/live_layer"))


class ContractRowTests(unittest.TestCase):
    """The generator's addresses and Magic's input port are the rows of osc/contract.json."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(HERE, "..", "..", "..", "osc", "contract.json")) as f:
            cls.rows = {c["address"]: c for c in json.load(f)["controls"]}

    def test_osc_out_rows(self):
        for address, _glob, top in rm.OSC_ROWS:
            with self.subTest(address=address):
                self.assertEqual((self.rows[address]["max"], self.rows[address].get("direction")), (top, None))

    def test_live_layer_row(self):
        row = self.rows[rm.LIVE_ADDRESS]
        self.assertEqual((row["direction"], row["kind"], row["min"], row["max"]), ("to_magic", "int", 0, 1))
        self.assertIn("127.0.0.1:%d" % rm.OSC_IN_PORT, row["blender"]["effect"])


class ProjectTests(unittest.TestCase):
    def test_check_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, out, _ = generated(tmp)
            problems = mp.check(mp.read(out), os.path.dirname(out))
            self.assertEqual(problems, [])

    def test_semantic_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, out, _ = generated(tmp)
            self.assertEqual(snapshot(mp.read(out)), SNAPSHOT)

    def test_osc_rows_are_one_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, out, _ = generated(tmp, osc_port=9999)
            senders = {s["message"]: s for s in mp.osc_senders(mp.read(out))}
            self.assertEqual(sorted(senders), sorted(a for a, _g, _t in rm.OSC_ROWS))
            for s in senders.values():
                self.assertEqual((s["ip"], s["port"]), ("127.0.0.1", "9999"))

    def test_default_osc_target_is_the_scene_port(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, out, _ = generated(tmp)
            self.assertEqual({s["port"] for s in mp.osc_senders(mp.read(out))}, {"9201"})

    def test_every_video_file_is_a_manifest_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, out, pkg = generated(tmp)
            m = mf.load(os.path.join(pkg, "manifest.json"))
            files = [iv.get("value") for iv in root.iter("InputValue") if iv.get("name") == "File"]
            expect = [c["passes"][k] for k in ("shadow", "beauty") for a in m.angle_ids for mv in m.moves
                      for c in [m.clips[m.clip_index(mv.name, a)]]]
            self.assertEqual(files, expect)

    def test_video_files_loop_instead_of_going_black(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _, _ = generated(tmp)
            loops = [iv.get("value") for iv in root.iter("InputValue") if iv.get("name") == "Looping"]
        self.assertEqual(set(loops), {"1"})
        self.assertEqual(len(loops), 16)

    def test_syphon_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, out, _ = generated(tmp, live="ROBOT_TEST - Blender")
            servers = [iv.get("value") for iv in root.iter("InputValue") if iv.get("name") == "Server"]
            self.assertEqual(servers, ["ROBOT_TEST - Blender"])
        self.assertEqual(rm.LIVE_SERVER, "ROBOT_LIVE - Blender")

    def test_android_draws_without_the_live_source(self):
        """A missing Syphon server blacks out whatever is wired to it, so the gate picks the Android alone at LiveOn 0 and the live branch hangs off input 1 only."""
        with tempfile.TemporaryDirectory() as tmp:
            root, _, _ = generated(tmp)
            scene = next(s for s in mp.scenes(root) if s.get("name") == "Robot")
            nodes = {n.get("id"): n for n in mp.scene_nodes(scene)[1:]}
            plug = {i: n.get("pluginName") for i, n in nodes.items()}

            def reaches(i, plugin):
                return plug[i] == plugin or any(reaches(c.get("id"), plugin) for c in nodes[i].iter("Child") if c.get("id") in nodes)

            gate = next(n for n in nodes.values() if [c.get("id") for c in n.iter("Child")] and plug[[c.get("id") for c in n.iter("Child")][0]] == "Mask"
                        and plug[n.get("id")] == "InputSelector")
            first, second = [c.get("id") for c in gate.iter("Child")]
            self.assertFalse(reaches(first, "SyphonClient"))
            self.assertTrue(reaches(second, "SyphonClient"))
            self.assertEqual(float(mp.find_global(root, rm.LIVE_GATE).get("value")), 0)

    def test_the_graph_reads_only_what_the_audio_source_names(self):
        """Every name the graph's expressions read is a graph Global or one of the audio Globals."""
        m = mf.Manifest(FIXTURE_DATA)
        have = {g[0].lower() for g in rm.clock_globals() + rm.graph_globals(m)}
        used = {w.lower() for g in rm.graph_globals(m) for _k, e in g[3] for w in re.findall(r"[A-Za-z_]\w*", e)}
        funcs = {"if", "floor", "sin", "min", "max", "abs", "x", "y", "and", "or"}
        self.assertEqual(sorted(used - have - funcs), [])

    def test_audio_globals_do_not_share_a_name_in_any_case(self):
        names = [g[0].lower() for g in rm.clock_globals() + rm.graph_globals(mf.Manifest(FIXTURE_DATA))]
        self.assertEqual(sorted({n for n in names if names.count(n) > 1}), [])

    def test_the_tier_reads_one_section_global(self):
        sources = {g[0]: g[2] for g in rm.clock_globals()}
        self.assertEqual(sources[rm.xray.SECTION], "global:State")
        tier = next(e for g in rm.graph_globals(mf.Manifest(FIXTURE_DATA)) if g[0] == "Tier" for _k, e in g[3])
        self.assertIn("Section", tier)
        self.assertNotIn("State", tier.replace("Section", ""))


def snapshot(root):
    """Per scene: each module's plugin and the plugins of its inputs, plus the Globals its params link to."""
    out = {}
    globals_by_id = mp.global_names(root)
    for scene in mp.scenes(root):
        nodes = mp.scene_nodes(scene)[1:]
        plug = {n.get("id"): n.get("pluginName") for n in nodes}
        rows = []
        for n in nodes:
            links = sorted("%s<-%s" % (iv.get("name"), globals_by_id.get(iv.get("feature"))) for iv in mp.params(n)
                           if iv.get("linked") == "1" and iv.get("layerID") == str(mp.GLOBAL_LAYER))
            rows.append((plug[n.get("id")], [plug[c.get("id")] for c in n.iter("Child")], links))
        out[scene.get("name")] = rows
    return out


VIDEO = ("VideoFile", [], ["Goto Start<-StartPulse", "Speed<-SpeedRatio"])


def pass_layers(*hides):
    """Per Angle the Move InputSelector and its Transparency, then the Null that draws them all."""
    out = []
    for h in hides:
        out += [VIDEO] * 4 + [("InputSelector", ["VideoFile"] * 4, ["Input #<-Move"]), ("Transparency", ["InputSelector"], ["Amount<-%s" % h])]
    return out + [("Null", ["Transparency"] * len(hides), [])]


SNAPSHOT = {
    "Robot": [("SyphonClient", [], [])] + pass_layers("HideAngle0", "HideAngle1") + [("Blend", ["SyphonClient", "Null"], [])]
    + pass_layers("HideAngle0", "HideAngle1") + [("Mask", ["Null", "Null"], []),
       ("Transparency", ["Mask", "Blend"], []), ("OSC Out", [], []), ("InputSelector", ["Mask", "Transparency"], ["Input #<-LiveOn"]),
       ("Chroma Zoom", ["InputSelector"], ["Blue_zoom<-HitEnv", "Red_zoom<-HitEnv"]),
       ("Color Controls", ["Chroma Zoom"], ["Contrast<-GradeCon", "Saturation<-GradeSat"]),
       ("Bloom", ["Color Controls"], ["Intensity<-DropAmt"]), ("Bright", ["Bloom"], ["Bright<-HitEnv"])],
    "OSC Out": [("OSCSender", [], ["Value<-OutClip"]), ("OSCSender", [], ["Value<-OutFrame"]), ("OSCSender", [], ["Value<-OutAngle"])],
}


class EffectTests(unittest.TestCase):
    """The MMV effects (robot_magic.effect_globals and effect_chain): what drives them, and that each is the identity when switched off."""
    FPS = 60
    IDENTITY = {"Red_zoom": 1, "Blue_zoom": 1, "Saturation": 1, "Contrast": 1, "Intensity": 0, "Bright": 0}
    SWITCH = {"Red_zoom": "FxHit", "Blue_zoom": "FxHit", "Saturation": "FxGrade", "Contrast": "FxGrade", "Intensity": "FxDrop", "Bright": "FxHit FxStrobe"}

    def setUp(self):
        self.m = mf.Manifest(FIXTURE_DATA, os.path.join(HERE, "..", "..", "package", "fixture"))

    def run_fx(self, drive, seconds, hits=None):
        rows = rm.effect_globals(self.m, rm.clip_hits(self.m) if hits is None else hits)
        def full(f):
            return dict({"Dt": 1.0 / self.FPS, "Kick": 0, "Section": 0, "Tier": 0, "OutClip": 0, "OutFrame": 0, "Angle": 0, "Flavor": 0.5}, **drive(f))
        return list(simulate(rows, full, int(seconds * self.FPS)))

    def test_clip_hits_come_from_the_clip_data_and_a_missing_file_gives_none(self):
        hits = rm.clip_hits(self.m)
        self.assertEqual(len(hits), len(self.m.clips))
        jab = self.m.clip_index("jab_cross", "front")
        self.assertEqual(hits[jab], [14, 29])
        broken = mf.Manifest(FIXTURE_DATA, tempfile.gettempdir() + "/no_such_package")
        self.assertEqual(rm.clip_hits(broken), [[] for _ in broken.clips])

    def test_hits_with_a_target_flash_too(self):
        """An Exchange's Hits name a target (the giant's point, the Android's, the floor): every Hit drives the flash and split, whoever strikes."""
        for target in ("g_core", "head", "floor", None):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp:
                root = package_with_media(tmp)
                clip = FIXTURE_DATA["clips"][self.m.clip_index("front_kick", "front")]
                path = os.path.join(root, clip["clip_data"])
                cd = json.load(open(path))
                cd["hits"] = [dict({"f": 40, "point": [0.5, 0.4, 9], "strength": 1, "limb": "g_hammer"}, **({"target": target} if target else {}))]
                with open(path, "w") as f:
                    json.dump(cd, f)
                hits = rm.clip_hits(mf.Manifest(FIXTURE_DATA, root))
                self.assertEqual(hits[self.m.clip_index("front_kick", "front")], [40])

    def test_drivers(self):
        jab, idle = self.m.clip_index("jab_cross", "front"), self.m.clip_index("idle", "front")
        cases = [   # frames[i] is frame i + 1 of the drive; a Global reads the frame before
            ("a Hit frame flashes, then decays", "HitEnv", lambda f: {"OutClip": jab, "OutFrame": f}, [(14, 1.0), (15, 1.0), (26, (0.2, 0.4)), (5, 0.0)]),
            ("a Clip with no Hit does not", "HitEnv", lambda f: {"OutClip": idle, "OutFrame": f}, [(14, 0.0), (29, 0.0)]),
            ("an Angle cut strobes for a few frames", "StrobeEnv", lambda f: {"Angle": 1 if f >= 30 else 0}, [(30, 1.0), (45, (0.0, 0.05)), (10, 0.0)]),
            ("drop eases the glow in", "DropAmt", lambda f: {"Section": 3 if f >= 30 else 0}, [(20, 0.0), (90, (0.7, 1.0)), (200, (0.99, 1.0))]),
            ("breakdown after a drop eases it out", "DropAmt", lambda f: {"Section": 3 if f < 120 else 4}, [(110, (0.9, 1.0)), (300, (0.0, 0.05))]),
            ("calm grade", "GradeSat", lambda f: {"Tier": 0}, [(200, (0.74, 0.76))]),
            ("build grade", "GradeSat", lambda f: {"Tier": 1}, [(200, (1.04, 1.06))]),
            ("drop grade", "GradeCon", lambda f: {"Tier": 2}, [(200, (1.19, 1.21))]),
        ]
        for name, glob, drive, expect in cases:
            with self.subTest(name):
                frames = self.run_fx(drive, 6)
                for f, want in expect:
                    v = frames[int(f)][glob]
                    lo, hi = want if isinstance(want, tuple) else (want, want)
                    self.assertTrue(lo - 1e-9 <= v <= hi + 1e-9, (f, v, want))

    def params(self):
        """{param: modifier expression} of the effect modules' linked params."""
        b = rm.build(self.m, project_dir=os.path.join(HERE, "..", "..", "package", "fixture"))
        root = b.build()
        names = mp.global_names(root)
        out = {}
        for n in mp.node_table(root, "Robot"):
            if n["plugin"] in ("Chroma Zoom", "Color Controls", "Bloom", "Bright"):
                for p in n["params"]:
                    if p["name"] in self.IDENTITY and p["modifiers"]:
                        out[p["name"]] = p["modifiers"][0][2]
        return out

    def test_each_effect_is_the_identity_when_switched_off(self):
        exprs = self.params()
        self.assertEqual(set(exprs), set(self.IDENTITY))
        env = ENV
        for switch in ("FxHit", "FxDrop", "FxStrobe", "FxGrade"):
            for x in (0.0, 0.5, 1.0, 1.3):
                with self.subTest(switch=switch, x=x):
                    off = {s: 0 if s == switch else 1 for s in rm.FX}
                    for param, expr in exprs.items():
                        if self.SWITCH[param] == switch:
                            got = eval(_translate(expr), env, dict(off, x=x, Kick=1, StrobeEnv=0))
                            self.assertAlmostEqual(got, self.IDENTITY[param])
                    if switch in ("FxHit", "FxStrobe"):
                        all_off = dict(off, FxHit=0, FxStrobe=0)
                        self.assertAlmostEqual(eval(_translate(exprs["Bright"]), env, dict(all_off, x=x, StrobeEnv=x)), 0)

    def test_the_split_is_capped_whatever_the_flavor(self):
        exprs = self.params()
        for param, full in (("Red_zoom", 1 + rm.SPLIT), ("Blue_zoom", 1 - rm.SPLIT)):
            for x in (1.0, 1.2, 1.4):
                with self.subTest(param=param, x=x):
                    self.assertAlmostEqual(eval(_translate(exprs[param]), ENV, {"x": x, "FxHit": 1}), full)

    def test_effects_off_leaves_the_composite_as_the_output(self):
        b = rm.build(self.m, effects=False)
        plugins = {n["plugin"] for n in mp.node_table(b.build(), "Robot")}
        self.assertFalse(plugins & {"Chroma Zoom", "Color Controls", "Bloom", "Bright"})


def with_angles(n):
    d = json.loads(json.dumps(FIXTURE_DATA))
    base = [c for c in d["clips"] if c["angle"] == "front"]
    d["angles"] = [{"id": "a%d" % i, "camera": "CAM_%d" % i} for i in range(n)]
    d["clips"] = [dict(c, id="%s__a%d" % (c["move"], i), angle="a%d" % i) for c in base for i in range(n)]
    assert mf.validate(d) == [], mf.validate(d)
    return mf.Manifest(d)


class AllAnglesPlayTests(unittest.TestCase):
    """A VideoFile that is not drawn does not advance, so every Angle's layer is drawn all the time and the off-air ones are transparent."""

    def project(self, n):
        return rm.build(with_angles(n), osc_in=19407).build()

    def test_every_angle_has_a_layer_with_its_own_transparency_and_all_files_share_the_pulse(self):
        for n in (1, 2, 3):
            with self.subTest(angles=n):
                root = self.project(n)
                names = mp.global_names(root)
                scene = next(sc for sc in mp.scenes(root) if sc.get("name") == "Robot")
                nodes = mp.scene_nodes(scene)[1:]
                links = lambda node: {iv.get("name"): names.get(iv.get("feature")) for iv in mp.params(node)
                                      if iv.get("linked") == "1" and iv.get("layerID") == str(mp.GLOBAL_LAYER)}
                videos = [x for x in nodes if x.get("pluginName") == "VideoFile"]
                self.assertEqual(len(videos), 2 * n * 4)
                self.assertEqual({links(v)["Goto Start"] for v in videos}, {"StartPulse"})
                self.assertEqual({links(v)["Speed"] for v in videos}, {"SpeedRatio"})
                amounts = [links(x).get("Amount") for x in nodes if x.get("pluginName") == "Transparency"]
                self.assertEqual(sorted(a for a in amounts if a), sorted(["HideAngle%d" % i for i in range(n)] * 2))
                selectors = [links(x).get("Input #") for x in nodes if x.get("pluginName") == "InputSelector"]
                self.assertEqual(selectors.count("Move"), 2 * n)

    def test_the_off_air_angles_are_hidden_and_the_on_air_one_is_not(self):
        sections = [0] * 6 + [2] * 10 + [3] * 8 + [2, 0] * 6
        for n in (1, 2, 3):
            with self.subTest(angles=n):
                m = with_angles(n)
                run = Run(m, sections, cut_rate=1.0)
                walk = cg.ClipGraph(m, cut_rate=1.0).walk(sections)
                cuts = 0
                for beat in range(1, len(sections) + 1):
                    v = run.settled(beat)
                    on = m.angle_ids.index(walk[beat - 1].angle)
                    self.assertEqual([v["HideAngle%d" % i] for i in range(n)], [0 if i == on else 1 for i in range(n)], "beat %d" % beat)
                    cuts += beat > 1 and walk[beat - 1].angle != walk[beat - 2].angle
                self.assertEqual(cuts > 0, n > 1)

    def test_all_angles_start_a_move_together(self):
        """One StartPulse, two frames long, restarts every Angle's VideoFile; the Angle only changes which layer is visible."""
        for n in (2, 3):
            with self.subTest(angles=n):
                m = with_angles(n)
                run = Run(m, [2] * 24, seed=2, cut_rate=1.0)
                pulses = [i for i, v in enumerate(run.frames) if v["StartPulse"] > 0.5]
                self.assertEqual(len(pulses) % 2, 0)
                for i in pulses[::2]:
                    self.assertGreater(run.frames[i + 1]["StartPulse"], 0.5)
                changes = [i for i in range(1, len(run.frames)) if run.frames[i]["MoveStart"] != run.frames[i - 1]["MoveStart"]]
                self.assertEqual(sorted(set(changes) & set(pulses)), changes)


if __name__ == "__main__":
    unittest.main()
