# Godot Colossus Scene: what the real models cost

Wanderer: Nomad Marksman Rig (DM-913). Colossus 1: Grock Endboss (Baue Franco). Both CC-BY 4.0, lines in `godot/colossus/CREDITS.md`. Budgets from `godot/colossus/docs/SPEC.md`.

## Stage 1, 2026-11-11: each model alone against its stand-in

`make godot-model-cost` (`tests/model_cost.gd`), Metal, Apple M1 Max, branch `integration/presentable`. Each subject stands alone on the plain at `Land.ARENA` in the scene's sun, fill, fog and haze; the scene's own Colossus and Wanderer are hidden. A probe camera looks at its back from three distances that match the director's shots, with the shot's lens (the lens decides which LOD Godot draws). Grock plays its `idle2` clip; the Nomad turns its Spine bone every frame so the skin is recomputed as under a clip; the Colossus stand-in stands and poses its IK every frame.

Counts are the frame with the subject minus the same view without it. "draws" counts the depth prepass and the colour pass. Frame time is the median of 6 rounds of 100 frames with vsync off (`Engine.max_fps = 0`); stand-in, model, variant and the empty view alternate inside each round. Load on the machine was 65 to 75 (`make status`: `fps_trustworthy` false): read the frame times as differences inside one view, not as fps. Across two full runs the same differences came back to within about 0.3 ms.

| Subject | View (distance, lens) | Tris drawn | Shadow tris | Draws | Shadow draws | Frame ms | Empty view ms |
|---|---|---:|---:|---:|---:|---:|---:|
| Colossus stand-in | close (8 m, 27°) | 16,128 | 16,128 | 8 | 4 | 6.88 | 8.35 |
| Grock | close | 48,675 | 48,675 | 2 | 1 | 7.41 | |
| Grock, no shadow | close | 48,675 | 0 | 2 | 0 | 7.55 | |
| Colossus stand-in | medium (168 m, 14.3°) | 56,448 | 162,432 | 30 | 43 | 8.32 | 8.23 |
| Grock | medium | 48,675 | 146,025 | 2 | 3 | 8.61 | |
| Grock, no shadow | medium | 48,675 | 0 | 2 | 0 | 8.41 | |
| Colossus stand-in | long walk (1,624 m, 6°) | 56,448 | 0 | 30 | 0 | 10.88 | 10.79 |
| Grock | long walk | 24,337 (LOD 1) | 0 | 2 | 0 | 11.08 | |
| Grock, no shadow | long walk | 24,337 | 0 | 2 | 0 | 10.97 | |
| Wanderer stand-in | close (3.2 m, 27°) | 7,688 | 7,688 | 6 | 3 | 9.83 | 10.21 |
| Nomad | close | 43,786 | 43,786 | 4 | 2 | 10.19 | |
| Nomad, skeleton still | close | 43,786 | 43,786 | 4 | 2 | 10.18 | |
| Wanderer stand-in | medium (4.5 m, 37.8°) | 7,688 | 7,688 | 6 | 3 | 9.14 | 9.29 |
| Nomad | medium | 43,786 | 43,786 | 4 | 2 | 9.62 | |
| Nomad, skeleton still | medium | 43,786 | 43,786 | 4 | 2 | 9.57 | |
| Wanderer stand-in | long walk (24 m, 53°) | 7,688 | 7,688 | 6 | 3 | 9.34 | 9.27 |
| Nomad | long walk | 8,854 (LOD 3) | 8,854 | 4 | 2 | 8.82 | |
| Nomad, skeleton still | long walk | 8,854 | 8,854 | 4 | 2 | 8.71 | |

Per subject, built once:

| Subject | Mesh instances | Surfaces | Tris LOD 0 | Bones | Textures | Texture memory |
|---|---:|---:|---:|---:|---:|---:|
| Colossus stand-in | 15 | 15 | 56,448 | 17 | 1 (512 px noise normal) | 1.33 MB |
| Grock | 1 | 1 | 48,675 | 17 | 3 (2k albedo BC1, 2k roughness BC1, 2k normal BC5) | 10.67 MB |
| Wanderer stand-in | 3 | 3 | 7,688 | 0 | 0 | 0 |
| Nomad | 2 | 2 | 43,786 | 53 | 5 (2k each: 2 albedo BC3, 2 normal BC5, 1 metallic-roughness BC1) | 24.0 MB |

Raw rows: [godot-model-cost-stage1.json](godot-model-cost-stage1.json).

### What the numbers say

- Both models sit far inside the budgets: 48.7k of 100k tris for the Colossus, 43.8k of 60k for the Wanderer, 4 to 6 draws (with shadow) per model against 1500, 0.1 M of 3 M visible tris together.
- The models draw fewer calls than the stand-ins (Grock 3 to 5 against 12 to 73; the Nomad 6 against 9), and Godot's own LODs carry the long walk: Grock at 1.6 km draws LOD 1 (24k tris), the Nomad at 24 m LOD 3 (8.9k).
- Frame time: Grock costs 0.2 to 0.5 ms over the stand-in, the Nomad 0.4 to 0.5 ms at close and medium and nothing measurable on the long walk. At close range a model that fills the frame is cheaper than the empty view: it hides terrain and fog.
- Skinning costs nothing measurable: the Nomad with a still skeleton is within 0.1 ms of the one that moves.
- Grock's shadow is the largest single item: 146k shadow tris at medium (three cascades at LOD 0). Switching it off wins 0.2 ms at medium and nothing at the other views.

### Tricks: built and not built

| Trick | Verdict | Expected gain |
|---|---|---|
| Simplified Wanderer skeleton | Built, because the humanoid map needs it: 88 bones to 53 (rig controls, twist and pole bones gone; knee, elbow, pelvis-side, finger-base and shoulder-cloth bones hand their weights to the bone they move with). Frame time: skinning is not measurable, so no further cut (the 30 finger bones stay for the grip). | none in frame time |
| Textures in Metal formats | Built: VRAM compressed with mipmaps (BC1, BC3, BC5), normal maps flagged. Godot's headless import had chosen lossless without mipmaps: 16 MB per 2k map instead of 2.7 to 5.3 MB. | 70 MB of GPU memory against lossless |
| Far LOD or impostor for the Colossus on the long walk | Not built. Godot already draws LOD 1 (24k tris, 2 draws) at 1.6 km; the stand-in drew 56k tris in 30 draws there. | under 0.1 ms |
| Shadow casting per distance (a low shadow proxy for Grock) | Not built. Upper bound measured by switching the shadow off: 0.2 ms at medium, nothing close or far. A proxy (a decimated copy on the same skin, shadow only) would win less. Build if the show frame gets tight. | under 0.2 ms |
| One draw call per character (atlas the Nomad's body and attire) | Not built. Saves 3 of 6 draws against a budget of 1500, and halves the texel density of both. | not measurable |
| Wanderer textures at 1k | Not built: the close grip stands 3 m off. | 18 MB of GPU memory, no frame time |
| Nomad body albedo as BC1 | Not built: its PNG has an alpha channel, so Godot stores BC3. | 2.7 MB of GPU memory |

## Stage 2, 2026-11-11: the Wanderer

The Nomad replaces the stand-in when its model is present (`assets/MODELS.md`); without it the stand-in shows and the start prints one line.

### How he moves

- Clips: Mixamo FBX from `assets/mixamo/` play on a source skeleton whose bones are renamed to Godot's humanoid profile at load (`wanderer/clips.gd`); `RetargetModifier3D` (global pose) carries the pose onto the Nomad, whose bones already carry the profile names (renamed in the prepare, so the import BoneMap would be one to one and is not set). Nothing of Mixamo is saved in the project.
- AnimationTree: a walk blend (idle at 0, walk at 1.6 m/s, run at 4.5 m/s) under a time scale that plays each clip at the speed whose planted foot does not slide; a climb transition (hang idle, shimmy left and right, climb up and down, hang swing); a mode transition (ground, climb, fall, stand up). Cross-fades 0.35 s (mode) and 0.25 s (climb) on an ease-in-out curve.
- After the retarget, on the Nomad, in this order: the procedural pose (only without clips), the feet on the land (`wanderer/wanderer_feet.gd`: IK only where the land under a foot differs from the land under the body by more than 1 cm, the hips drop for the lower foot), the leg IK, the chest look-at (35°, influence 0.35), the hand IK on the grips, the head look-at (60°, 0.85, 0.6 s ease). The chest turns before the hand IK: after it, it carried the hands 0.6 m off the grip.
- Hanging: the body hangs where the hang clip's pose puts the toes on the surface and the shoulders at 92% of an arm's length from the grip, fitted from the clip's pose every frame (smoothed 0.4 s). The turn toward a grip's surface is a damped spring (0.15 s). Moving between grips the leading hand goes first, decided once per move (sideways the hand on that side, up and down they alternate). A grip low on the legs: he stands on the land and reaches up.
- Fall: he lets go on impact and drops under gravity (the old snap to the ground from more than 6 m up was a jump of metres in one frame), then stands up.

Clip slots, the file each expects and its fallback: `godot/colossus/assets/MODELS.md`. Played now: idle (`Idle.fbx`), walk (`Walking-2.fbx`), run (`Fast Run.fbx`), shimmy left (`Braced Hang Shimmy.fbx`). On a fallback: hang idle (the shimmy's first frame, held), shimmy right, climb up, climb down, hang swing (hang idle), fall idle and stand up (idle).

Mixamo clips still to download (FBX Binary, Without Skin, 30 fps, In Place for walk and run), with the file name `make godot-models` copies:

| Slot | Mixamo clip | File name |
|---|---|---|
| hang idle | Braced Hang | `Braced Hang.fbx` |
| shimmy right | Braced Hang Shimmy, Mirror ticked (or Right Braced Hang Shimmy) | `Right Braced Hang Shimmy.fbx` |
| climb up | Climbing Up Wall | `Climbing Up Wall.fbx` |
| climb down | Climbing Down Wall | `Climbing Down Wall.fbx` |
| hang swing | Hanging Idle | `Hanging Idle.fbx` |
| fall idle | Falling Idle | `Falling Idle.fbx` |
| stand up | Standing Up | `Standing Up.fbx` |

`Braced Hang Hop Up.fbx` (downloaded) is a one-shot hop onto a ledge: as the looping climb-up slot it jumped 37 m/s at every loop, so it is not used.

### Numbers (`make godot-wanderer-motion`, headless, the stand-in Colossus)

| What | Result |
|---|---|
| Pose at idle | ankles 0.06 m above the origin, head 1.56 m, hands 0.84 m (arms down) |
| Head toward the Colossus at idle | 10° off the line to its head, which is 37° up |
| Walk 1.6 m/s, planted foot | slides 0.08 m/s median, 0.37 m/s p90 (231 planted ticks); clip stride 1.60 m/s on the Nomad's legs, played at 1.00 |
| Run 4.5 m/s, planted foot | slides 0.37 m/s median (30 planted ticks); `Fast Run` strides 5.54 m/s, played at 0.81 (`Slow Run` at 1.58 slid 3.0 m/s) |
| Hands on the grip while hanging | 0.014 m median, 0.058 m p90 from the target |
| Largest change of a joint's velocity in one tick (a pop shows as a jump) | steady walk 3.3 m/s, steady run 15.4 m/s (foot strike); idle to walk 2.1; ground to reach (from the run) 5.9; reach to hang 3.9; hang to move 2.9; move to hang 2.9; let go at the Fall 0.0 |
| Without any clip (procedural pose) | arms down, head turns; the procedural walk slides 1.8 m/s and the hands stop 0.11 m short of a grip |

The probe judges a pop against 4 m/s, and a change of state out of a run against the run's own steady motion. Before the fixes the same probe measured: walk slide 0.56 m/s (stride ratio from hip height, not leg length), hands 0.6 m off the grip, 37 m/s hand jumps (the leading hand flipped each tick on moves straight up), 423 m/s at the let go.

### Readability in the low hero shot on the long walk (`make godot-wanderer-read`, Metal)

The rubric fails of round 3 (`shot-2`, `2-approach-low-hero`) were not a dark figure: at the Shrine start the slope stood between the low camera and the Wanderer (3 of 19 samples of the line of sight under the land; the frame with him hidden was identical). `Director._long_walk` now raises the camera until the line to his knees clears the land by 0.2 m (`Director.clear_height`, tested).

| Gap to the Colossus | Wanderer px | Body luma | Ground beside | Contrast |
|---|---:|---:|---:|---:|
| start at the Shrine, before | 321 | 0.083 (hidden: 0.083, not drawn) | 0.081 | 0.03 |
| start at the Shrine, after | 244 | 0.126 | 0.429 | 0.71 |
| 1500 m | 183 | 0.179 | 0.242 | 0.26 |
| 1000 m | 526 | 0.442 | 0.665 | 0.34 |
| 450 m | 526 | 0.434 | 0.569 | 0.24 |

The stand-in at the same places: 0.13 to 0.36. A rim on the Nomad's materials changed none of these numbers and was taken out; no light was added.

### Cost (`make godot-model-cost`, Metal, load 30, not fps-trustworthy)

"wanderer" is the scene's own Wanderer: the Nomad on its clips through the retarget, feet, hand IK and look-at, posing every frame.

| View | Stand-in | Nomad (one bone moved) | Wanderer (clips, retarget, IK) | Empty view |
|---|---:|---:|---:|---:|
| close (3.2 m, 27°) | 8.38 ms | 8.74 ms | 8.80 ms | 8.73 ms |
| medium (4.5 m, 37.8°) | 8.41 ms | 8.75 ms | 8.70 ms | 8.52 ms |
| long walk (24 m, 53°) | 8.59 ms | 8.66 ms | 8.73 ms | 8.48 ms |

The animated Wanderer costs 0.14 to 0.42 ms over the stand-in, the same as the bare Nomad: clips, retarget and IK are not measurable on top of the mesh. Raw rows: [godot-model-cost-stage2.json](godot-model-cost-stage2.json).

### Look round 4

`docs/reports/godot-look-verdict.json`, round `godot-look-4`, rubric unchanged, one reviewer call on 27 frames: 26 pass, 1 fail. `shot-2` and `2-approach-low-hero` (the round 3 fails) pass: the Wanderer reads as an upright cloaked figure on the ridge. New fail: `4-shake-close-grip`, `wanderer-visible`: only two limb ends show at the top edge (pass in round 2 with the stand-in). Not fixed in this round; the close grip's aim at the hanging Nomad is the open item. Contact sheet for the user: [docs/images/2026-11-11/godot-models-wanderer.jpg](../images/2026-11-11/godot-models-wanderer.jpg).

## Stage 3, 2026-11-11: Grock as Colossus 1

Grock replaces the stand-in at the first roster entry (28 m) when its model is present; without it the stand-in shows. Code: `colossi/grock_colossus.gd`, `colossi/rig_gait.gd`.

### What Grock keeps and what it cannot do

- Rig: its own 17 bones. The imported tree stays whole (its clips address `Armature/Skeleton3D`), turned 180° so it walks toward -Z like the stand-in.
- Idle: `idle2` loops on the whole body; `RigGait` then replaces the legs with the procedural stride, bobs the hips, rolls the spine in a Shake and turns the head toward the Wanderer. Grock has no walk clip: the stride is procedural, its sweep fitted to the leg (hip to ankle 11.9 m) so the planted foot covers the 12.6 m of a step.
- Feet: `TwoBoneIK3D` on thigh, shin and foot, targets at the posed ankles, never below the land.
- Grab Points: 19 (calves, thighs, low back, a 4 by 3 grid on the back, the top of the hump, the top of the head as the climb's goal), found once on the mesh's back and top surface at rest; each rides the bone that skins that spot most (`root`, `Spine2`, `neck`, legs, shoulders). Links as on the stand-in.
- Fall: a ragdoll of 17 bodies (one per bone, capsules between joints, a third of their length thick), pinned joints built at the topple, the stand-in's push.
- Stands while he climbs: the Colossus no longer walks or turns while the Wanderer holds on (`Colossus.carrying`, SPEC: "stands while he climbs"). Before, the stand-in roamed on with him.
- Haze: its material gets `disable_fog`, as the stand-in's stone.
- Prepared once at start (`Roster.warm`: the model loaded and the Grab Points found); a Reset instantiates it.
- Not used: the Attack and Defend clips. The Shake stays the procedural spine roll; whether a clip reads as a shake-off was not tried or judged.
- Cannot: walk with its own legs' clip (none exists), bend a hand (no hand bones; the forearm is the last bone), show eyes (the stand-in's glowing eyes are gone).

### Numbers

`make godot-colossus-rig` (headless):

| What | Result |
|---|---|
| Ragdoll bodies | 17 (at most 24) |
| Grab Path | reaches the head from all 19 Grab Points |
| Walking at 5 m/s | ankles 0.78 m above the land at least (their rest height), planted foot slides 0.10 m/s median, 0.27 m/s p90 (it slid 1.7 m/s with the stand-in's stride angles) |
| Carrying | moved 0.00 m and turned 0.00° in 3 s with the Wanderer on it |
| Fall on flat land | down after 4.5 s, chest 1.8 m above the land, no body flung (farthest 17.7 m from the chest) |
| Fall on a 14° slope | down after 10.3 s, chest 1.6 m above the land, farthest body 21.0 m |

`make godot-wanderer-motion` on Grock: hands on the grip 0.0 cm median, 9.4 cm p90; joint velocity jumps at climb transitions 2.9 to 3.3 m/s; the topple of the Fall jumps 18.4 m/s (the ragdoll's push carries his grip).

`make godot-framing` (Metal), five runs: exit 0 five times, 64 of 64 checks each. The low hero walk from 300 m keeps him whole on 50 of 50 every time; with the giant standing, that walk now closes the gap only from 300 to 275 m and no longer crosses the 200 m switch between the long-walk and the near low hero camera (held still, 320 of 320 samples across that switch from eight directions, stage 2). Close grip through a Shake: head, hands and hips in frame on 30 of 30 in each run, after the close grip aims at them with 1.6 m of room (with 0.8 m, 17 of 30 on Grock: he climbs on during the pinned Shake and the dolly lags). Grock against the haze at the start, 1.6 km: contrast 0.99 (the stand-in 0.82), 172 px tall.

`make godot-hitch ARGS=again` (the Reset rebuilds Grock): worst frame 35 ms in the Reset (limit 50), medians 16.7 ms in every Phase. The plain run (the Reset builds the next stand-in): worst 47 ms.

### Cost of the whole scene (`make godot-model-cost`, Metal, load 11, not fps-trustworthy)

The Colossus standing, the Wanderer 6 m behind it, both stand-ins against both real models, alternating in one run:

| View | Stand-ins: tris (shadow) | draws (shadow) | frame | Models: tris (shadow) | draws (shadow) | frame | Empty view |
|---|---|---|---:|---|---|---:|---:|
| close (8 m, 27°) | 16,128 (16,128) | 8 (4) | 8.54 ms | 48,675 (48,675) | 2 (1) | 8.62 ms | 8.66 ms |
| medium (168 m, 14.3°) | 64,136 (177,808) | 36 (49) | 9.40 ms | 56,483 (161,641) | 6 (7) | 9.88 ms | 9.30 ms |
| long walk (1.6 km, 6°) | 64,136 (0) | 36 (0) | 12.53 ms | 27,793 (0) | 6 (0) | 12.71 ms | 12.45 ms |

The real models cost 0.08 to 0.48 ms over the stand-ins and draw 6 to 13 calls where the stand-ins draw 12 to 85. Raw rows: [godot-model-cost-stage3.json](godot-model-cost-stage3.json).

## How the models are prepared

```bash
make godot-models
```

Unpacks `nomad-marksman-rig.zip` and `grock-endboss.zip` from `DOWNLOADS` (default `~/Downloads`) into new, empty, git-ignored folders under `godot/colossus/assets/incoming/`, runs `tools/godot_prepare_models.py` in headless Blender on each source `.blend` (scripts off), imports the project, writes the import settings (`tools/godot_model_import.py`) and imports again. Out: `godot/colossus/assets/models/nomad/nomad.gltf` and `godot/colossus/assets/models/grock/grock.gltf` with `.bin` and `textures/`, 44 MB together. Not in git (user decision of 2026-11-11); pages and downloads in [godot/colossus/assets/MODELS.md](../../godot/colossus/assets/MODELS.md).

- Source: the `.blend` files, not Sketchfab's glTF. Grock's glTF splits the body into two meshes and carries a flat 4 KB normal map; the `.blend` has one mesh. The Nomad's `.blend` has the cleaner bone list (the glTF adds bone-shape meshes as nodes).
- Nomad: rifle, lights, bone-shape meshes removed; skeleton as above, renamed to Godot's humanoid profile (`Root`, `Hips`, `Spine`, `Chest`, `Neck`, `Head`, `LeftShoulder` ... `RightFoot`, fingers `LeftIndexProximal` ...; `Scarf1` to `Scarf3` keep their names); scaled to 1.75 m, feet at 0, hips over the origin. The attire keeps alpha (5% of its triangles sample alpha below 0.5: the frayed cloth), alpha scissor, two-sided; the body is one-sided. Textures stay 2k.
- Grock: deform bones only (17; the four IK bones are baked into the clips), all eight clips (Attack1 to 3, Defend1 to 3, Idle1, idle2). The metallic map is black everywhere and the normal map flat: both go, metallic 0. A normal map is made from the author's height map, scaled so the median surface tilts 12° (read at the material's own scale the height map tilts half the surface past 50°). Roughness stays. One-sided. Exported at the model's size (2.00 units, feet at 0.011); the import scales it to 28 m (`nodes/root_scale=14.0339`, clips and rest scale with it).
- Import settings: textures VRAM compressed with mipmaps, normal maps flagged; Grock `nodes/root_scale=14.0339`.
- The `.bin` of the Nomad is not byte-identical between two runs of the prepare (the texture PNGs and Grock are); the content is.

## Not in this session: Colossus 2 and 3

- Titan (`free-game-character-ancient-titan-vol2.zip`, 424 MB; the Sketchfab glTF 248 MB): 56k tris, one skin with 302 joints, no clips, 15 textures. Needs: a skeleton cut to the bones the Grab Path, foot IK and ragdoll use (about 20, the rest merged as for the Nomad), textures down to 4k albedo and normal and 2k for the rest, unused maps dropped. The rigged file behind the link on the Sketchfab page was not available; the glTF skin is what there is.
- Golem (`character_free_golem_rock_by_oscar_creativo.zip`, 668 MB): 84k tris, 90 joints, one clip "Motion", 59 textures. Needs the same plus a texture merge (59 maps suggest many materials: one draw call each). Stays out of git until its author confirms the CC-BY license (`docs/GUIDELINES.md`).
