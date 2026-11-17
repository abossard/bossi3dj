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
MOVE_SHARED = ("beats", "frames", "key_in", "key_out", "tier", "cut_points", "idle")
GIANT_POINTS = ("g_head", "g_core", "g_hammer", "g_claw", "g_knee_l", "g_knee_r", "g_foot_l", "g_foot_r")    # the giant machine's points, in an Exchange only
POINTS = ("head", "eye_l", "eye_r", "hand_l", "hand_r", "foot_l", "foot_r")
TARGETS = POINTS + GIANT_POINTS + ("floor",)


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
        self.opponent = clip.get("opponent") is True        # an Exchange: plays on the duel Angles
        self.family = clip.get("variant_of") or name         # a variant's family is its base Move; a base is its own family


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

    def angle_duel(self, angle_id):
        """True for a duel Angle (both fighters in the frame)."""
        return next(a.get("opponent") is True for a in self.angles if a["id"] == angle_id)

    def group(self, duel):
        """The Angle ids of one kind, in Manifest order: the duel Angles or the solo Angles."""
        return [a["id"] for a in self.angles if (a.get("opponent") is True) == duel]

    def move(self, name):
        return next(m for m in self.moves if m.name == name)

    def idle_move(self, key_pose, duel=False):
        """Name of the Idle Clip's Move of a Key Pose on the solo Angles (duel: on the duel Angles, None when there is none)."""
        return next((m.name for m in self.moves if m.idle and m.key_in == key_pose and m.opponent == duel), None)

    def idle_family(self, key_pose, duel=False):
        """Names of the Idle Clip's Move of a Key Pose and its variants, in Manifest order; empty when there is none."""
        return [m.name for m in self.moves if m.idle and m.key_in == key_pose and m.opponent == duel]

    @property
    def families(self):
        """Family names (base Moves) in Manifest order."""
        out = []
        for m in self.moves:
            if m.family not in out:
                out.append(m.family)
        return out

    def variants(self, family):
        """Names of the Moves of a family, the base first when it comes first in the Manifest."""
        return [m.name for m in self.moves if m.family == family]

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
                if not isinstance(a.get("opponent", False), bool):
                    out.append("angles[%d]: opponent must be true or false" % i)
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
                                                       "idle", "cut_points", "passes", "clip_data", "camera_track"), where, out):
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
        if not isinstance(c.get("opponent", False), bool):
            out.append("%s: opponent must be true or false" % where)
        if not isinstance(c["idle"], bool):
            out.append("%s: idle must be true or false" % where)
        elif c["idle"] and c["key_in"] != c["key_out"]:
            out.append("%s: an Idle Clip needs key_in equal to key_out" % where)
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
                    exchange = c.get("opponent") is True
                    if exchange:
                        bad = next(((e.get("f"), p) for e in cd.get("frames", []) for p in GIANT_POINTS
                                    if not (isinstance(e.get(p), list) and len(e[p]) == 3 and all(isinstance(v, (int, float)) for v in e[p]))), None)
                        if bad:
                            out.append("%s: an Exchange needs the giant's points in every frame: frame %r lacks %s" % (where, bad[0], bad[1]))
                    for h in cd.get("hits", []):
                        if not (_is_int(h.get("f")) and 0 <= h["f"] < c["frames"]):
                            out.append("%s: hit outside the Clip: %r" % (where, h))
                        if "target" in h and h["target"] not in TARGETS:
                            out.append("%s: hit target %r is not a point or floor" % (where, h["target"]))
                        giant = [k for k in ("limb", "target") if h.get(k) in GIANT_POINTS]
                        if giant and not exchange:
                            out.append("%s: hit %s %r is the giant's, but the Clip is not an Exchange (opponent)" % (where, giant[0], h[giant[0]]))
                except (ValueError, AttributeError) as e:
                    out.append("%s: clip data unreadable: %s" % (where, e))
    duel_angle = {a["id"]: a.get("opponent") is True for a in angles if isinstance(a, dict) and "id" in a} if isinstance(angles, list) else {}
    idles, touched = {}, {}
    for group in by_move.values():
        for g in group:
            touched.setdefault(g["angle"], set()).update((g["key_in"], g["key_out"]))
            if g["idle"] is True:
                idles.setdefault((g["key_in"], g["angle"]), set()).add(g.get("variant_of") or g["move"])
    for a in angle_ids:     # a solo Angle: every Key Pose; a duel Angle: the Key Poses its Clips start or end in
        for pose in (poses if not duel_angle.get(a) else [p for p in poses if p in touched.get(a, ())]):
            found = idles.get((pose, a), set())
            if len(found) != 1:
                out.append("Key Pose %s, Angle %s: %d Idle Clips (variants count as their base), exactly one needed" % (pose, a, len(found)))
    for move, group in by_move.items():      # a variant: its own Move in its base's family, the same way in and out
        bases = {json.dumps(g.get("variant_of")) for g in group}
        if len(bases) > 1:
            out.append("move %s: variant_of differs across Angles" % move)
            continue
        base = group[0].get("variant_of")
        if base is None:
            continue
        if not isinstance(base, str) or base not in by_move or base == move:
            out.append("move %s: variant_of %r is not another Move" % (move, base))
        elif by_move[base][0].get("variant_of") is not None:
            out.append("move %s: variant_of %r is itself a variant; name the base Move" % (move, base))
        else:
            shared = lambda g, k: g.get(k) is True if k == "opponent" else g.get(k)
            for k in ("key_in", "key_out", "tier", "idle", "opponent"):
                if shared(group[0], k) != shared(by_move[base][0], k):
                    out.append("move %s: %s differs from its base Move %s" % (move, k, base))
    for move, group in by_move.items():
        if len({g.get("opponent", False) is True for g in group}) > 1:
            out.append("move %s: opponent differs across Angles" % move)
        for k in MOVE_SHARED:
            if len({json.dumps(g[k]) for g in group}) > 1:
                out.append("move %s: %s differs across Angles" % (move, k))
        kind = group[0].get("opponent") is True       # a Move covers exactly the Angles of its kind
        have = [g["angle"] for g in group]
        missing = [a for a in angle_ids if duel_angle.get(a) == kind and a not in have]
        if missing:
            out.append("move %s: no Clip for Angle %s" % (move, ", ".join(map(str, missing))))
        wrong = [a for a in have if a in duel_angle and duel_angle[a] != kind]
        if wrong:
            out.append("move %s: %s on the %s Angle %s" % (move, "an Exchange" if kind else "a solo Move", "solo" if kind else "duel", ", ".join(map(str, wrong))))
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
