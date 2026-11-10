class_name ColossusMain
extends Node
## Builds the Colossus Scene: a 1920x1080 output viewport (sent to Syphon and shown in the window)
## and the debug overlay drawn on the window only.

const OUTPUT_SIZE := Vector2i(1920, 1080)
const SPAWN := Land.ARENA + Vector3(0.0, 0.0, -250.0)
const FADE_SECONDS := 1.0
const SHRINE_START := Vector3(0.0, 0.0, -18.0)

@export var syphon_enabled := true
@export var syphon_server := "COLOSSUS_OUT"
## Tests set their own port so they never receive or steal the show's OSC.
@export var osc_port := VjSignals.PORT
## The control page (http) and its self-check. 0 turns it off. Tests use 19211.
@export var page_port := ControlServer.PORT

var output: SubViewport
var world: World
var colossus: Colossus
var wanderer: Wanderer
var director: Director
var arc: ArcState
var vj: VjSignals
var overlay: DebugOverlay
var page: ControlServer
var syphon: Node
## Engine frame count when the Syphon server started: the addon has no frame counter.
var syphon_since_frame := 0
var dust: Dust
var wanderer_takeover := Takeover.new(4.0)

var _fade: ColorRect
var _next_index := 0
var _steer := Basis.IDENTITY
var _steering := false


func _ready() -> void:
	InputActions.install()
	output = SubViewport.new()
	output.size = OUTPUT_SIZE
	output.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	if RenderingServer.get_current_rendering_driver_name() == "metal":
		output.scaling_3d_mode = Viewport.SCALING_3D_MODE_METALFX_TEMPORAL
		output.scaling_3d_scale = 0.75
	add_child(output)

	world = World.new()
	output.add_child(world)
	dust = Dust.new()
	output.add_child(dust)
	wanderer = Wanderer.new()
	wanderer.height_at = world.height_at
	output.add_child(wanderer)
	director = Director.new()
	director.height_at = world.height_at
	director.wanderer = wanderer
	output.add_child(director)
	director.current = true

	var film_layer := CanvasLayer.new()
	film_layer.layer = 1
	var film := ColorRect.new()
	film.set_anchors_preset(Control.PRESET_FULL_RECT)
	film.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var film_mat := ShaderMaterial.new()
	film_mat.shader = load("res://world/film.gdshader")
	film.material = film_mat
	film_layer.add_child(film)
	output.add_child(film_layer)

	var fade_layer := CanvasLayer.new()
	fade_layer.layer = 2
	_fade = ColorRect.new()
	_fade.color = Color(0.043, 0.051, 0.063, 0.0)
	_fade.set_anchors_preset(Control.PRESET_FULL_RECT)
	_fade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	fade_layer.add_child(_fade)
	output.add_child(fade_layer)

	var screen := TextureRect.new()
	screen.texture = output.get_texture()
	screen.set_anchors_preset(Control.PRESET_FULL_RECT)
	screen.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	screen.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	screen.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(screen)

	vj = VjSignals.new()
	vj.port = osc_port
	add_child(vj)
	if page_port > 0:
		page = ControlServer.new()
		page.main = self
		page.port = page_port
		add_child(page)
	arc = ArcState.new()
	add_child(arc)
	overlay = DebugOverlay.new()
	overlay.main = self
	overlay.visible = false
	add_child(overlay)

	_start_arc()
	director.set_phase(arc.phase)

	vj.beat.connect(func() -> void: colossus.on_beat())
	vj.bar.connect(func(drop: bool) -> void: director.on_bar(drop))
	vj.shock.connect(func(_s: float) -> void: _shake())
	arc.phase_changed.connect(_on_phase)
	_start_syphon()


func _start_syphon() -> void:
	if not syphon_enabled:
		return
	if not ClassDB.class_exists("SyphonOutput"):
		push_warning("SyphonOutput not available; frames stay in the window only")
		return
	syphon = ClassDB.instantiate("SyphonOutput")
	syphon.set("server_name", syphon_server)
	syphon.set("texture", output.get_texture())
	syphon_since_frame = Engine.get_frames_drawn()
	add_child(syphon)


## Bring the next Colossus from the roster and put the Wanderer at the Shrine.
func _start_arc() -> void:
	if colossus:
		colossus.queue_free()
	var c := Roster.make(_next_index)
	_next_index = (_next_index + 1) % Roster.size()
	c.height_at = world.height_at
	c.roam_center = Land.ARENA
	c.roam_radius = Land.ROAM_RADIUS
	output.add_child(c)
	c.reset_to(SPAWN, PI)
	c.footfall.connect(_on_footfall)
	c.shaken.connect(wanderer.on_shaken)
	c.shaken.connect(director.on_shake)
	c.impact.connect(_on_impact)
	c.settled.connect(arc.body_settled)
	colossus = c
	wanderer.colossus = c
	director.colossus = c
	wanderer.place_at(Land.SHRINE + SHRINE_START)
	director.snap()


func _process(_delta: float) -> void:
	# macOS stops drawing a hidden window; Magic sits in front during a show
	# and still needs every frame.
	if not DisplayServer.window_can_draw():
		RenderingServer.force_draw(false)


func _physics_process(delta: float) -> void:
	wanderer_takeover.tick(delta)
	var v := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	var moving := v.length() > 0.1
	if moving or Input.is_action_pressed("run"):
		wanderer_takeover.touch()
	if moving and not _steering:
		# Latch the view when steering starts, so a director cut never turns a held key.
		_steer = director.global_transform.basis
	_steering = moving
	if wanderer_takeover.active():
		var right := Vector3(_steer.x.x, 0.0, _steer.x.z).normalized()
		var forward := Vector3(-_steer.z.x, 0.0, -_steer.z.z).normalized()
		var up := forward
		if wanderer.grip and wanderer.grip.normal().dot(Vector3.UP) < 0.7:
			up = Vector3.UP
		wanderer.wish = right * v.x + up * -v.y
		wanderer.running = Input.is_action_pressed("run")
	else:
		_autonomous()
	colossus.look_target = wanderer.global_position
	colossus.seek = arc.phase == Arc.Phase.CLIMB and not wanderer.on_colossus()
	world.apply_look(
		_scene("/vj/level"),
		_scene("/vj/fog"),
		_scene("/vj/fog_height"),
		_scene("/vj/haze"),
		_scene("/vj/intensity")
	)
	colossus.weight = _scene("/vj/bass")
	director.pin(int(_scene("/vj/cam")))


## The scene value of an address's current contract value.
func _scene(address: String) -> float:
	return VjMap.scene_value(address, vj.value(address))


func _autonomous() -> void:
	var entry := wanderer.global_position
	var nearest := INF
	for p in colossus.grab_points():
		var d := p.global_position.distance_squared_to(wanderer.global_position)
		if d < nearest:
			nearest = d
			entry = p.global_position
	var head := colossus.head_point()
	var grip_pos := wanderer.grip.global_position if wanderer.grip else Vector3.ZERO
	wanderer.wish = WandererBrain.wish(
		arc.phase,
		wanderer.on_colossus(),
		wanderer.global_position,
		colossus.global_position,
		entry,
		grip_pos,
		head.global_position if head else grip_pos
	)
	var chasing := arc.phase == Arc.Phase.CLIMB and not wanderer.on_colossus()
	wanderer.running = chasing
	if chasing:
		var g := wanderer.nearest_grip(Wanderer.REACH)
		if g:
			wanderer.grab(g)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and (event as InputEventMouseMotion).relative.length() > 0.5:
		director.look_by_mouse((event as InputEventMouseMotion).relative)
		return
	if not event.is_pressed() or event.is_echo():
		return
	if event.is_action("next_phase"):
		arc.send(Arc.Event.NEXT)
	elif event.is_action("reset"):
		arc.send(Arc.Event.RESET_NOW)
	elif event.is_action("shake"):
		_shake()
	elif event.is_action("next_colossus"):
		_next_index = (_next_index + 1) % Roster.size()
	elif event.is_action("grab"):
		_grab_or_let_go()
	elif event.is_action("debug"):
		overlay.visible = not overlay.visible
	else:
		for i in range(1, 6):
			if event.is_action("shot_%d" % i):
				director.force(i as Shots.Shot)


## Space: grab the nearest Grab Point (Approach and Climb), let go to the ground (Approach only).
func _grab_or_let_go() -> void:
	wanderer_takeover.touch()
	if wanderer.on_colossus():
		if arc.phase == Arc.Phase.APPROACH:
			wanderer.let_go()
	elif arc.phase == Arc.Phase.APPROACH or arc.phase == Arc.Phase.CLIMB:
		wanderer.grab(wanderer.nearest_grip(Wanderer.REACH))


## A Shake can happen in any Phase in which the Wanderer is on the Colossus.
func _shake() -> void:
	if wanderer.on_colossus():
		colossus.shake()


func _on_phase(phase: Arc.Phase) -> void:
	director.set_phase(phase)
	match phase:
		Arc.Phase.FALL:
			colossus.fall()
		Arc.Phase.RESET:
			var t := create_tween()
			t.tween_property(_fade, "color:a", 1.0, FADE_SECONDS)
			t.tween_callback(_start_arc)
			t.tween_property(_fade, "color:a", 0.0, FADE_SECONDS)
			t.tween_callback(func() -> void: arc.send(Arc.Event.FADE_DONE))


## The Wanderer rides the Fall down and lets go when the body hits the ground.
func _on_impact(at: Vector3) -> void:
	dust.puff(at, colossus.height_m * 0.9)
	if wanderer.on_colossus():
		wanderer.let_go()


func _on_footfall(at: Vector3, weight: float) -> void:
	if colossus.state == Colossus.State.ROAM:
		dust.puff(at, colossus.height_m * 0.2 * (0.5 + weight))
	var near := clampf(1.0 - director.global_position.distance_to(at) / 400.0, 0.0, 1.0)
	director.thump(weight * near)
