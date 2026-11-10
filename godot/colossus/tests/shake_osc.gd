extends SceneTree
## A Shake started by real OSC: the Wanderer hangs on the Colossus (Climb), then
## tools/godot_shock_send.py sends /vj/shock packets over udp to the test port, as Magic does. The
## timeline of what the scene does is printed: the shocks it counts, the Shake, the shot, and the
## bar line that carries the drop mark (a shock of 1.4 or more). Pass lines and fail lines, exit
## code 1 on any fail.
## Godot --path godot/colossus --script res://tests/shake_osc.gd

const TEST_PORT := 19202
const SENDER := "res://../../tools/godot_shock_send.py"
## A shock of 1.0 (a plain Shake) at 0.5 s, then a drop (1.5) once the first Shake is over.
const SHOCKS := ["0.5:1.0", "6.0:1.5"]
const WATCH_SECONDS := 12.0

var main: ColossusMain
var _failed := 0
var _bars: Array[String] = []
var _samples: Array[Dictionary] = []


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


func _climb() -> void:
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


func _run() -> void:
	await _wait(4.0)
	await _climb()
	_check(main.wanderer.on_colossus(), "the Wanderer hangs on the Colossus in the Climb")
	main.vj.bar.connect(func(drop: bool) -> void: _bars.append("bar drop=%s" % drop))
	var before: int = main.vj.shocks
	var args := PackedStringArray(
		[ProjectSettings.globalize_path(SENDER), "--port", str(TEST_PORT)]
	)
	args.append_array(SHOCKS)
	OS.create_process("python3", args)
	var start := Time.get_ticks_msec()
	while (Time.get_ticks_msec() - start) / 1000.0 < WATCH_SECONDS:
		await _wait(0.1)
		var s := {
			"t": (Time.get_ticks_msec() - start) / 1000.0,
			"shocks": main.vj.shocks - before,
			"shake": main.colossus.is_shaking(),
			"shot": main.director.shot,
			"drop_pending": main.vj._drop_pending,
			"shock_value": main.vj.value("/vj/shock"),
			"bars": _bars.size(),
		}
		_samples.append(s)
	_report()
	quit(1 if _failed > 0 else 0)


## Print the moments something changed, then check the story.
func _report() -> void:
	var last := {}
	for s in _samples:
		var now := {
			"shocks": s["shocks"],
			"shake": s["shake"],
			"shot": s["shot"],
			"drop_pending": s["drop_pending"],
			"bars": s["bars"],
		}
		if now != last:
			print(
				(
					"%5.1f s  shock %.1f  shocks seen %d  shaking %s  shot %d  drop pending %s  bars %d"
					% [
						s["t"],
						s["shock_value"],
						s["shocks"],
						s["shake"],
						s["shot"],
						s["drop_pending"],
						s["bars"]
					]
				)
			)
			last = now
	for b in _bars:
		print(b)
	var first_shake := _samples.filter(func(s: Dictionary) -> bool: return s["shake"])
	_check(not first_shake.is_empty(), "a shock over OSC starts a Shake")
	_check(
		not first_shake.is_empty() and first_shake[0]["shot"] == Shots.Shot.CLOSE_GRIP,
		"the director cuts to the close grip when it starts"
	)
	_check(_samples[-1]["shocks"] == 2, "both shocks were counted (2 seen)")
	var pending := _samples.filter(func(s: Dictionary) -> bool: return s["drop_pending"])
	_check(not pending.is_empty(), "the shock of 1.5 marks a drop")
	_check(
		pending.is_empty() or pending[0]["t"] > 5.5,
		"the plain shock of 1.0 marks no drop (the first mark comes with the 1.5)"
	)
	_check(_bars.has("bar drop=true"), "a bar line carries the drop mark")
	# Shots.pick lets a Shake in progress win over a drop: the drop's bar lands inside the Shake
	# (1.5 s long) and the aerial cut waits for a drop that comes after it. Printed, not asserted.
	var aerial := _samples.any(func(s: Dictionary) -> bool: return s["shot"] == Shots.Shot.AERIAL)
	print("info  the drop cut to the aerial shot: %s" % aerial)
	print("%d failed" % _failed)
