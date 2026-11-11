class_name WandererBody
extends Node3D
## The Nomad on its own skeleton. Mixamo clips play on a source skeleton (renamed to the humanoid
## profile at load, see WandererClips) and RetargetModifier3D carries the pose onto the Nomad.
## After it, on the Nomad: the feet planted on the land, the hands on the Grab Points by
## TwoBoneIK3D, chest and head turned toward the Colossus by LookAtModifier3D. Without any clip
## a procedural pose (WandererPose) stands in for them. The Wanderer moves the body; this node
## only poses it.

## Cross-fade between the ground, the climb and the fall (s): no pop at a state change.
const MODE_BLEND := 0.35
const CLIMB_BLEND := 0.25
## Smoothing of the speed that drives the walk blend (s).
const SPEED_SMOOTH := 0.25
## Hands reach the grip in this time; feet and look settle as slowly.
const HAND_BLEND := 0.3
## The hands hold the grip this far apart, along the surface.
const HAND_SPREAD := 0.18
## Time constant of the hang following the clip (s): shimmy and hop clips move it within a cycle.
const HANG_SMOOTH := 0.4
## Left elbow pole in the body's space (m); the right one is its mirror.
const ELBOW_POLE := Vector3(0.7, 1.5, -0.4)
const CLIMB_SLOTS := [
	"hang_idle", "shimmy_left", "shimmy_right", "climb_up", "climb_down", "hang_swing"
]
const P_MODE := &"parameters/mode/transition_request"
const P_CLIMB := &"parameters/climb/transition_request"
const P_LOCO := &"parameters/loco/blend_position"
const P_SCALE := &"parameters/loco_scale/scale"

var height_at: Callable = func(_x: float, _z: float) -> float: return 0.0
## The Nomad's skeleton (pose readers: probes and the debug overlay).
var skeleton: Skeleton3D
## Slots that play their own clip, and the clip each other slot borrows.
var resolved := {}
## Ground speed (m/s) at which the walk and run clips do not slide, on the Nomad's legs.
var walk_speed := 0.0
var run_speed := 0.0
## Where the body hangs from a grip: the grip this far above its origin (m) and the origin this
## far off the surface (m), following the hang fit of the clip's pose (WandererFeet) while he
## climbs.
var hang_reach := 2.0
var hang_out := 0.3

var _source: Skeleton3D
var _tree: AnimationTree
var _mode := ""
var _climb := ""
var _speed := 0.0
var _hand_w := 0.0
var _hand_l := Marker3D.new()
var _hand_r := Marker3D.new()
var _elbow_l := Marker3D.new()
var _elbow_r := Marker3D.new()
var _look := Marker3D.new()
var _hands: TwoBoneIK3D
var _head_look: LookAtModifier3D
var _chest_look: LookAtModifier3D
var _planter: WandererFeet
var _pose: WandererPose
var _stand_t := INF
var _landing := false
var _move_from: GrabPoint
var _move_to: GrabPoint
var _right_leads := false
var _stand_len := 1.0


func _ready() -> void:
	rotation.y = PI
	var model: Node = load(Wanderer.MODEL).instantiate()
	skeleton = model.find_child("Skeleton3D", true, false)
	skeleton.get_parent().remove_child(skeleton)
	skeleton.name = "Nomad"
	model.free()
	for m in [_hand_l, _hand_r, _elbow_l, _elbow_r, _look]:
		m.top_level = true
		add_child(m)
	var lib := _load_clips()
	if lib:
		_build_tree(lib)
		var retarget := RetargetModifier3D.new()
		retarget.profile = SkeletonProfileHumanoid.new()
		retarget.use_global_pose = true
		_source.add_child(retarget)
		retarget.add_child(skeleton)
	else:
		add_child(skeleton)
	_pose = WandererPose.new()
	_pose.active = lib == null
	skeleton.add_child(_pose)
	_planter = WandererFeet.new()
	_planter.body = self
	skeleton.add_child(_planter)
	_planter.legs = _two_bone(
		["LeftUpperLeg", "LeftLowerLeg", "LeftFoot"],
		["RightUpperLeg", "RightLowerLeg", "RightFoot"],
		[_planter.foot_l, _planter.foot_r],
		[_planter.knee_l, _planter.knee_r]
	)
	_planter.legs.influence = 0.0
	# Modifiers run in child order: the chest turns before the hands are put on the grip (a turn
	# after the hand IK would carry the hands off it), the head last.
	_chest_look = _look_at("Chest", 0.35, deg_to_rad(35.0))
	_hands = _two_bone(
		["LeftUpperArm", "LeftLowerArm", "LeftHand"],
		["RightUpperArm", "RightLowerArm", "RightHand"],
		[_hand_l, _hand_r],
		[_elbow_l, _elbow_r]
	)
	_hands.influence = 0.0
	_head_look = _look_at("Head", 0.85, deg_to_rad(60.0))


## Which clips play where: the library of every slot that resolves to a present clip, with the
## Mixamo bones renamed to the humanoid profile; null when no clip is present.
func _load_clips() -> AnimationLibrary:
	var present := PackedStringArray()
	for s in WandererClips.SLOTS:
		if ResourceLoader.exists(WandererClips.DIR + s["file"]):
			present.append(s["slot"])
	resolved = WandererClips.resolve(present)
	if present.is_empty():
		return null
	var loaded := {}
	for slot in present:
		var file := ""
		for s in WandererClips.SLOTS:
			if s["slot"] == slot:
				file = s["file"]
		var scene: Node = load(WandererClips.DIR + file).instantiate()
		var player: AnimationPlayer = scene.find_child("AnimationPlayer", true, false)
		var anim: Animation = player.get_animation(player.get_animation_list()[0]).duplicate(true)
		if _source == null:
			_source = scene.find_child("Skeleton3D", true, false)
			_source.get_parent().remove_child(_source)
			_source.name = "Skeleton3D"
			for b in _source.get_bone_count():
				_source.set_bone_name(b, WandererClips.bone_name(_source.get_bone_name(b)))
		scene.free()
		loaded[slot] = _clean(anim)
	add_child(_source)
	var lib := AnimationLibrary.new()
	for s in WandererClips.SLOTS:
		var r: Array = resolved[s["slot"]]
		if r[0] == "":
			continue
		var anim: Animation = loaded[r[0]]
		if r[1]:
			anim = WandererClips.first_frame(anim)
		elif s["slot"] != r[0]:
			anim = anim.duplicate(true)
		anim.loop_mode = (
			Animation.LOOP_NONE if s["slot"] in WandererClips.ONE_SHOT else Animation.LOOP_LINEAR
		)
		lib.add_animation(s["slot"], anim)
	return lib


## Tracks renamed to the profile, scale tracks dropped, the Hips' net travel taken out.
func _clean(anim: Animation) -> Animation:
	for t in range(anim.get_track_count() - 1, -1, -1):
		var path := String(anim.track_get_path(t))
		var bone := WandererClips.bone_name(path.get_slice(":", 1))
		if anim.track_get_type(t) == Animation.TYPE_SCALE_3D:
			anim.remove_track(t)
			continue
		anim.track_set_path(t, NodePath("Skeleton3D:" + bone))
		if bone == "Hips" and anim.track_get_type(t) == Animation.TYPE_POSITION_3D:
			WandererClips.in_place(anim, t)
		elif anim.track_get_type(t) == Animation.TYPE_POSITION_3D:
			anim.remove_track(t)
	return anim


func _build_tree(lib: AnimationLibrary) -> void:
	var player := AnimationPlayer.new()
	player.name = "Clips"
	add_child(player)
	player.root_node = player.get_path_to(self)
	player.add_animation_library("", lib)
	var ratio := _leg_ratio()
	walk_speed = _stride(player, "walk") * ratio
	run_speed = _stride(player, "run") * ratio
	hang_reach = _reach(player) * ratio
	var root := AnimationNodeBlendTree.new()
	var loco := AnimationNodeBlendSpace1D.new()
	loco.add_blend_point(_anim("idle"), 0.0)
	loco.add_blend_point(_anim("walk"), Wanderer.WALK)
	loco.add_blend_point(_anim("run"), Wanderer.RUN)
	loco.min_space = 0.0
	loco.max_space = Wanderer.RUN
	root.add_node("loco", loco)
	root.add_node("loco_scale", AnimationNodeTimeScale.new())
	root.connect_node("loco_scale", 0, "loco")
	var climb := AnimationNodeTransition.new()
	climb.xfade_time = CLIMB_BLEND
	climb.xfade_curve = _ease()
	root.add_node("climb", climb)
	for i in CLIMB_SLOTS.size():
		climb.add_input(CLIMB_SLOTS[i])
		root.add_node(CLIMB_SLOTS[i], _anim(CLIMB_SLOTS[i]))
		root.connect_node("climb", i, CLIMB_SLOTS[i])
	var mode := AnimationNodeTransition.new()
	mode.xfade_time = MODE_BLEND
	mode.xfade_curve = _ease()
	root.add_node("mode", mode)
	var inputs := [
		["ground", "loco_scale"], ["climb", "climb"], ["fall", "fall_idle"], ["stand", "stand_up"]
	]
	for i in inputs.size():
		mode.add_input(inputs[i][0])
		if not root.has_node(inputs[i][1]):
			root.add_node(inputs[i][1], _anim(inputs[i][1]))
		root.connect_node("mode", i, inputs[i][1])
	root.connect_node("output", 0, "mode")
	if lib.has_animation("stand_up"):
		_stand_len = lib.get_animation("stand_up").length
	_tree = AnimationTree.new()
	_tree.tree_root = root
	_tree.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_PHYSICS
	add_child(_tree)
	_tree.anim_player = _tree.get_path_to(player)
	_tree.root_node = _tree.get_path_to(self)
	_tree.active = true


## Ease in and out for a cross-fade: a linear fade starts and stops the blend at full rate, which
## steps every joint's velocity by the pose difference over the fade time.
static func _ease() -> Curve:
	var c := Curve.new()
	c.add_point(Vector2(0.0, 0.0), 0.0, 0.0)
	c.add_point(Vector2(1.0, 1.0), 0.0, 0.0)
	return c


func _anim(slot: String) -> AnimationNodeAnimation:
	var a := AnimationNodeAnimation.new()
	a.animation = slot if resolved.get(slot, ["", false])[0] != "" else &"idle"
	return a


## Nomad leg over Mixamo leg (hip joint to ankle at rest): strides and reach scale with the legs.
## Not the hips' height: the Nomad's hips bone sits 0.2 m lower in a leg of the same length.
func _leg_ratio() -> float:
	return _leg(skeleton) / maxf(_leg(_source), 0.01)


static func _leg(s: Skeleton3D) -> float:
	var hip := s.get_bone_global_rest(s.find_bone("LeftUpperLeg")).origin
	return hip.distance_to(s.get_bone_global_rest(s.find_bone("LeftFoot")).origin)


## Planted-foot speed of a walk or run clip on the source skeleton (m/s), 0 when it borrows.
func _stride(player: AnimationPlayer, slot: String) -> float:
	if resolved[slot][0] != slot:
		return 0.0
	var anim := player.get_animation(slot)
	var hips := _source.find_bone("Hips")
	var best := 0.0
	for foot_name in ["LeftFoot", "RightFoot"]:
		var foot := _source.find_bone(foot_name)
		var z := PackedFloat32Array()
		var y := PackedFloat32Array()
		var steps := 60
		var dt := anim.length / steps
		player.play(slot)
		for i in steps:
			player.seek(i * dt, true)
			var f := _source.get_bone_global_pose(foot).origin
			var h := _source.get_bone_global_pose(hips).origin
			z.append(f.z - h.z)
			y.append(f.y)
		best = maxf(best, WandererClips.stride_speed(z, y, dt))
	player.stop()
	return best


## Hands above the origin in the hang pose (source skeleton, m).
func _reach(player: AnimationPlayer) -> float:
	if resolved["hang_idle"][0] == "":
		return 2.0
	player.play("hang_idle")
	player.seek(0.0, true)
	var l := _source.get_bone_global_pose(_source.find_bone("LeftHand")).origin.y
	var r := _source.get_bone_global_pose(_source.find_bone("RightHand")).origin.y
	player.stop()
	return (l + r) * 0.5


func _two_bone(left: Array, right: Array, targets: Array, poles: Array) -> TwoBoneIK3D:
	var ik := TwoBoneIK3D.new()
	ik.setting_count = 2
	skeleton.add_child(ik)
	for i in 2:
		var chain: Array = left if i == 0 else right
		ik.set_root_bone_name(i, chain[0])
		ik.set_middle_bone_name(i, chain[1])
		ik.set_end_bone_name(i, chain[2])
		ik.set_target_node(i, ik.get_path_to(targets[i]))
		ik.set_pole_node(i, ik.get_path_to(poles[i]))
	return ik


func _look_at(bone: String, influence: float, limit: float) -> LookAtModifier3D:
	var look := LookAtModifier3D.new()
	look.bone_name = bone
	# The Nomad faces +Z in its own space; the bone's axis that points there looks.
	look.forward_axis = _forward_axis(bone)
	look.target_node = NodePath()
	look.use_angle_limitation = true
	look.symmetry_limitation = true
	look.primary_limit_angle = limit
	look.secondary_limit_angle = limit
	look.duration = 0.6
	look.transition_type = Tween.TRANS_SINE
	look.influence = influence
	skeleton.add_child(look)
	look.target_node = look.get_path_to(_look)
	return look


func _forward_axis(bone: String) -> SkeletonModifier3D.BoneAxis:
	var basis := skeleton.get_bone_global_rest(skeleton.find_bone(bone)).basis.orthonormalized()
	var local := basis.inverse() * Vector3.BACK
	var axes := [
		Vector3.RIGHT, Vector3.LEFT, Vector3.UP, Vector3.DOWN, Vector3.BACK, Vector3.FORWARD
	]
	var best := 0
	for i in axes.size():
		if local.dot(axes[i]) > local.dot(axes[best]):
			best = i
	return best as SkeletonModifier3D.BoneAxis


## Pose for this physics tick. `state` is the Wanderer's, `speed` his ground speed, `look` where
## his eyes go. While on the Colossus: `from` and `grip` the Grab Points he moves between (the
## same while he hangs), `t` how far (0..1), `reach` 0..1 while he reaches for a grip.
func drive(
	state: int,
	speed: float,
	airborne: bool,
	from: GrabPoint,
	grip: GrabPoint,
	t: float,
	look: Vector3,
	delta: float
) -> void:
	_look.global_position = look
	_speed = lerpf(_speed, speed, 1.0 - exp(-delta / SPEED_SMOOTH))
	_pose.speed = _speed
	_pose.stride_phase = fposmod(_pose.stride_phase + _speed * delta / 1.4, 1.0)
	var on_grip := grip != null and state != Wanderer.State.GROUND
	var standing_on_top := on_grip and grip.normal().dot(Vector3.UP) > 0.7
	_planter.grounded = state == Wanderer.State.GROUND and not airborne
	var want_hands := 0.0
	if on_grip:
		# The targets follow the grip even while the hands let go (standing on top): left
		# behind, the fading hands would trail a point the giant carries away.
		_place_hands(state, from, grip, t)
		if not standing_on_top:
			want_hands = t if state == Wanderer.State.REACHING else 1.0
	_hand_w = move_toward(_hand_w, want_hands, delta / HAND_BLEND)
	if _tree and on_grip and not standing_on_top and _hand_w > 0.5:
		var k := 1.0 - exp(-delta / HANG_SMOOTH)
		hang_reach = lerpf(hang_reach, _planter.hang_reach, k)
		hang_out = lerpf(hang_out, _planter.hang_out, k)
	_hands.influence = smoothstep(0.0, 1.0, _hand_w)
	_stand_t += delta
	if _landing and state == Wanderer.State.GROUND and not airborne:
		_landing = false
		_stand_t = 0.0
	if _tree == null:
		return
	var mode := "ground"
	if on_grip and not standing_on_top:
		mode = "climb"
		_tree.set(P_CLIMB, _climb_slot(state, from, grip))
	elif _stand_t < _stand_len:
		mode = "stand"
	elif airborne:
		mode = "fall"
	if mode != _mode:
		_mode = mode
		_tree.set(P_MODE, mode)
	_tree.set(P_LOCO, minf(_speed, Wanderer.RUN))
	_tree.set(P_SCALE, _loco_scale(_speed))


## Head, hands (where they hold, while they hold) and hips in the world: what a close shot frames.
func upper_body() -> PackedVector3Array:
	var xf := skeleton.global_transform
	var hands := (_hand_l.global_position + _hand_r.global_position) * 0.5
	if _hand_w < 0.5:
		hands = (
			xf
			* (
				(
					skeleton.get_bone_global_pose(skeleton.find_bone("LeftHand")).origin
					+ skeleton.get_bone_global_pose(skeleton.find_bone("RightHand")).origin
				)
				* 0.5
			)
		)
	return PackedVector3Array(
		[
			xf * skeleton.get_bone_global_pose(skeleton.find_bone("Head")).origin,
			hands,
			xf * skeleton.get_bone_global_pose(skeleton.find_bone("Hips")).origin,
		]
	)


## He let go of the Colossus: stand up once he is on the ground.
func landed() -> void:
	_landing = true


## Time scale of the walk blend: each clip at the speed whose planted foot does not slide.
func _loco_scale(v: float) -> float:
	var w := Wanderer.WALK / walk_speed if walk_speed > 0.0 else 1.0
	var r := Wanderer.RUN / run_speed if run_speed > 0.0 else w
	return lerpf(w, r, clampf((v - Wanderer.WALK) / (Wanderer.RUN - Wanderer.WALK), 0.0, 1.0))


func _climb_slot(state: int, from: GrabPoint, grip: GrabPoint) -> String:
	if state != Wanderer.State.MOVING or from == null or from == grip:
		return "hang_idle"
	var d := from.global_transform.basis.inverse() * (grip.global_position - from.global_position)
	if absf(d.y) >= absf(d.x):
		return "climb_up" if d.y > 0.0 else "climb_down"
	return "shimmy_right" if d.x > 0.0 else "shimmy_left"


## Hands on the grip, apart along the surface. Moving between grips the leading hand goes first
## (first half), the other follows (second half).
func _place_hands(state: int, from: GrabPoint, grip: GrabPoint, t: float) -> void:
	var side := grip.global_transform.basis.x.normalized()
	var n := grip.normal()
	var to_l := grip.global_position - side * HAND_SPREAD + n * 0.05
	var to_r := grip.global_position + side * HAND_SPREAD + n * 0.05
	if state == Wanderer.State.MOVING and from != null and from != grip:
		var fside := from.global_transform.basis.x.normalized()
		var at_l := from.global_position - fside * HAND_SPREAD + from.normal() * 0.05
		var at_r := from.global_position + fside * HAND_SPREAD + from.normal() * 0.05
		if from != _move_from or grip != _move_to:
			# Decided once per move: sideways the hand on that side leads, up or down they take
			# turns. Recomputed every tick, a move straight up flips it as the giant sways.
			_move_from = from
			_move_to = grip
			var d := grip.global_position - from.global_position
			var across := d.dot(side)
			_right_leads = across > 0.0 if absf(across) > 0.3 * d.length() else not _right_leads
		var right_leads := _right_leads
		var lead := smoothstep(0.0, 0.55, t)
		var trail := smoothstep(0.45, 1.0, t)
		to_l = at_l.lerp(to_l, trail if right_leads else lead)
		to_r = at_r.lerp(to_r, lead if right_leads else trail)
	_hand_l.global_position = to_l
	_hand_r.global_position = to_r
	# Elbow poles in the body's own space (the Nomad faces +Z, his left is +X): out to the side,
	# behind and below the shoulders. Off the grip's frame they would swing with the giant's
	# rolling surface and flip an elbow.
	_elbow_l.global_position = global_transform * ELBOW_POLE
	_elbow_r.global_position = global_transform * (ELBOW_POLE * Vector3(-1.0, 1.0, 1.0))
