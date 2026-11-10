# Flight round 2 (hover-5b4237): hand-over

Branch `claude/research-synthwave-flight-hover-5b4237`, commits 2a680ef (code) and the doc commit after it, not pushed.
Write-up: `docs/research/synthwave-flight.md`, section "Round 2". Runs: `flight-proofs-r2/` here.

## Done
- FL2 day Hover: cause was the Hover 4 m over dry hillsides (its water loop 1-2 km off, 6 m/s drift). Fixed in
  `flight.py` (water loops round the Skim ring, transit in the Skim-to-Hover blend, braking, latch). The coordinator
  approved the design: Hover only drifts, only over water, within 10-15 s of f=1. Live map: 6 of 8 seeds within 14 s,
  2 seeds 26-28 s (water on one side). verify_flight --quick passes (3h, 3i new).
- CAM_4 wedges: absent with the LOD blocks (planet patch sets only). Told the planet session.
- EN1 holds: verified live, pass.
- Wireframe "covers everything": planet session's Terrain shader only (2bbbb56); LOD blocks copy it at start.

## Next (Blender is with the planet session for its round 6 rebuild; it messages when back)
1. Restart the runtime: in Blender run the worktree bridge (`runpy.run_path(<wt>/blender/blender_osc_bridge.py)["start"]()`),
   add vj_flight/boost/blend/energy/hit props (vj_hit description "trigger"), exec `flight-r2-scripts/restart.py`
   (paths point at the hover worktree and its scratchpad; fix the scratchpad path if run from another session).
2. Proofs: exec proof_jobs.py then seq.py (writes ALLDONE in flight-proofs-r2/). About 20 min. Then
   `fl5_report.py`, `report.py`, `energy_report.py` on each run. Check the day Hover: speed trace (`v`, `fe` in grabs).
3. FL5 from fps_sunset: Approach p95 (suspect CUT_MS 60 ms budget when over half the wanted nodes are missing during
   the descent), Skim p50 (FRAME_MS 8 ms of LOD work per frame).
4. M1 options in the doc, first: warm every slot at start.
5. Region lock 160-240 ms at the Orbit (hover loops): spread over frames.
Hand-back cleanup: as done at 11:5x today (see the doc of flight-proofs-handover.md), plus vj_cam max is an int.

## Update 12:40: proofs recorded (flight-proofs-r2/), Blender handed back to the planet session
- EN1 pass everywhere. FL5: Approach p95 112, Skim p50 40.8 vs fixed 32.0/39.7 (fail, not profiled).
- Hover live: night/sunset OK; day and fps_sunset stuck in the Skim transit for the whole 80 s hold; a later live
  check took 30 s from 2 km. Steering in the blend closes only 40-57 m/s. Next: steer fully from f 2/3, or faster transit.
- Water at 4-45 m is a flat dark slab: over the SEA (level 0), 22-27 km from the pole, not high lakes. Planet's.
- Commits: 2a680ef, 915c600, aaf3732 (merge a179c28), and the proof-runs doc commit.
