extends SceneTree
## Does the fill light raise the median frame time? On and off alternate in one run, so foreign
## load on the machine hits both the same. Metal keeps the display link even with vsync switched
## off and has no GPU timer, so the median sits at 16.7 ms while the work fits a frame: it shows
## only a change that pushes the frame over. A verdict on fps needs `make status` to say
## fps_trustworthy; this comparison inside one run does not.
## Godot --path godot/colossus --script res://tests/cost.gd

const TEST_PORT := 19202
const ROUNDS := 4
const FRAMES := 150
const SKIP := 30

var main: ColossusMain


func _initialize() -> void:
	main = load("res://main.tscn").instantiate()
	main.syphon_enabled = false
	main.osc_port = TEST_PORT
	main.page_port = 0
	root.add_child(main)
	main.set_process_unhandled_input(false)
	_run()


func _median_ms() -> float:
	var times: Array[float] = []
	var last := Time.get_ticks_usec()
	for f in FRAMES:
		await RenderingServer.frame_post_draw
		var now := Time.get_ticks_usec()
		if f >= SKIP:
			times.append((now - last) / 1000.0)
		last = now
	times.sort()
	return times[times.size() / 2]


func _run() -> void:
	await create_timer(5.0).timeout
	var on: Array[float] = []
	var off: Array[float] = []
	for r in ROUNDS:
		for want in [true, false]:
			main.world.fill.visible = want
			var m: float = await _median_ms()
			(on if want else off).append(m)
			print("round %d  fill %s  median frame %.2f ms" % [r, want, m])
	on.sort()
	off.sort()
	print(
		(
			"median over rounds: fill on %.2f ms, off %.2f ms"
			% [on[on.size() / 2], off[off.size() / 2]]
		)
	)
	quit()
