# Playback, output and performance (Magic 3.0b6)

Tags: (saved file) = Magic's 36 bundled SampleProjects; (binary) = strings in `Contents/MacOS/Magic`; (guide) = User's Guide; (history) = VersionHistory.txt. "inferred" means the mapping is a name or order match, not a confirmed read-back. File layout, ids, sources, Internals indices and Syphon attrs: [format.md](format.md). Not repeated here.

## Contents
- Magic Window
- Preview Window and Preview Mode
- Playlist
- Audio file playback
- Projects
- Exporting movies
- Live performance and troubleshooting
- Keyboard shortcuts
- App preferences and launch arguments

## Magic Window

- Shows the displayed scene, which can differ from the edited one. Title = displayed scene name (guide).
- Status information: bottom left, graphics resolution and FPS. Toggle Cmd+I. "s" appears when Syphon is on (guide).
- Larger Status Text Size has independent windowed/fullscreen settings (guide).
- Fullscreen: Cmd+F cycles main display, then each extra display, then windowed. Cursor auto-hides (guide).
- Menu: Window > Magic Window Options > Enter Fullscreen On Display > [n], Exit Fullscreen, Always Hide Mouse Over Fullscreen (guide).
- Same-resolution displays arranged edge to edge can be spanned (guide).
- Start In Fullscreen + Display To Use + Start Auto-Advance: for unattended boot. Put a `.magic` file in the OS startup folder (guide).
- Exit Fullscreen For Other Apps is on by default; turn off to never drop out (guide).
- Graphics Resolution (Shift+Cmd+G): "Use fixed resolution" (default 1280x720) or "Use size of Magic Window" (guide).
- Resolution presets: 854x480, 1280x720, 1920x1080, 2560x1440, 3840x2160, 4096x2160, 1080x1080, 640x480, 800x600 (binary).
- Resolution is saved with the project. Lock Graphics Resolution ignores project values (guide). Pref key `lockGfxRes` (binary).
- Graphics memory: Load All Scenes Into Graphics Memory is on by default. Off = previous scene unloads on change, may drop frames, worst during transitions (guide).
- Per scene: tab menu Keep Scene In Graphics Memory, shown in bold. Ignored while Load All is on (guide).
- Saved as `Scenes/Scene@keepInGfxMem` (binary has the attr next to `isPostProcessing`, `excludedFromPostProcessing`; all 107 sample scenes carry `keepInGfxMem="0"`) (saved file).
- Show Free Graphics Memory shows KB in the status line (guide).
- Changing memory options or resolution triggers "Updating scenes, please wait..." (binary). Hidden if status info is off, never on a secondary display (guide).
- Cleanup Graphics Memory (Shift+Cmd+C): unloads all, reloads active scenes. Disabled/bypassed modules keep VRAM until then (guide).
- Throttling (Frame Rate): idle N whole ms after each frame. Default 1 ms. 0 disables (not recommended). With vsync off, 5 ms caps at 200 fps (guide). Dialog text "Idle for ... ms after drawing each frame" (binary).
- Trails and other modules render differently at different frame rates (guide).
- Vertical Sync: on by default, locks to display refresh (guide).
- Double Buffering: always on in macOS, toggle only on Windows (guide).
- Clock source: default is the audio output device. Untick Use Audio Output As Clock Source for system clock (guide). Pref key `useAudioOutputClock` (binary). New in 3.0 (history).
- Coordinates: [format.md](format.md).

## Preview Window and Preview Mode

- Preview Window: Shift+Cmd+E. Cannot go fullscreen or to another display (guide).
- Costs GPU, can cut Magic Window FPS by up to 50% (guide).
- Right-click menu: Preview Only, Preview & Edit, Stop Preview, Restart Preview. Same in tab and Scene Group menus (guide).
- Preview Window never changes the Magic Window (guide).
- Cmd+J previews the selected module's output alone; title shows "P" (guide).
- Preview Mode: Scene > Preview Mode. Tab clicks, add/duplicate scene go to the Preview Window. Only the Playlist changes the Magic Window (guide).
- Pref key `liveEditingMode` sits next to the project load strings; likely Preview Mode (binary, inferred).

## Playlist

UI: Shift+Cmd+P. Entry numbers start at 0 (history). Prev/Next wrap, skip disabled entries (guide).

### `Playlists/Playlist`
| Attr | Samples | Meaning |
|---|---|---|
| `random` | all 0 | Randomize: no repeat until all shown; ignored by Playback Control and export (guide) |
| `linkAutoAdvance` | all 0 | Likely the "Playback control" checkbox (inferred: only remaining playlist bool; binary lists `linkAutoAdvance` with `random`) |

### `Playlists/Playlist/Scene` (one per entry)
| Attr | Samples | Meaning |
|---|---|---|
| `id` | | `Scene@id`, not position. Effects2DExamples has scenes 1..9,11 and entries 1..9 (saved file) |
| `style` | 1 (55), 2 (19) | Transition. Button letters N/C/A (binary). Order None, Crossfade, Additive Dissolve (guide) gives 0/1/2; default Crossfade = 1 (inferred) |
| `duration` | all 2 | Transition seconds, default 2 (guide). Applies when arriving at this entry |
| `sceneDuration` | 30, 10, 7 | Auto-advance seconds, default 30 (guide). Binary action `SetPlaylistEntrySceneDuration` |
| `enabled` | all 1 | Disable option. Disabled = skipped by Prev/Next and auto-advance, still reachable by MIDI/OSC or click (guide) |
| `layerID feature subFeature featureString` | -1 except one stale 30 | Per-entry "Learn MIDI/OSC For Entry #" command (inferred from shape; matches source triple in format.md) |

- 3DSpectrums has entry `layerID="30"` pointing at an audio layer with `feature="-1"`: a leftover, not a trigger (saved file).
- Crossfade: 50/50 at midpoint. Additive Dissolve: both 100% at midpoint, brighter. None: cut, duration ignored (guide).
- Transitions draw two scenes, double cost. Selecting during a transition cancels it. Transition must be shorter than the entry (guide).
- Editor tab changes never use transitions (guide).

### `PlaylistMidiConfig`
- `layerID feature subFeature featureString`: global "select entry by value" command (guide). MoreScenes: `layerID="48"` = MIDI layer "Source 2", `feature="6"`, matching the guide's Program Change from Source 2 example. So MIDI feature 6 = Program Change here (saved file + guide).
- `prev*` / `next*`: Prev entry / Next entry buttons. OSC address goes in `nextFeatureString`, e.g. `/toggleC_1` (saved file).
- Playlist MIDI values stay 0..127, not scaled. Only entries 0..127 reachable by MIDI. Beat Clock, Pitch Bend, Iterator Notes cannot trigger (guide).
- OSC: first argument value selects the entry number (guide).
- View toggles (binary menu order Show MIDI/OSC Config, Show Transition Options, Show Auto-Advance Options, Show Start Times): `playlistMidiConfig`, `playlistTransitions`, `playlistDetails` (= auto-advance options, inferred), `playlistStartTimes`. Display only (guide).
- Start times: mm:ss, first fixed at 00:00.0, editing one changes the previous duration (guide).
- `Project@playlistChangesTabs` = Change Scene Tabs With Playlist (binary name match, all samples 0). Off saves CPU (guide).
- Restart Modules On Reselect: menu item (binary). Pref key `reselectingEntryRestartsNodes` (binary, inferred).

### Auto-advance and Playback Control
- Toggle: "A" button or Shift+Space. Current entry yellow; manual selection cyan (guide).
- Not millisecond-accurate live; exact in movie export (guide).
- Playback Control: play turns auto-advance on, pause/rewind turn it off. Entry follows file time (45 s with 30 s entries = 15 s into entry 1). Loop resets to entry 0 (guide).

## Audio file playback

- Play/pause: Shift+Cmd+Space. Rewind: Shift+Cmd+W. Graphics follow files only while playing; live input always runs (guide).
- Loop toggle loops at the end of the longest file (guide). Saved as `Project@looping` (13 of 36 samples have `1`) (saved file).
- Mute/Solo per file: solo beats mute; neither stops graphics reacting (guide). Saved as `isMuted`/`isSoloed` (saved file).
- Start time per file (positive = silence first, negative = cut). Saved as `offset` in seconds (MIDIFileExample `offset="0.5"`) (saved file, inferred from export length below).
- MIDI files need a MIDI output device to be heard (guide).
- Internals for playback: Audio/MIDI Playing, Playback Time (s), Playback Seeked (slider or rewind), Playlist Entry # (-1 if none) (guide). Indices: [format.md](format.md).
- Remove unused files: each costs memory and CPU (guide).

## Projects

- File > Import Project adds all scenes; "Merge Duplicate Sources?" dialog. Import is never undoable (guide).
- Tab/Scene Group menu Save ("Save Scene To Project...") writes chosen scenes only; playlist entries are dropped (guide, binary).
- Auto-Backup and Auto-Save (default 5 min) write to the user temp dir (guide). Folder name `MagicBackups` (binary).
- Collect Assets: copies assets to a chosen folder, rewrites refs, clears undo, then offers to save the project there (binary dialog text).
- Paths in v3 saves: module `File` param keeps relative `value="circle.png"` plus `absoluteFilename="C:\...\circle.png"` (ManyScenes) (saved file). 3.0 change: both saved "in case one can't be found" (history).
- Older saves have only relative `value`, sometimes Windows-style `..\Modules\Special\GLSLShaders\default.txt` (saved file).
- MIDIFileExample (older save) stores `AudioFile filename="Bach.ogg"` relative, no absolute (saved file).
- Passwords: File > Project Passwords, one for opening, one for editing. Edit lock disables Editor, Input Sources, Playlist. Setting needs Performer (guide).
- Binary has keys `pwdO` and `pwdV` beside the open/load strings, likely the two passwords (binary, inferred). No sample has them.

## Exporting movies

- File > Export Movie (Cmd+U). Not real time: live audio/MIDI/OSC params and VideoCapture are ignored (guide).
- Scene source options: Current scene, Playlist with auto-advance timing, Playlist MIDI file timing (binary). Transitions used, Randomize ignored (guide).

| Attr | Dialog field | Evidence |
|---|---|---|
| `width`, `height` | Resolution; multiple of 4 for mp4/mov, auto-rounded (guide) | 1280x720 (34), 1920x1080, 320x180 |
| `fps` | Frames/sec | 60 (34), 30 (2) |
| `duration` | Length, stored in frames at `fps` | MIDIFileExample 7707 / 60 = 128.45 s = Bach.ogg 127.94 s + 0.5 s offset (saved file). Default 600 = 10 s |
| `usePlaylist` | Playlist vs current scene | all 0 |
| `format` | Codec | 1001 (34), 1002 (2). Codes for other entries not derivable |
| `quality` | 0..10, H.264 and MJPEG. 0 = CRF 28, 10 = CRF 18 (binary) | all 7 |
| `outputFolder`, `outputFile` | Destination (folder for png, file for mp4/mov) (binary) | all empty |
| `useAlpha`, `megabitRate` | Transparency, old bitrate | only in older saves (megabitRate 10/20/100). Absent from the 3.0b6 binary and v3 saves, so likely ignored now |
| `useMovie` | unknown | in binary only |

- Codec list order (binary): H.264 (.mp4), H.264 422, H.264 444, ProRes 422 (.mov), ProRes 422 HQ, ProRes 4444, Motion JPEG (.mov), Image sequence (.png). Encoders seen: libx264, prores_ks, mjpeg, aac, pcm_s16le (binary).
- Alpha: ProRes 4444 and png only (guide). png frames are `00000000.png`, no audio (guide, binary).
- Audio: non-muted audio files only; AAC in mp4, uncompressed in mov (guide, history).
- Sample rate errors: guide says 96000 Hz or below; binary also has "must be set to 44100Hz or 48000Hz" (binary).
- Get audio/MIDI length sets Length from the longest file (guide, binary).
- Export width/height capped by the GPU max output size (binary).
- During export the status line shows movie size and frames written per second (guide).

## Live performance and troubleshooting (guide)

- Use external USB/pro audio hardware; on Windows, ASIO.
- Keep FPS at or above 60. Remove/disable modules, drop unneeded scenes, lower graphics resolution.
- GPU matters most; NVidia or AMD with lots of VRAM.
- Scene > Scene Editor Options > Module Text Update Speed > Off, or select a blank tab. Big gain on macOS.
- Disable screen savers, sleep, power saving; no battery. Close other apps, AV, indexing, backup, updaters; consider networking off.
- Projector/TV: disable all processing (game mode). Prefer high refresh, low display lag.
- Windows only: try double buffering off.
- Never mirror; use extended desktop, black empty background.
- Edit live with Preview Mode.
- Window > Disable All Keyboard Input (until restart). Best: control by MIDI/OSC only.
- Troubleshooting: update OS, GPU, audio/MIDI drivers first.
- Help > Graphics Info: Maximum Input Size (images/video larger fail to load), Maximum Output Size (Antialias needs well below it).
- MIDI driver hangs: Window > Disable All MIDI/OSC Input.

## Keyboard shortcuts (macOS, guide)

| Action | Keys |
|---|---|
| File play/pause | Shift+Cmd+Space |
| Rewind | Shift+Cmd+W |
| Playlist auto-advance | Shift+Space |
| Next / previous entry | Cmd+] / Cmd+[ |
| Fullscreen | Cmd+F |
| Status info | Cmd+I |
| Graphics resolution | Shift+Cmd+G |
| Syphon output | Shift+Cmd+S |
| Cleanup graphics memory | Shift+Cmd+C |
| Globals panel | Shift+Cmd+L |
| Magic / Preview / Playlist / Input Sources window | Shift+Cmd+M / E / P / I |
| Next / previous scene tab | Cmd+T / Cmd+R |
| Preview module output | Cmd+J |
| Force restart modules | Cmd+E |
| Export movie | Cmd+U |
| Save | Cmd+S |

- Disable All Keyboard Input blocks all of these.

## App preferences and launch arguments (binary)

- Keys stored outside projects (no sample has them): `startFullscreen`, `startFullscreenAutoAdvance`, `startFullscreenDisplay`, `exitFullscreenForOtherApps`, `throttleDur`, `vsync`, `doubleBuffering`, `showFps`, `monitoringMemory`, `fixedMagicSize`, `lockGfxRes`, `autoSaveDur`, `audioBufferSize`, `midiDisabled`, `useAudioOutputClock`.
- Short argument strings `-fs`, `-af`, `-mf`, `-mi`, `-rd`, `-psn` exist. The guide documents none of them; meaning not sourced. Do not rely on them.
