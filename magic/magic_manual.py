"""The handbook's generated parts: the table of what Magic sends and why (made from the built show project and
synthwave_magic.MUSIC) and the stops of the Path Camera (made from osc/contract.json).

    python3 magic/magic_manual.py sync     rewrite both blocks in docs/handbook.md (between their begin and end markers)
    python3 magic/magic_manual.py check    exit 1 when a block is out of step (tests/test_manual.py does the same)
    python3 magic/magic_manual.py table    print the Magic table

One row per /vj/* address: the control Global you set by hand (named like the address), its value, and whether the music drives the
address and how. Whether an address follows the music is read from the project: its Out Global's expression names `Follow`.
Standard library only.
"""
import os
import re
import sys

import magicproj as mp
import show_magic as show
import synthwave_magic as sm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HANDBOOK = os.path.join(ROOT, "docs", "handbook.md")


def control_name(address):
    """/vj/fog_height -> FogHeight: the control Global of an address."""
    return "".join(w.capitalize() for w in address[len("/vj/"):].split("_"))


def reaches_follow(root, start):
    """Does the Global `start` read Follow, directly or through the Globals its expressions name?"""
    names = {g.get("name"): g for g in mp.global_ivs(root)}
    seen, todo = set(), [start]
    while todo:
        name = todo.pop()
        if name == "Follow":
            return True
        if name in seen or name not in names:
            continue
        seen.add(name)
        iv = names[name]
        if iv.get("layerID") == str(sm.GLOBAL_LAYER):
            todo.append(mp.global_names(root)[iv.get("feature")])
        for _kind, _param, expr, _bypassed in mp.modifiers(iv):
            if expr:
                todo += mp.expression_identifiers(expr)
    return False


def rows(root=None):
    """(address, control Global, control value, follows the music, what the music does) for every sender of the project, in contract order."""
    root = root if root is not None else sm.ET.fromstring(show.build())
    senders = {s["message"]: s for s in mp.osc_senders(root)}
    names = {g.get("name"): g for g in mp.global_ivs(root)}
    out = []
    for address in sm.CONTRACT:
        control = control_name(address)
        follows = reaches_follow(root, senders[address]["value_source"].split(":", 1)[1])
        out.append((address, control, names[control].get("value"), follows, sm.MUSIC.get(address) or PAD_TEXT.get(address, "Nothing, the control alone.")))
    return out


def render(root=None):
    lines = ["| Address | Control Global | Default | Music | What the music does |", "|---|---|---|---|---|"]
    for address, control, value, follows, what in rows(root):
        lines.append("| `%s` | `%s` | %s | %s | %s |" % (address, control, value, "follows" if follows else "no", what))
    return "\n".join(lines)


PAD_TEXT = {"/vj/meteor": "Nothing: the Meteor pad fires one.", "/vj/hit": "Nothing: the Hit pad fires one.",
            "/vj/cam_auto": "Nothing. Godot only: CamAuto 1 lets Godot's director cut, 0 holds the shot Cam picks.",
            "/vj/cam": "Nothing. Godot only: the shot while CamAuto is 0.",
            "/vj/takeover": "Nothing: how long a control you touched stays yours, here and in the scene."}


def render_camera():
    """The stops of the Path Camera's index controls and of its height, from the contract rows' `stops`."""
    lines = []
    for address in ("/vj/path", "/vj/target", "/vj/height"):
        row = sm.CONTRACT[address]
        lines += ["", "`%s`: %s" % (address, row["plain"]), "", "| Value | Name |", "|---|---|"]
        lines += ["| %g | %s |" % (s["wire"], s["name"]) for s in row["stops"]]
    return "\n".join(lines).strip("\n")


BLOCKS = {"magic-table": render, "path-camera": render_camera}


def markers(name):
    return "<!-- %s:begin -->" % name, "<!-- %s:end -->" % name


def current(text, name):
    begin, end = markers(name)
    return text[text.index(begin) + len(begin):text.index(end)].strip("\n")


def stale():
    with open(HANDBOOK) as f:
        text = f.read()
    return [name for name, make in BLOCKS.items() if current(text, name) != make()]


def sync():
    with open(HANDBOOK) as f:
        text = f.read()
    new = text
    for name, make in BLOCKS.items():
        begin, end = markers(name)
        new = new[:new.index(begin) + len(begin)] + "\n" + make() + "\n" + new[new.index(end):]
    if new != text:
        with open(HANDBOOK, "w") as f:
            f.write(new)
        print("wrote docs/handbook.md")


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "check"
    if cmd == "sync":
        sync()
    elif cmd == "table":
        print(render())
    elif cmd == "check":
        out = stale()
        for name in out:
            print("out of step with the project or the contract: docs/handbook.md block %s" % name)
        return 1 if out else 0
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
