# Android and foundry set: design note (R5)

Look: Chrome Foundry (the user, 2026-11-15). Source of truth: [build_robot.py](build_robot.py) and [moves.py](moves.py); the `.blend` is generated.

## Android

- Stylised hard-surface steel, about 2.0 m tall. Rigid beveled parts parented to bones: no skinning, so no deformation artefacts.
- Silhouette for 1080p: broad shoulder domes, V-shaped chest, narrow gunmetal waist, chunky forearm gauntlets and shins, a small head with a crest. Every limb is at least 10 cm thick, so it reads at 1/4 frame height.
- Materials: polished steel (metallic, roughness 0.06 plus 0.08 noise, a cool strip light for long highlights) for the shell, dark gunmetal for joints, waist and back pack, so the parts separate. One emissive amber visor slit (colour 1, 0.35, 0.03 at strength 1.5, roughness 0.7, no specular), the only light on the body. A brighter emitter turns cream-white under AgX.
- Rig: root, hips, spine, chest, neck, head; arms and legs as 2-bone IK to wrist and ankle targets with fixed poles (elbows out and back, knees forward); pole angles are chosen by the build in the guard pose. Feet hang under their IK targets, so a planted ankle at 0.10 m puts the sole on the floor.
- Stance: orthodox (left foot and hand lead), body turned 30° clockwise, chin tucked, Android faces -Y.

## Moves ([moves.py](moves.py))

All Moves: 4 beats at 124 BPM, 30 fps, 58 frames, start and end in the guard Key Pose, a small bob between beats so a held guard never freezes. Keys on a beat grid, smoothstep between keys, one key per frame baked into Blender.

| Move | Tier | Hits (frame, limb) | Cut Points |
|---|---|---|---|
| idle_guard (Idle Clip) | calm | none | 0 |
| jab_cross | build | 15 hand_l 0.6, 29 hand_r 1.0 | 0, 3 |
| front_kick | drop | 29 foot_l 1.0 | 0 |
| take_hit | build | 15 head 1.0 | 0, 3 |

Cut Points are computed: a beat counts when its frame is within 0.5° and 5 mm of the guard.

The Idle Clip is the guard plus waves a·0.5·(1 − cos(2πk·f/57)): zero offset and zero speed at frames 0 and 57, so the identical first and last frames loop without a seam.

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
- Beauty: PNG RGBA 16 bit, transparent film, the alpha is the Matte.
- Shadow Pass: PNG RGBA 16 bit, black with alpha = shadow and contact shade on the floor (1 - Cycles Shadow Catcher).
- Depth Pass: half-float EXR, planar distance from the Shot Camera in metres. How it becomes video (range, codec) is the encode step's choice.
- Frames: `<package>/<pass>/<clip id>/NNNN.<ext>`; the Manifest names `<pass>/<clip id>.mov`.
