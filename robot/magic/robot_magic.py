"""Robot Scene generator: a Manifest to a Magic project, built with magic/magicproj.py's Builder.

    python3 robot/magic/robot_magic.py robot/package/fixture/manifest.json [--out FILE] [--live "ROBOT_LIVE - Blender"]

Scene "Robot": a VideoFile per Clip (beauty and Shadow Pass) into two InputSelectors, the Live World (Syphon ROBOT_LIVE) behind
the Android: Blend multiplies the Shadow Pass onto the Live World, Mask applies the Matte (the beauty's alpha), Transparency
composites the Android in front. Scene "OSC Out": OSCSenders for the Robot rows.

The Clip Graph is Magic Globals (graph_globals), the same logic as clip_graph.py: beat clock and energy come from Magic's audio
(the Globals of magic/synthwave_magic.py, picked by name), Move and Angle are latched on the beat, the tables of the graph are
nested ifs written from the Manifest. Moves in the selectors are ordered move-major, Angle minor: input = move * angles + angle.
"""
import argparse
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "magic"))
import magicproj as mp  # noqa: E402
import synthwave_magic as sm  # noqa: E402
from clip_graph import SALT_ANGLE, SALT_CUT, SALT_MOVE  # noqa: E402
from manifest import load  # noqa: E402

# One table for the OSC rows (proposed in robot/CONTRACTS.md, not yet in osc/contract.json): address, Out Global, wire maximum.
OSC_ROWS = [("/vj/clip", "OutClip", 255), ("/vj/clip_frame", "OutFrame", 4095), ("/vj/angle", "OutAngle", 7)]
OSC_IP, OSC_PORT = "127.0.0.1", 9201
LIVE_SERVER = "ROBOT_LIVE - Blender"      # Magic names a Syphon server "<server> - <app>"
OUTPUT_SERVER = "Main Server"
LIVE_GATE = "LiveOn"                       # 0 draws the Android alone, 1 composites the Live World
LIVE_ADDRESS = "/vj/live_layer"            # int from Blender's live layer, toggles 0/1 at 2 Hz while ROBOT_LIVE draws
OSC_IN_PORT = 9202                         # Magic's OSC input, 127.0.0.1
HIDE_ANGLE = "HideAngle"                   # HideAngle<i>: 1 while Angle i is off air, the Transparency of its layer
LIVE_TIMEOUT = 1.5                         # seconds without a toggle until LiveOn falls back to 0
BLEND_MULTIPLY = 3                         # Blend Mode values, modules.md

# Names taken from synthwave_magic.GLOBALS: audio bands, Clock, onsets, kick, beat clock (Phase, Tick, Beats, Bars, BPM), energy.
CLOCK_GLOBALS = ["Gain", "Sub", "Low", "Mid", "HiMid", "Air", "ClockPrev", "Clock", "Dt", "SubAvg", "HiMidAvg", "AirAvg", "KickBand",
                 "KFast", "KSlow", "KRef", "KRaw", "KOn", "Period", "GapAtKick", "KickT", "KickGap", "Kick", "Lock", "PhasePrev",
                 "Phase", "Tick", "Pulse", "BPM", "Beats", "Bars", "EnergyNow", "EnergyAvg"]
FREQ_NAMES = ["20-80 Hz", "80-320 Hz", "320-1.2k Hz", "1.2k-5k Hz", "5k-20k Hz"]


def clock_globals():
    """(name, value, source, mods) in Builder form for CLOCK_GLOBALS, read from the synthwave table."""
    by_name = {g[0]: g for g in sm.GLOBALS}
    out = []
    for name in CLOCK_GLOBALS:
        _n, src, value, ops = by_name[name]
        if isinstance(src, tuple):
            src = "audio:Source 0:Freq. Range:%s" % FREQ_NAMES[src[2]] if src[0] == "audio" else "global:%s" % src[1]
        mods = [(kind, expr if kind == "Expression" else param) for kind, param, expr in ops]
        out.append((name, value, src, mods))
    return out


# ------------------------------------------------------------ expression writing

def num(v):
    return "%.10g" % v


def table(var, values):
    """Nested ifs: values[i] where var == i, the last value otherwise."""
    expr = num(values[-1])
    for i in range(len(values) - 2, -1, -1):
        expr = "if(%s == %d, %s, %s)" % (var, i, num(values[i]), expr)
    return expr


def pick(cands):
    """The candidate chosen by PickH, as clip_graph.next_move: cands[min(n-1, floor(PickH*n))]."""
    n = len(cands)
    expr = num(cands[-1])
    for i in range(n - 2, -1, -1):
        expr = "if(floor(PickH*%d) == %d, %s, %s)" % (n, i, num(cands[i]), expr)
    return expr


def hash_expr(count, salt):
    return "sin(%s*12.9898 + Seed*78.233 + %s*37.719)*43758.5453" % (count, num(salt))


def ex(expr):
    return ("Expression", expr)


def graph_globals(m, seed=0, tier_build=0.25, tier_drop=0.55, cut_rate=1.0):
    """The Clip Graph of Manifest `m` as Globals (name, value, source, mods). Reads Beats, Bars, Phase, EnergyAvg, BPM.

    Every Global reads the previous frame, so the graph runs as a pipeline after the beat count changes (b = the frame it changes):
    BeatEv b+1, Wrap and NxtMove b+3 (the pick needs PickH and PickNext first), Move and Angle b+4, Sel b+5.
    """
    M, A = len(m.moves), len(m.angles)
    graph_moves = {mv.name: i for i, mv in enumerate(m.moves)}
    from clip_graph import ClipGraph
    g = ClipGraph(m)
    tiers = ("calm", "build", "drop")
    entries = []
    for t in tiers:
        for mv in m.moves:
            entries.append([graph_moves[c] for c in g.pool(mv.name, t)])
    pick_table = "0"
    for k in range(len(entries) - 1, -1, -1):
        pick_table = pick(entries[k]) if k == len(entries) - 1 else "if(Tier*%d + Move == %d, %s, %s)" % (M, k, pick(entries[k]), pick_table)
    ends = "BeatEv2 > 0.5 and (if(IsIdle > 0.5, Beats - floor(Beats/4)*4 == 0 and Beats - MoveStart > 0 and PickNext != Move, Beats - MoveStart >= MoveBeats))"
    cut_tests = ["(%s)" % " or ".join("NxtOff == %d" % c for c in mv.cut_points) for mv in m.moves]
    cut_here = cut_tests[-1]
    for i in range(M - 2, -1, -1):
        cut_here = "if(NxtMove == %d, %s, %s)" % (i, cut_tests[i], cut_here)
    per_beat = m.fps * 60.0 / m.bpm
    out = [
        ("Seed", seed, None, []),
        ("CutRate", cut_rate, None, []),
        ("TierBuild", tier_build, None, []),
        ("TierDrop", tier_drop, None, []),
        ("BeatsPrev", 0, "calc", [ex("Beats")]),
        ("BeatEv", 0, "calc", [ex("if(Beats > BeatsPrev, 1, 0)")]),
        ("BeatEv2", 0, "calc", [ex("BeatEv")]),
        ("BeatEv3", 0, "calc", [ex("BeatEv2")]),
        ("Tier", 0, "calc", [ex("if(EnergyAvg < TierBuild, 0, if(EnergyAvg < TierDrop, 1, 2))")]),
        ("MoveBeats", 0, "calc", [ex(table("Move", [mv.beats for mv in m.moves]))]),
        ("MoveFrames", 0, "calc", [ex(table("Move", [mv.frames for mv in m.moves]))]),
        ("IsIdle", 0, "calc", [ex(table("Move", [1 if mv.idle else 0 for mv in m.moves]))]),
        ("PickH", 0, "calc", [ex(hash_expr("floor(Beats/4)", SALT_MOVE)), ex("x - floor(x)")]),
        ("PickNext", 0, "calc", [ex(pick_table)]),
        ("AngleH", 0, "calc", [ex(hash_expr("Beats", SALT_CUT)), ex("x - floor(x)")]),
        ("AngleH2", 0, "calc", [ex(hash_expr("Beats", SALT_ANGLE)), ex("x - floor(x)")]),
        ("Wrap", 0, "calc", [ex("if(%s, 1, 0)" % ends)]),
        ("WrapPrev", 0, "calc", [ex("Wrap")]),
        ("NxtMove", 0, "calc", [ex("if(%s, PickNext, Move)" % ends)]),
        ("NxtOff", 0, "calc", [ex("if(%s, 0, (Beats - MoveStart) %% max(1, MoveBeats))" % ends)]),
        ("Move", 0, "calc", [ex("if(Wrap > 0.5, NxtMove, y)")]),
        ("MoveStart", 0, "calc", [ex("if(Wrap > 0.5, Beats, y)")]),
        ("Angle", 0, "calc", [ex("if(BeatEv3 > 0.5 and (%s) and AngleH < CutRate, (Angle + 1 + floor(AngleH2*%d)) %% %d, y)"
                                 % (cut_here, A - 1, A) if A > 1 else "0")]),
        ("Sel", 0, "calc", [ex("Move*%d + Angle" % A)]),
    ] + [(HIDE_ANGLE + str(a), 1, "calc", [ex("if(Angle == %d, 0, 1)" % a)]) for a in range(A)] + [
        ("StartPulse", 0, "calc", [ex("max(Wrap, WrapPrev)")]),
        ("SpeedRatio", 1, "calc", [ex("BPM/%s" % num(m.bpm))]),
        ("OutClip", 0, "calc", [ex(table("Sel", [m.clip_index(mv.name, a) for mv in m.moves for a in m.angle_ids]))]),
        ("OutFrame", 0, "calc", [ex("if(IsIdle > 0.5, max(0, floor((Beats - MoveStart + Phase)*%s)) %% max(1, MoveFrames), max(0, min(MoveFrames - 1, floor((Beats - MoveStart + Phase)*%s))))"
                                    % (num(per_beat), num(per_beat)))]),
        ("OutAngle", 0, "calc", [ex("Angle")]),
    ]
    return out


# ------------------------------------------------------------ project

def live_globals(timeout=LIVE_TIMEOUT):
    """LiveOn follows the heartbeat: 1 for `timeout` s after each change of the received value, else 0. LiveTimer starts at 0, so no heartbeat means 0."""
    return [
        ("LiveRaw", 0, "osc:%s" % LIVE_ADDRESS, []),
        ("LivePrev", 0, "calc", [ex("LiveRaw")]),  # a plain global: link reads the same frame, an Expression reads the last one
        ("LiveChanged", 0, "calc", [ex("if(LiveRaw != LivePrev, 1, 0)")]),
        ("LiveTimer", 0, "calc", [ex("if(LiveChanged > 0.5, %s, max(0, y - Dt))" % num(timeout))]),
        (LIVE_GATE, 0, "calc", [ex("if(LiveTimer > 0, 1, 0)")]),
    ]


def build(m, live=LIVE_SERVER, osc_ip=OSC_IP, osc_port=OSC_PORT, seed=0, size=None, project_dir=None, audio_device=None, osc_in=OSC_IN_PORT, clock=None, **graph):
    """Builder (not yet built) of the Robot project for Manifest `m`. File params are relative to project_dir when given.
    `clock` replaces the audio clock Globals (name, value, source, mods), for a test that drives Beats, Phase, EnergyAvg and BPM itself."""
    b = mp.Builder(syphon=OUTPUT_SERVER, size=tuple(size or m.size), fps=m.fps, audio_device=audio_device, osc_in=osc_in)
    for name, value, source, mods in (clock if clock is not None else clock_globals()) + graph_globals(m, seed=seed, **graph):
        b.glob(name, value, source, mods)
    for g in live_globals():
        b.glob(*g)
    robot, osc = b.scene("Robot"), b.scene("OSC Out")

    def clip_files(kind):
        """Every Angle's InputSelector over the Moves, each drawn all the time (Transparency 0 on air, 1 off air), so the Angles advance in
        step and a cut lands on the same frame: a VideoFile that is not drawn does not advance (idle_check.py)."""
        layers = []
        for a, angle in enumerate(m.angle_ids):
            nodes = []
            for mv in m.moves:
                path = m.path(m.clips[m.clip_index(mv.name, angle)]["passes"][kind])
                path = os.path.relpath(path, project_dir) if project_dir else os.path.abspath(path)
                nodes.append(robot.node("VideoFile", {"File": path, "Speed": ("global:SpeedRatio", [], 1), "Goto Start": ("global:StartPulse", [], 0),
                                                      "Looping": 1}))   # Looping 0 draws black after the last frame (restart_check.py); 1 replays instead
            moves = robot.node("InputSelector", {"Input #": ("global:Move", [], 0)}, inputs=nodes)
            layers.append(robot.node("Transparency", {"Amount": ("global:%s%d" % (HIDE_ANGLE, a), [], 1)}, inputs=[moves]))
        return robot.node("Null", inputs=layers)

    world = robot.node("SyphonClient", {"Server": live})
    shadow = clip_files("shadow")
    shaded = robot.node("Blend", {"Mode": BLEND_MULTIPLY}, inputs=[world, shadow])
    beauty = clip_files("beauty")
    matte = robot.node("Mask", {"Use Alpha": 1}, inputs=[beauty, beauty])
    comp = robot.node("Transparency", {"Amount": 0}, inputs=[matte, shaded])
    osc_mod = robot.scene_module(osc)
    # A module wired to a missing Syphon server draws black, bypassed or not; an InputSelector only evaluates the input it draws.
    gate = robot.node("InputSelector", {"Input #": ("global:%s" % LIVE_GATE, [], 0)}, inputs=[matte, comp])
    robot.output(gate, osc_mod)
    senders = []
    for address, glob, top in OSC_ROWS:
        senders.append(osc.node("OSCSender", {"IP Addr.": osc_ip, "Port": osc_port, "Message": address,
                                              "Value": ("global:%s" % glob, [ex("min(%d, max(0, floor(x + 0.5)))" % top)], 0)}))
    osc.output(*senders)
    return b


def build_project(manifest_path, out=None, **kw):
    """Root element of the Robot project; with `out` also written there."""
    m = load(manifest_path)
    b = build(m, project_dir=os.path.dirname(os.path.abspath(out)) if out else None, **kw)
    root = b.build()
    for iv in root.iter("InputValue"):
        if iv.get("name") == "File" and iv.get("value"):
            base = os.path.dirname(os.path.abspath(out)) if out else ""
            iv.set("absoluteFilename", os.path.normpath(os.path.join(base, iv.get("value"))))
    if out:
        mp.write(out, root)
    return root


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("manifest")
    ap.add_argument("--out", help="default: <manifest folder>/robot.magic")
    ap.add_argument("--live", default=LIVE_SERVER)
    ap.add_argument("--osc-ip", default=OSC_IP)
    ap.add_argument("--osc-port", type=int, default=OSC_PORT)
    ap.add_argument("--osc-in", type=int, default=OSC_IN_PORT, help="Magic OSC input port for the live heartbeat")
    ap.add_argument("--seed", type=float, default=0)
    a = ap.parse_args()
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.manifest)), "robot.magic")
    root = build_project(a.manifest, out, live=a.live, osc_ip=a.osc_ip, osc_port=a.osc_port, osc_in=a.osc_in, seed=a.seed)
    print("wrote %s (%d globals, %d OSC rows -> %s:%d)" % (out, len(mp.global_names(root)), len(OSC_ROWS), a.osc_ip, a.osc_port))


if __name__ == "__main__":
    main()
