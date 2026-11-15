# Rubric round 18: the idle pulse on the pyramids

The user (2026-11-15): "Stronger idle pulse". With no `/vj/beat` from Magic the runtime's idle pulse (124 BPM) drives the pyramids' glow. Frozen before the review.

Numbers (`blender/review/pulse_check.py`, orbit pyramids 0.15, held still):

- **N18-IDLE**: the idle pulse swings the pyramids' mean luminance 25 to 30 % by day.
- **N18-CAP**: a full beat (rt_pulse 1) is no brighter than in round 17 (+43 % by day); at night the idle peak stays below the full beat's.

Images (frames of `docs/video/gpu-terrain-idle-pulse.mp4` at full size, in time order, about 17 new frames a second):

- **R18-VISIBLE**: across the consecutive frames the pyramids visibly brighten and dim about twice a second, the whole pyramid at once.
- **R18-CALM**: the pulse reads as a glow, not a strobe: no frame where the pyramids flash white or lose their faces and edges, the land and sky do not pulse with them.
- **R18-COHERENT**: the pyramids stay part of the scene at their brightest (no clipped white blobs, colours kept).
