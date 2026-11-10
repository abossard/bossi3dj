# Choosing a Blender MCP server for scene authoring

Ticket: abossard/swift-vj#10. Researched 2026-11-03. Nothing was installed.

Question: which existing Blender MCP server should an external agent (Claude Code/Desktop) use to write and edit Eevee scenes in `/Applications/Blender.app`, given that SwiftVJ later drives the scene live (OSC-ish) and ingests it over Syphon.

Labels: **Fact** (observed in a cited source or local command), **Inference** (reasoned from facts), **Rec** (recommendation).

## Answer

- **Rec:** use the official **Blender Lab MCP** (`projects.blender.org/lab/blender_mcp`, add-on id `mcp`, server `blender-mcp`) as the default authoring server.
- **Rec:** keep **MCP for Blender** (`ahujasid/mcp-for-blender`, formerly `blender-mcp`) as the fallback, only if asset import (Poly Haven, Sketchfab) or its multi-view `look` tool is needed. Run it with `DISABLE_TELEMETRY=true`.
- **Rec:** do not route SwiftVJ live control through either MCP socket. MCP is the authoring path. Live control and video ingest need separate Blender add-ons (OSC, Syphon).

## Local environment

- **Fact:** `/Applications/Blender.app/Contents/MacOS/Blender --version` reports `Blender 5.2.3 LTS`, build date 2026-10-22.
- **Fact:** bundled Python is 3.13.13; the Eevee engine identifier in 5.2.3 is `BLENDER_EEVEE` (checked with `--background --factory-startup --python-expr`).
- **Fact:** `uv` 0.13.6 and `uvx` are installed at `/opt/homebrew/bin`.
- **Fact:** `~/Library/Application Support/Blender/` has profile dirs up to `5.0`, none for `5.2`. No MCP add-on is installed for 5.2 yet.

## Comparison

| | Blender Lab MCP (official) | MCP for Blender (community) |
|---|---|---|
| Owner | Blender Lab, blender.org ([page](https://www.blender.org/lab/mcp-server/)) | Siddharth Ahuja, "not affiliated with the official Blender Foundation" ([repo](https://github.com/ahujasid/mcp-for-blender)) |
| Blender min | `blender_version_min = "5.1.0"` ([manifest](https://projects.blender.org/lab/blender_mcp/src/branch/main/addon/blender_mcp_addon/blender_manifest.toml)) | `bl_info "blender": (3, 0, 0)`, legacy add-on ([addon.py](https://github.com/ahujasid/mcp-for-blender/blob/main/addon.py)) |
| 5.2 evidence | commit "Update 5.2: manual & API" 2026-09-11; bundles 5.2 API + manual RST | closed issues from users on 5.1/5.2 LTS (#243, #299); no stated 5.x test matrix |
| Versions | add-on 1.0.0, server `blender-mcp` 1.0.2, release tag v1.0.3 (2026-09-11) | `mcp-for-blender` 2.2.6 on PyPI (2026-10-28), add-on 1.8 |
| Transport | client stdio to server, server TCP to add-on; also Streamable HTTP per wiki | client stdio to server, server TCP JSON to add-on |
| Socket | `localhost:9876`, env `BLENDER_MCP_HOST`/`BLENDER_MCP_PORT` | `localhost:9876`, env `BLENDER_HOST`/`BLENDER_PORT` or `--port` |
| Auth on socket | none found | none ("anyone who can reach that port can run Python inside Blender", README) |
| Python exec | `execute_blender_code`, `execute_blender_code_for_cli` | `execute_blender_code` |
| Inspection | blend summaries, object/collection summaries, missing files, linked libs | `get_scene_info`, `get_addon_status` |
| Visual check | window/area screenshots, `render_thumbnail_to_path`, `render_viewport_to_path` | `look` (viewport, camera, multi-angle, frames; solid/material/rendered/wireframe/xray) |
| Docs for the model | `get_python_api_docs`, `search_api_docs`, `search_manual_docs` (bundled) | none listed |
| Headless | yes: `*_for_cli` tools spawn `blender --background` via `BLENDER_PATH`; `blender --background f.blend --command blender_mcp` serves the socket | no headless mode documented |
| Scene/material/GN tools | none dedicated; via Python | none dedicated; README: "The AI writes Blender Python itself" |
| Third-party network | none | Poly Haven, Sketchfab, Poly Pizza, Meshy, Tripo, Hyper3D, Hunyuan3D, paid "Premium" |
| Telemetry | none found | anonymous usage record on by default; content opt-in |
| License | GPL-3.0-or-later | MIT |
| Activity | last commit 2026-09-29, 25 open issues, 37 stars | last push 2026-10-29, 62 open issues, ~33k stars |

Sources for the table: Lab [readme.md](https://projects.blender.org/lab/blender_mcp/src/branch/main/readme.md), [readme_tools.rst](https://projects.blender.org/lab/blender_mcp/src/branch/main/readme_tools.rst), [mcp/pyproject.toml](https://projects.blender.org/lab/blender_mcp/src/branch/main/mcp/pyproject.toml), [connection.py](https://projects.blender.org/lab/blender_mcp/src/branch/main/mcp/blmcp/tools_helpers/connection.py), [blender_cli.py](https://projects.blender.org/lab/blender_mcp/src/branch/main/mcp/blmcp/tools_helpers/blender_cli.py), Gitea API for commits, tags, releases, issues. Community [README](https://github.com/ahujasid/mcp-for-blender/blob/main/README.md), [pyproject.toml](https://github.com/ahujasid/mcp-for-blender/blob/main/pyproject.toml), [PyPI JSON](https://pypi.org/pypi/mcp-for-blender/json), GitHub API.

## Safety of arbitrary Python execution

- **Fact (Lab):** blender.org warns the server runs LLM-generated code with no safeguards against data deletion or exfiltration, and recommends a VM or a system without sensitive data ([page](https://www.blender.org/lab/mcp-server/)).
- **Fact (Lab):** `weak_sandbox.py` says "this isn't really a sandbox". It blocks only `sys.exit`, `wm.quit_blender`, `wm.read_factory_settings`, `wm.read_factory_userpref`, `wm.read_userpref` ([source](https://projects.blender.org/lab/blender_mcp/src/branch/main/addon/blender_mcp_addon/weak_sandbox.py)).
- **Fact (Lab):** the add-on refuses to start its socket unless Blender's Online Access preference is on (`bpy.app.online_access`); background mode needs `--online-mode` ([__init__.py](https://projects.blender.org/lab/blender_mcp/src/branch/main/addon/blender_mcp_addon/__init__.py)). Auto Start defaults to on.
- **Fact (community):** README warns `execute_blender_code` is "potentially dangerous" and says to save work first.
- **Fact (community):** opt-in `BLENDER_MCP_SAFE_MODE=1` is an AST allowlist in the MCP server, not the add-on. Its docstring says the add-on socket "accepts a raw `execute_code` from any local process, so this guard covers the MCP path only". It blocks `os`/`sys`/`subprocess`/`socket`, `bpy.app.handlers`, `bpy.app.timers`, drivers and driver expressions, `register_class` ([safe_mode.py](https://github.com/ahujasid/mcp-for-blender/blob/main/src/blender_mcp/safe_mode.py)).
- **Fact (community):** the add-on has no reference to `bpy.app.online_access` while it downloads assets (grep of `addon.py`).
- **Inference:** both expose unauthenticated code execution on `localhost:9876` to every local process. The risk is equal at the socket. The community server adds a prompt-injection channel (third-party asset text in context, its own safe-mode rationale) and outbound telemetry.
- **Inference:** community safe mode blocks drivers and handlers, which a live-controllable SwiftVJ scene will likely need (OSC values feeding drivers or custom properties). Safe mode is therefore not usable for this goal.
- **Rec:** run Blender with a dedicated `.blend` working copy under git, keep the socket on `localhost`, stop the add-on server when not authoring, and approve `execute_blender_code` calls per call in Claude Code.

## Install steps (not executed)

Blender Lab MCP ([Setup wiki](https://projects.blender.org/lab/blender_mcp/wiki/Setup), [mcp/README.md](https://projects.blender.org/lab/blender_mcp/src/branch/main/mcp/README.md)):

- Add the Blender Lab extensions repository `https://lab.blender.org/` in Preferences > Get Extensions, install and enable "MCP" (or drag the add-on zip in twice: once for the repo, once for the add-on).
- Enable Preferences > System > Allow Online Access, or the socket will not bind (also open issue #45: silent failure when it is off).
- Server: `git clone https://projects.blender.org/lab/blender_mcp.git`, then MCP config `uv --directory <clone>/mcp run blender-mcp`. Alternative: `pip install git+https://projects.blender.org/lab/blender_mcp.git#subdirectory=mcp`.
- For `*_for_cli` tools set `BLENDER_PATH=/Applications/Blender.app/Contents/MacOS/Blender` (default is `blender` on `PATH`).
- **Inference:** for Claude Code this is `claude mcp add blender -- uv --directory <clone>/mcp run blender-mcp`. Not verified.
- **Fact:** `.mcpb` bundle for Claude Desktop exists (v1.0.3 release asset), but issue #57 reports it failing to install on macOS ("Operation not permitted" under `~/.cache/uv`), and says the Claude extension directory lists an older 1.0.1.

MCP for Blender ([README](https://github.com/ahujasid/mcp-for-blender/blob/main/README.md)):

- One-liner `curl ... | sh` installer, or `uvx mcp-for-blender setup`, which edits detected client configs (saves `.bak`) and installs the add-on.
- Manual: `claude mcp add blender uvx mcp-for-blender`, `uvx mcp-for-blender install-addon`, enable "Interface: MCP for Blender".
- **Rec:** if used, prefer the manual path and add `"env": {"DISABLE_TELEMETRY": "true"}`.
- **Fact:** both default to port 9876; only one can run per Blender instance without changing a port.

## Fit for the SwiftVJ end goal

- **Fact:** the Lab add-on executes requests from a `bpy.app.timers` poll, default interval 0.25 s active and 1.0 s idle after 5 s ([__init__.py](https://projects.blender.org/lab/blender_mcp/src/branch/main/addon/blender_mcp_addon/__init__.py)). The community add-on also drains a command queue via `bpy.app.timers`.
- **Inference:** that latency and the exec-per-call model rule out the MCP socket as SwiftVJ's live control channel.
- **Fact:** `maybites/NodeOSC` (OSC in Blender, last push 2026-06-05) and `maybites/TextureSharing` ("Texture sharing addon for Blender 5.x upwards", Syphon Metal server supported on macOS, last push 2026-10-07) exist ([TextureSharing](https://github.com/maybites/TextureSharing), [NodeOSC](https://github.com/maybites/NodeOSC)).
- **Inference:** the authoring agent should create the OSC-addressable parameters (custom properties, drivers, Geometry Nodes inputs) and Syphon output setup via `execute_blender_code`; neither MCP server knows about OSC or Syphon.
- **Inference:** the Lab server's bundled 5.2 API and manual search matters for this, because Eevee and Geometry Nodes APIs changed across 4.x and 5.x (example: engine id is `BLENDER_EEVEE` in 5.2.3) and models trained on older bpy produce stale code.

## Excluded candidates

- **Fact:** GitHub search "blender mcp" by stars (2026-11-03): next most-starred servers are `VxASI/blender-mcp-vxai` (300, last push 2025-03), `pranav-deshmukh/blender-mcp` (98, 2025-08), `bpy-dev/blender-mcp` (97, "Independent enhanced distribution of Blender Lab MCP"), `seehiong/blender-mcp-bridge` (84, 93 tools), `djeada/blender-mcp-server` (33, PyPI `blender-mcp-server` 0.2.0).
- **Rec:** excluded for low adoption, staleness, or being a repackaging of the Lab server. Not evaluated in depth.

## Open questions

- Whether the Lab `.mcpb` install bug (#57) is fixed; affects Claude Desktop only, not Claude Code.
- Lab issue #10: no add-on/server version compatibility check. Pin both to the same release tag.
- Neither project documents a Blender 5.2 test matrix. A smoke test (start add-on, `get_objects_summary`, create an Eevee material via `execute_blender_code`, `render_viewport_to_path`) should precede adoption.
- TextureSharing and NodeOSC compatibility with 5.2.3 is claimed (5.x) but untested here. That belongs to the Syphon/OSC ticket, not this one.
