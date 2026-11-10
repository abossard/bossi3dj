# Planet visual check, round 3

- Folder: blender/scenes/planet_proto/visual_check/round_3/
  - 220 grabs, 14 sheets, NOTES.md, ground_check.json, cuts.json. System views now named `CAM_SYS_<view>_night05_e0.png`.
- Build: commit ec31c4e (PNGs not committed). Godot was not running.
- M1: final build, 84 cuts at most 58.6 ms. Earlier sweeps on the previous build had day outliers (75 to 213 ms, one into a set unseen for 4 min at 161 ms). Cause of the non-cold one not found.
- M2: aim_jump 0 on all 36 cuts into CAM_3/CAM_9.
- Self-check risks:
  - CAM_3 night e0: the moon stays behind the valley ridge (its top edge 1 deg over level, the ridge 10 deg); the frame holds stars over the pyramids.
  - CAM_7: the sun is 51 deg off the view (no flock with open water behind it lies closer), out of frame at sunset; a pale wet flat at sunset/night.
  - CAM_4: p50 one hill about 40%; the moon cut by the frame edge at p25 sunset/night.
  - CAM_10 sunset f1: level pink sea fog over the lower 60%.
  - CAM_SYS: the Milky Way may read as a grey smear; dark 3 to 8 px border on some space grabs.
- Border cause: `scenes/syphon_out.py` (outside the repo, not edited) `camera_rect` projects corners 0.5 m in front of a camera 100 km out in single precision. Fix: `cam.matrix_world @ (v * 10000.0)` (tested live in memory).
