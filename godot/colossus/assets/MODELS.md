# Models

No model file is in git: not the downloads, not what the prepare makes of them, not their `.import` files. They live in git-ignored folders:

| Folder | Holds |
|---|---|
| `assets/incoming/` | the source archives, unpacked by `make godot-models` |
| `assets/models/` | what the scene loads: glTF, `.bin`, textures, their `.import` settings |
| `assets/mixamo/` | Mixamo clips |

Without them the scene still runs: each missing model's stand-in takes its place, and the start prints one line naming what is missing. Tests need no model.

## Rebuild

1. Download the archives below into `~/Downloads` with a Sketchfab login (file names as they arrive).
2. From the repository root:

```bash
make godot-models
```

It unpacks each source archive into its own new folder under `assets/incoming/`, runs `tools/godot_prepare_models.py` in headless Blender on the source `.blend` (scripts off), imports the project, writes the import settings (`tools/godot_model_import.py`: VRAM-compressed textures with mipmaps, normal maps flagged, Grock scaled to 28 m) and imports again. `DOWNLOADS=<dir>` takes the archives from elsewhere. What the prepare does to each model: [docs/reports/godot-model-cost.md](../../../docs/reports/godot-model-cost.md#how-the-models-are-prepared).

## Sketchfab models

| Model | Role | Author | Licence | Page | Downloads (`~/Downloads`) | As downloaded | Used |
|---|---|---|---|---|---|---|---|
| Nomad Marksman Rig | Wanderer | DM-913 | CC-BY 4.0 | https://sketchfab.com/3d-models/nomad-marksman-rig-aa3d08c56cc84d308e36920d3bcbe122 | glTF: `nomad_marksman_rig.zip`; source: `nomad-marksman-rig.zip` (`source/Hunter106.blend`) | 50,012 tris (with rifle), 89 joints, no clips | source `.blend` |
| Grock - Endboss | Colossus 1 | Baue Franco | CC-BY 4.0 | https://sketchfab.com/3d-models/grock-endboss-fc582e5f47da447d934d616ad271a3fe | glTF: `grock_-_endboss.zip`; source: `grock-endboss.zip` (`source/master.blend`) | 48,675 tris, 22 joints, 8 clips (Attack1 to 3, Defend1 to 3, Idle1, idle2) | source `.blend` |
| Ancient Titan Vol2 | Colossus 2 (not prepared yet) | Kaan Tezcan | CC-BY 4.0 (credit waived) | https://sketchfab.com/3d-models/free-game-character-ancient-titan-vol2-0e71dd1a27a2455b9adae83082905958 | glTF: `free_game_character_-_ancient_titan_vol2.zip` (248 MB); source: `free-game-character-ancient-titan-vol2.zip` (424 MB, `source/Titan.fbx`) | 56,160 tris, 302 joints, no clips, 15 textures | none yet |
| Golem Rock | Colossus 3 (not prepared yet) | Oscar Creativo | CC-BY label, "All rights reserved" in the text: not used until the author confirms CC-BY | https://sketchfab.com/3d-models/character-free-golem-rock-by-oscar-creativo-9383d3630e2945c5bdac5f7063308037 | glTF: `character_free_golem_rock_by_oscar_creativo.zip` (668 MB); source: `character-free-golem-rock-by-oscar-creativo.zip` (680 MB) | 83,982 tris, 90 joints, 1 clip ("Motion"), 59 textures | none yet |

Only the source archive of the Nomad and of Grock is read; their glTF archives are not needed. `CREDITS.md` names every CC-BY model the scene uses.

## Mixamo clips

Site: https://www.mixamo.com/ (Adobe login; no redistribution, so `assets/mixamo/` is git-ignored).

Export settings for every clip: Format FBX Binary, Skin "Without Skin", Frames per Second 30, Keyframe Reduction none. Walk and run with "In Place" ticked.

The Wanderer's animation slots look for these files in `assets/mixamo/`; a slot without its file falls back (stage 2 of `docs/handover/godot-models.md` says to what):

| Slot | File in `assets/mixamo/` | Mixamo clip to search for | In `~/Downloads` on 2026-11-11 |
|---|---|---|---|
| idle | `idle.fbx` | Idle | `Idle.fbx`, `Idle-2.fbx`, `Idle-3.fbx` |
| walk | `walk.fbx` | Walking (In Place) | `Walking.fbx`, `Walking-2.fbx` |
| run | `run.fbx` | Running (In Place) | no |
| hang idle | `hang_idle.fbx` | Braced Hang | no |
| shimmy left | `shimmy_left.fbx` | Braced Hang Shimmy (left) | no |
| shimmy right | `shimmy_right.fbx` | Braced Hang Shimmy (right) | no |
| climb up | `climb_up.fbx` | Climbing Up Wall | no |
| climb down | `climb_down.fbx` | Climbing Down Wall | no |
| hang swing | `hang_swing.fbx` | Hanging Idle (free hang, swinging) | no |
| fall idle | `fall_idle.fbx` | Falling Idle | no |
| stand up | `stand_up.fbx` | Standing Up | no |

Also in `~/Downloads`, not mapped to a slot: `Kneeling Idle.fbx`, `Sneak Walk.fbx`, `Walk In Circle.fbx`.
