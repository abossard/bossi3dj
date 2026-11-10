# Playback fps baseline (planet session, 2026-11-04 ~12:55)

Only one Blender running (live instance stopped on the user's request), GUI Blender 5.2.3,
`--factory-startup -Y`, built-in display (120 Hz), 3D view full area, camera view,
region 1920x1080 px, rendered shading, compositor on. Clocks advanced by a frame handler.
Script: `blender/scenes/planet_proto/bench_fps.py` (branch claude/nostalgic-mayer-2bcf15).

| scene | camera | fps | frame ms p50 / p95 | tris |
|---|---|---|---|---|
| synthwave_pyramids.blend (copy of 12:13 save) | CAM_0 ground | 24.6 | 31.0 / 43.0 | 1,235,404 |
| same | CAM_4 flyover | 23.1 | 42.6 / 52.8 | 1,235,404 |
| same | CAM_6 high orbit | 22.6 | 43.8 / 50.1 | 1,235,404 |
| planet_proto.blend | ground (pyramids, lake, fog) | 25.9 | 26.9 / 47.6 | 162,506 |
| planet_proto.blend | flyover 140 m above terrain | 58.2 | 17.0 / 19.0 | 126,184 |
| planet_proto.blend | flyover, LOD anchor on camera every frame | 6.7 | 155 / 211 | 137,410 |
| planet_proto.blend | orbit, whole planet | 49.0 | 20.4 / 23.1 | 91,774 |

Takeaways for scene-perf:
- Cutting triangles 8x does not move the ground shot (24.6 vs 25.9 fps): ground shots are bound by
  per-pixel cost (fog volume near the camera, blended water over the mirror, sky/haze shaders), not geometry.
- The island loses little between views (22.6-24.6), the planet doubles when the camera is above
  the fog layer: the volume and the low-angle water are the likely big items.
- Live instance while a second Blender ran: 15-23 fps before, 4-12 fps during. Never benchmark two at once.
