extends SceneTree
## Renders the look matrix on the real renderer: each director shot pinned through /vj/cam and
## /vj/cam_auto, then shot 1 at the ends of fog, fog_height and intensity. The output frame (what
## Syphon carries) of each goes to <out_dir> as PNG. Values go in through VjSignals.apply, the path
## OSC and the page use.
## Godot --path godot/colossus --script res://tests/look.gd -- <out_dir>

const TEST_PORT := 19202
const SETTLE := 2.0

## label, then address/wire value pairs written before the frame (defaults first).
const ENDS := [
	["fog_height-0", "/vj/fog_height", 0.0],
	["fog_height-0.41", "/vj/fog_height", 0.41],
	["fog_height-1", "/vj/fog_height", 1.0],
	["fog-0", "/vj/fog", 0.0],
	["fog-1", "/vj/fog", 1.0],
	["intensity-0", "/vj/intensity", 0.0],
	["intensity-1", "/vj/intensity", 1.0],
]

var main: ColossusMain
var output_size := Vector2(1920, 1080)
var _out := "user://look"


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if not args.is_empty():
		_out = args[0]
	DirAccess.make_dir_recursive_absolute(_out)
	_run()


func _wait(seconds: float) -> void:
	await create_timer(seconds).timeout


func _write(address: String, v: float) -> void:
	main.vj.apply(address, v, VjSignals.SOURCE_PAGE)


## Screen position of a world point in the output frame, and whether it is in front and inside.
func _screen(cam: Camera3D, p: Vector3) -> Dictionary:
	var at := cam.unproject_position(p)
	var inside := (
		not cam.is_position_behind(p)
		and at.x >= 0.0
		and at.x <= output_size.x
		and at.y >= 0.0
		and at.y <= output_size.y
	)
	return {"at": at, "inside": inside}


func _save(label: String) -> void:
	await RenderingServer.frame_post_draw
	var path := "%s/%s.png" % [_out, label]
	main.output.get_texture().get_image().save_png(path)
	var cam := main.output.get_camera_3d()
	var to_colossus := main.colossus.global_position - cam.global_position
	var angle := rad_to_deg((-cam.global_basis.z).angle_to(to_colossus))
	var top := _screen(cam, main.colossus.global_position + Vector3.UP * main.colossus.height_m)
	var foot := _screen(cam, main.colossus.global_position)
	var wand := _screen(cam, main.wanderer.global_position + Vector3.UP)
	print(
		(
			"saved %s  shot %d  %d fps  colossus %d m away, %d deg off the view axis (fov %d)"
			% [
				path,
				main.director.shot,
				Engine.get_frames_per_second(),
				to_colossus.length(),
				angle,
				cam.fov
			]
		)
	)
	print(
		(
			"probe %s  colossus %d px tall, top in frame %s  wanderer at %d,%d in frame %s, %d m"
			% [
				label,
				absf(foot["at"].y - top["at"].y) if not cam.is_position_behind(top_point()) else 0,
				top["inside"],
				wand["at"].x,
				wand["at"].y,
				wand["inside"],
				cam.global_position.distance_to(main.wanderer.global_position)
			]
		)
	)


func top_point() -> Vector3:
	return main.colossus.global_position + Vector3.UP * main.colossus.height_m


func _run() -> void:
	main = load("res://main.tscn").instantiate()
	main.syphon_enabled = false
	main.syphon_server = "COLOSSUS_TEST"
	main.osc_port = TEST_PORT
	main.page_port = 0
	root.add_child(main)
	main.set_process_unhandled_input(false)
	# The first published frames: Syphon shows the output from the first draw on.
	await _save("start-f1")
	for i in 20:
		await RenderingServer.frame_post_draw
	await _save("start-f20")
	await _wait(4.0)
	_write("/vj/cam_auto", 0.0)
	for n in 5:
		_write("/vj/cam", float(n))
		await _wait(SETTLE)
		await _save("shot-%d" % (n + 1))
	_write("/vj/cam", 0.0)
	for e in ENDS:
		main.vj.reset_defaults()
		_write("/vj/cam_auto", 0.0)
		_write("/vj/cam", 0.0)
		_write(e[1], e[2])
		await _wait(SETTLE)
		await _save(e[0])
	main.vj.reset_defaults()
	_write("/vj/cam_auto", 0.0)
	_write("/vj/cam", 0.0)
	main._start_arc()
	await _save("new-colossus-f1")
	for i in 20:
		await RenderingServer.frame_post_draw
	await _save("new-colossus-f20")
	quit()
