"""List the external files a .blend points at; with --fix, repoint paths from an old checkout.

    Blender -b --disable-autoexec FILE.blend --python tools/blend_paths.py -- [--fix]

Prints one JSON object: every text block, image, library, sound and font with its stored path
and whether the file exists. --fix rewrites paths that still name the swift-vj checkout
(Tools/magic-blender-lab/...) to this repository, relative to the .blend, and saves.
"""
import json
import os
import re
import sys

import bpy

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD = re.compile(r"^.*/Tools/magic-blender-lab/")
NEW = os.path.join(REPO, "blender") + os.sep


def blocks():
    for kind in ("texts", "images", "libraries", "sounds", "fonts", "movieclips"):
        for block in getattr(bpy.data, kind):
            path = getattr(block, "filepath", "")
            if path and path != "<builtin>":
                yield kind, block, path


def remap(path):
    """Old absolute checkout path -> path in this repo, relative to the open .blend."""
    absolute = bpy.path.abspath(path)
    if not OLD.match(absolute):
        return path
    return bpy.path.relpath(OLD.sub(NEW, absolute))


def main():
    fix = "--fix" in sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else False
    rows, changed = [], 0
    for kind, block, path in blocks():
        new = remap(path) if fix else path
        if new != path:
            block.filepath = new
            changed += 1
        rows.append({"kind": kind, "name": block.name, "path": new,
                     "exists": os.path.exists(bpy.path.abspath(new))})
    if changed:
        bpy.ops.wm.save_mainfile(compress=True)
    print("BLEND_PATHS " + json.dumps({"file": bpy.data.filepath, "changed": changed, "rows": rows}))


main()
