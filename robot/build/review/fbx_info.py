"""Summarise binary FBX files without Blender: animation length, bones, meshes.

python3 -I robot/build/review/fbx_info.py <file.fbx|dir> [...]   (prints one JSON line per file)

Reads the files as data only. Used for the Mixamo clips and character FBXs in robot/assets/.
"""

import json
import pathlib
import struct
import sys
import zlib

KTIME_PER_S = 46186158000
ARRAY = {"f": ("f", 4), "d": ("d", 8), "l": ("q", 8), "i": ("i", 4), "b": ("?", 1)}


def read_props(buf, pos, n):
    props = []
    for _ in range(n):
        t = chr(buf[pos]); pos += 1
        if t == "Y": props.append(struct.unpack_from("<h", buf, pos)[0]); pos += 2
        elif t == "C": props.append(buf[pos] != 0); pos += 1
        elif t == "I": props.append(struct.unpack_from("<i", buf, pos)[0]); pos += 4
        elif t == "F": props.append(struct.unpack_from("<f", buf, pos)[0]); pos += 4
        elif t == "D": props.append(struct.unpack_from("<d", buf, pos)[0]); pos += 8
        elif t == "L": props.append(struct.unpack_from("<q", buf, pos)[0]); pos += 8
        elif t in ARRAY:
            length, enc, clen = struct.unpack_from("<III", buf, pos); pos += 12
            raw = buf[pos:pos + clen]; pos += clen
            fmt, size = ARRAY[t]
            data = zlib.decompress(raw) if enc == 1 else raw
            props.append(("array", t, length))
        elif t in "SR":
            ln = struct.unpack_from("<I", buf, pos)[0]; pos += 4
            raw = buf[pos:pos + ln]; pos += ln
            props.append(raw.decode("utf-8", "replace") if t == "S" else ("raw", ln))
        else:
            raise ValueError(f"property type {t!r} at {pos}")
    return props, pos


def read_nodes(buf, pos, end, wide):
    nodes = []
    hdr = "<QQQB" if wide else "<IIIB"
    hsize = struct.calcsize(hdr)
    while pos < end:
        end_off, nprops, _plen, nlen = struct.unpack_from(hdr, buf, pos)
        if end_off == 0:
            break
        name = buf[pos + hsize:pos + hsize + nlen].decode("ascii", "replace")
        props, p = read_props(buf, pos + hsize + nlen, nprops)
        children = read_nodes(buf, p, end_off, wide) if p < end_off else []
        nodes.append((name, props, children))
        pos = end_off
    return nodes


def summarise(path):
    buf = path.read_bytes()
    if not buf.startswith(b"Kaydara FBX Binary"):
        return {"file": path.name, "error": "not a binary FBX"}
    version = struct.unpack_from("<I", buf, 23)[0]
    top = read_nodes(buf, 27, len(buf), version >= 7500)
    objects = next((c for n, _, c in top if n == "Objects"), [])
    out = {"file": path.name, "fbx_version": version, "bones": 0, "meshes": 0, "seconds": None, "stacks": []}
    bone_names = []
    for name, props, children in objects:
        if name == "Model" and len(props) > 2 and props[2] == "LimbNode":
            out["bones"] += 1
            bone_names.append(str(props[1]).split("\x00")[0])
        if name == "Geometry" and len(props) > 2 and props[2] == "Mesh":
            out["meshes"] += 1
        if name == "AnimationStack":
            stop = None
            for cn, _, cc in children:
                if cn == "Properties70":
                    for _, pp, _ in cc:
                        if pp and pp[0] in ("LocalStop", "ReferenceStop") and stop is None:
                            stop = pp[-1]
            label = str(props[1]).split("\x00")[0]
            secs = round(stop / KTIME_PER_S, 3) if isinstance(stop, int) else None
            out["stacks"].append({"name": label, "seconds": secs})
            out["seconds"] = out["seconds"] or secs
    out["mixamo_rig"] = any(b.startswith("mixamorig") for b in bone_names)
    out["root"] = bone_names[0] if bone_names else None
    return out


def main():
    files = []
    for arg in sys.argv[1:]:
        p = pathlib.Path(arg)
        files += sorted(p.rglob("*.fbx")) if p.is_dir() else [p]
    for f in files:
        try:
            print(json.dumps(summarise(f)))
        except Exception as e:  # malformed input is reported, not fatal
            print(json.dumps({"file": f.name, "error": str(e)}))


if __name__ == "__main__":
    main()
