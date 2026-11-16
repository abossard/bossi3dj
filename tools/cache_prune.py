"""Prune ~/Library/Caches/swiftvj-flight (issue #17): keep only the bakes the current code reads.
    python3 tools/cache_prune.py [--dry-run]
A bake is keyed by its .blend's stem and mtime: flight_rt's clearance map "<stem>-<mtime>-<res>.npz", gpu_terrain's maps
"<CACHE_V>-<stem>-<mtime>-<grid>.npz". One is kept when its .blend is in blender/scenes with that mtime and, for a
versioned one, its prefix is gpu_terrain's CACHE_V. Fails closed: a name with a prefix it does not know (another
writer's, a future version's), anything matching neither pattern and anything not a plain file is left alone.
The live scene's bakes are therefore never touched; a rebuilt .blend leaves its old bakes to the next prune.
"""
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENES = os.path.join(ROOT, "blender", "scenes")
CACHE = os.path.expanduser("~/Library/Caches/swiftvj-flight")
BAKE = re.compile(r"^(?:(?P<v>gt\d*)-)?(?P<stem>.+)-(?P<mtime>\d+)-(?P<grid>[0-9a-z]+)\.npz$")


def cache_v():
    """gpu_terrain.CACHE_V, read from its source (it imports bpy)."""
    src = open(os.path.join(SCENES, "planet_proto", "gpu_terrain.py")).read()
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "CACHE_V" for t in node.targets):
            return node.value.value
    raise LookupError("CACHE_V not found in gpu_terrain.py")


def blends():
    """{stem: mtime as the bakes key it} of the .blend files in blender/scenes."""
    return {f[:-6]: int(os.path.getmtime(os.path.join(SCENES, f))) for f in os.listdir(SCENES) if f.endswith(".blend")}


def stale(names, current, version):
    """The bake files among names that no current .blend (current: {stem: mtime}) and no current version read."""
    out = []
    for n in names:
        m = BAKE.match(n)
        if m is None or m["v"] is None and "-" in m["stem"]:      # not a bake, or an unknown prefix: kept
            continue
        if m["v"] is not None and m["v"] != version or current.get(m["stem"]) != int(m["mtime"]):
            out.append(n)
    return sorted(out)


def main(argv):
    if not os.path.isdir(CACHE):
        return 0
    names = [n for n in os.listdir(CACHE) if os.path.isfile(os.path.join(CACHE, n))]
    done, size = 0, 0
    for n in stale(names, blends(), cache_v()):
        p = os.path.join(CACHE, n)
        try:                        # a concurrent prune may have taken it: never fail make blender-open
            sz = os.path.getsize(p)
            if "--dry-run" not in argv:
                os.remove(p)
        except OSError:
            continue
        done, size = done + 1, size + sz
    print("cache_prune: %s %d stale bakes, %.0f MB (%s)" % ("would drop" if "--dry-run" in argv else "dropped", done,
                                                           size / 1e6, CACHE))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
