class_name Dust
extends Node3D
## Dust thrown up by footfalls and by the Fall: a small pool of one-shot particle bursts.

const POOL := 6
const COLOR := Color("8a8478")

var _emitters: Array[GPUParticles3D] = []
var _next := 0


func _ready() -> void:
	var draw := QuadMesh.new()
	draw.size = Vector2.ONE
	var mat := StandardMaterial3D.new()
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	mat.vertex_color_use_as_albedo = true
	mat.albedo_texture = _soft_disc()
	mat.roughness = 1.0
	mat.disable_receive_shadows = true
	draw.material = mat
	for i in POOL:
		var p := GPUParticles3D.new()
		p.one_shot = true
		p.emitting = false
		p.amount = 48
		p.lifetime = 6.0
		p.explosiveness = 0.9
		p.visibility_aabb = AABB(Vector3(-80, -5, -80), Vector3(160, 60, 160))
		p.draw_pass_1 = draw
		p.process_material = _process_material()
		add_child(p)
		_emitters.append(p)


## Throw dust at `at`; `size` is the cloud radius in metres.
func puff(at: Vector3, size: float) -> void:
	var p := _emitters[_next]
	_next = (_next + 1) % POOL
	var m := p.process_material as ParticleProcessMaterial
	m.emission_sphere_radius = size * 0.5
	m.initial_velocity_min = size * 0.15
	m.initial_velocity_max = size * 0.4
	m.scale_min = size * 0.6
	m.scale_max = size * 1.2
	p.global_position = at
	p.restart()


func _process_material() -> ParticleProcessMaterial:
	var m := ParticleProcessMaterial.new()
	m.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	m.direction = Vector3.UP
	m.spread = 80.0
	m.gravity = Vector3(0.0, 0.3, 0.0)
	m.damping_min = 1.5
	m.damping_max = 3.0
	var grow := Curve.new()
	grow.add_point(Vector2(0.0, 0.3))
	grow.add_point(Vector2(1.0, 1.0))
	var scale_tex := CurveTexture.new()
	scale_tex.curve = grow
	m.scale_curve = scale_tex
	var fade := Gradient.new()
	fade.set_color(0, Color(COLOR, 0.0))
	fade.set_color(1, Color(COLOR, 0.0))
	fade.add_point(0.12, Color(COLOR, 0.55))
	fade.add_point(0.5, Color(COLOR, 0.3))
	var ramp := GradientTexture1D.new()
	ramp.gradient = fade
	m.color_ramp = ramp
	return m


static func _soft_disc() -> GradientTexture2D:
	var g := Gradient.new()
	g.set_color(0, Color(1, 1, 1, 1))
	g.set_color(1, Color(1, 1, 1, 0))
	var t := GradientTexture2D.new()
	t.gradient = g
	t.fill = GradientTexture2D.FILL_RADIAL
	t.fill_from = Vector2(0.5, 0.5)
	t.fill_to = Vector2(1.0, 0.5)
	t.width = 128
	t.height = 128
	return t
