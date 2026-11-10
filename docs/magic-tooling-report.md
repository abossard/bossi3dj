# Tooling for Magic Music Visuals projects

Question: how should Claude read, inspect, diff, edit and generate Magic 3.0b6 (`/Applications/MagicBeta.app`) `.magic` projects and verify them in the running app: a skill, an MCP server, or both.

Researched 2026-11-04 on this Mac. Labels: **Fact** (seen in a file, the binary or a live frame), **Inference**, **Rec**.

## Answer

- **Rec:** a project skill, `.claude/skills/magic-projects/`, that drives a stdlib Python library and CLI, `magic/magicproj.py`. No MCP server.
- **Rec:** keep every live-app action (load, grab, play, listen) in the same CLI, behind explicit commands, so the skill can state when each one is safe.
- Built and verified: 29 unit tests (parametrised with `subTest`), a live build/edit/load/grab test, and skill-creator evals (results below).

## File format

- **Fact:** a `.magic` file is 3 header bytes + zlib XML. Magic's own saves carry a different header each time (`u6m`, `nL\x14`, `eKm`... across 45 files); Magic never checks it. `encode`/`decode` use `L*h`.
- **Fact:** Magic (JUCE) writes CRLF and wraps attributes. ElementTree output with the same elements loads fine (synthwave_pyramids.magic and every probe below). Round-trips are semantic, not byte-identical: all 36 bundled SampleProjects plus 9 user projects give an identical canonical tree after `parse -> serialize -> parse` (`CodecTests`).
- **Fact:** layout, ids, links and source encoding are in [the skill's format reference](../../../.claude/skills/magic-projects/references/format.md). Main points:
  - `Project` attrs `videoSharing`, `videoSharingName`, `videoSharingWidth/Height`, `looping`. `videoSharingName` was found in the binary's strings and confirmed live (server "magicproj-e2e - Magic").
  - Globals live in `<Globals>` as `InputValue`s; a link is `layerID=2147483646 feature=<Global id>` (`globalsUseID="1"`). Internals is `layerID=2147483645`.
  - Modifier `type` is the index into Magic's modifier list (binary strings: Gate, Scale, Offset, Smooth, ... with Power at 3). Type 21 holds every real expression in the samples.
  - A scene module's `sceneID` is the target `Scene@id`, not its position (Effects2DExamples has ids 1..9, 11).
  - Audio features 0 Volume, 1 Freq. Range, 2 Best Pitch, 3 Tone, ranges 0..6, in the binary's string table order.
- **Fact:** ISF modules declare params in the `.fs` JSON header. Magic's param name is `LABEL`, else `NAME` with a capital first letter, `point2D` as `<Name> X/Y` (`Chroma Zoom.fs` `master_zoom` is `Master_zoom` in the working synthwave project).

## Semantics verified live

Each row: build a probe with `magicproj.Builder`, `load`, `grab`, read pixel values. Magic reloaded `synthwave_pyramids.magic` after each run.

| Question | Probe | Result |
|---|---|---|
| Internals feature index | 9 stripes, brightness `x/2000` and `x` per index 0..8, again for 8..16 while playing | 0/2 = 1920 and 1/3 = 1080 (then 1280/720 after `--size 1280x720`), 5 = playback time (~3 s), 6 = ~150 (FPS), 7 = 0 (Iteration #), 8 ≥ 1, 10 = 0 stopped / 1 playing. The User's Guide order (Iteration # = 7 fits, Graphics Width = 4 does not) is not the index order. |
| Graphics resolution | RenderSettings 1600x900, videoSharing 1280x720 | frame 1280x720; RenderSettings only affects movie export |
| Global evaluation order | `Before=Count`, `Count=y+1`, `After=Count`; show `Count-Before`, `Count-After` | both 1, in a module param and inside later Globals. Every Global reads the previous frame's values; list order does not matter (matches the User's Guide, contradicts the note in `synthwave_magic.py`) |
| Audio file | `add_audio` a 20 s 440 Hz tone at amplitude 0.79, `play`, link Volume | Volume reads 0.79 (202/255) |
| Playback control | `play` = System Events Shift+Cmd+Space | toggles; Magic comes to the front |
| Coordinates | stripes at known Scale/Translate | 1 unit = half the frame height, x ±1.78, y ±1 |

## Operations the tool must support

| Operation | Why | `magicproj` |
|---|---|---|
| read, summarise | Globals and modifier chains are unreadable in raw XML (ids instead of names) | `info`, `globals`, `nodes`, `osc` |
| validate | Magic silently drops or mislinks broken ids; ExprTk typos only show in the editor | `check`: duplicate ids, dangling Global/source/input links, unknown modifiers, unknown expression names, reserved names, missing files, missing editor positions |
| diff | regenerated files differ in ids and formatting; text diff of XML is noise | `diff` keyed by Global name and scene/node id |
| edit | values, sources, modifier chains, renames, params, Syphon, OSC targets, OSC in, audio files | `set ...`, library `edit_*` functions (pure, return copies) |
| generate | new scenes and module chains with valid ids and editor layout | `Builder` |
| module params | names come from ISF headers or from saves of native modules | `catalog` |
| verify live | prove an edit reached the app | `load`, `grab`, `play`, `listen` |

Calibration: `check` reports 0 errors on all 45 Magic-saved files (the 36 samples are in `CheckTests.test_magic_saves_have_no_errors`). Its first version flagged several of them (Effects2DExamples, FunWithStars, ManyScenes, MIDIPiano, SceneGroupsExample, SceneModulesExample2 among others), which found the `sceneID` = `Scene@id` rule, case-insensitive ExprTk names (MIDIPiano uses `X`) and "Module Audio Output" tracks.

## Options weighed

| | Skill + CLI (chosen) | MCP server | Both |
|---|---|---|---|
| Install | none: project skill in the repo, stdlib Python | needs an entry in the user's Claude config (not allowed without asking) and a running process | both costs |
| Live app access | `open -a`, System Events window titles, syphon-python in a subprocess: one-shot commands, no state to keep | same calls; a long-lived Syphon client buys nothing because a grab takes ~1 s cold | same |
| Testability | plain functions, `unittest`, CLI in subprocess | needs a protocol harness | |
| Composability | output pipes into `jq`, scripts import the library and `Builder` | tool calls only; generators still need a library | |
| Discoverability | skill description triggers on `.magic`, Globals, Syphon, OSCSender | tools always listed, even when unrelated | |
| Safety rules | the skill explains why (port 9201, project replacement, focus) next to the commands | descriptions are short; rules get lost | |

- **Inference:** an MCP only pays off with state that outlives a command (a persistent OSC tap, an open Syphon client streaming frames) or for clients without a shell. Neither applies here: every live check is load, wait, grab once.
- **Fact:** Magic has no remote API for loading or playback. `open -a` loads; menus are reachable through System Events, but the play button is not (no menu item); Shift+Cmd+Space works when Magic is frontmost.

## Constraints the skill teaches

- `load` replaces Magic's project; note the editor title first and reload it (the tests take `MAGICPROJ_RESTORE`).
- Port 9201 belongs to the Blender bridge; `listen` refuses it.
- `play` takes focus from the user.
- Additional Module Folders (needed for custom ISF modules) are a user preference in `~/Library/Application Support/MAGIC/MAGIC_1_0.xml`; `catalog` reads it, nothing writes it.

## End-to-end check

`MAGICPROJ_LIVE=1 MAGICPROJ_RESTORE=<main checkout>/magic/projects/synthwave_pyramids.magic python3 magic/tests/test_magicproj.py -v LiveMagicTests`

- Builds a project (Globals with audio, OSC, Internals sources; Polygon → Scale → ColorHSB; OSCSender), adds a calculated `Bright` Global from Internals width, sets Hue 0 then 1/3, loads each, grabs server `magicproj-e2e` over Syphon.
- Passed: centre pixel red, then green, at full brightness; Magic ended on `synthwave_pyramids.magic - Editor - Master`.
- The first run failed at brightness 77 (0.3): it was written against the User's Guide's Internals order. That failure led to the Internals probes above.

## Skill evals

- 5 evals, 2 iterations, with and without the skill: 35/35 vs 34/35 assertions in iteration 2. Baselines found `magicproj.py` in the worktree, so the skill shows mostly as cost (evals 1-4: 46% less time, 17% fewer tokens) and in the live-app plan.
- The eval runs found one bug (`listen` crashed on the first message), now fixed and tested.
- Description: trigger proxy 20/20 (12 train, 8 held out); `run_loop.py` could not run because nested `claude -p` cannot authenticate in this session.
- Details: [magic-skill-evals.md](magic-skill-evals.md).

## Follow-ups

- `synthwave_magic.py` says Global order matters; it does not, and its onset chain (KickBand → KFast → KRaw → KOn → Kick) lags about 4 frames.
- Internals 4 and 9 read 0 in every probe; Playlist Entry # and Playback Seeked are the remaining candidates.

## Magic 3 compatibility (second pass)

Sources: the User's Guide and "What's New In Version 3.0" shipped in the app bundle. magicmusicvisuals.com returns a bot check to automated fetches and to the browser pane, so the online pages were not compared.

- **Fact (live):** a generated project with all 221 bundled modules and no params, loaded and saved by Magic 3.0b6, came back with every param and default. That save is `magic_modules_v3.json`; `catalog`, `check` and the Builder's Bypass handling use it. Magic fills in params a file omits.
- **Fact (live):** re-saving pre-3.0 samples (ManyScenes, LayersExamples) renames `Image` to `ImageFile`, drops `Premultiply`, `Grayscale`, Kaleidoscope `Corners`, adds `Additive`, `Audio`, `Audio Gain`, `Zoom`, `Rotation`, `Fill Edges`, sets `actualVersion="3"`, adds `absoluteFilename` to File params and renumbers every id. `check` now reports 0 migration warnings on the re-saved files; `diff` keys nodes by module and position so it survives renumbering.
- **Fact (live):** ISF param naming across all 189 bundled shaders: label or name with a capital first letter, `point2D` as X/Y, `color` as R/G/B/A, `Speed` added for shaders using `TIME`, audio inputs as `Source`.
- **Fact (binary):** MIDI feature table 0 Velocity ... 10 Iterator Notes; Internals 4 Playlist Entry #, 11 Playback Seeked.
- **Fact (saved):** `Tabs` are not stored in scene order (MIDIPiano).
- **Inference:** playlist transition `style` 0/1/2 = none/crossfade/additive (button letters N/C/A in the binary, guide order). Not confirmed in the app: the transition column is behind a popup menu, and computer use for Magic was declined.
- Feature-by-feature map: [the skill's v3.md](../../../.claude/skills/magic-projects/references/v3.md).
