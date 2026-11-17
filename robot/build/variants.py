"""Variants (#32): extra Moves in a base Move's family (`variant_of`, robot/CONTRACTS.md), so Magic never loops one
Clip. Pure, no bpy; moves.py adds them to MOVES.

- Idle families: per Key Pose, IDLE_FAMILIES gives one-bar Idle variants. Each is its Key Pose with a captured
  idle's micro-motion on top (breathing, sway, glances from robot/build/tracks/, extract_tracks.py): a window of the
  capture, detrended so it starts and ends at the Key Pose and faded in and out over EDGE frames, so any variant
  chains into any other.
- Move takes: MOVE_TAKES gives seeds for a Move's extra takes. A take moves the keys that are neither an end nor a
  Hit by up to a frame, scales its Hit strengths (so its hit-stop holds differ) and gets weight.py's seeded layer.
Every variant carries a seed; weight.py's seeded layer (breathing, weight shift, glances, hand height) is drawn from
it, so a variant renders the same every build.
"""
import json
import math
import os
import random

import moves
from moves import Hit, Key, Move

TRACKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tracks")
TRACK_CHANNELS = ("hips", "hips_rot", "spine_rot", "chest_rot", "head_rot")
EDGE = 8
# Key Pose: [(track, first source frame, scale, seed)], named idle_<pose>_v2 and on
IDLE_FAMILIES = {
    "guard": [("breathing_idle", 0, 1.5, 21), ("breathing_idle", 80, 1.5, 22), ("breathing_idle", 160, 1.5, 23),
              ("relaxed_idle", 40, 1.2, 24)],
    "low": [("relaxed_idle", 0, 1.3, 31), ("relaxed_idle", 70, 1.3, 32), ("relaxed_idle", 140, 1.3, 33),
            ("breathing_idle", 220, 1.3, 34)],
    "crouch": [("crouched_idle", 0, 1.5, 41), ("crouched_idle", 10, 1.5, 42), ("crouched_idle", 19, 1.5, 43),
               ("breathing_idle", 120, 1.0, 44)],
}
MOVE_TAKES = {"jab_cross": (2, 3)}
HIT_SCALE = (0.6, 0.8, 1.0)
_cache = {}


def _track(name):
    if name not in _cache:
        with open(os.path.join(TRACKS, name + ".json")) as fh:
            _cache[name] = json.load(fh)["frames"]
    return _cache[name]


def _at(frames, s, ch):
    i = min(int(s), len(frames) - 2)
    t = s - i
    return [a + (b - a) * t for a, b in zip(frames[i][ch], frames[i + 1][ch])]


def _wrap(d):
    return (d + 180.0) % 360.0 - 180.0


def track_offsets(move, frame, bpm=moves.BPM, fps=moves.FPS):
    """{channel: offset} of a tracked Move at `frame`: the capture window's change since its first frame, detrended
    to 0 at the last frame, scaled, faded over EDGE frames at both ends."""
    name, start, scale = move.track
    fr = _track(name)
    n = moves.move_frames(move, bpm, fps)
    k = frame / (n - 1)
    edge = moves._smoothstep(min(max(min(frame, n - 1 - frame) / EDGE, 0.0), 1.0))
    out = {}
    for ch in TRACK_CHANNELS:
        a, b, x = fr[start][ch], fr[start + n - 1][ch], _at(fr, start + frame, ch)
        diff = (lambda p, q: _wrap(p - q)) if ch.endswith("_rot") else (lambda p, q: p - q)
        out[ch] = tuple(scale * edge * (diff(xi, ai) - diff(bi, ai) * k) for xi, ai, bi in zip(x, a, b))
    return out


def _idle_variants():
    out = []
    for key, takes in IDLE_FAMILIES.items():
        pose = moves.KEY_POSES[key]
        for i, (track, start, scale, seed) in enumerate(takes):
            out.append(Move("idle_%s_v%d" % (key, i + 2), "calm", moves.BEATS, key, key,
                            [Key(0, pose), Key(moves.BEATS, pose)], [], True, (), "idle_" + key, seed,
                            (track, start, scale)))
    return out


def take(base, seed):
    """A take of `base`: inner keys shifted by up to a frame (never past a neighbour), Hit strengths scaled."""
    rnd = random.Random(seed)
    fpb = moves.frames_per_beat()
    hit_beats = {h.beat for h in base.hits}
    keys = list(base.keys)
    for i in range(1, len(keys) - 1):
        k = keys[i]
        if k.beat in hit_beats:
            continue
        beat = k.beat + rnd.choice((-1, 0, 1)) / fpb
        if keys[i - 1].beat < beat < keys[i + 1].beat:
            keys[i] = k._replace(beat=beat)
    scale = rnd.choice(HIT_SCALE)
    hits = [Hit(h.beat, h.limb, round(h.strength * scale, 3)) for h in base.hits]
    return base._replace(name="%s_v%d" % (base.name, seed), keys=keys, hits=hits, variant_of=base.name, seed=seed)


def all_variants(bases):
    """The variants, in family order, for the base Moves `bases` (name -> Move)."""
    return _idle_variants() + [take(bases[name], s) for name, seeds in MOVE_TAKES.items() for s in seeds]


def seeded_waves(seed, n):
    """weight.py's seeded layer for a variant of n frames: [(channel, axis, amplitude, harmonic)], each a
    (1 - cos) wave over the Clip, 0 with zero speed at both ends."""
    rnd = random.Random(seed * 7919)
    bars = max(1, round(n / moves.clip_frames()))
    return [("chest_rot", 0, rnd.uniform(1.0, 2.5), bars * rnd.choice((1, 2))),       # breathing
            ("hips", 0, rnd.uniform(-0.015, 0.015), bars),                             # weight shift
            ("head_rot", 1, rnd.uniform(-5.0, 5.0), bars * rnd.choice((1, 2, 3))),    # glance
            ("hand_l", 2, rnd.uniform(-0.02, 0.02), bars * rnd.choice((1, 2))),       # hand height
            ("hand_r", 2, rnd.uniform(-0.02, 0.02), bars * rnd.choice((1, 2)))]


def wave(amplitude, harmonic, frame, n):
    return amplitude * 0.5 * (1.0 - math.cos(2.0 * math.pi * harmonic * frame / (n - 1)))
