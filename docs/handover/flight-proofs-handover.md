# Flight proofs session: state (branch claude/research-synthwave-flight-proofs-292214, b844224, not pushed)

Write-up: `docs/research/synthwave-flight.md`, sections "Fast motion (FL5), second rework", "The look-ahead replaces the
travel margin", "Hard cuts (M1), staged", "Proof runs". Runs: `flight-proofs/` in this folder.

## Done
- LOD: per-node cache, slot objects rewritten in place, one Capture of PL_Surface, per-frame budget, look-ahead
  segment selection, staged cuts. CAM_4 8 to 24-32 fps; Flight stages 9-10 to 25-33 fps.
- 5c passes (look-ahead; full `verify_flight.py --quick` passes). 981f646 merged.
- Proofs recorded: day, sunset (boosts, hit), night sweeps; fps_sunset (no grabs); EN5; blends.

## Results
- FL5 (fps_sunset): Orbit, Hover pass; Approach fails on p95 (105 vs 70 ms); Skim fails, p50 40.3 vs 38.4 limit.
- FL2: coarse flat blocks and a swap at the day Hover (104 s, 108 s; sweep_day f00862-f00904). Not explained.
  First guess: the staged-cut / far-block path leaving near blocks coarse, or the look-ahead direction at hover speed.
- EN1: 12 still frames per sweep from staged-cut holds. Fixed in b844224 (old shot keeps moving), not run live.
- EN5 passes. M1: warm cuts 56-71 ms (one 156), first visits 72-846 ms; cuts show 4-6 frames late.
- CAM_4 at day shows no wireframe with the runtime: the Terrain LOD blocks may lack an attribute the planet's new
  wire logic reads (asked the planet session).

## Next
1. Run the EN1 fix live; reproduce the Hover coarse patch (flight 1 at day, watch `_state["shown"]` depths near the camera).
2. FL5 Skim/Approach: profile by stage without grabs; candidates: selection (5 ms), the draw of rewritten slots.
3. Wireframe attributes on LOD blocks.
4. M1 first visits: warm all slots at start; pin fixed shots' assembled blocks.

## Scripts: this session's scratchpad (restart.py, install_prof.py, run_prof.py, prof_an.py, stage_an.py, cuts_fps.py,
cuts_an.py, seq.py, proof_jobs.py): /private/tmp/claude-501/-Users-abossard-Desktop-projects-swift-vj--claude-worktrees-research-synthwave-flight-proofs-292214/eac9769f-32c2-47cc-ab17-cbeba784be9e/scratchpad/
Note: exec'ing those scripts inside a timer function breaks their closures; run them at top level.

## Hand-back cleanup: as in flight-energy-lod-handover.md, plus remove handlers named frame_w/other_pre/post,
the profiler draw handler, unregister DN["flt_tick_w"], set scene.camera (stop() restores CAM_11, which is deleted),
and restore vj_cam_speed (0 in the planet build).
