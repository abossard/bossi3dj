class_name DebugOverlay
extends Control
## F1 overlay on the window only (never in the Syphon frame): Grab Points, links, state and timings.

var main: ColossusMain


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE


func _process(_delta: float) -> void:
	if visible:
		queue_redraw()


func _draw() -> void:
	var cam: Director = main.director
	var out_size := Vector2(ColossusMain.OUTPUT_SIZE)
	var k := minf(size.x / out_size.x, size.y / out_size.y)
	var origin := (size - out_size * k) * 0.5
	for p: GrabPoint in main.colossus.grab_points():
		if cam.is_position_behind(p.global_position):
			continue
		var a := origin + cam.unproject_position(p.global_position) * k
		for q in p.linked():
			if not cam.is_position_behind(q.global_position):
				draw_line(
					a,
					origin + cam.unproject_position(q.global_position) * k,
					Color(0.79, 0.64, 0.35, 0.5),
					1.0
				)
		var held: bool = main.wanderer.grip == p
		draw_circle(a, 5.0 if held else 3.0, Color("cfe3ee") if held else Color("c9a35a"))
	var lines := [
		"Phase %s" % Arc.name_of(main.arc.phase),
		"Colossus %s" % main.colossus.name,
		"Shot %d  %d mm" % [cam.shot, Shots.lens_mm(cam.shot)],
		(
			"Takeover wanderer %s  camera %s"
			% [main.wanderer_takeover.active(), cam.takeover.active()]
		),
		"OSC %s" % ("live" if main.vj.fresh() else "quiet, internal 90 BPM"),
		(
			"%d fps  %.1f ms"
			% [
				Engine.get_frames_per_second(),
				Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0
			]
		),
	]
	var font := get_theme_default_font()
	for i in lines.size():
		draw_string(
			font,
			Vector2(16, 28 + i * 20),
			lines[i],
			HORIZONTAL_ALIGNMENT_LEFT,
			-1,
			15,
			Color("d6d0c3")
		)
