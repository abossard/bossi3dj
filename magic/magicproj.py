#!/usr/bin/env python3
"""Read, inspect, diff, edit, generate and live-check Magic Music Visuals
(.magic) projects.

    python3 magicproj.py info FILE          # scenes, globals, OSC, audio, Syphon
    python3 magicproj.py globals FILE       # every Global: source, value, modifiers
    python3 magicproj.py check FILE         # dangling links, bad names, missing files
    python3 magicproj.py diff A B           # semantic diff
    python3 magicproj.py set FILE -o OUT --value Gain=0.7 --syphon on
    python3 magicproj.py load FILE          # open in Magic, wait for the editor
    python3 magicproj.py grab --out f.png   # Magic's Syphon frame + pixel stats

A .magic file is 3 header bytes (not checked by Magic) + zlib-compressed XML.
Format notes come from Magic 3.0b6 saves and its bundled sample projects; see
docs/magic-tooling-report.md. Standard library only, except `grab`, which needs
syphon-python (it re-runs itself under SYPHON_PYTHON when the import fails).
"""
import argparse
import functools
import json
import os
import re
import socket
import struct
import subprocess
import sys
import time
import wave
import xml.etree.ElementTree as ET
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
MAGIC_APP = os.environ.get("MAGIC_APP") or next(
    (a for a in ("/Applications/MagicBeta.app", "/Applications/Magic.app") if os.path.isdir(a)), "/Applications/Magic.app")
MAGIC_PREFS = os.path.expanduser("~/Library/Application Support/MAGIC/MAGIC_1_0.xml")
SAMPLES = os.path.join(MAGIC_APP, "Contents/MacOS/SampleProjects")
SYPHON_PYTHON = os.environ.get("SYPHON_PYTHON", "python3.13")
SYPHON_PATH = os.environ.get("SYPHON_PYTHONPATH", os.path.expanduser("~/.local/lib/python3.13/site-packages"))
# Ports `listen` refuses because another process owns them. 9201 is this
# repo's Blender bridge; add more with MAGICPROJ_RESERVED_PORTS=9201,8000.
RESERVED_PORTS = {int(p) for p in os.environ.get("MAGICPROJ_RESERVED_PORTS", "9201").split(",") if p.strip()}

HEADER = b"L*h"                  # any 3 bytes; Magic's own saves vary
XML_DECL = b'<?xml version="1.0" encoding="UTF-8"?>\n\n'
GLOBAL_LAYER = 2147483646        # source "Globals": feature = Global's InputValue id
INTERNAL_LAYER = 2147483645      # source "Internals"
NO_LAYER = -1

# Modifier type = index in this list (Magic's menu order, Power at 3).
MODIFIERS = ["Gate", "Scale", "Offset", "Power", "Smooth", "Wrap", "Random", "Ramp",
             "Sine", "Triangle", "Threshold", "Average", "Peak", "Exponent", "Clamp",
             "Step", "Increase", "Trigger", "Invert", "Hold", "Delay", "Expression",
             "RandomTrigger"]
EXPRESSION = MODIFIERS.index("Expression")
AUDIO_FEATURES = ["Volume", "Freq. Range", "Best Pitch", "Tone"]
FREQ_RANGES = ["20-80 Hz", "80-320 Hz", "320-1.2k Hz", "1.2k-5k Hz", "5k-20k Hz", "Custom Freq.", "Iterator Freqs."]
# Internals feature index: read back from Magic 3.0b6 frames, plus the
# binary's label table for 4 and 11. 2/3 repeat width/height; 9 reads 0.
INTERNALS = {0: "Graphics Width", 1: "Graphics Height", 2: "Graphics Width 2", 3: "Graphics Height 2",
             4: "Playlist Entry #", 5: "Playback Time", 6: "Graphics FPS", 7: "Iteration #", 8: "Total Iterations",
             10: "Audio/MIDI Playing", 11: "Playback Seeked"}
# MIDI feature index (binary label table; 0, 2, 3, 6, 7, 10 seen in saves).
# subFeature: note number for 4 and 7, CC number for 3, 0..4 = beat, /2, /3, /4, BPM for 8.
MIDI_FEATURES = ["Velocity", "Pitch Bend", "Note Number", "Control Change", "Aftertouch", "Channel Pressure",
                 "Program Change", "Note Velocity", "Beat Clock", "Control Change Number", "Iterator Notes"]
BEAT_CLOCK = ["Beat", "/2", "/3", "/4", "Clock BPM"]
# Every bundled module with the params Magic 3.0b6 itself saves (see the JSON's _about).
MODULES_V3 = os.path.join(HERE, "magic_modules_v3.json")
# Names older saves use for modules that Magic 3 saves under a new name.
RENAMED_V3 = {"Image": "ImageFile"}
REMOVED_V3 = {"AudioToImage": "removed in 3.0; ISF modules read audio inputs directly"}


@functools.lru_cache(maxsize=None)
def modules_v3():
    with open(MODULES_V3, encoding="utf-8") as f:
        return json.load(f)["modules"]


def has_bypass(plugin):
    m = modules_v3().get(plugin)
    return "Bypass" in m["params"] if m else plugin not in ("SyphonClient", "OSCSender", "Polygon", "Text")

EXPRTK_WORDS = set("""abs acos acosh asin asinh atan atan2 atanh avg ceil clamp cos cosh cot csc
deg2grad deg2rad equal erf erfc exp expm1 floor frac grad2deg hypot iclamp inrange log log10
log1p log2 logn max min mul ncdf nequal not_equal pow rad2deg root round roundn sec sgn sin
sinc sinh sqrt sum swap tan tanh trunc if else and or not xor nand nor xnor mand mor true
false pi epsilon inf while for repeat until switch case default var return break continue
x y in like ilike shl shr""".split())


# --- File codec (calculations) -----------------------------------------------

def decode(data):
    """.magic bytes -> XML bytes."""
    return zlib.decompress(data[3:])


def encode(xml):
    """XML bytes -> .magic bytes."""
    return HEADER + zlib.compress(xml, 9)


def parse(data):
    return ET.fromstring(decode(data))


def serialize(root):
    root = _copy(root)
    ET.indent(root, "  ")
    return XML_DECL + ET.tostring(root, encoding="utf-8") + b"\n"


def _copy(e):
    return ET.fromstring(ET.tostring(e))


def canonical(root):
    """Order-preserving tuple tree without whitespace, for equality checks."""
    return (root.tag, tuple(sorted(root.attrib.items())), tuple(canonical(c) for c in root))


# --- Queries (calculations) --------------------------------------------------

def globals_el(root):
    g = root.find("Globals")
    if g is None:
        g = ET.SubElement(root, "Globals")
    return g


def global_ivs(root):
    return list(globals_el(root))


def global_names(root):
    """InputValue id -> Global name."""
    return {iv.get("id"): iv.get("name") for iv in global_ivs(root)}


def find_global(root, name):
    for iv in global_ivs(root):
        if iv.get("name") == name:
            return iv
    raise KeyError("no Global named %r" % name)


def scenes(root):
    s = root.find("Scenes")
    return list(s) if s is not None else []


def scene_nodes(scene):
    """Root Magic node first, then the scene's modules."""
    return [n for tag in ("Root", "Nodes") if scene.find(tag) is not None for n in scene.find(tag)]


def find_scene(root, name):
    for s in scenes(root):
        if s.get("name") == name or s.get("id") == str(name):
            return s
    raise KeyError("no scene %r (have %s)" % (name, ", ".join(s.get("name") for s in scenes(root))))


def params(node):
    ivs = node.find("InputValues")
    return list(ivs) if ivs is not None else []


def param(node, name):
    for iv in params(node):
        if iv.get("name") == name:
            return iv
    return None


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def _sources(root):
    """layer id -> (layer name, track element or None)."""
    tracks = {t.get("id"): t for t in root.iter("Track")}
    return {l.get("id"): (l.get("name"), tracks.get(l.get("trackID"))) for l in root.iter("Layer")}


def describe_source(iv, root, _cache=None):
    """Human-readable source of a parameter or Global."""
    names, layers = _cache or (global_names(root), _sources(root))
    if iv.get("linked") != "1":
        return "manual"
    layer = int(iv.get("layerID", NO_LAYER))
    feature = iv.get("feature", "0")
    if layer == NO_LAYER:
        return "calc"
    if layer == GLOBAL_LAYER:
        if iv.get("globalsUseID", "1") != "1":
            ivs = global_ivs(root)
            i = int(feature)
            return "global:%s" % (ivs[i].get("name") if 0 <= i < len(ivs) else "?index %d" % i)
        return "global:%s" % names.get(feature, "?id %s" % feature)
    if layer == INTERNAL_LAYER:
        i = int(feature)
        return "internal:%s" % INTERNALS.get(i, i)
    lname, track = layers.get(str(layer), ("?layer %d" % layer, None))
    if track is not None and track.get("isOSC") == "1":
        return "osc:%s" % iv.get("featureString", "")
    # An unassigned source (trackID -1, device absent) has no track to say what
    # it is; features above Tone only exist for MIDI.
    midi = track.get("isMidi") == "1" if track is not None else (int(feature) > 3 or "midi" in lname.lower())
    if midi:
        f, sub = int(feature), int(iv.get("subFeature", "0"))
        lname += "" if track is not None else " (unassigned)"
        name = MIDI_FEATURES[f] if 0 <= f < len(MIDI_FEATURES) else "?%d" % f
        if f in (3, 4, 7):
            return "midi:%s:%s:%d" % (lname, name, sub)
        if f == 8:
            return "midi:%s:%s:%s" % (lname, name, BEAT_CLOCK[sub] if 0 <= sub < len(BEAT_CLOCK) else sub)
        return "midi:%s:%s" % (lname, name)
    if track is None:
        lname += " (unassigned)"
    f = int(feature)
    out = "audio:%s:%s" % (lname, AUDIO_FEATURES[f] if 0 <= f < len(AUDIO_FEATURES) else "?%d" % f)
    if f == 1:
        s = int(iv.get("subFeature", "0"))
        out += ":" + (FREQ_RANGES[s] if 0 <= s < len(FREQ_RANGES) else "?%d" % s)
    return out


def modifiers(iv):
    """[(name, param, expression or None, bypassed)]"""
    out = []
    for op in iv.iter("ValueOperator"):
        t = int(op.get("type"))
        name = MODIFIERS[t] if 0 <= t < len(MODIFIERS) else "?%d" % t
        out.append((name, _num(op.get("param")), op.get("paramString") if t == EXPRESSION else None,
                    op.get("bypassed") == "1"))
    return out


def format_mods(mods):
    parts = []
    for name, p, expr, bypassed in mods:
        s = "%s(%s)" % (name, expr) if expr is not None else "%s %s" % (name, _fmt(p))
        parts.append(("[bypassed] " if bypassed else "") + s)
    return " -> ".join(parts)


def _fmt(v):
    if isinstance(v, float):
        return ("%.6g" % v)
    return str(v)


def global_table(root):
    cache = (global_names(root), _sources(root))
    return [{"id": iv.get("id"), "name": iv.get("name"), "value": _num(iv.get("value")),
             "source": describe_source(iv, root, cache), "modifiers": modifiers(iv)} for iv in global_ivs(root)]


def node_table(root, scene=None):
    cache = (global_names(root), _sources(root))
    snames = {s.get("id"): s.get("name") for s in scenes(root)}
    out = []
    for s in scenes(root) if scene is None else [find_scene(root, scene)]:
        for n in scene_nodes(s):
            ps = []
            for iv in params(n):
                src = describe_source(iv, root, cache)
                ps.append({"name": iv.get("name"), "value": iv.get("value"), "source": src, "modifiers": modifiers(iv)})
            sid = n.get("sceneID")
            out.append({"scene": s.get("name"), "id": n.get("id"), "plugin": n.get("pluginName"),
                        "scene_module": snames.get(sid, "?id %s" % sid) if sid is not None else None,
                        "isf": n.get("isfFilename"), "inputs": [c.get("id") for c in n.iter("Child")],
                        "bypassed": n.get("bypassed") == "1", "disabled": n.get("disabled") == "1", "params": ps})
    return out


def osc_senders(root):
    out = []
    for n in node_table(root):
        if n["plugin"] != "OSCSender":
            continue
        p = {x["name"]: x for x in n["params"]}
        val = p.get("Value", {})
        out.append({"scene": n["scene"], "id": n["id"], "ip": p.get("IP Addr.", {}).get("value"),
                    "port": p.get("Port", {}).get("value"), "message": p.get("Message", {}).get("value"),
                    "value_source": val.get("source"), "modifiers": val.get("modifiers", [])})
    return out


def audio_files(root):
    return [f.get("filename") for f in root.iter("AudioFile")]


def summary(root):
    p = root.attrib
    rs = root.find("RenderSettings")
    osc_in = [t.get("channel") for t in root.iter("Track") if t.get("isOSC") == "1"]
    inputs = sorted({t.get("deviceName") or t.get("name") for t in root.iter("Track")
                     if t.get("isInput") == "1" and t.get("isMidi") != "1" and t.get("isOSC") != "1"})
    return {
        "version": p.get("version"), "actualVersion": p.get("actualVersion"),
        "render": "%sx%s@%s" % (rs.get("width"), rs.get("height"), rs.get("fps")) if rs is not None else None,
        "syphon": {"on": p.get("videoSharing") == "1", "name": p.get("videoSharingName", "Main Server"),
                   "size": "%sx%s" % (p.get("videoSharingWidth"), p.get("videoSharingHeight")) if p.get("videoSharingWidth") else "-"},
        "looping": p.get("looping") == "1",
        "scenes": [{"id": s.get("id"), "name": s.get("name"), "modules": len(scene_nodes(s)) - 1} for s in scenes(root)],
        "playlist": [dict(e.attrib) for e in root.iterfind("Playlists/Playlist/Scene")],
        "globals": len(global_ivs(root)),
        "osc_senders": len(osc_senders(root)),
        "osc_in_ports": osc_in,
        "audio_inputs": inputs,
        "audio_files": audio_files(root),
        "sources": [{"id": l.get("id"), "name": l.get("name"), "track": l.get("trackID")} for l in root.iter("Layer")],
    }


# --- Diff (calculations) -----------------------------------------------------

def flatten(root):
    """Stable key -> value map: Globals by name, nodes by scene and id."""
    out = {}
    for k, v in root.attrib.items():
        out["project.%s" % k] = v
    for tag in ("RenderSettings",):
        e = root.find(tag)
        for k, v in (e.attrib.items() if e is not None else ()):
            out["%s.%s" % (tag, k)] = v
    for i, f in enumerate(audio_files(root)):
        out["audio[%d]" % i] = f
    tracks = {t.get("id"): "%s ch %s" % (t.get("name"), t.get("channel")) for t in root.iter("Track")}
    for t in root.iter("Track"):
        out["track[%s]" % tracks[t.get("id")]] = " ".join("%s=%s" % kv for kv in sorted(t.attrib.items())
                                                       if kv[0] not in ("id", "name", "channel"))
    for l in root.iter("Layer"):
        out["source[%s]" % l.get("name")] = tracks.get(l.get("trackID"), "unassigned")
    snames = {sc.get("id"): sc.get("name") for sc in scenes(root)}
    for i, e in enumerate(root.iterfind("Playlists/Playlist/Scene")):
        out["playlist[%d]" % i] = "%s: %ss, transition %ss style %s%s" % (
            snames.get(e.get("id"), "?id " + str(e.get("id"))), e.get("sceneDuration"), e.get("duration"), e.get("style"),
            "" if e.get("enabled", "1") == "1" else ", disabled")
    for g in global_table(root):
        key = "global[%s]" % g["name"]
        out[key + ".value"] = _fmt(g["value"])
        out[key + ".source"] = g["source"]
        out[key + ".modifiers"] = format_mods(g["modifiers"])
    # Magic renumbers every id when it saves, so nodes are keyed by module name
    # and position among same-named modules in their scene, not by id.
    rows = node_table(root)
    label, count = {}, {}
    for n in rows:
        k = (n["scene"], n["plugin"])
        count[k] = count.get(k, 0) + 1
        label[(n["scene"], n["id"])] = n["plugin"] if n["plugin"] == "Magic" else "%s#%d" % (n["plugin"], count[k])
    for n in rows:
        key = "scene[%s].node[%s]" % (n["scene"], label[(n["scene"], n["id"])])
        out[key + ".inputs"] = ",".join(label.get((n["scene"], i), "?" + i) for i in n["inputs"])
        for flag in ("bypassed", "disabled"):
            if n[flag]:
                out[key + "." + flag] = "1"
        seen = {}
        for p in n["params"]:
            k = p["name"] if p["name"] not in seen else "%s#%d" % (p["name"], seen[p["name"]])
            seen[p["name"]] = seen.get(p["name"], 0) + 1
            out["%s.%s" % (key, k)] = p["value"] if p["source"] == "manual" else \
                "%s <- %s %s" % (p["value"], p["source"], format_mods(p["modifiers"]))
    return out


def diff(a, b):
    """[(key, old or None, new or None)] for keys whose value differs."""
    fa, fb = flatten(a), flatten(b)
    return [(k, fa.get(k), fb.get(k)) for k in sorted(set(fa) | set(fb)) if fa.get(k) != fb.get(k)]


# --- Check (calculations) ----------------------------------------------------

def expression_identifiers(expr):
    expr = re.sub(r"'[^']*'", " ", expr)
    expr = re.sub(r"(?<![A-Za-z_])\d+\.?\d*(e[+-]?\d+)?|\.\d+(e[+-]?\d+)?", " ", expr, flags=re.I)
    locals_ = set(re.findall(r"\bvar\s+([A-Za-z_]\w*)", expr))
    return {w for w in re.findall(r"[A-Za-z_]\w*", expr)} - locals_


def check(root, base_dir="."):
    """[(level, message)]: level is 'error' (Magic will mislink or drop it) or 'warn'."""
    out = []
    err = lambda m: out.append(("error", m))
    warn = lambda m: out.append(("warn", m))
    ivs = list(root.iter("InputValue"))
    ids = {}
    for iv in ivs:
        ids.setdefault(iv.get("id"), []).append(iv.get("name"))
    for i, names in ids.items():
        if len(names) > 1:
            err("InputValue id %s used %d times (%s)" % (i, len(names), ", ".join(names[:4])))
    gids = global_names(root)
    gnames = list(gids.values())
    for name in sorted({n for n in gnames if gnames.count(n) > 1}):
        err("Global name %r is used twice; links and expressions become ambiguous" % name)
    for name in gnames:
        if name in ("x", "y"):
            err("Global %r: x and y are reserved" % name)
        elif not re.fullmatch(r"[A-Za-z_]\w*", name or ""):
            warn("Global %r cannot be used in expressions (spaces or symbols)" % name)
        elif name in EXPRTK_WORDS:
            warn("Global %r shadows an ExprTk function or keyword" % name)
    for iv in ivs:
        if iv.get("linked") == "1" and iv.get("layerID") == str(GLOBAL_LAYER) and iv.get("globalsUseID", "1") == "1" \
                and iv.get("feature") not in gids:
            err("%s links to missing Global id %s" % (_where(root, iv), iv.get("feature")))
        for op in iv.iter("ValueOperator"):
            t = int(op.get("type", -1))
            if not 0 <= t < len(MODIFIERS):
                err("%s has unknown modifier type %s" % (_where(root, iv), t))
            elif t == EXPRESSION:
                # ExprTk names are case-insensitive.
                known = EXPRTK_WORDS | {n.lower() for n in gnames}
                unknown = {w for w in expression_identifiers(op.get("paramString") or "") if w.lower() not in known}
                if unknown:
                    err("%s expression uses unknown names %s: %r" % (_where(root, iv), sorted(unknown), op.get("paramString")))
    layer_ids = {l.get("id") for l in root.iter("Layer")}
    for iv in ivs:
        lid = iv.get("layerID")
        if iv.get("linked") == "1" and lid not in layer_ids and int(lid or NO_LAYER) not in (NO_LAYER, GLOBAL_LAYER, INTERNAL_LAYER):
            warn("%s links to missing source %s; Magic treats it as no source" % (_where(root, iv), lid))
    track_ids = {t.get("id") for t in root.iter("Track")}
    for l in root.iter("Layer"):
        if l.get("trackID") not in track_ids:
            warn("source %r is unassigned (track %s)" % (l.get("name"), l.get("trackID")))
    nfiles = len(audio_files(root))
    for t in root.iter("Track"):
        if t.get("audioFileIndex") is not None and int(t.get("audioFileIndex")) >= nfiles:
            err("file track %s points at audio file %s of %d" % (t.get("id"), t.get("audioFileIndex"), nfiles))
    for f in audio_files(root):
        if not os.path.exists(os.path.join(base_dir, f)):
            warn("audio file not found: %s" % f)
    # Magic 3 saves a path relative to the project in `value` and the absolute
    # one in `absoluteFilename`, and tries both.
    for iv in ivs:
        if iv.get("name") in ("File", "Folder") and iv.get("value"):
            rel = iv.get("value").replace("\\", "/")
            if not (os.path.exists(os.path.join(base_dir, rel)) or os.path.exists(iv.get("absoluteFilename") or "")):
                warn("%s: file not found: %s" % (_where(root, iv), iv.get("value")))
    scene_ids = {s.get("id") for s in scenes(root)}
    tabs = root.find("Tabs")
    tab_list = list(tabs) if tabs is not None else []
    placed_all = {t.get("id") for tab in tab_list for t in tab}
    node_ids = {}
    for si, s in enumerate(scenes(root)):
        nodes = scene_nodes(s)
        here = {n.get("id") for n in nodes}
        for n in nodes:
            node_ids.setdefault(n.get("id"), []).append(s.get("name"))
            for c in n.iter("Child"):
                if c.get("id") not in here:
                    err("scene %r node %s %s: input %s is not in the scene" % (s.get("name"), n.get("id"), n.get("pluginName"), c.get("id")))
            sid = n.get("sceneID")
            if sid is not None and sid not in scene_ids:
                err("scene %r node %s: scene module points at missing scene id %s" % (s.get("name"), n.get("id"), sid))
        # Tabs are not stored in scene order (MIDIPiano), so look in all of them.
        missing = here - placed_all
        if missing:
            warn("scene %r: nodes %s have no editor position (Tab entry)" % (s.get("name"), sorted(missing, key=int)))
    for i, where in node_ids.items():
        if len(where) > 1:
            err("node id %s used %d times (%s)" % (i, len(where), ", ".join(where)))
    known = modules_v3()
    custom = set(isf_catalog(module_dirs()[2:]))
    snames = {s.get("name") for s in scenes(root)}
    for s in scenes(root):
        for n in scene_nodes(s)[1:]:
            plugin = n.get("pluginName")
            if n.get("sceneID") is not None or plugin in snames:
                continue
            if plugin in REMOVED_V3:
                warn("scene %r node %s: %r was %s" % (s.get("name"), n.get("id"), plugin, REMOVED_V3[plugin]))
            elif plugin in RENAMED_V3:
                warn("scene %r node %s: %r is the pre-3.0 name; Magic 3 saves %r" % (s.get("name"), n.get("id"), plugin, RENAMED_V3[plugin]))
            elif plugin not in known and plugin not in custom:
                warn("scene %r node %s: %r is not a Magic 3.0 module or in the Additional Module Folders" % (s.get("name"), n.get("id"), plugin))
            elif plugin in known:
                extra = [iv.get("name") for iv in params(n) if iv.get("name") not in known[plugin]["params"]]
                if extra:
                    warn("scene %r node %s %s: params %s are not in Magic 3's %s" % (s.get("name"), n.get("id"), plugin, extra, plugin))
    if root.get("videoSharing") != "1":
        warn("Syphon output is off (videoSharing=0): `grab` will not see this project")
    return out


def _where(root, iv):
    for g in global_ivs(root):
        if g is iv:
            return "Global %r" % iv.get("name")
    return "param %r (id %s)" % (iv.get("name"), iv.get("id"))


# --- Edits (calculations on a copy) ------------------------------------------

def next_id(root):
    """Next free id. Magic uses one counter for modules, params, tracks and sources."""
    ids = [int(e.get("id")) for e in root.iter() if e.tag in ("InputValue", "Node", "Track", "Layer")]
    return max(ids + [0]) + 1


def op_element(kind, value):
    """kind: modifier name or index; value: number, or the expression for Expression."""
    t = kind if isinstance(kind, int) else MODIFIERS.index(kind)
    expr = str(value) if t == EXPRESSION else "x"
    p = 0 if t == EXPRESSION else value
    return ET.Element("ValueOperator", type=str(t), param=_fmt(p), bypassed="0", paramLayerID="-1", paramFeature="-1",
                      paramSubFeature="-1", paramFeatureString="", bypassLayerID="-1", bypassFeature="-1",
                      bypassSubFeature="-1", bypassMidiToggle="0", bypassFeatureString="", paramMidiScale="1",
                      paramString=expr)


def parse_mod(spec):
    """'Smooth:0.6', 'Expression:x*2' or 'x*2' (an Expression)."""
    kind, sep, rest = spec.partition(":")
    if sep and kind in MODIFIERS:
        return (kind, rest if kind == "Expression" else float(rest))
    return ("Expression", spec)


def set_source(root, iv, source):
    """source: None (manual), 'calc', 'global:Name', 'osc:/addr', 'internal:Name',
    'audio:<source name>:<feature>[:<range>]' (feature/range by name or index)."""
    for k in ("feature", "subFeature", "featureString"):
        iv.attrib.pop(k, None)
    if source in (None, "manual"):
        iv.attrib.update(linked="0", layerID="-1", feature="0", subFeature="0")
        return iv
    iv.attrib.update(linked="1", open="1")
    kind, _, rest = source.partition(":")
    if kind == "calc":
        iv.attrib.update(layerID="-1", feature="0", subFeature="0")
    elif kind == "global":
        iv.attrib.update(layerID=str(GLOBAL_LAYER), feature=find_global(root, rest).get("id"), globalsUseID="1")
    elif kind == "internal":
        by_name = {v.lower(): k for k, v in INTERNALS.items()}
        iv.attrib.update(layerID=str(INTERNAL_LAYER), feature=str(int(rest) if rest.isdigit() else by_name[rest.lower()]),
                         subFeature="0")
    elif kind == "osc":
        layers = [l for l in root.iter("Layer") if _track(root, l) is not None and _track(root, l).get("isOSC") == "1"]
        if not layers:
            raise ValueError("no OSC source in the project; add one with --osc-in PORT")
        iv.attrib.update(layerID=layers[0].get("id"), featureString=rest)
    elif kind == "midi":
        lname, _, feat = rest.partition(":")
        feat, _, sub = feat.partition(":")
        layer = next((l for l in root.iter("Layer") if l.get("name") == lname or l.get("id") == lname), None)
        if layer is None:
            raise KeyError("no source %r; add one with --midi-in DEVICE[:CHANNEL]" % lname)
        f = _index(MIDI_FEATURES, feat or "Velocity")
        subf = _index(BEAT_CLOCK, sub) if f == 8 and sub and not sub.isdigit() else int(sub or 0)
        iv.attrib.update(layerID=layer.get("id"), feature=str(f), subFeature=str(subf))
    elif kind == "audio":
        lname, _, feat = rest.partition(":")
        feat, _, rng = feat.partition(":")
        layer = next((l for l in root.iter("Layer") if l.get("name") == lname or l.get("id") == lname), None)
        if layer is None:
            raise KeyError("no source %r" % lname)
        iv.attrib.update(layerID=layer.get("id"), feature=str(_index(AUDIO_FEATURES, feat or "Volume")),
                         subFeature=str(_index(FREQ_RANGES, rng) if rng else 0))
    else:
        raise ValueError("unknown source %r" % source)
    return iv


def _index(names, key):
    if str(key).isdigit():
        return int(key)
    for i, n in enumerate(names):
        if n.lower().replace(" ", "") == str(key).lower().replace(" ", ""):
            return i
    raise KeyError("%r not in %s" % (key, names))


def _track(root, layer):
    return next((t for t in root.iter("Track") if t.get("id") == layer.get("trackID")), None)


def input_value(root, name, value, source=None, mods=(), iv_id=None):
    iv = ET.Element("InputValue", name=name, id=str(iv_id or next_id(root)), globalsUseID="1",
                    linked="0", open="0", layerID="-1", feature="0", subFeature="0")
    set_source(root, iv, source)
    iv.set("featureVersion", "1")
    iv.set("value", _fmt(value))
    vo = ET.SubElement(iv, "ValueOperators")
    for kind, v in mods:
        vo.append(op_element(kind, v))
    return iv


def set_modifiers(iv, mods):
    vo = iv.find("ValueOperators")
    if vo is None:
        vo = ET.SubElement(iv, "ValueOperators")
    for op in list(vo):
        vo.remove(op)
    for kind, v in mods:
        vo.append(op_element(kind, v))


def add_global(root, name, value=0, source=None, mods=(), after=None):
    root = _copy(root)
    if name in global_names(root).values():
        raise ValueError("Global %r exists" % name)
    iv = input_value(root, name, value, source, mods)
    g = globals_el(root)
    pos = len(g) if after is None else list(g).index(find_global(root, after)) + 1
    g.insert(pos, iv)
    return root


def remove_global(root, name):
    """Removes a Global; params linked to it become manual at their value."""
    root = _copy(root)
    iv = find_global(root, name)
    gid = iv.get("id")
    globals_el(root).remove(iv)
    for other in root.iter("InputValue"):
        if other.get("layerID") == str(GLOBAL_LAYER) and other.get("feature") == gid:
            set_source(root, other, None)
    return root


def edit_global(root, name, value=None, source=False, mods=None, rename=None):
    root = _copy(root)
    iv = find_global(root, name)
    if value is not None:
        iv.set("value", _fmt(value))
    if source is not False:
        set_source(root, iv, source)
    if mods is not None:
        set_modifiers(iv, mods)
    if rename:
        if rename in global_names(root).values():
            raise ValueError("Global %r exists" % rename)
        for op in root.iter("ValueOperator"):
            if op.get("type") == str(EXPRESSION):
                op.set("paramString", re.sub(r"\b%s\b" % re.escape(name), rename, op.get("paramString")))
        iv.set("name", rename)
    return root


def edit_param(root, scene, node_id, name, value=None, source=False, mods=None):
    root = _copy(root)
    node = next((n for n in scene_nodes(find_scene(root, scene)) if n.get("id") == str(node_id)), None)
    if node is None:
        raise KeyError("no node %s in scene %r" % (node_id, scene))
    iv = param(node, name)
    if iv is None:
        iv = input_value(root, name, value if value is not None else 0)
        node.find("InputValues").append(iv)
    if value is not None:
        iv.set("value", _fmt(value))
    if source is not False:
        set_source(root, iv, source)
    if mods is not None:
        set_modifiers(iv, mods)
    return root


def set_syphon(root, on=True, name=None, size=None):
    root = _copy(root)
    root.set("videoSharing", "1" if on else "0")
    if name:
        root.set("videoSharingName", name)
    if size:
        w, h = size
        # Graphics resolution: fixed size (not "size of Magic Window"), used for Syphon too.
        root.attrib.update(videoSharingWidth=str(w), videoSharingHeight=str(h), fixedMagicSize="1")
        rs = root.find("RenderSettings")
        if rs is not None:
            rs.attrib.update(width=str(w), height=str(h))
    return root


def set_osc_target(root, ip=None, port=None, prefix=""):
    root = _copy(root)
    for n in root.iter("Node"):
        if n.get("pluginName") != "OSCSender":
            continue
        msg = param(n, "Message")
        if msg is not None and not (msg.get("value") or "").startswith(prefix):
            continue
        for pname, v in (("IP Addr.", ip), ("Port", port)):
            if v is not None and param(n, pname) is not None:
                param(n, pname).set("value", str(v))
    return root


def add_midi_in(root, device, channel=1, name="MIDI"):
    """A source on MIDI `device` channel `channel` (0 = global: Beat Clock).
    Magic writes 17 Tracks (channels 0..16) per MIDI device; so does this."""
    root = _copy(root)
    tracks = [t for t in root.iter("Track") if t.get("isMidi") == "1" and t.get("isInput") == "1" and t.get("name") == device]
    if not tracks:
        tid = next_id(root)
        tracks = [ET.SubElement(root.find("Tracks"), "Track", id=str(tid + ch), channel=str(ch), isInput="1", name=device,
                                deviceName="", isMidi="1") for ch in range(17)]
    track = next(t for t in tracks if t.get("channel") == str(channel))
    layer = next((l for l in root.iter("Layer") if l.get("name") == name), None)
    if layer is None:
        layer = ET.SubElement(root.find("Layers"), "Layer", name=name, id=str(next_id(root)), gain="0", gainVisible="0")
    layer.set("trackID", track.get("id"))
    return root


def connect(root, scene, node_id, inputs):
    """Set a node's input pins, top to bottom, to the nodes `inputs` (ids)."""
    root = _copy(root)
    sc = find_scene(root, scene)
    node = next((n for n in scene_nodes(sc) if n.get("id") == str(node_id)), None)
    if node is None:
        raise KeyError("no node %s in scene %r" % (node_id, scene))
    here = {n.get("id") for n in scene_nodes(sc)}
    missing = [i for i in map(str, inputs) if i not in here]
    if missing:
        raise KeyError("nodes %s are not in scene %r" % (missing, scene))
    ch = node.find("Children")
    for c in list(ch):
        ch.remove(c)
    for i in inputs:
        ET.SubElement(ch, "Child", id=str(i))
    return root


def route_source(root, source, device, channel=0):
    """Point a source (Layer) at an audio input device channel. Magic 3 lets
    each source use a different device; a missing source is created."""
    root = _copy(root)
    track = next((t for t in root.iter("Track") if t.get("isInput") == "1" and not t.get("isMidi") and not t.get("isOSC")
                  and (t.get("deviceName") or t.get("name").rsplit(" ", 1)[0]) == device and t.get("channel") == str(channel)), None)
    if track is None:
        track = ET.SubElement(root.find("Tracks"), "Track", id=str(next_id(root)), channel=str(channel), isInput="1",
                              name="%s %d" % (device, channel), deviceName=device)
    layer = next((l for l in root.iter("Layer") if l.get("name") == source), None)
    if layer is None:
        layer = ET.SubElement(root.find("Layers"), "Layer", name=source, id=str(next_id(root)), gain="0", gainVisible="0")
    layer.set("trackID", track.get("id"))
    return root


def set_playlist(root, names=None, seconds=None, transition=None, style=None, enabled=True):
    """Playlist entries for the scenes `names` (names or ids; default all, in order).
    seconds: auto-advance time (sceneDuration); transition: seconds (duration);
    style: 0 none, 1 crossfade, 2 additive dissolve (Magic's button order)."""
    root = _copy(root)
    pls = root.find("Playlists")
    if pls is None:
        pls = ET.SubElement(root, "Playlists")
    pl = pls.find("Playlist")
    if pl is None:
        pl = ET.SubElement(pls, "Playlist", linkAutoAdvance="0", random="0")
    old = {e.get("id"): e for e in pl.findall("Scene")}
    wanted = [find_scene(root, n).get("id") for n in names] if names else [s.get("id") for s in scenes(root)]
    for e in list(pl):
        pl.remove(e)
    for sid in wanted:
        # Elements without children are falsy, so no `old.get(sid) or ...`.
        e = old[sid] if sid in old else ET.Element("Scene", id=sid, style="1", duration="2", sceneDuration="30", enabled="1", layerID="-1",
                                       feature="-1", subFeature="-1", featureString="")
        for k, v in (("sceneDuration", seconds), ("duration", transition), ("style", style)):
            if v is not None:
                e.set(k, _fmt(v))
        e.set("enabled", "1" if enabled else "0")
        pl.append(e)
    return root


def set_osc_in(root, port):
    """Port Magic listens on for OSC input (creates the source if missing)."""
    root = _copy(root)
    track = next((t for t in root.iter("Track") if t.get("isOSC") == "1"), None)
    if track is None:
        tid = next_id(root)
        track = ET.SubElement(root.find("Tracks"), "Track", id=str(tid), channel=str(port), isInput="1",
                              name="Open Sound Control", deviceName="", isOSC="1")
        ET.SubElement(root.find("Layers"), "Layer", name="OSC In", id=str(tid + 1), trackID=str(tid), gain="0", gainVisible="0")
    track.set("channel", str(port))
    return root


def add_audio(root, path, source="Source 0", channels=None, loop=True):
    """Adds an audio file and routes `source` (a Layer name) to its channel 0
    (and the next source to channel 1). Playback still needs the play button."""
    root = _copy(root)
    path = os.path.abspath(path)
    if channels is None:
        channels = 2
        if path.lower().endswith(".wav"):
            with wave.open(path) as w:
                channels = w.getnchannels()
    index = len(audio_files(root))
    for parent, tag in (("SoundFiles", "SoundFile"), ("AudioFiles", "AudioFile")):
        p = root.find(parent)
        if p is None:
            p = ET.SubElement(root, parent, **({"version": "2"} if parent == "AudioFiles" else {}))
        ET.SubElement(p, tag, filename=path, isMuted="0", isSoloed="0", offset="0")
    tid = next_id(root)
    tracks = []
    for ch in range(channels):
        tracks.append(ET.SubElement(root.find("Tracks"), "Track", id=str(tid + ch), channel=str(ch), isInput="0",
                                    name="%s %d" % (os.path.basename(path), ch), soundFileIndex=str(index),
                                    audioFileIndex=str(index)))
    layers = list(root.iter("Layer"))
    if source:
        start = next((i for i, l in enumerate(layers) if l.get("name") == source), None)
        if start is None:
            raise KeyError("no source %r" % source)
        audio_layers = [l for l in layers[start:] if (_track(root, l) is None or _track(root, l).get("isOSC") != "1")
                        and (_track(root, l) is None or _track(root, l).get("isMidi") != "1")]
        for l, t in zip(audio_layers, tracks):
            l.set("trackID", t.get("id"))
    if loop:
        root.set("looping", "1")
    return root


# --- Builder (calculations) --------------------------------------------------

class Builder:
    """Generates a project from scratch.

        b = Builder(syphon="magicproj")
        b.glob("Hue", 0.3)
        b.glob("Level", 0, "audio:Source 0:Volume", [("Smooth", 0.6)])
        s = b.scene("Main")
        poly = s.node("Polygon", {"Sides": 4})
        col = s.node("ColorHSB", {"Hue": ("global:Hue",), "Saturation": 1, "Brightness": 1}, inputs=[poly])
        s.output(col)
        b.write("out.magic")

    A param value is a constant, or (source, [mods], value) where source is a
    `set_source` string. Globals may be linked before they are defined.
    """

    def __init__(self, syphon=None, size=(1920, 1080), fps=60, audio_device=None, osc_in=None):
        """audio_device: input device for Source 0/1; default: the one Magic is set to."""
        self.size, self.fps, self.syphon, self.osc_in = size, fps, syphon, osc_in
        self.audio_device = audio_device or magic_pref("audioDevice") or "Built-in Microphone"
        self._globals = []      # (name, value, source, mods)
        self._scenes = []
        self._id = 0

    def new_id(self):
        self._id += 1
        return self._id

    def glob(self, name, value=0, source=None, mods=()):
        self._globals.append((name, value, source, list(mods)))
        return name

    def scene(self, name):
        s = _SceneBuilder(self, name, len(self._scenes))
        self._scenes.append(s)
        return s

    def build(self):
        root = _template(self)
        # Every Global exists before any link is resolved, so order is free.
        g = globals_el(root)
        for name, value, _, _ in self._globals:
            g.append(input_value(root, name, value, iv_id=self.new_id()))
        for (_, _, source, mods), iv in zip(self._globals, list(g)):
            set_source(root, iv, source)
            set_modifiers(iv, mods)
        scenes_el, tabs, tv, sti = (root.find(t) for t in ("Scenes", "Tabs", "TabsVisible", "SceneTreeItems"))
        pending = []
        for s in self._scenes:
            se = ET.SubElement(scenes_el, "Scene", name=s.name, id=str(s.index), isPostProcessing="0",
                               excludedFromPostProcessing="0", keepInGfxMem="0")
            rnode = _node_el(root, self.new_id(), "Magic", magic=True)
            for out in s.outputs:
                ET.SubElement(rnode.find("Children"), "Child", id=str(out.id))
            ET.SubElement(se, "Root").append(rnode)
            nl = ET.SubElement(se, "Nodes")
            tab = ET.SubElement(tabs, "Tab")
            depth = _depths(s)
            rows = {}
            for n in s.nodes:
                nl.append(n.element(root, pending))
                col = depth[n.id]
                rows[col] = rows.get(col, -1) + 1
                ET.SubElement(tab, "Node", x=str(15 + col * 210), y=str(15 + rows[col] * 150), id=str(n.id),
                              expanded="1", annotation="", annotationVisible="0")
            ET.SubElement(tab, "Node", x=str(15 + (max(depth.values(), default=-1) + 1) * 210), y="15",
                          id=rnode.get("id"), expanded="1", annotation="", annotationVisible="0")
            ET.SubElement(tv, "TabVis", sceneID=str(s.index))
            ET.SubElement(sti, "SceneTreeItem", id=str(s.index), group="0")
        for iv, source, mods in pending:
            set_source(root, iv, source)
            set_modifiers(iv, mods)
        return root

    def write(self, path):
        write(path, self.build())


class _NodeSpec:
    def __init__(self, builder, plugin, values, inputs, scene_id=None, bypass=None, power=None):
        self.id = builder.new_id()
        self.b, self.plugin, self.values, self.inputs = builder, plugin, values, inputs
        self.scene_id, self.bypass, self.power = scene_id, bypass, power

    def element(self, root, pending):
        e = _node_el(root, self.id, self.plugin, scene_id=self.scene_id, bypass=self.bypass, power=self.power)
        for i in self.inputs:
            ET.SubElement(e.find("Children"), "Child", id=str(i.id))
        ivs = e.find("InputValues")
        items = list(self.values.items())
        if self.scene_id is None and has_bypass(self.plugin) and "Bypass" not in self.values:
            items.append(("Bypass", self.bypass or 0))
        if "Power" not in self.values:
            items.append(("Power", self.power or 1))
        for name, v in items:
            source, mods, value = None, [], v
            if isinstance(v, tuple):
                source = v[0]
                mods = list(v[1]) if len(v) > 1 else []
                value = v[2] if len(v) > 2 else 0
            iv = input_value(root, name, value, None, (), iv_id=self.b.new_id())
            ivs.append(iv)
            if source:
                pending.append((iv, source, mods))
        return e


class _SceneBuilder:
    def __init__(self, builder, name, index):
        self.b, self.name, self.index = builder, name, index
        self.nodes, self.outputs = [], []

    def node(self, plugin, values=None, inputs=(), bypass=None, power=None):
        """bypass/power: a constant or (source, [mods]) like any param."""
        n = _NodeSpec(self.b, plugin, dict(values or {}), list(inputs), bypass=bypass, power=power)
        self.nodes.append(n)
        return n

    def scene_module(self, scene, power=None):
        n = _NodeSpec(self.b, scene.name, {}, [], scene_id=scene.index, power=power)
        self.nodes.append(n)
        return n

    def chain(self, *nodes):
        for a, b in zip(nodes, nodes[1:]):
            b.inputs.append(a)
        return nodes[-1]

    def output(self, *nodes):
        self.outputs.extend(nodes)


def _depths(scene):
    depth = {}

    def d(n):
        if n.id not in depth:
            depth[n.id] = 0
            depth[n.id] = 1 + max([d(i) for i in n.inputs], default=-1)
        return depth[n.id]
    for n in scene.nodes:
        d(n)
    return depth


def _node_el(root, nid, plugin, scene_id=None, bypass=None, power=None, magic=False):
    e = ET.Element("Node", pluginName=plugin, magicNode="1" if magic else "0", disabled="0", bypassed="0",
                   bypassParamUsed="1" if isinstance(bypass, tuple) else "0",
                   powerParamUsed="1" if isinstance(power, tuple) else "0", dontRestart="0", id=str(nid))
    if scene_id is not None:
        e.set("sceneID", str(scene_id))
    ET.SubElement(e, "Children")
    ET.SubElement(e, "InputValues")
    return e


def _template(b):
    w, h = b.size
    root = ET.Element("Project", looping="0", playlistChangesTabs="0", videoSharing="1" if b.syphon else "0",
                      videoSharingWidth=str(w), videoSharingHeight=str(h), fixedMagicSize="1", fontSize="13",
                      audioFilePanelHeight="0", version="1.5", actualVersion="3")
    if b.syphon and b.syphon != "Main Server":
        root.set("videoSharingName", b.syphon)
    ET.SubElement(root, "RenderSettings", width=str(w), height=str(h), fps=str(b.fps), duration="600", usePlaylist="0",
                  format="1001", quality="7", outputFolder="", outputFile="")
    ET.SubElement(root, "PlaylistMidiConfig", layerID="-1", featureString="", feature="-1", subFeature="-1",
                  prevLayerID="-1", prevFeatureString="", prevFeature="-1", prevSubFeature="-1", nextLayerID="-1",
                  nextFeatureString="", nextFeature="-1", nextSubFeature="-1", playlistStartTimes="0",
                  playlistMidiConfig="0", playlistDetails="1", playlistTransitions="0")
    ET.SubElement(root, "SoundFiles")
    ET.SubElement(root, "AudioFiles", version="2")
    tracks = ET.SubElement(root, "Tracks")
    layers = ET.SubElement(root, "Layers")
    for ch in range(2):
        tid = b.new_id()
        ET.SubElement(tracks, "Track", id=str(tid), channel=str(ch), isInput="1", name="%s %d" % (b.audio_device, ch),
                      deviceName=b.audio_device)
        ET.SubElement(layers, "Layer", name="Source %d" % ch, id=str(b.new_id()), trackID=str(tid), gain="0", gainVisible="0")
    if b.osc_in:
        tid = b.new_id()
        ET.SubElement(tracks, "Track", id=str(tid), channel=str(b.osc_in), isInput="1", name="Open Sound Control",
                      deviceName="", isOSC="1")
        ET.SubElement(layers, "Layer", name="OSC In", id=str(b.new_id()), trackID=str(tid), gain="0", gainVisible="0")
    ET.SubElement(root, "Scenes")
    pl = ET.SubElement(ET.SubElement(root, "Playlists"), "Playlist", linkAutoAdvance="0", random="0")
    ET.SubElement(pl, "Scene", id="0", style="1", duration="2", sceneDuration="30", enabled="1", layerID="-1")
    for t in ("Tabs", "TabsVisible", "SceneTreeItems", "Globals"):
        ET.SubElement(root, t)
    return root


# --- Catalog (calculations) --------------------------------------------------

def catalog(roots):
    """plugin -> {param name: example value} from saved projects (native modules)."""
    out = {}
    for root in roots:
        for n in root.iter("Node"):
            if n.get("magicNode") == "1" or n.get("sceneID") is not None or not n.get("pluginName"):
                continue
            ps = out.setdefault(n.get("pluginName"), {})
            for iv in params(n):
                ps.setdefault(iv.get("name"), iv.get("value"))
    return out


def isf_params(text):
    """Magic's param names for an ISF shader: LABEL, else NAME with a capital
    first letter; point2D becomes '<Name> X' and '<Name> Y'. -> {name: default}."""
    m = re.search(r"/\*(.*?)\*/", text, re.S)
    if not m:
        return {}
    out = {}
    header = re.sub(r",(\s*[}\]])", r"\1", m.group(1))     # Magic accepts trailing commas
    for i in json.loads(header, strict=False).get("INPUTS", []):
        if i.get("TYPE") in ("image", "audio", "audioFFT"):
            continue
        name = i.get("LABEL") or i["NAME"]
        name = name[:1].upper() + name[1:]
        default = i.get("DEFAULT")
        if i.get("TYPE") == "point2D":
            d = default or [0, 0]
            out[name + " X"], out[name + " Y"] = d[0], d[1]
        elif i.get("TYPE") == "color":
            d = default or [0, 0, 0, 1]
            for c, v in zip("RGBA", d):
                out["%s %s" % (name, c)] = v
        else:
            out[name] = default
    return out


def magic_pref(name):
    """One value from Magic's preferences file, or None. Reads only the named key."""
    if not os.path.exists(MAGIC_PREFS):
        return None
    for v in ET.parse(MAGIC_PREFS).iter("VALUE"):
        if v.get("name") == name:
            return v.get("val")
    return None


@functools.lru_cache(maxsize=None)
def module_dirs():
    """Magic's built-in module folders plus the user's Additional Module Folders."""
    dirs = [os.path.join(MAGIC_APP, "Contents/MacOS", d) for d in ("Modules", "Modules2")]
    if os.path.exists(MAGIC_PREFS):
        for f in ET.parse(MAGIC_PREFS).iter("file"):
            if f.get("disabled") == "0" and f.get("name") and not f.get("name").endswith(".magic"):
                dirs.append(f.get("name"))
    return tuple(d for d in dirs if os.path.isdir(d))


@functools.lru_cache(maxsize=None)
def isf_catalog(dirs):
    """plugin (file stem) -> {param: default} for every .fs under dirs."""
    out = {}
    for d in dirs:
        for base, _, files in os.walk(d):
            for f in files:
                if f.endswith(".fs"):
                    try:
                        with open(os.path.join(base, f), encoding="utf-8", errors="replace") as fh:
                            out.setdefault(f[:-3], isf_params(fh.read()))
                    except ValueError:
                        pass
    return out


# --- Actions: files ----------------------------------------------------------

def read(path):
    with open(path, "rb") as f:
        return parse(f.read())


def write(path, root):
    with open(path, "wb") as f:
        f.write(encode(serialize(root)))


# --- Actions: running app ----------------------------------------------------

def _osascript(script):
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return r.stdout.strip(), r.stderr.strip()


def magic_windows():
    out, err = _osascript('tell application "System Events" to get name of every window of process "Magic"')
    if err:
        return None
    return [w.strip() for w in out.split(",") if w.strip()]


def load(path, timeout=20):
    """Opens a project in Magic (replacing the current one) and waits until the
    editor window names it. -> (ok, window names)."""
    path = os.path.abspath(path)
    subprocess.run(["open", "-a", MAGIC_APP, path], check=True)
    want = os.path.basename(path) + " - Editor"
    end = time.time() + timeout
    wins = []
    while time.time() < end:
        wins = magic_windows() or []
        if any(w.startswith(want) for w in wins):
            return True, wins
        time.sleep(0.5)
    return False, wins


def toggle_playback():
    """Play/pause audio files (Shift+Cmd+Space). Brings Magic to the front."""
    _osascript('tell application "MagicBeta" to activate')
    time.sleep(0.4)
    return _osascript('tell application "System Events" to keystroke space using {shift down, command down}')


def listen(port, seconds):
    """OSC messages received on `port` -> {address: [values]}."""
    if port in RESERVED_PORTS:
        raise ValueError("port %d is reserved (MAGICPROJ_RESERVED_PORTS); another process listens there" % port)
    sys.path.insert(0, os.path.join(HERE, "..", "osc"))
    from lab import parse_packet
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", port))
    s.settimeout(0.2)
    out, end = {}, time.time() + seconds
    while time.time() < end:
        try:
            data, _ = s.recvfrom(65535)
        except socket.timeout:
            continue
        for addr, _tags, args, _bundled in parse_packet(data):
            out.setdefault(addr, []).append(args[0] if len(args) == 1 else args)
    s.close()
    return out


def png_bytes(width, height, rgba_rows):
    """Minimal RGBA PNG; rgba_rows: list of row bytes, top first."""
    raw = b"".join(b"\0" + r for r in rgba_rows)
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def frame_stats(width, height, bgra_rows):
    """Mean RGB, lit fraction and a 3x3 grid of sample colours (rows top first)."""
    n, acc, lit = 0, [0, 0, 0], 0
    step = max(1, width * height // 40000)
    for y in range(0, height, max(1, int(step ** 0.5))):
        row = bgra_rows[y]
        for x in range(0, width, max(1, int(step ** 0.5))):
            b, g, r = row[x * 4], row[x * 4 + 1], row[x * 4 + 2]
            acc[0] += r; acc[1] += g; acc[2] += b; n += 1
            lit += (r + g + b) > 30
    grid = [[tuple(bgra_rows[int(height * (j + 0.5) / 3)][int(width * (i + 0.5) / 3) * 4:][:3][::-1]) for i in range(3)]
            for j in range(3)]
    return {"size": [width, height], "mean_rgb": [round(a / n, 1) for a in acc], "lit": round(lit / n, 3), "grid": grid}


def grab(app="Magic", server=None, out=None, timeout=10):
    """One Syphon frame from `app` -> stats dict; writes a PNG when `out` is set.
    Magic's frames arrive bottom-up; this flips them."""
    import syphon
    from syphon.utils.raw import copy_mtl_texture_to_bytes
    from Foundation import NSDate, NSRunLoop
    pump = lambda s: NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(s))
    d = syphon.SyphonServerDirectory()
    end = time.time() + timeout
    while time.time() < end:
        pump(0.3)
        for desc in d.servers:
            if desc.app_name != app or (server and desc.name != server):
                continue
            c = syphon.SyphonMetalClient(desc)
            t = time.time()
            while not c.has_new_frame and time.time() - t < 2:
                pump(0.02)
            if not c.has_new_frame:
                c.stop()
                continue
            tex = c.new_frame_image
            w, h = tex.width(), tex.height()
            raw = copy_mtl_texture_to_bytes(tex)
            c.stop()
            stride = len(raw) // h
            rows = [raw[y * stride:y * stride + w * 4] for y in range(h)]
            if app == "Magic":
                rows.reverse()
            stats = frame_stats(w, h, rows)
            stats["server"] = "%s - %s" % (desc.name, desc.app_name)
            if out:
                rgba = [bytes(x for i in range(0, len(r), 4) for x in (r[i + 2], r[i + 1], r[i], 255)) for r in rows]
                with open(out, "wb") as f:
                    f.write(png_bytes(w, h, rgba))
                stats["png"] = out
            return stats
    servers = ["%s - %s" % (s.name, s.app_name) for s in d.servers]
    raise RuntimeError("no frame from %s%s; servers: %s" % (app, " / " + server if server else "", servers or "none"))


def _grab_subprocess(argv):
    env = dict(os.environ, PYTHONPATH=SYPHON_PATH, MAGICPROJ_NO_REEXEC="1")
    return subprocess.run([SYPHON_PYTHON, os.path.abspath(__file__)] + argv, env=env).returncode


# --- CLI ---------------------------------------------------------------------

def _print_json(obj):
    print(json.dumps(obj, indent=2, default=str))


def _kv(spec):
    k, sep, v = spec.partition("=")
    if not sep:
        raise argparse.ArgumentTypeError("expected NAME=VALUE, got %r" % spec)
    return k, v


def _value(v):
    try:
        return float(v)
    except ValueError:
        return v


def cmd_info(a):
    s = summary(read(a.file))
    if a.json:
        return _print_json(s)
    sy = s["syphon"]
    print("Magic project v%s/%s, render %s, Syphon %s (%s, %s), looping %s" % (
        s["version"], s["actualVersion"], s["render"], "on" if sy["on"] else "off", sy["name"], sy["size"], s["looping"]))
    print("scenes: " + ", ".join("%s %s (%d)" % (x["id"], x["name"], x["modules"]) for x in s["scenes"]))
    print("playlist: " + (", ".join("%s%s %ss/%ss style %s" % (e.get("id"), "" if e.get("enabled", "1") == "1" else " (off)",
                                                          e.get("sceneDuration"), e.get("duration"), e.get("style"))
                                    for e in s["playlist"]) or "-"))
    print("globals: %d, OSC senders: %d, OSC in ports: %s" % (s["globals"], s["osc_senders"], ", ".join(s["osc_in_ports"]) or "-"))
    print("audio inputs: %s; files: %s" % (", ".join(s["audio_inputs"]) or "-", ", ".join(s["audio_files"]) or "-"))
    print("sources: " + ", ".join("%s->track %s" % (x["name"], x["track"]) for x in s["sources"]))


def cmd_globals(a):
    rows = global_table(read(a.file))
    if a.name:
        rows = [r for r in rows if re.search(a.name, r["name"])]
    if a.json:
        return _print_json(rows)
    for r in rows:
        print("%-14s %-10s %-28s %s" % (r["name"], _fmt(r["value"]), r["source"], format_mods(r["modifiers"])))


def cmd_nodes(a):
    rows = node_table(read(a.file), a.scene)
    if a.plugin:
        rows = [r for r in rows if re.search(a.plugin, r["plugin"] or "")]
    if a.json:
        return _print_json(rows)
    for r in rows:
        extra = " -> scene %r" % r["scene_module"] if r["scene_module"] else (" isf=%s" % r["isf"] if r["isf"] else "")
        print("[%s] %s %s%s inputs=%s%s" % (r["scene"], r["id"], r["plugin"], extra, ",".join(r["inputs"]) or "-",
                                             " BYPASSED" if r["bypassed"] else ""))
        for p in r["params"]:
            link = "" if p["source"] == "manual" else "  <- %s %s" % (p["source"], format_mods(p["modifiers"]))
            print("    %-16s %s%s" % (p["name"], p["value"], link))


def cmd_osc(a):
    rows = osc_senders(read(a.file))
    if a.json:
        return _print_json(rows)
    for r in rows:
        print("%-22s -> %s:%s  <- %s %s" % (r["message"], r["ip"], r["port"], r["value_source"], format_mods(r["modifiers"])))


def cmd_check(a):
    problems = check(read(a.file), os.path.dirname(os.path.abspath(a.file)))
    for level, msg in problems:
        print("%s: %s" % (level, msg))
    errors = sum(1 for l, _ in problems if l == "error")
    print("%d errors, %d warnings" % (errors, len(problems) - errors))
    return 1 if errors else 0


def cmd_diff(a):
    rows = diff(read(a.a), read(a.b))
    if a.json:
        return _print_json([{"key": k, "old": o, "new": n} for k, o, n in rows])
    for k, o, n in rows:
        if o is None:
            print("+ %s = %s" % (k, n))
        elif n is None:
            print("- %s = %s" % (k, o))
        else:
            print("~ %s: %s -> %s" % (k, o, n))
    print("%d differences" % len(rows))


def cmd_decode(a):
    xml = decode(open(a.file, "rb").read())
    if a.out:
        open(a.out, "wb").write(xml)
    else:
        sys.stdout.write(xml.decode("utf-8"))


def cmd_encode(a):
    root = ET.fromstring(open(a.xml, "rb").read())
    write(a.out, root)
    print("wrote", a.out)


def cmd_set(a):
    root = read(a.file)
    for name in a.remove_global or []:
        root = remove_global(root, name)
    for spec in a.add_global or []:
        name, value = _kv(spec)
        root = add_global(root, name, _value(value))
    for name, value in a.value or []:
        root = edit_global(root, name, value=_value(value))
    for name, src in a.source or []:
        root = edit_global(root, name, source=src)
    for name, mods in a.mods or []:
        root = edit_global(root, name, mods=[parse_mod(m) for m in mods.split(";") if m.strip()])
    for old, new in a.rename or []:
        root = edit_global(root, old, rename=new)
    for spec, value in a.param or []:
        scene, node_id, pname = spec.split("/", 2)
        if value.startswith("@"):
            root = edit_param(root, scene, node_id, pname, source=value[1:])
        else:
            root = edit_param(root, scene, node_id, pname, value=_value(value))
    if a.syphon or a.syphon_name or a.size:
        # --size alone changes the graphics resolution and keeps Syphon as it was.
        on = a.syphon == "on" if a.syphon else (True if a.syphon_name else root.get("videoSharing") == "1")
        size = tuple(int(x) for x in a.size.lower().split("x")) if a.size else None
        root = set_syphon(root, on, a.syphon_name, size)
    if a.osc_target:
        ip, _, port = a.osc_target.rpartition(":")
        root = set_osc_target(root, ip or None, int(port), a.osc_prefix or "")
    if a.osc_in:
        root = set_osc_in(root, a.osc_in)
    for spec, ids in a.inputs or []:
        scene, _, node_id = spec.rpartition("/")
        root = connect(root, scene, node_id, [i for i in ids.split(",") if i])
    for spec in a.route or []:
        src, _, target = spec.partition("=")
        dev, _, ch = target.rpartition(":") if re.search(r":\d+$", target) else (target, "", "0")
        root = route_source(root, src, dev, int(ch))
    for spec in a.midi_in or []:
        dev, _, name = spec.partition("=")
        dev, _, ch = dev.rpartition(":") if re.search(r":\d+$", dev) else (dev, "", "1")
        root = add_midi_in(root, dev, int(ch), name or "MIDI")
    if a.playlist_scenes or a.playlist_seconds is not None or a.playlist_transition is not None or a.playlist_style:
        style = {"none": 0, "crossfade": 1, "additive": 2}.get(a.playlist_style) if a.playlist_style else None
        names = [n.strip() for n in a.playlist_scenes.split(",")] if a.playlist_scenes else None
        root = set_playlist(root, names, a.playlist_seconds, a.playlist_transition, style)
    if a.audio:
        root = add_audio(root, a.audio, a.audio_source)
    if a.looping:
        root = _copy(root)
        root.set("looping", "1" if a.looping == "on" else "0")
    out = a.out or a.file
    problems = [p for p in check(root, os.path.dirname(os.path.abspath(out))) if p[0] == "error"]
    for _, msg in problems:
        print("error:", msg)
    if problems and not a.force:
        print("not written (use --force to write anyway)")
        return 1
    write(out, root)
    print("wrote", out)


def cmd_catalog(a):
    """Magic 3's own module list first; saved FILES (or the samples) and ISF headers
    in the Additional Module Folders add custom and third-party modules."""
    cat = {p: ("magic3", m["params"]) for p, m in modules_v3().items()}
    for p, v in isf_catalog(module_dirs()).items():
        cat.setdefault(p, ("isf", dict(v, Bypass=0, Power=1)))
    files = a.files or sorted(os.path.join(SAMPLES, f) for f in os.listdir(SAMPLES) if f.endswith(".magic"))
    for p, v in catalog(read(f) for f in files).items():
        cat.setdefault(p, ("saved", v))
    names = [p for p in sorted(cat) if not a.plugin or re.search(a.plugin, p, re.I)]
    if a.json:
        return _print_json({p: {"from": cat[p][0], "params": cat[p][1]} for p in names})
    for p in names:
        kind, ps = cat[p]
        print("%s [%s]: %s" % (p, kind, ", ".join("%s=%s" % kv for kv in ps.items())))


def cmd_load(a):
    ok, wins = load(a.file, a.timeout)
    print(("loaded" if ok else "NOT confirmed") + "; Magic windows: " + "; ".join(wins))
    extra = [w for w in wins if w not in ("Input Sources",) and " - " not in w]
    if extra:
        print("other windows (dialog?): " + "; ".join(extra))
    return 0 if ok else 1


def cmd_grab(a):
    try:
        import syphon  # noqa: F401
    except ImportError:
        if os.environ.get("MAGICPROJ_NO_REEXEC"):
            raise
        return _grab_subprocess(sys.argv[1:])
    if a.wait:
        time.sleep(a.wait)
    _print_json(grab(a.app, a.server, a.out, a.timeout))


def cmd_play(a):
    out, err = toggle_playback()
    print(err or "toggled playback (Shift+Cmd+Space)")


def cmd_listen(a):
    for addr, vals in sorted(listen(a.port, a.seconds).items()):
        print("%-24s n=%-5d last=%s" % (addr, len(vals), vals[-1]))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__.split("\n\n", 1)[1])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        p = sub.add_parser(name, help=help_)
        p.set_defaults(fn=fn)
        return p

    p = add("info", cmd_info, "project summary"); p.add_argument("file"); p.add_argument("--json", action="store_true")
    p = add("globals", cmd_globals, "Globals with source, value and modifiers"); p.add_argument("file")
    p.add_argument("--name", help="regex filter"); p.add_argument("--json", action="store_true")
    p = add("nodes", cmd_nodes, "modules per scene with params and links"); p.add_argument("file")
    p.add_argument("--scene"); p.add_argument("--plugin", help="regex filter"); p.add_argument("--json", action="store_true")
    p = add("osc", cmd_osc, "OSCSender targets and value sources"); p.add_argument("file"); p.add_argument("--json", action="store_true")
    p = add("check", cmd_check, "validate links, ids, names, files; exit 1 on errors"); p.add_argument("file")
    p = add("diff", cmd_diff, "semantic diff of two projects"); p.add_argument("a"); p.add_argument("b")
    p.add_argument("--json", action="store_true")
    p = add("decode", cmd_decode, ".magic -> XML"); p.add_argument("file"); p.add_argument("-o", "--out")
    p = add("encode", cmd_encode, "XML -> .magic"); p.add_argument("xml"); p.add_argument("-o", "--out", required=True)
    p = add("set", cmd_set, "edit a project (checked before writing)"); p.add_argument("file")
    p.add_argument("-o", "--out", help="default: overwrite FILE")
    p.add_argument("--value", nargs=2, action="append", metavar=("GLOBAL", "VALUE"))
    p.add_argument("--source", nargs=2, action="append", metavar=("GLOBAL", "SOURCE"),
                   help="manual | calc | global:Name | osc:/addr | internal:Name | audio:<source>:<feature>[:<range>]")
    p.add_argument("--mods", nargs=2, action="append", metavar=("GLOBAL", "CHAIN"),
                   help="replace the modifier chain: 'Smooth:0.6; x*Gain*4; Clamp:1' (bare text = Expression)")
    p.add_argument("--add-global", action="append", metavar="NAME=VALUE")
    p.add_argument("--remove-global", action="append", metavar="NAME")
    p.add_argument("--rename", nargs=2, action="append", metavar=("OLD", "NEW"), help="also rewrites expressions")
    p.add_argument("--param", nargs=2, action="append", metavar=("SCENE/NODE_ID/PARAM", "VALUE"),
                   help="VALUE or @SOURCE to link it")
    p.add_argument("--syphon", choices=["on", "off"]); p.add_argument("--syphon-name")
    p.add_argument("--size", help="fixed graphics resolution (also Syphon and export size), e.g. 1920x1080")
    p.add_argument("--osc-target", metavar="IP:PORT", help="every OSCSender (filter with --osc-prefix)")
    p.add_argument("--osc-prefix"); p.add_argument("--osc-in", type=int, metavar="PORT")
    p.add_argument("--inputs", nargs=2, action="append", metavar=("SCENE/NODE_ID", "ID,ID"), help="rewire a node's input pins")
    p.add_argument("--route", action="append", metavar="SOURCE=DEVICE[:CHANNEL]", help="route a source to an audio input channel")
    p.add_argument("--midi-in", action="append", metavar="DEVICE[:CHANNEL][=SOURCE]", help="add a MIDI source (default channel 1, name MIDI)")
    p.add_argument("--playlist-scenes", metavar="A,B,...", help="playlist entries (default: every scene)")
    p.add_argument("--playlist-seconds", type=float, help="auto-advance time per entry")
    p.add_argument("--playlist-transition", type=float, help="transition seconds")
    p.add_argument("--playlist-style", choices=["none", "crossfade", "additive"])
    p.add_argument("--audio", help="add an audio file and route a source to it"); p.add_argument("--audio-source", default="Source 0")
    p.add_argument("--looping", choices=["on", "off"], help="loop audio/MIDI file playback")
    p.add_argument("--force", action="store_true")
    p = add("catalog", cmd_catalog, "param names per module: saved projects (samples or FILES) + ISF headers")
    p.add_argument("files", nargs="*"); p.add_argument("--plugin"); p.add_argument("--json", action="store_true")
    p = add("load", cmd_load, "open in Magic (replaces its current project)"); p.add_argument("file")
    p.add_argument("--timeout", type=float, default=20)
    p = add("grab", cmd_grab, "one Syphon frame: stats, optional PNG"); p.add_argument("--app", default="Magic")
    p.add_argument("--server"); p.add_argument("--out"); p.add_argument("--wait", type=float, default=0)
    p.add_argument("--timeout", type=float, default=10)
    add("play", cmd_play, "toggle audio file playback (focuses Magic)")
    p = add("listen", cmd_listen, "log OSC that Magic sends to PORT"); p.add_argument("port", type=int)
    p.add_argument("--seconds", type=float, default=3)
    a = ap.parse_args(argv)
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
