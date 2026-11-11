# Flight presentable (B2), Part A nearly done, Part B waits for the Blender slot

Branch `blender/flight`. Part A (no Blender) is done except two `make verify` checks (step 1). Stopped at half context. Part B (live) has not started: it needs the orchestrator's go for the Blender slot. No Blender was opened.

## State

| Step | State | Proof |
|---|---|---|
| 1. `make verify` green | **no**: 3f 41.3 and 7h seed 1 sweep at full energy 39.9 (limit 39.24); 3d, 3j and the old 7h failures pass | `make verify` |
| 2. Start from `synthwave_runtime.main()` | done, not run live | `make test`; live in Part B |
| 3. `PRECONDITIONS` rows | done, not run live | `make test`; live in Part B |
| 4. Why `/vj/energy` and `/vj/hit` showed an effect | explained below | from the code and `docs/reports/blender-feature-check-planet.json` |
| 5. `make test` | green | see "make test" below |

## 1. Hover fixes (`blender/scenes/flight.py`)

- 7h `hits at hover` (acceleration 73-77 against 39.2): a boost carried the camera off its loop, `fe` fell, and the base speed `mix_log(weights(fe))` rose with it, 76 m/s2 along the path. Feedback, not `HOVER_DECEL`. Fix: past the Skim's key the base speed is followed (`vb`) like the floor `go`: at most `1.2 * HOVER_DECEL`, not rising during a surge.
- 7h hit surge (seed 3, 26.5 against 28 once the feedback was gone): the first hit landed while the camera braked onto the loop and the falling floor ate 9 m/s. Fix: `go` and `vb` do not fall while a boost or hit builds (`b1 > b` or `hk1 > hk`).
- 7h `sweep at full energy` seed 1 (39.7 against 39.2, also in the old note): the cap rose at 13.2 m/s2 times the energy's speed factor 1.4. Fix: the followers' rate is in the speed seen (`acc / max(ek, 1)`).
- 3d (seed 7 ramp, 53-56 deg/s against 45): the loop's nearest point hops, `want` flips, `rate` follows in one stage and the view leads by `rate * LOOK_AHEAD`, so the view's speed stepped. Fix: steering for the water, `want` is followed in two stages (`self.want`, weighted by the Hover's steering weight). Seed 7 ramp is now 40.8.
- `HOVER_DECEL` stays 11 (the 7h failure was not the braking); its comment now says 7 s and 330 m.
- 3j (Hover arrival, limit 15 s): the sea 2.3 s, water on one side 12.1 s worst. 3h 10.2 s, 3i 40 m.

### Still failing (both from the arrival at the water, both appeared with the two-stage `want`, which moves the paths)

- 3f, seed 6 `boost` at 153.6 s: 41.3 m/s2 at 43 m, 180 m/s. Vertical -33 (the stage height dives toward the Hover's 4 m as `fe` rises over `HOVER_ARRIVE` 400 m, at boost speed in about 2 s) plus tangential -22 (the floor `go` braking at 13.2 and the boost releasing). Next try: `fe`'s rise rate-limited (time, not distance) or `go`'s fall slowed while `fe` rises.
- 7h seed 1 `sweep at full energy` at 67.7 s: 39.9 at 23 m, 113 m/s, tangential 36. The cap rises at 13.2 seen, and the energy's Hover term `ENERGY_HOVER * BOOST_SPEED * en * w[HOVER]` (35 m/s at full energy) grows with `fe`. Next try: follow that term at the same rate as the cap (fold it into the followed base).
- The probe that decomposes the acceleration (tangential, vertical, lateral) was a scratch script; rebuild it in `docs/research/synthwave-flight/` if it is needed again (about 30 lines: run one program, print `|a|` split along the velocity, the radial and the rest, with `F.go`, `F.cap`, `F.vb`, `F.fe`).

## 2. The start

- `synthwave_runtime.main()` calls `start_sibling("//flight_rt.py")` and keeps the module in `_state["flight_rt"]`. `flight_rt.start()` returns at once without `Planet_Hydro` and `PL_Surface`: the island gets no handler, no timer, no per-frame work (only the import at load).
- Registration: `flight_rt` puts `frame` (`frame_change_pre`, first) and `on_cut` (`depsgraph_update_pre`), removing earlier ones by name and module, so a reload replaces them. `lod_scene` keeps one `build_tick` timer (`persistent=True`). New: on a load, `flight_rt` first stops a previous `lod_scene` (its timer and slot objects) and drops `director`, `energy`, `flight`, `lod_scene`, `lod_stream` from `sys.modules`, so a reload runs the files on disk and never stacks a second terrain stream or timer. Before, a reload kept the cached modules (stale code) and `lod_scene.start` reset its state over live slots.
- The clock: `flight_rt.frame` took wall time, so a frozen self-check could not hold any shot still. Now it takes `vj_runtime.peek_dt` (new, the runtime's dt for this frame without using up a step). With the clocks stopped the Flight holds its pose (`flight_pose` returns the last one at dt 0).
- Per-frame cost on the planet with `/vj/flight` 0 and no trigger: **not zero and not an early return.** `flight_rt.frame` is the On-Air Camera for every shot: each frame it steps the energy Drive, moves the shot on air (`energy.move`, every fixed shot has an ellipse by design, EN1), steps the Director, places `CAM_RIG` and runs `lod_scene.update`. The Flight's own integrator runs only while the Flight shot is on air or the old shot of a held cut; with another shot on air it costs nothing. `on_cut` is one lookup and a compare per depsgraph update. Part B measures the cost (idle A/B).

## 3. Self-check rows (`blender/scenes/synthwave_check.py`)

- `cams` takes `"flight"`: the shot with `vj_flight_cam` (flight_rt adds it as the last `CAM_n`, `CAM_11` on the planet), resolved by `Check.cam_number`.
- Per cell the check calls `vj_runtime.quiesce()`; it now calls `flight_rt.quiesce()`: the next frame starts the Drive, the Director and the Flight afresh, the Flight on seed 1 and settled at the `/vj/flight` set for the cell. Without it the Flight, the Drive's phase and the Director carry over between cells and the baselines of a moving shot never match. The self-check shows the stage, `verify_flight` section 1 proves the damping.

| Control | State | Advance |
|---|---|---|
| `vj_flight` | Flight shot | 2 s |
| `vj_boost` | `vj_flight` 0.66, Flight shot | 2 s |
| `vj_blend` | `CAM_1`, then a cut to `CAM_4` (unchanged) | 0.3 s |
| `vj_energy` | `CAM_0` (every fixed shot moves) | 2 s |
| `vj_hit` | `CAM_0` (the kick is on the rig) | 0.5 s |

## 4. Why `/vj/energy` and `/vj/hit` showed an effect without a reader

Without `flight_rt` nothing reads them (`git grep`: only `flight_rt.py`, `energy.py` and the defaults in `synthwave_runtime.py`). Each verdict rests on one cell: `/vj/energy` 1.0 on `CAM_9` (mad 0.90, frac 0.0416, ratio 91) while 0.0 on the same camera sat at the floor (ratio 1.8); `/vj/hit` 0.5 on `CAM_3` (mad 0.83, frac 0.022, ratio 82) while 1.0 gave 4.7. `Check.effective` takes one cell at `STRONG` (10x the floor) or more as an effect, and only a weak effect gets the second look on fresh baselines (`Check.test`, `confirmed`). The floor comes from 3 baselines taken back to back and cached per camera and state for the whole run (`Check.baselines`), so a change of the picture that is not on the stopped clocks and falls between a baseline and one cell counts as the control's effect. Such changes happen at that size: the run's widest floor is mad 1.06, frac 0.0415, the same frac as the energy cell. Wall-time work outside the check's clocks: the planet's LOD set swap and anchor (`planet_runtime.update_lod`), the GN LOD builds, the bridge's trigger latch. Fix for the check (not done, the orchestrator's call): a strong single cell repeats once too when the other cells of its camera stay at the floor.

## make test

- Python (`magic`, `osc`, `blender`): 44 (1 skipped), 21 and 6 tests, OK.
- Godot: in a fresh worktree `run_tests.gd` and `check.gd` fail to parse (no `.godot` class cache) and `make test` still exits 0. After `/Applications/Godot_mono.app/Contents/MacOS/Godot --headless --path godot/colossus --import`: `make godot-test` 345 passed, 0 failed; `make godot-check` 22 effect, 0 error.

## Part B (after the orchestrator's go)

```
make blender-rebuild
make blender-open
make blender-check ARGS="--only vj_flight,vj_boost,vj_blend,vj_energy,vj_hit --no-fallback"
```

The rebuild is needed only if the scene files are stale; the runtime files load from disk on open. On open the log must show `flight_rt: started, ... Flight shot CAM_11` once. Then:

- the five rows `effect`, each on its camera; the frames of a cell at stopped clocks stand still (settled);
- Hover arrival live: `/vj/flight` 0.66 until on the Skim track, then 1; the Hover in effect 10-15 s after f reaches 1;
- Orbit framing (planet and moon), M1 cut stalls, FL5 Approach and Skim frame times (context only under foreign load);
- idle cost A/B: fps with `flight_rt` started against stopped (`flight_rt.stop()` from the Blender MCP), the same fixed shot, clocks frozen, only if `make status` says `fps_trustworthy`;
- close with `make blender-kill`.

## Open

- The self-check's single strong cell (section 4).
- `planet_runtime.update_lod` still runs with `CAM_RIG` as `scene.camera` and the planet's own LOD sets stay built (the planet session's hooks from `flight-energy-lod-handover.md`).
- `make test` exits 0 when a Godot test script does not parse.

## Commands

```
make venv
make verify                                                            # about 4.5 min
.venv/bin/python docs/research/synthwave-flight/verify_flight.py --quick   # about 1.5 min
make test
```
