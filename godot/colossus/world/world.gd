class_name World
extends Node3D
## Sky, overcast dusk light, fog, the land and placeholder ruins.

const SUN_ELEVATION_DEG := 4.0
const SUN_COLOR := Color("e8c890")
const STONE := Color("262d35")
var environment: Environment
var sun: DirectionalLight3D
var land: Land


func _ready() -> void:
	_build_environment()
	_build_sun()
	land = Land.new()
	add_child(land)
	_build_shrine()
	_build_ruins()


func height_at(x: float, z: float) -> float:
	return land.height_at(x, z)


## Music drives the light and the fog; the arguments are scene values (VjMap.scene_value):
## sun energy, volumetric fog density, fog height in metres, distance haze density, exposure.
## Writes only values that moved, so a steady signal leaves the sky's radiance converged.
func apply_look(
	sun_energy: float, fog_density: float, fog_height_m: float, haze_density: float, exposure: float
) -> void:
	if _moved(sun.light_energy, sun_energy):
		sun.light_energy = sun_energy
	if _moved(environment.volumetric_fog_density, fog_density):
		environment.volumetric_fog_density = fog_density
	if _moved(environment.fog_height, fog_height_m):
		environment.fog_height = fog_height_m
	if _moved(environment.fog_density, haze_density):
		environment.fog_density = haze_density
	if _moved(environment.tonemap_exposure, exposure):
		environment.tonemap_exposure = exposure


static func _moved(current: float, wanted: float) -> bool:
	return absf(current - wanted) > absf(wanted) * 0.01


func _build_environment() -> void:
	var sky_mat := ProceduralSkyMaterial.new()
	sky_mat.sky_top_color = Color("3a424b")
	sky_mat.sky_horizon_color = Color("8f8d86")
	sky_mat.sky_curve = 0.12
	sky_mat.ground_horizon_color = Color("6a6a64")
	sky_mat.ground_bottom_color = Color("15171a")
	sky_mat.sun_angle_max = 18.0
	sky_mat.sky_energy_multiplier = 1.0
	var sky := Sky.new()
	sky.sky_material = sky_mat
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 0.6
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = 1.0
	env.sdfgi_enabled = true
	env.ssao_enabled = true
	env.ssil_enabled = true
	env.glow_enabled = true
	env.glow_hdr_threshold = 1.6
	env.glow_intensity = 0.6
	env.fog_enabled = true
	env.fog_light_color = Color("7d838a")
	env.fog_sun_scatter = 0.2
	env.fog_density = 0.00025
	# Low, so a far Colossus stays a dark shape against the bright sky instead of taking its colour.
	env.fog_aerial_perspective = 0.12
	env.fog_sky_affect = 0.55
	env.fog_height = 40.0
	env.fog_height_density = 0.006
	env.volumetric_fog_enabled = true
	env.volumetric_fog_density = 0.003
	env.volumetric_fog_albedo = Color("8c9196")
	env.volumetric_fog_anisotropy = 0.6
	env.volumetric_fog_length = 250.0
	env.volumetric_fog_ambient_inject = 0.3
	env.adjustment_enabled = true
	env.adjustment_saturation = 0.75
	env.adjustment_contrast = 1.2
	environment = env
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)


func _build_sun() -> void:
	# Light travels toward +Z: the sun sits beyond the Colossus as seen from the Shrine.
	sun = DirectionalLight3D.new()
	sun.rotation = Vector3(deg_to_rad(-SUN_ELEVATION_DEG), PI, 0.0)
	sun.light_color = SUN_COLOR
	sun.light_energy = 1.8
	sun.light_volumetric_fog_energy = 2.0
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 600.0
	add_child(sun)


func _stone() -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = STONE
	m.roughness = 0.95
	return m


func _build_shrine() -> void:
	var base := Land.SHRINE
	base.y = height_at(base.x, base.z)
	var mat := _stone()
	var slab := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = Vector3(30.0, 1.2, 30.0)
	slab.mesh = box
	slab.material_override = mat
	slab.position = base + Vector3(0.0, 0.3, 0.0)
	add_child(slab)
	var rng := RandomNumberGenerator.new()
	rng.seed = 3
	for i in 8:
		var a := TAU * i / 8.0
		var h := rng.randf_range(10.0, 14.0) * (0.45 if i % 3 == 1 else 1.0)
		var col := MeshInstance3D.new()
		var cyl := CylinderMesh.new()
		cyl.top_radius = 0.65
		cyl.bottom_radius = 0.75
		cyl.height = h
		col.mesh = cyl
		col.material_override = mat
		var at := base + Vector3(cos(a) * 11.0, 0.0, sin(a) * 11.0)
		col.position = Vector3(at.x, minf(height_at(at.x, at.z), base.y) + h * 0.5 + 0.6, at.z)
		add_child(col)


func _build_ruins() -> void:
	# Toppled statue fragment stand-in: a half-buried giant head in the plain.
	var head := MeshInstance3D.new()
	var s := SphereMesh.new()
	s.radius = 9.0
	s.height = 16.0
	head.mesh = s
	head.material_override = _stone()
	var at := Land.ARENA + Vector3(-420.0, 0.0, 380.0)
	head.position = Vector3(at.x, height_at(at.x, at.z) + 3.0, at.z)
	head.rotation = Vector3(0.4, 0.8, 1.1)
	add_child(head)
