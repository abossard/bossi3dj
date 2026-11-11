extends SceneTree
## Does the Wanderer read in the low hero shot on the long walk? On Metal, the shot pinned, the
## Wanderer at the Shrine start and at gaps down the plain: his height in pixels (of 1080) and the
## contrast of his body against the ground beside him (difference over the brighter, 0..1).
## Frames are saved to OUT for the look round. No Syphon, no page, own OSC port.
## Godot --path godot/colossus --script res://tests/wanderer_read.gd -- <out dir>

const TEST_PORT := 19202
const HERO_SHOT := 2
## Gaps Wanderer to Colossus (m); -1 is the real start at the Shrine.
const GAPS := [-1.0, 1500.0, 1000.0, 450.0]

var main: ColossusMain


func _initialize() -> void:
	main = load("res://main.tscn").instantiate()
	main.syphon_enabled = false
	main.osc_port = TEST_PORT
	main.page_port = 0
	root.add_child(main)
	main.set_process_unhandled_input(false)
	_run()


func _luma(img: Image, at: Vector2, half: int) -> float:
	var sum := 0.0
	var n := 0
	for y in range(int(at.y) - half, int(at.y) + half + 1):
		for x in range(int(at.x) - half, int(at.x) + half + 1):
			if x >= 0 and y >= 0 and x < img.get_width() and y < img.get_height():
				var c := img.get_pixel(x, y)
				sum += 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b
				n += 1
	return sum / maxf(n, 1.0)


func _run() -> void:
	var args := OS.get_cmdline_user_args()
	var out := args[0] if args.size() > 0 else "/tmp/colossus-wanderer-read"
	DirAccess.make_dir_recursive_absolute(out)
	await create_timer(3.0).timeout
	main.vj.apply("/vj/cam_auto", 0.0, VjSignals.SOURCE_PAGE)
	main.vj.apply("/vj/cam", float(HERO_SHOT - 1), VjSignals.SOURCE_PAGE)
	print("wanderer: %s" % ("Nomad" if main.wanderer.body else "stand-in"))
	for gap: float in GAPS:
		var c := main.colossus.global_position
		if gap < 0.0:
			main.wanderer.place_at(Land.SHRINE + ColossusMain.SHRINE_START)
		else:
			main.wanderer.place_at(Vector3(c.x, 0.0, c.z + gap))
		main.director.snap()
		await create_timer(4.0).timeout
		await RenderingServer.frame_post_draw
		var img := main.output.get_texture().get_image()
		var cam := main.output.get_camera_3d()
		var feet := cam.unproject_position(main.wanderer.global_position)
		var head := cam.unproject_position(main.wanderer.global_position + Vector3.UP * 1.7)
		var px := absf(feet.y - head.y)
		var body := (feet + head) * 0.5
		var half := maxi(int(px * 0.08), 1)
		var inside := _luma(img, body, half)
		var beside := (
			(
				_luma(img, body + Vector2(px * 0.6, 0.0), half)
				+ _luma(img, body - Vector2(px * 0.6, 0.0), half)
			)
			* 0.5
		)
		var contrast := absf(inside - beside) / maxf(maxf(inside, beside), 1e-4)
		# The same patch with him hidden: equal means he is not drawn there (occluded).
		main.wanderer.visible = false
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		var hidden := _luma(main.output.get_texture().get_image(), body, half)
		main.wanderer.visible = true
		var chest := main.wanderer.global_position + Vector3.UP * 1.2
		var blocked := 0
		for k in range(1, 20):
			var p := cam.global_position.lerp(chest, k / 20.0)
			if p.y < main.world.height_at(p.x, p.z):
				blocked += 1
		print("  line of sight camera to chest: %d of 19 samples under the land" % blocked)
		var name := "start" if gap < 0.0 else "%dm" % gap
		img.save_png("%s/low-hero-%s.png" % [out, name])
		print(
			(
				(
					"low hero %-6s wanderer %3d px at %d,%d  luma body %.3f (hidden %.3f)"
					+ "  beside %.3f  contrast %.2f  camera %.1f m off, fov %.1f"
				)
				% [
					name,
					px,
					body.x,
					body.y,
					inside,
					hidden,
					beside,
					contrast,
					cam.global_position.distance_to(main.wanderer.global_position),
					cam.fov,
				]
			)
		)
	quit()
