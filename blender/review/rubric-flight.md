# Synthwave Planet, Flight shot review rubric

Frozen before the first grab of the Flight review (2026-11-12). It does not change during the round. Frames are full size (1920x1080), named `<stage>_<look>` with stage `orbit`, `approach`, `skim`, `hover` and look `day`, `night_grid1` (`/vj/night` 1, `/vj/grid` 1), `night_grid0` (`/vj/grid` 0). A shot passes when every line that applies holds; a failed line names its id and where in the frame.

| ID | Line |
|---|---|
| FL-WHOLE | The terrain is whole: no hole, missing block, black or sky-coloured gap, crack or seam between blocks, no floating or dropped tile. Coarser detail in the distance is fine. |
| FL-WATER | `hover_*`: the camera is over water and water fills a clear part of the frame, with a shore line, not a wall of water and no gap between water and shore. Elsewhere water that is in view is intact. |
| FL-DUMMY | No dummy lines: no grid, lattice or line pattern on land, water or in the sky by day, and at night no lines that do not follow the terrain's own faces. By day (`*_day`) no lines at all. |
| FL-EDGES | `*_night_grid1`: the night edges on the land read as an uneven net that follows the terrain (as on the fixed shots), or are absent. `*_night_grid0`: no edges. |
| FL-SKY | Horizon and sky read as on the fixed shots: a curved or straight horizon with sky above it, sun or stars and moon where they belong, no hard band, box edge or step in the fog or sky. |
