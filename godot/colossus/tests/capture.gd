extends SceneTree
## Renders one Arc on the real renderer and saves the output frame of each Phase as PNG.
## Godot --path godot/colossus --script res://tests/capture.gd -- <out_dir>

const TEST_PORT := 19202

var main: ColossusMain
var _out := "user://capture"


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if not args.is_empty():
		_out = args[0]
	DirAccess.make_dir_recursive_absolute(_out)
	_run()


func _wait(seconds: float) -> void:
	await create_timer(seconds).timeout


func _wait_until(cond: Callable, limit: float) -> void:
	var t := 0.0
	while not cond.call() and t < limit:
		await _wait(0.25)
		t += 0.25
	if not cond.call():
		printerr("capture: gave up waiting after %.0f s" % limit)


func _save(label: String) -> void:
	await RenderingServer.frame_post_draw
	var img := main.output.get_texture().get_image()
	var path := "%s/%s.png" % [_out, label]
	img.save_png(path)
	print("saved %s  shot %d  %d fps" % [path, main.director.shot, Engine.get_frames_per_second()])


func _run() -> void:
	main = load("res://main.tscn").instantiate()
	main.syphon_enabled = OS.get_environment("CAPTURE_SYPHON") != "0"
	main.syphon_server = "COLOSSUS_TEST"
	main.osc_port = TEST_PORT
	root.add_child(main)
	# A mouse resting over the window would start a camera Takeover and change the shots.
	main.set_process_unhandled_input(false)

	print(
		(
			"driver %s  syphon %s"
			% [
				RenderingServer.get_current_rendering_driver_name(),
				ClassDB.class_exists("SyphonOutput")
			]
		)
	)
	await _wait(4.0)
	main.director.force(Shots.Shot.SCALE_WIDE)
	await _wait(1.5)
	await _save("1-approach-scale-wide")
	main.director.force(Shots.Shot.LOW_HERO)
	await _wait(1.5)
	await _save("2-approach-low-hero")

	var c := main.colossus.global_position
	main.wanderer.place_at(c + main.colossus.global_transform.basis.z * 6.0)
	main.arc.send(Arc.Event.NEXT)
	Engine.time_scale = 3.0
	await _wait_until(func() -> bool: return main.wanderer.on_colossus(), 30.0)
	await _wait(1.0)
	Engine.time_scale = 1.0
	main.director.force(Shots.Shot.OVER_SHOULDER)
	await _wait(1.5)
	await _save("3-climb-over-shoulder")
	main._shake()
	await _wait(0.5)
	await _save("4-shake-close-grip")
	main.director.force(Shots.Shot.AERIAL)
	await _wait(2.0)
	await _save("5-climb-aerial")

	main.arc.send(Arc.Event.NEXT)
	main.director.force(Shots.Shot.SCALE_WIDE)
	await _wait(2.4)
	await _save("6-fall-toppling")
	await _wait(3.0)
	await _save("7-fall-down")
	await _wait_until(func() -> bool: return main.arc.phase == Arc.Phase.RESET, 30.0)
	await _wait(1.0)
	await _save("8-reset-fade")
	await _wait_until(func() -> bool: return main.arc.phase == Arc.Phase.APPROACH, 30.0)
	await _wait(2.0)
	await _save("9-next-colossus")
	quit()
