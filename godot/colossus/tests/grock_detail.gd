extends SceneTree
## Does Grock show surface detail at the distances of the wide and medium shots, and what does each
## layer of it add? On Metal: the scale wide shot with the Wanderer 150 m and 450 m from the
## Colossus; for each variant of its surface (a flat normal map, the model's own derived one, the
## rock detail on top, the colour variation) the mean luma and the detail energy inside the body's
## box (mean absolute Laplacian of the luma, 0..255 steps per pixel: the fine light-and-dark
## structure a viewer reads as grain, plates and cracks), and the median frame time with vsync off.
## The film grain is switched off and the Colossus held still.
## Frames go to <out dir> as PNG. Own OSC port, no Syphon.
## Godot --path godot/colossus --script res://tests/grock_detail.gd -- <out dir> [<variant prefix>]

const TEST_PORT := 19202
const SETTLE_FRAMES := 90
const COST_FRAMES := 60
const REPEATS := 3
## The Wanderer's gap to the Colossus (m) in each view.
const GAPS := [150.0, 450.0]
## label, the shader parameters (model_normal, detail_strength, tint_strength, detail_scale), and
## the dust skirt round the feet (its density, 0 hides it, and colour) and whether the eyes show.
const PRODUCT := [1.0, 6.0, 0.6, 0.04]
const DUST := "c4b9a4"
const VARIANTS := [
	["flat", [0.0, 0.0, 0.0, 0.04], 0.15, DUST, true],
	["model normal", [1.0, 0.0, 0.0, 0.04], 0.15, DUST, true],
	["rock detail only", [0.0, 6.0, 0.6, 0.04], 0.15, DUST, true],
	["model + rock detail", PRODUCT, 0.15, DUST, true],
	["product, no dust skirt", PRODUCT, 0.0, DUST, true],
	["product, no eyes", PRODUCT, 0.15, DUST, false],
	["product", PRODUCT, 0.15, DUST, true],
]

var main: ColossusMain
var _out := "/tmp/colossus-grock-detail"


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() > 0:
		_out = args[0]
	DirAccess.make_dir_recursive_absolute(_out)
	if not GrockColossus.model_present():
		print("Grock is missing: see godot/colossus/assets/MODELS.md (make godot-models)")
		quit(1)
		return
	main = load("res://main.tscn").instantiate()
	main.syphon_enabled = false
	main.osc_port = TEST_PORT
	main.page_port = 0
	root.add_child(main)
	main.set_process_unhandled_input(false)
	_run()


func _frames(count: int) -> void:
	for i in count:
		await RenderingServer.frame_post_draw


func _median_ms() -> float:
	var times: Array[float] = []
	var last := Time.get_ticks_usec()
	for f in COST_FRAMES:
		await RenderingServer.frame_post_draw
		var now := Time.get_ticks_usec()
		if f >= 10:
			times.append((now - last) / 1000.0)
		last = now
	times.sort()
	return times[times.size() / 2]


## The body's box on screen: its middle 40 % across and the height from feet to top, kept in frame.
func _box(cam: Camera3D, img: Image) -> Rect2i:
	var c := main.colossus
	var foot := cam.unproject_position(c.global_position)
	var top := cam.unproject_position(c.global_position + Vector3.UP * c.height_m)
	var mid := (foot + top) * 0.5
	var half_h := absf(foot.y - top.y) * 0.5
	var box := Rect2(mid - Vector2(half_h * 0.4, half_h), Vector2(half_h * 0.8, half_h * 2.0))
	return Rect2i(box).intersection(Rect2i(Vector2i.ZERO, img.get_size()))


## The ground round its feet on screen: as wide as its height is tall, a fifth of the height up.
func _feet_box(cam: Camera3D, img: Image) -> Rect2i:
	var c := main.colossus
	var foot := cam.unproject_position(c.global_position)
	var top := cam.unproject_position(c.global_position + Vector3.UP * c.height_m)
	var h := absf(foot.y - top.y)
	var box := Rect2(foot - Vector2(h * 0.4, h * 0.2), Vector2(h * 0.8, h * 0.25))
	return Rect2i(box).intersection(Rect2i(Vector2i.ZERO, img.get_size()))


## Bright pixels (luma over 170) in a 240 px square round the head: what the glints add.
func _glints(cam: Camera3D, img: Image) -> int:
	var head := main.colossus.head_point()
	var at := Vector2i(cam.unproject_position(head.global_position))
	var box := Rect2i(at - Vector2i(120, 120), Vector2i(240, 240))
	box = box.intersection(Rect2i(Vector2i.ZERO, img.get_size()))
	var n := 0
	for y in range(box.position.y, box.end.y):
		for x in range(box.position.x, box.end.x):
			if _luma(img.get_pixel(x, y)) > 170.0:
				n += 1
	return n


## [mean luma 0..255, mean absolute Laplacian of the luma] inside `box`.
func _detail(img: Image, box: Rect2i) -> Array:
	var sum := 0.0
	var lap := 0.0
	var n := 0
	for y in range(box.position.y + 1, box.end.y - 1, 2):
		for x in range(box.position.x + 1, box.end.x - 1, 2):
			var l := _luma(img.get_pixel(x, y))
			sum += l
			lap += absf(
				(
					4.0 * l
					- _luma(img.get_pixel(x - 1, y))
					- _luma(img.get_pixel(x + 1, y))
					- _luma(img.get_pixel(x, y - 1))
					- _luma(img.get_pixel(x, y + 1))
				)
			)
			n += 1
	return [sum / maxf(n, 1.0), lap / maxf(n, 1.0)]


static func _luma(c: Color) -> float:
	return (0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b) * 255.0


func _surface(variant: Array) -> void:
	var v: Array = variant[1]
	var skirt := main.colossus.dust_skirt
	skirt.visible = variant[2] > 0.0
	(skirt.material as FogMaterial).density = variant[2]
	(skirt.material as FogMaterial).albedo = Color(variant[3])
	for eye: Node3D in main.colossus.find_children("eye_*", "MeshInstance3D", true, false):
		eye.visible = variant[4]
	var mat := (main.colossus as GrockColossus).rock_material()
	mat.set_shader_parameter("model_normal", v[0])
	mat.set_shader_parameter("detail_strength", v[1])
	mat.set_shader_parameter("tint_strength", v[2])
	mat.set_shader_parameter("detail_scale", v[3])


func _run() -> void:
	await create_timer(3.0).timeout
	var filter := OS.get_cmdline_user_args()[1] if OS.get_cmdline_user_args().size() > 1 else ""
	main.vj.apply("/vj/cam_auto", 0.0, VjSignals.SOURCE_PAGE)
	main.vj.apply("/vj/cam", 0.0, VjSignals.SOURCE_PAGE)
	# The film grain is noise at the pixel: off, and the Colossus held in its pose, so only the
	# surface differs between variants.
	for layer: CanvasLayer in main.output.find_children("*", "CanvasLayer", false, false):
		layer.visible = false
	for gap: float in GAPS:
		var c := main.colossus.global_position
		main.wanderer.place_at(Vector3(c.x, 0.0, c.z + gap))
		main.director.snap()
		await _frames(SETTLE_FRAMES)
		main.colossus.process_mode = Node.PROCESS_MODE_DISABLED
		var cam := main.output.get_camera_3d()
		Engine.max_fps = 0
		DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
		for _round in REPEATS:
			for v: Array in VARIANTS:
				if not (v[0] as String).begins_with(filter):
					continue
				_surface(v)
				await _frames(SETTLE_FRAMES)
				var img := main.output.get_texture().get_image()
				var box := _box(cam, img)
				var d := _detail(img, box)
				var f := _detail(img, _feet_box(cam, img))
				var glints := _glints(cam, img)
				var ms := await _median_ms()
				if _round == 0:
					img.save_png("%s/%dm-%s.png" % [_out, gap, (v[0] as String).replace(" ", "_")])
				print(
					(
						(
							"%4d m  %-24s box %dx%d px  luma %5.1f  detail %5.2f"
							+ "  feet luma %5.1f detail %5.2f  bright px at the head %d  %.2f ms"
						)
						% [gap, v[0], box.size.x, box.size.y, d[0], d[1], f[0], f[1], glints, ms]
					)
				)
	quit()
