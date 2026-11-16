# Blends keep land in frame (issue #25), hand-over 2026-11-16

## State

- Committed 158d3c1: `BLEND_LAND` keep, `BLEND_BY_HEIGHT` fog, `SKY_FRAME` variant (off). Its independent review (orchestrator, 2026-11-16) found 3 high, 2 medium, 2 low; #25 stays open, `SKY_FRAME` waits for the user.
- Uncommitted in `blender/scenes/path_camera.py` (working tree): a rework of the keep toward the reviewer's "plain rule". Not committed because item 5 below got worse.
- The reviewer's replay scripts are in `blender/review/issue25_review/` (`sim.py` helpers; `a.py` fall from space, change mid-blend, cut mid-blend; `b.py SEED near|far FADE SECONDS` random programs; `c.py` old vs new on eight hard cases). Run from the repo root: `python3 blender/review/issue25_review/c.py`.

## The rework (uncommitted)

- No rate-limited weight: while the Director blends, weight `k` = the lesser of an ease-in and an ease-out, each the greater of the blend's share (`BLEND_LAND_EASE[0]` 0.25) and the eye's log height over that end's eye (`BLEND_LAND_EASE[1]` 1 e-fold), so falls from a higher start are covered and `k` is 0 at both ends.
- The kept view is written back into `Director.pose`, so a change mid-blend starts from the view shown.
- After the Director ends while `banded()` still holds the eye, the keep goes out with height alone, with the last blend's ends.
- The heading comes from the view plus 0.25 x the sum of the end shots' forwards.
- `turn_limited()`: the shown view turns no faster than the view before the keep did plus `BLEND_LAND_TURN` (10 deg/s); a cut resets it.
- The beat's accent now goes on after the keep (`en.accent` in `PathCamera.step`; the Director is stepped without the drive), so the dip is no longer swallowed (review item 7).

## Numbers (working tree)

| check | 158d3c1 | rework |
|---|---|---|
| `a.py` fall from space (vantage planet h 1 -> orbit river): blend s with land < 0.1, max turn | 5.6 s (review) | 0.0 s, 19.7 deg/s |
| `a.py` change mid-blend (coast -> sun -> rise lake): land < 0.1 | about 8 s (review) | 0.0 s |
| `a.py` cut mid-blend: off the live view the frame after | 53 deg (review) | 0 |
| `verify_paths.py` 2c change turn (limit 72) | 67.6 | 71.6 |
| `verify_paths.py` 1b | fails (2.818, as before #25) | same |
| `blend_horizon.py` demo replay: blend s with land < 0.1 | 1.9 | 1.5 |
| `c.py` view off the live shot at a blend's end | up to 81 deg (review) | up to 91 deg |

## Open

1. **The end of a blend (review item 5)**: with the turn limit the shown view still lags the live shot by up to 91 deg when the blend ends (c.py cases 2, 5, 6) and then catches up at 10 deg/s over seconds. The keep needs an end condition that is met by the Director's end: e.g. bring `k` out early enough that the kept view's gap closes within the turn budget (a duration-aware ease-out: the remaining time x budget >= the gap), or let the Director's duration include the keep's turn (needs the Director's `duration()`, shared with other scenes).
2. `c.py` case 3 (vantage coast -> vantage river, rise pyramids at 4.7 s, far): 155 deg/s on the change frame; not traced.
3. The 6 s fades (`c.py` last two) exceed 72 deg/s, but so does 158d3c1's base (178.8, 96.2); their own limit is 60 x PACE = 360.
4. Add the reviewer's scenarios to `verify_paths.py` (mid-blend change, a fall from higher, a cut during a blend, far targets about 24 km, 6 s blends) and a "view on the live shot at the blend's end" check (review item 6).
5. Live: 5 s of flat frames in orbit river and 4 s in rise lake at 4 to 7 km remain even with land in frame (`out/issue25/live_after.jsonl`): the land renders flat from there (shader side).

## Commands

```bash
python3 blender/review/verify_paths.py
python3 blender/review/blend_horizon.py
python3 blender/review/issue25_review/a.py
python3 blender/review/issue25_review/c.py
```

Live: `blender/review/blend_live.py` (the demo program held against Magic, see its docstring), recordings with music `blender/review/sky_frame_record.sh`.
