# Rubric: regional water map and river flow (2026-11-15)

The user (2026-11-15): "yes regional water map". The brief: rivers under 25 m drawn; the river flow spread over the drawn water, ripples readable from 100 m to 1 km. Frozen before the review.

Numbers (`blender/review/water_map_check.py`, `river_check.py`): inland water drawn at 4 m against 12 m over the region; the share of wet texels with flow; frame time with the region on and off on the same poses.

Images: five fixed camera poses (river shots, about 100 m to 1 km from the water), each in three builds: A (before: 12 m map, flow on the centre line), B (12 m map, flow spread over the water, river ripple bands), C (B plus the regional 4 m map). Per build and pose the first and the last frame of a 3.5 s still-camera capture with the idle pulse off: only the water's own animation changes between them.

- **RW-RIVER**: the river reads as one continuous body of water with clean banks, no gaps, stair steps or dark texel blocks.
- **RW-RIPPLE**: on the river the ripple pattern is visible at the distance shown, and it has visibly moved between the first and the last frame (the flow), not frozen and not a flicker of noise.
- **RW-SEAM**: no line, step or change of detail where the regional map ends or blends (C only).
- **RW-COHERENT**: the river's ripples fit the scene's water (sea and lakes), not a different material; no bright or dark patches the flow alone causes.
