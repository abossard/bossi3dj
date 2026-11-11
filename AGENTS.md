# Working on bossi3dj

Live VJ scenes driven by one OSC contract: Magic Music Visuals sends `/vj/*`, a Blender scene and a Godot scene react, each publishes Syphon, Magic mixes them.

- Start with `make help` and `make status`. [STATE.md](STATE.md) says where the work stands and which decisions wait for the user.
- Terms are in [GLOSSARY.md](GLOSSARY.md). Use them in names; never the _Avoid_ words.

## Where things are

| Folder | Holds | Read first |
|---|---|---|
| `osc/` | `lab.py` relay and debug page, the address contract | [osc/CONTROLS.md](osc/CONTROLS.md) |
| `magic/` | `.magic` generators, `magicproj.py`, tests | skill `magic-projects` |
| `blender/` | OSC bridge, scenes, planet build, review tools | [blender/GUIDELINES.md](blender/GUIDELINES.md) |
| `godot/colossus/` | Godot 4.7 project of the Colossus Scene | [godot/colossus/docs/GUIDELINES.md](godot/colossus/docs/GUIDELINES.md) |
| `tools/` | status, Blender lock, `.blend` path check | `make help` |
| `docs/` | research, hand-over notes, the 2026-11 retrospective | [docs/retrospective-2026-11.md](docs/retrospective-2026-11.md) |

## The contract

- Every `/vj/*` address is a row in [osc/contract.json](osc/contract.json), shown in [osc/CONTROLS.md](osc/CONTROLS.md) (`make osc-sync` rewrites the table and the bridge's `SCALES`). Change the row first, then the Magic generator, then each scene. Continuous controls are 0..1 on the wire, each scene scales.
- A scene owns no music logic. Magic decides what the music means; scenes only take controls.
- Ports: Magic to relay 9200, Blender bridge 9201, Godot 9202, Blender scene page 9210, Godot scene page 9211, relay page 8765. Syphon servers: `CAM_OUT - Blender`, `COLOSSUS_OUT`.
- Tests and probes never bind those ports or publish those Syphon names. Godot tests use 19202, 19211 and `COLOSSUS_TEST`.

## Shared machine

- One Blender at a time. A second instance halves the fps of the first and both collide on udp 9201. `make blender-open` and `make blender-rebuild` refuse to start a second one.
- The Blender lock is automatic: a hook (`tools/blender_lock.py`) gives the live Blender to the first session that changes it and denies others until it has been idle for 5 minutes. A denied call means: do Blender-free work, don't message the owner for a slot.
- You may kill the live Blender for a rebuild (`make blender-kill`, user permission of 2026-11-04). The scene files are generated, nothing in them needs saving. Reopen with `make blender-open` afterwards.
- One live app at a time: `make blender-open`, `make godot-open` and `make godot-capture` refuse while the other app runs. A refusal means: do GPU-free work.
- Blender and Godot share one GPU. An fps number counts only when `make status` says `fps_trustworthy` and no other GPU app runs. The show runs Godot alone on the GPU; never close the user's Blender to measure Godot, hand that measurement to the user.
- Magic is the user's app. Never drive it with computer use. Read and write projects with `magicproj.py`, check its output with a Syphon grab.

## Done means observed

- An image claim needs pixels: read the Syphon frame content, not its size or rate. A black or stale frame has the right size.
- A logic claim needs `make test`. A scene claim needs the scene's health check or smoke run (see the folder's guidelines).
- Numbers before images: driver scan, ground check, cut timing, fps table. Look at images only for what numbers cannot say.
- Images go to the `shot-reviewer` subagent, at most 36 per call, as contact sheets of 480 px tiles. Its JSON verdict comes back; the images stay out of your context.
- A review round has one frozen rubric. A new wish from the user starts the next round, it does not change the bar mid-round.

## Sessions

- One session per area, one narrow brief at a time. Sessions work in the main checkout on the integration branch, one writer per area at a time (`blender/`, `godot/`, `osc/` with `magic/`). Commit only your own files, by path.
- A worktree only when two sessions must write the same area at once. Its directory name equals its branch name (`/` becomes `-`); remove it after the merge.
- Don't commit to `main` from a checkout other sessions share.
- Reuse sessions: follow-up work in an area goes to the session that already knows it, not to a fresh one. A restart costs 10 to 15 minutes of reading, rebuilding and reopening.
- Context is measured, not felt: the window is 1M tokens. Hand over to a fresh session only above about 350k tokens used (the orchestrator reads the number with `get_usage`), with `docs/handover/<topic>.md` (state, open items, exact commands).
- Every script that produced a result you report lives in the repo (`blender/review/`, `tools/`, `godot/colossus/tests/`). A scratchpad is wiped on reboot and took the island builder and two review toolsets with it.
- Wait for long runs with a background `until [ -f DONE ]` loop, never `sleep` chains.

## Tools

- Blender MCP: the Claude Desktop extension "Blender" (blender.org Lab MCP, tools `mcp__Blender__*`). Authoring and inspection only; live control goes through OSC or the scene page on 9210.
- Godot MCP and Scenario: `.mcp.json`. Godot MCP needs the editor open with the `godot_mcp` addon; headless tests don't.
- Python in `osc/` and `magic/` is standard library only. The verify scripts need `make venv`.
- Never use `sed` or `grep` on JSON, use `jq`.
