# Android and foundry set: design note (R5)

Look: Chrome Foundry (the user, 2026-11-15). Source of truth: [build_robot.py](build_robot.py) and [moves.py](moves.py); the `.blend` is generated.

## Android

- Stylised hard-surface steel, about 2.0 m tall. Rigid beveled parts parented to bones: no skinning, so no deformation artefacts.
- Silhouette for 1080p: broad shoulder domes, V-shaped chest, narrow gunmetal waist, chunky forearm gauntlets and shins, a small head with a crest. Every limb is at least 10 cm thick, so it reads at 1/4 frame height.
- Materials: polished steel (metallic, roughness 0.06 plus 0.08 noise, a cool strip light for long highlights) for the shell, dark gunmetal for joints, waist and back pack, so the parts separate. One emissive amber visor slit (colour 1, 0.35, 0.03 at strength 1.5, roughness 0.7, no specular), the only light on the body. A brighter emitter turns cream-white under AgX.
- Rig: root, hips, spine, chest, neck, head; arms and legs as 2-bone IK to wrist and ankle targets with fixed poles (elbows out and back, knees forward); pole angles are chosen by the build in the guard pose. Feet hang under their IK targets, so a planted ankle at 0.10 m puts the sole on the floor.
- Stance: orthodox (left foot and hand lead), body turned 30° clockwise, chin tucked, Android faces -Y.

## Moves ([moves.py](moves.py))

Key Poses (issue #19, 2026-11-16), all on both feet:
- `guard`: orthodox boxing guard (above).
- `low`: wide power stance squared to the front, hips at 0.76 m, fists low and wide.
- `crouch`: landing crouch, hips at 0.50 m, staggered feet, rear fist down by the floor, lead arm back.

Moves last 1, 2 or 4 bars (58, 116, 232 frames at 124 BPM, 30 fps) and start and end in their Key Poses. Keys on a beat grid, smoothstep between keys (or accelerating into an impact and settling after it), one key per frame baked into Blender. A foot moves only off the ground.

| Move | Tier | Bars | From > to | Hits |
|---|---|---|---|---|
| idle_guard, idle_low, idle_crouch (Idle Clips) | calm | 1 | each Key Pose | none |
| guard_shuffle | calm | 2 | guard > guard | none: steps in, looks around, steps back |
| settle_low | calm | 2 | guard > low | none |
| rise_guard | calm | 1 | low > guard | none |
| low_scan | calm | 4 | low > low | none: slow twist, arm flex |
| stand_up | calm | 2 | crouch > guard | none |
| jab_cross | build | 1 | guard > guard | jab, cross |
| take_hit | build | 1 | guard > guard | head |
| jab_jab_hook | build | 2 | guard > guard | jab, jab, hook, cross |
| palm_strike | build | 1 | low > low | two double palm pushes |
| rush_cross | build | 2 | low > guard | step-in cross |
| crouch_strike | build | 1 | crouch > crouch | two low punches |
| front_kick | drop | 1 | guard > guard | kick |
| uppercut_combo | drop | 1 | guard > guard | uppercut, hook, uppercut |
| leap_slam | drop | 2 | guard > crouch | leap 0.6 m up, fists slam on landing |
| ground_pound | drop | 1 | crouch > crouch | right and left hammer fists into the floor, then a two-fist finisher |
| burst_rise | drop | 2 | crouch > low | jump up arms wide, land wide, four punches |
| power_stomp | drop | 1 | low > low | three heel stomps on one spot ahead, the last the heaviest |
| low_charge | drop | 2 | low > guard | shoulder ram, two-fist hammer |

Every Key Pose has a Move out in every tier, and reaches every other Key Pose within two Moves (low to crouch goes through guard).

Cut Points are computed: a beat counts when its frame is within 0.5° and 5 mm of the Move's starting Key Pose.

An Idle Clip is its Key Pose plus waves a·0.5·(1 − cos(2πk·f/57)): zero offset and zero speed at the first and last frame, so the identical first and last frames loop without a seam.

## Foundry set

- A 12 x 12 m Shadow Catcher floor (the only set object that casts into the Shadow Pass; set objects cast no shadow), a camera-invisible 40 m floor below it, a molten channel 3.5 m behind the Android across the hall, I-beam columns at x ±7 m, gantries at 8 m, a dark back wall.
- Light: five sodium high bays (2100 K amber), one sodium key spot from front left, the molten channel's orange glow from behind and below, a weak cool roof light as rim for the silhouette. Dark warm world.
- In the Clips the set is invisible to the camera but lights and mirrors the steel; the Live World (`robot/live/`, R7) shows the same set.

## Shot Cameras (locked in v1)

| Angle | Camera | Where | Lens |
|---|---|---|---|
| front | `ShotCamera.front` | low front three-quarter on the lead side, 4.2 m away, 0.55 m high, looking up | 28 mm |
| side | `ShotCamera.side` | wide side on the lead side, 6.5 m away, 1.3 m high, Android about half the frame height | 35 mm |

## Passes and render

- Cycles, 128 samples, denoised, motion blur 0.5, AgX, 1920x1080, 30 fps.
- Beauty: QuickTime Animation (qtrle), 8-bit RGBA, written by Blender straight to `beauty/<clip id>.mov`, transparent film, the alpha is the Matte. `--beauty png` renders a 16-bit PNG sequence for comparison.
- Shadow Pass: PNG RGBA 16 bit, black with alpha = shadow and contact shade on the floor (1 - Cycles Shadow Catcher).
- Depth Pass: half-float EXR, planar distance from the Shot Camera in metres. How it becomes video (range, codec) is the encode step's choice.
- Frames: `<package>/<pass>/<clip id>/NNNN.<ext>`; the Manifest names `<pass>/<clip id>.mov`.
