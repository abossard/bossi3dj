# Planet visual check, round 2

- Folder: blender/scenes/planet_proto/visual_check/round_2/
  - 220 grabs, 14 sheets, NOTES.md, ground_check.json, cuts.json.
- Build: commit de0ceab (PNGs not committed).
- Self-check still fails:
  - CAM_3 day/sunset e0 (6 shots): it holds the pyramids from a rise with no sky in frame.
  - CAM_10 day/sunset (12 shots): pale patches of low flats at sea level remain.
  - M1: one cut at 89.8 ms, the run's first cut after the 15-minute grab run (a first-visit GPU re-upload, vbo_time_out 120 s). The other 83 cuts are at most 60.7 ms.
- Risks: CAM_1 f1 only a little thicker than f05; CAM_4 small notches at p0; CAM_9 night fog top level.
- M2: aim_jump 0 on all 36 cuts. aim_first reads about 35 deg on CAM_3 by day because CAM_3 now holds the pyramids while the moon is down.
