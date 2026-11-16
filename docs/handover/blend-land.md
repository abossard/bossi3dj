# Blends keep land in frame (issue #25), hand-over 2026-11-16

## State

- 158d3c1 had review findings (3 high, 2 medium, 2 low). The rework in `path_camera.py` answers 1 to 5 and 7; `SKY_FRAME` (off) still waits for the user.
- The reviewer's replay scripts: `blender/review/issue25_review/` (`a.py`, `b.py`, `c.py`). Their cases run in `make test`: `blender/tests/test_path_blends.py`.

## The keep, as built

- While the Director blends, weight `k` = the lesser of an ease-in and an ease-out, each the greater of the blend's share (`BLEND_LAND_EASE[0]` 0.25) and the eye's log height over that end's eye (`BLEND_LAND_EASE[1]` 1 e-fold); 0 at both ends. A fall from a higher start is covered.
- The turn toward the kept view is at most `BLEND_LAND_TURN` (10 deg/s) x the blend's seconds to go, so the keep is gone by the Director's end (review item 5).
- `turn_limited()`: the shown view turns at most the Director's own turn + `BLEND_LAND_TURN` + what empties a lag by the end, never over `BLEND_TURN_MAX` (59 deg/s) x DUR_MAX / blend unless the Director's own does; outside blends nothing is limited, so a cut is a cut (item 3).
- The shown view is written back into `Director.pose`: a change mid-blend starts from it (items 1 and the 155 deg/s change frame, which was the guard's lag left out of the write-back).
- The heading: the view's own plus 0.25 x the end shots' forwards (over the zenith it flipped). The beat's accent goes on last (item 7).

## Numbers

`test_path_blends.py` cases, blend seconds with land < 0.1, before the keep (ea44a0b) -> now: change mid-blend 14.2 -> 3.0, fall from space 6.5 -> 1.7, cut mid-blend 7.2 -> 0, far targets (24 km) 16.6 -> 7.7, far change 15.2 -> 12.8, 6 s blends 2.2 -> 1.9 and 1.4 -> 0.9. Every blend ends on the live view (0 deg), a cut's first frame is the live view. `verify_paths.py` 2c 70.8 deg/s (limit 72); 1b fails as before #25. Demo replay (`blend_horizon.py`) 11.5 -> 2.4 s.

## Open

1. Far hops keep less land: the 10 deg/s ease budget makes the keep go out early on big gaps.
2. Live: 5 s in orbit river and 4 s in rise lake at 4 to 7 km rendered flat with land in frame (158d3c1's live run, `out/issue25/live_after.jsonl`): shader side.

## Commands

```bash
python3 -m unittest blender/tests/test_path_blends.py
python3 blender/review/verify_paths.py
python3 blender/review/blend_horizon.py
python3 blender/review/issue25_review/c.py
```

Live: `blender/review/blend_live.py` (the demo program held against Magic, see its docstring), recordings with music `blender/review/sky_frame_record.sh`.
