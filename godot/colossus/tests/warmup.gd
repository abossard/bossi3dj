extends SceneTree
## How long the output frame takes to settle: luma and flat-black share of the whole frame every
## STEP-th frame, from the first draw on, then again after a new Colossus is built (_start_arc).
## Reports where the frame is not black any more. Real renderer, no Syphon, own OSC port.
## Godot --path godot/colossus --script res://tests/warmup.gd [-- bilinear]   (bilinear: no MetalFX)

const TEST_PORT := 19202
const FRAMES := 240
const STEP := 10
const BLACK := 0.02

var main: ColossusMain


func _initialize() -> void:
	main = load("res://main.tscn").instantiate()
	main.syphon_enabled = false
	main.osc_port = TEST_PORT
	main.page_port = 0
	root.add_child(main)
	main.set_process_unhandled_input(false)
	_run()


## [luma mean, share of flat-black pixels, share of flat black in the lowest 30% of rows] of the
## output frame, sampled on a coarse grid.
func _measure() -> Array:
	var img := main.output.get_texture().get_image()
	var step := 16
	var n := 0
	var black := 0
	var low := 0
	var low_n := 0
	var sum := 0.0
	for y in range(0, img.get_height(), step):
		for x in range(0, img.get_width(), step):
			var c := img.get_pixel(x, y)
			n += 1
			sum += 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b
			var flat := maxf(c.r, maxf(c.g, c.b)) <= 2.0 / 255.0
			if flat:
				black += 1
			if y >= img.get_height() * 0.7:
				low_n += 1
				if flat:
					low += 1
	return [sum / n * 255.0, float(black) / n, float(low) / maxf(low_n, 1)]


func _log(label: String) -> void:
	var settled := -1
	var first := true
	for f in range(1, FRAMES + 1):
		await RenderingServer.frame_post_draw
		if f % STEP == 0 or f == 1:
			var m := _measure()
			print(
				(
					"%s frame %3d  luma %5.1f  flat black %.2f  ground %.2f"
					% [label, f, m[0], m[1], m[2]]
				)
			)
			if m[2] <= BLACK and first:
				settled = f
				first = false
	print("%s first sampled frame with flat black ground <= %.2f: %d" % [label, BLACK, settled])


func _run() -> void:
	if "bilinear" in OS.get_cmdline_user_args():
		await process_frame
		main.output.scaling_3d_mode = Viewport.SCALING_3D_MODE_BILINEAR
		main.output.scaling_3d_scale = 1.0
	await _log("start")
	main._start_arc()
	await _log("new colossus")
	quit()
