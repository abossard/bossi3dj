Branch `godot/look-round2`, cut from `integration/presentable` at 1f2094d. Look round 2 of the Godot Colossus Scene. No push.

## State

- Verdicts: [docs/reports/godot-look-verdict.json](../reports/godot-look-verdict.json), `rounds` has round 1 (21 frames: 14 pass, 7 fail) and round 2 (25 frames: 21 pass, 4 fail). Of the 21 round 1 frames 19 pass and 2 fail (`shot-2`, `2-approach-low-hero`); the other 2 fails are the superseded `new-colossus-f1` and `f20`. Rubric unchanged. One fix pass and one re-grab were used.
- Black ground, numbers (`tools/png_stats.py`, share of the lowest 30% of rows with every channel 2 or less, before then after): shot-1 0.75 to 0.00, shot-2 0.49 to 0.00, fog_height-0 0.70 to 0.00, 1-approach 0.7 to 0.00, start frame 20 0.83 to 0.07 (frame 120, the first one Syphon publishes now, 0.018), new Colossus 0.83 to 0.016 after the hold.
  - Cause: the rock texture tinted `6b6660` came out black near the camera (white tint fixes it; the sand tint and the lights were not the cause, a fill light alone did nothing). A dim shadowless fill light (`World._build_fill`, energy 0.5) lifts the ground further.
  - The first frames of a start were also black for ~65 frames: a Shrine column stood 2 m before the camera. The Wanderer now starts 34 m before the Shrine and the three columns toward the plain are left out (`World.GATE`).
  - Lighting converges for about 120 frames after a start or a Colossus build (`make godot-warmup`). Syphon publishes from frame 120 (`SYPHON_WARMUP_FRAMES`) and the Reset holds black 2 s after the build (`RESET_HOLD_SECONDS`).
- Colossus on the long walk (`make godot-framing`, height in px of 1080, at the real start 1.6 km away): wide shot 172 px, low hero 120 px; at 1000 m 282 and 211, at 450 m 612 and 458. The wide shot goes telephoto (narrowest lens 6 degrees); the low hero shot spans Wanderer and giant, see below. Contrast of the chest against the frame beside it is 0.8 at every distance.
  - Cause of the invisible giant was haze, not size: depth fog and the sun's volumetric scatter lifted a far giant to the sky's brightness (contrast 0.01). The Colossus stone now has `disable_fog`, a lighter albedo (`80796f`) and the sun's fog energy is 1.0 (was 2.0) with anisotropy 0.4 (was 0.6).
- Low hero on the long walk (round 3): `Director._long_walk` aims and sets the lens to span the Wanderer's feet and head and the Colossus's feet and top (`Director.hero_lens`, factor 1.5, narrowest 8 degrees, logic test in `run_tests.gd`). `make godot-framing` exit 0: the Wanderer is whole in frame in the low hero shot at the start, 1500, 1000, 700, 450, 300, 150, 60 and 25 m, and on two live walks at 10x time (50 of 50 samples each, from the start and from 300 m). Giant's height in px in that shot: 117 at 1.6 km, 46 at 1500 m (on the slope, lens 24 degrees), 211 at 1000 m, 458 at 450 m, 520 at 300 m; walking down the slope it drops to 25 px at least (lens up to 53 degrees). Wide shot unchanged. Probe flakes under load 30 to 46 seen in unrelated shots (shot 1 and 5 contrast or px, first row). Frame time (`tools/godot_frame_log.py`, load 40, not trustworthy): Approach median 4.5 ms process time, fps median 60.
- Close grip: the Wanderer hangs 1.7 m below the grip and swings 0.6 m; the camera now stands 3 m off and aims at him. In frame on 30 of 30 samples through a Shake (was 9 of 30).
- Reset hitch: 167 ms to 36 ms (worst frame in Reset; worst in the whole Arc 48 ms) at load 25, medians 16.7 ms throughout. Cause: two 512 px normal maps made per Colossus (80 ms each). They are made once per seed at start (`Roster.warm`).
- Real OSC (`make godot-shake-osc`): `/vj/shock` 1.0 over udp to 19202 in a Climb counts one shock, starts a Shake and cuts to the close grip; 1.5 sets the drop mark and the next bar line carries `drop=true`.
- Fill light cost (`make godot-cost`): median 16.68 ms on, 16.70 ms off, alternating in one run at load 25. Metal pins the frame at 16.7 ms and has no GPU timer, so this shows only that the work still fits a frame. No fps verdict (`fps_trustworthy` was false the whole time).
- `make godot-test` (345), `make godot-lint`, `make godot-check` (22 effect), `make godot-smoke`, `make godot-page-test` green.

## Open

- `shot-2` and `2-approach-low-hero` still fail `wanderer-visible` in round 3 (reviewer: no Wanderer on the dark slope at 480 px; the pale blob in the Approach frame does not read as a figure). The numbers say he is whole in frame; he is a dark figure of about 19 px on dark ground. Not fixed, no further pass. Options: light the Wanderer (rim or emissive) or keep the telephoto off the Shrine slope.
- A drop that comes while a Shake is on stays on the close grip: `Shots.pick` returns the close grip first. The aerial cut waits for a drop with no Shake running. Not changed.
- Over-shoulder and close-grip shots in Approach (only reachable pinned) show the giant 26 and 40 px tall: they frame the Wanderer.
- Not seen: a real Magic session, bass dust size and beat footfall nudge.
- Syphon now appears 2 s after the window opens; the page's `syphon.active` is false until then.

## Commands

```bash
make godot-import        # once per fresh worktree
make godot-framing       # px, contrast, Wanderer in frame per shot and distance; close grip through a Shake; exit 1 on fail
make godot-warmup        # flat-black share from the first draw and after a new Colossus
make godot-hitch         # frames above 30 ms across one Arc
make godot-shake-osc     # real /vj/shock packets into a Climb
make godot-ablate ARGS="terrain"   # which feature turns the frame black
make godot-cost
make godot-look OUT=/tmp/look      # then: magick in.png -resize 480x tile.png, shot-reviewer
python3 tools/png_stats.py a.png   # flat_black_bottom, near_black_bottom
```
