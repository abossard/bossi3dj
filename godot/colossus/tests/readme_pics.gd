extends SceneTree
## The frames for the OSC manual in the README, on Metal: for each address the Godot scene reads,
## the output frame at its wire minimum and maximum from one shot and Phase (PNG into <out dir> as
## <name>-low.png and <name>-high.png), the Shake before and during (`shock`), and each director
## shot pinned (`cam-<wire>.png`). The Colossus and the Wanderer are held still for the pairs, so
## only the control differs. `tools/godot_readme_pics.sh` makes the JPEGs and checks each pair by
## number. No Syphon, no page, own OSC port.
## Address, name, wire minimum and maximum, shot (wire) it shows best in, Wanderer gap (m).

const TEST_PORT := 19202
const SETTLE := 2.2
## Wanderer to Colossus gap (m) for the Approach frames: the control pairs, and the footfall pairs.
const GAP := 250.0
const FOOT_GAP := 28.0
## Address, name, wire minimum and maximum, shot (wire value) it shows best in, Wanderer's gap (m).
const PAIRS := [
	["/vj/level", "level", 0.0, 1.0, 0, GAP],
	["/vj/intensity", "intensity", 0.0, 1.0, 0, GAP],
	["/vj/fog", "fog", 0.0, 1.0, 0, GAP],
	["/vj/fog_height", "fog_height", 0.0, 1.0, 0, GAP],
	["/vj/haze", "haze", 0.0, 1.0, 0, 1550.0],
]

var main: ColossusMain
var _out := "/tmp/colossus-readme-pics"


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() > 0:
		_out = args[0]
	DirAccess.make_dir_recursive_absolute(_out)
	main = load("res://main.tscn").instantiate()
	main.syphon_enabled = false
	main.osc_port = TEST_PORT
	main.page_port = 0
	root.add_child(main)
	main.set_process_unhandled_input(false)
	_run()


func _wait(seconds: float) -> void:
	var t := 0.0
	while t < seconds:
		if main.wanderer.on_colossus():
			main.wanderer_takeover.touch()
		await RenderingServer.frame_post_draw
		t += 1.0 / 60.0


func _write(address: String, v: float) -> void:
	main.vj.apply(address, v, VjSignals.SOURCE_PAGE)


func _pin(wire: int) -> void:
	_write("/vj/cam_auto", 0.0)
	_write("/vj/cam", float(wire))
	main.director.snap()


func _save(label: String) -> void:
	await RenderingServer.frame_post_draw
	main.output.get_texture().get_image().save_png("%s/%s.png" % [_out, label])
	print("saved %s shot %d" % [label, main.director.shot])


func _defaults(wire: int) -> void:
	main.vj.reset_defaults()
	_pin(wire)


## The Approach: the Wanderer `gap` m from the Colossus, both held where they are.
func _approach(gap: float) -> void:
	main.arc.send(Arc.Event.RESET_NOW)
	while main.arc.phase != Arc.Phase.APPROACH or main._fade.color.a > 0.0:
		await _wait(0.25)
	await _wait(2.5)
	main.colossus.process_mode = Node.PROCESS_MODE_INHERIT
	main.wanderer.process_mode = Node.PROCESS_MODE_INHERIT
	var c := main.colossus.global_position
	main.wanderer.place_at(Vector3(c.x, 0.0, c.z + gap))
	main.director.snap()
	await _wait(1.0)
	main.colossus.process_mode = Node.PROCESS_MODE_DISABLED
	main.wanderer.process_mode = Node.PROCESS_MODE_DISABLED


## He hangs on the Colossus in a Climb, held on his grip.
func _climb() -> void:
	main.arc.send(Arc.Event.RESET_NOW)
	while main.arc.phase != Arc.Phase.APPROACH or main._fade.color.a > 0.0:
		await _wait(0.25)
	await _wait(2.5)
	main.colossus.process_mode = Node.PROCESS_MODE_INHERIT
	main.wanderer.process_mode = Node.PROCESS_MODE_INHERIT
	var c := main.colossus
	main.wanderer.place_at(c.global_position + c.global_transform.basis.z * 6.0)
	main.arc.send(Arc.Event.NEXT)
	Engine.time_scale = 3.0
	var t := 0.0
	while main.wanderer.state != Wanderer.State.HANGING and t < 40.0:
		await create_timer(0.25).timeout
		t += 0.25
	Engine.time_scale = 1.0
	await _wait(1.0)


func _run() -> void:
	await create_timer(5.0).timeout
	_write("/vj/cam_auto", 0.0)
	var only := OS.get_cmdline_user_args()[1] if OS.get_cmdline_user_args().size() > 1 else ""
	var at_gap := -1.0
	for p: Array in PAIRS:
		if only != "" and not only.contains(p[1]):
			continue
		if p[5] != at_gap:
			at_gap = p[5]
			await _approach(at_gap)
		_defaults(p[4])
		_write(p[0], p[2])
		await _wait(SETTLE)
		await _save("%s-low" % p[1])
		_write(p[0], p[3])
		await _wait(SETTLE)
		await _save("%s-high" % p[1])
	_defaults(0)
	# The shots that need no climb.
	for wire in [0, 1] if only == "" else []:
		_pin(wire)
		await _wait(SETTLE)
		await _save("cam-%d" % wire)
	# Footfalls: the Wanderer close, the Colossus held (its footfall is the signal's doing).
	if only != "" and not only.contains("bass") and not only.contains("beat"):
		await _climb_part()
		quit()
		return
	await _approach(FOOT_GAP)
	for level in [0.0, 1.0] if only.contains("bass") or only == "" else []:
		_defaults(1)
		_write("/vj/bass", level)
		await _wait(0.5)
		await _save("bass-%s" % ("low" if level == 0.0 else "high"))
		var c := main.colossus
		main._on_footfall(_toward_camera(c), c.weight)
		await _wait(1.5)
		await _save("bass-%s-foot" % ("low" if level == 0.0 else "high"))
	if only == "" or only.contains("beat"):
		_defaults(1)
		await _wait(SETTLE)
		await _save("beat-low")
		_write("/vj/beat", 1.0)
		var c2 := main.colossus
		main._on_footfall(_toward_camera(c2), c2.weight)
		await _wait(1.5)
		await _save("beat-high")
		_write("/vj/beat", 0.0)
	if only == "":
		await _climb_part()
	quit()


## A footfall point 6 m from the Colossus on the camera's side.
func _toward_camera(c: Colossus) -> Vector3:
	var to_cam := main.output.get_camera_3d().global_position - c.global_position
	to_cam.y = 0.0
	return c.global_position + to_cam.normalized() * 6.0


## The Climb: the shots on the Colossus, and the Shake.
func _climb_part() -> void:
	_defaults(2)
	await _climb()
	for wire in [2, 3, 4]:
		_pin(wire)
		await _wait(SETTLE + 1.0)
		await _save("cam-%d" % wire)
	_pin(3)
	await _wait(SETTLE + 1.0)
	await _save("shock-low")
	main._shake()
	await _wait(0.5)
	await _save("shock-high")
