# Global perf levers on the live planet scene (synthwave_planet.blend, PID 8220)

M1 Max, Blender 5.2.3, region 2832x1893, preview pixel size AUTO (= 2 on this Retina screen). Drawn fps = Syphon sender frames/s.
Beat sim: a shockwave every 4 beats. vj_fog 0.65. OSC held for vj_cam/night/fog/hue/beat/bass/level/shock during runs.
- "Frozen" = clocks stopped (synthwave_tick removed) and all /vj/* held, CAM_0 day. Moving cameras give ±30% noise, frozen about ±5%.
- Visual check = full-res Syphon grab, side by side, per-pixel diff. Noise floor between two grabs of the same frame: mean 0.2/255, p99 5 to 7.

## Ranked

| change | fps before → after | visual | kept |
|---|---|---|---|
| render.use_border on, 0..1 | frozen 25.5 → 44.4. Moving, mean of 7 cams: day 33.0 → 51.0, twilight 36.2 → 51.8, night 33.5 → 49.7 | identical (mean diff 0.25) | yes |
| scenes/shader_dedupe.py: one Attribute node per name, and one call per input-less group, in each tree | frozen with border: A/B 3 rounds, 40.7 → 49.6 | identical (mean diff 0.2) | yes |
| Both, final matrix, mean CAM_0..6 | day 30.3 → 47.7, twilight 34.2 → 50.7, night 33.2 → 41.9. CAM_0: 17.2 → 45.4, 19.0 → 37.6, 19.3 → 30.6 | identical | yes |
| VJ_Sky night-only layers cut out by day (only exact at vj_night 0) | frozen, with dedupe: A/B 47.8 → 53.2 | identical at vj_night 0 only | no. Follow-up: a second day-only world switched by the runtime |
| Compositor off | about +40% (moving) | loses bloom | no |
| Fog: VJ_Fog bypassed / ground fog only removed | frozen 46 → 57 / 46 → 56 | loses fog | no |
| All Attribute nodes as uniforms (upper bound for the lookups) | frozen 46 → 59 | n/a | no |
| Bloom quality Low | frozen 46 → 45 | edges of thin wires differ slightly | no (no gain) |
| Fog: 2 of 6 march samples dropped / noise detail 1 or 0 | frozen 46 → 46.5 / moving no gain | n/a | no (no gain) |
| World probe 128, world sun extraction off, volume tile 16 / samples 32 | no gain | n/a | no |

## Applied
- build_world.py (backup: build_world_v_before_perf.py): render border in the render section; dedupe_all() before the CAM_OUT section. Not run: one Blender at a time, and the island .blend is not to be saved from the planet instance.
- The live planet instance has the border and dedupe applied, both pixel-identical and not saved. Everything else is restored, OSC holds are released and the sim is off.
- README scene section: performance paragraph with these numbers.
