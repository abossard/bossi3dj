# Flight session: pure models done, scene work blocked on Blender permission

Branch `claude/research-synthwave-flight-42dd8e` (worktree `.claude/worktrees/qlc-os2l-verification-c74002`), commits d012554..55394d3, not pushed.

- Plan: `docs/research/synthwave-flight.md`; its "Results so far" section has the numbers.
- Pure modules (no bpy), all checks pass in `python3 docs/research/synthwave-flight/verify_flight.py --quick`: about 2 min. Also `--lod-only` and `--blend-only`.
  - `scenes/flight.py`: the Flight.
  - `scenes/director.py`: blends.
  - `scenes/planet_proto/lod_stream.py`: CDLOD with N 8, K 9 and M0 0.75. No cracks or pops at 155 m/s with 3 frames of lag.
- Wired: `vj_flight`, `vj_boost` and `vj_blend` in synthwave_runtime DEFAULTS and RANGES (the web page picks them up), plus the README rows, marked "being built".
- Agreed with the planet session: `lod_stream.py` is mine, with one hook each in build_planet.py and planet_runtime.py (not written yet).
- Blocked: gates G1-G3 (GN cost per vertex, EEVEE vertex displacement, isolated re-evaluation). The auto-mode classifier denied changes to the live Blender (PID 86985). Nothing in the live scene was changed.
- Next, once Blender is allowed:
  - measure G1-G3;
  - runtime adapter: the CAM_RIG rig, incremental selection, block objects and morph displacement;
  - clearance-map bake;
  - in star_system: a smooth `up`, and aiming every `vj_track` shot;
  - a bridge guard;
  - proofs.
