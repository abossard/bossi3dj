class_name Colossus
extends Node3D
## The giant. Roams the plain, Shakes, Falls. Subclasses build the body and pose it;
## nothing outside colossi/ knows about bones or parts.

signal footfall(at: Vector3, weight: float)
signal shaken(strength: float)
## The falling body hit the ground at `at`.
signal impact(at: Vector3)
signal settled

enum State { ROAM, FALLING, DOWN }

const STEP_SECONDS := 2.5
const TURN_RATE := deg_to_rad(4.0)
const SHAKE_SECONDS := 1.5
## A goal not reached in this time is dropped (it may sit inside the turning circle).
const GOAL_SECONDS := 60.0
## The dust the feet keep stirring: a low, wide fog volume that goes with the body, so the giant
## stands in something and the Wanderer is knee-high to it.
const DUST_COLOR := Color("c4b9a4")
const DUST_DENSITY := 0.15

@export var height_m: float = 28.0
@export var seed_value: int = 1

var height_at: Callable = func(_x: float, _z: float) -> float: return 0.0
## Centre and radius of the area the Colossus roams.
var roam_center := Vector3.ZERO
var roam_radius := 600.0
var state: State = State.ROAM
var look_target: Vector3 = Vector3.ZERO
var weight: float = 0.5
## Current Shake roll of the body in radians; the director rolls the close grip shot with it.
var roll: float = 0.0
## Walk to look_target and stand there facing it (the Wanderer is coming to climb).
var seek: bool = false
## The Wanderer holds on: stand still, no step and no turn, while he climbs (SPEC: "stands while
## he climbs").
var carrying: bool = false
## The dust skirt round the feet (a FogVolume); hidden by the probes that compare without it.
var dust_skirt: FogVolume

var _rng := RandomNumberGenerator.new()
var _goal := Vector3.ZERO
var _goal_age := 0.0
var _step_phase := 0.0
var _steps := 0
var _shake_t := INF
var _head_yaw := 0.0
var _points: Array[GrabPoint] = []
var _head_point: GrabPoint


func _ready() -> void:
	_rng.seed = seed_value
	_pick_goal()
	_build()
	_build_dust_skirt()
	_points.assign(find_children("*", "GrabPoint", true, false))
	for p in _points:
		if p.head:
			_head_point = p
	var links: Array[PackedInt32Array] = []
	for p in _points:
		var idx := PackedInt32Array()
		for q in p.linked():
			idx.append(_points.find(q))
		links.append(idx)
	if not GrabPath.all_reach(_points.find(_head_point), links):
		push_warning("%s: Grab Path does not reach the head from every Grab Point" % name)


func _physics_process(delta: float) -> void:
	if state == State.ROAM:
		_roam(delta)
	_shake_t += delta
	roll = 0.0
	if _shake_t < SHAKE_SECONDS:
		var k := _shake_t / SHAKE_SECONDS
		roll = sin(k * PI * 3.0) * deg_to_rad(12.0) * (1.0 - k)
	var to_target := look_target - global_position
	var want := 0.0
	if to_target.length_squared() > 1.0:
		var local := global_transform.basis.inverse() * to_target
		want = clampf(atan2(-local.x, -local.z), deg_to_rad(-70.0), deg_to_rad(70.0))
	_head_yaw = lerp_angle(_head_yaw, want, 1.0 - exp(-delta / 0.8))
	_pose(float(_steps % 2) + _step_phase, roll, _head_yaw)


## Beat arrived: let the next footfall drift onto it.
func on_beat() -> void:
	_step_phase = Beat.nudge(_step_phase)


func shake() -> void:
	if state != State.ROAM or _shake_t < SHAKE_SECONDS:
		return
	_shake_t = 0.0
	shaken.emit(1.0)


func is_shaking() -> bool:
	return _shake_t < SHAKE_SECONDS


func fall() -> void:
	if state != State.ROAM:
		return
	state = State.FALLING
	_topple(1.0 if _rng.randf() < 0.5 else -1.0)


## Override: bring the body down to the side `side` (+1 its right, -1 its left). Call
## _hit_ground when it strikes the ground and _lie_down when it has come to rest.
## The default tips the whole Colossus over like a felled tree.
func _topple(side: float) -> void:
	var t := create_tween()
	t.set_process_mode(Tween.TWEEN_PROCESS_PHYSICS)
	t.tween_property(self, "rotation:z", side * 1.45, 3.0).set_trans(Tween.TRANS_QUAD).set_ease(
		Tween.EASE_IN
	)
	t.tween_callback(func() -> void: _hit_ground(to_global(Vector3.UP * height_m * 0.6)))
	t.tween_property(self, "rotation:z", side * 1.36, 0.35).set_trans(Tween.TRANS_SINE).set_ease(
		Tween.EASE_OUT
	)
	t.tween_property(self, "rotation:z", side * 1.42, 0.5).set_trans(Tween.TRANS_SINE).set_ease(
		Tween.EASE_IN_OUT
	)
	t.tween_interval(1.2)
	t.tween_callback(_lie_down)


func _hit_ground(at: Vector3) -> void:
	at.y = height_at.call(at.x, at.z)
	impact.emit(at)
	footfall.emit(at, 2.0)


func _lie_down() -> void:
	state = State.DOWN
	settled.emit()


func reset_to(at: Vector3, heading: float) -> void:
	state = State.ROAM
	rotation = Vector3(0.0, heading, 0.0)
	global_position = Vector3(at.x, height_at.call(at.x, at.z), at.z)
	_shake_t = INF
	_pick_goal()


## The Grab Points, collected once after _build. Do not modify the array.
func grab_points() -> Array[GrabPoint]:
	return _points


## Middle of the body, wherever it is (standing, falling or down).
func center() -> Vector3:
	return to_global(Vector3.UP * height_m * 0.45)


## The Grab Point the climb aims for (the one marked `head`).
func head_point() -> GrabPoint:
	return _head_point


func _build_dust_skirt() -> void:
	var mat := FogMaterial.new()
	mat.density = DUST_DENSITY
	mat.albedo = DUST_COLOR
	mat.edge_fade = 0.6
	dust_skirt = FogVolume.new()
	dust_skirt.shape = RenderingServer.FOG_VOLUME_SHAPE_ELLIPSOID
	dust_skirt.size = Vector3(height_m * 1.2, height_m * 0.18, height_m * 1.2)
	dust_skirt.position = Vector3(0.0, dust_skirt.size.y * 0.25, 0.0)
	dust_skirt.material = mat
	add_child(dust_skirt)


## Override: create meshes and Grab Points (one marked `head`), scaled to height_m.
func _build() -> void:
	pass


## Override: pose legs, body roll and head. `stride` runs 0..2 over a left and a right step,
## advancing only forward; `roll` and `yaw` are radians.
func _pose(_stride: float, _roll: float, _yaw: float) -> void:
	pass


## True while the legs should rest (standing, not walking).
func is_standing() -> bool:
	return state != State.ROAM or carrying or (seek and _near_look_target())


func _near_look_target() -> bool:
	var flat := Vector3(global_position.x, 0.0, global_position.z)
	return flat.distance_to(Vector3(look_target.x, 0.0, look_target.z)) < height_m * 0.5


func _roam(delta: float) -> void:
	if carrying:
		return
	var flat := Vector3(global_position.x, 0.0, global_position.z)
	var forward := -global_transform.basis.z
	var speed := height_m * 0.45 / STEP_SECONDS
	var goal := _goal
	if seek:
		goal = Vector3(look_target.x, 0.0, look_target.z)
	else:
		_goal_age += delta
		if flat.distance_to(_goal) < maxf(40.0, speed / TURN_RATE) or _goal_age > GOAL_SECONDS:
			_pick_goal()
	var to_goal := goal - flat
	if to_goal.length() > 1.0:
		rotate_y(
			clampf(
				forward.signed_angle_to(to_goal.normalized(), Vector3.UP),
				-TURN_RATE * 3.0 * delta if seek else -TURN_RATE * delta,
				TURN_RATE * 3.0 * delta if seek else TURN_RATE * delta
			)
		)
	if is_standing():
		return
	var before := _step_phase
	_step_phase = fposmod(_step_phase + delta / STEP_SECONDS, 1.0)
	if _step_phase < before:
		_steps += 1
		footfall.emit(global_position, weight)
	var next := global_position + (-global_transform.basis.z) * speed * delta
	next.y = height_at.call(next.x, next.z)
	global_position = next


func _pick_goal() -> void:
	var a := _rng.randf() * TAU
	var r := sqrt(_rng.randf()) * roam_radius
	_goal = roam_center + Vector3(cos(a) * r, 0.0, sin(a) * r)
	_goal_age = 0.0
