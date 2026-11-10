# Blender feature check (node B1)

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
make blender-kill && make blender-rebuild   # re-embeds synthwave_runtime.py, synthwave_web.py is read from file
make blender-open
make blender-check                          # about 30 min with the camera fallback
make blender-check ARGS="--only vj_fog,vj_hue --no-fallback"
python3 blender/review/feature_check_table.py blender/review/out/feature_check_Scene.json
```

## Things that cost time

- The `.blend` embeds a copy of `synthwave_runtime.py`; Blender runs that copy on load. After any runtime edit run `make blender-rebuild` (the builder re-embeds all text blocks). `synthwave_check.py`, `synthwave_web.py`, `syphon_out.py` and the page are read from files and need no rebuild. The island file has no builder: its embedded runtime is stale until its texts are refreshed.
- The viewport is noisy by itself (mean abs diff 0.1 to 1.0 between untouched renders, per camera). A paused viewport was tried: frames are identical within a cell but differ by 1 to 1.9 between cells, so it is worse. The check keeps playback running, averages 8 preview frames and measures the floor on 3 replicate baselines per camera and state.
- Weak effects (below 10 x floor) are measured again on fresh baselines; they count only when they repeat.

## Open

- Bugs 1 to 4 of the report have owners: Flight and Energy hook (B2), `VJ_Color` hue link and grid scroll (planet build), nebula (B3).
- Island scene: the check ran but is invalid (viewport probably Solid, noise floor 0.000). Open the island in Rendered shading and rerun `make blender-open SCENE=island`, `make blender-check`.
- `vj_energy` shows only on CAM_3 at 1.0 with no reader found: unexplained.
- Syphon orientation: `python3 blender/review/syphon_orientation.py` shows the delivered frame is bottom-up; Magic's side is unobserved.
- The check takes about 25 min on the planet, mostly the fallback over 11 cameras for controls with no effect. `--no-fallback` for a quick pass.
- `blender/review/refresh_texts.py` re-embeds text blocks of a .blend; `blender/scenes/synthwave_pyramids.blend` was refreshed with it and is committed.
