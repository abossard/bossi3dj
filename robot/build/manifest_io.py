"""The Manifest export keeps what other sessions add (#32 intake: `backdrops`). Pure, no bpy.

build_robot.py owns the top-level keys manifest() returns; any other top-level key in the Manifest on disk stays as
it is, after the build's own keys.
"""
import json
import os


def merged(path, ours):
    """`ours` updated into the Manifest at `path` (if any): our keys replace theirs, keys we do not own stay."""
    if not os.path.isfile(path):
        return dict(ours)
    with open(path) as fh:
        old = json.load(fh)
    out = dict(ours)
    out.update({k: v for k, v in old.items() if k not in ours})
    return out
