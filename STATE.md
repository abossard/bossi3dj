# State

Updated 2026-11-10. Keep this file short and current: where each stream stands, what is open, what waits for the user. Details go to `docs/handover/`.

## Now

- Run to presentable: graph, nodes and rules in [docs/handover/presentable-plan.md](docs/handover/presentable-plan.md). Integration branch `integration/presentable`.

## Origin

- Imported on 2026-11-10 from `abossard/swift-vj` at `f7094fb` (fresh import, history stays there).
- Old to new: `Tools/magic-blender-lab/scenes` is `blender/scenes`, `blender_osc_bridge.py` is `blender/`, `lab.py` is `osc/`, the Magic tooling is `magic/`, `Tools/godot-colossus` is `godot/colossus`.
- SHAs in hand-over notes (`d5e3323`, `32f7bee`, `39a18a4`) are swift-vj commits.

## Blender: Synthwave Planet Scene

- Works: planet build, star system with eclipses, 11 cameras, per-camera LOD, volumetric fog box, streaming LOD, Syphon and OSC. Self-check (`make blender-check`, 2026-11-10): 30 of 37 controls have an effect.
- Not working in the shipped scene: Flight camera and Energy controls (`/vj/flight`, `/vj/boost`, `/vj/blend`, `/vj/energy`, `/vj/hit`: the runtime never starts `flight_rt`), `/vj/hue`, `/vj/grid_speed`, `/vj/nebula`. Report: [docs/reports/blender-feature-check.md](docs/reports/blender-feature-check.md). Day mean 59 fps (M1 Max, 2026-11-05).
- Review round 8 was grabbed on `d5e3323`; 5 of 6 reviewer groups reported, CAM_6 to CAM_8 were not reviewed. Notes: `docs/handover/planet-visual-check-round8.md`.
- Open from round 8: day wires washed out on sunlit slopes, CAM_1 bank lines, CAM_4 water step and fog terraces, CAM_5 top band, CAM_9 dotted sky, ragged limb at 10 km orbit, river stubs, moon smear.
- Flight, open: FL5 Approach and Skim frame times, Hover arrival in 10 to 15 s, M1 cut stalls. Notes: `docs/handover/flight-hover-handover.md`.
- The island scene (`synthwave_pyramids.blend`) has no build script (lost with a scratchpad).
- Local only, git-ignored: star maps (817 MB) and all review grabs (1.7 GB) under `blender/scenes/planet_proto/`.

## Godot: Colossus Scene

- Works: full Arc (Approach, Climb, Fall, Reset), 263 logic tests, OSC in on 9202, Syphon `COLOSSUS_OUT` at 1080p, control page on 9211 with a self-check (`make godot-check`, 22 of 22 headless), values persist without packets. Not yet seen on Metal. Report: [docs/reports/godot-feature-check.md](docs/reports/godot-feature-check.md).
- Open: real Colossus and Wanderer models (downloads need a login), stand-in ruins, the Colossus is lost in haze beyond 450 m, 60 fps with Blender closed is unmeasured, pickup in Magic's SyphonClient was never checked, Scenario was never signed in.
- godot-mcp is installed and was never used in 43 h of work.

## OSC contract

- One source: `osc/contract.json`, 0..1 on the wire, synced into [osc/CONTROLS.md](osc/CONTROLS.md) and the Blender bridge. `magic/projects/show.magic` drives both scenes, not yet loaded in Magic. Bridge scaling not yet observed in a live Blender.

## Decided by the user (2026-11-10)

- Contract: every continuous `/vj/*` control is 0..1 on the wire, each scene scales it to its own range; the wire default gives each scene its tuned look. Indices (`/vj/cam`) stay integers, triggers keep their strength.
- `/vj/cam` N picks each scene's Nth shot (0-based, clamped to what the scene has). New `/vj/cam_auto` (0 or 1, default 1) hands the cuts to the scene's own director: Godot follows it, Blender ignores it.

## Waiting for the user

- Eclipse in space: the moon's shadow on the Planet, or lining up per space camera.
- Bend the straight show valley, or keep it.
- Start the next Flight session.
- Keep godot-mcp, or remove the addon and autoload.
- Sketchfab and Mixamo downloads; Scenario OAuth.

## Checked after the import (2026-11-10)

- `make magic-test` 35 pass, both generators reproduce the committed `.magic` files with 0 differences.
- `make godot-test` 71 pass, `make godot-smoke` passes, `make godot-lint` clean.
- Both scene `.blend` files resolve all external paths relative to the repo.
- Live: `make blender-open` (planet) came up in camera view with runtime, bridge and Syphon running, `health.py` reported no problems, 12 of 12 OSC messages sent to udp 9201 were applied, and a grabbed Syphon frame (1920x1080) showed the scene.
- That grab (`magicproj.py grab --app Blender --server CAM_OUT`) was vertically flipped. Not checked in Magic, which is the consumer that counts.
- `verify_flight.py` fails `5d descend: changes of more than one depth in a frame`, the same in swift-vj at `f7094fb`. `verify_star_system.py` needs `make venv` and was not run.
- Not run after the import: Godot on Metal (`make godot-capture`), Godot Syphon, `make blender-rebuild`, the Magic projects inside Magic, the lock hook inside a live agent session (pipe-tested only).
