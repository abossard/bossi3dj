"""Grades one eval run: python3 grade.py <eval name> <run dir> -> <run dir>/grading.json

Checks outputs with Python's zlib/ElementTree directly; magicproj is only used
for check() and diff(), which are what "opens in Magic without broken links"
and "nothing else changed" mean here.
"""
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "../../../../magic"))
import magicproj as mp  # noqa: E402

FIXTURE = os.path.join(HERE, "files/synthwave_pyramids.magic")
FIXTURE_SHA = "c78a7d85033c2aacc8aac16deb9b0dbd8f991a19"
BANDS = ["Sub", "Low", "Mid", "HiMid", "Air"]
TIMED = ["Strobe", "HueBase", "HueDrift", "CamAuto", "CamSel", "Sun", "Moon", "Pyramids", "Grid", "Stars", "Water",
         "Night", "MoonPhase", "FxTrails", "FxBlur", "FxChroma", "FxShake", "FxKaleido", "Blackout", "Shock", "Meteor",
         "Flamingos", "Haze", "Fog", "FogHue", "FogGlow", "Monitor", "Readout"]


def load(path):
    try:
        return ET.fromstring(zlib.decompress(open(path, "rb").read()[3:]))
    except Exception:
        return None


def text(path):
    return open(path, encoding="utf-8").read() if os.path.exists(path) else ""


def inspect(out):
    t = text(os.path.join(out, "answer.md"))
    low = t.lower()
    return [
        ("answer.md names OutShock as the Global behind /vj/shock", "outshock" in low, t[:200]),
        ("answer.md lists both ShockT and ShockAmp as dependencies", "shockt" in low and "shockamp" in low, ""),
        ("answer.md mentions the Clock dependency", "clock" in low, ""),
        ("answer.md identifies the 20-80 Hz band", bool(re.search(r"20\s*[-–]\s*80", t)), ""),
        ("answer.md identifies the 80-320 Hz band at half weight",
         bool(re.search(r"80\s*[-–]\s*320", t)) and bool(re.search(r"0\.5|half", low)), ""),
    ]


def edit(out):
    path = os.path.join(out, "synthwave_lab.magic")
    root = load(path)
    orig = load(FIXTURE)
    res = [("synthwave_lab.magic exists and decodes", root is not None, path)]
    if root is None:
        return res + [("input file unchanged", hashlib.sha1(open(FIXTURE, "rb").read()).hexdigest() == FIXTURE_SHA, "")]
    senders = mp.osc_senders(root)
    ports = sorted({(s["ip"], s["port"]) for s in senders})
    res.append(("all 30 OSCSenders target 127.0.0.1:9200", len(senders) == 30 and ports == [("127.0.0.1", "9200")], str(ports)))
    p = root.attrib
    res.append(("Syphon on, named synthwave-out, 1920x1080",
                (p.get("videoSharing"), p.get("videoSharingName"), p.get("videoSharingWidth"), p.get("videoSharingHeight"))
                == ("1", "synthwave-out", "1920", "1080"), str({k: v for k, v in p.items() if k.startswith("video")})))
    gain = next((g for g in mp.global_table(root) if g["name"] == "Gain"), None)
    res.append(("Global Gain value is 0.7", gain is not None and abs(float(gain["value"]) - 0.7) < 1e-9, str(gain and gain["value"])))
    allowed = re.compile(r"^(project\.videoSharing(Name|Width|Height)?|RenderSettings\.(width|height)|global\[Gain\]\.value|"
                         r"scene\[OSC Out\]\.node\[OSCSender#\d+\]\.(Port|IP Addr\.))$")
    extra = [k for k, _, _ in mp.diff(orig, root) if not allowed.match(k)]
    res.append(("no other semantic change", not extra, str(extra[:5])))
    res.append(("no check() errors", not [m for l, m in mp.check(root, out) if l == "error"], ""))
    res.append(("input file unchanged", hashlib.sha1(open(FIXTURE, "rb").read()).hexdigest() == FIXTURE_SHA, ""))
    t = text(os.path.join(out, "changes.md"))
    res.append(("changes.md reports the port, Syphon and Gain changes", "9200" in t and "0.7" in t and "synthwave-out" in t, t[:200]))
    return res


def generate(out):
    path = os.path.join(out, "beat_square.magic")
    root = load(path)
    res = [("beat_square.magic exists and decodes", root is not None, path)]
    if root is None:
        return res
    errors = [m for l, m in mp.check(root, out) if l == "error"]
    res.append(("no check() errors (links, ids, expressions)", not errors, str(errors[:3])))
    warns = [m for l, m in mp.check(root, out) if l == "warn" and "editor position" in m or "no Tab entry" in m]
    res.append(("every node has an editor position", not warns, str(warns[:2])))
    gl = {g["name"]: g for g in mp.global_table(root)}
    res.append(("Global Hue defaults to 0.6", "Hue" in gl and abs(float(gl["Hue"]["value"]) - 0.6) < 1e-9, str(gl.get("Hue"))))
    ivs = list(root.iter("InputValue"))
    bass = [iv for iv in ivs if iv.get("linked") == "1" and iv.get("feature") == "1" and iv.get("subFeature") == "0"
            and iv.get("layerID") not in ("-1", str(mp.GLOBAL_LAYER), str(mp.INTERNAL_LAYER))]
    res.append(("something reads audio Freq. Range 20-80 Hz", bool(bass), str(len(bass))))
    smooth = any(op.get("type") in ("4", "11", "12") or (op.get("type") == "21" and re.search(r"\by\b", op.get("paramString", "")))
                 for iv in bass for op in iv.iter("ValueOperator"))
    res.append(("the bass input is smoothed (Smooth/Average/Peak or a y-feedback expression)", smooth, ""))
    hue_linked = any(iv.get("name") == "Hue" and iv.get("layerID") == str(mp.GLOBAL_LAYER) for iv in ivs)
    res.append(("a colour Hue param is linked to the Hue Global", hue_linked, ""))
    nodes = mp.node_table(root)
    res.append(("has a Polygon module", any(n["plugin"] == "Polygon" for n in nodes), ""))
    scaled = any(n["plugin"] in ("Scale", "Polygon") and any(p["source"] != "manual" and p["name"] != "Power" and p["name"] != "Bypass"
                                                           for p in n["params"]) for n in nodes)
    res.append(("square size is linked to a source", scaled, ""))
    osc = mp.osc_senders(root)
    ok = any(o["message"] == "/test/bass" and o["ip"] == "127.0.0.1" and o["port"] == "9300" and o["value_source"] != "manual" for o in osc)
    res.append(("OSCSender /test/bass -> 127.0.0.1:9300 with a linked value", ok, str(osc)))
    res.append(("Syphon output on", root.get("videoSharing") == "1", ""))
    return res


def diffsum(out):
    t = text(os.path.join(out, "diff_summary.md"))
    low = t.lower()
    named = [g for g in TIMED if re.search(r"\b%s\b" % g, t)]
    return [
        ("names all five band Globals", all(re.search(r"\b%s\b" % b, t) for b in BANDS), ""),
        ("says the bands become synthetic/calculated", bool(re.search(r"synthetic|calc|scripted|generated", low)), ""),
        ("mentions the Random noise modifier", "random" in low, ""),
        ("names at least 10 controls that become timers", len(named) >= 10, "%d named" % len(named)),
        ("says OSC targets/scenes/modules are unchanged", bool(re.search(r"(unchanged|identical|same|no change|not change|untouched)", low))
         and bool(re.search(r"osc|scene|module|node", low)), ""),
    ]


def plan(out):
    t = text(os.path.join(out, "plan.md"))
    low = t.lower()
    code = "\n".join(re.findall(r"```[^\n]*\n(.*?)```", t, re.S)).lower()
    binds = re.search(r"(listen\s+9201|nc\s+[^\n]*-l[^\n]*9201|bind\([^\n]*9201|sendto\([^\n]*9201|oscsend[^\n]*9201)", code)
    loads = re.search(r"magicproj\.py\s+load|open\s+-a[^\n]*magic", code)
    uses_9200 = "9200" in code
    return [
        ("no command binds or sends on port 9201", bool(t) and not binds, binds.group(0) if binds else ""),
        ("observes the OSC without taking Blender's port (retargeted copy, lab relay or passive capture)",
         bool(re.search(r"osc-target|retarget|lab\.py|make lab|tcpdump|pcap", low)), ""),
        ("leaves Magic's project as it was: loads nothing, or reloads the original afterwards",
         not loads or bool(re.search(r"reload|restore|load (it|the original|synthwave)[^\n]*back", low)), loads.group(0) if loads else "no load"),
        ("checks that port 9200 is free before using it (or does not use it)",
         not uses_9200 or bool(re.search(r"lsof|in use|already (running|bound)", low)), ""),
        ("states the expected /vj/beat range (0..1, pulses on beats)",
         bool(re.search(r"0\s*(\.\.|to|-|–|and)\s*1|<=\s*1(\.0)?\b|\[0,\s*1\]", low)) and "beat" in low, ""),
        ("says OSCSender sends /vj/beat only when its value changes",
         bool(re.search(r"(only|just) (send|sent|sends)[^\n]*chang|on change|when (its|the) value changes", low)), ""),
    ]


GRADERS = {"plan-live-osc-check": plan, "inspect-shock-and-kick": inspect, "edit-osc-syphon-gain": edit, "generate-beat-square": generate,
           "diff-synthetic-build": diffsum}


# --- General Magic evals (evals.json) ---------------------------------------

def _check_errors(root, base):
    return [m for l, m in mp.check(root, base) if l == "error"]


def midi_piano(out):
    t = text(os.path.join(out, "answer.md"))
    low = t.lower()
    return [
        ("names the Iterator Notes MIDI feature", "iterator notes" in low, ""),
        ("explains the 88-key Iterator starting at note 21", "88" in t and bool(re.search(r"\b21\b|a0", low)), ""),
        ("says the MIDI source must be assigned to a device/channel in Input Sources",
         bool(re.search(r"unassigned|no device|not assigned|input sources|trackid=\"?-1", low)), ""),
        ("explains key lighting via Threshold-gated Power/Bypass/Saturation", "threshold" in low and bool(re.search(r"power|bypass|saturation", low)), ""),
        ("explains InputSelector picks the Left/Right/Middle/Black key shape by note within the octave",
         "inputselector" in low.replace(" ", "") and bool(re.search(r"%\s*12|mod(ulo)? 12|within the octave|octave", low)), ""),
        ("says Left Key / Right Key are key-shape scenes used as scene modules",
         bool(re.search(r"scene module|key shape|shape", low)) and "left key" in low, ""),
    ]


def playlist_show(out):
    path = os.path.join(out, "show.magic")
    root = load(path)
    res = [("show.magic exists and decodes", root is not None, path)]
    if root is None:
        return res
    orig = load(os.path.join(HERE, "files/ManyScenes.magic"))
    entries = list(root.iterfind("Playlists/Playlist/Scene"))
    ids = [s.get("id") for s in mp.scenes(orig)]
    res.append(("every scene is in the playlist once, in order", [e.get("id") for e in entries] == ids, str([e.get("id") for e in entries])))
    res.append(("every entry auto-advances after 16 s", all(float(e.get("sceneDuration", 0)) == 16 for e in entries), ""))
    res.append(("every entry uses the crossfade style (1)", all(e.get("style") == "1" for e in entries), str({e.get("style") for e in entries})))
    p = root.attrib
    res.append(("Syphon on as magic-show at 1280x720", (p.get("videoSharing"), p.get("videoSharingName"), p.get("videoSharingWidth"),
                                                     p.get("videoSharingHeight")) == ("1", "magic-show", "1280", "720"), ""))
    res.append(("looping on", p.get("looping") == "1", ""))
    allowed = re.compile(r"^(project\.\w+|RenderSettings\.\w+|playlist\[\d+\])$")
    extra = [k for k, _, _ in mp.diff(orig, root) if not allowed.match(k)]
    res.append(("scenes and modules unchanged", not extra, str(extra[:4])))
    t = text(os.path.join(out, "changes.md")).lower()
    res.append(("changes.md notes the project has no audio files", bool(re.search(r"no audio file|has no (audio )?files|without audio file|no files", t)), ""))
    res.append(("changes.md says auto-advance is switched on in Magic (not stored in the project)",
                bool(re.search(r"shift\s*\+\s*space|auto-advance (button|toggle|checkbox)|start auto-advance|not (stored|saved) in the (project|file)", t)), ""))
    return res


def iterator_midi_osc(out):
    path = os.path.join(out, "spectrum_bars.magic")
    root = load(path)
    res = [("spectrum_bars.magic exists and decodes", root is not None, path)]
    if root is None:
        return res
    res.append(("no check() errors", not _check_errors(root, out), str(_check_errors(root, out)[:3])))
    nodes = mp.node_table(root)
    it = [n for n in nodes if n["plugin"] == "Iterator"]
    res.append(("an Iterator with 16 iterations", any(any(p["name"] == "Iterations" and float(p["value"] or 0) == 16 for p in n["params"]) for n in it), ""))
    ivs = list(root.iter("InputValue"))
    res.append(("a bar height reads Freq. Range Iterator Freqs. (feature 1, sub 6)",
                any(iv.get("feature") == "1" and iv.get("subFeature") == "6" and iv.get("linked") == "1" for iv in ivs), ""))
    midi_layers = {l.get("id") for l in root.iter("Layer") for t in root.iter("Track")
                   if t.get("id") == l.get("trackID") and t.get("isMidi") == "1" and t.get("channel") == "1"}
    res.append(("a MIDI source on channel 1", bool(midi_layers), ""))
    res.append(("something reads MIDI CC 1 (feature 3, sub 1)",
                any(iv.get("layerID") in midi_layers and iv.get("feature") == "3" and iv.get("subFeature") == "1" for iv in ivs), ""))
    osc_tracks = [t for t in root.iter("Track") if t.get("isOSC") == "1" and t.get("channel") == "8000"]
    gl = {g["name"]: g for g in mp.global_table(root)}
    res.append(("OSC input on port 8000", bool(osc_tracks), ""))
    res.append(("Global Speed reads osc:/speed", gl.get("Speed", {}).get("source") == "osc:/speed", str(gl.get("Speed", {}).get("source"))))
    # Speed directly, or a Global computed from Speed (one hop).
    via = {"Speed"} | {g["name"] for g in gl.values() if any("Speed" in (m[2] or "") for m in g["modifiers"]) or g["source"] == "global:Speed"}
    res.append(("a rotation is linked to Speed", any(n["plugin"].startswith("Rotate") and any(
        any(p["source"] == "global:" + v or any(re.search(r"\\b%s\\b" % v, m[2] or "") for m in p["modifiers"]) for v in via)
        for p in n["params"]) for n in nodes), str(sorted(via))))
    return res


def repair(out):
    path = os.path.join(out, "fixed.magic")
    root = load(path)
    res = [("fixed.magic exists and decodes", root is not None, path)]
    if root is None:
        return res
    res.append(("no check() errors", not _check_errors(root, out), str(_check_errors(root, out)[:3])))
    gl = {g["name"] for g in mp.global_table(root)}
    res.append(("Globals are still Spin and Pulse", gl == {"Spin", "Pulse"}, str(gl)))
    srcs = [p["source"] for n in mp.node_table(root) for p in n["params"]]
    res.append(("all five bar Scales link to Pulse again", srcs.count("global:Pulse") == 5, str(srcs.count("global:Pulse"))))
    trails = [n for n in mp.node_table(root) if n["scene"] == "Scene 1" and n["plugin"] == "Trails"]
    res.append(("the Scene 1 Trails has its five inputs back", bool(trails) and len(trails[0]["inputs"]) == 5, ""))
    exprs = [m[2] for n in mp.node_table(root) for p in n["params"] for m in p["modifiers"] if m[2]]
    res.append(("the typo Spinn is gone", not any("Spinn" in e for e in exprs), str(exprs)))
    t = text(os.path.join(out, "fixes.md")).lower()
    res.append(("fixes.md names all three problems", "spinn" in t and bool(re.search(r"9999|missing global|dangling|broken link", t))
                and bool(re.search(r"4242|missing input|trail", t)), ""))
    return res


def advice(out):
    t = text(os.path.join(out, "advice.md"))
    low = t.lower()
    return [
        ("lower or fix the graphics resolution instead of rendering at 4K", bool(re.search(r"graphics resolution", low)), ""),
        ("watch FPS in the status information / aim for 60", bool(re.search(r"status info|cmd\+i|fps", low)), ""),
        ("mentions frame-rate throttling or vsync", bool(re.search(r"throttl|vsync|vertical sync", low)), ""),
        ("mentions graphics memory / Load All Scenes Into Graphics Memory", bool(re.search(r"graphics memory|keepingfxmem", low)), ""),
        ("mentions Module Text Update Speed or closing the editor", bool(re.search(r"module text update|update speed|blank tab", low)), ""),
        ("export via File > Export Movie", "export movie" in low, ""),
        ("export follows audio files only; live inputs are ignored", bool(re.search(r"live (input|audio|midi|osc)[^\n]*(ignor|not)|ignor[^\n]*live", low)), ""),
        ("H.264 settings: quality (CRF) and width/height multiple of 4 or 1920x1080 at 60",
         bool(re.search(r"h\.?264|mp4", low)) and bool(re.search(r"quality|crf", low)), ""),
    ]


def isf_module(out):
    import glob
    fs = [f for f in glob.glob(os.path.join(out, "*.fs"))]
    res = [("a .fs file was written", bool(fs), str(fs))]
    params = {}
    if fs:
        try:
            params = mp.isf_params(open(fs[0]).read())
        except ValueError:
            params = None
    res.append(("the .fs header parses and has an amount input", bool(params) and any(k.lower() == "amount" for k in params), str(params)))
    root = load(os.path.join(out, "demo_mirror.magic"))
    res.append(("demo_mirror.magic decodes", root is not None, ""))
    if root is None:
        return res
    nodes = mp.node_table(root)
    mod = [n for n in nodes if n["plugin"] == "Mirror Pulse"]
    res.append(("a Mirror Pulse node (pluginName = file stem)", bool(mod) and fs and os.path.basename(fs[0]) == "Mirror Pulse.fs", ""))
    polys = {n["id"] for n in nodes if n["plugin"] == "Polygon"}
    res.append(("Mirror Pulse takes the Polygon as input", bool(mod) and bool(set(mod[0]["inputs"]) & polys), ""))
    res.append(("its Amount param reads Source 0 volume", bool(mod) and any(p["name"] == "Amount" and p["source"] == "audio:Source 0:Volume"
                                                                   for p in mod[0]["params"]), ""))
    res.append(("no check() errors", not _check_errors(root, out), ""))
    t = text(os.path.join(out, "notes.md")).lower()
    res.append(("notes.md explains Additional Module Folders", "additional module folder" in t, ""))
    return res


GRADERS.update({"inspect-midi-piano": midi_piano, "edit-playlist-show": playlist_show, "generate-iterator-midi-osc": iterator_midi_osc,
                "repair-hand-edit": repair, "advise-performance-export": advice, "custom-isf-module": isf_module})


def main():
    name, run = sys.argv[1], sys.argv[2]
    results = GRADERS[name](os.path.join(run, "outputs"))
    exp = [{"text": t, "passed": bool(p), "evidence": e} for t, p, e in results]
    passed = sum(e["passed"] for e in exp)
    json.dump({"expectations": exp, "summary": {"passed": passed, "failed": len(exp) - passed, "total": len(exp),
                                                 "pass_rate": round(passed / len(exp), 2)}},
              open(os.path.join(run, "grading.json"), "w"), indent=2)
    print("%s %s: %d/%d" % (name, os.path.basename(run), passed, len(exp)))


if __name__ == "__main__":
    main()
