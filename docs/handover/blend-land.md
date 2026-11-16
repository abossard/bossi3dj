# Blends keep land in frame (issue #25), hand-over 2026-11-16

## State

- 158d3c1 had review findings (3 high, 2 medium, 2 low). The rework in `path_camera.py` answers 1 to 5 and 7; `SKY_FRAME` (off) still waits for the user.
- The reviewer's replay scripts: `blender/review/issue25_review/` (`a.py`, `b.py`, `c.py`). Their cases run in `make test`: `blender/tests/test_path_blends.py`.

## The keep, as built

- While the Director blends, the view turns toward the kept view by at most `BLEND_LAND_TURN` (10 deg/s) x the seconds from the blend's nearer end: none at either end, no weights or height terms (second review: they were not pinned, and the height term snapped on a change while banded() held the eye).
- `turn_limited()`: the shown view turns at most the Director's own turn + `BLEND_LAND_TURN` + what empties a lag by the end, never over `BLEND_TURN_MAX` (59 deg/s) x DUR_MAX / blend unless the Director's own does; outside blends nothing is limited, so a cut is a cut (item 3).
- The shown view is written back into `Director.pose`: a change mid-blend starts from it (items 1 and the 155 deg/s change frame, which was the guard's lag left out of the write-back); on a change the guard measures the Director's own turn from the view shown.
- The heading: the view's own plus 0.25 x the end shots' forwards (over the zenith it flipped). The beat's accent goes on last (item 7).

## Numbers

`test_path_blends.py` (in `make test`), blend seconds with land < 0.1, before the keep (ea44a0b) -> now: change mid-blend 14.2 -> 2.5, fall from space 6.5 -> 1.7, cut mid-blend 7.2 -> 0, far targets (24 km) 16.6 -> 8.3, far change 15.2 -> 13.2, 6 s blends 2.2 -> 2.1 and 1.4 -> 1.1; far changes with the eye held 10.3 and 2.6 s at 66 and 39 deg/s (the second review: 522 and 427). Keep left on a blend's last frame at most 0.31 deg (17.9 with the time cap removed); a cut's frame is the live view after a kept frame (33.9 deg); the beat's dip stays on the kept view. `verify_paths.py` 2c 70.8 deg/s (limit 72); 1b fails as before #25. The review's fuzz (`issue25_review/fuzz.py 3 90 fixed`): no turn over the limit at 15 and 30 s fades; the 60 s fade's overs are the same with the keep off.

## Open

1. Far hops keep less land: the 10 deg/s ease budget makes the keep go out early on big gaps.
2. The haze from height (done, code only): `build_planet.fog_distance()`, applied in `planetize_fog()` to the island's `VJ_Fog` that the planet draws, grows the haze's distance by 3 m per m of eye height over 500 m (`FOG_D_RISE`, the Value node `fog_d_rise`). `/vj/haze` 0 cleared the demo's 9.75 flat seconds; A/B on the demo program 10.5 -> 1.25 flat s. Shot-reviewer (`rubric-issue25-haze.md`): t 9, 12, 28 and 34 pass; t 34 failed first on two different poses and passes at one pinned pose (`out/issue25/t34`, the haze changes 0.03 % there). Committed without the rebuilt `.blend` (the robot's render took Blender): `make blender-rebuild` in the next slot.

## Commands

```bash
python3 -m unittest blender/tests/test_path_blends.py
python3 blender/review/verify_paths.py
python3 blender/review/blend_horizon.py
python3 blender/review/issue25_review/c.py
```

Live: `blender/review/blend_live.py` (the demo program held against Magic, see its docstring), recordings with music `blender/review/sky_frame_record.sh`.
