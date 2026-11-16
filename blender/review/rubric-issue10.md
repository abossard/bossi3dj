# Rubric: issue #10, holes and a pale ring on mountain ridges

Frozen before the live A/B (`ridge_check.py`). Each shot comes as a pair, `_before` (fix off) and `_after` (fix on), same pose and same seconds.

- **I10-HOLE**: no see-through patch on any ridge or peak in `_after`. A see-through patch shows sky, far land or a dark pit where the mountain's own surface should be. Pass when none.
- **I10-RING**: no pale, wet-looking or cyan ring round a peak or along a ridge line in `_after`. Pass when none.
- **I10-SAME**: away from ridges and peaks (valleys, plains, coasts, the pyramids, water), `_after` looks like `_before`. Pass when no difference stands out.
- **I10-COAST**: shores and the land's edge at the water read as clean as or cleaner than `_before`: no new specks, fringes or stair steps. Pass when none.
