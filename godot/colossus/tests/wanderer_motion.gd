extends SceneTree
## How the Nomad moves, in numbers, headless: the pose at rest, foot sliding while he walks and
## runs, joint speed at every change of state (a pop is a spike far above the steady motion), the
## hands on the grips while he climbs, the head toward the Colossus. Needs the Nomad model
## (assets/MODELS.md); reports which clips played and which fell back. Own OSC port, no Syphon.
## Godot --headless --path godot/colossus --script res://tests/wanderer_motion.gd

const TEST_PORT := 19202
## A planted foot is within this height of its lowest over the section (m).
const PLANTED := 0.03
## Change of a joint's velocity in one tick (m/s) above which a frame counts as a pop: a clip at
## a fast step changes it by 1 to 2 m/s per tick.
const POP := 4.0

var main: ColossusMain
var body: WandererBody
var _bones := PackedInt32Array()
var _last := PackedVector3Array()
var _vel := PackedVector3Array()
var _failed := 0
var _fastest_bone := ""


func _initialize() -> void:
	if not Wanderer.model_present():
		print("the Nomad is missing: see godot/colossus/assets/MODELS.md (make godot-models)")
		quit(1)
		return
	main = load("res://main.tscn").instantiate()
	main.syphon_enabled = false
	main.osc_port = TEST_PORT
	main.page_port = 0
	root.add_child(main)
	main.set_process_unhandled_input(false)
	_run()


func _check(ok: bool, what: String) -> void:
	print("%s  %s" % ["pass" if ok else "FAIL", what])
	if not ok:
		_failed += 1


func _bone(name: String) -> Vector3:
	var s := body.skeleton
	return s.global_transform * s.get_bone_global_pose(s.find_bone(name)).origin


## The largest change of a joint's world velocity within one tick (m/s): a pop is a jump of the
## pose, which shows as a velocity that changes at once; fast smooth motion (the body leaping to a
## grip with the hands held on it) does not count.
## Forget the last pose: the probe moved the body itself (place_at), not a pop.
func _reset_joints() -> void:
	_last.clear()
	_vel.clear()


func _joint_speed(dt: float) -> float:
	var s := body.skeleton
	var xf := s.global_transform
	var worst := 0.0
	var fresh := _last.size() < _bones.size()
	for i in _bones.size():
		var p := s.get_bone_global_pose(_bones[i]).origin
		if fresh:
			_last.append(p)
			_vel.append(Vector3.INF)
			continue
		var v := (p - _last[i]) / maxf(dt, 1e-4)
		# The first velocity after a reset has nothing to change from.
		var change := 0.0 if _vel[i] == Vector3.INF else v.distance_to(_vel[i])
		if change > worst:
			worst = change
			_fastest_bone = s.get_bone_name(_bones[i])
		_last[i] = p
		_vel[i] = v
	return worst


## Samples `seconds` of physics ticks: joint speed per tick, feet (world) and the Wanderer state.
func _sample(seconds: float) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var t := 0.0
	while t < seconds:
		# One sample per physics tick, read when the skeleton has finished its modifiers: outside
		# that, Godot holds the pose without them.
		await physics_frame
		await body.skeleton.skeleton_updated
		var dt := get_root().get_physics_process_delta_time() * Engine.time_scale
		t += dt / Engine.time_scale
		(
			out
			. append(
				{
					"dt": dt,
					"joint": _joint_speed(dt),
					"bone": _fastest_bone,
					"feet": [_bone("LeftFoot"), _bone("RightFoot")],
					"state": main.wanderer.state,
					"speed": Vector2(main.wanderer.velocity.x, main.wanderer.velocity.z).length(),
					"hands": [_bone("LeftHand"), _bone("RightHand")],
					"targets": [body._hand_l.global_position, body._hand_r.global_position],
					"hand_w": body._hands.influence,
					"grip": main.wanderer.grip,
					"pos": main.wanderer.global_position,
					"yaw": main.wanderer.rotation.y,
					"t": main.wanderer._t,
				}
			)
		)
	return out


static func _percentile(values: Array, p: float) -> float:
	if values.is_empty():
		return 0.0
	var v := values.duplicate()
	v.sort()
	return v[mini(int(p * v.size()), v.size() - 1)]


## Horizontal speed of each planted foot (m/s): planted means within PLANTED of the foot's lowest
## height above the land over the section, in two ticks running.
func _slide(samples: Array[Dictionary]) -> Dictionary:
	var slides := []
	for f in 2:
		var low := INF
		for s in samples:
			var p: Vector3 = s["feet"][f]
			low = minf(low, p.y - main.world.height_at(p.x, p.z))
		for i in range(1, samples.size()):
			var a: Vector3 = samples[i - 1]["feet"][f]
			var b: Vector3 = samples[i]["feet"][f]
			var ha := a.y - main.world.height_at(a.x, a.z)
			var hb := b.y - main.world.height_at(b.x, b.z)
			if ha < low + PLANTED and hb < low + PLANTED:
				slides.append(Vector2(b.x - a.x, b.z - a.z).length() / samples[i]["dt"])
	var speeds := []
	for s in samples:
		speeds.append(s["speed"])
	return {
		"median": _percentile(slides, 0.5),
		"p90": _percentile(slides, 0.9),
		"planted_ticks": slides.size(),
		"speed": _percentile(speeds, 0.5),
	}


func _joints(samples: Array[Dictionary]) -> Dictionary:
	var j := []
	for s in samples.slice(1):
		j.append(s["joint"])
	return {"p50": _percentile(j, 0.5), "max": _percentile(j, 1.0)}


func _run() -> void:
	await create_timer(1.0).timeout
	body = main.wanderer.body
	var s := body.skeleton
	for b in s.get_bone_count():
		var n := s.get_bone_name(b)
		if not (
			n.contains("Index")
			or n.contains("Middle")
			or n.contains("Ring")
			or n.contains("Little")
			or n.contains("Thumb")
		):
			_bones.append(b)
	var played := []
	var borrowed := []
	for slot: String in body.resolved:
		var r: Array = body.resolved[slot]
		if r[0] == slot:
			played.append(slot)
		else:
			borrowed.append(
				"%s<-%s%s" % [slot, r[0] if r[0] != "" else "pose", " (held)" if r[1] else ""]
			)
	print("clips played: %s" % ", ".join(played))
	print("slots on a fallback: %s" % ", ".join(borrowed))
	print(
		(
			"stride speed: walk %.2f m/s, run %.2f m/s (Wanderer walks %.1f, runs %.1f); hang reach %.2f m"
			% [body.walk_speed, body.run_speed, Wanderer.WALK, Wanderer.RUN, body.hang_reach]
		)
	)
	var c := main.colossus
	c.process_mode = Node.PROCESS_MODE_DISABLED
	var w := main.wanderer
	var to_c := Vector3(0.0, 0.0, 1.0)
	# Idle: inside the distance at which he waits for the Colossus.
	w.place_at(c.global_position + to_c * 40.0)
	w.rotation.y = 0.0
	await create_timer(2.0).timeout
	_reset_joints()
	var idle := await _sample(2.0)
	var origin := w.global_position
	var feet_y := minf(_bone("LeftFoot").y, _bone("RightFoot").y) - origin.y
	var head_y := _bone("Head").y - origin.y
	var hand_y := maxf(_bone("LeftHand").y, _bone("RightHand").y) - origin.y
	print(
		(
			"idle: ankles %.2f m above the origin, head %.2f m, highest hand %.2f m"
			% [feet_y, head_y, hand_y]
		)
	)
	_check(feet_y > -0.05 and feet_y < 0.2, "idle: feet on the ground")
	_check(head_y > 1.4 and head_y < 1.8, "idle: head at standing height")
	_check(hand_y < 1.2, "idle: arms down (no T-pose)")
	# The head's forward (+Z of the bone) against the line to the Colossus's head.
	await physics_frame
	await body.skeleton.skeleton_updated
	var sk := body.skeleton
	var head := sk.global_transform * sk.get_bone_global_pose(sk.find_bone("Head"))
	var to_head := c.head_point().global_position - head.origin
	var gaze := rad_to_deg(head.basis.z.normalized().angle_to(to_head.normalized()))
	var rise := rad_to_deg(asin(to_head.normalized().y))
	print(
		(
			"idle: the Colossus head is %.0f degrees up; the head looks %.0f degrees off it"
			% [rise, gaze]
		)
	)
	_check(gaze < rise, "idle: the head turns toward the Colossus")
	print("idle joints: %s" % _joints(idle))
	# Walk: from idle into a walk toward the Colossus (Approach), then steady.
	w.place_at(c.global_position + to_c * 200.0)
	_reset_joints()
	var start := await _sample(1.5)
	var walk := await _sample(6.0)
	var ws := _slide(walk)
	print(
		(
			"walk %.2f m/s: planted foot slides median %.3f m/s, p90 %.3f m/s over %d planted ticks"
			% [ws["speed"], ws["median"], ws["p90"], ws["planted_ticks"]]
		)
	)
	var steady := _joints(walk)
	print("walk joints: %s; idle to walk: %s" % [steady, _joints(start)])
	_check(_joints(start)["max"] < POP, "idle to walk: no pop (velocity jump under %.0f m/s)" % POP)
	# Climb: he runs to the nearest grip, reaches, hangs and climbs.
	c.process_mode = Node.PROCESS_MODE_INHERIT
	w.place_at(c.global_position + to_c * 30.0)
	_reset_joints()
	main.arc.send(Arc.Event.NEXT)
	var climb := await _sample(25.0)
	var run_part: Array[Dictionary] = []
	for x in climb:
		if x["state"] == Wanderer.State.GROUND and x["speed"] > 3.0:
			run_part.append(x)
	var rs := _slide(run_part)
	# A change of state may jump as much as the steady motion it leaves (the run's foot strike).
	var steady_max := maxf(_joints(walk)["max"], _joints(run_part)["max"])
	print("run joints: %s" % _joints(run_part))
	print(
		(
			"run %.2f m/s: planted foot slides median %.3f m/s, p90 %.3f m/s over %d planted ticks"
			% [rs["speed"], rs["median"], rs["p90"], rs["planted_ticks"]]
		)
	)
	var transitions := {}
	var hand_err := []
	var miss := Vector3.ZERO
	for i in range(1, climb.size()):
		var a: Dictionary = climb[i - 1]
		var b: Dictionary = climb[i]
		if a["state"] != b["state"]:
			var key := (
				"%s to %s" % [Wanderer.State.keys()[a["state"]], Wanderer.State.keys()[b["state"]]]
			)
			var window := climb.slice(maxi(i - 5, 1), mini(i + 25, climb.size()))
			var m: float = _joints(window)["max"]
			if m > transitions.get(key, 0.0):
				transitions[key] = m
				var who := ""
				for x in window:
					if x["joint"] >= m:
						who = "%s at %+d ticks" % [x["bone"], window.find(x) - (i - maxi(i - 5, 1))]
				print("    %s peak: %s" % [key, who])
		if b["state"] == Wanderer.State.HANGING and b["hand_w"] > 0.99:
			for h in 2:
				hand_err.append((b["hands"][h] as Vector3).distance_to(b["targets"][h]))
				var g: GrabPoint = b["grip"]
				miss += (
					g.global_transform.basis.inverse()
					* ((b["targets"][h] as Vector3) - (b["hands"][h] as Vector3))
				)
	print("climb joints: %s" % _joints(climb))
	var worst := 1
	for i in range(1, climb.size()):
		if climb[i]["state"] != Wanderer.State.GROUND and climb[i]["joint"] > climb[worst]["joint"]:
			worst = i
	for i in range(maxi(worst - 3, 1), mini(worst + 3, climb.size())):
		var a: Dictionary = climb[i - 1]
		var b: Dictionary = climb[i]
		print(
			(
				(
					"  tick %d %s state %d t %.2f jump %.1f: target moved %.3f m, body %.3f m,"
					+ " yaw %.3f, same grip %s, hand w %.2f"
				)
				% [
					i,
					b["bone"],
					b["state"],
					b["t"],
					b["joint"],
					(b["targets"][0] as Vector3).distance_to(a["targets"][0]),
					(b["pos"] as Vector3).distance_to(a["pos"]),
					b["yaw"] - a["yaw"],
					b["grip"] == a["grip"],
					b["hand_w"],
				]
			)
		)
	for k: String in transitions:
		print("  %s: largest velocity jump %.1f m/s" % [k, transitions[k]])
		var bar := maxf(POP, steady_max) if k.begins_with("GROUND") else POP
		_check(transitions[k] <= bar, "%s: no pop (at most %.1f m/s)" % [k, bar])
	print(
		(
			"hands on the grip while hanging: median %.3f m, p90 %.3f m from the target (%d samples)"
			% [_percentile(hand_err, 0.5), _percentile(hand_err, 0.9), hand_err.size()]
		)
	)
	print("hang offsets now: reach %.2f m, out %.2f m" % [body.hang_reach, body.hang_out])
	print(
		(
			"hand to target, summed in the grip's frame (x side, y up, z out of the surface): %s"
			% (miss / maxf(hand_err.size(), 1))
		)
	)
	_check(w.on_colossus(), "climbing after 25 s")
	_check(not hand_err.is_empty() and _percentile(hand_err, 0.5) < 0.1, "hands on the grip")
	# Fall: he rides the body down, lets go on impact and stands up.
	main.arc.send(Arc.Event.NEXT)
	var fall: Array[Dictionary] = []
	while main.arc.phase == Arc.Phase.FALL and fall.size() < 900:
		fall.append_array(await _sample(0.25))
	var fall_tr := {}
	for i in range(1, fall.size()):
		if fall[i - 1]["state"] != fall[i]["state"]:
			var key := (
				"%s to %s"
				% [
					Wanderer.State.keys()[fall[i - 1]["state"]],
					Wanderer.State.keys()[fall[i]["state"]]
				]
			)
			fall_tr[key] = _joints(fall.slice(maxi(i - 5, 1), mini(i + 40, fall.size())))["max"]
	for k: String in fall_tr:
		print("  fall %s: largest velocity jump %.1f m/s" % [k, fall_tr[k]])
	print("fall joints: %s" % _joints(fall))
	print("wanderer_motion: %s" % ("passed" if _failed == 0 else "%d failed" % _failed))
	quit(1 if _failed > 0 else 0)
