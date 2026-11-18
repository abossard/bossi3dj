# Hand-over: Robot live test, #29 rerun (2026-11-18)

From the robot-magic worker (context at 37 %, over the 30 % hand-over line). Background: `docs/handover/robot-magic.md`, sections from "R8 live test, run of 2026-11-18" on.

## State

- Code ready, committed: adaptive kick gate, pause reset (`Hush`, 2.5 s), harness waits for VolSlow below Quiet, colour split capped (db5f481); variation (#32), backdrops (970978d), duel Angles (#23).
- `robot_live_test.magic` is NOT yet regenerated from the current v1 (mocap, variants, backdrops, new Exchanges).
- Magic: holds `magic/projects/show.magic` (restored 2026-11-18 morning). `robot/magic/live/held_project.txt` names show.magic.
- #29 open. Last run: bar offset median 111 ms, max 812 ms; review round 3 failed on D1 tile 19, E3 tiles 19-20, L6 (low confidence).

## Steps

1. Regenerate and check (no Magic, no Blender):

   ```bash
   python3 robot/magic/live_test.py prepare robot/package/v1/manifest.json
   ```
   ```bash
   python3 magic/magicproj.py check robot/magic/live/robot_live_test.magic
   ```
   ```bash
   make robot-test
   ```
   `prepare` validates the media files; if R5's package is incomplete it fails, then ask orchestrator-2.
2. Wait until nothing renders: `pgrep -x ffmpeg` and `pgrep -x Blender` both empty (an `until` loop, no sleep chains).
3. `python3 robot/magic/live_test.py note` (Magic must hold show.magic), then `python3 magic/magicproj.py load robot/magic/live/robot_live_test.magic` and confirm the editor title. Loads: one Magic session allows about 25; count them.
4. `python3 robot/magic/live_test.py run`: preflight (probe Fps), audio check (peak Volume over 0.1, else stop and tell orchestrator-2: never touch Magic's UI), waits for VolSlow below Quiet, then 90 s recording to `docs/video/robot-live-test.mp4` and `robot/magic/live/events.txt`.
5. `python3 robot/magic/live_test.py restore` at once (show.magic). If an "Error!" window opens, tell orchestrator-2; the user closes it, then retry restore.
6. `python3 robot/magic/live_test.py analyze robot/package/v1/manifest.json` (needs the media; if they are missing, load the Manifest with `check_files=False` as in the 2026-11-18 analysis, and use the Manifest the project was built from). Keep a dated copy of the video (`docs/video/robot-live-test-<date>.mp4`).
7. Numbers to report:
   - #29: `bar_offset` and `bar_offset_after_30s` (median, max) against 111 / 812 ms (2026-11-18), 381 / 966 ms and 48 ms (2026-11-16). Pass: no drift between drops and a median near the 2026-11-16 48 ms.
   - Kick gate: KickRate per section from the probe log (intro, drops about 4 a bar; breakdown, buildup near 0); `Bpm` at the end (124 wanted).
   - Latency: pulses land 40-150 ms after the beat on the synthetic kick in the replay, more than `Latency` 0.04 s: if the bar offset median sits at a steady +100 ms, propose raising `Latency` in `xray.py`.
   - X-Ray start: State stays 0 through the intro (the 2026-11-18 run misread it at 1.26 s).
   - Section reads against the track (intro 0, drop 7.7, breakdown 23.2, buildup 31.0, drop 38.7, breakdown 54.2, buildup 61.9, drop 69.7 s).
   - Solo and duel switches (Idle to Idle, duel in drops), Move changes on bar lines, cuts on Cut Points.
   - Repeats: picks of the same Move variant within 60 s (v1 now has variants), families, idle chains.
   - Backdrops: the run is the first with plates: which backdrops come, changes at Angle changes; fps with the plates (the probe's Fps).
8. Review round 4: copy `robot/build/review/rubric-live-r3.md` to `rubric-live-r4.md`, update the tile tiers and duel tiles from the log (the snippet in the 2026-11-18 analysis: tier and Angle kind at `i*2.5 + 1.25` s) and the backdrop line (plates now behind the fighters), freeze it before the review; make `sheet_gamma.png` (ffmpeg lutrgb gamma 2.2); send both sheets to the `shot-reviewer`. Watch E3 (split capped now) and L6 (Android colour on duel Angles).
9. Append the numbers to `docs/handover/robot-magic.md` as "R8 live test, run of <date>", commit by path (`docs/handover/robot-magic.md`, the rubric), report to orchestrator-2 (local_a45f5ac3-446a-4346-8188-59d914ec9784) in a few lines. Keep #29 open unless the run passes.
