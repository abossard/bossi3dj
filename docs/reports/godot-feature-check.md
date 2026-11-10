# Godot Colossus Scene: feature check

Run 2026-11-10 on branch `godot/control-page`, headless (`make godot-check`, page port 19211, udp 19202, no Syphon, engine time scale 4). Same code as the page's "Check all" (`io/feature_check.gd`); the page run over HTTP gave the same 22 effect rows (`make godot-page-test`, and once clicked in the Browser pane).

## Result: 22 effect, 0 no effect, 0 error

Each row sets the control through the same write path as OSC, lets the scene step, and reads the number the scene acts on. Sweeps write min, default and max and compare with the value `io/vj_map.gd` expects. "observed" is what the scene held, "expected" what the table says.

| control | address | verdict | observed | expected | reads |
|---|---|---|---|---|---|
| level | /vj/level | effect | [1.4,1.8,2.6] | [1.4,1.8,2.6] | sun_energy at min, default, max |
| bass | /vj/bass | effect | [0.0,0.5,1.0] | [0.0,0.5,1.0] | weight at min, default, max |
| fog | /vj/fog | effect | [0.002,0.003,0.012] | [0.002,0.003,0.012] | fog_density at min, default, max |
| fog_height | /vj/fog_height | effect | [0.0,40.0,60.0] | [0.0,40.0,60.0] | fog_height at min, default, max |
| haze | /vj/haze | effect | [0.0002,0.00025,0.0012] | [0.0002,0.00025,0.0012] | haze_density at min, default, max |
| intensity | /vj/intensity | effect | [0.2,1.0,2.0] | [0.2,1.0,2.0] | exposure at min, default, max |
| shot_1 | /vj/cam | effect | 1 | 1 | director shot after pinning 1 |
| shot_2 | /vj/cam | effect | 2 | 2 | director shot after pinning 2 |
| shot_3 | /vj/cam | effect | 3 | 3 | director shot after pinning 3 |
| shot_4 | /vj/cam | effect | 4 | 4 | director shot after pinning 4 |
| shot_5 | /vj/cam | effect | 5 | 5 | director shot after pinning 5 |
| shot_auto | /vj/cam | effect | 0 | 0 | pinned shot after auto |
| beat | /vj/beat | effect | 4 | null | beats counted for 4 pulses |
| beat_simulator | /vj/beat | effect | 4 | null | beats counted from the simulator |
| osc_packet | /vj/fog | effect | [0.7] | 0.7 | value after one udp packet |
| hold | /vj/fog | effect | 0.9 | 0.9 | value after an OSC packet against a hold |
| defaults |  | effect | 0.0 | 0.0 | largest distance from a rest value |
| phase_climb |  | effect | "Climb" | "Climb" | Phase after the jump |
| shake | /vj/shock | effect | 0.173 | 0.01 | largest Shake roll in radians |
| phase_fall |  | effect | "Fall" | "Fall" | Phase after the jump |
| phase_reset |  | effect | "Reset" | "Reset" | Phase after the jump |
| phase_approach |  | effect | "Approach" | "Approach" | Phase after the jump |

Beat rows have no expected value: they count beats (4 pulses, 4 beats). Preconditions are one data table (`FeatureCheck.NEEDS`): Shake needs the Wanderer on the Colossus, so the check goes to Climb, puts the Wanderer under the lowest Grab Point and grabs. The check ends with values and holds as found and the Phase in Approach.

The check can fail: with `colossus.weight` no longer written the bass row reads `[0.5, 0.5, 0.5]` against `[0, 0.5, 1]` and gives "no effect"; with `fog_height` clamped to 30 m the row gives "error".

## Bugs found and fixed

- **A held fader lost its effect after 2 s.** `VjSignals.value()` fell back to the rest value 2 s after the last packet, but Magic sends only on change. Every value now stays until the next write (test: 60 s without a packet). `/vj/cam` was the worst case: a pinned director shot let go after 2 s. Only `/vj/beat` keeps its fallback, the internal 90 BPM beat.
- **`/vj/fog_height` in metres became kilometres of fog.** Godot read 0..1 and mapped it to 10..90 m with no clamp, so Magic's default 25 became about 2 km. The table now takes metres and clamps 0..60, rest 40 m (the old rest, 0.375 of 10..90 m). Assumption until the decision: the address is the fog height in metres, as Magic and Blender send it.
- **A slow frame could swallow a page trigger.** A fired trigger is high for 0.1 s. The edge is seen before the pulse ends, so a frame longer than 0.1 s still fires it.

## Changed behaviour to know

- `/vj/cam` above 5 used to be ignored by the director (the old pin kept); it now clamps to 5. Assumption until the decision: 0 is auto, 1..5 pin a shot. A different meaning is a change of the `/vj/cam` row in `io/vj_map.gd`.
- The check puts values and holds back as found, not to defaults. On a fresh scene that is the same; on a show, where Magic sends only on change, restoring defaults would lose every standing fader. The page's Defaults button sets the rest values and releases holds, and a check row proves it.

## Left open

- Defaults still differ per scene (`/vj/fog` 0.1 in Godot against 0.35 in Magic, `/vj/haze` 0.05 against 1). The rest values are the tuned Godot look; the contract owner decides.
- `/vj/intensity` 0 reaches the scene as exposure 0.2 (the old clamp), so Magic's range 0..2 loses its lowest part.
- `SyphonOutput` has no frame counter. The page shows `Engine.get_frames_drawn()` since the server started, an upper bound of what was published. Needs the live pass.
- `/vj/bass` is judged at `Colossus.weight`. The dust size and camera thump it drives are not observed.
- `/vj/beat` is judged by the beat count. The footfall nudge it triggers (`Colossus.on_beat`) moves the step only inside a window and is not observed.
- `make godot-smoke` fails its wall-clock assert "a frame in every 2 s" at load 75 to 125 (worst gaps 2.9 s and 3.3 s here). The base commit fails it too under the same load (2.2 s), all other smoke rows pass. Rerun when `make status` says `fps_trustworthy`.
- Allocation per frame is not measured, only kept by construction: with no client the server does one `is_connection_available()` call and an empty-array loop per frame, and `VjSignals` writes into existing dictionary keys.

## For the live pass (Metal, window, nothing else on the GPU)

Needs Blender closed. Each item is something headless cannot see.

1. Start and open the page: `make godot-open`, then `open http://127.0.0.1:9211`. Header shows Phase, shot, fps, Syphon `COLOSSUS_OUT` with a rising frame count.
2. Run "Check all" on the page on Metal: expect 22 effect again (`jq .check.summary` of `curl -s http://127.0.0.1:9211/api/state`).
3. Syphon content: grab `COLOSSUS_OUT` and read pixel statistics, once with the page closed and once open. Nothing of the page may appear in the frame.
4. fps and frame time with only Godot on the GPU: `make status` must say `fps_trustworthy`, then read `fps` and `frame_ms` from `/api/state` across a full Arc.
5. Look: `/vj/fog_height` at Magic's 25 m and at 60 m, `/vj/fog` 0 and 1, `/vj/intensity` 0.2 and 2, each of the five pinned shots with the Colossus readable. `make godot-capture OUT=<dir>` and a contact sheet to `shot-reviewer`.
6. Shake and the director's close grip with the Wanderer on the Colossus, from the page's Shake button and from a real OSC `/vj/shock`.
7. A real Magic session: a fader left standing for more than 2 s keeps its effect; `make lab` relays to 9202 and the page shows `osc` as source.
