# Magic tooling findings (session magic-scene-tooling-874023)

- Tool: `magic/magicproj.py` on branch `claude/magic-scene-tooling-874023`.
- Verified live in Magic 3.0b6 (frames over Syphon):
  - `videoSharingName` on `<Project>` sets the Syphon server name (default "Main Server").
  - Internals feature index: 0/2 graphics width, 1/3 graphics height (follow videoSharingWidth/Height, not RenderSettings), 5 playback time (s), 6 live FPS, 7 Iteration #, 8 Total Iterations (1 outside an Iterator), 10 Audio/MIDI Playing. 4 and 9 read 0.
  - Shift+Cmd+Space via System Events toggles audio file playback (Magic must be frontmost).
  - Audio file in SoundFiles/AudioFiles + file Tracks + Layer trackID: Volume of a 0.79-amplitude tone reads 0.79.
- Magic's own saves: random 3-byte header, CRLF + wrapped attributes; all 45 local saves round-trip semantically and pass `magicproj check` with 0 errors.
- ExprTk names are case-insensitive (MIDIPiano sample uses `X`).
- Scene module `sceneID` refers to `Scene@id`, not the scene's position.
- Global evaluation is double-buffered, not ordered: with Before="Count", Count="y + 1", After="Count", both Count-Before and Count-After read 1 (inside Globals and in module params). So `synthwave_magic.py`'s note "Order matters: a Global that reads a later one sees its previous value" is wrong: every Global-to-Global hop costs one frame, earlier or later. The Kick chain (KickBand -> KFast -> KRaw -> KOn -> Kick) therefore lags ~4 frames. Probe files: scratchpad order*.magic of session magic-scene-tooling-874023.
