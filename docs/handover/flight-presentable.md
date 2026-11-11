# Flight presentable (B2), Part A done, Part B half done

Branch `blender/flight`, `integration/presentable` merged (round 10, 939420e). Part A (no Blender): `make verify` and `make test` green. Part B (live, 2026-11-11, load 45 to 185, no fps numbers): the five Flight rows show an effect, the full check found four other controls that lost theirs; Hover arrival, cut stalls and idle cost are not measured. Stopped at half context, Blender closed.

## Part B, live results

- Start: the runtime starts `flight_rt` once (one `frame` and one `on_cut` handler from `flight_rt`, LOD on, 178 regions, Flight shot `CAM_11`). `open -a` keeps no log, so the start line was read from the handler's module state; a reload through `start_sibling` prints it once.
- Five rows (`--only vj_flight,vj_boost,vj_blend,vj_energy,vj_hit --no-fallback`, `docs/reports/blender-feature-check-planet-flight5.json`): all `effect`. `vj_flight` 4070x on `CAM_11`, `vj_boost` 553x on `CAM_11`, `vj_blend` 5762x on `CAM_1` (single-cell, repeated on fresh baselines: only blend 0 is a hard cut), `vj_energy` 464x and `vj_hit` 108x on `CAM_0` (two and more cells each, not single-cell). Every cell settled.
- Fixed on the way (both in this commit):
  - `vj_boost` first showed no effect: floor mad 58, frac 0.94 on `CAM_11` at `vj_flight` 0.66. `blender/review/flight_repeat.py` showed seed 1 but a different region per cell (153, 62, 35): `star_system` computes the sun from the camera, so a reset Flight took the previous cell's sun and with it another orbit plane. `flight_rt.CHECK_SUN` is the reset Flight's sun; three cells then end on the same pose to 0.01 m.
  - `vj_cam` errored (`no camera cut` for every camera): `flight_rt` keeps `CAM_RIG` in `scene.camera`. `flight_rt` now publishes the shot asked for as `driver_namespace["vj_shot"]` (a function, removed by `stop`); `Check.cell` and the page's `camera` (`synthwave_web.shot_name`) read it. Rerun of `--only vj_cam`: effect 1146x, all 12 cameras cut.
- Full check (`docs/reports/blender-feature-check-planet-flight.json`, before the `vj_cam` fix): 31 effect, 1 error (`vj_cam`, fixed since), 5 no effect. Against `docs/reports/blender-feature-check-planet.json` (2026-11-10):
  - new effect: `vj_blend`, `vj_boost`, `vj_flight`, `vj_nebula` (8.5x, single-cell, repeated)
  - lost, round 10 (lattice removed): `vj_grid_speed` (expected), `vj_bass` (was 1437x through the lattice's pulse `gk`; now it only pulses the night mesh edges at `build_planet.py` `pulse`, and its row tests by day on `CAM_0`). Round 10's to set the row (`vj_night`).
  - lost, from `flight_rt`'s LOD terrain: `vj_water` (was 2058x on `CAM_1`). With `flight_rt` started `Planet_Hydro` is hidden and the water is the LOD slots' `Sea LOD` material; at frozen clocks `vj_water` 1 to 0 on `CAM_1` changes mad 0.04, frac 0.0002 (MCP probe). `Sea LOD` reads `vj_water` (two attribute nodes) but the river shot shows nearly nothing of it: compare `Sea` and `Sea LOD` (the `lift` waves at `build_planet.py` `lift` are on `Planet_Hydro`).
  - lost, probably the same cause: `vj_flamingos` (was 103x on `CAM_0`, one cell: 0 hides them; now 1.6x on every camera). The flock is on the planet surface; check whether the LOD slots carry it.
  - lost, noisy floor: `vj_meteor` (was 29x on `CAM_2`). Its state is `vj_night` 1 and its floors are 10 to 17x the day floors (`CAM_0` mad 2.4, frac 0.17 against 0.14 before): something at night changes between baselines at frozen clocks with `flight_rt` on. First suspect: the LOD set swap or block builds on wall time.
  - contract: `/vj/cam` page 0..11 against contract 0..10 (`CAM_11` is the Flight shot), and the bridge clamps a wire index to 10, so Magic cannot cut to the Flight shot. The contract row is the orchestrator's call (`osc/contract.json`, then Magic).
  - bridge check `/vj/cam 12`: BAD because the page reported `CAM_RIG`; fixed by `shot_name` (the page module loads at open, so it shows after the next `make blender-open`).
- A cut at frozen clocks with a fresh Director lands at once (`blender/review/cut_trace.py`, `CAM_0` to `CAM_1`: on air in 0.2 s, rig 0.6 m off the shot, no blend, no LOD hold).

## Part B, next (exact commands)

```
git merge integration/presentable
make blender-open                      # the .blend was not committed; rebuild only if build_planet changed
make blender-check ARGS="--only vj_water,vj_flamingos,vj_meteor,vj_bass,vj_cam"
```
Then the water and flamingo loss (LOD slots), the night floor, and the rest of the brief:
- Hover arrival: Blender MCP `DN["hover_job"] = {"out": "/abs/hover.json"}`, exec `blender/review/hover_arrival.py`, wait for `DN["hover_done"]`; `events.arrive_s` is the time (10 to 15 s), `draws` hold per-frame ms by stage (Approach 1, Skim 2). Not run yet.
- Cut stalls: `blender/review/cut_jobs.py` (M1 70 ms).
- Idle cost: `DN["ab"]` with cell A exec `m = DN['vj_runtime'].quiesce.__globals__['_state']['flight_rt']; m._state['lod'] or m.start()` and B `m = ...; m._state['lod'] and m.stop()`, both `set` `{"vj_cam": 0}`, `settle` 8, `measure` 10, exec `blender/review/ab_frametime.py`; the last cell is B, so start `flight_rt` again after. Only with `fps_trustworthy`.
- Then the planet table of `docs/reports/blender-feature-check.md` from a fresh full run (`feature_check_table.py`).

## State

| Step | State | Proof |
|---|---|---|
| 1. `make verify` green | yes, 348 ok: 3f 37.0, 7h seed 1 sweep 19.8 (limit 39.24), 3d 34.0, 3h 10.2 s, 3j 12.1 s | `make verify` |
| 2. Start from `synthwave_runtime.main()` | done, not run live | `make test`; live in Part B |
| 3. `PRECONDITIONS` rows | done, not run live | `make test`; live in Part B |
| 4. Why `/vj/energy` and `/vj/hit` showed an effect | explained below; a lone strong cell now repeats | from the code and `docs/reports/blender-feature-check-planet.json` |
| 5. `make test` | green | see "make test" below |

## 1. Hover fixes (`blender/scenes/flight.py`)

- 7h `hits at hover` (acceleration 73-77 against 39.2): a boost carried the camera off its loop, `fe` fell, and the base speed `mix_log(weights(fe))` rose with it, 76 m/s2 along the path. Feedback, not `HOVER_DECEL`. Fix: past the Skim's key the base speed is followed (`vb`) like the floor `go`: at most `1.2 * HOVER_DECEL`, not rising during a surge.
- 7h hit surge (seed 3, 26.5 against 28 once the feedback was gone): the first hit landed while the camera braked onto the loop and the falling floor ate 9 m/s. Fix: `go` and `vb` do not fall while a boost or hit builds (`b1 > b` or `hk1 > hk`).
- 7h `sweep at full energy` seed 1 (39.7 against 39.2, also in the old note): the cap rose at 13.2 m/s2 times the energy's speed factor 1.4. Fix: the followers' rate is in the speed seen (`acc / max(ek, 1)`).
- 3d (seed 7 ramp, 53-56 deg/s against 45): the loop's nearest point hops, `want` flips, `rate` follows in one stage and the view leads by `rate * LOOK_AHEAD`, so the view's speed stepped. Fix: steering for the water, `want` is followed in two stages (`self.want`, weighted by the Hover's steering weight). Seed 7 ramp is now 40.8.
- `HOVER_DECEL` stays 11 (the 7h failure was not the braking); its comment now says 7 s and 330 m.
- 3j (Hover arrival, limit 15 s): the sea 2.3 s, water on one side 12.1 s worst. 3h 10.2 s, 3i 40 m.

### The last two (both from the arrival at the water)

- 3f, seed 6 `boost` at 153.6 s was 41.3 m/s2 (vertical -33: a boost returning to the loop crossed `HOVER_ARRIVE` in 2 s and the stage height dived). Fix: the blend `self.arrive` rises at most at `1 / HOVER_ARRIVE_TIME` (4 s), falls at once, resets below the Skim. Worst 3f now 37.0 (seed 6 `boost` at 70.7 s, tangential).
- 7h seed 1 `sweep at full energy` at 67.7 s was 39.9 (tangential 36: the cap rose at 13.2 seen and the energy's Hover term grew with `fe` on top). Fix: the term is in `sp` (divided by `ek`), so the followers and the cap carry it. Same drift on the loop (6 * 1.4 + 35 m/s at full energy); with the cap binding (water abeam) the term is capped too. Now 19.8.
- `docs/research/synthwave-flight/probe_acc.py 3:6:boost "7:1:sweep at full energy"` splits the worst acceleration of single verify cases into tangential, vertical and lateral, with `fe`, `go`, `cap`, `vb`.

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

Without `flight_rt` nothing reads them (`git grep`: only `flight_rt.py`, `energy.py` and the defaults in `synthwave_runtime.py`). Each verdict rests on one cell: `/vj/energy` 1.0 on `CAM_9` (mad 0.90, frac 0.0416, ratio 91) while 0.0 on the same camera sat at the floor (ratio 1.8); `/vj/hit` 0.5 on `CAM_3` (mad 0.83, frac 0.022, ratio 82) while 1.0 gave 4.7. `Check.effective` takes one cell at `STRONG` (10x the floor) or more as an effect, and only a weak effect gets the second look on fresh baselines (`Check.test`, `confirmed`). The floor comes from 3 baselines taken back to back and cached per camera and state for the whole run (`Check.baselines`), so a change of the picture that is not on the stopped clocks and falls between a baseline and one cell counts as the control's effect. Such changes happen at that size: the run's widest floor is mad 1.06, frac 0.0415, the same frac as the energy cell. Wall-time work outside the check's clocks: the planet's LOD set swap and anchor (`planet_runtime.update_lod`), the GN LOD builds, the bridge's trigger latch. Fix (done): `Check.test` repeats a strong effect on fresh baselines too when it is `Check.lone`: one cell shows and the other judged cells of that camera stay at the floor. The row's note says `weak or single-cell, repeated` or `a weak or single-cell first effect did not repeat`. No unit test: `synthwave_check.py` imports `bpy` and numpy, which `make test`'s python has neither of; the live run proves it.

## make test

- Python (`magic`, `osc`, `blender`): 44 (1 skipped), 21 and 6 tests, OK (2026-11-11, after the fixes).
- Godot: in a fresh worktree `run_tests.gd` and `check.gd` fail to parse (no `.godot` class cache) and `make test` still exits 0. After `/Applications/Godot_mono.app/Contents/MacOS/Godot --headless --path godot/colossus --import`: `make godot-test` 345 passed, 0 failed; `make godot-check` 22 effect, 0 error.

## Part B (after the orchestrator's go)

```
git merge integration/presentable     # the wireframe removal
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

- `planet_runtime.update_lod` still runs with `CAM_RIG` as `scene.camera` and the planet's own LOD sets stay built (the planet session's hooks from `flight-energy-lod-handover.md`).
- `make test` exits 0 when a Godot test script does not parse.

## Commands

```
make venv
make verify                                                            # about 4.5 min
.venv/bin/python docs/research/synthwave-flight/verify_flight.py --quick   # about 1.5 min
make test
```
