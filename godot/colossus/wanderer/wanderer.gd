class_name Wanderer
extends CharacterBody3D
## The small figure. Walks on the ground, climbs the Grab Path, hangs and swings during a Shake.

enum State { GROUND, REACHING, HANGING, MOVING }

const WALK := 1.6
const RUN := 4.5
const HANG_LENGTH := 1.1
const REACH := 4.0
const CLIMB_SPEED := 1.4
## Time constant of the turn toward a grip's surface (s).
const FACE_SECONDS := 0.15
## Off the floor this long counts as falling (a step off a slope's edge does not).
const AIR_SECONDS := 0.15
const CLOTH := Color("8f8a80")
## The prepared Nomad (not in git, see assets/MODELS.md); the stand-in takes its place without it.
const MODEL := "res://assets/models/nomad/nomad.gltf"

var colossus: Colossus
var height_at: Callable = func(_x: float, _z: float) -> float: return 0.0
## World-space direction set by the brain or by Takeover.
var wish := Vector3.ZERO
var running := false
var state: State = State.GROUND
var grip: GrabPoint
## The Nomad, posed by clips and IK; null when its model is missing (the stand-in shows).
var body: WandererBody
## False builds the stand-in even with the model present (cost probes compare the two).
var use_model := true

var _from: GrabPoint
var _t := 0.0
var _len := 1.0
var _swing := Vector2.ZERO
var _reach_from := Vector3.ZERO
var _air_t := 0.0
var _yaw_rate := 0.0


func _ready() -> void:
	# After the Colossus has moved its Grab Points this tick, so the body never trails its grip.
	process_physics_priority = 1
	if use_model and model_present():
		body = WandererBody.new()
		body.height_at = height_at
		add_child(body)
	else:
		_build_stand_in()
	var col := CollisionShape3D.new()
	var shape := CapsuleShape3D.new()
	shape.radius = 0.25
	shape.height = 1.75
	col.shape = shape
	col.position.y = 0.875
	add_child(col)


func _build_stand_in() -> void:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = CLOTH
	mat.roughness = 1.0
	var torso := MeshInstance3D.new()
	var cap := CapsuleMesh.new()
	cap.radius = 0.22
	cap.height = 1.5
	torso.mesh = cap
	torso.position.y = 0.75
	torso.material_override = mat
	add_child(torso)
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


static func model_present() -> bool:
	return ResourceLoader.exists(MODEL)


## Head, hands and hips in the world (the stand-in's: head 1.6 m up, hands at the grip or 1.0 m,
## hips 0.9 m).
func upper_body() -> PackedVector3Array:
	if body:
		return body.upper_body()
	var up := global_transform.basis.y
	var hands := grip.global_position if grip else global_position + up * 1.0
	return PackedVector3Array([global_position + up * 1.6, hands, global_position + up * 0.9])


func on_colossus() -> bool:
	return state != State.GROUND


func _physics_process(delta: float) -> void:
	match state:
		State.GROUND:
			_ground(delta)
		State.REACHING:
			_t = minf(_t + delta / 0.45, 1.0)
			global_position = _reach_from.lerp(_hang_pos(grip), smoothstep(0.0, 1.0, _t))
			_face(grip, delta)
			if _t >= 1.0:
				state = State.HANGING
				_swing = Vector2.ZERO
		State.HANGING:
			_hang(delta)
		State.MOVING:
			_swing = GrabPath.swing(_swing.x, _swing.y, HANG_LENGTH, delta)
			_t = minf(_t + delta * CLIMB_SPEED / _len, 1.0)
			global_position = _hang_pos(_from).lerp(_hang_pos(grip), smoothstep(0.0, 1.0, _t))
			_face(grip, delta)
			if _t >= 1.0:
				state = State.HANGING
	if body:
		_drive_body(delta)


func _drive_body(delta: float) -> void:
	var look := global_position + -global_transform.basis.z * 10.0 + Vector3.UP * 1.6
	if colossus:
		var head := colossus.head_point()
		look = head.global_position if head else colossus.center()
	_air_t = _air_t + delta if state == State.GROUND and not is_on_floor() else 0.0
	var airborne := _air_t > AIR_SECONDS
	var speed := Vector2(velocity.x, velocity.z).length() if state == State.GROUND else 0.0
	var t := _t if state != State.HANGING else 1.0
	body.drive(state, speed, airborne, _from, grip, t, look, delta)


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
	_from = p
	state = State.REACHING
	_reach_from = global_position
	_t = 0.0


func let_go() -> void:
	if body and state != State.GROUND:
		body.landed()
	state = State.GROUND
	grip = null
	_from = null
	_yaw_rate = 0.0
	velocity = Vector3.ZERO
	rotation = Vector3(0.0, rotation.y, 0.0)
	# From up on the body he drops under gravity (and lands, then stands up): a snap to the
	# ground would be a jump of metres in one frame.
	var ground := height_at.call(global_position.x, global_position.z) as float
	if global_position.y < ground + 0.05:
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
	_face(grip, delta)
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
		+ n * _hang_out()
		+ (Vector3.DOWN * HANG_LENGTH).rotated(n, _swing.x)
		- Vector3.UP * _hang_drop()
	)
	# A grip low on the legs: he stands on the land and reaches up, never hangs below it.
	hanging.y = maxf(hanging.y, height_at.call(hanging.x, hanging.z) as float)
	return hanging.lerp(standing, stand)


## How far below HANG_LENGTH the origin hangs: the stand-in's 0.6 m, or the Nomad's own
## (WandererBody.hang_reach: the grip's height above his origin).
func _hang_drop() -> float:
	return body.hang_reach - HANG_LENGTH if body else 0.6


## How far off the surface the origin hangs: the stand-in's 0.3 m, or the Nomad's own
## (WandererBody.hang_out).
func _hang_out() -> float:
	return body.hang_out if body else 0.3


## Turns toward the surface of a grip like a damped spring (time constant FACE_SECONDS): it starts
## and ends at rest. A snap, or a turn that starts at full speed, would whip the Nomad's body round
## under hands held on the grip.
func _face(p: GrabPoint, delta: float) -> void:
	var n := p.normal()
	var flat := Vector3(-n.x, 0.0, -n.z)
	if flat.length() <= 0.1:
		return
	var off := wrapf(atan2(-flat.x, -flat.z) - rotation.y, -PI, PI)
	var w := 1.0 / FACE_SECONDS
	_yaw_rate += (w * w * off - 2.0 * w * _yaw_rate) * delta
	rotation = Vector3(0.0, rotation.y + _yaw_rate * delta, 0.0)
