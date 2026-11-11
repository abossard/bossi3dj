extends SceneTree
## Which of Grock's own clips could be the Shake? For each clip (and none, the roll alone): the
## Wanderer climbs onto the Colossus, hangs on a Grab Point, a Shake plays, and over its
## SHAKE_SECONDS the probe reads the distance of each of his hands to its IK target (m), how far
## the Grab Point he holds travels from where it was, and its fastest speed. Headless, needs both
## models. Own OSC port, no Syphon.
## Godot --headless --path godot/colossus --script res://tests/shake_clips.gd -- [<climb seconds>]

const TEST_PORT := 19202
## The hands stay on their Grab Points when the largest miss stays under this (m).
const HANDS_ON := 0.05
const CLIPS := ["", "Attack1", "Attack2", "Attack3", "Defend1", "Defend2", "Defend3"]

var main: ColossusMain
var body: WandererBody


func _initialize() -> void:
	if not Wanderer.model_present() or not GrockColossus.model_present():
		print("a model is missing: see godot/colossus/assets/MODELS.md (make godot-models)")
		quit(1)
		return
	main = load("res://main.tscn").instantiate()
	main.syphon_enabled = false
	main.osc_port = TEST_PORT
	main.page_port = 0
	root.add_child(main)
	main.set_process_unhandled_input(false)
	_run()


static func _percentile(values: Array, p: float) -> float:
	if values.is_empty():
		return 0.0
	var v := values.duplicate()
	v.sort()
	return v[mini(int(p * v.size()), v.size() - 1)]


func _bone(bone_name: String) -> Vector3:
	var s := body.skeleton
	return s.global_transform * s.get_bone_global_pose(s.find_bone(bone_name)).origin


func _hang() -> void:
	var c := main.colossus
	main.wanderer.place_at(c.global_position + c.global_transform.basis.z * 6.0)
	main.arc.send(Arc.Event.NEXT)
	Engine.time_scale = 3.0
	var t := 0.0
	while main.wanderer.state != Wanderer.State.HANGING and t < 40.0:
		await create_timer(0.25).timeout
		t += 0.25
	# Let him climb on for the seconds given as an argument (at 3x), to try a higher grip.
	var more := (
		float(OS.get_cmdline_user_args()[0]) if OS.get_cmdline_user_args().size() > 0 else 0.0
	)
	await create_timer(more / 3.0).timeout
	Engine.time_scale = 1.0
	await _hold(1.0)


## Waits `seconds` with the keyboard Takeover held, so he stays on his grip instead of climbing on.
func _hold(seconds: float) -> void:
	var t := 0.0
	while t < seconds:
		main.wanderer_takeover.touch()
		await physics_frame
		t += get_root().get_physics_process_delta_time()


## One Shake with `clip`: [hand miss samples, the grip's travel, its fastest speed, frames].
func _shake(clip: String) -> Dictionary:
	var c := main.colossus as GrockColossus
	c.shake_clip = clip
	var grip := main.wanderer.grip
	var start := grip.global_position
	var last := start
	var miss := []
	var travel := 0.0
	var fastest := 0.0
	var off_grip := 0
	main._shake()
	var t := 0.0
	while t < Colossus.SHAKE_SECONDS + 0.5:
		main.wanderer_takeover.touch()
		await physics_frame
		await body.skeleton.skeleton_updated
		var dt := get_root().get_physics_process_delta_time()
		t += dt
		var now := main.wanderer.grip.global_position
		travel = maxf(travel, now.distance_to(start))
		fastest = maxf(fastest, now.distance_to(last) / dt)
		last = now
		if main.wanderer.state != Wanderer.State.HANGING or body._hands.influence < 0.99:
			off_grip += 1
			continue
		miss.append(_bone("LeftHand").distance_to(body._hand_l.global_position))
		miss.append(_bone("RightHand").distance_to(body._hand_r.global_position))
	return {"miss": miss, "travel": travel, "fastest": fastest, "off_grip": off_grip}


func _run() -> void:
	await create_timer(1.0).timeout
	body = main.wanderer.body
	await _hang()
	print("hanging on %s" % main.wanderer.grip.name)
	for clip: String in CLIPS:
		# The Shake needs its cooldown, and the Wanderer his hands back on the grip.
		await _hold(Colossus.SHAKE_SECONDS + 1.5)
		var r := await _shake(clip)
		var miss: Array = r["miss"]
		print(
			(
				(
					"%-8s hands from target: median %.3f, p95 %.3f, max %.3f m (%s %.0f cm)"
					+ "  grip travels %.2f m, fastest %.1f m/s, %d ticks off the grip"
				)
				% [
					clip if clip != "" else "no clip",
					_percentile(miss, 0.5),
					_percentile(miss, 0.95),
					_percentile(miss, 1.0),
					"on" if _percentile(miss, 1.0) < HANDS_ON else "off",
					HANDS_ON * 100.0,
					r["travel"],
					r["fastest"],
					r["off_grip"],
				]
			)
		)
	quit()
