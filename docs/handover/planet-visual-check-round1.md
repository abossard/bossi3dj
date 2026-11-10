# Planet visual check, round 1

- Folder: blender/scenes/planet_proto/visual_check/round_1/
  - 220 grabs: 198 matrix, 12 CAM_4 loop, 6 CAM_SYS, 4 system views.
  - 14 sheets, NOTES.md, ground_check.json, cuts.json, proof/.
- Build: commit cd153fe on research/synthwave-planet; all grabs are from it (PNGs not committed).
- Zoomed-out view (S1-S7): whole planet; shading from the viewer's own altitude (sun-lit simulation from space, synthwave on the ground); moon without a cut; thin limb; round sun from space; new star sky; purple layers and nebula removed; CAM_SYS plus four system views. Free-viewport proof: proof/free_viewport_zoomed_out_night.png.
- Floating pyramids: a half-depth lift in unit_pyramid. Fixed; every pyramid in view sits within 1 px of the drawn ground.
- M1 fails by day: 4 of 28 cuts over 70 ms, worst 261.8 ms. That is the run's first cut, cold after the 15-minute matrix; cuts into CAM_6 by day are 93 to 132 ms (world swap). Sunset and night pass. M2 passes (0 deg on 36 cuts).
- Self-check fail: the CAM_4 loop at 50%.
- star_system.py is not edited (this session cannot edit the main checkout); verify_star_system.py passes.
