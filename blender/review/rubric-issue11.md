# Rubric: issue #11, far small pyramids' base edges read dashed

Frozen before the live A/B (`ridge_check.py` with the `pyr_base_band` switch). Each shot is a pair from the same pose and seconds: `_before` (round 17's edge strip along the base) and `_after` (the base band: glows from the land up to a level line over the base). Judge the small, far site pyramids, not the large near island pyramids (their edges are tubes, unchanged).

- **I11-DASH**: in `_after` no far pyramid's base line is broken into dashes or dots. Pass when every visible base line is continuous.
- **I11-LINE**: the base band reads as the pyramid's foot outline, about as thin as its ridge edges; not a thick glowing collar, a stripe partway up the faces, or a halo on the land. Pass when none.
- **I11-SAME**: the ridges, faces, capstones and the land look as in `_before`. Pass when no difference stands out.
