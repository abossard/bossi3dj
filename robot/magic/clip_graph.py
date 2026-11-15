"""Clip Graph: the pure model of what Magic walks (Moves joined by Key Poses, Angle cuts at Cut Points). Stdlib only.

State is (move, angle, start): the Move on air, the Angle on air and the beat count at which the Move began. `step` is called
once per beat with the running beat count and the music's energy:
- when the Move has run its beats (always on a bar, since Clips are 4, 8 or 16 beats), pick the next Move among those whose
  key_in equals the current key_out, in the Intensity Tier the energy is in (any tier if that one has none), not the current
  Move unless it is the only one; the pick comes from the bar number;
- at a Cut Point of the Move on air (offset in beats since its start), cut to another Angle with probability `cut_rate`.
Picks are a hash of the beat count and the seed, so a run repeats. robot_magic.py writes the same hash and the same tables
into Magic Globals; tests/test_robot_magic.py runs those Globals beside this model.
"""
import math
from collections import namedtuple

State = namedtuple("State", "move angle start")
SALT_MOVE, SALT_CUT, SALT_ANGLE = 0, 1, 2


def hash01(n, seed, salt):
    """Deterministic value in [0, 1) from a count and the seed. Same formula in Magic: x - floor(x) of sin(...) x 43758.5453."""
    v = math.sin(n * 12.9898 + seed * 78.233 + salt * 37.719) * 43758.5453
    return v - math.floor(v)


class ClipGraph:
    def __init__(self, manifest, seed=0, tier_build=0.25, tier_drop=0.55, cut_rate=1.0):
        self.manifest, self.seed = manifest, seed
        self.tier_build, self.tier_drop, self.cut_rate = tier_build, tier_drop, cut_rate
        self.moves = manifest.moves
        self.angles = manifest.angle_ids

    def tier(self, energy):
        return "calm" if energy < self.tier_build else "build" if energy < self.tier_drop else "drop"

    def candidates(self, move, tier):
        """Names of the Moves that may follow `move` in `tier`: same Key Pose, current Move left out unless it is alone."""
        key = self.manifest.move(move).key_out
        fits = [m for m in self.moves if m.key_in == key]
        cands = [m.name for m in fits if m.tier == tier] or [m.name for m in fits]
        return [c for c in cands if c != move] or cands

    def next_move(self, move, bar, tier):
        cands = self.candidates(move, tier)
        return cands[min(len(cands) - 1, int(math.floor(hash01(bar, self.seed, SALT_MOVE) * len(cands))))] if cands else move

    def next_angle(self, angle, beat):
        n = len(self.angles)
        if n < 2 or not hash01(beat, self.seed, SALT_CUT) < self.cut_rate:
            return angle
        i = self.angles.index(angle)
        return self.angles[(i + 1 + int(math.floor(hash01(beat, self.seed, SALT_ANGLE) * (n - 1)))) % n]

    def start(self):
        return State(self.moves[0].name, self.angles[0], 0)

    def step(self, state, beat, energy):
        move, angle, start = state
        offset = beat - start
        if offset >= self.manifest.move(move).beats:
            move, start, offset = self.next_move(move, beat // 4, self.tier(energy)), beat, 0
        if offset in self.manifest.move(move).cut_points:
            angle = self.next_angle(angle, beat)
        return State(move, angle, start)

    def walk(self, energies):
        """States after beats 1..len(energies), one energy per beat; the state before is `start()`."""
        out, s = [], self.start()
        for beat, e in enumerate(energies, 1):
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
        return min(m.move(state.move).frames - 1, int(math.floor((beat - state.start + phase) * per_beat)))
