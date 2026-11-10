# Planet grafted into the official scene (planet session, 2026-11-04 13:40)

Live now, only Blender running: `blender/scenes/synthwave_planet.blend` (PID 8220, user prefs, Blender MCP connected,
OSC 9201 with Magic, web 9210, Syphon on). The island file `synthwave_pyramids.blend` (12:13 save) is untouched.

## How it is made
- `blender -b --factory-startup -Y scenes/synthwave_pyramids.blend --python scenes/planet_proto/build_planet.py -- --graft`
  (branch `research/synthwave-planet`, worktree `.claude/worktrees/nostalgic-mayer-2bcf15`). Writes `scenes/synthwave_planet.blend`.
- Kept from the island: runtime + bridge texts, VJ_* shader groups (fog bank, sky, sun, colour, phase, meteor), sun/corona/moon
  (pushed to 150/120 km), nebula, pyramids (dropped onto the planet plaza), flamingos (re-seeded in shallows), render settings, bloom.
- Removed: Terrain, Sea, Sea_Far, Land_Mirror, island cameras. New: Planet, Water, Props, Sea_Backdrop, Atmosphere, Planet_Hydro (hidden),
  LOD_Anchor, CAM_0..CAM_6 (island roles; CAM_6 orbits the planet). planet_runtime.py moves the LOD anchor on cuts.
- Save perf changes into synthwave_pyramids.blend (render settings, VJ_* groups) and a rebuild carries them over. Planet materials
  (Terrain, Sea, Sea Backdrop, Atmosphere, Pyramid, Palm) and GN live in build_planet.py: ask me for changes there.

## Live fps (rendered, region 2832x1893, day, vj_fog 0.35, vj_cam held), before the two shader changes below
| cam | 0 | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|---|
| island (your baseline) | 18.3 | 15.6 | 24.9 | 18.6 | 15.3 | 22.6 | 16.2 |
| planet | 17.5 | 40 | 53 | 55 | 27 | 44 | 28.5 |

## Changed live at about 13:30 (unsaved in the live file, already in build_planet.py)
1. material `Sea`: Bump Height = ripples only (no wave/shock lift).
2. material `Sea Backdrop`: VJ_Sky -> VJ_SkyBase on the mirrored direction, x0.7.
Rough (collided with your harness): CAM_4 about 40, CAM_6 about 33, CAM_0 about 21.

## Planet-side levers I can apply on request
- `Planet`/`Water` modifier inputs: Detail (0.03 rad per cell, bigger = coarser), Max Level (6), Mirror Distance (6000 m, 0 = no mirror).
- Props Distance (5000 m). Water material: drop the flow-mapped ripples (2 noise), drop shock rings in the sea.
- Terrain material: drop the night grid / shock-ring grid warp (4 slots per pixel).
- Atmosphere shell off below 2 km (rt_space already zeroes its emission, but it still rasterizes).
