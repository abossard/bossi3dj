# Flight presentable (B2), interim note, Part A

Branch `blender/flight`, merged from `integration/presentable` at 2f48b70. Stopped at half context. Part A is not finished; Part B (live) has not started. No Blender was opened.

## State

| Item | State |
|---|---|
| 5d descend | fixed in the check, passes |
| Hover arrival model | reproduced the live 26-47 s; transit reworked; new check 3j passes |
| `make verify` | **fails**: 3d (53.1 deg/s, limit 45) and 7h acceleration (hits at hover, seeds 1 and 3; sweep at full energy seed 1, 39.7 vs 39.2) |
| Wiring `flight_rt`, `energy`, director from `synthwave_runtime.main()` | not started |
| `PRECONDITIONS` rows for the five controls | not started |
| Why `/vj/energy` and `/vj/hit` show an effect without a reader | not started |
| `make test` | not run after the changes |

### 5d descend

- The 16 changes are face `(1,0,0,0)` flipping between root and depth 2 at about 600 m altitude. Every one is past the horizon for both selection cameras.
- Cause: the cull uses `now and later` horizons; the look-ahead camera bobs with the terrain-following altitude, so the root's cull flips (frames 531-829).
- Fix in `verify_flight.py`: 5d counts multi-depth changes in front of the horizon, as 5c already skips cull changes past it. The hidden ones are printed (`past the horizon for both cameras (not seen): 16`).

### Hover arrival

- New check 3j in `verify_flight.py`: a jump of `/vj/flight` from the Skim (2/3) to the Hover (1), 8 seeds x 4 start states (0, 15, 30, 45 s on the Skim track) x 2 regions (the sea, and the mountain region with water on one side). Measure: s from f reaching 1 to the Hover in effect (`fe` 1), limit 15. f itself takes 21 s from 2/3 to 1.
- Before the changes: water on one side 47 s worst, 13 of 32 over 15 s (the live map had 26-28 s). Now: 12.0 s worst (seed 5, water 2.3 km off), the sea 2.2 s.
- Causes found, each with its change in `blender/scenes/flight.py`:
  1. Pure pursuit to a target 3 km off flies the arc through it, `dist / (2 sin alpha)` wide (a 1.5 km radius half circle). Change: `dist` clamped to `look`.
  2. The Hover's 0.4 g at transit speed: a camera beside its loop circled it at 450-560 m. Fixed by 3 (a slower turn), not by more lateral acceleration (tried, it broke 3d).
  3. U-turns at 85 m/s take 18 s. Change: a transit speed cap `HOVER_TURN` 30 m/s with the water abeam or behind, `HOVER_TRANSIT` 125 m/s head-on (`cos(alpha)^2`), followed and released at `1.2 * HOVER_DECEL`, not falling during a surge.
  4. Base speed followed `f`, not the stage in effect: a dip to 71 m/s early in the blend. Change: `mix_log(weights(fe))`.
  5. `HOVER_STEER` 1/12 to 1/48 (steers for the water almost from the Skim's key), `HOVER_DECEL` 8 to 11.
- Open regressions from these changes (all in `make verify`):
  - 3d: seed 7 `ramp` at 85.2 s, f 0.832, 13 m, 23 m/s. The loop's nearest point hops, alpha jumps from +6 to -38 deg in one frame, `want` follows, and the view (`rate * LOOK_AHEAD`) swings at 53-58 deg/s. Pre-existing hop, new trajectory. Next try: low-pass the pursuit target (or `want`) for the Hover track only, or use the global nearest instead of the hinted one when the camera is off the loop.
  - 7h `hits at hover` acceleration 73-77 (limit 39.2): likely the cap or `HOVER_DECEL` 11 against a hit's surge. Check with `HOVER_DECEL` 8 first (with 8, 3j water on one side was 14.7 s worst and 3f failed once, so retest both).
  - 7h seed 3 `hits at hover` surge was 25.2 (limit 28) in one variant, passes now.
- `HOVER_DECEL`'s comment still says 85 m/s in 10 s; fix the numbers once the value settles.

## Part A, left to do

1. Make `make verify` green (above), then `make test`.
2. Wire the start: one call from `synthwave_runtime.main()` that starts `flight_rt`, `energy` and the director on the planet only. Check their registration (`driver_namespace`, handlers, timers) so a reload through `vj_loader.py` replaces, never stacks. Idle cost with `/vj/flight` 0 must be zero or measured negligible.
3. `PRECONDITIONS` in `blender/scenes/synthwave_check.py`: `/vj/boost` needs Skim or Hover, `/vj/blend` needs a cut between shots, `/vj/flight` needs time to move, `/vj/hit` and `/vj/energy` need the Director's accents on a moving shot. Check the names in the check table.
4. Explain from the code why `/vj/energy` (CAM_9, 0.90 mad) and `/vj/hit` (CAM_3, 0.83 mad) show an effect in the self-check without a reader. Start with `synthwave_check.py` (what it changes besides the property, the baseline timing) and with `star_system.py`, `synthwave_runtime.py` for any read of `vj_energy`, `vj_hit`.
5. Commit, update this note, end the turn.

## Part B (after the orchestrator's go)

```
make blender-rebuild
make blender-open
make blender-check ARGS="--only vj_flight,vj_boost,vj_blend,vj_energy,vj_hit --no-fallback"
```

Then: Hover arrival live (10-15 s after f reaches 1), Orbit framing, M1 cut stalls, FL5 Approach and Skim frame times (context only under foreign load), idle cost A/B with the Flight wiring on and off, clocks frozen. Close Blender with `make blender-kill`.

## Commands

```
make venv
make verify                                                            # about 4.5 min
.venv/bin/python docs/research/synthwave-flight/verify_flight.py --quick   # about 1.5 min
```
