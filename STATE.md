# State

Updated 2026-11-11. Keep this file short and current: where each stream stands, what is open, what waits for the user. Details go to `docs/handover/`.

## Now

- Run to presentable: graph, nodes and rules in [docs/handover/presentable-plan.md](docs/handover/presentable-plan.md). Integration branch `integration/presentable`.

## Origin

- Imported on 2026-11-10 from `abossard/swift-vj` at `f7094fb` (fresh import, history stays there).
- Old to new: `Tools/magic-blender-lab/scenes` is `blender/scenes`, `blender_osc_bridge.py` is `blender/`, `lab.py` is `osc/`, the Magic tooling is `magic/`, `Tools/godot-colossus` is `godot/colossus`.
- SHAs in hand-over notes (`d5e3323`, `32f7bee`, `39a18a4`) are swift-vj commits.

## Blender: Synthwave Planet Scene

- Works: planet build, star system with eclipses, 11 cameras, per-camera LOD, volumetric fog box, streaming LOD, Syphon and OSC. Both scenes run the runtime and bridge from the files on disk (`vj_loader.py`); `make blender-open` waits for a checked start state.
- Self-check (`make blender-check`, 2026-11-10): planet 33 of 37 controls with an effect, island 30 of 37; contract cross-check 0 mismatches, bridge scaling 6 of 6 live. Report: [docs/reports/blender-feature-check.md](docs/reports/blender-feature-check.md).
- `/vj/nebula` works on the planet since round 9 (Milky Way band from the star map, 247 x noise floor on CAM_10).
- Look round 9 (2026-11-11, 35 shots, [notes](docs/handover/planet-look-round9.md), [verdicts](docs/reports/planet-look-round9-verdict.json)): 26 pass. CAM_0 to CAM_3 and CAM_6 to CAM_9 pass. Open: CAM_5 pale top band in fog, CAM_4 water step, crease and night haze at fog 1, CAM_10 core glow at nebula 0, square stars at 200 mm. Moon maps at 4096 and the nebula band show no frame-time cost (context only).
- Round 10 (2026-11-11, [notes](docs/handover/planet-look-round10.md), [verdicts](docs/reports/planet-look-round10-verdict.json)): every dummy line source is out of the build (terrain lattice, orbit lattice, scroll, lattice light on the fog). No lines by day: `/vj/grid` 0 against 1 is within the noise floor on three cameras, all 12 day shots pass. The orbit night shot passes. Frame time, context only: day 35.4 to 33.9 ms, orbit night 23.9 to 20.3 ms.
- Real mesh edges at night were tried and failed review on the flat plain (its mesh is a regular grid). The user dropped them on 2026-11-11: the planet has no lines at all, `/vj/grid` is island only. Removal from the build is in progress.
- Reviewer on the day land without lines: CAM_0 "a little empty", CAM_3 foreground "a flat uniform purple band".
- Flight (branch `blender/flight`, not merged, never run live): the runtime starts `flight_rt` on the planet, self-check rows exist, Hover arrival in the model 12 s worst. `make verify` passes (348 checks). Notes: [flight-presentable.md](.claude/worktrees/blender-flight/docs/handover/flight-presentable.md) in the worktree.
- `/vj/energy` and `/vj/hit` showed an effect without a reader because one strong cell counted in the self-check; on `blender/flight` a lone strong cell is repeated before it counts.
- Blender is 5.3.0 since 2026-11-11, settings copied from 5.2 (a fresh 5.3 folder had no MCP add-on and opened out of camera view).
- M1 cut timing: 11 of 84 cuts over 70 ms at load 86, not judged. No fps table yet.
- The island scene (`synthwave_pyramids.blend`) has no build script (lost with a scratchpad).
- Local only, git-ignored: star maps (817 MB) and all review grabs (1.7 GB) under `blender/scenes/planet_proto/`.

## Godot: Colossus Scene

- Works: full Arc (Approach, Climb, Fall, Reset), 345 logic tests, OSC in on 9202, control page on 9211 with a self-check (22 of 22 headless and on Metal), values persist without packets, Syphon `COLOSSUS_OUT` (app `Godot`) at 1080p with pixel content, nothing of the page in the frame. Report: [docs/reports/godot-feature-check.md](docs/reports/godot-feature-check.md).
- Look rounds 2 and 3 (2026-11-11, same rubric, 357 logic tests): 19 of the 21 round 1 frames pass. Ground no longer flat black, the Colossus reads at 1.6 km, the Wanderer is in the close grip on 30 of 30 samples, `/vj/shock` works from real packets. Notes: [docs/handover/godot-look-round2.md](docs/handover/godot-look-round2.md).
- Still failing: `shot-2` and `2-approach-low-hero`. The low hero shot now holds the Wanderer whole in frame (probe), but the reviewer cannot see him: a dark stand-in of about 19 px on dark ground. Left for the real model.
- Syphon publishes from frame 120 (2 s after the window opens) and the Reset holds black 2 s, because the lighting needs that long to converge.
- Frame time, context only (foreign load): median 16.7 ms, worst frame in the Arc 48 ms, Reset hitch 167 ms down to 36 ms.
- Open: real Colossus and Wanderer models (downloads need a login), stand-in ruins, a trustworthy fps table, pickup in Magic's SyphonClient, Scenario was never signed in.
- godot-mcp is installed and was never used in 43 h of work.

## OSC contract

- One source: `osc/contract.json`, 0..1 on the wire, synced into [osc/CONTROLS.md](osc/CONTROLS.md) and the Blender bridge. `magic/projects/show.magic` drives both scenes, not yet loaded in Magic. 

## Decided by the user

- Contract: every continuous `/vj/*` control is 0..1 on the wire, each scene scales it to its own range; the wire default gives each scene its tuned look. Indices (`/vj/cam`) stay integers, triggers keep their strength.
- Blender planet, 2026-11-11: no lines at all, also no real mesh edges at night.
- Blender planet, 2026-11-11, hard rule: never a dummy wireframe, on the ground or from orbit, at any time of day. Dummy is every line pattern that is not the edge set of the drawn mesh (today: the 24 m `WIRE_CELL` lattice and the 600 m `ORBIT_LATTICE` in `build_planet.py`). The real mesh edges may show from sunset to night, no lines by day. `/vj/grid_speed` is island only.
- Godot, 2026-11-11: bring in the real Colossus and Wanderer models now, to learn their cost early. Target: looks great at very high frame rate, tricks allowed. Model pages are in `godot/colossus/docs/SPEC.md`.
- Godot low hero shot on the long walk keeps the Wanderer in frame, the giant may shrink below 60 px (2026-11-11).
- `/vj/cam` N picks each scene's Nth shot (0-based, clamped to what the scene has). New `/vj/cam_auto` (0 or 1, default 1) hands the cuts to the scene's own director: Godot follows it, Blender ignores it.

## Waiting for the user

- Eclipse in space: the moon's shadow on the Planet, or lining up per space camera.
- Bend the straight show valley, or keep it.
- Keep godot-mcp, or remove the addon and autoload.
- Sketchfab and Mixamo downloads (links sent 2026-11-11); Scenario OAuth.

## Checked after the import (2026-11-10)

- `make magic-test` 35 pass, both generators reproduce the committed `.magic` files with 0 differences.
- `make godot-test` 71 pass, `make godot-smoke` passes, `make godot-lint` clean.
- Both scene `.blend` files resolve all external paths relative to the repo.
- Live: `make blender-open` (planet) came up in camera view with runtime, bridge and Syphon running, `health.py` reported no problems, 12 of 12 OSC messages sent to udp 9201 were applied, and a grabbed Syphon frame (1920x1080) showed the scene.
- That grab (`magicproj.py grab --app Blender --server CAM_OUT`) was vertically flipped. Not checked in Magic, which is the consumer that counts.
- `verify_flight.py` fails `5d descend: changes of more than one depth in a frame`, the same in swift-vj at `f7094fb`. `verify_star_system.py` needs `make venv` and was not run.
- Not run after the import: Godot on Metal (`make godot-capture`), Godot Syphon, `make blender-rebuild`, the Magic projects inside Magic, the lock hook inside a live agent session (pipe-tested only).
