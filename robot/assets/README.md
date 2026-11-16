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
- Licence: KitBash3D kit licence (the pack ships no licence text, only a readme). Commercial use in finished work is the normal KitBash3D terms; not redistributable. Credit not stated. Check the account terms before publishing a video.
- Use: arena and backdrop. Clean white and gray panels with emissive trim fit the Chrome Foundry steel look; the emissive colors can carry beat flashes. The 3.8 GB file is heavy: append only the needed objects, never open it whole in the live scene.

### Neo City (`neocity/`)
- Contents: 1 `.blend`, 384 PNG (62 materials: galvanized steel, brass, painted metal, grating, neon lights, banners, letters, tinted glass, street tiles, asphalt), readme.
- Preview: swatch sheet only.
- Licence: KitBash3D, as above.
- Use: street-level backdrop (neon signs and glass give sodium and color light). Warmer and dirtier than Minerva, closer to a back-alley fight. Light enough to open (241 MB).

### Luminara (`luminara/`)
- Contents: 428 PNG (69 materials: ancient brickwork, boulders, crystals, airship and boat atlases, canvas, rusted metal), no `.blend` yet.
- Preview: swatch sheet only.
- Licence: KitBash3D, as above.
- Use: not usable until the `.blend` is downloaded. Fits a ruin or crystal-cavern arena, not the foundry look. Textures only; unused for now.

### Arclink City Megapolis (`arclink_megapolis/`)
- Contents: 1 `.blend` (asset-browser library), `blender_assets.cats.txt`, 354 PNG in `textures/1K`, `2K`, `4K` (PBR with Emission, Alpha, Displacement). Catalog: GT_AL Bright and GT_AL Dark, each with Greebles, Large, Mid and Small Buildings, and Misc (Entrances, Ground Misc, Passageway, Road). Object counts need Blender.
- Preview: swatch sheet (grayscale panels); the real city look is in the biome renders below.
- Licence: Greeble Town "Commercial License" (readme text in `arclink_biomes/_zips/6fe73a6f...txt`). Geo-Scatter geometry nodes have their own terms (geoscatter.com/legal). Credit not stated.
- Use: the Live World backdrop, a dark megacity behind both fighters, with the Dark set for the foundry mood. Instancing the greebles also adds detail scale cues for the giant machine's body.

### Arclink biomes (`arclink_biomes/`)
- Contents: 8 biomes (`arclink_city_1..8`, each `.biome` plus 3 or 4 `.preset` layers) and 8 preview JPG (350 px), the PDF manual (`_zips/`), readme.
- Preview: `_prev/biome_1..8.jpg`: real renders. 1 is a dark blue-lit city, 5 a gray city with green light lines.
- Use: needs the Geo-Scatter addon (a free Biome Reader exists, per the readme). That runs inside Blender, so it only works in a Blender build step. It can fill a wide city around the arena in few steps.

### DUNE (`dune/`)
- Contents: 10 `.blend`, 11 PNG icons, `DUNE.zip` (kpack: `DUNE.blend`, `DUNE.png`), install note (KitOps dPack/kPack for SCI-FI FLEX).
- Preview: `_prev/dune_*.jpg` (256 px icons: orange dune, mountain on sand).
- Licence: none shipped; unknown. Ask or check the seller's page before video use.
- Use: an alternative open-air arena, desert floor with dust haze, for a scene idea that leaves the foundry. Light files except the dunes at 168 MB.

### HUMANOID M2000 (`humanoid_m2000/`)
- Contents: DROID `.blend`/`.fbx`/`.obj`, 2 JPG (a logo and a Warsaw panorama; the panorama is stock-looking, so not to be shipped).
- Geometry (OBJ): 151,558 vertices, 302,164 triangles, 20 objects (head, neck, chest, waist, hip, arm, forearm, hands, thigh, shin, foot, wires).
- Rig (FBX strings): 95 `LimbNode` bones, 148 `Cluster` skin clusters, an Armature, IK-named nodes present. Weighting and IK need Blender to check.
- Preview: `_prev/humanoid_m2000_blend.jpg` (128 px blend thumbnail).
- Licence: none shipped; unknown.
- Use: candidate Android replacement for #28, or the opponent if scaled up. High-poly (300k triangles), so it needs a decimated or proxy copy for the live layer, and it renders fine in the pre-rendered Clips.

### ANDROID JUNO FEMALE B (`juno_android/`)
- Contents: ANDROID `.blend`/`.fbx`/`.obj`, `env2.jpg` (an HDRI-like panorama), `W logo.jpg`.
- Geometry (OBJ): 104,616 vertices, 206,874 triangles, 43 objects (head, ears, neck wires, body, arm, forearm, hand, 5 fingers each with separate objects, thumb, thigh, shin, foot).
- Rig: not readable from the FBX text (zero bone names found); the `.blend` (Blender 3.3) must be inspected. Treat as unrigged until proven otherwise.
- Preview: `_prev/juno_android_blend.jpg` (white android with ear pieces, 128 px; the two thumbnails may be swapped in the packs, check in Blender).
- Licence: none shipped; unknown.
- Use: best-looking Android replacement for #28 (finger detail; thumbnail shows a white android with dark joints). If it has no rig, the part objects give a rigid-parts rig (parent each part to a bone) that suits our key-table Moves.

## Not decided here
- The `.blend` files were not opened. Counts of objects, rig details and Blender-side materials wait for a Blender slot (`robot/build/inspect_asset.py` reads a `.blend` with auto-run off).
- Video use and credit for DUNE, HUMANOID and JUNO are unknown.
