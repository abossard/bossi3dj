# Full perf pass, feature-complete planet (synthwave_planet.blend)

Drawn fps (Syphon frames/s), M1 Max, Blender 5.2.3. Beat sim: a shockwave every 4 beats. vj_fog 0.65. OSC held during runs. Moving cameras: 6 s settle after a cut, 4 s measure. Every cell was checked to be in camera view.
Live scene left as built (32f7bee): all tests restored, OSC holds released, sim off.

## Baselines, mean of CAM_0..10 (day / twilight / night)
| build | day | twilight | night | slowest |
|---|---|---|---|---|
| island scene (12:13 save, before) | 18.8 | 20.2 | 18.2 | CAM_1 ~14 |
| first planet graft, no border/dedupe | 30.3 | 34.2 | 33.2 | CAM_0 ~17 |
| first planet graft + border + dedupe | 47.7 | 50.7 | 41.9 | CAM_0 31-45 |
| feature-complete 2c99540 | 26.1 | 25.6 | 24.6 | CAM_0 16 |
| 32f7bee (Spots_Pyramids rename, new waterline) | 46.2 | 47.0 | 40.1 | CAM_8 25-29 |

## Ranked changes
| change | fps before → after | visual | status |
|---|---|---|---|
| Pyramid_Spots → Spots_Pyramids. The runtime moved it every frame as a "Pyramid_*", which re-ran the whole Flock_Birds scatter | day CAM_0 26 → 45, CAM_3 30 → 57; night CAM_0 26 → 43. Mean of 11 cams: 26 → 46 | same (also stops every 5th shockwave starting at the spots object) | in build 3bb07b0 |
| render.use_border 0..1 | frozen CAM_0 25.5 → 44.4; first graft +50% | identical | in build and build_world.py |
| shader_dedupe.py (one Attribute per name, one input-less group, per tree) | frozen A/B 40.7 → 49.6 | identical | in build and build_world.py |

## Measured on 32f7bee without gain (day, mean of CAM_8/7/10/0, base 36.0-40.8)
Detail 0.04: 36.5. Mirror Distance 0: 36.2. Atmosphere hidden: 38.1. Sea_Backdrop hidden: 37.4. Reflections modifiers off: 38.5. Max Level 6: 38.9 (earlier build: +15%).

## Where the remaining time goes (day, same 4 cams, base ~38)
| upper bound / variant | fps | note |
|---|---|---|
| Water hidden | 61.3 | water is 39k tris, so the cost is per pixel |
| VJ_Fog bypassed (all materials) | 58.2 | |
| Fog removed from the Sea material only | 53.8 | most of the fog cost is on the water |
| Sea ripple Bump removed (geometry normal) | 53.3 | the Bump evaluates the ripple graph (2 noises + 4 shock rings) about 3x per pixel |
| Sea DITHERED | 42.6 | look change (stochastic transparency), not kept |
| Sea backface culling | 46.4 | visible: large parts of the water vanish (faces point away). Rejected |
| Sea transparency overlap off | 44.0 | visible, same diff as culling. Rejected |

The water's cost is overdraw: blended water layers each run the full shader, including fog and the 3x bump. Both culling tests prove the overdraw exists, but removing it changes the water. Options for the water owner, each needing a look check:
- orient the water faces upward (consistent normals), then backface culling becomes free;
- make the ripple Bump cheaper (fewer noise octaves, or no shock rings in the bump);
- apply the fog on the water once, not per layer.
Other open lever: a day-only world (+11% by day, exact only at vj_night 0).
Runtime robustness: select pyramids by the Pyramids collection, not the "Pyramid_" prefix.

## Day-only world (approved by the user), proven live on PID 84605
- Module scenes/day_world.py: make(world, cut) builds "<world> Day" plus "VJ_Sky Day" with the night-only layers unlinked, and sets fake users on both worlds. sync(scene) shows the day world while vj_night <= 0 and rt_space <= 0.
- Hooks: synthwave_runtime (design session), build_planet.py (planet session, with the 240-star cut), build_world.py (default cut, not run).
- Side by side on CAM_8 (off-pole, frozen, scene re-tagged every 0.1 s):
  - noise floor between two grabs: mean 0.95, p99 16;
  - day vs full at vj_night 0: mean 0.99, p99 17;
  - cold first switch (shader not yet compiled), 3 grabs right after: mean 0.6 to 0.99;
  - full at vj_night 0.001 vs day at 0: mean 0.53, p99 11.
  All at noise level, so no pop.
- fps A/B, frozen CAM_8, 3 rounds: 25.7 → 30.6 (+19%).
- Test gotcha: with synthwave_tick removed nothing re-tags the scene, so after a cut a world keeps stale VJ_Frame (rt_up_*) attributes and shows a tilted sky band. Re-tag the scene, or compare only after a fresh tag.
- The live instance is restored: full world only, day copy removed, OSC hold back to vj_fog only, sim off, camera view, Syphon publishing. The web control page was cutting cameras during the test, so I blocked web writes for the test; that is restored.

## Final pass (PID 37861, 39a18a4 + live runtime upgrade, day world active)
Drawn fps, beat sim with a shockwave every 4 beats, vj_fog 0.65, CAM_0..10, all cells in camera view:
| state | mean | per camera 0..10 |
|---|---|---|
| day | 59.2 | 63.4 51.9 77.4 76.7 78.7 69.3 44.3 43.3 30.4 64.5 51.2 |
| twilight | 52.2 | 54.4 47.0 63.1 60.2 58.8 52.5 53.1 40.6 28.6 60.8 55.3 |
| night | 53.2 | 59.3 48.0 65.1 60.3 61.3 59.4 46.1 41.4 27.4 58.8 57.9 |
The day world was active in 10 of 11 day cells. CAM_6 (high orbit, rt_space > 0) correctly used the full world. Twilight and night used the full world.
Left running: no OSC holds, sim off, camera view, Syphon publishing.

## Water LOD check (5987ed0, PID 53020, Godot running: pause was refused by the permission check)
A/B in the same instance: LOD as built (Sea Far beyond 500 m of the shot's anchor) vs off (threshold 1e9, all water Sea = the look before).
Look, frozen day, per-pixel diff of every camera:
- identical (wire noise only): CAM_0, 2, 3, 4, 5, 6, 9;
- visible: CAM_1 (river patch gone, far-left river ripple texture smoother), CAM_7 (pale sawtooth band in the near water gone), CAM_8 (pale layer and banding over the river and far sea gone), CAM_10 (white patches in the lower water gone).
Cause: those patches are back faces of water 7 to 10 km away (far side of the planet), seen through the near transparent water. Ray cast at the CAM_1 patch: Sea at 62 m (front), Sea Far at 7459 m (back face). A distance LOD sets them to Sea Far, which culls them, so it cannot keep the CAM_1 river patch.
fps, moving cams, beat sim, LOD on / off, mean of CAM_0..10: day 54.7 / 54.6, twilight 41.1 / 41.0, night 34.9 / 33.7.
CAM_8 moving: day 52.7 / 49.1, twilight 38.6 / 35.5, night 36.6 / 32.9. Other cells swing ±30% (Godot).
Frozen CAM_8 A/B, 3 rounds: night 47.0 / 46.5 (no gain); day 30-51 both ways (too noisy).
Per camera, day / twilight / night, LOD on / off:
0: 56.8/57.8 45.9/45.9 40.3/29.8 | 1: 51.9/47.1 47.8/28.1 26.8/26.8 | 2: 58.1/59.9 33.3/46.2 30.3/42.1 | 3: 58.5/59.0 45.7/32.4 28.5/29.8
4: 58.5/59.5 31.7/56.2 30.8/30.7 | 5: 58.2/54.8 56.5/48.2 43.9/43.1 | 6: 47.8/57.5 50.2/47.3 42.3/43.2 | 7: 52.1/52.3 35.6/39.4 37.2/35.3
8: 52.7/49.1 38.6/35.5 36.6/32.9 | 9: 60.0/60.0 29.8/34.3 39.0/28.7 | 10: 46.7/43.8 37.5/38.0 28.4/27.8
Day sits near 60 on most cameras (cap). Left running: LOD as built, no holds, sim off, camera view, Syphon publishing.
