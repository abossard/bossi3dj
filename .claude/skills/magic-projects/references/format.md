# .magic format (Magic 3.0b6)

Facts marked *live* were read back from Magic's Syphon frame; the rest come from Magic's own saves (45 files: bundled SampleProjects plus user projects), its User's Guide and strings in its binary. Full evidence: `docs/magic-tooling-report.md`.

## Contents
- File and XML layout
- Ids and links
- Sources (layerID / feature)
- Modifiers
- Modules and params
- Audio files
- Syphon and OSC

## File and XML layout

- 3 header bytes, then zlib. Magic's saves have a different random header each time; it never checks it.
- Magic writes CRLF and wrapped attributes; any well-formed XML with the same elements loads. Round-trips are semantic, not byte-identical.
- `<Project>` attrs: `videoSharing` (Syphon on), `videoSharingName` (*live*: server name, default "Main Server"), `videoSharingWidth/Height` (graphics resolution, *live*), `looping` (audio files), `version="1.5"`, `actualVersion="3"`.
- Children in order: `RenderSettings` (movie export only, *live*: does not change the graphics size), `PlaylistMidiConfig`, `SoundFiles`, `AudioFiles version="2"`, `Tracks`, `Layers`, `Scenes`, `Playlists`, `Tabs`, `TabsVisible`, `SceneTreeItems`, `Globals`.
- `Scene name id` holds `Root/Node` (the "Magic" output node, `magicNode="1"`, its `Children` are the scene outputs) and `Nodes/Node...`.
- `Tabs/Tab` (one per scene, same order) holds editor positions `Node x y id`. Some of Magic's own samples lack entries for some nodes and still load.

## Ids and links

- `Node id`, `InputValue id`, `Track id`, `Layer id` share one counter in Magic's saves; keep them unique (`magicproj.next_id`). Magic renumbers all of them every time it saves (*live*), so compare projects with `magicproj diff`, which keys nodes by module name and position.
- `Child id` = a node in the same scene feeding this node's input pin, first child = first pin.
- Scene module: a `Node` whose `pluginName` is the scene name and `sceneID` = that `Scene@id` (not its position).
- `globalsUseID="1"`: a Global link's `feature` is the Global's `InputValue id`. Without it (old files) it is the index in `Globals`.

## Sources (on any `InputValue`: a Global or a module param)

| `linked` | `layerID` | Meaning |
|---|---|---|
| 0 | -1 | manual value (`value`) |
| 1 | -1 | no source: input 0, modifiers compute it ("calc") |
| 1 | 2147483646 | Global, `feature` = Global id |
| 1 | 2147483645 | Internals, `feature` index below |
| 1 | a `Layer id` | that source; its `Track` decides audio, MIDI (`isMidi`) or OSC (`isOSC`, `channel` = port, address in `featureString`, `"/addr 1"` picks argument 1) |

Audio `feature`: 0 Volume, 1 Freq. Range, 2 Best Pitch, 3 Tone. Freq. Range `subFeature`: 0 20-80 Hz, 1 80-320, 2 320-1.2k, 3 1.2k-5k, 4 5k-20k, 5 Custom, 6 Iterator. All 0..1.

Internals `feature`: 0 and 2 graphics width, 1 and 3 graphics height (*live*), 4 Playlist Entry # (*binary*; reads 0 on entry 0), 5 playback time in s, 6 graphics FPS, 7 Iteration #, 8 Total Iterations (1 outside an Iterator), 10 Audio/MIDI Playing (*live*), 11 Playback Seeked (*binary*). 9 reads 0 and has no label. The User's Guide's table order is not the index order. MIDI feature indices: [inputs.md](inputs.md).

Evaluation (*live*): every Global and param reads the previous frame's value of each Global it names, independent of list order. A chain of N Global hops lags N frames.

## Modifiers (`ValueOperators/ValueOperator`)

`type` = index: 0 Gate, 1 Scale, 2 Offset, 3 Power, 4 Smooth, 5 Wrap, 6 Random, 7 Ramp, 8 Sine, 9 Triangle, 10 Threshold, 11 Average, 12 Peak, 13 Exponent, 14 Clamp, 15 Step, 16 Increase, 17 Trigger, 18 Invert, 19 Hold, 20 Delay, 21 Expression, 22 RandomTrigger.

- `param` is the numeric parameter; `paramString` is the expression (only read for type 21; other types carry `"x"`).
- Expression is ExprTk: `x` input, `y` previous output, Globals by name (case-insensitive). `var a := ...;` declares locals.
- Meaning per type (User's Guide): Average over `param` s (max 1), Smooth 0..1, Peak decays by `param` (holds too long for drums), Increase/Ramp/Sine/Triangle generate from time at rate `param` + input, Trigger counts rising crossings of `param`, Hold/Delay in seconds, Threshold → 0/1, Gate → 0 below, Clamp caps at `param`, Step rounds to multiples, Wrap = mod, Invert = p - x, Power = x^p, Exponent = p^x.
- `bypassed="1"` passes the input through.

## Modules and params

- `Node pluginName` = module name. ISF modules (Effects2D, Layers, Modules2, Additional Module Folders) are named after the `.fs` file; native modules are `.dylib`.
- Param names for ISF (*live*, all 189 bundled shaders): `LABEL`, else `NAME`, first letter capitalised; `point2D` becomes `<Name> X`/`<Name> Y`; `color` becomes `<Name> R/G/B/A`; a shader that uses `TIME` gets a `Speed` param (`Speed (M)` if it already has one); an audio input becomes `Source`. `magicproj catalog` lists the exact names Magic 3 saves.
- Every module with an input pin has `Bypass`; every module has `Power`. Magic fills in any param a file leaves out (*live*), so generated files may list only the params they set. Link them like any param; `bypassParamUsed="1"` / `powerParamUsed="1"` on the node marks the param as shown (Builder sets it for linked ones).
- `OSCSender` params: `IP Addr.`, `Port`, `Message`, `Value`. One target per sender; it sends only when `Value` changes.
- `SyphonClient` param `Server` = `"<server name> - <app name>"`.
- Coordinates (*live*, 1920x1080): y runs -1 (bottom) to 1 (top), x about -1.78 to 1.78; one unit is half the frame height. `Polygon Sides 4` at Scale 1 is a square as tall as the frame, axis-aligned.
- `Text` params include `Text` (lines separated by `\\`) and `Line #` (-1 = all lines).

## Audio files

- `SoundFiles/SoundFile` and `AudioFiles/AudioFile` (same `filename`; absolute in generated files, bare names like `Bach.ogg` resolve next to the project), one `Track isInput="0" soundFileIndex audioFileIndex channel` per channel, then point a `Layer trackID` at a file track. `looping="1"` loops.
- Playback starts with the play button or Shift+Cmd+Space in Magic (*live*); the Volume feature then follows the file (*live*: 0.79 for a 0.79-amplitude tone).
- `Track isInput="0"` without a file index is "Module Audio Output" (VideoFile audio).

## Syphon and OSC

- Syphon out: `videoSharing="1"`. Frames read with syphon-python are bottom-up; `magicproj grab` flips them.
- OSC in: a `Track isOSC="1" channel=<port>` plus a `Layer`. OSC out: OSCSender modules. To keep senders running whatever scene the playlist shows, put them in their own scene and draw it as a scene module from every shown scene, or from the post-processing scene (inference: a module runs only while something draws it).
