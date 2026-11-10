# Agent-built Blender scenes over MCP (authoring path)

Researched 2026-11-03. Host: macOS Apple Silicon, Blender 5.2.3 LTS at `/Applications/Blender.app`. Nothing installed. Builds on `/Users/abossard/Desktop/projects/swift-vj-worktrees/research-blender-mcp-server/docs/research/blender-mcp-server.md` (referred to below as "prior note"); facts reused from it were re-checked where marked. Live OSC/DMX/Syphon plumbing is out of scope.

## 1. Available Blender MCP servers: tool surfaces, 5.x support, headless, visual feedback, safety

### Takeaway
Two servers matter. The official Blender Lab MCP (Blender 5.1+, bundled 5.2 API and manual search, headless `*_for_cli` tools, screenshots and renders) suits correctness on 5.2. The community "MCP for Blender" (ahujasid) is the asset and generation server (Poly Haven, Sketchfab, Poly Pizza, four 3D generators) and has the stronger `look` tool. Neither has dedicated material, Geometry Nodes or animation tools. Both route almost everything through one "execute Python" tool, and neither authenticates its localhost socket.

### Cited Findings
- Lab MCP full tool list (27 tools, generated from docstrings): `execute_blender_code`, `execute_blender_code_for_cli`, blend-file summaries (datablocks, missing files, linked libraries, path info, "usage guess"), each with a `_for_cli` twin, `get_object_detail_summary`, `get_objects_summary`, `get_python_api_docs`, `search_api_docs`, `search_manual_docs`, `get_screenshot_of_area_as_image`, `get_screenshot_of_window_as_image`, `get_screenshot_of_window_as_json`, `jump_to_tab_by_name`, `jump_to_tab_by_space_type`, `jump_to_view3d_object_by_name`, `jump_to_view3d_object_data_by_name`, `render_thumbnail_to_path`, `render_viewport_to_path` ([readme_tools.rst](https://projects.blender.org/lab/blender_mcp/raw/branch/main/readme_tools.rst)).
- Lab MCP describes itself as "deliberately small, maintainable, and does no more than necessary". Architecture: MCP client over stdio to `blender-mcp`, then TCP socket to the add-on. It bundles `prompts.yml` (instructions sent at connection), `data/api/` (Python API RST) and `data/manual/` (manual RST) ([readme.md](https://projects.blender.org/lab/blender_mcp/raw/branch/main/readme.md)).
- Lab MCP: deferred (long-running) responses work only in the interactive add-on server. Background mode needs requests to complete synchronously ([readme.md](https://projects.blender.org/lab/blender_mcp/raw/branch/main/readme.md)).
- Lab MCP: requires Blender 5.1.0 or newer, add-on v1.0.3 released 2026-09-11, with a commit adding the 5.2 manual and API on 2026-09-11 (prior note; [glama listing](https://glama.ai/mcp/servers/A-to-PC/blender-lab-mcp-client?locale=de-DE) repeats 5.1+ and v1.0.3).
- Lab MCP open issues relevant to scene authoring (fetched 2026-11-03): #70 and #61, `render_thumbnail_to_path` can render at full scene resolution and samples; #12, no rendering to a temp file "without risking changes to the users file"; #11, no WEBP screenshots; #10, no add-on/server version check; #45, the socket never binds when Online Access is off and fails silently; #57, the `.mcpb` bundle fails to install on macOS ([issues API](https://projects.blender.org/api/v1/repos/lab/blender_mcp/issues?state=open&type=issues&limit=50)).
- MCP for Blender (ahujasid) exposes nine tools: `execute_blender_code`, `look`, `get_scene_info` (compact, with `root`/`query` drill-down), `generate_3d`, `search_assets`, `import_asset`, `get_addon_status`, `disable_telemetry`, `record_trajectory_feedback`. "The AI writes Blender Python itself" for modeling, materials, animation and rigging ([README](https://github.com/ahujasid/mcp-for-blender/blob/main/README.md)).
- `look` views are `viewport`, `camera`, `angles` (auto-framed multi-view sheet) and `frames` (animation strip). Shading options are solid, material, rendered, wireframe and xray. It can also return a render or an image file ([README](https://github.com/ahujasid/mcp-for-blender/blob/main/README.md)).
- MCP for Blender limits, from its README: Poly Haven downloads run on Blender's main thread and can freeze it (advice: use 1k or 2k textures). Timeouts mean you should "break large requests into steps". Run only one MCP client instance at a time ([README](https://github.com/ahujasid/mcp-for-blender/blob/main/README.md)).
- Safety, both servers: unauthenticated `localhost:9876`. Lab's weak sandbox blocks only quit/reset operators. The community `BLENDER_MCP_SAFE_MODE=1` blocks drivers, handlers and timers, and the community server sends telemetry by default (prior note, sources there).
- Other servers: `sandraschi/blender-mcp` advertises a headless mode for PNG, MP4 and Gaussian splat output ([repo](https://github.com/sandraschi/blender-mcp)). `seehiong/blender-mcp-bridge` (93 tools), `bpy-dev/blender-mcp` (a repackaged Lab MCP) and `djeada/blender-mcp-server` have low adoption (prior note). `A-to-PC/blender-lab-mcp-client` is an unofficial client for the Lab add-on protocol ([glama](https://glama.ai/mcp/servers/A-to-PC/blender-lab-mcp-client?locale=de-DE)).
- Rich-Siomporas forked the Lab MCP as `blender-agent` (Lab issue #39, 2026-06-12). The fork adds a skills registry (animation, boolean modeling, lighting skills, which can be fetched from git), a "welcome" tool and a streamable HTTP transport, so a client connects through a `.mcp.json` in the working folder. The author says skills "can dramatically improve performance on well-defined tasks, especially for smaller models" ([issue #39](https://projects.blender.org/api/v1/repos/lab/blender_mcp/issues/39)).
- Non-MCP alternative: the `cli-anything-blender` (HKUDS) skill drives Blender as a stateful CLI from JSON scene descriptions with a `--json` output mode, and needs Blender 4.2+ ([skillselion listing](https://skillselion.com/skills/hkuds/cli-anything/cli-anything-blender); [claudemarketplaces](https://claudemarketplaces.com/skills/hkuds/cli-anything/cli-anything-blender)).

### Inferences
- For a 5.2 show scene, run the Lab MCP for authoring and verification. Its API search counters stale bpy (see Q4 probe). Add the community server only during an asset-gathering phase, on a different port, with telemetry off.
- The Lab `*_for_cli` tools can drive a headless "build from script, render a check frame" loop against a working-copy `.blend`. That avoids the GUI main-thread freeze, but deferred (long) operations are rejected there.
- `look(view="angles")` and `look(view="frames")` from the community server give the best one-call checks for composition and animation. Lab only offers window or area screenshots and renders to a path.

### Gaps
- No Blender 5.2 test matrix for either server. Not smoke-tested here, because nothing was installed.
- No published token-per-call sizes for screenshot tools on either server.

## 2. Practices that make agent-built scenes good

### Takeaway
What works: a small tool set built around code execution, vision after every step, inspecting before writing, short self-contained scripts that return a dict, and non-destructive structure (modifiers, node groups with exposed inputs, custom properties feeding drivers). In Blender 5.2 the Python paths for Geometry Nodes modifier inputs differ from what most training data and tutorials show, so verify against the bundled API docs.

### Cited Findings
- The Lab connection prompt tells the model to: "Respect existing structure and naming conventions"; "NEVER assume missing values - inspect the scene first"; prefer `bpy.ops` for standard actions and `bpy.data` for precise or side-effect-free creation; set mode, active object and selection explicitly; update the depsgraph before reading computed values; flush bmesh edits; "Return structured data (dicts, lists) from executed code, not print output"; capture references right after creation because names auto-suffix `.001`; prefer modifiers over destructive edits; inspect large scenes progressively ([prompts.yml](https://projects.blender.org/lab/blender_mcp/raw/branch/main/mcp/blmcp/data/prompts.yml)).
- Lab issue #55 (2026-09-12): agents assume a persistent console. Each `execute_blender_code` call needs `import bpy` and starts with a fresh namespace, and agents failed with `NameError` on `bpy` and on variables from earlier calls. Results are returned by assigning a JSON-serialisable dict to `result` ([issue #55](https://projects.blender.org/api/v1/repos/lab/blender_mcp/issues/55)).
- A practitioner building a multi-agent Blender system (Guilherme, devtalk, 2026-02-07) reports: a viewport screenshot after each operation was the "single biggest quality improvement", and without it the agent drifts after a few steps. Splitting "decide" from "write bpy" across models worked better. Narrow per-domain agents (geometry, materials, lighting) plus a verification layer helped. A TCP socket beat HTTP for 30+ round-trip tasks ([devtalk thread](https://devtalk.blender.org/t/built-a-multi-agent-system-on-top-of-blenders-python-api-and-sharing-architecture-learnings-for-the-mcp-discussion/44260)).
- The same author (Lab issue #4, 2026-03-05): exposing 50+ narrow tools (`create_cube`, `add_material`, ...) performed poorly, because the model "spent more tokens deciding which tool to call". Consolidating to a general `execute_code` tool improved results ([issue #4](https://projects.blender.org/api/v1/repos/lab/blender_mcp/issues/4)).
- NodeToPython (Blender Extensions, GPL-3.0) converts Geometry Nodes, material and compositor node trees into Python functions or an add-on. The extensions listing shows a 4.2.0 release (2026-07-11) said to add Blender 5.2 LTS support ([extensions.blender.org](https://extensions.blender.org/add-ons/node-to-python/); [GitHub](https://www.Github.com/BrendanParmer/NodeToPython)).
- Local probe, Blender 5.2.3, `--background --factory-startup` (2026-11-03):
  - A Geometry Nodes tree can be built entirely in Python: `bpy.data.node_groups.new(name, "GeometryNodeTree")`, `tree.interface.new_socket(name, in_out=..., socket_type=...)` (with `default_value`, `min_value`, `max_value` on the socket), `nodes.new(...)`, `links.new(...)`.
  - The 4.x idiom `mod["Socket_1"]` for a GN modifier input fails in 5.2.3 with `TypeError: ... doesn't support IDProperties`. So does a driver on `modifiers["GN"]["Socket_1"]`.
  - The working 5.2.3 path is `mod.properties.inputs.Socket_1.value`. The type is `GeometryNodesModifierInterface`, and an input item has `attribute_name`, `name`, `type` and `value`.
  - A driver on `modifiers["GN"].properties.inputs.Socket_1.value`, fed from a Scene custom property `scene["svj_amp"]` (AVERAGE driver), is valid and evaluates: grid Z was 1.25 after a depsgraph update.
  - `scene.id_properties_ui("svj_amp").update(min=..., max=..., description=...)` works for custom-property UI ranges.
  - Factory `preferences.filepaths.use_scripts_auto_execute` is `False`.
- A NousResearch "blender-mcp" companion skill encodes bpy idioms and pitfalls: inspect first, take viewport screenshots between steps, report absolute render paths ([claudeskills.info](https://claudeskills.info/skills/nousresearch/hermes-agent/blender-mcp/)).

### Inferences
- Scene template: a starter `.blend` (or a `build_scene.py` that runs via `execute_blender_code_for_cli`) with fixed collections (for example `SVJ_Geo`, `SVJ_Lights`, `SVJ_Cam`, `SVJ_FX`), a prefixed naming scheme, and one "control" ID (a Scene or Empty) that holds every live parameter as a custom property with UI ranges. Drivers then fan those properties out to GN inputs, material values, light energy and camera values. A live controller only has to write a few known custom properties.
- Put the agent's scene code in versioned `.py` files (idempotent "build or rebuild" functions). Do not rely on one-off console edits. This fits the fresh-namespace exec model (#55) and lets a broken scene be rebuilt deterministically.
- Prefer non-Python driver types (AVERAGE/SUM, or simple expressions) for live parameters. With script auto-execution off by default, scripted Python drivers on file load are a risk. Inference: the probe confirms only that autoexec is off; that simple-expression drivers bypass it is from general Blender knowledge and not verified here.
- Use NodeToPython in reverse, to turn a hand-tuned or downloaded node graph into code the agent can read and edit, instead of having the agent invent large graphs.
- Add a project skill or a CLAUDE.md section listing the 5.2-specific paths verified above (GN modifier inputs, engine id `BLENDER_EEVEE`). Stale idioms are a predictable failure.

### Gaps
- No published, measured comparison of starter-template versus from-scratch agent scenes.
- It is not confirmed whether Lab's bundled API docs show the new `properties.inputs` path prominently enough for agents to find it.

## 3. Asset sources reachable from agents, and licensing

### Takeaway
Through MCP only the community server integrates assets: Poly Haven (CC0, no key), Poly Pizza (key, mostly CC-BY), Sketchfab (key), and the generators Tripo, Hunyuan3D, Hyper3D Rodin and Meshy (own key or paid "Premium"). It writes license metadata onto imported objects for Poly Haven and Poly Pizza. Hunyuan3D's licence excludes the EU, UK and South Korea, which matters for a Swiss/EU user.

### Cited Findings
- Poly Haven: about 2,400 HDRIs, textures and models, no key. Models import from `.blend` (not glTF, FBX or USD). Textures build a Principled material. HDRIs pack into a new world. All assets are CC0 ([README](https://github.com/ahujasid/mcp-for-blender/blob/main/README.md)).
- Poly Pizza: about 10,600 low-poly models, free key, about 69% CC-BY. Filter with `licence="CC0"`. Credit is written to the `polypizza_attribution` custom property ([README](https://github.com/ahujasid/mcp-for-blender/blob/main/README.md)).
- Generators: `generate_3d` supports Tripo, Hunyuan3D (Tencent Cloud, region-dependent, SecretId and SecretKey), Hyper3D Rodin and Meshy (own key requires a paid Meshy plan). "Premium" generates without user keys. Keys are stored in add-on preferences or env vars such as `BLENDERMCP_TRIPO_API_KEY` ([README](https://github.com/ahujasid/mcp-for-blender/blob/main/README.md)).
- Tencent Hunyuan 3D 2.0 and 2.1 community licences define the territory as worldwide excluding the EU, UK and South Korea. Commercial use is limited (large-MAU use needs a Tencent license) ([HF LICENSE](https://huggingface.co/tencent/Hunyuan3D-2/blob/main/LICENSE); [scancode summary](https://scancode-licensedb.aboutcode.org/tencent-hunyuan-3d-2.0-cla.html)).
- Lab MCP has no asset or network integrations (prior note).

### Inferences
- For a show, the clean path is Poly Haven (CC0) for HDRIs and materials, plus self-made or Blender asset-library content. Treat Poly Pizza and Sketchfab assets as license-tracked, and keep the attribution custom properties in the scene.
- Generated meshes (Tripo, Rodin, Meshy) are usually heavy, non-quad and single-material. For real-time Eevee they need decimation or remeshing before use. This is general practice, not measured here.
- Blender asset libraries (local `.blend` catalogs) need no MCP integration. Agents can `bpy.data.libraries.load(path, link=...)` through `execute_blender_code`.

### Gaps
- Sketchfab download licensing as handled by the server: the README gives few details.
- Output ownership and commercial terms for Tripo, Rodin and Meshy outputs were not checked in their ToS.
- No primary-source check of whether the Hunyuan3D exclusion applies to the cloud API used via Tencent Cloud (versus the open weights).
- Switzerland is not named in the Hunyuan exclusion list. Its legal treatment was not researched.

## 4. Reported quality and limits; failure modes; token costs; mitigations

### Takeaway
Agents do well at layout, primitives, Principled materials, lights, basic camera placement, simple keyframes and batch scripting. They are weak at multi-node Geometry Nodes graphs (and especially debugging them), complex procedural shaders, precise spatial math, animation curves and timing, and aesthetic judgement. The main mitigations are vision checks after each step, version-correct API docs, skills, small steps, and limiting scene-dump size.

### Cited Findings
- MakeUseOf (Bryan M. Wolfe, 2026-09-24, Claude Code + community BlenderMCP): iterative lamp-shade modeling with screenshots worked. A worn-brass shader came out too glossy and Claude fixed the roughness itself. Claude added error handling around heavy modifier stacks and self-referential GN. Failures: on Geometry Nodes, "the second something breaks inside one it already built, it kind of flounders"; a scatter effect took long to diagnose; one Blender crash needed both apps restarted; render-look-adjust loops are slow; "I wouldn't hand it something that has to run unattended overnight" ([MakeUseOf](https://www.makeuseof.com/claude-code-loose-in-blender-is-a-completely-different-assistant-than-it-is-in-a-cad-program/)).
- MindStudio (2026-05-06, community server, Blender 3.x/4.x): Geometry Nodes are "brittle" beyond a few nodes. Basic Principled materials are fine but complex procedural shaders are not. Simple keyframes are fine but curves, timing and rigging are not. Lights can be placed but the model can't judge whether they look right. Placement is imprecise. Training data leans toward older Blender APIs. Connection drops on crash ([MindStudio](https://www.mindstudio.ai/blog/claude-blender-mcp-real-world-performance)). Secondary source.
- A search summary also reports unconnected nodes left in material and GN editors ([search aggregate incl. Vagon, Harkness](https://vagon.io/blog/how-to-use-blender-mcp-with-anthropic-claude-ai)). Not verified at the primary source.
- Devtalk practitioner: precise geometric math (lattices, curves, symmetry) remains unreliable, and docs plus examples got him "50% of the way" ([devtalk](https://devtalk.blender.org/t/built-a-multi-agent-system-on-top-of-blenders-python-api-and-sharing-architecture-learnings-for-the-mcp-discussion/44260)).
- Blender developer Brecht (same thread, 2026-02-08) would "not focus on generative use cases like building an Eiffel Tower". He sees MCP's value in making Blender easier to learn and use: naming, diagnosis, shading fixes, render settings, validation checklists ([devtalk](https://devtalk.blender.org/t/built-a-multi-agent-system-on-top-of-blenders-python-api-and-sharing-architecture-learnings-for-the-mcp-discussion/44260)).
- Token and context cost: in a Codex trajectory, `get_objects_summary` on a 1,670-object scene returned about 904 KB and added about 15.5k–15.7k input tokens to the next request. A clearer tool description reduced misuse (Lab issue #54, 2026-09-12) ([issue #54](https://projects.blender.org/api/v1/repos/lab/blender_mcp/issues/54)).
- Lab issue #64: server instructions say to return lists but the result must be a dict, which is a source of avoidable errors ([issues API](https://projects.blender.org/api/v1/repos/lab/blender_mcp/issues?state=open&type=issues&limit=50)).
- Stale API confirmed locally: the common 4.x GN-modifier input idiom fails on 5.2.3, with the replacement path described in Q2 (local probe, 2026-11-03).
- Mitigations reported in sources: the skills registry in the `blender-agent` fork ([issue #39](https://projects.blender.org/api/v1/repos/lab/blender_mcp/issues/39)); bundled API and manual search in Lab MCP ([readme.md](https://projects.blender.org/lab/blender_mcp/raw/branch/main/readme.md)); RAG over the API docs plus DSPy-optimized prompts ([devtalk](https://devtalk.blender.org/t/built-a-multi-agent-system-on-top-of-blenders-python-api-and-sharing-architecture-learnings-for-the-mcp-discussion/44260)); "break large requests into steps" ([README](https://github.com/ahujasid/mcp-for-blender/blob/main/README.md)).

### Inferences
- The biggest quality risks for a VJ scene are GN graphs and shader networks. Keep them small and modular: several small node groups with named, exposed inputs, built from version-checked code or converted with NodeToPython, rather than one large agent-invented graph.
- Animation for live visuals is better expressed as drivers or GN time inputs bound to control properties than as hand-keyed F-curves, which agents handle badly. This also matches live control.
- Budget context per step. Use the cheap inspectors (`get_object_detail_summary`, path info, `get_scene_info` with `query`) and bounded screenshots, not whole-scene dumps.

### Gaps
- No quantitative benchmark (success rate per task type, tokens per finished scene) for Claude plus either server on Blender 5.x was found.
- Nothing found on Opus- or Sonnet-specific behaviour differences in Blender.

## 5. Published workflows and case studies of MCP-built scenes used for real-time or live visuals

### Takeaway
I found no credible published case study of an MCP-authored Blender scene used for live or VJ visuals. Coverage is demos, hands-on articles, and advice to treat MCP as a prototyping and assistance tool.

### Cited Findings
- A targeted search ("blender mcp" VJ live visuals) returned only general Blender MCP listings and generic VJ pages, with no MCP-to-live-show workflow ([sandraschi/blender-mcp](https://github.com/sandraschi/blender-mcp); [gamedev.tv VJ thread](https://community.gamedev.tv/t/any-ideas-how-to-be-a-live-vj/227910)).
- One user report surfaced in search: heavy production scenes block the UI because MCP runs on Blender's main thread ([search aggregate](https://repos.skila.ai/servers/blender-mcp)). Consistent with the community README's main-thread note ([README](https://github.com/ahujasid/mcp-for-blender/blob/main/README.md)) and the Lab add-on's `bpy.app.timers` polling (prior note).
- Example prompts the community README advertises are scene-level ("low poly scene in a dungeon", "beach vibe using HDRIs ... from Poly Haven", "make the lighting like a studio", "make it isometric"), not live-performance workflows ([README](https://github.com/ahujasid/mcp-for-blender/blob/main/README.md)).

### Inferences
- For SwiftVJ this is new ground. The defensible workflow from the evidence: the agent authors a parameterized scene offline over MCP (from a template, with control custom properties and drivers), screenshots and renders verify it, and the author commits it. At show time MCP is stopped, and only the separate live-control and video-out path drives the scene (prior note).
- Main-thread blocking means do not run MCP authoring calls against the Blender instance that is outputting during a show.

### Gaps
- No case studies, talks or devtalk threads on agent-authored real-time or VJ Blender scenes were found. Searches on YouTube and social media were not done, and may hold demos of uncertain reliability.
