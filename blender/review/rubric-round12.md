# Synthwave Planet, review round 12 rubric

Frozen before the first change of round 12. It does not change during the round. File names as in round 11 (`CAM_<n>_<day|night>_...`, night pair tag `grid0` / `grid1`, flyover pair tag `fly_a` / `fly_b`, orbit hand-over tag `handover`). A shot passes when every line that applies holds; a failed line names its id and where in the frame. Counterexample of what must never appear: the reference image given with the call.

| ID | Line |
|---|---|
| R12-NET | At night with `/vj/grid` 1, the edges form an uneven net of triangles on plains and smooth slopes: no family of evenly spaced parallel lines and no run of straight collinear edges across more than about five cells, anywhere larger than a tenth of the frame. |
| R12-R10 | The round 10 rules hold: no lines by day on land or water, no pattern that is not a mesh edge (counterexample: the reference image), lines do not move against the terrain while the camera and the LOD stand still. |
| R12-DAY | By day the land's shape and shading are no worse than in round 11: no new faceting, cracks, holes or seams at patch borders. |
| R12-WATER | Water is intact: no new lakes or puddles on the plains, no water standing as a wall, no gap between water and shore, rivers run in their channels as before. |
