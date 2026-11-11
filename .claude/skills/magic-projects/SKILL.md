---
name: magic-projects
description: Work with Magic Music Visuals (Magic 3, Magic.app or MagicBeta.app) and its .magic projects. Read, explain, check, diff, edit, generate and live-verify scenes, modules, Globals, modifiers, ExprTk expressions, audio, MIDI and OSC inputs and mappings, OSCSender output, Iterators, ISF/GLSL shaders and custom modules, video, camera and Syphon inputs, Syphon output, playlists and transitions, audio file playback, movie export and live-performance settings. Use whenever the user mentions Magic or Magic Music Visuals, a .magic file, a Magic scene, module, Global or modifier, Magic MIDI/OSC learn, or Magic V3 compatibility, even if they only say "my visuals project" or "the Magic patch".
---

# Magic Music Visuals

Magic (`/Applications/Magic.app`, beta `MagicBeta.app`) builds audio-reactive visuals from scenes of connected modules whose parameters link to audio, MIDI, OSC, Globals and Internals through modifier chains. A project is one `.magic` file: 3 ignored header bytes + zlib XML.

Work through `python3 magic/magicproj.py` (stdlib Python, no install). It decodes, validates and rewrites the XML while keeping ids, links and editor positions consistent. Hand-editing the XML with sed or regex breaks those silently, and Magic shows the damage only as dead links or missing modules.

## Official documentation

The authoritative docs ship inside the app; cite them when answering:
- User's Guide: `/Applications/MagicBeta.app/Contents/MacOS/UsersGuide/Magic_UsersGuide.html` (or `Magic.app`), sections Input Sources, Magic Window, Playlist Window, Projects, Modules, Global Parameters, Exporting Movies, Optimizing For Live Performance, Troubleshooting.
- Version history with "What's New In Version 3.0": `.../Contents/MacOS/VersionHistory.txt`.
- Sample projects for every feature: `.../Contents/MacOS/SampleProjects/*.magic` (pre-3.0 saves; Magic 3 migrates them, see [v3.md](references/v3.md)).
- The references below condense these and add what was verified in the running app.

## Pick the reference for the topic

Read only what the task needs:

| Topic | Reference |
|---|---|
| File layout, ids, links, source encoding, modifier types, coordinates | [format.md](references/format.md) |
| Scenes, scene modules, layers, the module catalog, Iterator, ISF/GLSL/FFGL and custom modules | [modules.md](references/modules.md) |
| Audio, MIDI, OSC input and features, MIDI/OSC learn, OSC/MIDI output, video, camera and Syphon inputs, Globals | [inputs.md](references/inputs.md) |
| Magic window, graphics resolution, playlist and transitions, audio file playback, export, video sharing, projects and assets, live performance tuning | [playback.md](references/playback.md) |
| Magic 3.0 changes, V3 compatibility of old projects, app settings vs project settings | [v3.md](references/v3.md) |

## Commands

| Need | Command |
|---|---|
| Overview: scenes, playlist, Syphon, audio, sources | `info FILE` |
| Every Global: source, value, modifier chain | `globals FILE [--name REGEX]` |
| Modules per scene, params and links | `nodes FILE [--scene NAME] [--plugin REGEX]` |
| OSCSender addresses, targets, value sources | `osc FILE` |
| Validate (exit 1 on errors) | `check FILE` |
| Semantic diff (Globals by name, nodes by scene/id) | `diff A B` |
| Param names and defaults of a module | `catalog [--plugin REGEX] [FILES]` |
| Raw XML | `decode FILE [-o X.xml]`, `encode X.xml -o FILE` |
| Edit | `set FILE -o OUT ...` (below) |
| Load into the running Magic | `load FILE` |
| Read Magic's output frame | `grab [--server NAME] [--out PNG] [--wait S]` |
| Play/pause audio files | `play` |
| Log OSC that Magic sends | `listen PORT [--seconds S]` |

`set` options (repeatable, applied in this order, checked before writing; `--force` writes anyway):
- `--remove-global NAME`, `--add-global NAME=VALUE`, `--value GLOBAL VALUE`, `--rename OLD NEW` (rewrites expressions too)
- `--source GLOBAL SOURCE`: `manual`, `calc`, `global:Name`, `osc:/addr`, `midi:<source>:<feature>[:<sub>]`, `internal:Name`, `audio:<source>:<feature>[:<range>]`, e.g. `audio:Source 0:Freq. Range:20-80 Hz`
- `--mods GLOBAL 'Smooth:0.6; x*Gain*4; Clamp:1'` replaces the chain; bare text is an Expression
- `--param SCENE/NODE_ID/PARAM VALUE` or `@SOURCE`; node ids come from `nodes`; `--inputs SCENE/NODE_ID ID,ID` rewires a node's input pins (top pin first)
- `--syphon on|off`, `--syphon-name NAME`, `--size 1920x1080`
- `--osc-target IP:PORT [--osc-prefix /addr/]`, `--osc-in PORT`
- `--midi-in DEVICE[:CHANNEL][=SOURCE]` adds a MIDI source; `--route SOURCE=DEVICE[:CHANNEL]` points a source at an audio input (3.0: sources may use different devices)
- `--playlist-scenes A,B --playlist-seconds 16 --playlist-transition 2 --playlist-style none|crossfade|additive`
- `--audio FILE [--audio-source "Source 0"]` adds a looping audio file and routes the source (and the next one) to it; `--looping on|off` sets file looping alone

For new projects and structural edits (scenes, module chains, Iterators, playlists) write a short Python script with `magicproj.Builder` and the library edit functions (`edit_global`, `edit_param`, `add_global`, ...). They return modified copies, so the script can `diff` before and after. Get module param names from `catalog`: it lists the exact params and defaults Magic 3 saves for every bundled module (`magic_modules_v3.json`), plus ISF modules in the user's Additional Module Folders. Generated files may leave params out; Magic fills in defaults. `check` warns on pre-3.0 module and param names, so run it on old projects before editing them.

## Workflow

1. Inspect: `info`, then `globals`/`nodes`/`osc` for the part you touch. Quote names exactly as printed.
2. Edit into a new file (`-o`) unless the user asked for in place. If a script generates the project, change the script and regenerate.
3. `check` and `diff` against the original. Report the diff lines that matter; an unexpected line means the edit did more than intended.
4. Verify in the app only when the task needs it.

## Running app

The user may be performing or editing in Magic:
- `load` replaces the open project. Read the current one from `load`'s window titles first (the editor title names the file), and load it back afterwards. Unsaved edits there are lost, so ask when the user may have some.
- `play` presses Shift+Cmd+Space, which brings Magic to the front. Say so; call it again to pause.
- Preferences (Additional Module Folders, audio device, MIDI/OSC enable) are the user's settings. Ask before changing them or telling the user to; custom ISF modules only load from such a folder.
- `listen` binds a UDP port. Use a free one (`lsof -nP -iUDP:PORT`), and retarget a copy's OSCSenders there (`--osc-target 127.0.0.1:PORT`) instead of binding a port another app owns. `listen` refuses `MAGICPROJ_RESERVED_PORTS` (default 9201).

## Verifying output

- `grab` reads one frame over Syphon (Magic publishes it with `set --syphon on`; server "<name> - Magic", default "Main Server"). It prints size, mean RGB, lit fraction and a 3x3 colour grid; `--out` writes a PNG to look at.
- `grab` needs syphon-python; it re-runs itself under `python3.13` with `PYTHONPATH=~/.local/lib/python3.13/site-packages` (override with `SYPHON_PYTHON`, `SYPHON_PYTHONPATH`).
- To prove an edit, make it visible: link a colour or size to the value you changed, grab before and after, compare numbers. `tests/test_magicproj.py:LiveMagicTests` is a worked example (`MAGICPROJ_LIVE=1 MAGICPROJ_RESTORE=<project to reload>`).
- Audio files need playback: `load`, `play`, wait, `grab`, `play`. `internal:Audio/MIDI Playing` and `internal:Playback Time` show the state in the frame.

## Semantics (verified in Magic 3.0b6)

- Every Global and param reads the previous frame's value of the Globals it names, whatever the list order. Each Global-to-Global hop adds one frame of latency.
- A `calc` Global (no source) starts at 0 at load; feedback expressions (`y` = previous output) need a seed or guard.
- Peak holds far too long for drums; use `max(x, y*exp(-Dt*k))` with a `Dt` Global from an Increase clock.
- OSCSender sends only when its value changes, so a constant never arrives; add a short jitter at load if the receiver needs an initial value.
- Text cannot print numbers: use a multi-line Text and link `Line #`.
- ExprTk names are case-insensitive; Global names used in expressions need no spaces and must not be `x`, `y` or a function name.
- Internals indices differ from the User's Guide order (format.md has the measured table).
- Params are clamped to their range silently; the modifier output shown can still exceed it.

## This repository

This repository also holds a Magic → Blender OSC setup (`magic/` generators, an optional `osc/lab.py` debug relay, a Blender bridge or Godot scene on UDP 9201). Read [repo-lab.md](references/repo-lab.md) only for work on that setup.
