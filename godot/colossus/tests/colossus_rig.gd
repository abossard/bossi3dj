extends SceneTree
## The first Colossus of the roster on its rig, in numbers, headless: the Grab Path reaches the
## head, the feet stay on the land while it walks (ankle height, planted-foot slide), it stands
## while carrying, and its ragdoll settles on flat and on sloped ground (time, chest height, no body
## flung off). Own OSC port, no Syphon.
## Godot --headless --path godot/colossus --script res://tests/colossus_rig.gd

const TEST_PORT := 19202
const PLANTED := 0.05
const MAX_BODIES := 24

var main: ColossusMain
var _failed := 0


func _initialize() -> void:
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


static func _percentile(values: Array, p: float) -> float:
	if values.is_empty():
		return 0.0
	var v := values.duplicate()
	v.sort()
	return v[mini(int(p * v.size()), v.size() - 1)]


func _skeleton(c: Colossus) -> Skeleton3D:
	return c.find_child("Skeleton3D", true, false) as Skeleton3D


func _feet(c: Colossus) -> Array[Vector3]:
	var s := _skeleton(c)
	var out: Array[Vector3] = []
	for b in s.get_bone_count():
		if s.get_bone_name(b).to_lower().begins_with("foot"):
			out.append(s.global_transform * s.get_bone_global_pose(b).origin)
	return out


## A spot within the roaming area where the land tilts at least `deg` degrees, or the arena.
func _slope(deg: float) -> Vector3:
	var h: Callable = main.world.height_at
	for r in range(100, 1400, 50):
		for k in 16:
			var a := k * TAU / 16.0
			var p := Land.ARENA + Vector3(cos(a), 0.0, sin(a)) * r
			var dx: float = h.call(p.x + 5.0, p.z) - h.call(p.x - 5.0, p.z)
			var dz: float = h.call(p.x, p.z + 5.0) - h.call(p.x, p.z - 5.0)
			if rad_to_deg(atan(Vector2(dx, dz).length() / 10.0)) >= deg:
				return p
	return Land.ARENA


func _fall_on(at: Vector3, label: String) -> void:
	main.arc.send(Arc.Event.RESET_NOW)
	await create_timer(1.0).timeout
	while main.arc.phase != Arc.Phase.APPROACH:
		await create_timer(0.25).timeout
	# Three Resets bring the first Colossus back.
	while main.colossus.name != Roster.ENTRIES[0]["name"]:
		main.arc.send(Arc.Event.RESET_NOW)
		await create_timer(1.0).timeout
		while main.arc.phase != Arc.Phase.APPROACH:
			await create_timer(0.25).timeout
	var c := main.colossus
	c.reset_to(at, 0.0)
	await create_timer(1.0).timeout
	main.arc.send(Arc.Event.NEXT)
	main.arc.send(Arc.Event.NEXT)
	var t := 0.0
	while c.state != Colossus.State.DOWN and t < 15.0:
		await create_timer(0.1).timeout
		t += 0.1
	await create_timer(1.0).timeout
	var bodies := c.find_children("*", "PhysicalBone3D", true, false)
	var centre := c.center()
	var land: float = main.world.height_at(centre.x, centre.z)
	var far := 0.0
	var fast := 0.0
	for b: PhysicalBone3D in bodies:
		far = maxf(far, b.global_position.distance_to(centre))
		fast = maxf(fast, b.linear_velocity.length())
	print(
		(
			(
				"fall on %s: down after %.1f s, chest %.1f m above the land, farthest body %.1f m"
				+ " from it, fastest %.2f m/s"
			)
			% [label, t, centre.y - land, far, fast]
		)
	)
	_check(c.state == Colossus.State.DOWN and t < 12.0, "fall on %s settles" % label)
	_check(far < c.height_m, "fall on %s: no body flung off" % label)
	_check(centre.y - land < c.height_m * 0.35, "fall on %s: the body lies on the land" % label)


func _run() -> void:
	await create_timer(1.0).timeout
	var c := main.colossus
	print("colossus %s, class %s" % [c.name, c.get_script().get_global_name()])
	var bodies := c.find_children("*", "PhysicalBone3D", true, false).size()
	print("ragdoll bodies %d" % bodies)
	_check(bodies > 0 and bodies <= MAX_BODIES, "at most %d ragdoll bodies" % MAX_BODIES)
	var points := c.grab_points()
	var links: Array[PackedInt32Array] = []
	for p in points:
		var idx := PackedInt32Array()
		for q in p.linked():
			idx.append(points.find(q))
		links.append(idx)
	_check(
		GrabPath.all_reach(points.find(c.head_point()), links),
		"the Grab Path reaches the head from all %d Grab Points" % points.size()
	)
	# Walking: the Wanderer far away, the Colossus roams.
	main.wanderer.place_at(c.global_position + Vector3(0.0, 0.0, 900.0))
	var ankles := []
	var slides := []
	var last: Array[Vector3] = _feet(c)
	var low := INF
	var samples: Array = []
	for i in 360:
		await physics_frame
		await _skeleton(c).skeleton_updated
		var feet := _feet(c)
		samples.append(feet)
		for f in feet:
			var land: float = main.world.height_at(f.x, f.z)
			ankles.append(f.y - land)
			low = minf(low, f.y - land)
	for i in range(1, samples.size()):
		for f in samples[i].size():
			var a: Vector3 = samples[i - 1][f]
			var b: Vector3 = samples[i][f]
			if a.y - main.world.height_at(a.x, a.z) < low + PLANTED:
				slides.append(Vector2(b.x - a.x, b.z - a.z).length() * 60.0)
	print(
		(
			(
				"walking: ankle %.2f m above the land lowest, %.2f median; planted foot slides"
				+ " %.2f m/s median, %.2f p90 (%d)"
			)
			% [
				low,
				_percentile(ankles, 0.5),
				_percentile(slides, 0.5),
				_percentile(slides, 0.9),
				slides.size()
			]
		)
	)
	_check(low > -0.2, "walking: no foot sinks into the land")
	# Carrying: he holds on to the lowest Grab Point, it stands.
	main.wanderer.place_at(c.global_position + c.global_transform.basis.z * 6.0)
	await create_timer(0.5).timeout
	main.wanderer.grab(main.wanderer.nearest_grip(30.0))
	await create_timer(1.5).timeout
	var at := c.global_position
	var yaw := c.rotation.y
	await create_timer(3.0).timeout
	print(
		(
			"carrying: moved %.2f m, turned %.2f deg in 3 s"
			% [c.global_position.distance_to(at), rad_to_deg(absf(c.rotation.y - yaw))]
		)
	)
	_check(c.global_position.distance_to(at) < 0.01, "carrying: it stands")
	main.wanderer.let_go()
	await _fall_on(Land.ARENA, "flat ground")
	var slope := _slope(12.0)
	var dx: float = (
		main.world.height_at(slope.x + 5.0, slope.z) - main.world.height_at(slope.x - 5.0, slope.z)
	)
	var dz: float = (
		main.world.height_at(slope.x, slope.z + 5.0) - main.world.height_at(slope.x, slope.z - 5.0)
	)
	print(
		(
			"slope at %s: %.0f degrees"
			% [slope.round(), rad_to_deg(atan(Vector2(dx, dz).length() / 10.0))]
		)
	)
	slope.y = main.world.height_at(slope.x, slope.z)
	await _fall_on(slope, "sloped ground")
	print("colossus_rig: %s" % ("passed" if _failed == 0 else "%d failed" % _failed))
	quit(1 if _failed > 0 else 0)
