"""Clip Graph: the pure model of what Magic walks (Moves joined by Key Poses, Angle cuts at Cut Points). Stdlib only.

State is (move, angle, start, tier): the Move on air, the Angle on air, the beat count at which the Move began and the Intensity
Tier. `step` is called once per beat with the running beat count and the music's section (Music X-Ray State: 2 buildup is build,
3 drop is drop, anything else calm). The tier follows the section only on a bar boundary, so a section change mid-bar waits:
- when a Move Clip has run its beats (always on a bar, since Clips are 4, 8 or 16 beats), pick the next Move among the
  non-idle Moves whose key_in equals the current key_out, in the Intensity Tier, not the current Move unless it
  is the only one; the pick comes from the bar number. With no pick the Android goes to the Idle Clip of that Key Pose;
- an Idle Clip loops (Magic does that) and is left on the next bar boundary, once it has played, into such a pick; with no pick it stays;
- at a Cut Point of the Move on air (offset in beats since its start), cut to another Angle with probability `cut_rate`.
Solo and duel (#23): a Manifest may hold duel Angles and Exchanges (Moves with the giant machine, on the duel Angles only). Picks stay
within the kind of the Move on air and cuts within the Angles of that kind. The walk wants the duel while the tier is one of `duel_tiers`
(default: drop) and solo otherwise; it changes kind only through an Idle Clip: a Move that ends goes to the Idle Clip of its key_out, which
on the next bar line hands over to the Idle Clip of the same Key Pose of the other kind (on the first Angle of that kind), which is left on
the bar after as usual. A Key Pose with no Idle Clip of the wanted kind stays in its kind.
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
    def __init__(self, manifest, seed=0, cut_rate=1.0, duel_tiers=("drop",)):
        self.manifest, self.seed = manifest, seed
        self.cut_rate = cut_rate
        self.moves = manifest.moves
        self.angles = manifest.angle_ids
        self.duel_tiers = tuple(duel_tiers) if manifest.group(True) else ()

    def wants_duel(self, tier):
        return tier in self.duel_tiers

    @staticmethod
    def tier(section):
        return "drop" if section == SECTION_DROP else "build" if section == SECTION_BUILDUP else "calm"

    def latch(self, tier, beat, section):
        """The tier after beat `beat`: it takes the section's tier on a bar boundary only."""
        return self.tier(section) if beat % 4 == 0 else tier

    def candidates(self, move, tier):
        """Names of the Move Clips that may follow `move` in `tier`: same Key Pose, current Move left out unless it is alone. May be empty."""
        cur = self.manifest.move(move)
        key = cur.key_out
        cands = [m.name for m in self.moves if not m.idle and m.key_in == key and m.tier == tier and m.opponent == cur.opponent]
        return [c for c in cands if c != move] or cands

    def exits(self, duel=False):
        """{(key pose, tier): names of the solo Moves (duel: the Exchanges) that start in that Key Pose in that tier}, every pair listed."""
        out = {(k, t): [] for k in self.manifest.key_poses for t in ("calm", "build", "drop")}
        for m in self.moves:
            if not m.idle and m.opponent == duel:
                out[(m.key_in, m.tier)].append(m.name)
        return out

    def dead_ends(self):
        """(key pose, tier) pairs with no Move to leave the pose in that tier: the walk waits in the pose's Idle Clip there until the tier changes."""
        return [k for k, v in self.exits().items() if not v]

    def pool(self, move, tier):
        """What the pick draws from: the candidates, else the Idle Clip of the Key Pose (an Idle Clip with no candidate stays).
        When the tier wants the other kind and the Key Pose has an Idle Clip of that kind: a Move goes to its own kind's Idle Clip, an Idle Clip to the other's."""
        m = self.manifest.move(move)
        want = self.wants_duel(tier)
        if want != m.opponent:
            other = self.manifest.idle_move(m.key_out, want)
            if other is not None:
                return [other] if m.idle else [self.manifest.idle_move(m.key_out, m.opponent)]
        cands = self.candidates(move, tier)
        if cands:
            return cands
        return [move if m.idle else self.manifest.idle_move(m.key_out, m.opponent)]

    def next_move(self, move, bar, tier):
        pool = self.pool(move, tier)
        return pool[min(len(pool) - 1, int(math.floor(hash01(bar, self.seed, SALT_MOVE) * len(pool))))]

    def next_angle(self, angle, beat):
        """A cut within the Angles of `angle`'s kind."""
        group = self.manifest.group(self.manifest.angle_duel(angle))
        n = len(group)
        if n < 2 or not hash01(beat, self.seed, SALT_CUT) < self.cut_rate:
            return angle
        i = group.index(angle)
        return group[(i + 1 + int(math.floor(hash01(beat, self.seed, SALT_ANGLE) * (n - 1)))) % n]

    def start(self):
        first = self.moves[0]
        return State(first.name, self.manifest.group(first.opponent)[0], 0, "calm")

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
        mv = self.manifest.move(move)
        if self.manifest.angle_duel(angle) != mv.opponent:       # the kind changed: the first Angle of the new kind
            angle = self.manifest.group(mv.opponent)[0]
        elif offset % mv.beats in mv.cut_points:
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
