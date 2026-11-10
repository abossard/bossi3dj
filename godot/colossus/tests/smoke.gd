extends SceneTree
## Headless run of one full Arc.
## Godot --headless --path godot/colossus --script res://tests/smoke.gd

## Never the show's port: a test must not steal or feed the live scene's OSC.
const TEST_PORT := 19202
## C3: once running, a frame at least every 2 s. Wall-clock time is reported, never asserted:
## it swings with whatever else loads the machine (retrospective: "Report it, don't fail").
const WARN_GAP_MS := 2000

var _failed := 0
var _last_frame_ms := 0
var _worst_gap_ms := 0


func _initialize() -> void:
	_run()


func _check(name: String, ok: bool) -> void:
	if ok:
		print("ok   %s" % name)
	else:
		_failed += 1
		printerr("FAIL %s" % name)


func _wait(seconds: float) -> void:
	await create_timer(seconds).timeout


func _wait_until(cond: Callable, limit: float) -> bool:
	var t := 0.0
	while t < limit:
		if cond.call():
			return true
		await create_timer(0.25).timeout
		t += 0.25
	return cond.call()


func _run() -> void:
	Engine.time_scale = 4.0
	var main: ColossusMain = load("res://main.tscn").instantiate()
	main.osc_port = TEST_PORT
	main.syphon_enabled = false
	root.add_child(main)
	await process_frame
	_last_frame_ms = Time.get_ticks_msec()
	print(
		(
			"info first frame %d ms since engine start (%s)"
			% [_last_frame_ms, DisplayServer.get_name()]
		)
	)
	process_frame.connect(
		func() -> void:
			var now := Time.get_ticks_msec()
			_worst_gap_ms = maxi(_worst_gap_ms, now - _last_frame_ms)
			_last_frame_ms = now
	)
	await _wait(0.5)
	var space: PhysicsDirectSpaceState3D = main.world.get_world_3d().direct_space_state
	for p: Vector3 in [Land.ARENA, Land.SHRINE]:
		var ray := PhysicsRayQueryParameters3D.create(
			p + Vector3.UP * 2000.0, p + Vector3.DOWN * 2000.0
		)
		var hit: Dictionary = space.intersect_ray(ray)
		_check(
			"C3 terrain collision under %s" % p,
			not hit.is_empty() and absf(hit.position.y - main.world.height_at(p.x, p.z)) < 0.5
		)
	_check("starts in Approach", main.arc.phase == Arc.Phase.APPROACH)
	_check(
		"Colossus has a Grab Path",
		main.colossus.grab_points().size() >= 10 and main.colossus.head_point() != null
	)
	_check("Wanderer starts on the ground", not main.wanderer.on_colossus())

	var c := main.colossus.global_position
	main.wanderer.place_at(c - main.colossus.global_transform.basis.z * -6.0)
	main.arc.send(Arc.Event.NEXT)
	_check("Next goes to Climb", main.arc.phase == Arc.Phase.CLIMB)
	_check(
		"Wanderer grabs on",
		await _wait_until(func() -> bool: return main.wanderer.on_colossus(), 40.0)
	)
	_check(
		"Wanderer reaches the head",
		await _wait_until(
			func() -> bool: return main.wanderer.grip == main.colossus.head_point(), 120.0
		)
	)

	var udp := PacketPeerUDP.new()
	udp.set_dest_address("127.0.0.1", TEST_PORT)
	udp.put_packet(_osc_float("/vj/shock", 1.0))
	_check("OSC /vj/shock arrives", await _wait_until(func() -> bool: return main.vj.fresh(), 2.0))
	_check(
		"Shake starts while on the Colossus",
		await _wait_until(func() -> bool: return main.colossus.is_shaking(), 2.0)
	)
	var grip := main.wanderer.grip
	var sway := 0.0
	for i in 20:
		sway = maxf(sway, main.wanderer.global_position.distance_to(grip.global_position))
		await _wait(0.05)
	_check("Shake swings the Wanderer at the head", sway > 0.2)
	await _wait(2.0)
	_check("Wanderer still holds after the Shake", main.wanderer.on_colossus())

	var first: String = main.colossus.name
	main.arc.send(Arc.Event.NEXT)
	_check("Next goes to Fall", main.arc.phase == Arc.Phase.FALL)
	_check(
		"Fall settles into Reset before the timeout",
		(
			await _wait_until(func() -> bool: return main.arc.phase == Arc.Phase.RESET, 40.0)
			and main.arc._in_phase < ArcState.FALL_TIMEOUT
		)
	)
	_check("Wanderer let go after the Fall", not main.wanderer.on_colossus())
	_check(
		"Reset returns to Approach",
		await _wait_until(func() -> bool: return main.arc.phase == Arc.Phase.APPROACH, 20.0)
	)
	_check("Reset brought the next Colossus", main.colossus.name != first)
	var slow := " (over %d ms, machine busy?)" % WARN_GAP_MS if _worst_gap_ms >= WARN_GAP_MS else ""
	print("info C3 worst gap between frames %d ms%s" % [_worst_gap_ms, slow])

	print("smoke: %s" % ("passed" if _failed == 0 else "%d failed" % _failed))
	quit(1 if _failed > 0 else 0)


func _osc_float(address: String, v: float) -> PackedByteArray:
	var b := PackedByteArray()
	for part in [address, ",f"]:
		var str_bytes: PackedByteArray = (part as String).to_utf8_buffer()
		str_bytes.append(0)
		while str_bytes.size() % 4 != 0:
			str_bytes.append(0)
		b.append_array(str_bytes)
	var four := PackedByteArray()
	four.resize(4)
	four.encode_float(0, v)
	four.reverse()
	b.append_array(four)
	return b
