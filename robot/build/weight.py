"""Weight: physical layers on a key table's Pose sequence, applied by `moves.frames()` (#31,
docs/research/weighted-animation.md section 4, steps 1, 3 and 4). Pure, no bpy.

- Hit-stop: the Clip holds still for round(1 + 2·strength) frames from each Hit frame, then plays faster until the
  next beat, so the next beat still lands on its frame (`time_warp`). An Exchange's two fighters share one warp.
- Ballistic flight: while both feet are off the floor the hips follow a parabola under g through the take-off and
  touch-down frames; hands and feet move with them, so the body keeps its keyed shape (`ballistic`).
- Recoil: after the hold, the striking limb springs back along its approach and the hips take a smaller reaction
  (a damped sine, `recoil`).
- Landing dip: at a touch-down after flight and at a stomp the hips and hands sink and spring back (`dip`).
Recoils and dips fade out over the Clip's last END_FRAMES frames, so its last frame is still its Key Pose, and the
hips give way where a planted leg would no longer reach its foot.

`measure()` is the research's check: hips acceleration in flight against -g and the ground force per kilogram from
an estimated centre of mass (the floor pushes, never pulls; no skating).

    python3 robot/build/weight.py      (prints the check per Move, key tables before and after weight)
"""
import bisect
import math

G = 9.81
FPS = 30
ANKLE_Z = 0.10
AIR_M = 1e-6               # both feet above ANKLE_Z by more than this: in flight
END_FRAMES = 10
RECOIL = {"limb": (0.04, 5.0, 0.35), "hips": (0.02, 3.0, 0.5)}     # amplitude per strength (m), Hz, damping
DIP = (3.0, 0.5)                                                   # Hz, damping
DIP_M = (0.0, 0.06)
HAND_FLOOR_M = (0.15, 0.45)    # a hand this low takes none of the dip, this high all of it
MU = 0.8


def hold_frames(strength):
    return int(round(1 + 2 * strength))


def _catch_up(h, b, out0, speeds):
    """Output frame per source frame h..b, from out0 at h to b at b: each source frame takes output time in
    proportion to its speed plus a floor (the mean speed), so the catch-up hurries more where the key table is slow
    and keeps fast motion near its pace."""
    v = speeds[h:b] if speeds else [1.0] * (b - h)
    floor = 1.0 * (sum(v) / len(v)) + 1e-9
    cost = [x + floor for x in v]
    k = (b - out0) / sum(cost)
    t = [float(out0)]
    for c in cost:
        t.append(t[-1] + c * k)
    return t


def time_warp(n, stops, beat_frames, speeds=None):
    """Source frame (float) per output frame for a Clip of n frames. `stops`: [(hit frame, strength)];
    `beat_frames`: the frames of the beats; `speeds`: the key table's largest position change from each frame to
    the next. After a hold the catch-up ends at the next beat (or the next stop) that leaves at least 2 frames to
    catch up in; a stop with no such beat is skipped."""
    s = [float(f) for f in range(n)]
    stops = sorted(stops)
    marks = sorted(set(beat_frames) | {h for h, _ in stops} | {n - 1})
    for i, (h, strength) in enumerate(stops):
        hold = hold_frames(strength)
        nxt = stops[i + 1][0] if i + 1 < len(stops) else n - 1
        b = next((m for m in marks if h + hold + 2 <= m <= nxt), None)
        if b is None:
            continue
        t = _catch_up(h, b, h + hold, speeds)
        for f in range(h, b + 1):
            if f <= h + hold:
                s[f] = float(h)
                continue
            j = min(max(bisect.bisect_right(t, f) - 1, 0), len(t) - 2)
            s[f] = min(h + j + (f - t[j]) / (t[j + 1] - t[j]), float(b))
        s[b] = float(b)
    return s


def speeds(seq):
    """The largest position change of any channel from each frame to the next (rotations left out)."""
    return [max(math.dist(a[c], b[c]) for c in a if not c.endswith("_rot")) for a, b in zip(seq, seq[1:])]


def flights(seq):
    """[(take-off, touch-down)]: the frames around each run with both feet in the air."""
    air = [p["foot_l"][2] > ANKLE_Z + AIR_M and p["foot_r"][2] > ANKLE_Z + AIR_M for p in seq]
    out, f = [], 1
    while f < len(seq):
        if air[f] and not air[f - 1]:
            g = f
            while g < len(seq) and air[g]:
                g += 1
            if g < len(seq):
                out.append((f - 1, g))
            f = g
        f += 1
    return out


def _add(p, ch, d, w=1.0):
    p[ch] = tuple(a + b * w for a, b in zip(p[ch], d))


def arcs(seq, pins):
    """[(start, end)] of ballistic hips: each flight cut at pinned frames (a contact or a dodge in the air holds its
    keyed place; the contact's impulse changes the arc)."""
    out = []
    for t0, t1 in flights(seq):
        cuts = [t0] + sorted(p for p in set(pins) if t0 < p < t1) + [t1]
        out += [(a, b) for a, b in zip(cuts, cuts[1:]) if b - a >= 2]
    return out


def ballistic(seq, pins=()):
    for t0, t1 in arcs(seq, pins):
        T = (t1 - t0) / FPS
        h0, h1 = seq[t0]["hips"], seq[t1]["hips"]
        for f in range(t0 + 1, t1):
            tau = (f - t0) / FPS
            k = tau / T
            want = (h0[0] + (h1[0] - h0[0]) * k, h0[1] + (h1[1] - h0[1]) * k,
                     h0[2] + (h1[2] - h0[2]) * k + 0.5 * G * tau * (T - tau))
            d = tuple(a - b for a, b in zip(want, seq[f]["hips"]))
            for ch in ("hips", "hand_l", "hand_r", "foot_l", "foot_r"):
                _add(seq[f], ch, d)
            for ch in ("foot_l", "foot_r"):
                x, y, z = seq[f][ch]
                seq[f][ch] = (x, y, max(z, ANKLE_Z + 2 * AIR_M))


def _spring(t, amp, hz, zeta):
    w = 2 * math.pi * hz
    return amp * math.exp(-zeta * w * t) * math.sin(w * math.sqrt(1 - zeta * zeta) * t)


def _unit(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v) if n > 1e-9 else (0.0, 0.0, 0.0)


def recoil(seq, raw_at, stops):
    """Per stop (frame, limb, strength): after the hold the limb springs back along -u, u the limb's direction into
    the contact in the key table (`raw_at(frame)` gives the unwarped Pose); the hips take a smaller, level reaction.
    Returns the offsets [(frame, channel, (dx, dy, dz))]."""
    out = []
    for h, limb, strength in stops:
        if limb not in seq[0] or limb.startswith("foot") or limb == "head":
            continue
        a, b = raw_at(h - 1)[limb], raw_at(h)[limb]
        u = _unit(tuple(y - x for x, y in zip(a, b)))
        uh = _unit((u[0], u[1], 0.0))
        start = h + hold_frames(strength)
        for f in range(start + 1, len(seq)):
            t = (f - start) / FPS
            for ch, uu, key in ((limb, u, "limb"), ("hips", uh, "hips")):
                amp, hz, zeta = RECOIL[key]
                d = -_spring(t, amp * strength, hz, zeta)
                out.append((f, ch, tuple(c * d for c in uu)))
    return out


def dip(seq, raw_at, stops, landings=True):
    """Hips and hands keep sinking after each touch-down from flight and each stomp (a foot Hit, after its hold) and
    spring back: a damped sine that starts at the hips' falling speed there (at most DIP_M deep), so the legs take
    the fall instead of stopping it. `landings` False: stomps only (a capture lands by itself). Returns the offsets [(frame, channel, (0, 0, dz))]."""
    w_d = 2 * math.pi * DIP[0] * math.sqrt(1 - DIP[1] ** 2)
    events = [(t1, (seq[t1 - 1]["hips"][2] - seq[t1]["hips"][2]) * FPS) for _t0, t1 in flights(seq)] if landings else []
    events += [(h + hold_frames(st), (raw_at(h - 1)["hips"][2] - raw_at(h)["hips"][2]) * FPS)
               for h, limb, st in stops if limb.startswith("foot")]
    out = []
    for start, fall in events:
        amp = min(max(fall, 0.0) / w_d, DIP_M[1])
        if amp < 0.005:
            continue
        for f in range(start + 1, len(seq)):
            dz = -_spring((f - start) / FPS, amp, *DIP)
            out.append((f, "hips", (0.0, 0.0, dz)))
            for hand in ("hand_l", "hand_r"):
                z = seq[f][hand][2]
                w = min(max((z - HAND_FLOOR_M[0]) / (HAND_FLOOR_M[1] - HAND_FLOOR_M[0]), 0.0), 1.0)
                out.append((f, hand, (0.0, 0.0, dz * w)))
    return out


def _end_weight(f, n):
    d = n - 1 - f
    return 1.0 if d >= END_FRAMES else 0.5 * (1 - math.cos(math.pi * d / END_FRAMES))


def _reach_ok(p, hip_joint, leg_m):
    return all(math.dist(hip_joint(p, s), p["foot_" + s]) <= leg_m
               for s in ("l", "r") if p["foot_" + s][2] <= ANKLE_Z + AIR_M)


def apply_offsets(seq, offsets, hip_joint, leg_m):
    """Add offsets, faded out at the Clip's end; where the hips would leave a planted foot out of reach they move
    back toward their keyed place, in quarters."""
    by_frame = {}
    for f, ch, d in offsets:
        by_frame.setdefault(f, []).append((ch, d))
    n = len(seq)
    for f, items in by_frame.items():
        w = _end_weight(f, n)
        if w == 0.0:
            continue
        base = dict(seq[f])
        for k in (1.0, 0.75, 0.5, 0.25, 0.0):
            p = dict(base)
            for ch, d in items:
                _add(p, ch, d, w * (k if ch == "hips" else 1.0))
            if k == 0.0 or _reach_ok(p, hip_joint, leg_m):
                break
        seq[f] = p


def pins(stops, dodges=()):
    """Frames whose keyed pose holds in the air: each Hit and its hold, each Dodge."""
    return sorted({f for h, _l, s in stops for f in range(h, h + hold_frames(s) + 1)} | set(dodges))


def weigh(sample, n, stops, beat_frames, hip_joint, leg_m, warp=None, dodges=()):
    """The weighted Pose sequence. `sample(frame)` gives the key table's Pose at a (fractional) frame; `stops`:
    [(frame, limb, strength)] of the Hits; `warp` overrides the time warp (an Exchange shares one); `dodges`: frames
    whose keyed pose must hold."""
    if warp is None:
        warp = time_warp(n, [(h, s) for h, _l, s in stops], beat_frames, speeds([sample(f) for f in range(n)]))
    seq = [sample(s) for s in warp]
    if "hips" not in seq[0]:
        return seq
    ballistic(seq, pins(stops, dodges))
    apply_offsets(seq, recoil(seq, sample, stops) + dip(seq, sample, stops), hip_joint, leg_m)
    return seq


def centre_of_mass(p, hip_joint):
    """Estimate from the channels (research 2.4): trunk 0.70, arms 0.05 each split hand and shoulder, legs 0.16 each
    split hip joint and ankle."""
    hx, hy, hz = p["hips"]
    c = [0.70 * hx, 0.70 * hy, 0.70 * (hz + 0.25)]
    for hand, sx in (("hand_l", 0.14), ("hand_r", -0.14)):
        for i, v in enumerate(p[hand]):
            c[i] += 0.025 * v
        for i, v in enumerate((hx + sx, hy, hz + 0.45)):
            c[i] += 0.025 * v
    for s in ("l", "r"):
        for i, (a, b) in enumerate(zip(hip_joint(p, s), p["foot_" + s])):
            c[i] += 0.16 * (0.6 * a + 0.4 * b)
    return tuple(c)


def measure(seq, hip_joint, pinned=()):
    """The research's check on a Pose sequence: hips z acceleration in flight (m/s², ballistic is -9.81; frames on
    an arc between pins) and, with a foot planted, the smallest vertical ground force per kg and the largest
    friction it would need (|F_xy| / F_z)."""
    air = [f for t0, t1 in arcs(seq, pinned) for f in range(t0 + 1, t1)]
    flying = {f for t0, t1 in flights(seq) for f in range(t0, t1 + 1)}
    acc = lambda xs, f: (xs[f + 1] - 2 * xs[f] + xs[f - 1]) * FPS * FPS  # noqa: E731
    hz = [p["hips"][2] for p in seq]
    com = [centre_of_mass(p, hip_joint) for p in seq]
    air_acc = [acc(hz, f) for f in air]
    ground = [f for f in range(1, len(seq) - 1) if f not in flying]
    fz = [acc([c[2] for c in com], f) + G for f in ground]
    fxy = [math.hypot(acc([c[0] for c in com], f), acc([c[1] for c in com], f)) for f in ground]
    return {"air_acc": (min(air_acc), max(air_acc)) if air_acc else None,
            "min_fz": min(fz) if fz else None,
            "max_friction": max((a / b if b > 0 else math.inf) for a, b in zip(fxy, fz)) if fz else None}


if __name__ == "__main__":
    import moves
    for name, move in moves.MOVES.items():
        before = measure(moves.frames(move, weighted=False), moves.hip_joint)
        after = measure(moves.frames(move), moves.hip_joint, pins(moves.stops(move)))
        fmt = lambda m: "air %s  min Fz %6.1f  friction %5.2f" % (  # noqa: E731
            "%6.1f..%6.1f" % m["air_acc"] if m["air_acc"] else "      -       ", m["min_fz"], m["max_friction"])
        print("%-16s before: %s | after: %s" % (name, fmt(before), fmt(after)))
