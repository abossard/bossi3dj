# Inputs, features and mapping (Magic 3.0b6)

Tags: (saved file) = Magic's own saves (SampleProjects plus the user's `synesthesia-visuals/magic/*.magic`, all CRLF Magic output). (binary) = strings or disassembly of `Magic` and module dylibs. (guide) = User's Guide. File layout, ids, the `layerID` sentinel table, audio `feature`/Freq. Range `subFeature`, modifiers and Internals live in [format.md](format.md). This file does not repeat them.

## Contents
- Input Sources window: Tracks and Layers
- Audio features
- MIDI features
- OSC input
- MIDI/OSC Learn
- Modifier param/bypass MIDI/OSC control
- Playlist MIDI/OSC control
- Outputs: OSC, MIDI, Syphon/Spout
- Video inputs
- Globals
- Export and Internals notes

## Input Sources window: Tracks and Layers

- `Track` = one channel Magic can read (device channel, file channel, OSC port). `Layer` = one row ("source") in the Input Sources window. Params link to a `Layer id`, never to a Track (saved file).
- `Layer name` is the user label shown in module menus. Default "Source #" (guide, saved file).
- `Layer trackID="-1"` = source with no device present (MIDIPiano "MIDI", master-bus "Source 1"). Magic loads it (saved file).
- Re-routing a source to another device keeps module links, because links name the Layer (guide).
- Audio input Track: `isInput="1"`, `channel` = device channel, `name="<device> <channel>"`, optional `deviceName` (newer and Windows saves) (saved file).
- One Track per channel of every audio device Magic saw (Effects2DExamples lists 3 devices) (saved file).
- MIDI input Track: `isInput="1" isMidi="1"`, `name` = device name, `channel` 0..16. Magic writes all 17 for every MIDI device present (debug.magic: IAC plus two Launchpad ports, 51 Tracks) (saved file).
- MIDI channel 0 = "global" channel for non-channel messages such as Beat Clock. Channel 1 is the default (guide).
- OSC Track: `isInput="1" isOSC="1" name="Open Sound Control" channel=<UDP port>` (saved file). Default port 8000 (guide). Menu "Change OSC Port" (binary).
- Several OSC ports work at once: master-bus has OSC Tracks on 8000 and 16666, each with its own Layer (saved file).
- Gain: `Layer gain` and `gainVisible` ("Show Gain" slider). Up to +/-24 dB per audio source, saved with the project (guide). Every save holds `gain="0" gainVisible="0"`, so the stored unit is unconfirmed (saved file).
- Module Audio Output: two Tracks `isInput="0" name="Module Audio Output 0/1"` with no file index (saved file). Mix of all VideoFile modules with Audio on, global to the project (guide). No sample routes a Layer to them (saved file).
- Audio files: see format.md. MIDIFileExample stores bare names (`filename="Bach.ogg"`), resolved next to the project (saved file).
- MIDI file: `SoundFile`/`AudioFile filename="Bach.mid"` plus 17 Tracks `isInput="0" isMidi="1" soundFileIndex audioFileIndex channel=0..16 name="Bach.mid"` (saved file).
- MIDIFileExample's Layers "Ch 1..3" point at the file Tracks with `channel` 1..3 (saved file).
- MIDIFileExample sets `isMuted="1"` on the .mid, so only Bach.ogg is heard. Graphics still follow muted files (saved file, guide).
- MIDI file notes are only heard through a MIDI output device (Input Sources menu "MIDI Output Device"). That device is an app setting, not a project attribute (guide; no save carries it).
- Record MIDI Input writes a .mid and adds it to the project (guide).
- Live inputs need no playback. Files respond only while playing (guide).
- Menu items: Add Source, Rename Source, Remove Source(s), Adjust Gain, Change Source Device/File, Re-Scan MIDI Devices, Restart Input Device(s), Merge Duplicate Sources..., Disable All MIDI/OSC Input (binary).

## Audio features

- Index and Freq. Range sub-indices: see format.md. The binary label arrays are in index order: Volume, Freq. Range, Best Pitch, Tone. Ranges: 20-80 Hz, 80-320 Hz, 320-1.2k Hz, 1.2k-5k Hz, 5k-20k Hz, Custom Freq., Iterator Freqs. (binary).
- All audio features are 0..1 (guide).
- Volume: overall amplitude (guide). Used by 26 saves (saved file).
- Freq. Range presets: FreqRanges.magic uses subFeature 0-4 (saved file). Iterator Freqs. (subFeature 6): IteratorCubeExamples, IteratorSpectrumExamples, StereoSpectrum_30Band (saved file).
- Custom Freq. (`feature="1" subFeature="5"`): cutoffs go in `extraFeature1` (low) and `extraFeature2` (high) on the same `InputValue`, as doubles (binary).
  - The writer emits the two attributes only when feature == 1 and subFeature == 5 (binary, disassembly).
  - Load defaults when missing: 200 and 2500 (binary, constants read by the loader).
  - UI labels: "Set Custom Freq.", "Lower cutoff frequency", "Upper cutoff frequency" (binary).
  - No save uses Custom Freq., so the units (Hz by label) and the 200/2500 defaults are not confirmed by a saved file.
- Best Pitch (`feature="2"`): monophonic pitch, 40 Hz = 0 to 2560 Hz = 1, log, 1/6 per octave (guide). Example: ScrollingPitchTracker.magic (saved file).
- Tone (`feature="3"`): brightness, 40 Hz to 20480 Hz, log (guide). Examples: SimpleStereoColor, MoreScenes, ManyScenes (saved file).

## MIDI features

Stored on the `InputValue` whose `layerID` points at a Layer on an `isMidi` Track. Index order is the binary's label table (`Velocity` ... `Iterator Notes`, contiguous pointer array) (binary).

| `feature` | Name (menu label) | `subFeature` | Confirmed by a save |
|---|---|---|---|
| 0 | Velocity: highest velocity of held notes | 0 | yes: MIDIFileExample sizes (Scale X/Y) |
| 1 | Pitch Bend: -8192..8191 to 0..1, centre 0.5 | 0 | no |
| 2 | Note Number: last note, 0..127 to 0..1 | 0 | yes: MIDIFileExample Hue `*127 -> Wrap 12 -> /12`, Y position |
| 3 | Control Change (Ctrl. Change) | CC number | yes: master-bus Blackout CC 19, Buildup CC 27 |
| 4 | Aftertouch, per note | note number | no |
| 5 | Channel Pressure (Ch. Pressure) | 0 | no |
| 6 | Program Change (Prog. Change) | 0 | yes: default of every `PlaylistMidiConfig` |
| 7 | Note Velocity, per note | note number | yes: master-bus Drop note 9, sample playlist Prev/Next notes 3/4/24/33/40 |
| 8 | Beat Clock | 0 beat, 1 /2, 2 /3, 3 /4, 4 Clock BPM | no |
| 9 | Control Change Number (Ctrl. Number): last CC used | 0 | no |
| 10 | Iterator Notes: velocity of note = current Iterator index | 0 | yes: MIDIPiano (Saturation, Power, Bypass, Angle) |

- Beat Clock sub-labels come from a separate binary array: Beat Clock, Beat Clock /2, /3, /4, Clock BPM (binary). Order matches the guide.
- Scaling: everything 0..1 (value/127) for params. The Playlist sees raw 0..127 (guide).
- Beat Clock: 24 ppqn, 1 at the start of a beat falling linearly to 0. Clock BPM: 1.0 = 120 BPM, 0.5 = 60 (guide).
- Note range for per-note features: low C (octave -2) to high G (octave 8), i.e. 128 notes (guide). That `subFeature` is the raw note number is inferred from master-bus and the playlist values, not read from code.
- The guide's table lists the features in a different order. Use the index table above.
- Not usable for the Playlist: Pitch Bend, Beat Clock, Iterator Notes (guide).
- master-bus "Drop" shows the momentary-to-toggle idiom: Note Velocity note 9 -> Trigger 0.5 -> Wrap 2 (saved file).
- MIDIPiano links Power/Bypass to Iterator Notes through Threshold (0.01 or 0.0001, some followed by Invert), so each key's modules switch with its held note (saved file).

## OSC input

- Link: `layerID` = a Layer on an `isOSC` Track, address in `featureString`. Magic omits `feature`/`subFeature` on such InputValues (master.magic `BEAT`: `featureString="/audio/beat/onbeat"`) (saved file).
- No preset features. The feature is a text box holding the address (guide).
- Multi-argument messages: append the argument index after a space, `"/my/command 1"` = second argument (guide).
- The value is used as sent; OSC has no 0..1 scaling rule in the guide (guide).

## MIDI/OSC Learn

- UI only. Click a linked param's Source/Feature label, Start, send a message, Use. The result is the same `layerID`/`feature`/`subFeature`/`featureString` as manual setup (guide).
- "Auto" button: listen on open and use the first message (guide). Settings key `autoMidiLearn` (binary).
- Learn cannot detect Velocity, Note Number or Control Change Number. Pick those by hand (guide).
- Learn picks up Beat Clock on channel 0 by default. "Ignore Beat Clock For MIDI Learn" turns that off (guide). Key `midiLearnIgnoresBeatClock` (binary).
- Learn is unavailable while "Disable All MIDI/OSC Input" is on (guide, binary).

## Modifier param/bypass MIDI/OSC control

`ValueOperator` attributes (names in binary; meanings from the guide and the menu labels "Learn Param...", "Param Range (", "Learn Bypass...", "Use As Toggle", "Set MIDI/OSC Param Scale", and `NodeAction_SetOperatorBypassMIDIToggle` / `NodeAction_SetOperatorValueMidiScale`):

- `paramLayerID`, `paramFeature`, `paramSubFeature`, `paramFeatureString`: source driving the modifier's `param` (Learn Param). Same encoding as an InputValue link.
- `bypassLayerID`, `bypassFeature`, `bypassSubFeature`, `bypassFeatureString`: source driving the modifier's bypass (Learn Bypass). Bypassed only while held (guide).
- `bypassMidiToggle="1"`: "Use As Toggle", each press flips bypass (guide).
- `paramMidiScale`: the "Param Range" factor applied to the incoming 0..1 value, for params above 1 or negative (guide).
- A param with a MIDI/OSC command is no longer editable by hand (guide).
- No save uses this: all 825 ValueOperators hold -1 / "" / `bypassMidiToggle="0"`. `paramMidiScale` is 0 in 455 and 1 in 370 of them (saved file).

## Playlist MIDI/OSC control

`PlaylistMidiConfig` (one per project) (saved file):

- `layerID`, `feature`, `subFeature`, `featureString`: global command. Its raw value (0..127, OSC first argument) selects the entry number (guide).
- `prevLayerID`/`prevFeature`/`prevSubFeature`/`prevFeatureString` and `next...`: the "Prev entry" / "Next entry" buttons (guide; names in binary).
- Unset = `-1` everywhere, as in all user saves (saved file).
- Sample values: global Program Change (`feature="6"`), Prev/Next on Note Velocity (`7`, note in `subFeature`), Next on OSC `/toggleC_1` or `/toggleC_2` (saved file).
- Samples keep `layerID` values of Layers that are not in the file. Magic still loads them (saved file).
- OSC playlist control: address pattern match, entry # from the first argument (guide).
- Only entries 0..127 are reachable by MIDI. OSC has no limit (guide).
- Playlist UI sub-feature labels "CC #", "Note V. #", "Aft. #" (binary).
- `playlistMidiConfig`, `playlistStartTimes`, `playlistTransitions`, `playlistDetails` are 0/1 flags. Names match the Playlist menu "Show MIDI/OSC Config", "Show Start Times", "Show Transition Options" (binary). That they only toggle panels is inferred.
- Per-entry commands: each `Playlists/Playlist/Scene` entry has its own `layerID`/`feature`/`subFeature`/`featureString` ("Learn MIDI/OSC For Entry #"). In all saves they are -1 (saved file, binary).

## Outputs: OSC, MIDI, Syphon/Spout

- OSCSender module (`Special/OSCSender.dylib`) params: `IP Addr.`, `Port`, `Message`, `Value` (binary, saved file). Dylib defaults: Port 8000, Message `/myMessage` (binary).
- One IP address and one port for all OSCSender modules in a project (guide). The user's hihihi.magic follows that: two senders to 127.0.0.1:7701, `/level/bass` and `/scene/one/1` (saved file).
- Sends a numeric value only (guide). Send rule: see format.md.
- MIDI output: only the "MIDI Output Device" used to play MIDI files (guide, binary `midiOutputDevice`, `MidiOutputThread`). No module sends MIDI: no MIDI dylib ships in `Modules/` (binary).
- Syphon output: `videoSharing`, name, size in format.md. `fixedMagicSize="1"` = "Use fixed resolution" in Graphics Resolution, the default (key next to `videoSharingWidth/Height` in the binary; meaning from the guide). Spout is the Windows equivalent, default name "Main Sender" (guide).

## Video inputs

Module names are the `pluginName` values (saved file). Params from dylib strings and saves.

- `VideoCapture` (webcam): Device, Scale, Crop, Flip, Deinterlace, Stop All, Start This (binary). Windows saves add Grayscale (saved file). `Device="0"` in every save (saved file). New devices are not detected after the module is added. Ignored on movie export (guide). Example: MultiVidCap.magic (guide).
- `VideoStream` (IP camera): URL, Reload, Scale, Crop, Pause (binary, guide). URL is browser-style, e.g. an MJPEG URL. Stream audio is ignored. Ignored on export (guide).
- `VideoFile`: File, Reload, Scale, Crop, Deinterlace, Speed, Start Time, End Time, Goto Start, Scene Start, Looping, Audio, Audio Gain (binary, guide). Windows saves add Sync or Grayscale (saved file). Audio feeds Module Audio Output (guide). Examples: VideoExamples.magic, `File="shortCars.avi"` (saved file).
- `VideoFolder`: Folder, Reload, Cache, Scale, Crop, Speed, Cur. File, Loop Cur., Goto Prev, Goto Next, Randomize, Resume, Scene Start, Loop Folder (binary, guide). No audio (guide).
- ImageFile: `File`, `Reload`, `Scale`. Pre-3.0 saves (all bundled samples) call it `Image`; Magic 3 loads them and saves `ImageFile` (verified).
- `ImageFolder`: Folder, Reload, Cache, Scale, Index, Looping (binary, guide).
- `JpegFolder`: Folder, Reload, Cache, Scale, Index, Play, FPS, Scene Start, Looping (guide; binary has all but FPS as plain strings).
- File params store a path relative to the project in `value` plus `absoluteFilename` on the InputValue (ManyScenes, master.magic) (saved file). Older samples store a bare name only (saved file).
- `SyphonClient`: param `Server` = `"<server name> - <app name>"`, e.g. `"Shader - SwiftVJApp"`, `"S - Synesthesia"` (saved file). Binary shows `" - Unknown"` as the app-less fallback (binary). Windows module: SpoutReceiver (guide, binary).

## Globals

- `Globals/InputValue` list. A Global is linked like any param (manual, calc, source, other Global) and carries modifiers (saved file, guide). Link encoding: format.md.
- Default names "Global 0", "Global 1" ... (saved file; binary "Global ").
- Panel: Scene > Show/Hide Globals Panel, Shift+Cmd+L. Add, Insert New Global Here, Duplicate, Remove, drag to reorder (guide; binary "Add/Insert/Duplicate/Remove Global Parameter").
- Reordering changes only the display and the Features list, not links (guide). That fits id links (`globalsUseID="1"`).
- Renaming updates all references (guide).
- Name rules: not `x` or `y` (guide). For use in Expressions: no spaces, not an ExprTk function name such as `sin` or `pow` (guide).
- GlobalsExamples.magic (saved file):
  - Two "calc" Globals: Global 0 = Sine 1, Global 1 = Sine 3.
  - Scene 0: two RotateAxis Angle params share Global 0, one as Scale -1 -> Offset 0.25 (mirrored, phase-shifted).
  - Scene 1: five Scale Y params on Global 1 with Delay 0, 0.2, 0.4, 0.6, 0.8 (staggered wave).
- Globals as constants and clocks (saved file):
  - IteratorBasicExamples: `time` = calc + Increase 1, `iters` = manual 100. Expressions `x+sin(x*time)`, `x/iters`.
  - IteratorSpectrumExamples `iters`=120, StereoSpectrum_30Band `iters`=30. Expression `x/iters`.
- Global driven by a Global: Timer.magic `textLineHeight` links to Global `fontSize` (manual 50) with Expression `x/36`. A Text param then uses `floor(x)*textLineHeight` (saved file).
- User pattern: master-bus/master `Multi` (manual, Step 0.1 -> Offset 0.5) scales band Globals via `x*Multi` (saved file).

## Export and Internals notes

- Movie export ignores params linked to live audio, MIDI or OSC, and modules VideoCapture and VideoStream. Only file playback drives exported movies (guide).
- Binary Internals label table, index order: 0 Graphics Width, 1 Graphics Height, 2 and 3 unlabeled, 4 Playlist Entry #, 5 Playback Time, 6 Graphics FPS, 7 Iteration #, 8 Total Iterations, 9 unlabeled, 10 Audio/MIDI Playing, 11 Playback Seeked (binary). This settles the two candidates format.md leaves open: 4 is Playlist Entry #, Playback Seeked is 11, and 9 is unlabeled.
