class_name GrockColossus
extends Colossus
## Colossus 1, Grock Endboss (assets/MODELS.md), on its own skeleton at 28 m. Its idle clip plays
## on the whole body; RigGait swings the legs, bobs the hips, rolls the spine in a Shake and turns
## the head; TwoBoneIK3D plants the feet. Grab Points sit on the mesh's back and top surface, each
## on the bone that skins that spot. The Fall is a ragdoll of one body per bone (17). Nothing
## outside colossi/ knows these bone names.

const MODEL := "res://assets/models/grock/grock.gltf"
const IDLE := "idle2"
const SHAKE_CLIP := ""
const SHAKE_BLEND := 0.2
## Rock detail over the model's own textures (grock_rock.gdshader): the terrain's tiling rock.
const ROCK_SHADER := preload("res://colossi/grock_rock.gdshader")
const ROCK_DETAIL := "res://assets/terrain/rocky_terrain_02_normal_rough.png"
const ROCK_TINT := "res://assets/terrain/rocky_terrain_02_albedo_height.png"
## The glints that stand for its eyes (it has none): pale, as the stand-in's.
const EYE_COLOR := Color("cfe3ee")
const EYE_ENERGY := 8.0
## Where the eyes are on the face, in the rig's own space (x, y); the glint sits on the face's
## front surface there. A metre across, flattened against the face.
const EYES := [["eye_l", 1.0, 27.2], ["eye_r", -1.0, 27.2]]
const EYE_RADIUS := 0.6
## Bones: [thigh_l, shin_l, foot_l, thigh_r, shin_r, foot_r, upper_arm_l, upper_arm_r, spine, head,
## hips].
const GAIT_BONES := [
	"UpperLeg.L",
	"LowerLeg.L",
	"Foot.L",
	"UpperLeg.R",
	"LowerLeg.R",
	"Foot.R",
	"UpperArm.L",
	"UpperArm.R",
	"Spine1",
	"Head",
	"root",
]
## Each bone's body for the Fall: the bone it ends at (the next joint), or "" for a sphere on the
## bone's own axis of the given length (m) for bones without a child.
const BODIES := {
	"root": ["Spine1", 0.0],
	"Spine1": ["Spine2", 0.0],
	"Spine2": ["neck", 0.0],
	"neck": ["Head", 0.0],
	"Head": ["", 3.5],
	"shoulder.L": ["UpperArm.L", 0.0],
	"UpperArm.L": ["LowerArm.L", 0.0],
	"LowerArm.L": ["", 8.0],
	"shoulder.R": ["UpperArm.R", 0.0],
	"UpperArm.R": ["LowerArm.R", 0.0],
	"LowerArm.R": ["", 8.0],
	"UpperLeg.L": ["LowerLeg.L", 0.0],
	"LowerLeg.L": ["Foot.L", 0.0],
	"Foot.L": ["", 3.0],
	"UpperLeg.R": ["LowerLeg.R", 0.0],
	"LowerLeg.R": ["Foot.R", 0.0],
	"Foot.R": ["", 3.0],
}
## Grab Points in the rig's own space (it faces +Z, its back is -Z), metres at 28 m: [name, x, y]
## on the back surface; "top" and "head" are found on the top of the hump and of the head.
const BACK_GRIPS := [
	["calf_l", 2.9, 4.0],
	["thigh_l", 2.3, 9.0],
	["calf_r", -2.9, 4.0],
	["thigh_r", -2.3, 9.0],
	["low_back", 0.0, 13.5],
]
const GRID_ROWS := [15.5, 18.0, 20.5, 23.0]
const GRID_COLS := [-3.0, 0.0, 3.0]

## The model, loaded once, and the Grab Point layout found on its mesh (Roster.warm).
static var _scene: PackedScene
static var _layout := {}

## The clip played as a Shake (one of its own: Attack1 to 3, Defend1 to 3); "" keeps the idle clip
## and the roll RigGait gives the spine.
var shake_clip := SHAKE_CLIP

var _skeleton: Skeleton3D
var _sim: PhysicalBoneSimulator3D
var _ik: TwoBoneIK3D
var _gait: RigGait
var _anim: AnimationPlayer
var _bodies: Array[PhysicalBone3D] = []
var _chest: PhysicalBone3D
var _legs := PackedFloat32Array([0.0, 0.0, 0.0, 0.0])
## Half the planted leg's sweep (radians): the angle over which hip to ankle covers half a step.
var _sweep := 0.35
var _fall_t := 0.0
var _still_t := 0.0
var _hit := false


static func model_present() -> bool:
	return ResourceLoader.exists(MODEL)


## Loads the model and finds the Grab Points on its mesh, once: a Reset then builds Grock in one
## frame.
static func warm() -> void:
	if _scene != null or not model_present():
		return
	_scene = load(MODEL)
	var probe: Node = _scene.instantiate()
	_layout = _find_layout(probe)
	probe.free()


func _build() -> void:
	warm()
	var model: Node3D = _scene.instantiate()
	# The rig faces +Z; the Colossus walks toward -Z. The imported tree stays whole: its clips
	# address Armature/Skeleton3D from the model's root.
	model.name = "Body"
	model.rotation.y = PI
	add_child(model)
	_skeleton = model.find_child("Skeleton3D", true, false)
	_anim = model.find_child("AnimationPlayer", true, false)
	for mi: MeshInstance3D in _skeleton.find_children("*", "MeshInstance3D", true, false):
		# The haze must not swallow a far giant: at 1.6 km it would take him to the colour of
		# the sky (the rock shader draws without fog).
		mi.material_override = _rock_material(mi.mesh.surface_get_material(0))
	_anim.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_PHYSICS
	_anim.get_animation(IDLE).loop_mode = Animation.LOOP_LINEAR
	_anim.play(IDLE)
	shaken.connect(_on_shaken)
	_build_grab_path()
	_build_eyes()
	_build_gait()
	_build_ragdoll()


func _build_grab_path() -> void:
	var pts := {}
	for key: String in _layout:
		if key.begins_with("eye"):
			continue
		var g: Dictionary = _layout[key]
		var bone: String = g["bone"]
		var at := _attach(bone)
		var rest := _skeleton.get_bone_global_rest(_skeleton.find_bone(bone))
		var n: Vector3 = g["normal"]
		var up := Vector3.FORWARD if absf(n.y) > 0.9 else Vector3.UP
		var p := GrabPoint.new()
		p.name = key
		p.transform = rest.affine_inverse() * Transform3D(Basis.looking_at(-n, up), g["at"])
		at.add_child(p)
		pts[key] = p
	pts["head"].head = true
	_link(pts["calf_l"], pts["thigh_l"])
	_link(pts["calf_r"], pts["thigh_r"])
	_link(pts["thigh_l"], pts["low_back"])
	_link(pts["thigh_r"], pts["low_back"])
	_link(pts["low_back"], pts["grid_0_1"])
	for row in GRID_ROWS.size():
		for col in GRID_COLS.size():
			if col < GRID_COLS.size() - 1:
				_link(pts["grid_%d_%d" % [row, col]], pts["grid_%d_%d" % [row, col + 1]])
			if row < GRID_ROWS.size() - 1:
				_link(pts["grid_%d_%d" % [row, col]], pts["grid_%d_%d" % [row + 1, col]])
	_link(pts["grid_%d_1" % (GRID_ROWS.size() - 1)], pts["top"])
	_link(pts["top"], pts["head"])


## Its own textures and the terrain's rock as detail, drawn without fog.
static func _rock_material(source: Material) -> ShaderMaterial:
	var src := source as StandardMaterial3D
	var mat := ShaderMaterial.new()
	mat.shader = ROCK_SHADER
	mat.set_shader_parameter("albedo_tex", src.albedo_texture)
	mat.set_shader_parameter("normal_tex", src.normal_texture)
	mat.set_shader_parameter("rough_tex", src.roughness_texture)
	mat.set_shader_parameter("detail_tex", load(ROCK_DETAIL))
	mat.set_shader_parameter("tint_tex", load(ROCK_TINT))
	return mat


## The rock shader's material, for the probes that switch its parts.
func rock_material() -> ShaderMaterial:
	var mi := _skeleton.find_children("*", "MeshInstance3D", true, false)[0] as MeshInstance3D
	return mi.material_override as ShaderMaterial


## Two emissive glints on the face, on the head bone so the head's turn carries them.
func _build_eyes() -> void:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = EYE_COLOR
	mat.emission_enabled = true
	mat.emission = EYE_COLOR
	mat.emission_energy_multiplier = EYE_ENERGY
	var glint := SphereMesh.new()
	glint.radius = EYE_RADIUS
	glint.height = EYE_RADIUS * 2.0
	glint.radial_segments = 12
	glint.rings = 6
	glint.material = mat
	var head := _skeleton.find_bone("Head")
	var rest := _skeleton.get_bone_global_rest(head)
	var at := _attach("Head")
	for key: String in ["eye_l", "eye_r"]:
		var eye := MeshInstance3D.new()
		eye.name = key
		eye.mesh = glint
		eye.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		var spot: Dictionary = _layout[key]
		var flat := Basis.from_scale(Vector3(1.0, 0.6, 0.45))
		eye.transform = rest.affine_inverse() * Transform3D(flat, spot["at"])
		at.add_child(eye)


func _build_gait() -> void:
	var ik := TwoBoneIK3D.new()
	ik.setting_count = 2
	_gait = RigGait.new()
	_gait.bone_names = PackedStringArray(GAIT_BONES)
	_gait.height_at = height_at
	var foot := _skeleton.find_bone("Foot.L")
	_gait.ankle = _skeleton.get_bone_global_rest(foot).origin.y
	var hip := _skeleton.get_bone_global_rest(_skeleton.find_bone("UpperLeg.L")).origin
	var leg := hip.distance_to(_skeleton.get_bone_global_rest(foot).origin)
	# A step covers what the body walks in STEP_SECONDS (Colossus._roam's speed).
	_sweep = asin(clampf(height_m * 0.45 / (2.0 * leg), 0.0, 0.9))
	_skeleton.add_child(_gait)
	for side in 2:
		var s := "L" if side == 0 else "R"
		var target := Marker3D.new()
		target.top_level = true
		add_child(target)
		var pole := Marker3D.new()
		pole.top_level = true
		add_child(pole)
		_gait.foot_targets.append(target)
		_gait.knee_poles.append(pole)
		ik.set_root_bone_name(side, "UpperLeg." + s)
		ik.set_middle_bone_name(side, "LowerLeg." + s)
		ik.set_end_bone_name(side, "Foot." + s)
	_skeleton.add_child(ik)
	for side in 2:
		ik.set_target_node(side, ik.get_path_to(_gait.foot_targets[side]))
		ik.set_pole_node(side, ik.get_path_to(_gait.knee_poles[side]))
	_ik = ik


func _build_ragdoll() -> void:
	_sim = PhysicalBoneSimulator3D.new()
	_skeleton.add_child(_sim)
	for bone_name: String in BODIES:
		var spec: Array = BODIES[bone_name]
		var b := _skeleton.find_bone(bone_name)
		var rest := _skeleton.get_bone_global_rest(b)
		var body := PhysicalBone3D.new()
		body.name = "Body_" + bone_name
		body.bone_name = bone_name
		body.mass = 800.0
		body.linear_damp = 0.2
		body.angular_damp = 1.5
		body.collision_layer = 2
		body.collision_mask = 1
		var col := CollisionShape3D.new()
		var seg: Vector3
		if spec[0] != "":
			var to := _skeleton.get_bone_global_rest(_skeleton.find_bone(spec[0])).origin
			seg = rest.basis.inverse() * (to - rest.origin)
		else:
			seg = Vector3.UP * float(spec[1])
		var radius := clampf(_layout_radius(bone_name, seg.length()), 0.6, 4.0)
		var cap := CapsuleShape3D.new()
		cap.radius = radius
		cap.height = maxf(seg.length(), radius * 2.0 + 0.01)
		col.shape = cap
		# The body mid-segment, the joint at the bone's head (as Godot's own ragdoll generator).
		body.body_offset = PlaceholderColossus._along(seg)
		body.joint_offset = Transform3D(Basis.IDENTITY, Vector3.DOWN * seg.length() * 0.5)
		body.add_child(col)
		_sim.add_child(body)
		_bodies.append(body)
		if bone_name == "Spine2":
			_chest = body


## A body's radius: a third of its length, the stand-in's proportions for a stocky giant.
static func _layout_radius(_bone: String, length: float) -> float:
	return length * 0.33


func center() -> Vector3:
	return _chest.global_position


func _physics_process(delta: float) -> void:
	super._physics_process(delta)
	if state == State.FALLING:
		_watch_fall(delta)


func _pose(stride: float, roll: float, yaw: float) -> void:
	if state != State.ROAM:
		return
	var step := fmod(stride, 1.0)
	var lift := sin(step * PI) * 0.7
	var want := [0.0, 0.0, 0.0, 0.0]
	if not is_standing():
		# The planted leg sweeps from front to back at an even pace over one step, as far as the
		# body travels in it: its foot stays put on the land while the body passes over.
		var sweep := _sweep * (1.0 - 2.0 * step)
		var left := sweep if stride < 1.0 else -sweep
		var left_forward := stride >= 1.0
		want = [left, -lift if left_forward else 0.0, -left, 0.0 if left_forward else -lift]
	for i in 4:
		_legs[i] = lerpf(_legs[i], want[i], 0.15)
	_gait.legs = _legs
	_gait.roll = roll
	_gait.yaw = yaw
	_gait.bob = absf(sin(step * PI)) * 0.012 * height_m if not is_standing() else 0.0


func _on_shaken(_strength: float) -> void:
	if shake_clip == "" or state != State.ROAM:
		return
	_anim.play(shake_clip, SHAKE_BLEND)
	_anim.queue(IDLE)


func _topple(side: float) -> void:
	_ik.active = false
	_gait.active = false
	_anim.stop()
	for body in _bodies:
		body.joint_type = PhysicalBone3D.JOINT_TYPE_PIN
	_sim.physical_bones_start_simulation()
	var push := global_transform.basis.x * side * 6.0 - global_transform.basis.z * 1.5
	for body in _bodies:
		var up: float = (body.global_position.y - global_position.y) / height_m
		body.apply_central_impulse(push * body.mass * up)


func _watch_fall(delta: float) -> void:
	_fall_t += delta
	var ground: float = height_at.call(_chest.global_position.x, _chest.global_position.z)
	if not _hit and _chest.global_position.y - ground < height_m * 0.25:
		_hit = true
		_hit_ground(_chest.global_position)
	var fastest := 0.0
	for body in _bodies:
		fastest = maxf(fastest, body.linear_velocity.length())
	_still_t = _still_t + delta if fastest < 0.8 else 0.0
	if (_fall_t > 2.5 and _still_t > 1.0) or _fall_t > 12.0:
		if not _hit:
			_hit = true
			_hit_ground(_chest.global_position)
		_lie_down()


func _attach(bone: String) -> BoneAttachment3D:
	var node_name := "At_" + bone.replace(".", "_")
	var existing := _skeleton.get_node_or_null(node_name) as BoneAttachment3D
	if existing:
		return existing
	var a := BoneAttachment3D.new()
	a.name = node_name
	a.bone_name = bone
	_skeleton.add_child(a)
	return a


func _link(a: GrabPoint, b: GrabPoint) -> void:
	a.links.append(a.get_path_to(b))
	b.links.append(b.get_path_to(a))


## Grab Points on the mesh at rest: for each spot, the back-most vertex near it (the top-most for
## "top" and "head"), its normal, and the bone that skins it most. {name: {at, normal, bone}}.
static func _find_layout(model: Node) -> Dictionary:
	var mi: MeshInstance3D
	for n in model.find_children("*", "MeshInstance3D", true, false):
		mi = n
	var arrays := mi.mesh.surface_get_arrays(0)
	var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
	var bones: PackedInt32Array = arrays[Mesh.ARRAY_BONES]
	var weights: PackedFloat32Array = arrays[Mesh.ARRAY_WEIGHTS]
	var per := bones.size() / verts.size()
	var skin := mi.skin
	var spots := []
	for g: Array in BACK_GRIPS:
		spots.append([g[0], Vector2(g[1], g[2]), "back"])
	for row in GRID_ROWS.size():
		for col in GRID_COLS.size():
			spots.append(
				["grid_%d_%d" % [row, col], Vector2(GRID_COLS[col], GRID_ROWS[row]), "back"]
			)
	for e: Array in EYES:
		spots.append([e[0], Vector2(e[1], e[2]), "front"])
	spots.append(["top", Vector2.ZERO, "top"])
	spots.append(["head", Vector2.ZERO, "head"])
	var out := {}
	for spot: Array in spots:
		var best := -1
		var best_score := -INF
		var radius := 0.8
		while best < 0 and radius < 6.0:
			for i in verts.size():
				var v := verts[i]
				var score := -INF
				match spot[2]:
					"back":
						if Vector2(v.x, v.y).distance_to(spot[1]) < radius:
							score = -v.z
					"front":
						if Vector2(v.x, v.y).distance_to(spot[1]) < radius:
							score = v.z
					"top":
						if absf(v.x) < radius * 2.0 and v.z < 2.0:
							score = v.y
					"head":
						if absf(v.x) < radius * 2.0 and v.z > 2.5:
							score = v.y
				if score > best_score:
					best_score = score
					best = i
			radius *= 1.5
		var bone_index := 0
		var top_weight := -1.0
		for k in per:
			if weights[best * per + k] > top_weight:
				top_weight = weights[best * per + k]
				bone_index = bones[best * per + k]
		out[spot[0]] = {
			"at": verts[best],
			"normal": normals[best].normalized(),
			"bone": skin.get_bind_name(bone_index) if skin else "Spine2",
		}
	return out
