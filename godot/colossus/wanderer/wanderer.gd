class_name Wanderer
extends CharacterBody3D
## The small figure. Walks on the ground, climbs the Grab Path, hangs and swings during a Shake.

enum State { GROUND, REACHING, HANGING, MOVING }

const WALK := 1.6
const RUN := 4.5
const HANG_LENGTH := 1.1
const REACH := 4.0
const CLIMB_SPEED := 1.4
const CLOTH := Color("8f8a80")

var colossus: Colossus
var height_at: Callable = func(_x: float, _z: float) -> float: return 0.0
## World-space direction set by the brain or by Takeover.
var wish := Vector3.ZERO
var running := false
var state: State = State.GROUND
var grip: GrabPoint

var _from: GrabPoint
var _t := 0.0
var _len := 1.0
var _swing := Vector2.ZERO
var _reach_from := Vector3.ZERO


func _ready() -> void:
	# After the Colossus has moved its Grab Points this tick, so the body never trails its grip.
	process_physics_priority = 1
	var mat := StandardMaterial3D.new()
	mat.albedo_color = CLOTH
	mat.roughness = 1.0
	var body := MeshInstance3D.new()
	var cap := CapsuleMesh.new()
	cap.radius = 0.22
	cap.height = 1.5
	body.mesh = cap
	body.position.y = 0.75
	body.material_override = mat
	add_child(body)
	var head := MeshInstance3D.new()
	var s := SphereMesh.new()
	s.radius = 0.12
	s.height = 0.24
	head.mesh = s
	head.position.y = 1.62
	head.material_override = mat
	add_child(head)
	var cape := MeshInstance3D.new()
	var prism := PrismMesh.new()
	prism.size = Vector3(0.7, 1.2, 0.08)
	cape.mesh = prism
	cape.position = Vector3(0.0, 0.85, 0.2)
	cape.material_override = mat
	add_child(cape)
	var col := CollisionShape3D.new()
	var shape := CapsuleShape3D.new()
	shape.radius = 0.25
	shape.height = 1.75
	col.shape = shape
	col.position.y = 0.875
	add_child(col)


func on_colossus() -> bool:
	return state != State.GROUND


func _physics_process(delta: float) -> void:
	match state:
		State.GROUND:
			_ground(delta)
		State.REACHING:
			_t = minf(_t + delta / 0.45, 1.0)
			global_position = _reach_from.lerp(_hang_pos(grip), smoothstep(0.0, 1.0, _t))
			if _t >= 1.0:
				state = State.HANGING
				_swing = Vector2.ZERO
		State.HANGING:
			_hang(delta)
		State.MOVING:
			_swing = GrabPath.swing(_swing.x, _swing.y, HANG_LENGTH, delta)
			_t = minf(_t + delta * CLIMB_SPEED / _len, 1.0)
			global_position = _hang_pos(_from).lerp(_hang_pos(grip), smoothstep(0.0, 1.0, _t))
			_face(grip)
			if _t >= 1.0:
				state = State.HANGING


func nearest_grip(max_dist: float) -> GrabPoint:
	if colossus == null:
		return null
	var hand := global_position + Vector3.UP * 1.9
	var best: GrabPoint = null
	var best_d := max_dist
	for p in colossus.grab_points():
		var d := hand.distance_to(p.global_position)
		if d < best_d:
			best_d = d
			best = p
	return best


func grab(p: GrabPoint) -> void:
	if p == null or state != State.GROUND:
		return
	grip = p
	state = State.REACHING
	_reach_from = global_position
	_t = 0.0


func let_go() -> void:
	state = State.GROUND
	grip = null
	velocity = Vector3.ZERO
	rotation = Vector3(0.0, rotation.y, 0.0)
	var ground := height_at.call(global_position.x, global_position.z) as float
	if global_position.y < ground + 0.05 or global_position.y > ground + 6.0:
		global_position.y = ground + 0.05


func place_at(at: Vector3) -> void:
	let_go()
	global_position = Vector3(at.x, height_at.call(at.x, at.z) + 0.05, at.z)


func on_shaken(strength: float) -> void:
	if state == State.HANGING or state == State.MOVING:
		_swing.y += strength * 2.2


func _ground(delta: float) -> void:
	var flat := Vector3(wish.x, 0.0, wish.z).limit_length(1.0)
	var v := flat * (RUN if running else WALK)
	velocity.x = v.x
	velocity.z = v.z
	velocity.y = -0.5 if is_on_floor() else velocity.y - 9.81 * delta
	move_and_slide()
	var ground := height_at.call(global_position.x, global_position.z) as float
	if global_position.y < ground - 0.5:
		global_position.y = ground + 0.05
		velocity.y = 0.0
	if flat.length() > 0.1:
		rotation.y = lerp_angle(rotation.y, atan2(-flat.x, -flat.z), 1.0 - exp(-delta * 8.0))


func _hang(delta: float) -> void:
	_swing = GrabPath.swing(_swing.x, _swing.y, HANG_LENGTH, delta)
	global_position = _hang_pos(grip)
	_face(grip)
	if wish.length() < 0.2:
		return
	var others := grip.linked()
	var spots: Array[Vector3] = []
	for o in others:
		spots.append(o.global_position)
	var i := GrabPath.choose_link(grip.global_position, grip.normal(), spots, wish)
	if i < 0:
		return
	_from = grip
	grip = others[i]
	_len = maxf(_from.global_position.distance_to(grip.global_position), 0.5)
	_t = 0.0
	state = State.MOVING


## Where the body sits for a grip: hanging below it on walls, standing on it on top surfaces,
## blended by how much the surface faces up so a tilting body never makes the Wanderer jump.
## The Shake swing moves him sideways along the surface, never into it.
func _hang_pos(p: GrabPoint) -> Vector3:
	var n := p.normal()
	var stand := smoothstep(0.5, 0.9, n.dot(Vector3.UP))
	var side := p.global_transform.basis.x.normalized()
	var standing := p.global_position + side * sin(_swing.x) * 0.6
	var hanging := (
		p.global_position
		+ n * 0.3
		+ (Vector3.DOWN * HANG_LENGTH).rotated(n, _swing.x)
		- Vector3.UP * 0.6
	)
	return hanging.lerp(standing, stand)


func _face(p: GrabPoint) -> void:
	var n := p.normal()
	var flat := Vector3(-n.x, 0.0, -n.z)
	if flat.length() > 0.1:
		rotation = Vector3(0.0, atan2(-flat.x, -flat.z), 0.0)
