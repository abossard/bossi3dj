extends SceneTree
## Numbers for what the director frames, on the real renderer: for each shot and each distance of
## the Wanderer from the Colossus, the Colossus's height on screen in pixels (of the 1080 px
## frame) and whether the Wanderer is in frame; then the close-grip shot through a Shake. Pass
## lines and fail lines, exit code 1 on any fail. Own OSC port, no Syphon, no page.
## Godot --path godot/colossus --script res://tests/framing.gd [-- /vj/fog_height 0.0 ...]
## Address and wire value pairs after `--` are written first, to see a look with one control moved;
## `env:<property> <value>` sets an Environment property instead.

const TEST_PORT := 19202
const FRAME := Vector2(1920, 1080)
## Distances Wanderer to Colossus: -1 is where the Wanderer really starts (at the Shrine, on its
## slope), then the walk down the plain.
const GAPS := [-1.0, 1500.0, 1000.0, 700.0, 450.0, 300.0, 150.0, 60.0, 25.0]
## The Colossus reads as a silhouette from this height on (about a tenth of the frame).
const MIN_COLOSSUS_PX := 100.0
## The low hero shot gives up size for the Wanderer: the giant may shrink to this height.
const HERO_MIN_COLOSSUS_PX := 20.0
## Time runs this much faster while the Wanderer walks on his own, sampled every real half second.
const WALK_TIME_SCALE := 10.0
const WALK_SECONDS := 25.0
## The shots the director cuts to in Approach that frame the Colossus; the over-shoulder and the
## close grip frame the Wanderer, and the Colossus only when he hangs on it.
const COLOSSUS_SHOTS := [1, 2, 5]
const WANDERER_SHOTS := [3, 4]
## The low hero shot holds the Wanderer too, whole at every distance; the Colossus may shrink.
const HERO_SHOT := 2
## The Colossus differs from the sky beside it by this share of the sky's brightness at least.
const MIN_CONTRAST := 0.15

var main: ColossusMain
var _failed := 0


func _initialize() -> void:
	main = load("res://main.tscn").instantiate()
	main.syphon_enabled = false
	main.osc_port = TEST_PORT
	main.page_port = 0
	root.add_child(main)
	main.set_process_unhandled_input(false)
	_run()


func _wait(seconds: float) -> void:
	await create_timer(seconds).timeout


func _check(ok: bool, what: String) -> void:
	print("%s  %s" % ["pass" if ok else "FAIL", what])
	if not ok:
		_failed += 1


func _on_screen(cam: Camera3D, p: Vector3) -> Dictionary:
	var at := cam.unproject_position(p)
	var behind := cam.is_position_behind(p)
	return {
		"at": at,
		"inside": not behind and at.x >= 0.0 and at.x <= FRAME.x and at.y >= 0.0 and at.y <= FRAME.y
	}


## Colossus height in pixels, and whether its head and feet are both in frame.
func _colossus() -> Dictionary:
	var cam := main.output.get_camera_3d()
	var feet := _on_screen(cam, main.colossus.global_position)
	var head := _on_screen(cam, main.colossus.global_position + Vector3.UP * main.colossus.height_m)
	var px := absf(feet["at"].y - head["at"].y)
	if cam.is_position_behind(main.colossus.global_position):
		px = 0.0
	return {"px": px, "whole": feet["inside"] and head["inside"]}


## Mean luma (0..1) of a small square of the output frame around a screen point.
func _patch(img: Image, at: Vector2, half: int) -> float:
	var sum := 0.0
	var n := 0
	for y in range(int(at.y) - half, int(at.y) + half + 1, 2):
		for x in range(int(at.x) - half, int(at.x) + half + 1, 2):
			if x >= 0 and y >= 0 and x < img.get_width() and y < img.get_height():
				var c := img.get_pixel(x, y)
				sum += 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b
				n += 1
	return sum / maxf(n, 1.0)


## How much the Colossus's chest differs from the frame beside it, as a share of the brighter of
## the two (0..1): a patch on the chest against patches left and right at a body width.
func _contrast(px: float) -> float:
	await RenderingServer.frame_post_draw
	var img := main.output.get_texture().get_image()
	var cam := main.output.get_camera_3d()
	var chest := cam.unproject_position(
		main.colossus.global_position + Vector3.UP * main.colossus.height_m * 0.6
	)
	var half := maxi(int(px * 0.06), 2)
	var inside := _patch(img, chest, half)
	var beside := (
		(
			_patch(img, chest + Vector2(px * 0.6, 0.0), half)
			+ _patch(img, chest - Vector2(px * 0.6, 0.0), half)
		)
		* 0.5
	)
	var from := cam.global_position
	var to := main.colossus.global_position + Vector3.UP * main.colossus.height_m * 0.6
	var query := PhysicsRayQueryParameters3D.create(from, to, 1)
	var hit := cam.get_world_3d().direct_space_state.intersect_ray(query)
	print(
		(
			"  chest at %d,%d  luma inside %.3f  beside %.3f  line of sight %s (camera y %.0f, chest y %.0f)"
			% [
				chest.x,
				chest.y,
				inside,
				beside,
				"blocked at %d m" % from.distance_to(hit["position"]) if hit else "clear",
				from.y,
				to.y
			]
		)
	)
	if OS.get_environment("FRAMING_OUT") != "":
		img.save_png(
			"%s/%d-%d.png" % [OS.get_environment("FRAMING_OUT"), main.director.shot, int(px)]
		)
	return absf(beside - inside) / maxf(maxf(beside, inside), 0.01)


func _wanderer_in_frame() -> bool:
	var cam := main.output.get_camera_3d()
	var feet := _on_screen(cam, main.wanderer.global_position)
	var head := _on_screen(cam, main.wanderer.global_position + Vector3.UP * 1.7)
	return feet["inside"] or head["inside"]


## The Wanderer's feet and head are both in frame.
func _wanderer_whole() -> bool:
	var cam := main.output.get_camera_3d()
	var feet := _on_screen(cam, main.wanderer.global_position)
	var head := _on_screen(cam, main.wanderer.global_position + Vector3.UP * 1.7)
	return feet["inside"] and head["inside"]


func _pin(shot: int) -> void:
	main.vj.apply("/vj/cam_auto", 0.0, VjSignals.SOURCE_PAGE)
	main.vj.apply("/vj/cam", float(shot - 1), VjSignals.SOURCE_PAGE)


func _gap_table() -> void:
	for gap: float in GAPS:
		for shot in range(1, 6):
			_pin(shot)
			var c := main.colossus.global_position
			if gap < 0.0:
				main.wanderer.place_at(Land.SHRINE + ColossusMain.SHRINE_START)
			else:
				main.wanderer.place_at(Vector3(c.x, 0.0, c.z + gap))
			main.director.snap()
			await _wait(1.2)
			var real_gap := main.wanderer.global_position.distance_to(main.colossus.global_position)
			var col := _colossus()
			var seen := _wanderer_in_frame()
			var contrast: float = await _contrast(col["px"])
			print(
				(
					"shot %d %s gap %4d m  fov %4.1f  colossus %3d px, contrast %.2f, whole %s, wanderer %s"
					% [
						shot,
						"start" if gap < 0.0 else "     ",
						real_gap,
						main.output.get_camera_3d().fov,
						col["px"],
						contrast,
						col["whole"],
						seen
					]
				)
			)
			if shot in COLOSSUS_SHOTS:
				_check(
					col["px"] >= MIN_COLOSSUS_PX,
					"shot %d at %d m: colossus %d px" % [shot, real_gap, col["px"]]
				)
				_check(
					contrast >= MIN_CONTRAST,
					"shot %d at %d m: contrast %.2f" % [shot, real_gap, contrast]
				)
			if shot in WANDERER_SHOTS:
				_check(seen, "shot %d at %d m: wanderer in frame" % [shot, real_gap])


## The low hero shot while the Wanderer walks on his own (the camera lags behind him), from the real
## start down the Shrine's slope and from 300 m on the plain: he stays whole in frame throughout.
func _walk_table() -> void:
	for gap: float in [-1.0, 300.0]:
		_pin(HERO_SHOT)
		if gap < 0.0:
			main.wanderer.place_at(Land.SHRINE + ColossusMain.SHRINE_START)
		else:
			var c := main.colossus.global_position
			main.wanderer.place_at(Vector3(c.x, 0.0, c.z + gap))
		main.director.snap()
		await _wait(1.5)
		Engine.time_scale = WALK_TIME_SCALE
		var seen := 0
		var samples := 0
		var px_min := INF
		var t := 0.0
		while t < WALK_SECONDS:
			await _wait(0.5)
			t += 0.5
			if main.wanderer.global_position.distance_to(main.colossus.global_position) < 30.0:
				break
			samples += 1
			px_min = minf(px_min, _colossus()["px"])
			if _wanderer_whole():
				seen += 1
		Engine.time_scale = 1.0
		var left := main.wanderer.global_position.distance_to(main.colossus.global_position)
		print(
			(
				"low hero walking from %s: wanderer whole on %d of %d, %d m left, colossus %d px at least"
				% ["the start" if gap < 0.0 else "300 m", seen, samples, left, px_min]
			)
		)
		_check(
			seen == samples, "low hero walking from %d m keeps the Wanderer whole in frame" % gap
		)


## The Wanderer hangs on the Colossus (Climb), a Shake starts, the close-grip shot holds him.
func _shake_table() -> void:
	_pin(1)
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
	_check(main.wanderer.on_colossus(), "the Wanderer hangs on the Colossus")
	_pin(4)
	await _wait(1.0)
	main._shake()
	var seen := 0
	var samples := 0
	for i in 30:
		await _wait(0.1)
		samples += 1
		if _wanderer_in_frame():
			seen += 1
	print("close grip through a Shake: wanderer in frame on %d of %d samples" % [seen, samples])
	_check(seen == samples, "close grip through a Shake keeps the Wanderer in frame")


func _run() -> void:
	var args := OS.get_cmdline_user_args()
	await _wait(1.0)
	for i in range(0, args.size() - 1, 2):
		if args[i].begins_with("env:"):
			var prop := args[i].trim_prefix("env:")
			var cur: Variant = main.world.environment.get(prop)
			main.world.environment.set(
				prop,
				(float(args[i + 1]) != 0.0) if typeof(cur) == TYPE_BOOL else float(args[i + 1])
			)
		else:
			main.vj.apply(args[i], float(args[i + 1]), VjSignals.SOURCE_PAGE)
		print("set %s %s" % [args[i], args[i + 1]])
	await _wait(3.0)
	await _gap_table()
	await _walk_table()
	await _shake_table()
	print("%d failed" % _failed)
	quit(1 if _failed > 0 else 0)
