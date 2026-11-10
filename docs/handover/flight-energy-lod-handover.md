# Flight: energy controls and LOD rework (branch claude/research-synthwave-energy-controls-11aae2)

Hand-over from the energy/LOD session, 2026-11-06. The full write-up is in `docs/research/synthwave-flight.md` on the branch.

## Done
- `/vj/energy`, `/vj/hit` and the pulse on every shot: `scenes/energy.py`, wired in `flight_rt.py`, `flight.py`, `director.py`. Checks in `verify_flight.py` section 7 (`--energy-only`), all pass.
- Live energy proofs on CAM_0..10 and CAM_SYS: no still frames (EN1), speed and turn rise with the energy (EN2, EN4), every hit reaches a 0.70x lens (EN3). Sheets, traces (svg) and videos in `flight-energy-proofs/`.
- LOD: blocks baked to plain meshes by 8 GN builders in a timer; hidden blocks out of the depsgraph. Fixed shots about 10 to 28-38 fps; cut stalls 2-17 s to three frames of 150-190 ms.
- OSC bridge: triggers are held high over a frame change (pulses were lost under 10 fps).

## Still open
- Fast motion (CAM_4 at 95 m/s, the Skim, boosts): about 44 blocks a second at 4-6 ms each; the queue never empties. Next: profile `FLT_Lod` per node; prebuild along tracks and paths; damp the horizon cull's churn.
- M1 (70 ms on a cut) fails: the first draw of about 140 newly shown meshes.
- FL1-FL5 proofs on an idle machine: one Flight run at sunset recorded (see the doc); day and night sweeps, seeds and blends are not.
- The `synthwave_runtime.py` hook for `flight_rt` is still not written; the planet session's hooks (drop `lod_sets()`, skip `update_lod` for the rig) too.

## Next session: where to start (state after merging 08d52c1)
- The planet session's smooth globe handover (45b3cc5, and 08d52c1 for the night side) is merged. Rerun the Flight sweeps to check FL2 at 8-12 km. Blender is free and running the new build; the planet session's terms still apply.
- Load the live runtime from the worktree: put `scenes` and `scenes/planet_proto` first on `sys.path`, pop `flight_rt flight director energy lod_scene lod_stream` from `sys.modules`, add `vj_flight vj_boost vj_blend vj_energy vj_hit` to the scene (vj_hit with UI description "trigger"), `flight_rt.start()`. The prebuild takes about 25 s (41 blocks/s).
- Optionally start the worktree's `blender_osc_bridge.py` (it has the trigger latch). At hand-back: `bpy.data.texts["blender_osc_bridge.py"].as_module().start()`, then `flight_rt.stop()`, then remove CAM_RIG, CAM_11, FLT_Rivers and the Planet LOD collection, set `vj_cam` max back to 10.
- A sequencer that runs recorder jobs back to back via a timer was in the scratchpad (`DN["seq_jobs"]`, writes ALLDONE). Rewrite it: about 20 lines.
- Profiling FL5: `ev.modifiers["lod"].execution_time` per builder; 5.9 ms for a 16-node block. Try variants on a copy of `FLT_Lod` (as the rivers test did), cutting groups of nodes: `cube_dir` math chain, the 4 Sample Index nodes, the mirror branch, White Noise, Delete Geometry, Realize Instances. Batch of 8 builders gives 4 ms a block (parallel).
- Churn: about 44 blocks/s at 95 m/s. Coarse blocks change with height from the horizon cull; margin noise from the Director's speed.
- 5c (boost pop 1.29 cm vs 1 cm): not fixed; it fails the same at bb6bdea. It's `lod_stream` params (K, M0) or the margin; any change there touches the live LOD too.
- `energy_report.py`, `cuts_report.py`, `report.py` turn the runs into tables. `report.py`'s labelled montage needs a font for magick (`-font`); the sheets came out unlabelled.

## Live Blender gotchas
- `bpy.app.timers` drop a timer whose function raises: `lod_scene.build_tick` now catches and prints.
- `scene.update_tag()` every frame makes any geometry tag cost about 8 µs per object in the depsgraph: keep objects out (`hide_viewport`) rather than hidden from the camera.
- `ID.copy()` of an evaluated mesh is 70x faster than `bpy.data.meshes.new_from_object` and keeps attributes and materials.
- mathutils `Matrix` has no `trace()`.
