"""Robot Scene generator: a Manifest to a Magic project, built with magic/magicproj.py's Builder.

    python3 robot/magic/robot_magic.py robot/package/fixture/manifest.json [--out FILE] [--live "ROBOT_LIVE - Blender"]

Scene "Robot": a VideoFile per Clip (beauty and Shadow Pass) into two InputSelectors, the Live World (Syphon ROBOT_LIVE) behind
the Android: Blend multiplies the Shadow Pass onto the Live World, Mask applies the Matte (the beauty's alpha), Transparency
composites the Android in front. Scene "OSC Out": OSCSenders for the Robot rows.

The Clip Graph is Magic Globals (graph_globals), the same logic as clip_graph.py: beat clock and section come from Magic's audio
(the Globals of xray.py: Beats, BeatFrac, Bpm and Section, whose Music X-Ray State sets the Intensity Tier), Move and Angle are latched on the beat, the tables of the graph are
nested ifs written from the Manifest. Moves in the selectors are ordered move-major, Angle minor: input = move * angles + angle.
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "magic"))
import magicproj as mp  # noqa: E402
import xray  # noqa: E402
from clip_graph import FAMILY_WINDOW, SALT_ANGLE, SALT_CUT, SALT_FAMILY, SALT_FLAVOR, SALT_VARIANT, VARIANT_WINDOW  # noqa: E402
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


def clock_globals():
    """(name, value, source, mods) of the audio analysis: beat clock and section, see xray.py."""
    return xray.globals_()


# ------------------------------------------------------------ expression writing

def num(v):
    return "%.10g" % v


def tree(var, items, lo=0):
    """items[i] (expressions) where the integer var == lo + i, by halves so the nesting stays log2(n) deep (ExprTk and the tests'
    interpreter limit nesting); below lo the first, past the end the last."""
    if len(items) == 1:
        return items[0]
    mid = len(items) // 2
    return "if(%s < %d, %s, %s)" % (var, lo + mid, tree(var, items[:mid], lo), tree(var, items[mid:], lo + mid))


def table(var, values):
    """values[i] where the integer var == i, the last value past the end."""
    return tree(var, [num(v) for v in values])


def pick(cands):
    """The candidate with the best Score, the first on a tie, as clip_graph.next_move."""
    expr = num(cands[-1])
    for i in range(len(cands) - 2, -1, -1):
        rest = ["%s%d" % (SCORE, c) for c in cands[i + 1:]]
        best = rest[0] if len(rest) == 1 else "max(%s)" % ", ".join(rest)
        expr = "if(%s%d >= %s, %s, %s)" % (SCORE, cands[i], best, num(cands[i]), expr)
    return expr


def hash_expr(count, salt):
    return "sin(%s*12.9898 + Seed*78.233 + %s*37.719)*43758.5453" % (count, num(salt))


def frac01(count, salt):
    """hash01 of clip_graph inline: x - floor(x) of the hash (ExprTk's frac keeps the sign)."""
    h = hash_expr(count, salt)
    return "((%s) - floor(%s))" % (h, h)


SCORE, USED = "Score", "Used"       # Score<i>, Used<i>: per Move, its pick score and the beat it was last picked (0: never)


def score_expr(m, mv):
    """clip_graph.ClipGraph.score of Move `mv` at the current beat, from the Used Globals of its family."""
    fam = [USED + str(m.moves.index(m.move(v))) for v in m.variants(mv.family)]
    fu = fam[0] if len(fam) == 1 else "max(%s)" % ", ".join(fam)
    vu = USED + str(m.moves.index(mv))
    return ("if(%s < 0.5 or Beats - %s >= %d, 1024 + 8*floor(64*%s), 8*floor(64*(Beats - %s)/%d))"
            " + if(%s < 0.5 or Beats - %s >= %d, 4 + 2*%s, 2*(Beats - %s)/%d)") % (
        fu, fu, FAMILY_WINDOW, frac01("floor(Beats/4)", SALT_FAMILY + m.families.index(mv.family)), fu, FAMILY_WINDOW,
        vu, vu, VARIANT_WINDOW, frac01("floor(Beats/4)", SALT_VARIANT + m.moves.index(mv)), vu, VARIANT_WINDOW)


def ex(expr):
    return ("Expression", expr)


def graph_globals(m, seed=0, cut_rate=1.0, duel_tiers=("drop",)):
    """The Clip Graph of Manifest `m` as Globals (name, value, source, mods). Reads Beats, BeatFrac, Section, Bpm.

    Every Global reads the previous frame, so the graph runs as a pipeline after the beat count changes (b = the frame it changes):
    BeatEv and Score b+1, PickNext and Chain b+2, Wrap and NxtMove b+3, Move, Used and Angle b+4, Sel b+5.
    """
    M, A = len(m.moves), len(m.angles)
    graph_moves = {mv.name: i for i, mv in enumerate(m.moves)}
    from clip_graph import ClipGraph
    g = ClipGraph(m, duel_tiers=duel_tiers)
    tiers = ("calm", "build", "drop")
    entries, chains = [], []
    for t in tiers:
        for mv in m.moves:
            entries.append([graph_moves[c] for c in g.pool(mv.name, t)])
            chains.append(1 if g.chain(mv.name, t) else 0)
    pick_table = tree("(Tier*%d + Move)" % M, [pick(e) for e in entries])
    ends = ("BeatEv2 > 0.5 and (if(IsIdle > 0.5, Beats - floor(Beats/4)*4 == 0 and Beats - MoveStart > 0 and PickNext != Move"
            " and (Chain < 0.5 or Beats - MoveStart >= MoveBeats), Beats - MoveStart >= MoveBeats))")
    cut_tests = ["(%s)" % " or ".join("NxtOff == %d" % c for c in mv.cut_points) for mv in m.moves]
    cut_here = tree("NxtMove", cut_tests)
    per_beat = m.fps * 60.0 / m.bpm
    out = [
        ("Seed", seed, None, []),
        ("CutRate", cut_rate, None, []),
        ("BeatsPrev", 0, "calc", [ex("Beats")]),
        ("BeatEv", 0, "calc", [ex("if(Beats > BeatsPrev, 1, 0)")]),
        ("BeatEv2", 0, "calc", [ex("BeatEv")]),
        ("BeatEv3", 0, "calc", [ex("BeatEv2")]),
        # the Intensity Tier follows the section on a bar line only, in the frame BeatEv is (the pick reads it one frame later); 2 buildup is build (1), 3 drop is drop (2), the rest calm (0)
        ("Tier", 0, "calc", [ex("if(Beats > BeatsPrev and Beats - floor(Beats/4)*4 == 0, if(abs(Section - 3) < 0.5, 2, if(abs(Section - 2) < 0.5, 1, 0)), y)")]),
        ("MoveBeats", 0, "calc", [ex(table("Move", [mv.beats for mv in m.moves]))]),
        ("MoveFrames", 0, "calc", [ex(table("Move", [mv.frames for mv in m.moves]))]),
        ("IsIdle", 0, "calc", [ex(table("Move", [1 if mv.idle else 0 for mv in m.moves]))]),
    ] + [(SCORE + str(i), 0, "calc", [ex(score_expr(m, mv))]) for i, mv in enumerate(m.moves)] + [
        ("PickNext", 0, "calc", [ex(pick_table)]),
        ("Chain", 0, "calc", [ex(table("(Tier*%d + Move)" % M, chains))]),
        ("AngleH", 0, "calc", [ex(hash_expr("Beats", SALT_CUT)), ex("x - floor(x)")]),
        ("AngleH2", 0, "calc", [ex(hash_expr("Beats", SALT_ANGLE)), ex("x - floor(x)")]),
        ("Wrap", 0, "calc", [ex("if(%s, 1, 0)" % ends)]),
        ("WrapPrev", 0, "calc", [ex("Wrap")]),
        ("NxtMove", 0, "calc", [ex("if(%s, PickNext, Move)" % ends)]),
        ("NxtOff", 0, "calc", [ex("if(%s, 0, (Beats - MoveStart) %% max(1, MoveBeats))" % ends)]),
        ("Move", 0, "calc", [ex("if(Wrap > 0.5, NxtMove, y)")]),
        ("MoveStart", 0, "calc", [ex("if(Wrap > 0.5, Beats, y)")]),
    ] + [(USED + str(i), 0, "calc", [ex("if(Wrap > 0.5 and NxtMove == %d, Beats, y)" % i)]) for i in range(M)] + [
        ("Flavor", 0, "calc", [ex(frac01("MoveStart", SALT_FLAVOR))]),
        ("Angle", 0, "calc", [ex(angle_expr(m, cut_here))]),
        ("Sel", 0, "calc", [ex("Move*%d + Angle" % A)]),
    ] + [(HIDE_ANGLE + str(a), 1, "calc", [ex("if(Angle == %d, 0, 1)" % a)]) for a in range(A)] + [
        ("StartPulse", 0, "calc", [ex("max(Wrap, WrapPrev)")]),
        ("SpeedRatio", 1, "calc", [ex("%s/%s" % (xray.BPM, num(m.bpm)))]),
        ("OutClip", 0, "calc", [ex(table("Sel", [clip_on(m, mv, a) for mv in m.moves for a in m.angle_ids]))]),
        ("OutFrame", 0, "calc", [ex("if(IsIdle > 0.5, max(0, floor((Beats - MoveStart + BeatFrac)*%s)) %% max(1, MoveFrames), max(0, min(MoveFrames - 1, floor((Beats - MoveStart + BeatFrac)*%s))))"
                                    % (num(per_beat), num(per_beat)))]),
        ("OutAngle", 0, "calc", [ex("Angle")]),
    ]
    for duel in (False, True):
        if m.group(duel) and len(local_moves(m, duel)) != len(m.moves):
            out.append((MOVE_IN[duel], 0, "calc", [ex(table("Move", [local_moves(m, duel).index(mv) if mv in local_moves(m, duel) else 0 for mv in m.moves]))]))
    return out


MOVE_IN = {False: "MoveInSolo", True: "MoveInDuel"}      # the input of a solo or duel Angle's selector: the Move's place among the Moves of that kind


def local_moves(m, duel):
    """The Moves of one kind, in Manifest order: what a solo or duel Angle's selector holds."""
    return [mv for mv in m.moves if mv.opponent == duel]


def move_input(m, duel):
    """The Global a selector of that kind reads: Move itself when every Move is of that kind (a solo-only Manifest)."""
    return "Move" if len(local_moves(m, duel)) == len(m.moves) else MOVE_IN[duel]


def clip_on(m, mv, angle):
    """/vj/clip of a Move on an Angle; a Move has no Clip on the other kind's Angles, which the graph never shows, so its first Angle's Clip stands in."""
    if (mv.name, angle) in m._by:
        return m.clip_index(mv.name, angle)
    return m.clip_index(mv.name, m.group(mv.opponent)[0])


def angle_expr(m, cut_here):
    """Angle after a beat: the first Angle of the new kind when the Move's kind changes, else a cut within the Angles of its kind (clip_graph.next_angle)."""
    A = len(m.angle_ids)
    if A < 2:
        return "0"
    duel = [1 if m.angle_duel(a) else 0 for a in m.angle_ids]
    groups = {d: [m.angle_ids.index(a) for a in m.group(d)] for d in (False, True)}
    pos = [groups[bool(duel[i])].index(i) for i in range(A)]

    def cut(d):
        g = groups[d]
        if len(g) < 2:
            return "y"
        return table("((%s + 1 + floor(AngleH2*%d)) %% %d)" % (table("Angle", pos), len(g) - 1, len(g)), g)
    within = cut(False) if not groups[True] else "if(%s == 1, %s, %s)" % (table("Angle", duel), cut(True), cut(False))
    flavor = frac01("if(Wrap > 0.5, Beats, MoveStart)", SALT_FLAVOR)     # the Flavor of the Move that starts or runs in this frame
    cut_branch = "if(BeatEv3 > 0.5 and (%s) and AngleH < CutRate*(0.4 + 1.2*%s), %s, y)" % (cut_here, flavor, within)
    if not groups[True]:
        return cut_branch
    kind_n = table("NxtMove", [1 if mv.opponent else 0 for mv in m.moves])
    return "if(BeatEv3 > 0.5 and %s != %s, if(%s == 1, %d, %d), %s)" % (kind_n, table("Angle", duel), kind_n, groups[True][0], groups[False][0], cut_branch)


# ------------------------------------------------------------ effects

# Switches (manual Globals, 1 on, 0 off): each effect is the identity of its modules at 0, so switching one off never changes the frame otherwise.
FX = {"FxHit": 1, "FxDrop": 1, "FxStrobe": 1, "FxGrade": 1}
GRADE = {"calm": (0.75, 0.95), "build": (1.05, 1.08), "drop": (1.3, 1.2)}     # tier: Saturation, Contrast of Color Controls
HIT_DECAY, STROBE_DECAY, DROP_TAU, GRADE_TAU = 0.15, 0.06, 0.4, 0.5         # seconds
SPLIT, HIT_FLASH, STROBE_FLASH, FLASH_MAX = 0.025, 0.35, 0.5, 0.6


def clip_hits(m):
    """Hit frames per Clip index from the Clip Data; a Clip whose Clip Data is missing or unreadable has none (no flash, never an error)."""
    out = []
    for c in m.clips:
        try:
            with open(m.path(c["clip_data"])) as f:
                out.append(sorted({int(h["f"]) for h in json.load(f).get("hits", [])}))
        except (OSError, ValueError, KeyError, TypeError):
            out.append([])
    return out


def effect_globals(m, hits, fx=None):
    """Globals of the MMV effects (name, value, source, mods). Reads OutClip, OutFrame, Angle, Flavor, Tier, Section, Kick and Dt.
    HitEnv: 0.6 + 0.8 x Flavor for the 2 frames of a Clip Data Hit, then decays (flash and chromatic split). StrobeEnv: as much in the frame
    after an Angle cut, then decays. So each pick hits and cuts with its own strength.
    DropAmt: eases to 1 while X-Ray says drop (glow). GradeSat, GradeCon: ease to the tier's grade."""
    fx = dict(FX, **(fx or {}))
    hit = tree("OutClip", ["if(%s, 1, 0)" % " or ".join("(OutFrame >= %d and OutFrame < %d)" % (f, f + 2) for f in h) if h else "0" for h in hits] + ["0"])
    ease = lambda target, tau: ex("y + ((%s) - y)*(1 - exp(-Dt/%s))" % (target, num(tau)))
    tier = lambda vals: "if(Tier == 2, %s, if(Tier == 1, %s, %s))" % (num(vals[2]), num(vals[1]), num(vals[0]))
    sat, con = [[GRADE[t][k] for t in ("calm", "build", "drop")] for k in (0, 1)]
    return [(name, value, None, []) for name, value in sorted(fx.items())] + [
        ("HitEnv", 0, "calc", [ex("max((%s)*(0.6 + 0.8*Flavor), y*exp(-Dt/%s))" % (hit, num(HIT_DECAY)))]),
        ("AngleLag", 0, "calc", [ex("Angle")]),
        ("StrobeEnv", 0, "calc", [ex("max(if(Angle != AngleLag, 0.6 + 0.8*Flavor, 0), y*exp(-Dt/%s))" % num(STROBE_DECAY))]),
        ("DropAmt", 0, "calc", [ease("if(abs(Section - 3) < 0.5, 1, 0)", DROP_TAU)]),
        ("GradeSat", 1, "calc", [ease(tier(sat), GRADE_TAU)]),
        ("GradeCon", 1, "calc", [ease(tier(con), GRADE_TAU)]),
    ]


def effect_chain(scene, src):
    """The effect modules after `src`, in order: chromatic split, grade, glow, flash. Each is the identity when its switch is 0 or its Global rests."""
    split = scene.node("Chroma Zoom", {"Red_zoom": ("global:HitEnv", [ex("1 + %s*x*FxHit" % num(SPLIT))], 1),
                                       "Blue_zoom": ("global:HitEnv", [ex("1 - %s*x*FxHit" % num(SPLIT))], 1)}, inputs=[src])
    grade = scene.node("Color Controls", {"Saturation": ("global:GradeSat", [ex("1 + (x - 1)*FxGrade")], 1),
                                          "Contrast": ("global:GradeCon", [ex("1 + (x - 1)*FxGrade")], 1)}, inputs=[split])
    glow = scene.node("Bloom", {"Intensity": ("global:DropAmt", [ex("x*FxDrop*(0.5 + 0.5*Kick)")], 0)}, inputs=[grade])
    return scene.node("Bright", {"Bright": ("global:HitEnv", [ex("min(%s, %s*x*FxHit + %s*StrobeEnv*FxStrobe)" % (num(FLASH_MAX), num(HIT_FLASH), num(STROBE_FLASH)))], 0)},
                      inputs=[glow])


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


def build(m, live=LIVE_SERVER, osc_ip=OSC_IP, osc_port=OSC_PORT, seed=0, size=None, project_dir=None, audio_device=None, osc_in=OSC_IN_PORT, clock=None, matte_pass=False,
          effects=True, fx=None, **graph):
    """Builder (not yet built) of the Robot project for Manifest `m`. File params are relative to project_dir when given.
    `matte_pass`: the Matte is its own Pass ("matte" in each Clip's passes, grey) instead of the beauty's alpha (decode_cost.py measures both).
    `effects`: the MMV effect modules after the composite (effect_chain), switched by the Fx Globals (`fx` overrides their start values).
    `clock` replaces the audio clock Globals (name, value, source, mods), for a test that drives Beats, BeatFrac, Section and Bpm itself."""
    b = mp.Builder(syphon=OUTPUT_SERVER, size=tuple(size or m.size), fps=m.fps, audio_device=audio_device, osc_in=osc_in)
    for name, value, source, mods in (clock if clock is not None else clock_globals()) + graph_globals(m, seed=seed, **graph):
        b.glob(name, value, source, mods)
    for g in live_globals() + (effect_globals(m, clip_hits(m), fx) if effects else []):
        b.glob(*g)
    robot, osc = b.scene("Robot"), b.scene("OSC Out")

    def clip_files(kind):
        """Every Angle's InputSelector over the Moves, each drawn all the time (Transparency 0 on air, 1 off air), so the Angles advance in
        step and a cut lands on the same frame: a VideoFile that is not drawn does not advance (idle_check.py)."""
        layers = []
        for a, angle in enumerate(m.angle_ids):
            nodes = []
            duel = m.angle_duel(angle)
            for mv in local_moves(m, duel):
                path = m.path(m.clips[m.clip_index(mv.name, angle)]["passes"][kind])
                path = os.path.relpath(path, project_dir) if project_dir else os.path.abspath(path)
                nodes.append(robot.node("VideoFile", {"File": path, "Speed": ("global:SpeedRatio", [], 1), "Goto Start": ("global:StartPulse", [], 0),
                                                      "Looping": 1}))   # Looping 0 draws black after the last frame (restart_check.py); 1 replays instead
            moves = robot.node("InputSelector", {"Input #": ("global:%s" % move_input(m, duel), [], 0)}, inputs=nodes)
            layers.append(robot.node("Transparency", {"Amount": ("global:%s%d" % (HIDE_ANGLE, a), [], 1)}, inputs=[moves]))
        return robot.node("Null", inputs=layers)

    world = robot.node("SyphonClient", {"Server": live})
    shadow = clip_files("shadow")
    shaded = robot.node("Blend", {"Mode": BLEND_MULTIPLY}, inputs=[world, shadow])
    beauty = clip_files("beauty")
    matte = robot.node("Mask", {"Use Alpha": 0}, inputs=[beauty, clip_files("matte")]) if matte_pass else robot.node("Mask", {"Use Alpha": 1}, inputs=[beauty, beauty])
    comp = robot.node("Transparency", {"Amount": 0}, inputs=[matte, shaded])
    osc_mod = robot.scene_module(osc)
    # A module wired to a missing Syphon server draws black, bypassed or not; an InputSelector only evaluates the input it draws.
    gate = robot.node("InputSelector", {"Input #": ("global:%s" % LIVE_GATE, [], 0)}, inputs=[matte, comp])
    robot.output(effect_chain(robot, gate) if effects else gate, osc_mod)
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
