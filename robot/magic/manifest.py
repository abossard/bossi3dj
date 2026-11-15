"""Manifest loader and validator for a Render Package (contract: robot/CONTRACTS.md). Stdlib only.

    python3 robot/magic/manifest.py robot/package/fixture/manifest.json
"""
import json
import os
import sys

TIERS = ("calm", "build", "drop")
CLIP_BEATS = (4, 8, 16)
PASSES = ("beauty", "shadow", "depth")
MAX_ANGLES, MAX_CLIPS = 8, 256        # OSC wire: /vj/angle 0..7, /vj/clip 0..255
MOVE_SHARED = ("beats", "frames", "key_in", "key_out", "tier", "cut_points")


class ManifestError(Exception):
    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


def frames_for(beats, bpm, fps):
    """Frames of a Clip of `beats` beats: beats x 60 / bpm x fps, rounded half up."""
    return int(beats * 60.0 / bpm * fps + 0.5)


class Move:
    """What the Clips of one Move share across Angles."""

    def __init__(self, name, clip):
        self.name = name
        for k in MOVE_SHARED:
            setattr(self, k, clip[k])


class Manifest:
    def __init__(self, data, base_dir=None):
        self.data, self.base_dir = data, base_dir
        self.bpm, self.fps, self.size = data["bpm"], data["fps"], data["size"]
        self.key_poses = list(data["key_poses"])
        self.angles = list(data["angles"])
        self.clips = list(data["clips"])
        self.moves = []
        for c in self.clips:
            if c["move"] not in [m.name for m in self.moves]:
                self.moves.append(Move(c["move"], c))
        self._by = {(c["move"], c["angle"]): i for i, c in enumerate(self.clips)}

    @property
    def angle_ids(self):
        return [a["id"] for a in self.angles]

    def move(self, name):
        return next(m for m in self.moves if m.name == name)

    def clip_index(self, move, angle):
        """Index in `clips`: the value of /vj/clip."""
        return self._by[(move, angle)]

    def path(self, rel):
        return os.path.join(self.base_dir, rel) if self.base_dir else rel


def _require(d, keys, where, out):
    missing = [k for k in keys if k not in d]
    if missing:
        out.append("%s: missing %s" % (where, ", ".join(missing)))
    return not missing


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _json(path):
    with open(path) as f:
        return json.load(f)


def validate(data, base_dir=None):
    """Problems of a Manifest dict, one string each; with base_dir also the files and the frame counts in Clip Data."""
    out = []
    if not isinstance(data, dict):
        return ["manifest is not an object"]
    if not _require(data, ("version", "bpm", "fps", "size", "key_poses", "angles", "clips"), "manifest", out):
        return out
    if data["version"] != 1:
        out.append("version must be 1, got %r" % (data["version"],))
    for k in ("bpm", "fps"):
        if not isinstance(data[k], (int, float)) or isinstance(data[k], bool) or data[k] <= 0:
            out.append("%s must be a positive number" % k)
    size = data["size"]
    if not (isinstance(size, list) and len(size) == 2 and all(_is_int(v) and v > 0 for v in size)):
        out.append("size must be [width, height] of positive integers")
    poses = data["key_poses"]
    if not (isinstance(poses, list) and poses and all(isinstance(p, str) for p in poses)) or len(set(poses)) != len(poses):
        out.append("key_poses must be a non-empty list of unique names")
        poses = []
    angles = data["angles"]
    angle_ids = []
    if not (isinstance(angles, list) and angles):
        out.append("angles must be a non-empty list")
    else:
        for i, a in enumerate(angles):
            if isinstance(a, dict) and _require(a, ("id", "camera"), "angles[%d]" % i, out):
                angle_ids.append(a["id"])
        if len(set(angle_ids)) != len(angle_ids):
            out.append("angle ids are not unique")
        if len(angles) > MAX_ANGLES:
            out.append("%d angles, /vj/angle holds %d" % (len(angles), MAX_ANGLES))
    clips = data["clips"]
    if not (isinstance(clips, list) and clips):
        return out + ["clips must be a non-empty list"]
    if len(clips) > MAX_CLIPS:
        out.append("%d clips, /vj/clip holds %d" % (len(clips), MAX_CLIPS))
    ok_numbers = not any(m.startswith(("bpm", "fps")) for m in out)
    ids, by_move = set(), {}
    for i, c in enumerate(clips):
        where = "clips[%d]" % i
        if not isinstance(c, dict) or not _require(c, ("id", "move", "angle", "beats", "frames", "key_in", "key_out", "tier",
                                                       "cut_points", "passes", "clip_data", "camera_track"), where, out):
            continue
        where = "clip %s" % c["id"]
        if c["id"] != "%s__%s" % (c["move"], c["angle"]):
            out.append("%s: id must be <move>__<angle>" % where)
        if c["id"] in ids:
            out.append("%s: duplicate id" % where)
        ids.add(c["id"])
        if c["angle"] not in angle_ids:
            out.append("%s: angle %r is not in angles" % (where, c["angle"]))
        if c["beats"] not in CLIP_BEATS:
            out.append("%s: beats must be one of %s" % (where, CLIP_BEATS))
        elif ok_numbers and c["frames"] != frames_for(c["beats"], data["bpm"], data["fps"]):
            out.append("%s: frames %r, but %d beats at %g bpm and %g fps are %d" % (
                where, c["frames"], c["beats"], data["bpm"], data["fps"], frames_for(c["beats"], data["bpm"], data["fps"])))
        for k in ("key_in", "key_out"):
            if c[k] not in poses:
                out.append("%s: %s %r is not a Key Pose" % (where, k, c[k]))
        if c["tier"] not in TIERS:
            out.append("%s: tier must be one of %s" % (where, TIERS))
        cp = c["cut_points"]
        cp_ok = isinstance(cp, list) and cp and all(_is_int(v) for v in cp) and cp == sorted(set(cp)) and cp[0] == 0
        if not cp_ok or (_is_int(c["beats"]) and cp[-1] >= c["beats"]):
            out.append("%s: cut_points must be sorted, unique, start with 0 and stay inside the %r beats" % (where, c["beats"]))
        if not (isinstance(c["passes"], dict) and all(isinstance(c["passes"].get(p), str) for p in PASSES)):
            out.append("%s: passes needs a path for each of %s" % (where, ", ".join(PASSES)))
        by_move.setdefault(c["move"], []).append(c)
        if base_dir:
            files = [c["clip_data"], c["camera_track"]] + [v for v in (c["passes"] or {}).values() if isinstance(v, str)]
            for rel in files:
                if not isinstance(rel, str) or not os.path.isfile(os.path.join(base_dir, rel)):
                    out.append("%s: file missing: %s" % (where, rel))
            cd_path = os.path.join(base_dir, c["clip_data"]) if isinstance(c["clip_data"], str) else ""
            if os.path.isfile(cd_path):
                try:
                    cd = _json(cd_path)
                    if cd.get("clip") != c["id"]:
                        out.append("%s: clip data names clip %r" % (where, cd.get("clip")))
                    if len(cd.get("frames", [])) != c["frames"]:
                        out.append("%s: clip data has %d frames, the Clip %r" % (where, len(cd.get("frames", [])), c["frames"]))
                    for h in cd.get("hits", []):
                        if not (_is_int(h.get("f")) and 0 <= h["f"] < c["frames"]):
                            out.append("%s: hit outside the Clip: %r" % (where, h))
                except (ValueError, AttributeError) as e:
                    out.append("%s: clip data unreadable: %s" % (where, e))
    for move, group in by_move.items():
        for k in MOVE_SHARED:
            if len({json.dumps(g[k]) for g in group}) > 1:
                out.append("move %s: %s differs across Angles" % (move, k))
        missing = [a for a in angle_ids if a not in [g["angle"] for g in group]]
        if missing:
            out.append("move %s: no Clip for Angle %s" % (move, ", ".join(map(str, missing))))
    return out


def load(path, check_files=True):
    """Manifest of a manifest.json; raises ManifestError listing every problem."""
    base = os.path.dirname(os.path.abspath(path))
    problems = validate(_json(path), base if check_files else None)
    if problems:
        raise ManifestError(problems)
    return Manifest(_json(path), base)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(__doc__)
        return 2
    try:
        m = load(argv[0])
    except ManifestError as e:
        print("\n".join(e.problems))
        return 1
    print("ok: %d clips, %d moves, %d angles" % (len(m.clips), len(m.moves), len(m.angles)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
