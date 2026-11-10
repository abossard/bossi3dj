# Planet visual check, round 4

- Folder: blender/scenes/planet_proto/visual_check/round_4/
  - 220 grabs on commit 8c62054 (8k NASA star map), 14 sheets, NOTES.md (with the single fog reference photos listed), ground_check.json, cuts.json and three earlier sweeps.
- Star map comparison for the user: visual_check/starmap_compare/ (CAM_0, CAM_9, CAM_SYS, CAM_6 night, CAM_3 night e1 at 1920, 100% Milky Way crop, 8k and 16k).
  - 8k: footprint 4.8 GB; stars about one screen pixel, crisp.
  - 16k: footprint 7.1 GB; most stars fall between screen pixels, the sky looks emptier. fps indistinguishable under the machine's load.
  - `--stars 16k` switches.
- M2 pass (aim_jump 0 on 36 cuts).
- M1 not measured fairly on the final build: an `edmformer_batch.py` process (another project) held 49 GB, swap full. 39 of 84 cuts over 70 ms in that sweep. Earlier sweeps: stalls follow machine load (file scanning, swapping), not cuts; cuts into space 55 to 65 ms.
- The machine rebooted mid-round (about 15:50): /private/tmp scratch scripts were rebuilt from the session transcript.
- Self-check risks: CAM_4 moon cut by the frame edge at p25 sunset/night; CAM_7 soft sun glint on the near water at sunset; CAM_10 night f1 dark violet layer over the sea; system-view border (syphon_out.py, outside the repo).
