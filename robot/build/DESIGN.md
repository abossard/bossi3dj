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

Weight ([weight.py](weight.py), #31, docs/research/weighted-animation.md steps 1, 3, 4): `moves.frames()` puts physical layers on the key tables. A Hit holds the Clip still for round(1 + 2·strength) frames, a stomp round(1 + strength); the time then catches up over the next two beats (or by the next Hit), faster where the key table is slow. An Exchange's fighters share one warp. In flight the hips follow a parabola under g, cut at contacts and Dodges in the air; hands and feet move with them. After the hold the fist springs back along its approach, and the hips take a smaller level reaction. Touch-downs from flight and stomps dip the hips and hands, starting at the falling speed. Recoils and dips fade out over the last 10 frames, and the hips give way where a planted leg would lose its foot. Step 2 (not on Idle Clips): each chain samples the key table early or late (hips lead by 3 frames, the head trails by 2) and follows it through a second-order spring. Heavy chains are slow and damped, fists fast; the giant's springs are 0.6x slower. No channel strays more than 6 cm or 10° from its key. Pins restore the key at the first and last frame, at every Hit (the whole body, so the strike reaches), and around each flight. Planted feet and flights keep the key table. The spring runs on the key table's own timeline, before the hit-stop. Last, the fall limit: standing, the hips never bend down harder than 0.9 g (the floor pushes, it cannot pull), so a drop starts earlier and a rebound's crest rounds off; Hits, holds, flights and the ends stay keyed. Test: the vertical ground force per kg on the hips stays above 0 outside holds and flights. The landing dip is 2 Hz, at most 5 cm, so it stays inside that limit. `python3 robot/build/weight.py` prints the research's check per Move (hips acceleration in flight, ground force per kg, friction), before and after.

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

- Cycles, 128 samples, denoised, motion blur 0.25 (0.5 smeared fast Hits, round A2), AgX, 1920x1080, 30 fps.
- Beauty: QuickTime Animation (qtrle), 8-bit RGBA, written by Blender straight to `beauty/<clip id>.mov`, transparent film, the alpha is the Matte. `--beauty png` renders a 16-bit PNG sequence for comparison.
- Shadow Pass: PNG RGBA 16 bit, black with alpha = shadow and contact shade on the floor (1 - Cycles Shadow Catcher).
- Depth Pass: half-float EXR, planar distance from the Shot Camera in metres. How it becomes video (range, codec) is the encode step's choice.
- Frames: `<package>/<pass>/<clip id>/NNNN.<ext>`; the Manifest names `<pass>/<clip id>.mov`.

## Android model: HUMANOID M2000 (the user's pick, 2026-11-17)

Our rig stays the driver; `moves.py`, `exchanges.py`, the Clip Data points and `check()` do not change. Plan, settled by `review/inspect_assets.sh` (slot 1):
- The FBX holds 74 bones under `ROOT`, most named `Bone.011` to `Bone.050`, plus named mesh pieces: HIP, WAIST, CHEST, NECK, HEAD, ARM, FOREARM, HANDS, THIGH, SHIN, FOOT and WIRES (`.001` and `.002` copies for the other side). Names alone give no map; the report's bone tree (heads and tails) and mesh binding (parent bone or Armature modifier with vertex groups) decide the path:
  - Rigid pieces (each piece moves with one bone): parent each piece to our matching bone (hips, spine, chest, neck, head, upperarm, forearm, hand, thigh, shin, foot), as `build_parts` does now, and drop the M2000 armature.
  - Skinned mesh: keep the M2000 armature, give each mapped bone a Copy Rotation from ours (hips also Copy Location), matched by head position.
- Import (`import_asset` in `build_robot.py`): append the collection, drop FLOOR_* and ENV_*, scale so hips sit at 1.00 m and the head top at 1.98 m, soles at the ankle height; re-parent the Clip Data points to the M2000 head, hands and feet; metal roughness 0.25 or more, an emissive visor and a rim light per Angle.
- Proof: `check()` (planted soles, lowest point), one probe frame per Key Pose, then the Eevee preview of every Move for the reel.

Built (2026-11-17): the M2000 is a hybrid, rigid pieces parented to its bones plus skinned hands, neck and wires. `import_m2000` bakes every piece in its saved pose, turns the model to face -Y, scales it by 0.1133 (shoulders at 1.54 m, where the Move tables put the guard; hips 1.094 m, head top 1.92 m, ankles 0.10 m), lines each piece up with our bone (`M2000_PIECES`: torso as is, limbs turned onto our bone at the joint, feet by the ankle with the sole on the floor), splits the hands by side and drops its armature, floor, environment and wires. Our rig's bones take its proportions; the legs stay straight below the hips at x 0.11 (0.477 m per bone). `check`: planted soles and ankles 0 on all 21 Moves, lowest point 0, punches overreach up to 0.12 m. The shell ramp is lifted from 0.31 to 0.80 grey: the file shows it white only at Filmic +4.5 EV. Fists: `_curl_fingers` bends its finger chains (`M2000_FINGERS`, `FIST_CURL_DEG` 100/90/70 from base to tip) and tucks the thumbs (`M2000_THUMBS`: left x +60, right z +30) before the hands bake; `review/fist_probe.py` chose them (75 on every bone stayed cupped, 120 put the tips through the palm). Guard: the lead fist sits over the lead shoulder (x 0.22) so the forearm stays clear of the face with its narrow shoulders. Both wait for a look at the next build.

## Mocap Clips ([mocap.py](mocap.py), [retarget.py](retarget.py); #31, proof stage)

The user, 2026-11-17: the key-table Moves look mechanical. Mixamo captures replace them, starting with a proof: `mocap_idle` (Action Adventure `idle (2)`, one bar of a breathing idle that loops) and `mocap_flip_uppercut` (Free Test `back flip to uppercut`, 8 beats, guard to guard).
- The build bakes `mocap.<name>` per Mocap Clip. Every body bone follows its Mixamo bone's world rotation, corrected for the rest-pose difference (T-pose against arms down). Forward kinematics on our bone lengths gives the joints; hips travel scales by the leg length ratio.
- Arms and legs keep their IK: the targets sit on the captured wrist and ankle, the poles beside the captured elbow and knee each frame. Hands take the captured rotation relative to the solved forearm.
- A foot near the floor and nearly still is planted. It holds at one spot, flat, blending over 3 frames. No foot part goes below the floor.
- The time map runs through Anchors (beat, source frame), so contacts land on beats. Hits name their source frame. The first and last beat blend into the Key Poses; an Idle Clip blends its last 12 frames into its first. Net travel is taken out in proportion to the hips' path.
- Weight on top: the hit-stop through the time map, the fist recoil and the stomp dip. No ballistic layer or landing dip: the capture flies and lands by itself. An ankle target past the leg's reach follows the leg.
- `review/mocap_check.py` gives the numbers, `review/mocap_proof.py` the low renders, `review/mocap_reel.sh` the reel beside the hand-keyed Clips.

## Variants ([variants.py](variants.py), #32)

A variant is its own Move in its base's family (`variant_of` in the Manifest, robot/CONTRACTS.md): the same Key Poses, tier and idle, its own Clips. The first batch:
- Idle families: four one-bar variants per Key Pose (`idle_<pose>_v2` to `_v5`). Each is the Key Pose plus a window of a captured idle's micro-motion (breathing, sway, glances; `tracks/*.json` from `extract_tracks.py`), detrended to start and end at the Key Pose and faded over 8 frames, so any variant chains into any.
- Move takes: `jab_cross_v2`, `_v3` move inner keys by up to a frame and scale Hit strengths (other hit-stop holds). The Mocap takes `mocap_flip_uppercut_v2`, `_v3` put the same capture on other Anchors.
- Every variant has a seed. weight.py's seeded layer draws breathing, weight shift, glance and hand height from it, zero at the ends and at Hits.
- The guard Key Pose comes from capture (2026-11-17, the user's Mixamo fight clips): Fighting Idle's mean (`captured.key_pose`), 4 cm deeper, on the hand-keyed guard's planted feet. One line in moves.py (`GUARD = ...`; `HAND_GUARD` to go back). The hand-keyed Moves are still written on `HAND_GUARD`. `moves.on_guard` restyles each of their Poses onto the new guard: what they leave as the old guard's becomes the new one's, and rotations and fists keep their change from it. Hips and feet stay where they were written, so steps and contacts hold. Low and crouch keep their hand-keyed poses; no capture fits them yet. The bladed capture guard leaves the hand-keyed jabs reaching short (overreach up to 0.24 m on jab_cross and jab_jab_hook); the Mocap fight Moves are their replacement.
- Guard Idle family from the fight idles: Fighting Idle twice (its bounce at 0.6, since the soles stay flat), Fight Idle, and Fight Idle-3's weave at 0.5 without its hips turn, which sits at XYZ Euler's 90° lock. Fight Idle-2 repeats Fight Idle frame for frame. Tracks now carry the hands too.
- Mocap fight Moves: `mocap_fist_fight`, `mocap_jab_elbow`, `mocap_uppercut_jab`, with takes (`_v2` and `_v3`; `mocap_uppercut_jab_v2` is the second Uppercut Jab clip). Hits are on contact frames (the fist furthest forward, the elbow's forward stop). Their end blends step a foot to the Key Pose spot instead of sliding it.

## Clip Library ([library.py](library.py), #32)

The package holds the Clip Library: moves.py's key-table Moves with their variants, and the Mocap Moves (mocap.py) as Moves with `source: mocap`, baked as `move.<name>` like the others. The hand-keyed jab_cross, jab_jab_hook and uppercut_combo are gone (the user: unusable); `mocap_jab_elbow`, `mocap_uppercut_jab`, `mocap_fist_fight` and `mocap_flip_uppercut` with their takes replace them. A Mocap Move's Cut Points are its first beat only. `check` measures the Mocap Moves on the posed rig (planted where the foot-lock holds the ankle at 0.10 m); their end blends lift a sole the blend would tilt into the floor.

