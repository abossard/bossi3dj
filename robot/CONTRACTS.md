# Robot Scene contracts

The parts of the Robot Scene meet only through these. Change a contract here first, then the code on each side.

## Manifest (`package/<name>/manifest.json`)

One per Render Package. Written by `build/`, read by `magic/` and `live/`.

| Field | Meaning |
|---|---|
| `version` | integer, 1 |
| `bpm` | tempo the Clips are rendered at (124) |
| `fps` | frame rate of every Clip (30) |
| `size` | `[width, height]`, 1920x1080 |
| `key_poses` | list of Key Pose names, e.g. `["guard"]` |
| `angles` | list of `{id, camera}`: Angle id and its Shot Camera name |
| `clips` | list of Clips, below |
| `quality` | optional: `low` (Eevee, for judging motion), `high` (Cycles) or `mixed`; missing means `high` |

Each Clip:

| Field | Meaning |
|---|---|
| `id` | `<move>__<angle>`, unique |
| `move` | Move name |
| `angle` | Angle id |
| `beats` | length in beats (4, 8 or 16); frames = beats × 60 / bpm × fps, rounded |
| `frames` | frame count |
| `key_in`, `key_out` | Key Pose at the first and last frame |
| `tier` | Intensity Tier: `calm`, `build` or `drop` |
| `idle` | `true` for an Idle Clip: `key_in` equals `key_out`, first and last frames identical, Magic loops it; `false` for a Move Clip, which Magic restarts on each pick |
| `quality` | optional: this Clip's render quality, `low` or `high`; missing means `high` |
| `opponent` | optional: `true` for an Exchange, a Clip with both the Android and the giant machine in the frame (`robot/build/GIANT.md`); missing or `false` for a Clip with the Android alone. `key_in`, `key_out`, `idle` and `cut_points` always describe the Android |
| `cut_points` | beats inside the Clip where a switch is allowed, `[0]` at least |
| `passes` | `{beauty, shadow, depth}`: file paths relative to the package; beauty carries the Matte as alpha |
| `clip_data` | path of the Clip Data file |
| `camera_track` | path of the Camera Track file |

Clips of one Move share timing across Angles, so Magic may cut Angles at any frame.

Pass files, one `.mov` per Clip and Pass, 1920x1080, 30 fps, the Clip's frame count:

| Pass | Codec | Values |
|---|---|---|
| beauty | QuickTime Animation (qtrle), 8-bit RGBA | colour, alpha is the Matte |
| shadow | ProRes 422, grey | the Shadow Pass coverage as in the render, 0 = no shadow |
| depth | ProRes 422 HQ, 10-bit grey | distance from the Shot Camera in metres divided by 20, clamped to 0..1; 1 is 20 m or more and where the Android is absent |

ProRes 4444 for beauty decoded below 30 fps at 3 Angles in Magic; qtrle holds 4 (docs/handover/robot-magic.md, 2026-11-16).

Every Key Pose has exactly one Idle Clip per Angle. A Move Clip that ends with no next pick goes to the Idle Clip of its `key_out`; the Clip Graph leaves the Idle Clip on the next bar boundary into any Move with that `key_in`.

## Clip Data (`clip_data/<clip id>.json`)

| Field | Meaning |
|---|---|
| `clip` | Clip id |
| `frames` | list, one entry per frame: `{f, head, eye_l, eye_r, hand_l, hand_r, foot_l, foot_r}`, and in an Exchange also `{g_head, g_core, g_hammer, g_claw, g_foot_l, g_foot_r}` (the giant's), each `[x, y, depth]` with x, y in 0..1 from the top left and depth in metres from the Shot Camera |
| `hits` | list of Hits: `{f, point: [x, y, depth], strength: 0..1, limb}` and optional `target`; in an Exchange `limb` may be a giant point (`g_hammer`, ...) and `target` names the struck point of the other fighter or `floor`. A Hit without `target` is valid |

## Camera Track (`camera/<angle>.json`)

Per frame: camera location, rotation (quaternion), focal length and sensor width. In v1 the Shot Cameras are locked, so one entry repeats.

## Syphon

- `ROBOT_LIVE`: the live Blender scene. Tests use `ROBOT_TEST`. Never `CAM_OUT - Blender` or `COLOSSUS_OUT`.

## OSC (proposed, not yet in `osc/contract.json`)

Magic tells the live scene what is on air. Rows go through the `osc/` owner; until then nothing sends them.

| Address | Wire | Meaning |
|---|---|---|
| `/vj/clip` | integer 0..255 | index of the Clip on air in the Manifest's `clips` list |
| `/vj/clip_frame` | integer 0..4095 | frame of that Clip, counted by Magic from the Clip's start |
| `/vj/angle` | integer 0..7 | index of the Angle on air in the Manifest's `angles` list |

The live scene places Live Layers from the Clip Data of `/vj/clip` at `/vj/clip_frame`, and replays the Camera Track of `/vj/angle`. Musical controls (`/vj/beat`, `/vj/level` and the rest) keep their existing rows.
