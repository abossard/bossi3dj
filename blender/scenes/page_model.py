"""What the control page on http 9210 shows, as plain data and without Blender (blender/tests/test_page_model.py).

synthwave_web.py reads the scene's vj_* properties and hands them to describe(); the page gets back every control with its
address, group and one-sentence description from osc/contract.json, and the sections in the order of the README manual.
Also here: the coverage check (every address Blender reads has a control), the preset file and the page settings.
Standard library only.
"""
import json
import os
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
LOCAL = os.path.join(ROOT, "blender", "local")        # git-ignored: presets and page settings of this machine
PRESET_FILE = os.path.join(LOCAL, "presets.json")
SETTINGS_FILE = os.path.join(LOCAL, "page.json")
PREFIX = "vj_"
CAMERA_KEY = "vj_cam"
OTHER = "Other"
# The Path Camera's choices, drawn first on the page in this order: index controls with named stops as buttons, the rest as faders.
CAMERA = ["vj_path", "vj_target", "vj_height", "vj_blend"]
NAME_MAX = 40
HOSTS = {"local": "127.0.0.1", "lan": "0.0.0.0"}


def key_of(address):
    """/vj/fog_height -> vj_fog_height, the scene property."""
    return address.strip("/").replace("/", "_")


def address_of(key):
    return "/" + key.replace("_", "/", 1)


def blender_rows(rows):
    return [r for r in rows if r.get("blender")]


def describe(controls, rows, groups):
    """The controls in the order of the README manual, each with address, group, plain, effect and unit from the contract.
    `controls`: dicts with at least "key" (the scene's UI data); `rows`: the contract's controls; `groups`: its group order.
    A property the contract does not know lands in group OTHER, last; the page never hides one."""
    by_key = {key_of(r["address"]): (i, r) for i, r in enumerate(rows)}
    rank = {g: i for i, g in enumerate(groups)}
    out = []
    for c in controls:
        i, row = by_key.get(c["key"], (len(rows), None))
        d = dict(c, address=address_of(c["key"]))
        if row is None:
            d.update(group=OTHER, label=c["key"][len(PREFIX):], plain="", effect="", unit="", stops=None, wire_default=None,
                     order=(len(groups), i, c["key"]))
        else:
            b = row.get("blender") or {}
            d.update(group=row["group"], label=row.get("label") or c["key"][len(PREFIX):], plain=row["plain"], effect=b.get("effect", ""),
                     unit=b.get("unit", ""), stops=row.get("stops"),
                     wire_default=row["default"], order=(rank.get(row["group"], len(groups)), i, c["key"]))
        out.append(d)
    out.sort(key=lambda d: d["order"])
    for d in out:
        del d["order"]
    return out


def sections(described, skip=()):
    """[{"title", "keys"}] in manual order, one per group that has controls: what the page draws below the camera."""
    out = []
    for d in described:
        if d["key"] in skip:
            continue
        if not out or out[-1]["title"] != d["group"]:
            out.append({"title": d["group"], "keys": []})
        out[-1]["keys"].append(d["key"])
    return out


def coverage(controls, rows):
    """The addresses Blender reads that have no control on the page, and the page's properties the contract does not list."""
    have = {c["key"] for c in controls}
    want = {key_of(r["address"]): r["address"] for r in blender_rows(rows)}
    return {"missing": sorted(a for k, a in want.items() if k not in have), "extra": sorted(k for k in have if k not in want)}


def page_state(controls, rows, groups):
    """The part of /api/state that describes the controls (the values and the rest come from the scene on every snapshot)."""
    d = describe(controls, rows, groups)
    have = {c["key"] for c in d}
    camera = [k for k in CAMERA if k in have]
    return {"controls": d, "path_camera": camera, "sections": sections(d, camera), "coverage": coverage(controls, rows)}


# ---------------------------------------------------------------- source badge counts

def source_counts(sources, hold, keys):
    """How many of `keys` take their value from each source (the bridge's `source` map), plus how many are held."""
    counts = {}
    for k in keys:
        s = sources.get(k)
        if s:
            counts[s] = counts.get(s, 0) + 1
    counts["held"] = len([k for k in keys if k in hold])
    return counts


# ---------------------------------------------------------------- Art-Net chip

def artnet_chip(state, fps=0.0):
    """The status chip for the bridge's Art-Net input (`bridge.artnet_state()`, None when the bridge has none): {"level", "text"}, level
    "off" (nothing to say), "ok" (frames arrive), "warn" (listening, nothing usable yet) or "bad" (not listening).
    `fps` is the rate of frames of the universe in use over the last seconds."""
    if not state:
        return {"level": "off", "text": "Art-Net -"}
    if not state.get("enabled"):
        return {"level": "off", "text": "Art-Net off"}
    if not state.get("bound"):
        return {"level": "bad", "text": "Art-Net not listening (%s)" % (state.get("error") or "port busy")}
    where = "u%s a%s" % (state.get("universe"), state.get("address"))
    if fps > 0:
        return {"level": "ok", "text": "Art-Net %s, %d fps" % (where, round(fps))}
    if state.get("other_universe") and not state.get("frames"):
        return {"level": "warn", "text": "Art-Net %s, frames for another universe" % where}
    if state.get("frames"):
        return {"level": "warn", "text": "Art-Net %s, no frames now" % where}
    return {"level": "warn", "text": "Art-Net %s, no frames yet" % where}


def rate(prev, now, frames):
    """Frames per second between two readings (time, count); 0 when there is no earlier reading or the counter went back."""
    if prev is None or now <= prev[0] or frames < prev[1]:
        return 0.0
    return (frames - prev[1]) / (now - prev[0])


# ---------------------------------------------------------------- presets

class PresetError(ValueError):
    pass


class Presets:
    """Named sets of control values in one JSON file, written whole and atomically so a crash never leaves half a file."""

    def __init__(self, path=PRESET_FILE):
        self.path = path

    def all(self):
        try:
            with open(self.path) as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def save(self, name, values, known):
        """Stores `values` (key -> number) under `name`. Keys the scene does not have are refused, not dropped."""
        name = str(name or "").strip()
        if not name or len(name) > NAME_MAX:
            raise PresetError("name must be 1 to %d characters" % NAME_MAX)
        bad = sorted(k for k in values if k not in known)
        if bad:
            raise PresetError("unknown controls: %s" % ", ".join(bad))
        clean = {}
        for k, v in values.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise PresetError("%s is not a number" % k)
            clean[k] = round(float(v), 6)
        data = self.all()
        data[name] = {"values": clean}
        self._write(data)
        return data

    def delete(self, name):
        data = self.all()
        if name not in data:
            raise PresetError("no preset named %r" % name)
        del data[name]
        self._write(data)
        return data

    def _write(self, data):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path), suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=1, sort_keys=True)
        os.replace(tmp, self.path)


# ---------------------------------------------------------------- page settings

def read_settings(path=SETTINGS_FILE):
    """{"host": "local" | "lan"}. The page listens on 127.0.0.1 unless this machine's settings file says lan."""
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    return {"host": data.get("host") if data.get("host") in HOSTS else "local"}


def bind_host(path=SETTINGS_FILE):
    return HOSTS[read_settings(path)["host"]]


def host_allowed(host_header, lan, port):
    """The Host header of a request. On loopback only loopback names are served (a web page on another site cannot reach the
    scene by pointing a name of its own at 127.0.0.1); with lan on, any name goes, since the phone calls the Mac by its address."""
    if lan:
        return True
    host = (host_header or "").strip().lower()
    return host in ("127.0.0.1:%d" % port, "localhost:%d" % port, "[::1]:%d" % port, "127.0.0.1", "localhost")
