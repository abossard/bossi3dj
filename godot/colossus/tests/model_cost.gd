extends SceneTree
## What each real model costs against its stand-in, on Metal, in the scene's own light and fog.
## Each subject stands alone on the plain (the scene's own Colossus and Wanderer are hidden) and a
## probe camera looks at it from three distances that match the director's shots: the close grip,
## a medium shot and the long walk from the Shrine, with the shot's lens (the lens decides the LOD
## Godot draws). Per subject and view: objects, triangles and draw calls drawn in the colour and
## the shadow pass (minus the same view with no subject), surfaces, bones, texture memory, and the
## median frame time with vsync off, the subject and its stand-in alternating in one run so foreign
## load hits both alike. A verdict on fps needs `make status` to say fps_trustworthy; the
## difference inside one run does not. No Syphon, no page, own OSC port.
## Godot --path godot/colossus --script res://tests/model_cost.gd [-- <json out>]

const TEST_PORT := 19202
const ROUNDS := 6
const FRAMES := 120
const SKIP := 20
const COLOSSUS_HEIGHT := 28.0
## [view, camera distance m, vertical fov degrees, aim height in units of the subject's height]
## Colossus: close grip 3 m off the back (8 m from the body axis, 50 mm lens); the scale wide shot
## at a gap of 150 m (18 m behind the Wanderer, lens fitted to the giant); the long walk from the
## Shrine (1.6 km, the narrowest wide lens).
const COLOSSUS_VIEWS := [
	["close", 8.0, 27.0, 0.6],
	["medium", 168.0, 14.3, 0.45],
	["long walk", 1624.0, 6.0, 0.45],
]
## Wanderer: close grip (3 m off, 0.8 m aside, 50 mm), over-shoulder (4 m behind, 35 mm), and the
## low hero shot on the long walk (24 m behind, the lens spans him and the giant: up to 53 degrees).
const WANDERER_VIEWS := [
	["close", 3.2, 27.0, 0.6],
	["medium", 4.5, 37.8, 0.6],
	["long walk", 24.0, 53.0, 0.5],
]
const MODELS := {
	"grock": "res://assets/models/grock/grock.gltf",
	"nomad": "res://assets/models/nomad/nomad.gltf",
}

var main: ColossusMain
var cam: Camera3D
var at := Vector3.ZERO
var _sway := 0.0
var _sway_bone := -1
var _sway_skeleton: Skeleton3D


func _initialize() -> void:
	main = load("res://main.tscn").instantiate()
	main.syphon_enabled = false
	main.osc_port = TEST_PORT
	main.page_port = 0
	root.add_child(main)
	main.set_process_unhandled_input(false)
	_run()


func _process(delta: float) -> bool:
	# A bone that moves every frame, as a clip would: the skin is recomputed each frame.
	if _sway_skeleton and _sway_skeleton.is_visible_in_tree():
		_sway += delta
		_sway_skeleton.set_bone_pose_rotation(
			_sway_bone, Quaternion(Vector3.FORWARD, sin(_sway * 2.0) * 0.1)
		)
	return false


func _model(key: String) -> Node3D:
	var n: Node3D = load(MODELS[key]).instantiate()
	# glTF characters face +Z; the scene's forward is -Z.
	n.rotation.y = PI
	main.output.add_child(n)
	n.global_position = at
	return n


func _subjects() -> Dictionary:
	var standin_colossus := PlaceholderColossus.new()
	standin_colossus.height_m = COLOSSUS_HEIGHT
	standin_colossus.height_at = main.world.height_at
	main.output.add_child(standin_colossus)
	standin_colossus.reset_to(at, 0.0)
	# Standing and posing every frame (feet IK, head turn), as in a Climb.
	standin_colossus.seek = true
	standin_colossus.look_target = at
	var grock := _model("grock")
	var anim: AnimationPlayer = grock.find_child("AnimationPlayer", true, false)
	anim.get_animation("idle2").loop_mode = Animation.LOOP_LINEAR
	anim.play("idle2")
	var standin_wanderer := Wanderer.new()
	main.output.add_child(standin_wanderer)
	standin_wanderer.global_position = at
	standin_wanderer.process_mode = Node.PROCESS_MODE_DISABLED
	var nomad := _model("nomad")
	_sway_skeleton = nomad.find_child("Skeleton3D", true, false)
	_sway_bone = _sway_skeleton.find_bone("Spine")
	# Variants that price a trick: no shadow from the Colossus (the most a low shadow proxy can
	# win), and a Wanderer whose skeleton does not move (the share of the skinning).
	var grock_unshadowed := _model("grock")
	for mi: MeshInstance3D in grock_unshadowed.find_children("*", "MeshInstance3D", true, false):
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var unshadowed_anim: AnimationPlayer = grock_unshadowed.find_child(
		"AnimationPlayer", true, false
	)
	unshadowed_anim.play("idle2")
	return {
		"colossus stand-in": standin_colossus,
		"grock": grock,
		"grock no shadow": grock_unshadowed,
		"wanderer stand-in": standin_wanderer,
		"nomad": nomad,
		"nomad still": _model("nomad"),
	}


func _show(subjects: Dictionary, which: String) -> void:
	for k: String in subjects:
		subjects[k].visible = k == which


func _place_camera(view: Array, height: float) -> void:
	var d: float = view[1]
	var p := at + Vector3(0.0, 0.0, d)
	var ground: float = main.world.height_at.call(p.x, p.z)
	p.y = maxf(at.y + height * float(view[3]), ground + 1.7)
	cam.global_position = p
	cam.fov = view[2]
	cam.look_at(at + Vector3.UP * height * float(view[3]), Vector3.UP)


func _counts() -> Dictionary:
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	var vp := main.output.get_viewport_rid()
	var out := {}
	for pass_name: String in ["visible", "shadow"]:
		var t := (
			RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE
			if pass_name == "visible"
			else RenderingServer.VIEWPORT_RENDER_INFO_TYPE_SHADOW
		)
		out[pass_name + "_objects"] = RenderingServer.viewport_get_render_info(
			vp, t, RenderingServer.VIEWPORT_RENDER_INFO_OBJECTS_IN_FRAME
		)
		out[pass_name + "_tris"] = RenderingServer.viewport_get_render_info(
			vp, t, RenderingServer.VIEWPORT_RENDER_INFO_PRIMITIVES_IN_FRAME
		)
		out[pass_name + "_draws"] = RenderingServer.viewport_get_render_info(
			vp, t, RenderingServer.VIEWPORT_RENDER_INFO_DRAW_CALLS_IN_FRAME
		)
	return out


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


## Surfaces, LOD0 triangles, mesh instances, bones and texture bytes of a subject.
static func _build_facts(subject: Node) -> Dictionary:
	var textures := {}
	var surfaces := 0
	var tris := 0
	var instances := 0
	var bones := 0
	for n in subject.find_children("*", "", true, false) + [subject]:
		if n is Skeleton3D:
			bones += (n as Skeleton3D).get_bone_count()
		if not n is MeshInstance3D:
			continue
		var mi := n as MeshInstance3D
		instances += 1
		for s in mi.mesh.get_surface_count():
			surfaces += 1
			var info: Dictionary = RenderingServer.mesh_get_surface(mi.mesh.get_rid(), s)
			var idx: int = info.get("index_count", 0)
			tris += idx / 3 if idx > 0 else int(info.get("vertex_count", 0)) / 3
			var mat := mi.get_active_material(s)
			if mat is BaseMaterial3D:
				for p in mat.get_property_list():
					var v: Variant = mat.get(p["name"])
					if v is Texture2D:
						textures[(v as Texture2D).get_rid()] = v
	# Bytes as stored on the GPU: the format Godot uploaded and the mip chain (read back once).
	var tex_bytes := 0
	for rid: RID in textures:
		var img: Image = (textures[rid] as Texture2D).get_image()
		if img:
			tex_bytes += img.get_data_size()
	return {
		"mesh_instances": instances,
		"surfaces": surfaces,
		"tris_lod0": tris,
		"bones": bones,
		"textures": textures.size(),
		"texture_mb": snappedf(tex_bytes / 1048576.0, 0.01),
	}


func _run() -> void:
	await process_frame
	for key: String in MODELS:
		if not ResourceLoader.exists(MODELS[key]):
			print("%s is missing: see godot/colossus/assets/MODELS.md (make godot-models)" % key)
			quit(1)
			return
	at = Land.ARENA
	at.y = main.world.height_at.call(at.x, at.z)
	main.colossus.visible = false
	main.colossus.process_mode = Node.PROCESS_MODE_DISABLED
	main.wanderer.visible = false
	main.wanderer.process_mode = Node.PROCESS_MODE_DISABLED
	main.director.process_mode = Node.PROCESS_MODE_DISABLED
	cam = Camera3D.new()
	cam.far = main.director.far
	cam.near = main.director.near
	main.output.add_child(cam)
	cam.current = true
	var subjects := _subjects()
	await create_timer(5.0).timeout
	Engine.max_fps = 0
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	var report := {"subjects": {}, "rows": [], "driver": RenderingServer.get_video_adapter_name()}
	for k: String in subjects:
		report["subjects"][k] = _build_facts(subjects[k])
		print("%-18s %s" % [k, report["subjects"][k]])
	var groups := [
		[["colossus stand-in", "grock", "grock no shadow"], COLOSSUS_VIEWS, COLOSSUS_HEIGHT],
		[["wanderer stand-in", "nomad", "nomad still"], WANDERER_VIEWS, 1.75],
	]
	for group: Array in groups:
		var who_all: Array = group[0]
		for view: Array in group[1]:
			_place_camera(view, group[2])
			_show(subjects, "")
			var empty: Dictionary = await _counts()
			var row := {"view": view[0], "distance_m": view[1], "fov": view[2]}
			for who: String in who_all:
				_show(subjects, who)
				var c: Dictionary = await _counts()
				for key: String in c:
					c[key] -= empty[key]
				row[who] = c
			var times := {"": []}
			for who: String in who_all:
				times[who] = []
			for r in ROUNDS:
				var order: Array = who_all + [""]
				for i in r % order.size():
					order.push_back(order.pop_front())
				for who: String in order:
					_show(subjects, who)
					times[who].append(await _median_ms())
			_show(subjects, "")
			for who: String in times:
				var t: Array = times[who]
				t.sort()
				var median: float = t[t.size() / 2]
				if who == "":
					row["empty_ms"] = snappedf(median, 0.01)
				else:
					row[who]["frame_ms"] = snappedf(median, 0.01)
					row[who]["frame_ms_rounds"] = t
			report["rows"].append(row)
			for who: String in who_all:
				var c: Dictionary = row[who]
				print(
					(
						"%-9s %-18s tris %7d (+%6d shadow)  draws %3d (+%3d shadow)  objects %2d  frame %.2f ms"
						% [
							view[0],
							who,
							c["visible_tris"],
							c["shadow_tris"],
							c["visible_draws"],
							c["shadow_draws"],
							c["visible_objects"],
							c["frame_ms"],
						]
					)
				)
			print("%-9s empty frame %.2f ms" % [view[0], row["empty_ms"]])
	var args := OS.get_cmdline_user_args()
	var out_path := args[0] if args.size() > 0 else "/tmp/colossus-model-cost.json"
	var f := FileAccess.open(out_path, FileAccess.WRITE)
	f.store_string(JSON.stringify(report, "  "))
	f.close()
	print("written ", out_path)
	quit()
