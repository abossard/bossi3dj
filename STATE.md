# State

Updated 2026-11-11. Keep this file short and current: where each stream stands, what is open, what waits for the user. Details go to `docs/handover/`.

## Now

- 2026-11-11: the Godot Colossus Scene is parked by the user ("too ugly to be honest"). Nothing more is built there until the user says so. State, reasons and open tasks: [docs/handover/godot-parked.md](docs/handover/godot-parked.md); the README marks it as parked.
- 2026-11-12, the user: "just do all, please. End to end. Complete the work, handbook, website to control it, OSC integration in MMV". Two sessions run: B10 finishes the planet (Flight shot, day look and camera items as round 13, missing manual pictures, island check, fps table; notes `docs/handover/planet-finish.md`) and holds Blender; B11 writes the handbook (`docs/handbook.md`), completes the control page on 9210 and proves Magic to Blender to Magic (notes `docs/handover/handbook-page-magic.md`), Blender-free part first. Third stream, in the reused B9 session (448k tokens of context when it started): Art-Net input in the bridge and a QLC+ fixture generated from the contract (`docs/artnet-qlc.md`), Blender-free part first; the live test needs the user's QLC+ and the Blender slot.
- 2026-11-12, where the streams stand ([planet-finish.md](docs/handover/planet-finish.md), [handbook-page-magic.md](docs/handover/handbook-page-magic.md), [artnet-qlc.md](docs/artnet-qlc.md)): B10 planet: Flight batch done (the stream now draws its water, the sky follows the Flight, no edges on the stream, settable seed; review 3 of 12 before, 9 of 12 after; the three Approach frames still show holes along the shores); round 13 done (plains shaded by slope, night haze, nebula glow and square stars fixed: 26 of 35 entries pass; open: the CAM_4 crease and water step, the CAM_5 band); the four missing manual pictures exist; frame-time table recorded under load (context only); self-check 36 of 37. The green lakes and shore triangles the user saw were the session's own hole test (green emission under the water) left on the output by a stalled grab, not the scene; the holes it showed are real. Island batch started: 29 of 37, new without effect `/vj/flamingos`. The session hit the weekly limit of its model (Opus) there and continues on Sonnet 5.5. B11 done: handbook, control page (page test 22 of 22 live, 37 of 37 controls), Magic generator; live proof of all 38 addresses and Magic's own Syphon output; `show.magic` no longer black without Godot. Art-Net and the QLC+ fixture are built and unit-tested; the sender test against the live planet passed 7 of 7 (baseline, changed channel, resting channel against OSC, trigger, camera ranges, hold, other universe). Not tested: QLC+ itself and whether it shares udp 6454 with the bridge on one machine. Running in parallel since then, all three in reused sessions on Sonnet 5.5: the planet session (island rest, Flight Approach holes, CAM_4 crease and water step), the Art-Net session (QLC+ workspace file, `make qlc-install`, a test checklist), the handbook session (Art-Net in handbook, README and on the page, the Flight picture in the gallery).
- Focus is Blender again (user, 2026-11-11). `main` and `integration/presentable` are pushed in step; work goes on on `integration/presentable`.
- Blender, where it stands: one command (`make blender-open`) to a checked start state; planet 36 of 37 controls with an effect from the page's "Check all" (the one without is island only by design); no dummy wireframe, real mesh edges at night by `/vj/grid`; Flight shot `CAM_11`; Magic drives it straight on udp 9201.
- Blender, left open on purpose: fps table and cut stalls on an idle machine, the island's self-check rerun (30 of 37 on 2026-11-10), the Flight shot's streamed terrain at full size, the cause of the two builds without night edges (a guard catches them), CAM_4 and CAM_5 look items of round 9, the picture inside Magic.
- README: explanation, screenshots, named cameras and the manual of all OSC channels are on `main`.
- Run history: graph, nodes and rules in [docs/handover/presentable-plan.md](docs/handover/presentable-plan.md).

## Origin

- Imported on 2026-11-10 from `abossard/swift-vj` at `f7094fb` (fresh import, history stays there).
- Old to new: `Tools/magic-blender-lab/scenes` is `blender/scenes`, `blender_osc_bridge.py` is `blender/`, `lab.py` is `osc/`, the Magic tooling is `magic/`, `Tools/godot-colossus` is `godot/colossus`.
- SHAs in hand-over notes (`d5e3323`, `32f7bee`, `39a18a4`) are swift-vj commits.

## Blender: Synthwave Planet Scene

- Works: planet build, star system with eclipses, 11 cameras, per-camera LOD, volumetric fog box, streaming LOD, Syphon and OSC. Both scenes run the runtime and bridge from the files on disk (`vj_loader.py`); `make blender-open` waits for a checked start state.
- Self-check: planet 36 of 37 controls with an effect, run from the page's "Check all" in a browser on a fresh open (2026-11-11, [rows](docs/reports/blender-page-check-planet-2026-11-11.json)); the one without is `/vj/grid_speed`, island only by design. Island 30 of 37 (2026-11-10, not rerun); contract cross-check 0 mismatches, bridge scaling 6 of 6 live. Report: [docs/reports/blender-feature-check.md](docs/reports/blender-feature-check.md).
- `/vj/nebula` works on the planet since round 9 (Milky Way band from the star map, 247 x noise floor on CAM_10).
- Look round 9 (2026-11-11, 35 shots, [notes](docs/handover/planet-look-round9.md), [verdicts](docs/reports/planet-look-round9-verdict.json)): 26 pass. CAM_0 to CAM_3 and CAM_6 to CAM_9 pass. Open: CAM_5 pale top band in fog, CAM_4 water step, crease and night haze at fog 1, CAM_10 core glow at nebula 0, square stars at 200 mm. Moon maps at 4096 and the nebula band show no frame-time cost (context only).
- Round 10 (2026-11-11, [notes](docs/handover/planet-look-round10.md), [verdicts](docs/reports/planet-look-round10-verdict.json)): every dummy line source is out of the build (terrain lattice, orbit lattice, scroll, lattice light on the fog). No lines by day: `/vj/grid` 0 against 1 is within the noise floor on three cameras, all 12 day shots pass. The orbit night shot passes. Frame time, context only: day 35.4 to 33.9 ms, orbit night 23.9 to 20.3 ms.
- Real mesh edges show at night (Wireframe node on the terrain, strength `/vj/grid`). Round 11 (2026-11-11, [notes](docs/handover/planet-look-round11.md), [verdicts](docs/reports/planet-look-round11-verdict.json)) added relief to the plains: swells about 4 m over 320 m, knolls about 1.4 m over 90 m; faces under 1 degree in the CAM_0 foreground 57 % to 1.4 %; lakes and rivers unchanged; no camera under ground. 14 of 19 shots pass. Still failing: the night edges on smooth ground read as a regular lattice (CAM_0, CAM_1, CAM_3), and the day plain reads flat in tone (CAM_0, CAM_3). Relief cannot fix the lattice look: the cells are regular wherever the ground is smooth. Options in the note: irregular triangulation, vertex jitter, or no edges.
- Reviewer on the day land without lines: CAM_0 "a little empty", CAM_3 foreground "a flat uniform purple band".
- Round 12 (2026-11-11, [notes](docs/handover/planet-look-round12.md), [verdicts](docs/reports/planet-look-round12-verdict.json)): interior patch vertices shifted sideways by up to 0.30 of a cell, every cell split along one fixed diagonal. All 11 day shots pass. On the committed scene (179ba64) the reviewer passes CAM_0 and CAM_1 at night as an irregular net; the numbers are no better than round 11 (longest straight run 193, 269, 26 px against 196, 275, 33). The user keeps the edges as they are. Fresh opens of the committed scene draw the night edges (line share 0.12 and 0.13 on CAM_0) and `/vj/grid` (46x) and `/vj/bass` (23x) show an effect. Two earlier builds of the same code (b1154c6, 9a8d405) opened with no night edges until a node of `PL_Land` was re-evaluated; the cause is unknown and it did not reproduce in three rebuilds. A guard at the start now probes for the edges (about 0.6 s), re-evaluates the land once if they are missing, and `make blender-open` fails if they stay missing ([notes](docs/handover/planet-edge-guard.md)). Map paths are relative now. `/vj/flamingos` shows an effect on CAM_7 (28x), where a flock is in view; CAM_0 has no water and no flock. Lines do not move against the terrain: the evaluated mesh is identical over four snapshots, and with the rig held and `/vj/energy` 0 two frames 1 s apart overlap 0.92; with running clocks the camera's lens pulses with beat and energy (up to 0.4 px at the frame edge) and takes the 1 px lines with it. Open: the Flight shot's streamed terrain at full size.
- Flight (merged 2026-11-11, [notes](docs/handover/flight-presentable.md)): the runtime starts `flight_rt` on the planet; the Flight shot is `CAM_11` and `/vj/cam` goes 0..11 (contract, bridge, Magic generator). The Flight's streamed terrain draws only while the Flight shot is on air or in a blend; a fixed shot shows the planet as built (frames equal with the runtime started or stopped, within the noise floor, on CAM_0 day and night and CAM_1 day). Full self-check on the round 11 build: 35 of 37 with an effect; without: `/vj/grid_speed` (on purpose) and `/vj/flamingos` (no flock in CAM_0's view). Hover arrival: the model does not depend on the frame time (12.2 s worst at 17, 54 and 100 ms steps, now part of `make verify`); live the Hover was in effect 0.0 s and 1.2 s after `/vj/flight` reached 1 (the 24.7 s of an earlier run did not come back). From the jump of `/vj/flight` to the Hover it is about 21 s, because the control itself is damped by design. Open: cut stalls 57 to 110 ms and idle cost 2.3 ms more with the runtime started, both under load, not judged.
- `/vj/energy` and `/vj/hit` showed an effect without a reader because one strong cell counted in the self-check; on `blender/flight` a lone strong cell is repeated before it counts.
- Blender is 5.3.0 since 2026-11-11, settings copied from 5.2 (a fresh 5.3 folder had no MCP add-on and opened out of camera view).
- M1 cut timing: 11 of 84 cuts over 70 ms at load 86, not judged. No fps table yet.
- The island scene (`synthwave_pyramids.blend`) has no build script (lost with a scratchpad).
- Local only, git-ignored: star maps (817 MB) and all review grabs (1.7 GB) under `blender/scenes/planet_proto/`.

## Godot: Colossus Scene

- Works: full Arc (Approach, Climb, Fall, Reset), 345 logic tests, OSC in on 9201 (the one scene port; 20 of 20 test packets applied live on 2026-11-11), control page on 9211 with a self-check (22 of 22 from the page's "Check all" in a browser on Metal, 2026-11-11, [rows](docs/reports/godot-page-check-2026-11-11.json)), values persist without packets, Syphon `COLOSSUS_OUT` (app `Godot`) at 1080p with pixel content, nothing of the page in the frame. Report: [docs/reports/godot-feature-check.md](docs/reports/godot-feature-check.md).
- Look rounds 2 and 3 (2026-11-11, same rubric, 357 logic tests): 19 of the 21 round 1 frames pass. Ground no longer flat black, the Colossus reads at 1.6 km, the Wanderer is in the close grip on 30 of 30 samples, `/vj/shock` works from real packets. Notes: [docs/handover/godot-look-round2.md](docs/handover/godot-look-round2.md).
- Still failing: `shot-2` and `2-approach-low-hero`. The low hero shot now holds the Wanderer whole in frame (probe), but the reviewer cannot see him: a dark stand-in of about 19 px on dark ground. Left for the real model.
- Syphon publishes from frame 120 (2 s after the window opens) and the Reset holds black 2 s, because the lighting needs that long to converge.
- Frame time, context only (foreign load): median 16.7 ms, worst frame in the Arc 48 ms, Reset hitch 167 ms down to 36 ms.
- Open: real Colossus and Wanderer models (downloads need a login), stand-in ruins, a trustworthy fps table, pickup in Magic's SyphonClient, Scenario was never signed in.
- godot-mcp is installed and was never used in 43 h of work.

## OSC contract

- One source: `osc/contract.json`, 0..1 on the wire, synced into [osc/CONTROLS.md](osc/CONTROLS.md) and the Blender bridge. `magic/projects/show.magic` drives both scenes (38 addresses straight to udp 9201, `/vj/cam` 0..11). Loaded into MagicBeta on 2026-11-11 with no relay running: the Blender bridge received about 470 packets a second straight from Magic, all 37 controls read `osc`, 0 errors. Not checked: the picture inside Magic (its Syphon output is off in the project) and the mix with Godot. 

## Decided by the user

- Contract: every continuous `/vj/*` control is 0..1 on the wire, each scene scales it to its own range; the wire default gives each scene its tuned look. Indices (`/vj/cam`) stay integers, triggers keep their strength.
- Godot, 2026-11-11: parked. The look with the real models (Nomad, Grock) does not convince the user after round 6.
- Godot, 2026-11-11: no model file goes into git. `godot/colossus/assets/MODELS.md` lists the sources, licences and the prepare command; the scene falls back to the stand-ins when a model is missing.
- 2026-11-11: no relay in the show path, since the two scenes never run together. Magic sends straight to one scene port, udp 9201, where both the Blender bridge and Godot listen; `make lab` stays as an optional debug tool. Committed (9c8793c); the Godot side is proven by its tests only, not live.
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
- Seven Mixamo clips (Braced Hang, Right Braced Hang Shimmy, Climbing Up Wall, Climbing Down Wall, Hanging Idle, Falling Idle, Standing Up); Scenario OAuth.

## Checked after the import (2026-11-10)

- `make magic-test` 35 pass, both generators reproduce the committed `.magic` files with 0 differences.
- `make godot-test` 71 pass, `make godot-smoke` passes, `make godot-lint` clean.
- Both scene `.blend` files resolve all external paths relative to the repo.
- Live: `make blender-open` (planet) came up in camera view with runtime, bridge and Syphon running, `health.py` reported no problems, 12 of 12 OSC messages sent to udp 9201 were applied, and a grabbed Syphon frame (1920x1080) showed the scene.
- That grab (`magicproj.py grab --app Blender --server CAM_OUT`) was vertically flipped. Not checked in Magic, which is the consumer that counts.
- `verify_flight.py` fails `5d descend: changes of more than one depth in a frame`, the same in swift-vj at `f7094fb`. `verify_star_system.py` needs `make venv` and was not run.
- Not run after the import: Godot on Metal (`make godot-capture`), Godot Syphon, `make blender-rebuild`, the Magic projects inside Magic, the lock hook inside a live agent session (pipe-tested only).
