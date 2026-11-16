"""Clip Graph: the pure model of what Magic walks (Moves joined by Key Poses, Angle cuts at Cut Points). Stdlib only.

State is (move, angle, start, tier): the Move on air, the Angle on air, the beat count at which the Move began and the Intensity
Tier. `step` is called once per beat with the running beat count and the music's section (Music X-Ray State: 2 buildup is build,
3 drop is drop, anything else calm). The tier follows the section only on a bar boundary, so a section change mid-bar waits:
- when a Move Clip has run its beats (always on a bar, since Clips are 4, 8 or 16 beats), pick the next Move among the
  non-idle Moves whose key_in equals the current key_out, in the Intensity Tier, not the current Move unless it
  is the only one; the pick comes from the bar number. With no pick the Android goes to the Idle Clip of that Key Pose;
- an Idle Clip loops (Magic does that) and is left on the next bar boundary, once it has played, into such a pick; with no pick it stays;
- at a Cut Point of the Move on air (offset in beats since its start), cut to another Angle with probability `cut_rate`.
Picks are a hash of the beat count and the seed, so a run repeats. robot_magic.py writes the same hash and the same tables
into Magic Globals; tests/test_robot_magic.py runs those Globals beside this model.
"""
import math
from collections import namedtuple

State = namedtuple("State", "move angle start tier", defaults=("calm",))
SALT_MOVE, SALT_CUT, SALT_ANGLE = 0, 1, 2
SECTION_BUILDUP, SECTION_DROP = 2, 3      # Music X-Ray State: 0 intro, 2 buildup, 3 drop, 4 breakdown; everything else is calm


def hash01(n, seed, salt):
    """Deterministic value in [0, 1) from a count and the seed. Same formula in Magic: x - floor(x) of sin(...) x 43758.5453."""
    v = math.sin(n * 12.9898 + seed * 78.233 + salt * 37.719) * 43758.5453
    return v - math.floor(v)


class ClipGraph:
    def __init__(self, manifest, seed=0, cut_rate=1.0):
        self.manifest, self.seed = manifest, seed
        self.cut_rate = cut_rate
        self.moves = manifest.moves
        self.angles = manifest.angle_ids

    @staticmethod
    def tier(section):
        return "drop" if section == SECTION_DROP else "build" if section == SECTION_BUILDUP else "calm"

    def latch(self, tier, beat, section):
        """The tier after beat `beat`: it takes the section's tier on a bar boundary only."""
        return self.tier(section) if beat % 4 == 0 else tier

    def candidates(self, move, tier):
        """Names of the Move Clips that may follow `move` in `tier`: same Key Pose, current Move left out unless it is alone. May be empty."""
        key = self.manifest.move(move).key_out
        cands = [m.name for m in self.moves if not m.idle and m.key_in == key and m.tier == tier]
        return [c for c in cands if c != move] or cands

    def pool(self, move, tier):
        """What the pick draws from: the candidates, else the Idle Clip of the Key Pose (an Idle Clip with no candidate stays)."""
        cands = self.candidates(move, tier)
        if cands:
            return cands
        m = self.manifest.move(move)
        return [move if m.idle else self.manifest.idle_move(m.key_out)]

    def next_move(self, move, bar, tier):
        pool = self.pool(move, tier)
        return pool[min(len(pool) - 1, int(math.floor(hash01(bar, self.seed, SALT_MOVE) * len(pool))))]

    def next_angle(self, angle, beat):
        n = len(self.angles)
        if n < 2 or not hash01(beat, self.seed, SALT_CUT) < self.cut_rate:
            return angle
        i = self.angles.index(angle)
        return self.angles[(i + 1 + int(math.floor(hash01(beat, self.seed, SALT_ANGLE) * (n - 1)))) % n]

    def start(self):
        return State(self.moves[0].name, self.angles[0], 0, "calm")

    def step(self, state, beat, section):
        move, angle, start, _tier = state
        tier = self.latch(state.tier, beat, section)
        offset = beat - start
        m = self.manifest.move(move)
        if m.idle:
            leave = beat % 4 == 0 and offset > 0 and self.next_move(move, beat // 4, tier) != move
        else:
            leave = offset >= m.beats
        if leave:
            move, start, offset = self.next_move(move, beat // 4, tier), beat, 0
        if offset % self.manifest.move(move).beats in self.manifest.move(move).cut_points:
            angle = self.next_angle(angle, beat)
        return State(move, angle, start, tier)

    def walk(self, sections):
        """States after beats 1..len(sections), one section per beat; the state before is `start()`."""
        out, s = [], self.start()
        for beat, e in enumerate(sections, 1):
            s = self.step(s, beat, e)
            out.append(s)
        return out

    def clip_index(self, state):
        """Value of /vj/clip for a state."""
        return self.manifest.clip_index(state.move, state.angle)

    def frame(self, state, beat, phase=0.0):
        """Value of /vj/clip_frame: Magic's count from the Clip's start, at beat count `beat` plus a beat fraction."""
        m = self.manifest
        per_beat = m.fps * 60.0 / m.bpm
        mv, f = m.move(state.move), int(math.floor((beat - state.start + phase) * per_beat))
        return f % mv.frames if mv.idle else min(mv.frames - 1, f)
