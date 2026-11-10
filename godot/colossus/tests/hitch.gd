extends SceneTree
## Frame times of one Arc on the real renderer: every frame above THRESHOLD_MS with the Phase, the
## seconds in it and the fade, then the median and the worst frame per Phase. Walks Approach,
## Climb, Fall and lets Fall hand over to Reset by itself. No Syphon, no page, own OSC port.
## Godot --path godot/colossus --script res://tests/hitch.gd

const TEST_PORT := 19202
const THRESHOLD_MS := 30.0
const CLIMB_SECONDS := 6.0
const LIMIT_SECONDS := 60.0

var main: ColossusMain
var _frames := {}
var _slow: Array[String] = []
var _phase_t := 0.0
var _last_phase := -1
var _last_us := 0
var _elapsed := 0.0
var _climb_started := false


func _initialize() -> void:
	main = load("res://main.tscn").instantiate()
	main.syphon_enabled = false
	main.osc_port = TEST_PORT
	main.page_port = 0
	root.add_child(main)
	main.set_process_unhandled_input(false)


func _process(_delta: float) -> bool:
	var now := Time.get_ticks_usec()
	if _last_us == 0:
		_last_us = now
		return false
	var ms := (now - _last_us) / 1000.0
	_last_us = now
	_elapsed += ms / 1000.0
	var phase: int = main.arc.phase
	if phase != _last_phase:
		_last_phase = phase
		_phase_t = 0.0
		print("phase %s at %.1f s" % [Arc.name_of(phase), _elapsed])
	_phase_t += ms / 1000.0
	if _elapsed > 4.0:
		var key := Arc.name_of(phase)
		if not _frames.has(key):
			_frames[key] = []
		_frames[key].append(ms)
		if ms > THRESHOLD_MS:
			_slow.append(
				(
					"slow %.0f ms  %s %.2f s in  fade %.2f"
					% [ms, Arc.name_of(phase), _phase_t, main._fade.color.a]
				)
			)
	if phase == Arc.Phase.APPROACH and _elapsed > 4.0 and not _climb_started:
		_climb_started = true
		main.arc.send(Arc.Event.NEXT)
	if phase == Arc.Phase.CLIMB and _phase_t > CLIMB_SECONDS:
		main.arc.send(Arc.Event.NEXT)
	if _climb_started and phase == Arc.Phase.APPROACH and _elapsed > 10.0 and _phase_t > 3.0:
		_report()
		return true
	if _elapsed > LIMIT_SECONDS:
		_report()
		return true
	return false


func _report() -> void:
	for s in _slow:
		print(s)
	for key: String in _frames:
		var v: Array = _frames[key]
		v.sort()
		print(
			(
				"%s  frames %d  median %.1f ms  p95 %.1f  worst %.0f ms"
				% [key, v.size(), v[v.size() / 2], v[int(v.size() * 0.95)], v[-1]]
			)
		)
