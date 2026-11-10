# Handover: Godot control page (node G1)

Branch `godot/control-page`, cut from `integration/presentable`. Done headless; nothing here needed the GPU.

## State

- Page on http 127.0.0.1:9211 (`io/control_server.gd`, `io/control_page.html`), `GET /api/state`, `POST /api/{set,fire,hold,defaults,phase,sim,check}`. Port is `ColossusMain.page_port`, 0 turns it off, tests use 19211.
- One owner of the values: `io/vj_signals.gd`. OSC, page, simulator and check write through `apply(address, value, source)`. A hold refuses every source but the page. Values persist; only `/vj/beat` has a fallback.
- Contract value to scene value is data: `io/vj_map.gd` (`lo`, `hi`, `rest`, `out_lo`, `out_hi`, `kind`, `drives`). `World.apply_look` takes scene values.
- Self-check: `io/feature_check.gd` (table `TABLE`, preconditions `NEEDS`, pure verdict functions), probes in `io/scene_probe.gd`. 22 rows, all effect headless. Result and live-pass list: [docs/reports/godot-feature-check.md](../reports/godot-feature-check.md).
- Phase jump: `Arc.step_toward` (pure) and `ArcState.go_to`; a performer's Next or Reset-now cancels a walk.
- `make status` shows `godot_scene` (reads 9211; `GODOT_PAGE_PORT=19211` for a test run).
- 223 logic tests pass (152 new). `make godot-lint` green.

## Open

- Contract decision (user): units of `/vj/fog_height`, meaning of `/vj/cam`. When it arrives, change the two rows in `io/vj_map.gd` and their expected values in the table test `_test_vj_map`; no code changes. `osc/CONTROLS.md` rows belong to the contract node.
- `make godot-smoke` failed only its wall-clock assert "a frame in every 2 s" (load 75 to 125; the base commit fails it equally). Rerun on an idle machine.
- Live pass items are in the report. Nothing was seen on Metal, no Syphon pixel, no real fps.
- Syphon frame count is `Engine.get_frames_drawn()` since the server started; the addon has no counter.

## Commands

```bash
make godot-import       # once per fresh worktree
make godot-lint
make godot-test
make godot-smoke
make godot-check        # rows on stdout, JSON in CHECK_OUT (default /tmp/colossus-feature-check.json)
make godot-page-test    # headless scene on 19211, HTTP requests, the page's Check all
```

Rerun one row: `Godot --headless --path godot/colossus --script res://tests/check.gd -- /tmp/out.json bass,fog_height`.
Keep the scene up for a browser: `Godot --headless --path godot/colossus --script res://tests/serve.gd -- 120`, then open http://127.0.0.1:19211.
