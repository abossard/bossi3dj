extends SceneTree
## The frame-time table of the real scene on Metal with both models, in four parts:
##   shots    each director shot pinned, 20 s, in two situations: far (the Wanderer at the
##            Shrine, the long walk) and near (he hangs on the Colossus in a Climb);
##   arc      one whole Arc (Approach, Climb, Fall, Reset, back to Approach) with vsync off: per
##            Phase, and the worst frame of the Arc;
##   vsync    the same Arc with vsync on: the frames over 16.7 ms and over 33.3 ms;
##   sweep    the internal resolution from the show's setting up to 2x, to see where the GPU
##            stops being hidden by the display link;
##   features each renderer feature switched off once, alternating with the scene as it is, in two
##            views, to name what the frame spends most on.
## Per row: median, 95th percentile and worst frame time (ms, from frame to frame), draw calls and
## triangles in the frame (colour and shadow passes together), and the GPU time when the device
## reports one. Vsync is off and `Engine.max_fps` 0 except in `vsync`. A verdict on fps needs `make
## status` to say fps_trustworthy; the differences inside one run do not. No Syphon, no page, own
## OSC port, no change to the scene.
## Godot --path godot/colossus --script res://tests/fps.gd -- <out.json> [shots|arc|vsync|...]

const TEST_PORT := 19202
const ROW_SECONDS := 20.0
const SETTLE_SECONDS := 3.0
const FEATURE_FRAMES := 150
const FEATURE_ROUNDS := 3
const FRAME_60 := 1000.0 / 60.0
## Metal keeps the display link with vsync off, and has no GPU timer: a frame that fits in about
## 8.3 ms reads 8.3 ms whatever it costs. So the table also reads each row with the internal
## resolution at STRESS_SCALE times the output (bilinear, no MetalFX), where the GPU is the limit
## and the frame time grows with the work, and `sweep` walks the scale to find where the floor ends.
const STRESS_SCALE := 1.5
const STRESS_SECONDS := 5.0
const SWEEP_SCALES := [1.0, 1.25, 1.5, 1.75, 2.0]
const ARC_LIMIT_SECONDS := 90.0
## Label and /vj/cam wire value (0 is shot 1).
const SHOTS := [
	["scale wide", 0],
	["low hero", 1],
	["over-shoulder", 2],
	["close grip", 3],
	["aerial", 4],
]
## Label, then the Environment or light property switched off and its off value.
const FEATURES := [
	["volumetric fog", "env:volumetric_fog_enabled", false],
	["SDFGI", "env:sdfgi_enabled", false],
	["sun shadow", "sun:shadow_enabled", false],
	["SSAO", "env:ssao_enabled", false],
	["SSIL", "env:ssil_enabled", false],
	["glow", "env:glow_enabled", false],
	["distance fog", "env:fog_enabled", false],
	["fill light", "fill:visible", false],
]
## Label, the shot (wire value) and how the Wanderer stands for the feature views.
const VIEWS := [["far, scale wide", 0, "far"], ["near, close grip", 3, "near"]]

var main: ColossusMain
var _out := "/tmp/colossus-fps.json"
var _report := {}
var _vp := RID()


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() > 0:
		_out = args[0]
	main = load("res://main.tscn").instantiate()
	main.syphon_enabled = false
	main.osc_port = TEST_PORT
	main.page_port = 0
	root.add_child(main)
	main.set_process_unhandled_input(false)
	_run()


static func _percentile(sorted: Array, p: float) -> float:
	return sorted[mini(int(p * sorted.size()), sorted.size() - 1)] if not sorted.is_empty() else 0.0


func _info(pass_type: int, what: int) -> int:
	return RenderingServer.viewport_get_render_info(_vp, pass_type, what)


## Draw calls and triangles in the frame just drawn, colour and shadow passes together.
func _counts() -> Vector2i:
	var draws := 0
	var tris := 0
	for pass_type in [
		RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE,
		RenderingServer.VIEWPORT_RENDER_INFO_TYPE_SHADOW
	]:
		draws += _info(pass_type, RenderingServer.VIEWPORT_RENDER_INFO_DRAW_CALLS_IN_FRAME)
		tris += _info(pass_type, RenderingServer.VIEWPORT_RENDER_INFO_PRIMITIVES_IN_FRAME)
	return Vector2i(draws, tris)


## Frame times for `seconds`: [ms per frame], with the draw calls and triangles and the GPU time
## sampled once a second.
func _sample(seconds: float, hold: bool = false) -> Dictionary:
	var times: Array[float] = []
	var draws: Array[int] = []
	var tris: Array[int] = []
	var gpu: Array[float] = []
	var t := 0.0
	var last := Time.get_ticks_usec()
	var next_info := 0.5
	while t < seconds:
		if hold:
			main.wanderer_takeover.touch()
		await RenderingServer.frame_post_draw
		var now := Time.get_ticks_usec()
		var ms := (now - last) / 1000.0
		last = now
		t += ms / 1000.0
		times.append(ms)
		if t >= next_info:
			next_info += 1.0
			var c := _counts()
			draws.append(c.x)
			tris.append(c.y)
			gpu.append(RenderingServer.viewport_get_measured_render_time_gpu(_vp))
	return _row(times, draws, tris, gpu)


func _row(times: Array, draws: Array, tris: Array, gpu: Array) -> Dictionary:
	var sorted: Array = times.duplicate()
	sorted.sort()
	draws.sort()
	tris.sort()
	gpu.sort()
	var mid := draws.size() / 2
	return {
		"frames": times.size(),
		"median_ms": snappedf(_percentile(sorted, 0.5), 0.01),
		"p95_ms": snappedf(_percentile(sorted, 0.95), 0.01),
		"worst_ms": snappedf(sorted[-1], 0.01),
		"over_16_7": sorted.filter(func(v: float) -> bool: return v > FRAME_60).size(),
		"over_33_3": sorted.filter(func(v: float) -> bool: return v > FRAME_60 * 2.0).size(),
		"draws": draws[mid] if not draws.is_empty() else 0,
		"tris": tris[mid] if not tris.is_empty() else 0,
		"gpu_ms": snappedf(gpu[mid], 0.01) if not gpu.is_empty() else 0.0,
	}


func _line(label: String, r: Dictionary) -> void:
	print(
		(
			(
				"%-26s median %5.2f  p95 %5.2f  worst %6.2f ms  over 16.7: %3d, 33.3: %3d of %d"
				+ "  draws %3d  tris %7d  gpu %.2f ms"
			)
			% [
				label,
				r["median_ms"],
				r["p95_ms"],
				r["worst_ms"],
				r["over_16_7"],
				r["over_33_3"],
				r["frames"],
				r["draws"],
				r["tris"],
				r["gpu_ms"],
			]
		)
	)


func _pin(cam_value: int) -> void:
	main.vj.apply("/vj/cam_auto", 0.0, VjSignals.SOURCE_PAGE)
	main.vj.apply("/vj/cam", float(cam_value), VjSignals.SOURCE_PAGE)
	main.director.snap()


## The Wanderer at the start of the long walk, the Colossus roaming.
func _far() -> void:
	main.arc.send(Arc.Event.RESET_NOW)
	await _until(func() -> bool: return main.arc.phase == Arc.Phase.APPROACH, 40.0)
	await create_timer(SETTLE_SECONDS).timeout
	main.wanderer.place_at(Land.SHRINE + ColossusMain.SHRINE_START)
	main.director.snap()


## He hangs on the Colossus in a Climb, held on his grip.
func _near() -> void:
	await _far()
	var c := main.colossus
	main.wanderer.place_at(c.global_position + c.global_transform.basis.z * 6.0)
	main.arc.send(Arc.Event.NEXT)
	Engine.time_scale = 3.0
	await _until(func() -> bool: return main.wanderer.state == Wanderer.State.HANGING, 40.0)
	Engine.time_scale = 1.0
	for i in 30:
		main.wanderer_takeover.touch()
		await RenderingServer.frame_post_draw


func _until(cond: Callable, limit: float) -> void:
	var t := 0.0
	while not cond.call() and t < limit:
		if main.wanderer.on_colossus():
			main.wanderer_takeover.touch()
		await create_timer(0.25).timeout
		t += 0.25


func _unlimited() -> void:
	Engine.max_fps = 0
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)


## 0 is the show's setting (MetalFX temporal at 0.75); any other value renders that many times the
## output's size, bilinear.
func _scale(factor: float) -> void:
	# The scale goes first when it stays inside the mode's limits, the mode first when it leaves them
	# (MetalFX takes 0.33 to 1, bilinear any), or the engine falls back to another upscaler.
	if factor <= 0.0:
		main.output.scaling_3d_scale = 0.75
		main.output.scaling_3d_mode = Viewport.SCALING_3D_MODE_METALFX_TEMPORAL
	else:
		main.output.scaling_3d_mode = Viewport.SCALING_3D_MODE_BILINEAR
		main.output.scaling_3d_scale = factor


func _sweep() -> void:
	_report["sweep"] = {}
	for view: Array in VIEWS:
		if view[2] == "far":
			await _far()
		else:
			await _near()
		_pin(view[1])
		await create_timer(SETTLE_SECONDS).timeout
		var row := {}
		for factor: float in [0.0] + SWEEP_SCALES:
			_scale(factor)
			await create_timer(1.0).timeout
			var m := await _frame_median(view[2] == "near")
			row["production" if factor == 0.0 else "%.2fx" % factor] = snappedf(m, 0.01)
			print("%s  scale %s: %.2f ms" % [view[0], "production" if factor == 0.0 else factor, m])
		_scale(0.0)
		_report["sweep"][view[0]] = row


func _shots() -> void:
	_report["shots"] = {}
	for situation: String in ["far", "near"]:
		if situation == "far":
			await _far()
		else:
			await _near()
		for s: Array in SHOTS:
			_pin(s[1])
			await create_timer(SETTLE_SECONDS).timeout
			var r := await _sample(ROW_SECONDS, situation == "near")
			_scale(STRESS_SCALE)
			await create_timer(1.0).timeout
			var stress := await _sample(STRESS_SECONDS, situation == "near")
			_scale(0.0)
			r["stress_median_ms"] = stress["median_ms"]
			r["stress_p95_ms"] = stress["p95_ms"]
			_report["shots"]["%s, %s" % [situation, s[0]]] = r
			_line("%s, %s" % [situation, s[0]], r)
			print("    at %.1fx the pixels: median %.2f ms" % [STRESS_SCALE, stress["median_ms"]])


## One Arc: Approach (the Wanderer 60 m from the Colossus), Climb, Fall, Reset and the Approach
## after it. Per Phase rows (a Phase's first ROW_SECONDS) and every frame with its Phase.
func _arc(label: String) -> Dictionary:
	main.vj.apply("/vj/cam_auto", 1.0, VjSignals.SOURCE_PAGE)
	main.arc.send(Arc.Event.RESET_NOW)
	await _until(func() -> bool: return main.arc.phase == Arc.Phase.APPROACH, 40.0)
	await create_timer(SETTLE_SECONDS).timeout
	var c := main.colossus
	main.wanderer.place_at(c.global_position + c.global_transform.basis.z * 60.0)
	main.director.snap()
	var frames := {}
	var phase_t := {}
	var times: Array[float] = []
	var started := false
	var left := false
	var t := 0.0
	var last := Time.get_ticks_usec()
	while t < ARC_LIMIT_SECONDS:
		await RenderingServer.frame_post_draw
		var now := Time.get_ticks_usec()
		var ms := (now - last) / 1000.0
		last = now
		t += ms / 1000.0
		var phase: int = main.arc.phase
		var key := Arc.name_of(phase)
		phase_t[key] = phase_t.get(key, 0.0) + ms / 1000.0
		if phase_t[key] <= ROW_SECONDS:
			if not frames.has(key):
				frames[key] = [[], [], [], []]
			frames[key][0].append(ms)
			var info := _counts()
			frames[key][1].append(info.x)
			frames[key][2].append(info.y)
			frames[key][3].append(RenderingServer.viewport_get_measured_render_time_gpu(_vp))
		times.append(ms)
		if phase == Arc.Phase.APPROACH and not started and phase_t[key] > ROW_SECONDS:
			started = true
			main.arc.send(Arc.Event.NEXT)
		elif phase == Arc.Phase.CLIMB and phase_t[key] > ROW_SECONDS:
			main.arc.send(Arc.Event.NEXT)
		elif phase == Arc.Phase.RESET:
			left = true
		elif phase == Arc.Phase.APPROACH and started and left and phase_t[key] > ROW_SECONDS + 3.0:
			break
	var out := {}
	for key: String in frames:
		var f: Array = frames[key]
		out[key] = _row(f[0], f[1], f[2], f[3])
		_line("%s, %s" % [label, key], out[key])
	var all := _row(times, [], [], [])
	out["whole Arc"] = all
	_line("%s, whole Arc" % label, all)
	return out


func _write(path: String, value: Variant) -> Variant:
	var parts := path.split(":")
	var target: Object = main.world.environment if parts[0] == "env" else main.world.get(parts[0])
	var before: Variant = target.get(parts[1])
	target.set(parts[1], value)
	return before


func _features(factor: float) -> void:
	var tag := "production" if factor == 0.0 else "%.1fx pixels" % factor
	_scale(factor)
	_report["features"][tag] = {}
	for view: Array in VIEWS:
		if view[2] == "far":
			await _far()
		else:
			await _near()
		_pin(view[1])
		await create_timer(SETTLE_SECONDS).timeout
		var rounds := {"as is": []}
		for f: Array in FEATURES:
			rounds[f[0]] = []
		for round_number in FEATURE_ROUNDS:
			var order: Array = ["as is"] + FEATURES.map(func(f: Array) -> String: return f[0])
			for name: String in order:
				var was: Variant = null
				var path := ""
				for f: Array in FEATURES:
					if f[0] == name:
						path = f[1]
						was = _write(path, f[2])
				var r := await _frame_median(view[2] == "near")
				rounds[name].append(r)
				if path != "":
					_write(path, was)
		var base := _percentile(_sorted(rounds["as is"]), 0.5)
		_report["features"][tag][view[0]] = {"as is": snappedf(base, 0.01)}
		print("%s, %s: as is %.2f ms" % [tag, view[0], base])
		for f: Array in FEATURES:
			var m := _percentile(_sorted(rounds[f[0]]), 0.5)
			_report["features"][tag][view[0]][f[0]] = snappedf(m, 0.01)
			print("  %-16s off: %.2f ms  (%+.2f)" % [f[0], m, m - base])


static func _sorted(values: Array) -> Array:
	var v := values.duplicate()
	v.sort()
	return v


## The median over FEATURE_FRAMES of the GPU time if the device reports it, else of the frame time.
func _frame_median(hold: bool) -> float:
	var times: Array[float] = []
	var gpu: Array[float] = []
	var last := Time.get_ticks_usec()
	for i in FEATURE_FRAMES:
		if hold:
			main.wanderer_takeover.touch()
		await RenderingServer.frame_post_draw
		var now := Time.get_ticks_usec()
		if i >= 30:
			times.append((now - last) / 1000.0)
			gpu.append(RenderingServer.viewport_get_measured_render_time_gpu(_vp))
		last = now
	times.sort()
	gpu.sort()
	return gpu[gpu.size() / 2] if gpu[gpu.size() / 2] > 0.0 else times[times.size() / 2]


func _run() -> void:
	await create_timer(6.0).timeout
	_vp = main.output.get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(_vp, true)
	for i in 60:
		await RenderingServer.frame_post_draw
	_report["gpu_timer_ms"] = RenderingServer.viewport_get_measured_render_time_gpu(_vp)
	_report["cpu_render_ms"] = RenderingServer.viewport_get_measured_render_time_cpu(_vp)
	print(
		(
			"render time the engine reports: gpu %.2f ms, cpu %.2f ms (0 gpu: no GPU timer)"
			% [_report["gpu_timer_ms"], _report["cpu_render_ms"]]
		)
	)
	var args := OS.get_cmdline_user_args()
	var part := args[1] if args.size() > 1 else "all"
	_report["driver"] = RenderingServer.get_video_adapter_name()
	if part in ["all", "shots"]:
		_unlimited()
		await _shots()
	if part in ["all", "arc"]:
		_unlimited()
		_report["arc"] = await _arc("vsync off")
	if part in ["all", "vsync"]:
		Engine.max_fps = 60
		DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_ENABLED)
		_report["vsync"] = await _arc("vsync on")
	if part in ["all", "sweep"]:
		_unlimited()
		await _sweep()
	if part in ["all", "features"]:
		_unlimited()
		_report["features"] = {}
		await _features(0.0)
		await _features(STRESS_SCALE)
		_scale(0.0)
	var f := FileAccess.open(_out, FileAccess.WRITE)
	f.store_string(JSON.stringify(_report, "  "))
	f.close()
	print("written ", _out)
	quit()
