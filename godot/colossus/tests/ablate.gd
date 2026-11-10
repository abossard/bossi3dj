extends SceneTree
## Which renderer feature makes the frame go flat black? For each variant of the look it rebuilds
## the Colossus (the start and the Reset do that), then prints the flat-black share of the whole
## frame at frame 30 (the warm-up) and of the lowest 30% of rows at frame 120 (the settled ground).
## Real renderer, no Syphon, own OSC port.
## Godot --path godot/colossus --script res://tests/ablate.gd

const TEST_PORT := 19202
const EARLY := 30
const LATE := 120

## label, then the Environment or light property to set and its value.
const VARIANTS := [
	["as is", "", null],
	["no ssao", "ssao_enabled", false],
	["no ssil", "ssil_enabled", false],
	["no glow", "glow_enabled", false],
	["no volumetric fog", "volumetric_fog_enabled", false],
	["no sdfgi", "sdfgi_enabled", false],
	["no fog", "fog_enabled", false],
	["no sun shadow", "sun:shadow_enabled", false],
	["no fill", "fill:visible", false],
	["fill energy 1.5", "fill:light_energy", 1.5],
	["fill energy 4", "fill:light_energy", 4.0],
	["terrain no ao", "terrain:output_ambient_occlusion", false],
	["terrain no roughness", "terrain:output_roughness", false],
	["terrain no specular", "terrain:output_specular", false],
	["terrain no normal map", "terrain:output_normal_map", false],
	["terrain grey", "terrain:show_grey", true],
	["terrain no dual scaling", "terrain:dual_scaling_enabled", false],
	["terrain no macro variation", "terrain:macro_variation_enabled", false],
	["terrain no auto shader", "terrain:auto_shader_enabled", false],
	["terrain show albedo", "terrain:show_texture_albedo", true],
	["terrain show normal", "terrain:show_texture_normal", true],
	["terrain show rough", "terrain:show_texture_rough", true],
	["terrain show autoshader", "terrain:show_autoshader", true],
	["terrain show control", "terrain:show_control_texture", true],
	["terrain show colormap", "terrain:show_colormap", true],
	["terrain no projection", "terrain:projection_enabled", false],
	["asset tint white", "asset:albedo_color", Color.WHITE],
	["asset uv 0.2", "asset:uv_scale", 0.2],
	["asset uv 0.01", "asset:uv_scale", 0.01],
	["asset detiling", "asset:detiling_rotation", 0.5],
	["tint rock 6b6660", "tint:1", Color("6b6660")],
	["tint rock 8c867f", "tint:1", Color("8c867f")],
	["tint rock b0aaa3", "tint:1", Color("b0aaa3")],
	["tint rock white", "tint:1", Color.WHITE],
	["hide colossus", "hide:colossus", null],
	["hide wanderer", "hide:wanderer", null],
	["hide land", "hide:world.land", null],
	["hide dust", "hide:dust", null],
	["hide sun", "sun:visible", false],
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


## Share of flat-black pixels in rows from `top` to the bottom (fractions of the height).
func _flat_black(top: float) -> float:
	return _ground(top)[0]


## [flat-black share, mean luma 0..255] of the rows from `top` to the bottom.
func _ground(top: float) -> Array:
	var img := main.output.get_texture().get_image()
	var n := 0
	var black := 0
	var sum := 0.0
	for y in range(int(img.get_height() * top), img.get_height(), 12):
		for x in range(0, img.get_width(), 12):
			var c := img.get_pixel(x, y)
			n += 1
			sum += 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b
			if maxf(c.r, maxf(c.g, c.b)) <= 2.0 / 255.0:
				black += 1
	return [float(black) / maxf(n, 1.0), sum / maxf(n, 1.0) * 255.0]


func _frames(count: int) -> void:
	for i in count:
		await RenderingServer.frame_post_draw


func _apply(path: String, value: Variant) -> void:
	if path == "":
		return
	if path.begins_with("hide:"):
		var node: Object = main
		for part in path.trim_prefix("hide:").split("."):
			node = node.get(part)
		node.set("visible", not node.get("visible"))
		return
	if path.begins_with("terrain:"):
		main.world.land.terrain.material.set(path.trim_prefix("terrain:"), value)
	elif path.begins_with("tint:"):
		var assets := main.world.land.terrain.assets
		assets.get_texture_asset(int(path.trim_prefix("tint:"))).albedo_color = value
	elif path.begins_with("asset:"):
		var a := main.world.land.terrain.assets
		for i in a.get_texture_count():
			a.get_texture_asset(i).set(path.trim_prefix("asset:"), value)
	elif ":" in path:
		var parts := path.split(":")
		main.world.get(parts[0]).set(parts[1], value)
	else:
		main.world.environment.set(path, value)


func _run() -> void:
	await _frames(150)
	main.vj.apply("/vj/cam_auto", 0.0, VjSignals.SOURCE_PAGE)
	for v: Array in VARIANTS:
		if (
			not OS.get_cmdline_user_args().is_empty()
			and not v[0].begins_with(OS.get_cmdline_user_args()[0])
		):
			continue
		if not v[1].begins_with("hide:"):
			_apply(v[1], v[2])
		main._start_arc()
		if v[1].begins_with("hide:"):
			_apply(v[1], v[2])
		await _frames(EARLY)
		var early := _flat_black(0.0)
		await _frames(LATE - EARLY)
		var late := _ground(0.7)
		print(
			(
				"%-18s warm-up frame %d: %.2f   ground at frame %d: %.2f  luma %.1f"
				% [v[0], EARLY, early, LATE, late[0], late[1]]
			)
		)
		if v[1].begins_with("hide:"):
			_apply(v[1], v[2])
		else:
			_apply(v[1], not v[2] if typeof(v[2]) == TYPE_BOOL else v[2])
	quit()
