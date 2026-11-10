# Blender feature check and wiring (nodes B1, B4)

Branch `blender/feature-check`. Report: [docs/reports/blender-feature-check.md](../reports/blender-feature-check.md).

## What exists

- `blender/scenes/synthwave_check.py`: the check, loaded by `synthwave_web.py` for every run. One `bpy.app.timers` callback exists only while a check runs. Table of preconditions: `PRECONDITIONS` at the top of the file.
- `synthwave_web.py`: `POST /api/check` (body `{"only": [...], "frames_dir": "...", "fallback": false}`), `GET /api/check`, `POST /api/check/abort`.
- `synthwave_control.html`: "Check all" button and a result table.
- `synthwave_runtime.py`: `freeze`, `advance`, `quiesce`, `driver_namespace["vj_runtime"]`. A freeze lapses 4 s after the last renewal.
- `syphon_out.py`: `previews` counter, so a reader can tell a new preview frame.
- `blender/review/feature_check.py` (`make blender-check`): waits for a cold start, contract cross-check, udp 9201 probe, runs the check, writes `blender/review/out/feature_check_<scene>.json` and PNGs of the frames of failing controls.
- `blender/review/feature_check_table.py`: markdown tables from that JSON.
- `blender/review/attribute_readers.py`: lists shader Attribute readers of vj_* properties in a `.blend` (headless).

## Commands

```
make blender-open SCENE=planet|island      # opens, then start_check.py waits for the start state
make blender-check                          # about 25 min with the camera fallback, includes the six bridge messages
make blender-kill && make blender-prepare && make blender-rebuild   # only after editing build_planet.py or the loader
make blender-check ARGS="--only vj_fog,vj_hue --no-fallback"
python3 blender/review/feature_check_table.py blender/review/out/feature_check_Scene.json
```

## Things that cost time

- Both `.blend` files embed one text block, `vj_loader.py`; the runtime, bridge, Syphon sender and page are read from disk on every open. No rebuild after editing them. `make blender-prepare` (island file) and `make blender-rebuild` (planet, grafted from the island) are only for the loader, `build_planet.py` and the island's own data. `health.py` flags an embedded text that differs from its file.
- Blender opens 3D views in Solid whatever the file stores; `_play` in the runtime sets camera view and Rendered. A Solid island run reads every shader control as dead (noise floor 0.000).
- The viewport is noisy by itself (mean abs diff 0.1 to 1.0 between untouched renders). The check keeps playback running, averages 8 preview frames and measures the floor on 3 replicate baselines per camera and state. Weak effects (below 10 x floor) must repeat on fresh baselines.
- EEVEE draws flat frames while it compiles: `start_check.py` waits for luminance variance, `blender-open` takes about a minute on the planet.
- A viewport that is paused is worse (1 to 1.9 mad between cells).

## Open

- Flight and Energy (B2): `/vj/blend`, `/vj/boost`, `/vj/flight` have no reader on either scene; `/vj/hit` and `/vj/energy` read nothing but show a weak effect on one planet camera (unexplained). The hook is one call in `synthwave_runtime.main()`.
- `/vj/nebula` shows on no planet camera (B3).
- `/vj/eclipse` and `/vj/star_speed` do nothing on the island (no star system); the page still lists them.
- Syphon orientation: `python3 blender/review/syphon_orientation.py` shows the delivered frame is bottom-up; Magic's side is unobserved (user's app).
- `/vj/grid_speed` scrolls the planet's wire lattice along the meridians at cells/s (`la` in `build_planet.py`). The default 0.6 cells/s moves the grid at the rest look; judge it by eye (look issue, B3 or the user).
- `fps_trustworthy` was false throughout (load 40 and more from other jobs): no fps recorded.
