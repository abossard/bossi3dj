# Synthwave Planet, review round 16 rubric

Frozen before the checks of round 16 (2026-11-14). It does not change during the round. Frames are full size (1920x1080) Syphon grabs of the live GPU terrain, every control held at the show defaults.

Set R (rivers, `blender/review/river_check.py`): per shot a frame (`<shot>.png`), the per-pixel change over 40 frames on a still camera with the idle pulse off (`<shot>_motion.png`, grey, x8) and the change the river flow adds (`<shot>_flow.png`, grey, x8: black means the flow moves nothing there).

| ID | Line |
|---|---|
| R16-RIVER-SEEN | The frame shows a river course (a narrow band of water through land), not only a lake or the sea. Say where, and roughly how wide it is in pixels. |
| R16-RIVER-WHOLE | Where a river is seen it runs as one continuous band: no gaps where it vanishes and reappears, no beaded or dotted segments, no stair steps along its banks. Name where it breaks. |
| R16-FLOW | The flow map is bright along the river course seen in the frame (the water moves there), and dark elsewhere. A fully black flow map fails when R16-RIVER-SEEN holds. |

Set P (pyramids): frames of the pyramid targets.

| ID | Line |
|---|---|
| R16-EDGE | The pyramids' neon edges read as clean continuous lines: not dotted, beaded or broken into specks, not a glittering fringe. |
| R16-KEEP | Every earlier rule holds: no holes, no seams or rings in the ground, the ground in the scene's palette. |
