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

## How the models are prepared

```bash
make godot-models
```

Unpacks `nomad-marksman-rig.zip` and `grock-endboss.zip` from `DOWNLOADS` (default `~/Downloads`) into new, empty, git-ignored folders under `godot/colossus/assets/incoming/`, runs `tools/godot_prepare_models.py` in headless Blender on each source `.blend` (scripts off) and re-imports the project. Out: `godot/colossus/assets/models/nomad/nomad.gltf` and `godot/colossus/assets/models/grock/grock.gltf` with `.bin` and `textures/`, 44 MB together, committed.

- Source: the `.blend` files, not Sketchfab's glTF. Grock's glTF splits the body into two meshes and carries a flat 4 KB normal map; the `.blend` has one mesh. The Nomad's `.blend` has the cleaner bone list (the glTF adds bone-shape meshes as nodes).
- Nomad: rifle, lights, bone-shape meshes removed; skeleton as above, renamed to Godot's humanoid profile (`Root`, `Hips`, `Spine`, `Chest`, `Neck`, `Head`, `LeftShoulder` ... `RightFoot`, fingers `LeftIndexProximal` ...; `Scarf1` to `Scarf3` keep their names); scaled to 1.75 m, feet at 0, hips over the origin. The attire keeps alpha (5% of its triangles sample alpha below 0.5: the frayed cloth), alpha scissor, two-sided; the body is one-sided. Textures stay 2k.
- Grock: deform bones only (17; the four IK bones are baked into the clips), all eight clips (Attack1 to 3, Defend1 to 3, Idle1, idle2). The metallic map is black everywhere and the normal map flat: both go, metallic 0. A normal map is made from the author's height map, scaled so the median surface tilts 12° (read at the material's own scale the height map tilts half the surface past 50°). Roughness stays. One-sided. Exported at the model's size (2.00 units, feet at 0.011); the import scales it to 28 m (`nodes/root_scale=14.0339`, clips and rest scale with it).
- The `.bin` of the Nomad is not byte-identical between two runs of the prepare (the texture PNGs and Grock are); the content is.

## Not in this session: Colossus 2 and 3

- Titan (`free-game-character-ancient-titan-vol2.zip`, 424 MB; the Sketchfab glTF 248 MB): 56k tris, one skin with 302 joints, no clips, 15 textures. Needs: a skeleton cut to the bones the Grab Path, foot IK and ragdoll use (about 20, the rest merged as for the Nomad), textures down to 4k albedo and normal and 2k for the rest, unused maps dropped. The rigged file behind the link on the Sketchfab page was not available; the glTF skin is what there is.
- Golem (`character_free_golem_rock_by_oscar_creativo.zip`, 668 MB): 84k tris, 90 joints, one clip "Motion", 59 textures. Needs the same plus a texture merge (59 maps suggest many materials: one draw call each). Stays out of git until its author confirms the CC-BY license (`docs/GUIDELINES.md`).
