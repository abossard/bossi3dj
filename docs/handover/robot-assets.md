# Robot assets: from the ratings to the builds

Proposal of 2026-11-17. Nothing is built yet. Each Blender step waits for a slot from the orchestrator. Packs, previews and licence notes: [robot/assets/README.md](../../robot/assets/README.md). Review page: https://claude.ai/artifact/96MxnQ3pehYHytBsvSSndp (the `ratings`, `ideas` and `state` collections are read with ArtifactData).

## What the user decided (ratings read 2026-11-17, 06:35)

- 5 stars:
  - HUMANOID M2000, ANDROID JUNO and the Security Bot;
  - Mission to Minerva, Neo City, Luminara, Arclink Megapolis and DUNE;
  - all 10 new Moves.
- 4 stars: the Arclink biomes. 3 stars: today's scripted Android. 1 star: today's Chrome Foundry set.
- Roles picked on the page (`state/picks`):

  | Role | Pick |
  |---|---|
  | Android | HUMANOID M2000 |
  | Arena | Arclink Megapolis |
  | Backdrop | Arclink biomes |
  | Opponent | Security Bot |

- Notes: "LOVE IT. ALL OF IT!" No scene ideas saved, no favourites.
- Luminara comment: the project is non-commercial, "just for me for fun". Licence gaps (Cargo tier, missing licence texts) no longer block anything. Keep the Security Bot's CC-BY credit anyway.
- Scope from the same session:
  - use only the three Mixamo packs in `robot/assets/mixamo/packs/`, never the loose FBXs in `~/Downloads` (the Godot scene's);
  - prefer high-quality assets that build reliably.

## Build order

The picks go first. Everything else rated 5 stays as a variant for later.

### 0. Inspect (Blender slot 1, about 15 min)

Every downloaded `.blend` gets `inspect_asset.py` before any import. It opens a file with auto-run off and writes `report.json` plus the text blocks:

```bash
B=/Applications/Blender.app/Contents/MacOS/Blender
for f in "robot/assets/humanoid_m2000/extracted/HUMANOID M2000/DROID.blend" \
         "robot/assets/security_bot/security_bot_v1/security_bot_release_v1.blend" \
         "robot/assets/juno_android/extracted/ANDROID. JUNO FEMALE B/ANDROID.blend" \
         "robot/assets/arclink_megapolis/extracted/GT ArcLink City Data Megapolis.blend"; do
  n=$(basename "$(dirname "$f")"); $B -b --factory-startup "$f" -P robot/build/review/inspect_asset.py -- robot/build/probe/asset/"$n"
done
```

What to read in the reports:

| Asset | Check |
|---|---|
| M2000 | Bone names and IK (the FBX has 74 bones, root `ROOT`), height in model units, materials. |
| Security Bot | Armature, height, and its two poses ("Default Mode", "Gun Mode"). |
| Juno | Whether `ANDROID.blend` holds the Auto-Rig Pro rig (the downloaded FBX has none). |
| Arclink | The object names in the Dark catalogue. |
| All | Read every text block before anything runs. |

### 1. Android: M2000 replaces the scripted parts

Keep our rig as the driver and let the M2000 rig follow it. Then `moves.py`, `exchanges.py`, the Clip Data points and `check()` stay as they are.

- **New `import_asset` step in `build_robot.py`**, called after `build_rig`:
  - Append the M2000 collection from `DROID.blend` (`bpy.data.libraries.load`, append, not link, so the build stays self-contained).
  - Drop `FLOOR_*` and `ENV_*`.
  - Apply transforms and scale so its hips and head match our rest pose (hips 1.00 m, head top 1.98 m).
  - Put the soles at the ankle height from `moves.ANKLE_Z`.
- **Bone map**: a table in `build_robot.py` from our deform bones to M2000 bones:
  - `hips`, `spine`, `chest`, `neck`, `head`;
  - `upperarm`, `forearm`, `hand` (.L and .R);
  - `thigh`, `shin`, `foot` (.L and .R).
  - Each M2000 bone gets a Copy Rotation constraint from ours, and the hips also get Copy Location.
  - Our IK and Key Poses keep working unchanged.
  - The names come from the report in step 0.
- **Drop `build_parts`** (the boxes, spheres and cylinders). Keep `build_points` and re-parent the points to the M2000 head, hands and feet.
- **Look**: keep the M2000's own white shell. Set the metal to roughness 0.25 or more, so it holds light instead of mirroring a black world (the reason #28's Android read dark). Add an emissive visor and a rim light per Angle.
- **Check**: `check()` (planted soles, lowest point) and one probe frame per Key Pose. M2000 has 302k triangles, which is fine for pre-rendered Clips.
- **Juno as a variant later**: the same bone map, with a second table if the inspect shows Juno's rig.

### 2. Opponent: the Security Bot at 6 m

- **Finding: the asset is not the hunched hammer-and-claw machine GIANT.md describes.** Its own previews show a slim biped with a white shell, black joints and a red chest light, plus a "Gun Mode" with a shoulder cannon.
- **Proposed change to [GIANT.md](../../robot/build/GIANT.md)** (not applied, the robot build session owns that file):
  - `g_hammer` and `g_claw` become the right and left fists.
  - The overhead hammer becomes a two-fist smash.
  - The claw sweep becomes a low backhand.
  - The core stays the red chest light.
  - The Exchange names and beat timing in `exchanges.py` stay.
- **Import**: the same `import_asset` step, scaled to 6 m, feet on the floor, 4 m in front of the Android facing it. Bone map from a giant rig driven by `exchanges.py`'s control points.
- **Check**: the Exchange tests (both key tables, speed cap, planted ankles, the contact rule).

### 3. Arena: Arclink Megapolis, Dark set

The Clips' beauty Pass holds only the fighters. The set is invisible to the camera but shows in reflections and catches the shadow. The Live World shows the set itself. So the arena changes both what the steel reflects and what the Live World draws.

- **`build_set`**: replace the foundry hall (rated 1 star) with Arclink Dark ground, road and passageway pieces appended from the asset catalogue, tiled about 14 by 14 m around the duel.
- **Keep the 12 m `floor_catcher`** exactly as it is, so the Shadow Pass does not change.
- **Keep sodium as the key light.** Drop the molten channel unless the user asks for it back.
- **Cover piece**: one Arclink entrance piece placed at the edge of the duel is the cover for `cover_flank`.

### 4. Backdrop: Arclink biomes, after one question

- The biomes need the Geo-Scatter addon (the free Biome Reader, per the pack's readme). Installing an addon needs the user's yes.
- **Reliable route that needs no addon**: hand-place the Arclink Dark large and mid buildings in a ring 15 to 60 m behind the Angles, as instances with 1K textures. This gives the same dark city as `biome_1.jpg`.
- **User decision of 2026-11-17: install the Biome Reader.**
  - The free download is a form on https://www.geoscatter.com/download.html (name, profession, email, the terms, a security check). The user fills it in; agents don't. The site says other sources aren't legitimate.
  - Downloaded 2026-11-17: Biome Reader 5.6.4, a Blender extension for Blender 5.2 or later (this machine has 5.3.0), in `robot/assets/geoscatter/`. Details and its network fetch: [robot/assets/README.md](../../robot/assets/README.md).
  - Install once the orchestrator gives a Blender slot: Preferences > Add-ons (or Get Extensions) > Install from Disk, depending on what the archive turns out to be.
  - Licence (geoscatter.com/legal): the engine is free, renders need no extra licence, and the scripts are GPL-3.0.
- **Installed 2026-11-17, about 10:15** (orchestrator slot after R5), with `robot/build/review/biome_reader_setup.py`. Preferences diff (`robot/build/probe/biomes/before.json` against `after.json`):
  - `bl_ext.user_default.biome_reader` was added to the enabled add-ons;
  - its own preferences: `fetch_automatic_allow` off, `blend_environment_path_allow` on, and two search paths (`arclink_megapolis/extracted/`, `binaryframe_biomes/kit/`);
  - nothing else changed: other add-ons, extension repositories, asset libraries and online access are as before.
  - Files written: `~/Library/Application Support/Blender/5.3/extensions/user_default/biome_reader/` and `config/userpref.blend`. The Arclink, BinaryFrame and FutureScratch biomes were copied into `~/Library/Application Support/Blender/data/scatter library/_biomes_/GreebleTown/`.
- **Preview round B1** (`biome_preview.py`, front Shot Camera, Eevee half size, 5 min for 3 frames; rubric `robot/build/review/rubric-biomes.md`; frames in `robot/build/probe/biomes/`, git-ignored):
  - `arclink_city_1.png` passes: a dark megastructure city with cyan trims fills about 45 % of the frame behind the figure.
  - `chipset_01.png` and `chipset_04.png` fail: the BinaryFrame parts are at real mainboard scale, so they show as specks on the horizon (about 2 % of the frame). To use BinaryFrame as a megastructure, scale its instances up about 100 to 200 times, or scatter it on a small plane close behind the duel and scale that. This needs one more slot.
- **BinaryFrame megastructure, round B2** (2026-11-17 12:22, 3 min of Blender; `biome_preview.py` takes `--scale`, `--area`, `--y0`, `--tag`, `--measure`):
  - Measured at scale 1, the median part is 0.45 m (chipset_01) and 0.37 m (chipset_04), so S = 20, not the 100 to 200 guessed in B1. Scaling the emitter object without applying it scales positions, spacing and sizes together, because Geo-Scatter's scale and density spaces default to "local".
  - At `--scale 20 --area 120 120 --y0 8`, the median part is 9.0 m and 7.3 m, and the largest are 41 m and 19 m. That gives 171 instances (chipset_01) and 763 (chipset_04).
  - `chipset_04_mega.png` passes, marginally: tall lit fins and big cylinders behind the figure read as power-plant machinery and fill about 25 % of the frame. The right third is still dark.
  - `chipset_01_mega.png` fails: the scale now reads big, but 171 instances are too sparse (about 5 % of the frame) and mostly black on black. Next try is a bigger `--area` (e.g. 240 240) or S 12, measure first.
  - Command: `$B -b robot/build/robot.blend -P robot/build/review/biome_preview.py -- robot/build/probe/biomes [--measure] --scale 20 --area 120 120 --y0 8 --tag _mega "$L/Binary Frames/chipset_01.biome" "$L/Binary Frames/chipset_04.biome"`, with `L="$HOME/Library/Application Support/Blender/data/scatter library/_biomes_/GreebleTown"`.
- **FutureScratch megastructure, round B3** (2026-11-17, one slot of about 6 min):
  - Kit search path added with `biome_reader_setup.py configure robot/assets/futurescratch_biomes/kit`. The only change in the userpref dump is that one entry in `blend_environment_paths` (`robot/build/probe/biome_reader/before_fs.json` vs `after_fs.json`).
  - Measured at scale 1, the median part is 2.0 m (greeble_01, 135 parts) and 2.0 m (greeble_03, 9 parts), so S = 4.
  - At `--scale 4 --area 200 200 --y0 8`, the median part is 8.1 m and 8.0 m, the largest 94 m and 47 m, with 1990 and 19125 instances.
  - Both pass: `greeble_01_mega.png` shows a giant rusty tank with orange bands, pipes and coils over the figure (about 90 % of the frame). `greeble_03_mega.png` shows a refinery of stacked drums, copper pipes and spheres (about 85 %).
  - The reviewer notes that the nearest parts sit close to the camera, so it reads as an industrial interior more than a far skyline. For a skyline, raise `--y0` (e.g. 40).
  - Command: as above, with `"$L/Future Scratch/greeble_01.biome" "$L/Future Scratch/greeble_03.biome"` and `--scale 4 --area 200 200 --y0 8 --tag _mega`.
- **Then**: run one biome preset (`arclink_city_1`, the dark blue-lit one) once in a build step, realise it to instances, and save it into the scene, so the live Blender never runs Geo-Scatter.
- **Live World budget**: instances only, a triangle cap. Judge fps only when `make status` says `fps_trustworthy`.

### 5. City fill (wide Angles)

One biome or hand-placed far layer, 60 to 300 m, fogged. Folded into step 4.

### 6. Moves from the Mixamo packs

All 10 were rated 5. Speed is the clip's length over its beats on the 124 BPM grid (below 1x is slow motion). "Reliable" means no contact between the bodies.

| Move | Build | Tier | Bars | Key Poses | Clips (speed) | Hand-keyed | What happens | Angle |
|---|---|---|---|---|---|---|---|---|
| backflip_uppercut | reliable | drop | 4 | guard > guard | back flip to uppercut (0.75x, slow motion) | none | the flip hangs in the air over bars 1 to 3, the uppercut lands on the downbeat of bar 4 | duel_low, a cut on the uppercut |
| backflip_uppercut_fast | reliable | drop | 2 | guard > guard | back flip to uppercut (1.5x) | none | the same, punchy, for dense drops | close_android |
| hammer_roll (Exchange) | reliable | build | 1 | guard > crouch | falling to roll (0.93x) | the giant's hammer, no contact | the hammer comes down, the Android rolls out under it, the floor cracks on beat 3 | duel_wide |
| sweep_jump_mocap (Exchange) | reliable | build | 1 | low > crouch | jump (1.12x), hard landing (last beat) | the claw sweep, no contact | mocap weight for the existing sweep_jump | duel_low |
| circle_strafe | reliable | calm | 2 | guard > guard | left strafe walking (1.07x), right turn 90 | the giant's turn | the Android circles in guard | duel_wide, an orbiting camera |
| run_up_leap | reliable | build | 2 | guard > crouch | running (loop, 4 strides) | the leap from leap_slam | the run-up crosses the arena in bar 1 and leaps on bar 2 | duel_wide, tracking |
| breather | reliable | calm | 1 or 2 | guard > guard | idle, idle (2..5) (windows) | none | new Idle Clips with real weight shifts | any |
| dance_break | reliable | calm | 4 | guard > guard | a 16-beat window of gangnam style or samba dancing | the giant's clumsy mirror (optional) | a taunt in the breakdown; a crowd moment | duel_wide |
| cover_flank | medium | build | 2 | low > guard | stand to cover (1.17x), crouched sneaking left (1.31x), cover to stand (1.55x) | none | the Android hides behind an arena piece and pops out on the bar. Needs a reliable arena piece in place | duel_low |
| thrown_landing (Exchange) | harder | drop | 2 | guard > crouch | falling idle (loop), hard landing | the claw grabs and throws (contact) | grab on beat 1, throw on 3, airborne through bar 2, the landing hits the drop downbeat | duel_wide, cut to close_android on the landing |

- **Path that keeps one rig for every character**: turn each clip into channel key tables, not bone animation.
  - A new build step imports the FBX with Blender's FBX importer, inside a build only.
  - It samples per frame the world positions of `mixamorig:Hips`, `LeftHand`, `RightHand`, `LeftFoot` and `RightFoot`, and the rotations of `Spine`, `Spine2` and `Head`.
  - It scales them to our rig and maps them onto `hips`, `hand_l/r`, `foot_l/r` and `spine/chest/head_rot`.
  - It time-warps the key moments onto the 124 BPM grid and writes a `Move` in `moves.py` form.
  - The first and last beat blend into the Key Poses.
- **Order**, reliable first:
  1. `breather`
  2. `circle_strafe`
  3. `backflip_uppercut` (4 bars) and `_fast` (2 bars)
  4. `hammer_roll`
  5. `sweep_jump_mocap`
  6. `run_up_leap`
  7. `dance_break`
  8. `cover_flank` (needs the cover piece from step 3)
  9. `thrown_landing` (a contact Exchange: hand-keyed grab and Hits)
- **Tests**: the existing parametrized Move tests (Key Poses at both ends, no jump per frame, planted ankles) cover every new Move, plus the Exchange tests for the three Exchanges.

### 7. Variants for later (all rated 5)

| Variant | What it needs |
|---|---|
| Juno as the Android | Step 1 with a second bone map. |
| Neo City arena or backdrop | The colour scene; the Neo City `.blend` is 241 MB. |
| Minerva arena or backdrop | Append only the needed objects from the 3.8 GB `.blend`. Its dark-grey panels for the floor. |
| DUNE open-air scene | The 5 KitOps inserts work in Cycles without the addon. The dPack needs the Simple Scifi or Flex addon (the user's yes). |
| Luminara | Waits for its `.blend` (KitBash3D Cargo download, the user's login). |

## Blender slots

| Slot | What | Time |
|---|---|---|
| 1 | Inspect the four `.blend` files | about 15 min |
| 2 | M2000 import, bone map, `check`, Key Pose probes | about 20 min |
| 3 | Security Bot import at 6 m, Exchange probes | about 20 min |
| 4 | Arclink arena and backdrop ring, one probe frame per Angle | about 20 min |
| 5 | Mixamo-to-Move bakes and previews (`QUALITY=low`) | about 30 min |

Before any slot: script work of about one session per step. After the slots: `make robot-render QUALITY=low` for a preview reel, then high quality on the user's word.

## Open questions for the user

1. Answered 2026-11-17: install the Biome Reader (step 4).
2. Retire the molten channel with the foundry hall (rated 1 star), or keep it as an accent?
3. Should the Security Bot use Gun Mode in some Exchanges?
