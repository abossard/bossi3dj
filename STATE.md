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
- Not working: Flight camera (`/vj/flight`, `/vj/boost`, `/vj/blend`: the runtime never starts `flight_rt`), `/vj/nebula` on the planet. `/vj/energy` and `/vj/hit` show an effect without a known reader.
- Review round 8 was grabbed on `d5e3323`; 5 of 6 reviewer groups reported, CAM_6 to CAM_8 were not reviewed. Notes: `docs/handover/planet-visual-check-round8.md`.
- Open from round 8: day wires washed out on sunlit slopes, CAM_1 bank lines, CAM_4 water step and fog terraces, CAM_5 top band, CAM_9 dotted sky, ragged limb at 10 km orbit, river stubs, moon smear.
- Flight, open: FL5 Approach and Skim frame times, Hover arrival in 10 to 15 s, M1 cut stalls. Notes: `docs/handover/flight-hover-handover.md`.
- The island scene (`synthwave_pyramids.blend`) has no build script (lost with a scratchpad).
- Local only, git-ignored: star maps (817 MB) and all review grabs (1.7 GB) under `blender/scenes/planet_proto/`.

## Godot: Colossus Scene

- Works: full Arc (Approach, Climb, Fall, Reset), 345 logic tests, OSC in on 9202, control page on 9211 with a self-check (22 of 22 headless and on Metal), values persist without packets, Syphon `COLOSSUS_OUT` (app `Godot`) at 1080p with pixel content, nothing of the page in the frame. Report: [docs/reports/godot-feature-check.md](docs/reports/godot-feature-check.md).
- Look round 2 (2026-11-11, same rubric): 19 of the 21 round 1 frames pass. Ground no longer flat black, the Colossus reads at 1.6 km (120 to 172 px of 1080), the Wanderer is in the close grip on 30 of 30 samples, `/vj/shock` works from real packets. Notes: [docs/handover/godot-look-round2.md](docs/handover/godot-look-round2.md).
- Still failing: `shot-2` and `2-approach-low-hero` lose the Wanderer on the long walk (the lens that holds the giant cannot hold him).
- Syphon publishes from frame 120 (2 s after the window opens) and the Reset holds black 2 s, because the lighting needs that long to converge.
- Frame time, context only (foreign load): median 16.7 ms, worst frame in the Arc 48 ms, Reset hitch 167 ms down to 36 ms.
- Open: real Colossus and Wanderer models (downloads need a login), stand-in ruins, a trustworthy fps table, pickup in Magic's SyphonClient, Scenario was never signed in.
- godot-mcp is installed and was never used in 43 h of work.

## OSC contract

- One source: `osc/contract.json`, 0..1 on the wire, synced into [osc/CONTROLS.md](osc/CONTROLS.md) and the Blender bridge. `magic/projects/show.magic` drives both scenes, not yet loaded in Magic. 

## Decided by the user

- Contract: every continuous `/vj/*` control is 0..1 on the wire, each scene scales it to its own range; the wire default gives each scene its tuned look. Indices (`/vj/cam`) stay integers, triggers keep their strength.
- Blender, 2026-11-11: no wireframe by day (0 up to sunset, fading in toward night), and lines never move over the terrain on the planet: no grid scroll, `/vj/grid_speed` is island only.
- Godot low hero shot on the long walk keeps the Wanderer in frame, the giant may shrink below 60 px (2026-11-11).
- `/vj/cam` N picks each scene's Nth shot (0-based, clamped to what the scene has). New `/vj/cam_auto` (0 or 1, default 1) hands the cuts to the scene's own director: Godot follows it, Blender ignores it.

## Waiting for the user

- Eclipse in space: the moon's shadow on the Planet, or lining up per space camera.
- Bend the straight show valley, or keep it.
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
