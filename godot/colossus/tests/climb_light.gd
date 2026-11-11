extends SceneTree
## How dark are the climb shots, and what lifts them? On Metal: the Wanderer climbs onto the
## Colossus (as tests/capture.gd does), he is held on his grip, and for each lighting
## variant the over-shoulder and the close grip shot are grabbed: mean luma (0..255), the share of
## near-black pixels (luma under 8) and of the lowest quarter (luma under 30), and the median
## frame time of 60 frames with vsync off. Variants are lights hung on the director (a camera-
## relative lamp: energy, pitch, colour) and Environment, light or rock-shader properties. Own OSC
## port, no Syphon.
## Godot --path godot/colossus --script res://tests/climb_light.gd -- [<variant label prefix>]

const TEST_PORT := 19202
const SETTLE_FRAMES := 90
const COST_FRAMES := 60
## The variant list runs this many times over, so the frame times can be read as medians.
const REPEATS := 3
## Label and the /vj/cam wire value that pins the shot.
const SHOTS := [["over-shoulder", 2], ["close grip", 3]]

## label, then property writes: [path, value] (World member:property, env:property for the
## Environment, director:property, rock:parameter of Grock's shader).
const VARIANTS := [
	["as is", []],
	["no shot look", [["director:shot_look", false]]],
	["no rock detail", [["rock:detail_strength", 0.0], ["rock:tint_strength", 0.0]]],
	["flat model normal", [["rock:model_normal", 0.0]]],
]

var main: ColossusMain


func _initialize() -> void:
	main = load("res://main.tscn").instantiate()
	main.syphon_enabled = false
	main.osc_port = TEST_PORT
	main.page_port = 0
	root.add_child(main)
	main.set_process_unhandled_input(false)
	_run()


## Draws `count` frames with the keyboard Takeover held, so the Wanderer stays on his grip.
func _frames(count: int) -> void:
	for i in count:
		main.wanderer_takeover.touch()
		await RenderingServer.frame_post_draw


func _wait(seconds: float) -> void:
	await create_timer(seconds).timeout


## [mean luma 0..255, near-black share, dark share] of the whole output frame.
func _luma() -> Array:
	var img := main.output.get_texture().get_image()
	var n := 0
	var sum := 0.0
	var black := 0
	var dark := 0
	var grid := PackedFloat32Array([0, 0, 0, 0, 0, 0, 0, 0, 0])
	for y in range(0, img.get_height(), 6):
		for x in range(0, img.get_width(), 6):
			var c := img.get_pixel(x, y)
			var l := (0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b) * 255.0
			n += 1
			sum += l
			grid[3 * (3 * y / img.get_height()) + 3 * x / img.get_width()] += l
			black += 1 if l < 8.0 else 0
			dark += 1 if l < 30.0 else 0
	for i in 9:
		grid[i] /= n / 9.0
	return [sum / n, float(black) / n, float(dark) / n, grid]


func _median_ms() -> float:
	var times: Array[float] = []
	var last := Time.get_ticks_usec()
	for f in COST_FRAMES:
		main.wanderer_takeover.touch()
		await RenderingServer.frame_post_draw
		var now := Time.get_ticks_usec()
		if f >= 10:
			times.append((now - last) / 1000.0)
		last = now
	times.sort()
	return times[times.size() / 2]


func _climb() -> void:
	await process_frame
	main.vj.apply("/vj/cam_auto", 0.0, VjSignals.SOURCE_PAGE)
	await _wait(4.0)
	var c := main.colossus.global_position
	main.wanderer.place_at(c + main.colossus.global_transform.basis.z * 6.0)
	main.arc.send(Arc.Event.NEXT)
	Engine.time_scale = 3.0
	var t := 0.0
	while not main.wanderer.on_colossus() and t < 30.0:
		await _wait(0.25)
		t += 0.25
	await _wait(1.0)
	Engine.time_scale = 1.0


func _write(path: String, value: Variant) -> Variant:
	var parts := path.split(":")
	if parts[0] == "rock":
		var mat: ShaderMaterial = (main.colossus as GrockColossus).rock_material()
		var was: Variant = mat.get_shader_parameter(parts[1])
		mat.set_shader_parameter(parts[1], value)
		return was
	var target: Object = main.world
	if parts[0] == "director":
		target = main.director
	elif parts[0] == "env":
		target = main.world.environment
	elif parts[0] != "world" and parts[0] != "director":
		target = main.world.get(parts[0])
	var before: Variant = target.get(parts[1])
	target.set(parts[1], value)
	return before


func _run() -> void:
	await _climb()
	var filter := OS.get_cmdline_user_args()[0] if OS.get_cmdline_user_args().size() > 0 else ""
	print("wanderer %s" % ("Nomad" if main.wanderer.body else "stand-in"))
	Engine.max_fps = 0
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	for _round in REPEATS:
		for v: Array in VARIANTS:
			if (v[0] as String).begins_with(filter):
				await _variant(v)
	Engine.time_scale = 1.0
	quit()


func _variant(v: Array) -> void:
	var undo := []
	for w: Array in v[1]:
		undo.append([w[0], _write(w[0], w[1])])
	var line := "%-22s" % v[0]
	for s: Array in SHOTS:
		main.vj.apply("/vj/cam", float(s[1]), VjSignals.SOURCE_PAGE)
		main.director.snap()
		await _frames(SETTLE_FRAMES)
		var l := _luma()
		var ms := await _median_ms()
		line += "  %s luma %5.1f  black %.3f  dark %.3f  %.2f ms |" % [s[0], l[0], l[1], l[2], ms]
	print(line)
	for u: Array in undo:
		_write(u[0], u[1])
