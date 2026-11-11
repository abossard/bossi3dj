"""The handbook's table of what Magic sends and why, made from the built show project and synthwave_magic.MUSIC.

    python3 magic/magic_manual.py sync     rewrite the table in docs/handbook.md (between the magic-table markers)
    python3 magic/magic_manual.py check    exit 1 when the table is out of step (tests/test_manual.py does the same)
    python3 magic/magic_manual.py table    print the table

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
BEGIN, END = "<!-- magic-table:begin -->", "<!-- magic-table:end -->"


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
            "/vj/cam_auto": "Nothing: CamAuto 1 lets the cutter cut (Godot: its own director), 0 holds the shot Cam picks."}


def current(text):
    return text[text.index(BEGIN) + len(BEGIN):text.index(END)].strip("\n")


def stale():
    with open(HANDBOOK) as f:
        return current(f.read()) != render()


def sync():
    with open(HANDBOOK) as f:
        text = f.read()
    new = text[:text.index(BEGIN) + len(BEGIN)] + "\n" + render() + "\n" + text[text.index(END):]
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
        if stale():
            print("out of step with the show project: docs/handbook.md magic table")
            return 1
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
