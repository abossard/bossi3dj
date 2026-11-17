# Robot assets (analysis of the 2026-11-17 downloads)

The packs live next to this file (git-ignored, `robot/assets/<name>/`; only this README is committed). Each has `_zips/` (the original archives), `extracted/`, and for Minerva `_other_formats/` (3ds Max and Unreal, left zipped). Previews for the review page are in `_prev/`.

Nothing here has been opened in Blender yet (the 13 h Move render holds Blender until about 09:00 on 2026-11-17). Everything below comes from file lists, readmes, OBJ and FBX text, and `.blend` headers.

All archives passed `unzip -t` / `7z t` and their sizes were stable over 30 s.

| Pack | Folder | What it is | Blender file | Size |
|---|---|---|---|---|
| Kitbash3D Mission to Minerva | `minerva/` | Sci-fi space-station / lunar kit | `kb3d_missiontominerva-native.blend` (3.8 GB, saved by Blender 2.93) | 9.5 GB |
| Kitbash3D Neo City | `neocity/` | Cyberpunk street kit | `kb3d_neocity-native.blend` (241 MB, 2.93) | 2.1 GB |
| Kitbash3D Secrets of the Luminara | `luminara/` | Ancient / pulp adventure kit (airships, ruins, boats) | none yet, textures only | 3.0 GB |
| Greeble Town Arclink City Megapolis | `arclink_megapolis/` | Sci-fi megacity kit, Bright and Dark sets, asset-browser library | `GT ArcLink City Data Megapolis.blend` (49 MB, zstd, Blender 3.0+) | 3.3 GB |
| Arclink City Geo-Scatter biomes | `arclink_biomes/` | 8 Geo-Scatter biome presets that scatter the Arclink kit into a city | none (`.biome` + `.preset`) | 11 MB |
| DUNE Master v1.2 | `dune/` | Desert kit: dunes, mountains, dust haze, landscape geo | 10 `.blend` (Dune 1-3 about 168 MB each, Dune_s, Mountain 1-3, Dust Haze, Landscape Geo, Sand Dunes) plus `DUNE.zip` (KitOps kpack) | 1.3 GB |
| HUMANOID M2000 | `humanoid_m2000/` | Segmented droid (thumbnail: dark, female-looking figure), rigged | `DROID.blend` (24 MB, 3.0), `DROID.fbx`, `DROID.obj` | 72 MB |
| ANDROID JUNO FEMALE B | `juno_android/` | Segmented female android with detailed hands | `ANDROID.blend` (21 MB, 3.3), `ANDROID.fbx`, `ANDROID.obj` | 50 MB |

## Per pack

### Minerva (`minerva/`)
- Contents: 1 `.blend`, 404 PNG (63 materials, 4K, PBR sets: ao, basecolor, height, metallic, normal, roughness), readme. Material names: white, gray and yellow metal panels, shiny metal, armored glass, holo colors, screens, emissive blue/green/gold, magnetic energy, cable, terrain, lawn, water.
- 3ds Max Arnold and Unreal 6.x 2K archives: unused, in `_other_formats/`.
- Preview: no renders in the pack; `_prev/minerva.jpg` is a swatch sheet of its materials.
- Seller: KitBash3D's free kit from October 2022, made for a community challenge (a settlement on a planet in the Minerva Galaxy): cargo ships, rovers, terraformers, community centres, modular habitats. KitBash3D lists 60 models and 63 PBR materials ([kit page](https://kitbash3d.com/pages/mission-to-minerva-free-kit), [CG Channel](https://www.cgchannel.com/?p=140648)).
- Licence: free for individual artists, commercial use included, with a KitBash3D account. The pack ships no licence text. Tier depends on team size; no credit requirement found; AI training forbidden ([licences](https://kitbash3d.com/pages/licenses)). Not redistributable.
- Use: arena and backdrop. Clean white and gray panels with emissive trim fit the Chrome Foundry steel look; the emissive colors can carry beat flashes. The 3.8 GB file is heavy: append only the needed objects, never open it whole in the live scene.

### Neo City (`neocity/`)
- Contents: 1 `.blend`, 384 PNG (62 materials: galvanized steel, brass, painted metal, grating, neon lights, banners, letters, tinted glass, street tiles, asphalt), readme.
- Preview: swatch sheet only.
- Seller: KitBash3D Mini Kit from 2020: street kiosks, apartment blocks and skyscrapers taken from Neo Tokyo, Neo Tokyo 2, Cyber Streets and Neo Shanghai ([kit page](https://kitbash3d.com/products/mini-kit-neo-city)).
- Licence: KitBash3D, commercial use, as above.
- Use: street-level backdrop (neon signs and glass give sodium and color light). Warmer and dirtier than Minerva, closer to a back-alley fight. Light enough to open (241 MB).

### Luminara (`luminara/`)
- Contents: 428 PNG (69 materials: ancient brickwork, boulders, crystals, airship and boat atlases, canvas, rusted metal), no `.blend` yet.
- Preview: swatch sheet only.
- Seller: KitBash3D's challenge kit: ancient temples, aqueducts, tombs and hidden treasure ([behind the kit](https://kitbash3d.com/a/blog/secrets-of-the-luminara-behind-the-kit)). Distributed through Cargo.
- Licence: depends on the tier it was taken under. Cargo Basic and Personal assets are non-commercial ([Cargo FAQ](https://help.kitbash3d.com/en/articles/7939191-cargo-licensing-faqs)). Check before any public use.
- Use: not usable until the `.blend` is downloaded. Fits a ruin or crystal-cavern arena, not the foundry look. Textures only; unused for now.

### Arclink City Megapolis (`arclink_megapolis/`)
- Contents: 1 `.blend` (asset-browser library), `blender_assets.cats.txt`, 354 PNG in `textures/1K`, `2K`, `4K` (PBR with Emission, Alpha, Displacement). Catalog: GT_AL Bright and GT_AL Dark, each with Greebles, Large, Mid and Small Buildings, and Misc (Entrances, Ground Misc, Passageway, Road). Object counts need Blender.
- Preview: swatch sheet (grayscale panels); the real city look is in the biome renders below.
- Seller: Greeble Town on Superhive Market, Blender kitbash buildings for Blender 2.83 to 5.1, royalty-free. One review says it is below Greeble Town's usual quality ([store page](https://superhivemarket.com/products/arclink-city-data-megapolis-kitbash-buildings)).
- Licence: Greeble Town "Commercial License" (readme text in `arclink_biomes/_zips/6fe73a6f...txt`). Geo-Scatter geometry nodes have their own terms (geoscatter.com/legal). Credit not stated.
- Use: the Live World backdrop, a dark megacity behind both fighters, with the Dark set for the foundry mood. Instancing the greebles also adds detail scale cues for the giant machine's body.

### Arclink biomes (`arclink_biomes/`)
- Contents: 8 biomes (`arclink_city_1..8`, each `.biome` plus 3 or 4 `.preset` layers) and 8 preview JPG (350 px), the PDF manual (`_zips/`), readme.
- Preview: `_prev/biome_1..8.jpg`: real renders. 1 is a dark blue-lit city, 5 a gray city with green light lines.
- Use: needs the Geo-Scatter addon (a free Biome Reader exists, per the readme). That runs inside Blender, so it only works in a Blender build step. It can fill a wide city around the arena in few steps.

### DUNE (`dune/`)
- Contents: 10 `.blend`, 11 PNG icons, `DUNE.zip` (kpack: `DUNE.blend`, `DUNE.png`), install note (KitOps dPack/kPack for SCI-FI FLEX).
- Preview: `_prev/dune_*.jpg` (256 px icons: orange dune, mountain on sand).
- Seller: DarioMac, "Dune - Simple Scifi & Scifi Flex dPack" on Superhive: geometry-node sand dunes, mountains and fog. The dPack needs the Simple Scifi or Flex addon; the 5 KitOps inserts (sands, mountains, fog) work alone in Cycles, because the mountains use displacement. Dune values, fog and sandstorm density are modifier settings ([store page](https://superhivemarket.com/products/dune--simple-scifi--scifi-flex-dpack)).
- Licence: none shipped. The store sells it as a normal Superhive product; check the store terms before video use.
- Use: an alternative open-air arena, desert floor with dust haze, for a scene idea that leaves the foundry. Light files except the dunes at 168 MB.

### HUMANOID M2000 (`humanoid_m2000/`)
- Contents: DROID `.blend`/`.fbx`/`.obj`, 2 JPG (a logo and a Warsaw panorama; the panorama is stock-looking, so not to be shipped).
- Geometry (OBJ): 151,558 vertices, 302,164 triangles, 20 objects (head, neck, chest, waist, hip, arm, forearm, hands, thigh, shin, foot, wires).
- Rig (FBX strings): 95 `LimbNode` bones, 148 `Cluster` skin clusters, an Armature, IK-named nodes present. Weighting and IK need Blender to check.
- Preview: `_prev/humanoid_m2000_blend.jpg` (128 px blend thumbnail).
- Seller: sold on CGTrader and Superhive as a rigged and animated character, made in Blender 3.0 with a Cycles light setup, FBX with bones and materials, royalty-free ([CGTrader](https://www.cgtrader.com/3d-models/character/sci-fi-character/humanoid-m2000-rigged-character)).
- Licence: royalty-free per the store page; no licence text shipped.
- Use: candidate Android replacement for #28, or the opponent if scaled up. High-poly (300k triangles), so it needs a decimated or proxy copy for the live layer, and it renders fine in the pre-rendered Clips.

### ANDROID JUNO FEMALE B (`juno_android/`)
- Contents: ANDROID `.blend`/`.fbx`/`.obj`, `env2.jpg` (an HDRI-like panorama), `W logo.jpg`.
- Geometry (OBJ): 104,616 vertices, 206,874 triangles, 43 objects (head, ears, neck wires, body, arm, forearm, hand, 5 fingers each with separate objects, thumb, thigh, shin, foot).
- Rig: the store sells the "B" version rigged with Auto-Rig Pro for Mixamo, Unreal and Unity ([CGTrader](https://www.cgtrader.com/3d-models/character/sci-fi-character/android-juno-female-b-rigged-for-unreal-engine-unity-mixamo), [Superhive](https://superhivemarket.com/products/android-juno-female-b-auto-rig-pro-rigged-for-mixamo-unreal-engineunity)). The FBX string scan found no bone names, so verify the armature in the `.blend` (Blender 3.3).
- Preview: `_prev/juno_android_blend.jpg` (white android with ear pieces, 128 px; the two thumbnails may be swapped in the packs, check in Blender).
- Licence: royalty-free per the store page; no licence text shipped.
- Use: best-looking Android replacement for #28 (finger detail; thumbnail shows a white android with dark joints). Its Auto-Rig Pro rig maps to our channels; if the armature turns out missing, the part objects give a rigid-parts rig.

## Not decided here
- The `.blend` files were not opened. Counts of objects, rig details and Blender-side materials wait for a Blender slot (`robot/build/inspect_asset.py` reads a `.blend` with auto-run off).
- Store pages call M2000, Juno, Arclink and DUNE royalty-free, but the downloads ship no licence text; Luminara depends on its Cargo tier. Check each before a public video.

## More Geo-Scatter biome packs (only the brochures so far)

On 2026-11-17 at 09:32 the user downloaded four PDFs and nothing else. Each PDF is the brochure of a free Geo-Scatter biome pack: a cover, one preview render per biome, a requirements page, the install guide and an info page. Image-only pages, read with `robot/build/review/pdf_pages.swift`; the page renders are in `<pack>/pdf/page_NN.jpg`, the PDFs in `<pack>/_zips/`.

| Pack | Folder | Biomes | Look | Needs |
|---|---|---|---|---|
| Greeble Town BinaryFrame | `binaryframe_biomes/` | Chipset 01 to 08 | a circuit-board megastructure: dark slabs, gold pins and chips, seen from above like a city | the biome archive plus Greeble Town's BinaryFrame kit |
| Greeble Town FutureScratch | `futurescratch_biomes/` | Greeble 01 to 08 | dark industrial greebles: pipes, tanks, vents, cables; closest to the foundry mood | the biome archive plus Greeble Town's FutureScratch kit |
| 3D Shaker Spring Grass | `spring_grass_biomes/` | Grass 01 to 08 | lawn grasses on a terrace | the biome archive plus 3D Shaker's Spring Grass collection |
| Geo-Scatter Plant Library | `plant_library_biomes/` | 31: Lawn 01 to 07, Wild Grass 01 to 04, Forest 01 to 06, Autumn 01 to 04, Wasteland 01 to 06, Rockplain 01 to 04 | vegetation | the biome archive plus the free Plant Library (Blender 3.4 or later) |

- Requirements from every brochure: Geo-Scatter or Biome Reader 5.3.1 or later (we have 5.6.4) and Blender 3.3 LTS or later.
- Missing for every pack: the biome files (`.biome`, `.preset`, `.scatpack` or zip) and the partner models they scatter. Nothing can be placed until those are downloaded, from the same store pages as the brochures.
- Fit for the Robot Scene: FutureScratch (foundry mood) and BinaryFrame (a megastructure under the duel) are arena and backdrop candidates. Wasteland and Rockplain could make an open-air floor. The lawns, grass and forests don't fit a robot duel; offered only.

## Geo-Scatter Biome Reader (`geoscatter/`)

The free Biome Reader from geoscatter.com, downloaded by the user on 2026-11-17 to place the Arclink biomes. The archive is in `_zips/`, the unpacked files in `extracted/`.

- File: `Biome-Reader_5.6.4_for_b3d_5.2.zip` (85 MB, 413 files). It passed `unzip -t` and its size was stable over 30 s. One empty translation stub, `Fran?ais.csv.wip`, did not extract because of its file-name encoding; it has no effect.
- Type: a Blender extension, not a legacy add-on (`blender_manifest.toml`):
  - id `biome_reader`, version 5.6.4, `blender_version_min = "5.2.0"`;
  - this machine's Blender is 5.3.0;
  - permissions `files` and `network`.
- Network: `gpl_script/ui/ui_biome_library.py` fetches scatpack store previews and a version number from `raw.githubusercontent.com/DB3D/scatter-fetch`. It runs on its own after the number of days set in its preferences (`fetch_automatic_daycount`). No other network calls were found.
- Licence (`LICENSES.txt`, `non_gpl/blends/GEOSCATTER_ENGINE_BIOMEREADER_INDIVIDUAL.license`, geoscatter.com/legal):
  - The Python code is GPL-3.0.
  - The Geo-Scatter engine (`non_gpl/blends/engine.blend`) is under the vendor's EULA. It is free to use and render with, but may not be redistributed or modified.
  - Valid only when downloaded from geoscatter.com/download, which is where the user got it.
- Install: needs a Blender slot.
  - Extensions install into `~/Library/Application Support/Blender/5.3/extensions/user_default/biome_reader/` (from Preferences, or `blender --command extension install-file -r user_default --enable <zip>`).
  - Enabling it saves the user preferences.
  - Placing the Arclink biomes also means pointing the Biome Reader's library path at `arclink_biomes/extracted/_biomes_`, one more preference change.

## Mixamo clips (`mixamo/`)

Only the three Mixamo packs, copied from `~/Downloads` into `mixamo/packs/<pack>/extracted/`: Free Test Pack (11 clips), Locomotion Pack (12), Action Adventure Pack (22). The loose FBXs in `~/Downloads` belong to the Godot Colossus Scene (`make godot-models`) and are not used here (user decision of 2026-11-17). `mixamo/fbx_info.jsonl` lists each clip, made with `robot/build/review/fbx_info.py` (reads binary FBX as data, no Blender).

- Every clip uses the Mixamo rig (65 `mixamorig` bones) and carries no mesh.
- Length in beats at 124 BPM (0.484 s per beat), the clips that could become Moves:

| Clip | Pack | Seconds | Beats | Could be |
|---|---|---|---|---|
| back flip to uppercut | Free Test | 5.83 | 12 (3 bars) | a drop Move, the one fight clip |
| hard landing | Action Adventure | 2.0 | 4 | the end of a leap or throw |
| falling to roll | Action Adventure | 1.8 | 3.7 | a dodge |
| jump | Free Test, Locomotion | 2.17 | 4.5 | a dodge over a sweep |
| falling idle | Action Adventure | 0.7 | loop | airborne after a throw |
| running | Locomotion, Action Adventure | 0.7 | loop | a run-up |
| strafes, turns | Free Test, Locomotion | 0.7 to 1.6 | 1 to 3 | circling in guard |
| stand to cover, cover to stand, cover sneaks | Action Adventure | 1.1 to 1.5 | 2 to 3 | hiding behind an arena piece |
| idle, idle (2..5) | all | 2.3 to 10 | | calm Idle Clips |
| samba dancing, gangnam style | Free Test | 23.9, 12.4 | 49, 26 | a dance break |

- Missing for a fight: punches, kicks, blocks, hit reactions, knock-downs. User decision of 2026-11-17: use only these packs. Strikes and blocks stay hand-keyed in our key tables.
- Which character can wear them:
  - Juno: the store sells the "B" version rigged with Auto-Rig Pro for Mixamo, but the downloaded `ANDROID.fbx` has no armature (0 bones, 43 meshes). The rig, if present, is in `ANDROID.blend`; check in Blender.
  - M2000: its own rig (74 bones in the FBX, root `ROOT`), not Mixamo. Clips need a bone map.
  - Today's scripted Android and the Security Bot: no Mixamo rig; retarget only.
- How they fit our Moves: retarget, time-warp the key moments onto beats, bake, and pass the planted-ankle and Key Pose tests. Exchanges still need hand-placed Hits.
