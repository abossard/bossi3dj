extends SceneTree
## Headless test runner.
## Godot --headless --path godot/colossus --script res://tests/run_tests.gd
## Each test is a table of cases run through one check.

var _failed := 0
var _passed := 0


func _init() -> void:
	_test_arc()
	_test_choose_link()
	_test_all_reach()
	_test_swing_settles()
	_test_takeover()
	_test_shots()
	_test_osc()
	_test_beat()
	_test_fov()
	_test_brain()
	print("%d passed, %d failed" % [_passed, _failed])
	quit(1 if _failed > 0 else 0)


func _check(name: String, got: Variant, want: Variant) -> void:
	var ok: bool = is_equal_approx(got, want) if (got is float and want is float) else got == want
	if ok:
		_passed += 1
	else:
		_failed += 1
		printerr("FAIL %s: got %s, want %s" % [name, str(got), str(want)])


func _test_arc() -> void:
	var ph := Arc.Phase
	var ev := Arc.Event
	var cases := [
		[ph.APPROACH, ev.NEXT, ph.CLIMB],
		[ph.CLIMB, ev.NEXT, ph.FALL],
		[ph.FALL, ev.NEXT, ph.FALL],
		[ph.FALL, ev.FALL_SETTLED, ph.RESET],
		[ph.RESET, ev.FADE_DONE, ph.APPROACH],
		[ph.RESET, ev.NEXT, ph.RESET],
		[ph.APPROACH, ev.FALL_SETTLED, ph.APPROACH],
		[ph.CLIMB, ev.RESET_NOW, ph.RESET],
		[ph.APPROACH, ev.FADE_DONE, ph.APPROACH],
	]
	for c in cases:
		_check("arc %s+%s" % [c[0], c[1]], Arc.next(c[0], c[1]), c[2])


func _test_choose_link() -> void:
	var up := Vector3.UP
	var cands: Array[Vector3] = [
		Vector3(1, 0, 0), Vector3(0, 0, 1), Vector3(-1, 0, 0), Vector3(0, 5, 0.2)
	]
	var cases := [
		["east", Vector3(1, 0, 0), 0],
		["north", Vector3(0, 0, 1), 1],
		["west", Vector3(-1, 0, 0), 2],
		["mostly east", Vector3(1, 0, 0.4), 0],
		["south has no link", Vector3(0, 0, -1), -1],
		["wish along normal", Vector3(0, 1, 0), -1],
		["diagonal ties to first best", Vector3(1, 0, 1), 0],
	]
	for c in cases:
		_check("choose_link %s" % c[0], GrabPath.choose_link(Vector3.ZERO, up, cands, c[1]), c[2])


func _test_all_reach() -> void:
	var cases := [
		["chain", [PackedInt32Array([1]), PackedInt32Array([2]), PackedInt32Array([])], 2, true],
		[
			"links one way",
			[PackedInt32Array([]), PackedInt32Array([0]), PackedInt32Array([1])],
			0,
			true
		],
		["island", [PackedInt32Array([1]), PackedInt32Array([]), PackedInt32Array([])], 1, false],
		["dead end below the goal", [PackedInt32Array([1]), PackedInt32Array([])], 0, false],
		["no goal", [PackedInt32Array([])], -1, false],
		["single", [PackedInt32Array([])], 0, true],
	]
	for c in cases:
		var links: Array[PackedInt32Array] = []
		links.assign(c[1])
		_check("all_reach %s" % c[0], GrabPath.all_reach(c[2], links), c[3])


func _test_swing_settles() -> void:
	var cases := [[0.6, 1.4], [-1.0, 1.0], [0.2, 3.0]]
	for c in cases:
		var s := Vector2(c[0], 0.0)
		for i in 600:
			s = GrabPath.swing(s.x, s.y, c[1], 1.0 / 60.0)
		_check("swing settles from %s at %s m" % [c[0], c[1]], absf(s.x) < 0.05, true)


func _test_takeover() -> void:
	var cases := [
		["untouched", [], false],
		["just touched", ["touch"], true],
		["3.9 s idle", ["touch", 3.9], true],
		["4.1 s idle", ["touch", 4.1], false],
		["retouched", ["touch", 3.0, "touch", 3.0], true],
	]
	for c in cases:
		var t := Takeover.new(4.0)
		for step in c[1]:
			if step is String:
				t.touch()
			else:
				t.tick(step)
		_check("takeover %s" % c[0], t.active(), c[2])


func _test_shots() -> void:
	var ph := Arc.Phase
	var sh := Shots.Shot
	var cases := [
		[ph.APPROACH, 0, false, false, 0, sh.SCALE_WIDE],
		[ph.APPROACH, 8, false, false, 0, sh.LOW_HERO],
		[ph.CLIMB, 0, true, false, 0, sh.CLOSE_GRIP],
		[ph.CLIMB, 4, false, false, 0, sh.CLOSE_GRIP],
		[ph.CLIMB, 0, false, false, 0, sh.OVER_SHOULDER],
		[ph.APPROACH, 0, true, false, 0, sh.CLOSE_GRIP],
		[ph.CLIMB, 0, false, true, 0, sh.AERIAL],
		[ph.CLIMB, 0, false, true, 16, sh.OVER_SHOULDER],
		[ph.FALL, 2, false, false, 0, sh.SCALE_WIDE],
		[ph.FALL, 6, false, false, 0, sh.CLOSE_GRIP],
		[ph.RESET, 0, false, false, 0, sh.SCALE_WIDE],
	]
	for c in cases:
		_check("shot %s" % [c.slice(0, 5)], Shots.pick(c[0], c[1], c[2], c[3], c[4]), c[5])


func _osc_message(address: String, args: Array) -> PackedByteArray:
	var b := _osc_string(address)
	var tags := ","
	var body := PackedByteArray()
	for a in args:
		var four := PackedByteArray()
		four.resize(4)
		if a is float:
			tags += "f"
			four.encode_float(0, a)
		else:
			tags += "i"
			four.encode_s32(0, a)
		four.reverse()
		body.append_array(four)
	b.append_array(_osc_string(tags))
	b.append_array(body)
	return b


func _osc_string(s: String) -> PackedByteArray:
	var b := s.to_utf8_buffer()
	b.append(0)
	while b.size() % 4 != 0:
		b.append(0)
	return b


func _osc_bundle(messages: Array) -> PackedByteArray:
	var b := _osc_string("#bundle")
	var tt := PackedByteArray()
	tt.resize(8)
	b.append_array(tt)
	for m in messages:
		var size := PackedByteArray()
		size.resize(4)
		size.encode_s32(0, m.size())
		size.reverse()
		b.append_array(size)
		b.append_array(m)
	return b


func _test_osc() -> void:
	var cases := [
		["float", _osc_message("/vj/beat", [0.75]), [["/vj/beat", [0.75]]]],
		["int", _osc_message("/vj/cam", [3]), [["/vj/cam", [3]]]],
		["two args", _osc_message("/vj/x", [1.5, -2]), [["/vj/x", [1.5, -2]]]],
		[
			"bundle",
			_osc_bundle([_osc_message("/vj/bass", [0.25]), _osc_message("/vj/shock", [1.5])]),
			[["/vj/bass", [0.25]], ["/vj/shock", [1.5]]]
		],
		[
			"nested bundle",
			_osc_bundle([_osc_bundle([_osc_message("/vj/fog", [0.5])])]),
			[["/vj/fog", [0.5]]]
		],
		["garbage", PackedByteArray([1, 2, 3]), []],
		["truncated", _osc_message("/vj/beat", [0.75]).slice(0, 14), []],
	]
	for c in cases:
		_check("osc %s" % c[0], OscDecode.decode(c[1]), c[2])


func _test_beat() -> void:
	var cases := [
		["first beat at zero", Beat.fallback_count(0.0), 0],
		["before the second beat", Beat.fallback_count(60.0 / 90.0 - 0.001), 0],
		["second beat at 90 bpm", Beat.fallback_count(60.0 / 90.0 + 0.001), 1],
		["a minute is 90 beats", Beat.fallback_count(60.0), 90],
		["rising", Beat.rising(0.2, 0.8), true],
		["falling", Beat.rising(0.8, 0.2), false],
		["held high", Beat.rising(0.8, 0.9), false],
		["nudge never pulls a step back", Beat.nudge(0.1), 0.1],
		["nudge early step forward", Beat.nudge(0.9), 0.95],
		["nudge outside window", Beat.nudge(0.4), 0.4],
		["nudge on boundary", Beat.nudge(0.0), 0.0],
	]
	for c in cases:
		_check("beat %s" % c[0], c[1], c[2])


func _test_fov() -> void:
	var sh := Shots.Shot
	var cases := [
		[sh.SCALE_WIDE, 53.13],
		[sh.LOW_HERO, 67.38],
		[sh.OVER_SHOULDER, 37.85],
		[sh.CLOSE_GRIP, 26.99],
		[sh.AERIAL, 46.40]
	]
	for c in cases:
		_check("fov %s" % c[0], snappedf(Shots.fov(c[0]), 0.01), c[1])


func _test_brain() -> void:
	var ph := Arc.Phase
	var o := Vector3.ZERO
	var cases := [
		[
			"approach far walks to colossus",
			ph.APPROACH,
			false,
			Vector3(0, 0, 200),
			o,
			o,
			o,
			o,
			Vector3(0, 0, -1)
		],
		["approach near waits", ph.APPROACH, false, Vector3(0, 0, 50), o, o, o, o, o],
		[
			"climb on ground runs to entry",
			ph.CLIMB,
			false,
			Vector3(10, 0, 0),
			o,
			Vector3(0, 3, 0),
			o,
			o,
			Vector3(-1, 0, 0)
		],
		[
			"climb on colossus heads up",
			ph.CLIMB,
			true,
			o,
			o,
			o,
			Vector3(0, 5, 0),
			Vector3(0, 30, 0),
			Vector3(0, 1, 0)
		],
		["climb at head holds", ph.CLIMB, true, o, o, o, Vector3(0, 30, 0), Vector3(0, 30.2, 0), o],
		["fall holds", ph.FALL, true, o, o, o, o, Vector3(0, 30, 0), o],
		["reset holds", ph.RESET, false, Vector3(0, 0, 200), o, o, o, o, o],
	]
	for c in cases:
		var got := WandererBrain.wish(c[1], c[2], c[3], c[4], c[5], c[6], c[7])
		_check("brain %s" % c[0], got.is_equal_approx(c[8]), true)
