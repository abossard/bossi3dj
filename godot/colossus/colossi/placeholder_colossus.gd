class_name PlaceholderColossus
extends Colossus
## Rigged stand-in until the Sketchfab models are imported: a Skeleton3D with stone parts on bone
## attachments, Grab Points riding the bones, feet planted on the land by TwoBoneIK3D and a
## physical-bone ragdoll for the Fall. A real Colossus swaps the parts and keeps the rest.

const STONE := Color("2d2b28")
const MOSS := Color("2c3024")
const EYE := Color("cfe3ee")
## [bone, parent, head offset from the parent's head], offsets in units of height_m.
const BONES := [
	["hips", "", Vector3(0.0, 0.46, 0.0)],
	["spine", "hips", Vector3(0.0, 0.1, 0.02)],
	["chest", "spine", Vector3(0.0, 0.16, 0.0)],
	["neck", "chest", Vector3(0.0, 0.17, -0.06)],
	["head", "neck", Vector3(0.0, 0.05, -0.05)],
	["thigh_l", "hips", Vector3(-0.12, -0.01, 0.0)],
	["shin_l", "thigh_l", Vector3(0.0, -0.22, 0.015)],
	["foot_l", "shin_l", Vector3(0.0, -0.21, -0.015)],
	["thigh_r", "hips", Vector3(0.12, -0.01, 0.0)],
	["shin_r", "thigh_r", Vector3(0.0, -0.22, 0.015)],
	["foot_r", "shin_r", Vector3(0.0, -0.21, -0.015)],
	["upper_arm_l", "chest", Vector3(-0.27, 0.12, 0.0)],
	["forearm_l", "upper_arm_l", Vector3(-0.02, -0.21, 0.0)],
	["hand_l", "forearm_l", Vector3(0.0, -0.2, 0.0)],
	["upper_arm_r", "chest", Vector3(0.27, 0.12, 0.0)],
	["forearm_r", "upper_arm_r", Vector3(0.02, -0.21, 0.0)],
	["hand_r", "forearm_r", Vector3(0.0, -0.2, 0.0)],
]
## Limb segments [bone, child, radius]: a stone capsule each, and a ragdoll body each.
const LIMBS := [
	["spine", "chest", 0.15],
	["thigh_l", "shin_l", 0.075],
	["shin_l", "foot_l", 0.062],
	["thigh_r", "shin_r", 0.075],
	["shin_r", "foot_r", 0.062],
	["upper_arm_l", "forearm_l", 0.06],
	["forearm_l", "hand_l", 0.055],
	["upper_arm_r", "forearm_r", 0.06],
	["forearm_r", "hand_r", 0.055],
]
## Chest ellipsoid around the chest bone's head, in units of height_m.
const CHEST_CENTER := Vector3(0.0, 0.04, 0.0)
const CHEST_RADII := Vector3(0.25, 0.15, 0.17)

var _skeleton: Skeleton3D
var _sim: PhysicalBoneSimulator3D
var _ik: TwoBoneIK3D
var _bodies: Array[PhysicalBone3D] = []
var _rest := {}
var _feet: Array[Marker3D] = []
var _legs := [0.0, 0.0, 0.0, 0.0]
var _fall_t := 0.0
var _still_t := 0.0
var _hit := false


func _build() -> void:
	var h := height_m
	_skeleton = Skeleton3D.new()
	add_child(_skeleton)
	for b: Array in BONES:
		var i := _skeleton.add_bone(b[0])
		if b[1] != "":
			_skeleton.set_bone_parent(i, _skeleton.find_bone(b[1]))
		_skeleton.set_bone_rest(i, Transform3D(Basis.IDENTITY, b[2] * h))
		_rest[b[0]] = b[2] * h
	_skeleton.reset_bone_poses()
	var stone := _stone_material()
	var moss := _stone_material()
	moss.albedo_color = MOSS
	for l: Array in LIMBS:
		_capsule(_attach(l[0]), _rest[l[1]], l[2] * h, stone)
	var hips := _attach("hips")
	_ellipsoid(hips, Vector3(0.0, -0.01, 0.01) * h, Vector3(0.2, 0.11, 0.15) * h, stone)
	var chest := _attach("chest")
	_ellipsoid(chest, CHEST_CENTER * h, CHEST_RADII * h, stone)
	_ellipsoid(
		chest, (CHEST_CENTER + Vector3(0.0, 0.03, 0.06)) * h, Vector3(0.2, 0.12, 0.12) * h, moss
	)
	var head := _attach("head")
	_ellipsoid(head, Vector3(0.0, 0.03, -0.02) * h, Vector3(0.07, 0.075, 0.08) * h, stone)
	_eyes(head, h)
	_build_grab_path(h, chest)
	_build_feet_ik()
	_build_ragdoll(h)


func _build_grab_path(h: float, chest: Node3D) -> void:
	var calf_l := _point(_attach("shin_l"), Vector3(0.0, -0.1, 0.066) * h, Vector3.BACK)
	var thigh_l := _point(_attach("thigh_l"), Vector3(0.0, -0.1, 0.078) * h, Vector3.BACK)
	var calf_r := _point(_attach("shin_r"), Vector3(0.0, -0.1, 0.066) * h, Vector3.BACK)
	var thigh_r := _point(_attach("thigh_r"), Vector3(0.0, -0.1, 0.078) * h, Vector3.BACK)
	var low_back := _point(_attach("spine"), Vector3(0.0, 0.08, 0.17) * h, Vector3.BACK)
	var grid: Array = []
	for row in 4:
		var line: Array[GrabPoint] = []
		for col in 3:
			var x := (col - 1) * 0.12
			var y := -0.1 + row * 0.065
			line.append(_point(chest, _on_chest(x, y) * h, Vector3.BACK))
		grid.append(line)
	var shoulder := _point(
		chest, (CHEST_CENTER + Vector3(0.0, CHEST_RADII.y, 0.04)) * h, Vector3.UP
	)
	var top := _point(_attach("head"), Vector3(0.0, 0.105, -0.02) * h, Vector3.UP)
	top.head = true
	_link(calf_l, thigh_l)
	_link(calf_r, thigh_r)
	_link(thigh_l, low_back)
	_link(thigh_r, low_back)
	_link(low_back, grid[0][1])
	for row in 4:
		for col in 3:
			if col < 2:
				_link(grid[row][col], grid[row][col + 1])
			if row < 3:
				_link(grid[row][col], grid[row + 1][col])
	_link(grid[3][1], shoulder)
	_link(shoulder, top)


## A point on the back of the chest ellipsoid at x, y (units of height_m) from its centre.
func _on_chest(x: float, y: float) -> Vector3:
	var r := CHEST_RADII
	var z := r.z * sqrt(maxf(1.0 - pow(x / r.x, 2.0) - pow(y / r.y, 2.0), 0.05))
	return CHEST_CENTER + Vector3(x, y, z + 0.004)


func _build_feet_ik() -> void:
	var ik := TwoBoneIK3D.new()
	ik.setting_count = 2
	for i in 2:
		var side := "l" if i == 0 else "r"
		var target := Marker3D.new()
		target.name = "FootTarget_" + side
		add_child(target)
		var pole := Marker3D.new()
		pole.name = "KneePole_" + side
		add_child(pole)
		_feet.append(target)
		_feet.append(pole)
		ik.set_root_bone_name(i, "thigh_" + side)
		ik.set_middle_bone_name(i, "shin_" + side)
		ik.set_end_bone_name(i, "foot_" + side)
	_skeleton.add_child(ik)
	_ik = ik
	for i in 2:
		ik.set_target_node(i, ik.get_path_to(_feet[i * 2]))
		ik.set_pole_node(i, ik.get_path_to(_feet[i * 2 + 1]))


func _build_ragdoll(h: float) -> void:
	_sim = PhysicalBoneSimulator3D.new()
	_skeleton.add_child(_sim)
	var parts := LIMBS.duplicate()
	parts.append(["hips", "", 0.12])
	parts.append(["chest", "", 0.16])
	parts.append(["head", "", 0.07])
	for l: Array in parts:
		var body := PhysicalBone3D.new()
		body.name = "Body_" + l[0]
		body.bone_name = l[0]
		body.mass = 800.0
		body.linear_damp = 0.2
		body.angular_damp = 1.5
		body.collision_layer = 2
		body.collision_mask = 1
		# The body sits mid-segment with the joint at the bone's head, as Godot's own ragdoll
		# generator places them; bodies centred on the joint fling off the ground on contact.
		var col := CollisionShape3D.new()
		if l[1] != "":
			var seg: Vector3 = _rest[l[1]]
			var cap := CapsuleShape3D.new()
			cap.radius = l[2] * h
			cap.height = maxf(seg.length(), cap.radius * 2.0 + 0.01)
			col.shape = cap
			body.body_offset = _along(seg)
			body.joint_offset = Transform3D(Basis.IDENTITY, Vector3.DOWN * seg.length() * 0.5)
		else:
			var ball := SphereShape3D.new()
			ball.radius = l[2] * h
			col.shape = ball
			var centre := (CHEST_CENTER * h) if l[0] == "chest" else Vector3.ZERO
			body.body_offset = Transform3D(Basis.IDENTITY, centre)
			body.joint_offset = Transform3D(Basis.IDENTITY, -centre)
		body.add_child(col)
		_sim.add_child(body)
		_bodies.append(body)


func center() -> Vector3:
	return _bodies[_bodies.size() - 2].global_position


func _physics_process(delta: float) -> void:
	super._physics_process(delta)
	if state == State.FALLING:
		_watch_fall(delta)


func _pose(stride: float, roll: float, yaw: float) -> void:
	if state != State.ROAM:
		return
	var step := fmod(stride, 1.0)
	var swing := cos(step * PI) * 0.35
	var lift := sin(step * PI) * 0.7
	var want := [0.0, 0.0, 0.0, 0.0]
	if not is_standing():
		var left := swing if stride < 1.0 else -swing
		# The leg travelling forward bends its knee.
		var left_forward := stride >= 1.0
		want = [left, -lift if left_forward else 0.0, -left, 0.0 if left_forward else -lift]
	for i in 4:
		_legs[i] = lerpf(_legs[i], want[i], 0.15)
	_rotate("thigh_l", Vector3.RIGHT, _legs[0])
	_rotate("shin_l", Vector3.RIGHT, _legs[1])
	_rotate("thigh_r", Vector3.RIGHT, _legs[2])
	_rotate("shin_r", Vector3.RIGHT, _legs[3])
	_rotate("upper_arm_l", Vector3.RIGHT, -_legs[0] * 0.6)
	_rotate("upper_arm_r", Vector3.RIGHT, -_legs[2] * 0.6)
	_rotate("spine", Vector3.BACK, roll)
	_rotate("head", Vector3.UP, yaw)
	var bob := absf(sin(step * PI)) * 0.012 * height_m if not is_standing() else 0.0
	var hips: Vector3 = _rest["hips"] + Vector3.UP * bob
	_skeleton.set_bone_pose_position(_skeleton.find_bone("hips"), hips)
	_plant_feet(hips)


## Foot IK targets: where the posed feet are (worked out down the leg chain), never below the land.
func _plant_feet(hips: Vector3) -> void:
	for i in 2:
		var side := "l" if i == 0 else "r"
		var thigh := Basis(Vector3.RIGHT, _legs[i * 2])
		var shin := Basis(Vector3.RIGHT, _legs[i * 2 + 1])
		var knee_local: Vector3 = hips + _rest["thigh_" + side] + thigh * _rest["shin_" + side]
		var foot_local: Vector3 = knee_local + thigh * shin * _rest["foot_" + side]
		var foot := to_global(foot_local)
		var ground: float = height_at.call(foot.x, foot.z)
		foot.y = maxf(foot.y, ground + 0.01 * height_m)
		_feet[i * 2].global_position = foot
		_feet[i * 2 + 1].global_position = to_global(knee_local + Vector3.FORWARD * height_m * 0.3)


func _topple(side: float) -> void:
	_ik.active = false
	# Joints are built from the bodies' current places, so build them now, on the posed body:
	# built at setup, before the bodies follow their bones, they fling the body apart.
	for body in _bodies:
		body.joint_type = PhysicalBone3D.JOINT_TYPE_PIN
	_sim.physical_bones_start_simulation()
	var push := global_transform.basis.x * side * 6.0 - global_transform.basis.z * 1.5
	for body in _bodies:
		var up: float = (body.global_position.y - global_position.y) / height_m
		body.apply_central_impulse(push * body.mass * up)


func _watch_fall(delta: float) -> void:
	_fall_t += delta
	var chest := _bodies[_bodies.size() - 2]
	var ground: float = height_at.call(chest.global_position.x, chest.global_position.z)
	if not _hit and chest.global_position.y - ground < height_m * 0.25:
		_hit = true
		_hit_ground(chest.global_position)
	var fastest := 0.0
	for body in _bodies:
		fastest = maxf(fastest, body.linear_velocity.length())
	_still_t = _still_t + delta if fastest < 0.8 else 0.0
	if (_fall_t > 2.5 and _still_t > 1.0) or _fall_t > 12.0:
		if not _hit:
			_hit = true
			_hit_ground(chest.global_position)
		_lie_down()


func _rotate(bone: String, axis: Vector3, angle: float) -> void:
	_skeleton.set_bone_pose_rotation(_skeleton.find_bone(bone), Quaternion(axis, angle))


func _attach(bone: String) -> BoneAttachment3D:
	var node_name := "At_" + bone
	var existing := _skeleton.get_node_or_null(node_name) as BoneAttachment3D
	if existing:
		return existing
	var a := BoneAttachment3D.new()
	a.name = node_name
	a.bone_name = bone
	_skeleton.add_child(a)
	return a


## Transform that lays a Y-axis capsule along `seg`, centred on it.
static func _along(seg: Vector3) -> Transform3D:
	var dir := seg.normalized()
	var axis := Vector3.UP.cross(dir)
	var basis := Basis.IDENTITY
	if axis.length() > 1e-4:
		basis = Basis(axis.normalized(), Vector3.UP.angle_to(dir))
	elif dir.y < 0.0:
		basis = Basis(Vector3.RIGHT, PI)
	return Transform3D(basis, seg * 0.5)


func _capsule(parent: Node3D, seg: Vector3, radius: float, mat: Material) -> void:
	var m := MeshInstance3D.new()
	var c := CapsuleMesh.new()
	c.radius = radius
	c.height = seg.length() + radius * 1.2
	m.mesh = c
	m.material_override = mat
	m.transform = _along(seg)
	parent.add_child(m)


func _ellipsoid(parent: Node3D, at: Vector3, radii: Vector3, mat: Material) -> void:
	var m := MeshInstance3D.new()
	var s := SphereMesh.new()
	s.radius = 1.0
	s.height = 2.0
	m.mesh = s
	m.material_override = mat
	m.position = at
	m.scale = radii
	parent.add_child(m)


func _eyes(head: Node3D, h: float) -> void:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = EYE
	mat.emission_enabled = true
	mat.emission = EYE
	mat.emission_energy_multiplier = 8.0
	for side in [-1.0, 1.0]:
		var eye := MeshInstance3D.new()
		var e := SphereMesh.new()
		e.radius = 0.008 * h
		e.height = 0.016 * h
		eye.mesh = e
		eye.material_override = mat
		eye.position = Vector3(side * 0.03 * h, 0.04 * h, -0.095 * h)
		head.add_child(eye)


func _stone_material() -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = STONE
	m.roughness = 0.95
	var bumps := NoiseTexture2D.new()
	bumps.width = 512
	bumps.height = 512
	bumps.seamless = true
	bumps.as_normal_map = true
	bumps.bump_strength = 6.0
	var n := FastNoiseLite.new()
	n.seed = seed_value
	n.frequency = 0.02
	n.fractal_octaves = 5
	bumps.noise = n
	m.normal_enabled = true
	m.normal_texture = bumps
	m.uv1_triplanar = true
	m.uv1_scale = Vector3.ONE * 0.25
	return m


func _point(parent: Node3D, at: Vector3, normal: Vector3) -> GrabPoint:
	var g := GrabPoint.new()
	g.position = at
	parent.add_child(g)
	if not normal.is_equal_approx(Vector3.BACK):
		g.basis = Basis.looking_at(-normal, Vector3.FORWARD if absf(normal.y) > 0.9 else Vector3.UP)
	return g


func _link(a: GrabPoint, b: GrabPoint) -> void:
	a.links.append(a.get_path_to(b))
	b.links.append(b.get_path_to(a))
