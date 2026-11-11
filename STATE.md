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
- Self-check (`make blender-check`): planet 35 of 37 controls with an effect (2026-11-11), island 30 of 37 (2026-11-10); contract cross-check 0 mismatches, bridge scaling 6 of 6 live. Report: [docs/reports/blender-feature-check.md](docs/reports/blender-feature-check.md).
- `/vj/nebula` works on the planet since round 9 (Milky Way band from the star map, 247 x noise floor on CAM_10).
- Look round 9 (2026-11-11, 35 shots, [notes](docs/handover/planet-look-round9.md), [verdicts](docs/reports/planet-look-round9-verdict.json)): 26 pass. CAM_0 to CAM_3 and CAM_6 to CAM_9 pass. Open: CAM_5 pale top band in fog, CAM_4 water step, crease and night haze at fog 1, CAM_10 core glow at nebula 0, square stars at 200 mm. Moon maps at 4096 and the nebula band show no frame-time cost (context only).
- Round 10 (2026-11-11, [notes](docs/handover/planet-look-round10.md), [verdicts](docs/reports/planet-look-round10-verdict.json)): every dummy line source is out of the build (terrain lattice, orbit lattice, scroll, lattice light on the fog). No lines by day: `/vj/grid` 0 against 1 is within the noise floor on three cameras, all 12 day shots pass. The orbit night shot passes. Frame time, context only: day 35.4 to 33.9 ms, orbit night 23.9 to 20.3 ms.
- Real mesh edges show at night (Wireframe node on the terrain, strength `/vj/grid`). Round 11 (2026-11-11, [notes](docs/handover/planet-look-round11.md), [verdicts](docs/reports/planet-look-round11-verdict.json)) added relief to the plains: swells about 4 m over 320 m, knolls about 1.4 m over 90 m; faces under 1 degree in the CAM_0 foreground 57 % to 1.4 %; lakes and rivers unchanged; no camera under ground. 14 of 19 shots pass. Still failing: the night edges on smooth ground read as a regular lattice (CAM_0, CAM_1, CAM_3), and the day plain reads flat in tone (CAM_0, CAM_3). Relief cannot fix the lattice look: the cells are regular wherever the ground is smooth. Options in the note: irregular triangulation, vertex jitter, or no edges.
- Reviewer on the day land without lines: CAM_0 "a little empty", CAM_3 foreground "a flat uniform purple band".
- Round 12 (2026-11-11, [notes](docs/handover/planet-look-round12.md), [verdicts](docs/reports/planet-look-round12-verdict.json)): interior patch vertices shifted sideways by up to 0.30 of a cell, every cell split along one fixed diagonal. All 11 day shots pass. On the committed scene (179ba64) the reviewer passes CAM_0 and CAM_1 at night as an irregular net; the numbers are no better than round 11 (longest straight run 193, 269, 26 px against 196, 275, 33). The user keeps the edges as they are. Fresh opens of the committed scene draw the night edges (line share 0.12 and 0.13 on CAM_0) and `/vj/grid` (46x) and `/vj/bass` (23x) show an effect. Not solved: two earlier builds of the same code (b1154c6, 9a8d405) opened with no night edges until a node of `PL_Land` was re-evaluated; cause unknown, nothing guards against the next such build. Map paths are relative now. `/vj/flamingos`: CAM_0 has no water in view and so no flock; CAM_1 has 225 points; the self-check row still tests CAM_0. Open too: the line-motion number (pair not clean), the Flight shot's streamed terrain at full size.
- Flight (merged 2026-11-11, [notes](docs/handover/flight-presentable.md)): the runtime starts `flight_rt` on the planet; the Flight shot is `CAM_11` and `/vj/cam` goes 0..11 (contract, bridge, Magic generator). The Flight's streamed terrain draws only while the Flight shot is on air or in a blend; a fixed shot shows the planet as built (frames equal with the runtime started or stopped, within the noise floor, on CAM_0 day and night and CAM_1 day). Full self-check on the round 11 build: 35 of 37 with an effect; without: `/vj/grid_speed` (on purpose) and `/vj/flamingos` (no flock in CAM_0's view). Open: Hover arrival live 24.7 s against 10 to 15 (12 s in the model; frames were 54 ms under load); cut stalls 57 to 110 ms and idle cost 2.3 ms more with the runtime started, both under load, not judged.
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
- Blender planet, 2026-11-11: the night edges stay as they are after round 12, as a plain OSC control: `/vj/grid`, default 1. No further mesh rounds. The fresh-open bug (no edges until a node is re-evaluated) gets fixed.
- Blender planet, 2026-11-11: the terrain mesh becomes irregular so the real night edges form an uneven net (round 12).
- Blender planet, 2026-11-11: `/vj/grid` at night is the only wireframe control; no day control (`/vj/grid_day` was proposed and withdrawn the same day).
- Blender planet, 2026-11-11: the real mesh edges stay at night; the flat ground gets gentle relief so they read as terrain ("make it a little bit less flat"). The drop decided earlier that day is withdrawn.
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
