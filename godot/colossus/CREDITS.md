# Credits

## Land

| Asset | Source | License |
|---|---|---|
| `assets/dem/maelifellssandur_295x259_f32le.raw`: Mælifellssandur, 8 x 8 km cropped from tile N63 W020 (columns 1505 to 1799, rows 592 to 850), float32 metres | Copernicus DEM GLO-30, https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N63_00_W020_00_DEM/Copernicus_DSM_COG_10_N63_00_W020_00_DEM.tif | © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved. Free use with this attribution. |
| `assets/terrain/gravelly_sand_*`: Gravelly Sand by Dario Barresi, 1k, packed into Terrain3D channels (albedo + height, normal + roughness) | https://polyhaven.com/a/gravelly_sand | CC0 |
| `assets/terrain/rocky_terrain_02_*`: Rocky Terrain 02 by Amal Kumar, 1k, packed the same way | https://polyhaven.com/a/rocky_terrain_02 | CC0 |

## Characters

| Asset | Source | License |
|---|---|---|
| `assets/models/nomad/`: the Wanderer, from "Nomad Marksman Rig" by DM-913 (https://sketchfab.com/SuperKapoo913); rifle removed, skeleton cut to 53 bones and renamed, scaled, made with `tools/godot_prepare_models.py` | https://sketchfab.com/3d-models/nomad-marksman-rig-aa3d08c56cc84d308e36920d3bcbe122 | CC-BY 4.0, http://creativecommons.org/licenses/by/4.0/ |
| `assets/models/grock/`: Colossus 1, from "Grock - Endboss" by Baue Franco (https://sketchfab.com/BaueFranco); deform bones only, metallic and flat normal map dropped, normal map made from its height map, made with `tools/godot_prepare_models.py` | https://sketchfab.com/3d-models/grock-endboss-fc582e5f47da447d934d616ad271a3fe | CC-BY 4.0, http://creativecommons.org/licenses/by/4.0/ |

## Addons

| Addon | Source | License |
|---|---|---|
| `addons/terrain_3d` | Terrain3D 1.1.0, https://github.com/TokisanGames/Terrain3D | MIT (`addons/terrain_3d/LICENSE.txt`) |
| `addons/godot-syphon` | godot-syphon 1.0.1, https://github.com/buresu/godot-syphon | MIT (`addons/godot-syphon/LICENSE`) |
| `addons/godot-syphon/bin/Syphon.framework` | Syphon Framework, https://github.com/Syphon/Syphon-Framework | BSD-style (`addons/godot-syphon/bin/Syphon.framework.LICENSE`) |
| `addons/godot_mcp` | @satelliteoflove/godot-mcp 4.1.11, https://github.com/satelliteoflove/godot-mcp | MIT (`addons/godot_mcp/LICENSE`) |

## Agent skills

| Skill | Source | Commit | License |
|---|---|---|---|
| `scenario` in `.claude/skills/scenario/` | https://github.com/scenario-labs/skills/tree/5a7460b0b66399e44652ef13eab09f6f8a1976a7/skills/scenario (release `skills-v0.60.1`) | `5a7460b0b66399e44652ef13eab09f6f8a1976a7` | MIT, Scenario Inc. (`.claude/skills/scenario/LICENSE`) |
