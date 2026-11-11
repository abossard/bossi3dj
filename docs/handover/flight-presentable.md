# Flight presentable (B2), Part A done, Part B half done, Part C (terrain gate) done, Hover live open

Branch `blender/flight`, `integration/presentable` merged (round 10, 939420e). Part A (no Blender): `make verify` and `make test` green. Part B (live, 2026-11-11, load 45 to 185, no fps numbers): the five Flight rows show an effect, the full check found four other controls that lost theirs; Hover arrival, cut stalls and idle cost are not measured. Stopped at half context, Blender closed.

## Part C, the terrain gate (2026-11-11, Blender-free part)

Decision (orchestrator): a fixed shot on air shows the planet as built; the Flight's streamed terrain only while the Flight shot (`CAM_11`) is on air or one side of a running blend.

What the stream did before: `lod_scene.update` hid the planet's own land and water sets (`Planet.<key>`, `Water.<key>`; `Planet_Hydro` itself is an evaluation object in a hidden collection, never drawn) and its slots drew `Terrain LOD` and `Sea LOD` for every shot; the build timer ran always; and `planet_runtime` saw only `CAM_RIG` as `scene.camera`, so after the start it never switched set, anchor or flock again (the "Open" item of the planet session).

- `director.streamed(flight, shot, sides, blending)`: pure, the rule. `Director.sides` holds the shots of a running blend (a change of mind mid-blend adds one, so a blend that ever had the Flight as a side stays streamed until it ends).
- `lod_scene.pause()`: timer unregistered, every slot emptied (shown, staged, retiring; an empty slot draws nothing and is not evaluated again), selection state reset, node and block caches kept. `resume()`: timer on. `start()` no longer starts the timer; the fixed shots' prewarm is only queued and bakes while the stream runs. `live()`: the stream shows a view with all its near blocks since the last resume. `hide_sets` is gone from `lod_scene`.
- `flight_rt.frame`: per frame `stream = streamed(...)`; on a change `resume` or `pause` (in the frame handler, before the rig is placed). LOD update, prewarm at a blend start and the cut hold run only while streamed. Publishes `driver_namespace["vj_terrain"]` = (the fixed shot whose sets the planet shows, `stream and lod_scene.live()`). The sets' shot (`planet_shot`): the fixed shot on air; in a blend between fixed shots the new one once the rig is nearer to it than to the old one (a switch at about mid-blend, where the path is high); the Flight keeps the last fixed shot.
- `planet_runtime` (embedded at build: needs `make blender-rebuild`): `on_air()` reads `vj_terrain` (falls back to `scene.camera` without `flight_rt`); `update_lod`, `on_cut` and a path shot's sky follow that shot, so set, anchor and flamingo flock switch at a cut as without the Flight runtime. `show_lod_set` keeps `Planet.*` and `Water.*` hidden while the stream is shown; a change of that flag re-applies the current set. It owns set visibility alone now.
- `/vj/energy` and `/vj/hit` still move the rig of every fixed shot (`moved_pose`, `Director` accents); they never touched the terrain.

Hand-over at a cut (the choice: a held frame into the Flight, an immediate switch out of it):
- Cut into the Flight: the old fixed shot stays on air (its sets, its energy move) while `lod_scene` stages the Flight's view (`holding`, up to `HOLD_MAX` 12 frames, then a forced flip); the sets hide only once `live()`, so a forced flip with near blocks still missing shows the sets under the partial stream rather than a hole. Cost: the cut lands up to 12 frames late (0.2 s at 60 fps) on a warm cache; on a cold one (first visit to that region) the forced flip may show the coarse set for a few frames. The stream's first frame after a resume writes about 150 blocks staged at 30 a frame (`STAGE_BLOCKS`, 25 ms budget), as every staged cut before.
- Cut out of the Flight: in the same frame `pause()` empties the slots and `planet_runtime` shows the fixed shot's precomputed set and flock. Cost: one frame with about 150 `clear_geometry` calls and one depsgraph relations rebuild from `hide_set` on the set objects (15 to 20 ms measured for one show/hide before); `cut_jobs.py` measures it live.
- Blend into the Flight: the stream resumes at the blend's start and prewarms the Flight's pose; its first view after a resume is always staged (30 blocks a frame into hidden slots, not 150 in one frame), but during a blend the rig is never held (`flight_rt.frame`: the hold needs `D.tr is None`); the sets stay on until `live()`, then hide. Blend out of the Flight: the stream runs to the blend's end, then the switch as at a cut out. The switch between the stream and the set is a LOD pop (same `PL_Surface`, other mesh density), not a gap.
- Not chosen: prebuilding the Flight's terrain during fixed shots (costs builds while a fixed shot is on air, against the decision).

Step 2, from the code:
- `/vj/flamingos`: the flock is `Flamingos`, filled by `planet_runtime.copy_flocks` from `Flock.<key>` at a set switch. With the rig as `scene.camera` no switch happened after the start, so `CAM_0` showed the start camera's flock spots (or none). Restored by `on_air()`.
- `/vj/water`: `CAM_1`'s water is its `Water.<key>` set (`Sea`), hidden by the stream and not switched to either. Restored by the gate and `on_air()`.
- `/vj/meteor`: the sky reads `rt_met*` from `synthwave_runtime.meteors` (no camera, no terrain; idle meteors need dt, 0 at frozen clocks). Its night floors 10 to 17x: work on wall time between baselines, the suspects being the build timer (the prewarm of eleven fixed shots baking during the check) and `swap()` adding far blocks as they are baked. Both are off with a fixed shot now. Live check left: the floors back near the day floors.
- Also follows from the gate: `star_system` trackers (`vj_track`) compare `tc == scene.camera` (the rig): a tracker shot on air takes the off-air branch (own radial up, sun at `p + s * 150 km`). At `/vj/energy` 0 the rig sits on the shot, so the pose is the same; not changed.

Contract: `/vj/cam` 0..11 (`CAM_11` the planet's Flight shot), `make osc-sync` (CONTROLS table, bridge `SCALES` clamp 11), `magic/synthwave_magic.py` `CamSel` 0..1 to 0..11 and `CamCount` 1..12 (the auto-cutter's full cycle now includes the Flight shot), `make magic-build` (both committed projects that carry it). Godot's wire map (`vj_map.gd` hi 11, its contract test) follows; `main.gd` still clamps to `AERIAL`.

Tests: `blender/tests/test_terrain.py` (the rule, and a stepped Director through cuts, blends and a change of mind). `make verify` 348 ok; `make test`: magic 44 (1 skipped), osc 21, blender 8, `godot-test` 357 passed, `godot-check` 22 effect (2026-11-11). Not run live: nothing of Part C has met Blender yet.

## Part C, live (2026-11-11, `integration/presentable` 05f3b9b merged: round 11 ground; load 95, `fps_trustworthy` false)

- `make verify` 348 ok after the merge, `make blender-rebuild` (needed: `planet_runtime` is embedded), `make blender-open` start state ready. On a fixed shot: `stream` False, build timer off, 0 slots shown, only `CAM_0`'s `Planet.`, `Water.`, `Props.` sets visible.
- Equality (`blender/review/terrain_equality.py`, numbers `terrain_equality_diff.py blender/review/out/terrain_eq`): clocks frozen, `/vj/energy` 0, `flight_rt.moved_pose` held at the shot's own pose (the energy ellipse moves a fixed shot by at least 1 m at any energy, `energy.move` `AMP_MIN`). Mean abs diff 0..255 and share of pixels off by more than 8:

| case | floor started (A1-A2) | floor stopped (B1-B2) | started-stopped (A1-B1, A2-B2) |
|---|---|---|---|
| `CAM_0` day | 0.042, 0.00013 | 0.043, 0.00031 | 0.052 / 0.042, 0.00031 / 0.00034 |
| `CAM_1` day (river) | 0.073, 0.00073 | 0.049, 0.0002 | 0.075 / 0.055, 0.00066 / 0.00023 |
| `CAM_0` night | 0.677, 0.031 | 0.366, 0.010 | 0.646 / 0.614, 0.029 / 0.026 |

  Started against stopped stays within the larger floor in every case.
- Full check (`docs/reports/blender-feature-check-planet-flight.json`, table in `docs/reports/blender-feature-check.md`): 35 effect, 2 no effect, contract 0 mismatches, holds released. Back: `vj_water` 744x on `CAM_1`, `vj_meteor` 5.4x on `CAM_2` (was 29x on 2026-11-10). Kept: `vj_flight` 65357x and `vj_boost` 104x on `CAM_11`, `vj_blend` 5277x on `CAM_1`, `vj_energy` 6208x, `vj_hit` 5384x, `vj_cam` 1941x, `vj_bass` 30x on `CAM_0`. New against 2026-11-10: `vj_blend`, `vj_boost`, `vj_flight`, `vj_nebula`. Lost: `vj_grid_speed` (on purpose) and `vj_flamingos` (2.3x best, all 12 cameras): `Flock.CAM_0.0` has 0 points in this build (round 11 relief; `CAM_6` also 0). The runtime part works: after a cut to `CAM_1` its sets and its 225 flock points are on, 49 in view at 818 m and more. Owner: the planet build (`build_planet.py` flock spots), not the Flight; or move the row to a camera with a flock.
- Hover arrival (`hover_arrival.py`, `blender/review/out/hover_arrival.json`): **24.7 s** from f at 1 to the Hover (`verify_flight` 3h: 10.2 s on its synthetic ground), seed 1. Frames median 54 ms in that window, the clock's 0.1 s cap hit by 1.1 % of frames, sim time 24.6 s against wall 24.7 s: not a slow-clock artefact. Open: live ground (round 11 relief) or the larger dt (54 ms against the verify step); next look at `F.step` with `dt` 0.054 on the verify terrain (`verify_flight.py` 3h at that step). **Update (2026-11-11, step test and two live runs):** the model does not depend on the frame time: `verify_flight.py` 3j now runs at 17, 54 and 100 ms, worst in effect after f at 1: the sea 2.28 / 2.32 / 2.40 s, water on one side 12.13 / 12.20 / 12.20 s (limit 15), so no integrator change. Live again (`hover_arrival.py`, load 100, frames median 38 to 41 ms, seed 6223): Hover in effect 0.0 s and 1.18 s after f at 1 (`out/hover_arrival.json`, `hover_arrival_2.json`); the 24.7 s above did not come back. What does take 21 s in both runs is f itself going from 0.66 to 1 (`FLIGHT_RATE` 1/50 per s, by design: a jump from 0 to 1 flies for about a minute), so from the jump to the Hover it is about 21 to 22 s; the 10 to 15 s target is counted from f at 1. If the user wants it from the jump, the rate is the lever, a decision for them.
- Cut stalls, hard cuts `/vj/blend` 0 (`blender/review/cut_flight_jobs.py`, `blender/review/out/cut_flight.json`), worst draw interval within 1.5 s, frames 46 to 54 ms at rest: into the Flight 92, 102, 106, 108, 110 ms; out of the Flight 57, 66, 82, 88, 90 ms (to `CAM_0`, `CAM_0`, `CAM_5`, `CAM_1`, `CAM_9`); between fixed shots 71 to 90 ms. Under load: reported, not judged against M1 70 ms.
- Idle A/B (`ab_frametime.py` on `CAM_0`, `/vj/blend` 0, 3 rounds interleaved, `blender/review/out/idle_ab.json`): started 48.3 ms (47.7 to 48.8), stopped 46.0 ms (45.5 to 46.3); 2.3 ms more, the rounds do not overlap. `flight_rt.frame` itself is 0.27 ms median (wrapped for 130 frames), the build timer is off and no slot is shown, so the rest comes after the handler: most likely the rig moving every frame (the energy ellipse) against a still `CAM_0` when stopped. `fps_trustworthy` false (load 95): context only.


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

- `planet_runtime` follows the shot behind the rig (Part C); the planet's own LOD sets stay built (the planet session's hooks from `flight-energy-lod-handover.md`).
- `make test` exits 0 when a Godot test script does not parse.

## Commands

```
make venv
make verify                                                            # about 4.5 min
.venv/bin/python docs/research/synthwave-flight/verify_flight.py --quick   # about 1.5 min
make test
```
