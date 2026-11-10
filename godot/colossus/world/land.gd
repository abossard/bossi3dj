class_name Land
extends Node3D
## Mælifellssandur in the Fjallabak highlands: 8 x 8 km of Copernicus GLO-30 (tile N63 W020)
## in Terrain3D. A black sand plain where the Colossus roams, the Shrine on the glacier foot
## to the south, low ridges to the north. Beyond the edge the plain runs on, flat.

const DEM := "res://assets/dem/maelifellssandur_295x259_f32le.raw"
const DEM_SIZE := Vector2i(295, 259)
const SIZE_M := 8000.0
const SPACING := 2.0
## DEM height of the plain; it becomes y = 0.
const PLAIN_ELEVATION := 621.0
## Relief exaggeration, so the ridges read as silhouettes through the fog.
const RELIEF := 1.5
## Where the Colossus roams, and the Shrine 850 m beyond its edge.
const ARENA := Vector3(14.0, 0.0, 15.0)
const ROAM_RADIUS := 600.0
const SHRINE := Vector3(14.0, 0.0, 1467.0)
const SAND := "res://assets/terrain/gravelly_sand"
const ROCK := "res://assets/terrain/rocky_terrain_02"
const SAND_TINT := Color("4a4744")

var terrain: Terrain3D


func _ready() -> void:
	terrain = Terrain3D.new()
	terrain.vertex_spacing = SPACING
	terrain.free_editor_textures = false
	terrain.assets = _assets()
	add_child(terrain)
	var m := terrain.material
	m.world_background = Terrain3DMaterial.FLAT
	m.auto_shader_enabled = true
	m.set_shader_param("auto_slope", 1.2)
	m.set_shader_param("auto_base_texture", 0)
	m.set_shader_param("auto_overlay_texture", 1)
	m.show_checkered = false
	var height := Image.create_from_data(
		DEM_SIZE.x, DEM_SIZE.y, false, Image.FORMAT_RF, FileAccess.get_file_as_bytes(DEM)
	)
	var px := int(SIZE_M / SPACING)
	height.resize(px, px, Image.INTERPOLATE_CUBIC)
	var maps: Array[Image] = [height, null, null]
	terrain.data.import_images(
		maps, Vector3(-SIZE_M * 0.5, 0.0, -SIZE_M * 0.5), -PLAIN_ELEVATION * RELIEF, RELIEF
	)
	# Full collision (the Colossus falls anywhere). Setting the mode builds it from the heights.
	terrain.collision_mode = Terrain3DCollision.FULL_GAME


## Ground height at x, z; the flat background (0) outside the DEM.
func height_at(x: float, z: float) -> float:
	var h := terrain.data.get_height(Vector3(x, 0.0, z))
	return 0.0 if is_nan(h) else h


func _assets() -> Terrain3DAssets:
	var assets := Terrain3DAssets.new()
	for spec: Array in [[SAND, SAND_TINT, 0.05], [ROCK, Color("6b6660"), 0.03]]:
		var t := Terrain3DTextureAsset.new()
		t.albedo_texture = load(spec[0] + "_albedo_height.png")
		t.normal_texture = load(spec[0] + "_normal_rough.png")
		t.albedo_color = spec[1]
		t.uv_scale = spec[2]
		assets.set_texture_asset(assets.get_texture_count(), t)
	return assets
