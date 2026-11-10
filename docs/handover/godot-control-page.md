# Handover: Godot control page (node G1)

Branch `godot/control-page`, cut from `integration/presentable`. Done headless; nothing here needed the GPU.

## State

- Page on http 127.0.0.1:9211 (`io/control_server.gd`, `io/control_page.html`), `GET /api/state`, `POST /api/{set,fire,hold,defaults,phase,sim,check}`. Port is `ColossusMain.page_port`, 0 turns it off, tests use 19211.
- One owner of the values: `io/vj_signals.gd`. OSC, page, simulator and check write through `apply(address, value, source)`. A hold refuses every source but the page. Values persist; only `/vj/beat` has a fallback.
- Wire value to scene value is data: `io/vj_map.gd` (`lo`, `hi`, `rest`, `out_lo`, `out_hi`, `kind`, `drives`), the Godot column of `osc/contract.json`: 0..1 on the wire, one linear range per scene, `/vj/cam` Nth shot 0-based plus `/vj/cam_auto`, wire defaults give the tuned look. `_test_vj_map_matches_contract` reads the JSON and fails on drift; to change a range, edit `osc/contract.json`, `make osc-sync`, then the table. `World.apply_look` takes scene values.
- Self-check: `io/feature_check.gd` (table `TABLE`, preconditions `NEEDS`, pure verdict functions), probes in `io/scene_probe.gd`. 22 rows, all effect headless. Result and live-pass list: [docs/reports/godot-feature-check.md](../reports/godot-feature-check.md).
- Phase jump: `Arc.step_toward` (pure) and `ArcState.go_to`; a performer's Next or Reset-now cancels a walk.
- `make status` shows `godot_scene` (reads 9211; `GODOT_PAGE_PORT=19211` for a test run).
- 332 logic tests pass. `make godot-lint` green. `make test` now runs `godot-check` too.

## Live pass done 2026-11-10

Results in [the report](../reports/godot-feature-check.md): Check all 22 effect on Metal, Syphon server `COLOSSUS_OUT - Godot` with rows bottom first, page does not change the frame, OSC sweep arrives as `osc`, frame times as context, look verdicts in `docs/reports/godot-look-verdict.json` (14 pass, 7 fail). New tools: `make godot-look`, `tools/png_stats.py`, `tools/godot_frame_log.py`; `/api/state` has a `profile` block.

## Open

- Contract applied and merged with C1. Defaults come from `osc/contract.json` (level 0.5, bass 0, intensity 0.5, fog 0.35, fog_height 0.42, haze 1, cam 0, cam_auto 1).
- Haze wire 1 is the rest look, so haze can only be lowered; bass wire 0 is weight 0.5 (see the report, "Left open").
- `make godot-smoke` prints the worst frame gap and asserts logic only.
- Failing frames, for the user or a look session: flat black ground in the first seconds after start or a Colossus build and with fog_height 0 (likely SDFGI warm-up, try a shadowless fill light), no Colossus visible in the 1.6 km Approach walk (director `TELEPHOTO_RANGE` is deliberate), no Wanderer in the close-grip Shake frame. Not seen: real `/vj/shock` Shake, a real Magic session, bass dust size and beat nudge.
- Syphon frame count is `Engine.get_frames_drawn()` since the server started; the addon has no counter.

## Commands

```bash
make godot-import       # once per fresh worktree
make godot-lint
make godot-test
make godot-smoke
make godot-check        # rows on stdout, JSON in CHECK_OUT (default /tmp/colossus-feature-check.json)
make godot-page-test    # headless scene on 19211, HTTP requests, the page's Check all
make godot-look OUT=/tmp/look      # Metal: five pinned shots and the ends of fog, fog_height, intensity (refuses while Blender runs)
python3 tools/godot_frame_log.py   # fps across one Arc from the running scene's page
python3 tools/png_stats.py a.png   # mean, variance, lit share, 3x3 luma grid
```

Rerun one row: `Godot --headless --path godot/colossus --script res://tests/check.gd -- /tmp/out.json bass,fog_height`.
Keep the scene up for a browser: `Godot --headless --path godot/colossus --script res://tests/serve.gd -- 120`, then open http://127.0.0.1:19211.
