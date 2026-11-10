# Planet waterline v2 (commit 8f1f555 on research/synthwave-planet)

- Sea material: `use_transparency_overlap = False`, `use_backface_culling = True`. Fixes flat patches on rivers (water under a bank drawn over the river through the cut-away bed). It should also cut water overdraw, the main per-pixel cost in perf-planet-full-pass.md. Not measured yet.
- Hydrology: exact depression fill (24 relaxation rounds after pointer jumping). No lakes where Mountain >= 0.1. Lakes now cover 1.8% of the sphere (was 4.7%, half of it false), with 135 rivers.
- River bed is carved 2-3 m deep. It used to sit exactly at the water surface because of a clamped bank term.
- At 17:00 the user's GUI Blender has synthwave_planet.blend open. The material change is applied there live through MCP. The file on disk still predates the material change: rebuild with `--graft` once that Blender is closed.
