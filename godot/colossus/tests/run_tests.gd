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
	_test_fit_fov()
	_test_hero_lens()
	_test_stone_bumps()
	_test_brain()
	_test_vj_map()
	_test_vj_map_matches_contract()
	_test_values_persist()
	_test_hold_and_defaults()
	_test_step_toward()
	_test_go_to()
	_test_beat_sim()
	_test_http()
	_test_osc_encode()
	_test_check_verdicts()
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


func _test_fit_fov() -> void:
	# size m, distance m, narrowest lens deg, field of view wanted deg, the giant's height in px in a
	# 1080 px frame at that lens (0: not asked). The long walk shows him 100 px tall at least.
	var cases := [
		[28.0, 1700.0, 6.0, 6.0, 168.0],
		[28.0, 1700.0, 8.0, 8.0, 126.0],
		[28.0, 500.0, 6.0, 6.0, 577.0],
		[28.0, 150.0, 6.0, 15.9, 720.0],
		[28.0, 20.0, 6.0, 60.0, 0.0],
	]
	for c in cases:
		var fov := Director.fit_fov(c[0], c[1], c[2])
		_check("fit_fov %s" % [c.slice(0, 3)], snappedf(fov, 0.1), c[3])
		if c[4] > 0.0:
			var px: float = 1080.0 * c[0] / (2.0 * c[1] * tan(deg_to_rad(fov) * 0.5))
			_check("fit_fov px %s" % [c.slice(0, 3)], absf(px - c[4]) < c[4] * 0.02, true)


func _test_hero_lens() -> void:
	# lowest and highest elevation to hold (deg), narrowest lens (deg), field of view wanted (deg),
	# elevation to aim at (deg). A narrow span keeps the telephoto, a climb behind the Wanderer widens.
	var cases := [
		[-1.4, 0.7, 8.0, 8.0, -0.35],
		[-2.0, 2.0, 8.0, 8.0, 0.0],
		[-20.0, 2.0, 8.0, 33.0, -9.0],
		[-45.0, 5.0, 8.0, 60.0, -20.0],
	]
	for c in cases:
		var lens := Director.hero_lens(c[0], c[1], c[2])
		_check("hero_lens fov %s" % [c.slice(0, 3)], snappedf(lens.x, 0.1), c[3])
		_check("hero_lens aim %s" % [c.slice(0, 3)], snappedf(lens.y, 0.01), c[4])
		# Both ends of the span sit inside the frame.
		_check(
			"hero_lens holds %s" % [c.slice(0, 2)],
			lens.x * 0.5 >= maxf(absf(c[0] - lens.y), absf(c[1] - lens.y)) or lens.x == 60.0,
			true
		)


## The stone's normal map is made once per seed, and Roster.warm makes one for every Colossus.
func _test_stone_bumps() -> void:
	Roster.warm()
	var seeds: Array[int] = []
	for entry in Roster.ENTRIES:
		seeds.append(entry["seed"])
	for n in seeds:
		var first := PlaceholderColossus.stone_bumps(n)
		_check("stone bumps seed %d once" % n, PlaceholderColossus.stone_bumps(n) == first, true)
	_check(
		"stone bumps differ per seed",
		PlaceholderColossus.stone_bumps(seeds[0]) == PlaceholderColossus.stone_bumps(seeds[1]),
		false
	)


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


func _test_vj_map() -> void:
	var cases := [
		# address, wire value, stored value, scene value
		["/vj/fog_height", 0.41, 0.41, 38.95],
		["/vj/fog_height", 0.0, 0.0, 0.0],
		["/vj/fog_height", 1.0, 1.0, 95.0],
		["/vj/fog_height", 25.0, 1.0, 95.0],
		["/vj/fog_height", -3.0, 0.0, 0.0],
		["/vj/fog", 0.0, 0.0, 0.0],
		["/vj/fog", 0.35, 0.35, 0.00301],
		["/vj/fog", 1.0, 1.0, 0.0086],
		["/vj/fog", 7.0, 1.0, 0.0086],
		["/vj/haze", 0.0, 0.0, 0.0],
		["/vj/haze", 0.5, 0.5, 0.000125],
		["/vj/haze", 1.0, 1.0, 0.00025],
		["/vj/haze", 4.0, 1.0, 0.00025],
		["/vj/level", 0.0, 0.0, 1.0],
		["/vj/level", 0.5, 0.5, 1.8],
		["/vj/level", 1.0, 1.0, 2.6],
		["/vj/bass", 0.0, 0.0, 0.5],
		["/vj/bass", 0.5, 0.5, 0.75],
		["/vj/bass", 1.0, 1.0, 1.0],
		["/vj/intensity", 0.0, 0.0, 0.2],
		["/vj/intensity", 0.5, 0.5, 1.0],
		["/vj/intensity", 1.0, 1.0, 1.8],
		["/vj/intensity", 3.0, 1.0, 1.8],
		["/vj/cam", 0.0, 0.0, 0.0],
		["/vj/cam", 2.4, 2.0, 2.0],
		["/vj/cam", 2.6, 3.0, 3.0],
		["/vj/cam", 4.0, 4.0, 4.0],
		["/vj/cam", 10.0, 10.0, 10.0],
		["/vj/cam", 50.0, 10.0, 10.0],
		["/vj/cam", -1.0, 0.0, 0.0],
		["/vj/cam_auto", 1.0, 1.0, 1.0],
		["/vj/cam_auto", 0.0, 0.0, 0.0],
		["/vj/cam_auto", 0.4, 0.0, 0.0],
		["/vj/cam_auto", 0.6, 1.0, 1.0],
		["/vj/shock", 0.5, 0.5, 0.5],
		["/vj/shock", 9.0, 1.5, 1.5],
	]
	for c in cases:
		_check("map stores %s %s" % [c[0], c[1]], VjMap.clamp_value(c[0], c[1]), c[2])
		_check("map scene %s %s" % [c[0], c[1]], VjMap.scene_value(c[0], c[1]), c[3])
	# The wire default gives the tuned rest look: address, wire default, scene value.
	var rests := [
		["/vj/level", 0.5, 1.8],
		["/vj/bass", 0.0, 0.5],
		["/vj/beat", 0.0, 0.0],
		["/vj/shock", 0.0, 0.0],
		["/vj/intensity", 0.5, 1.0],
		["/vj/fog", 0.35, 0.00301],
		["/vj/fog_height", 0.41, 38.95],
		["/vj/haze", 1.0, 0.00025],
		["/vj/cam", 0.0, 0.0],
		["/vj/cam_auto", 1.0, 1.0],
	]
	for r in rests:
		_check("map wire default %s" % r[0], VjMap.rest(r[0]), r[1])
		_check("map rest look %s" % r[0], VjMap.scene_value(r[0], VjMap.rest(r[0])), r[2])
	_check("every address has a table row", VjMap.addresses().size(), rests.size())


## osc/contract.json is the one source of the contract; the table must not drift from its Godot
## column. Per address: wire range and default, the scene range where the contract gives one, an
## integer kind exactly for a shot or toggle, and no address in one side only.
func _test_vj_map_matches_contract() -> void:
	var path := ProjectSettings.globalize_path("res://").path_join("../../osc/contract.json")
	var text := FileAccess.get_file_as_string(path.simplify_path())
	var parsed: Variant = JSON.parse_string(text)
	_check("contract.json is read", parsed is Dictionary, true)
	if not parsed is Dictionary:
		return
	var wanted := []
	for c: Dictionary in (parsed as Dictionary)["controls"]:
		if c["godot"] == null:
			continue
		var a: String = c["address"]
		wanted.append(a)
		var g: Dictionary = c["godot"]
		var known := VjMap.known(a)
		_check("contract %s is in the table" % a, known, true)
		if not known:
			continue
		var row: Dictionary = VjMap.ROWS[a]
		_check("contract %s wire min" % a, float(row["lo"]), float(c["min"]))
		_check("contract %s wire max" % a, float(row["hi"]), float(c["max"]))
		_check("contract %s default" % a, float(row["rest"]), float(c["default"]))
		var whole: bool = row["kind"] == VjMap.Kind.SHOT or row["kind"] == VjMap.Kind.TOGGLE
		_check("contract %s integer kind" % a, whole, c["kind"] == "int")
		if g.has("min"):
			_check("contract %s scene min" % a, float(row["out_lo"]), float(g["min"]))
			_check("contract %s scene max" % a, float(row["out_hi"]), float(g["max"]))
	for a: String in VjMap.addresses():
		_check("table %s is in the contract" % a, wanted.has(a), true)


func _signals() -> VjSignals:
	var v := VjSignals.new()
	return v


func _test_values_persist() -> void:
	# A value stays until the next write, however long no packet comes.
	var cases := [
		["/vj/fog", 0.8, 0.8],
		["/vj/fog_height", 0.9, 0.9],
		["/vj/cam", 3.0, 3.0],
		["/vj/bass", 0.9, 0.9],
		["/vj/haze", 0.3, 0.3],
	]
	for c in cases:
		var v := _signals()
		_check("write %s taken" % c[0], v.apply(c[0], c[1], VjSignals.SOURCE_OSC), true)
		for i in 600:
			v._process(0.1)
		_check("%s after 60 s without a packet" % c[0], v.value(c[0]), c[2])
		v.free()
	var quiet := _signals()
	for i in 20:
		quiet._process(0.1)
	_check("internal beat while /vj/beat is quiet", quiet.beats >= 2, true)
	_check("unwritten value is its rest value", quiet.value("/vj/level"), 0.5)
	_check("unknown address is ignored", quiet.apply("/vj/hue", 0.5, VjSignals.SOURCE_OSC), false)
	_check("unknown address is counted", quiet.ignored, 1)
	quiet.free()
	var live := _signals()
	for i in 40:
		live.apply("/vj/beat", 0.0, VjSignals.SOURCE_OSC)
		live._process(0.1)
	_check("no internal beat while /vj/beat is written", live.beats, 0)
	live.free()


func _test_hold_and_defaults() -> void:
	# source, held, taken, value after writing 0.1 over a page value of 0.9
	var cases := [
		[VjSignals.SOURCE_OSC, true, false, 0.9],
		[VjSignals.SOURCE_SIM, true, false, 0.9],
		[VjSignals.SOURCE_PAGE, true, true, 0.1],
		[VjSignals.SOURCE_OSC, false, true, 0.1],
	]
	for c in cases:
		var v := _signals()
		v.apply("/vj/fog", 0.9, VjSignals.SOURCE_PAGE)
		v.set_hold("/vj/fog", c[1])
		_check("hold %s %s taken" % [c[0], c[1]], v.apply("/vj/fog", 0.1, c[0]), c[2])
		_check("hold %s %s value" % [c[0], c[1]], v.value("/vj/fog"), c[3])
		v.free()
	var v := _signals()
	for a: String in VjMap.addresses():
		v.apply(a, float(VjMap.ROWS[a]["hi"]), VjSignals.SOURCE_PAGE)
	v.set_hold("/vj/fog", true)
	v.reset_defaults()
	var off := 0.0
	for a: String in VjMap.addresses():
		off = maxf(off, absf(v.value(a) - VjMap.rest(a)))
	_check("defaults restore every rest value", off, 0.0)
	_check("defaults release holds", v.held_addresses().size(), 0)
	v.fire("/vj/shock", 1.0)
	_check("fire raises the trigger", v.value("/vj/shock"), 1.0)
	v._process(VjSignals.PULSE_SECONDS + 0.05)
	_check("fire ends after the pulse", v.value("/vj/shock"), 0.0)
	_check("fire counted one shock", v.shocks, 1)
	v.free()


func _test_step_toward() -> void:
	var ph := Arc.Phase
	var ev := Arc.Event
	var cases := [
		[ph.APPROACH, ph.APPROACH, -1],
		[ph.APPROACH, ph.CLIMB, ev.NEXT],
		[ph.APPROACH, ph.FALL, ev.NEXT],
		[ph.APPROACH, ph.RESET, ev.RESET_NOW],
		[ph.CLIMB, ph.APPROACH, ev.RESET_NOW],
		[ph.CLIMB, ph.FALL, ev.NEXT],
		[ph.FALL, ph.CLIMB, ev.RESET_NOW],
		[ph.FALL, ph.APPROACH, ev.RESET_NOW],
		[ph.FALL, ph.RESET, ev.RESET_NOW],
		[ph.RESET, ph.APPROACH, -1],
		[ph.RESET, ph.CLIMB, -1],
		[ph.RESET, ph.RESET, -1],
	]
	for c in cases:
		_check("step_toward %s to %s" % [c[0], c[1]], Arc.step_toward(c[0], c[1]), c[2])


func _test_go_to() -> void:
	var ph := Arc.Phase
	var ev := Arc.Event
	# start Phase, goal, events the clock or the performer sends afterwards, Phase at the end
	var cases := [
		["approach to fall", ph.APPROACH, ph.FALL, [], ph.FALL],
		["approach to climb", ph.APPROACH, ph.CLIMB, [], ph.CLIMB],
		["fall to approach waits in reset", ph.FALL, ph.APPROACH, [], ph.RESET],
		["fall to approach", ph.FALL, ph.APPROACH, [ev.FADE_DONE], ph.APPROACH],
		["fall to climb", ph.FALL, ph.CLIMB, [ev.FADE_DONE], ph.CLIMB],
		["climb to reset", ph.CLIMB, ph.RESET, [], ph.RESET],
		["performer Next ends the walk", ph.FALL, ph.CLIMB, [ev.NEXT, ev.FADE_DONE], ph.APPROACH],
	]
	for c in cases:
		var arc := ArcState.new()
		arc.phase = c[1]
		arc.go_to(c[2])
		for e in c[3]:
			arc.send(e)
		_check("go_to %s" % c[0], arc.phase, c[4])
		arc.free()


func _test_beat_sim() -> void:
	# time, bpm, beat, shock every 4
	var cases := [
		[0.0, 120.0, 1.0, 1.0],
		[0.05, 120.0, exp(-6.0 * 0.1), 1.0],
		[0.25, 120.0, exp(-6.0 * 0.5), 0.0],
		[0.5, 120.0, 1.0, 0.0],
		[1.0, 120.0, 1.0, 0.0],
		[2.0, 120.0, 1.0, 1.0],
	]
	for c in cases:
		_check("sim beat %s" % [c.slice(0, 2)], BeatSim.beat(c[0], c[1]), c[2])
		_check("sim shock %s" % [c.slice(0, 2)], BeatSim.shock(c[0], c[1], 4), c[3])
	_check("sim shock never", BeatSim.shock(0.0, 120.0, 0), 0.0)
	_check("sim bass on the kick", BeatSim.bass(0.0, 120.0), 0.9)
	_check("sim level starts mid", BeatSim.level(0.0, 120.0), 0.55)


func _test_http() -> void:
	var head := "POST /api/set?x=1 HTTP/1.1\r\nHost: 127.0.0.1:9211\r\nContent-Length: 7\r\n\r\n"
	var post := head + '{"a":1}'
	var cases := [
		["no blank line yet", "GET / HTTP/1.1\r\nHost: x\r\n".to_utf8_buffer(), {}],
		["empty", PackedByteArray(), {}],
		["body incomplete", post.substr(0, post.length() - 2).to_utf8_buffer(), {}],
		[
			"get",
			"GET /api/state HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n".to_utf8_buffer(),
			{
				"method": "GET",
				"path": "/api/state",
				"headers": {"host": "127.0.0.1"},
				"body": "",
			},
		],
		[
			"post with body and query",
			post.to_utf8_buffer(),
			{
				"method": "POST",
				"path": "/api/set",
				"headers": {"host": "127.0.0.1:9211", "content-length": "7"},
				"body": '{"a":1}',
			},
		],
	]
	for c in cases:
		_check("http parse %s" % c[0], HttpLite.parse(c[1]), c[2])
	var out := HttpLite.response(404, "text/plain", "no".to_utf8_buffer()).get_string_from_utf8()
	_check("http status line", out.begins_with("HTTP/1.1 404 Not Found\r\n"), true)
	_check("http length", out.contains("Content-Length: 2\r\n"), true)
	_check("http body", out.ends_with("\r\n\r\nno"), true)


func _test_osc_encode() -> void:
	var cases := [["/vj/fog", 0.7], ["/vj/fog_height", 25.0], ["/vj/cam", 3.0], ["/a", -1.5]]
	for c in cases:
		var got := OscDecode.decode(OscDecode.encode_float(c[0], c[1]))
		_check("osc round trip %s" % c[0], got.size() == 1 and got[0][0] == c[0], true)
		_check("osc round trip value %s" % c[0], got[0][1][0], c[1])


func _test_check_verdicts() -> void:
	var e := FeatureCheck.EFFECT
	var n := FeatureCheck.NO_EFFECT
	var x := FeatureCheck.ERROR
	var sweeps := [
		["follows", [1.4, 1.8, 2.6], [1.4, 1.8, 2.6], e],
		["within tolerance", [1.4, 1.81, 2.6], [1.4, 1.8, 2.6], e],
		["never moved", [0.5, 0.5, 0.5], [0.0, 0.5, 1.0], n],
		["wrong top", [0.0, 40.0, 30.0], [0.0, 40.0, 60.0], x],
		["empty", [], [], x],
		["length differs", [1.0], [1.0, 2.0], x],
	]
	for c in sweeps:
		_check("sweep verdict %s" % c[0], FeatureCheck.sweep_verdict(c[1], c[2]), c[3])
	var changes := [
		["reached", 0.0, 3.0, 3.0, e],
		["stayed", 0.0, 0.0, 3.0, n],
		["went elsewhere", 0.0, 2.0, 3.0, x],
	]
	for c in changes:
		_check("change verdict %s" % c[0], FeatureCheck.change_verdict(c[1], c[2], c[3]), c[4])
	var counts := [["all", 4, 4, e], ["more", 5, 4, e], ["none", 0, 4, n], ["some", 2, 4, x]]
	for c in counts:
		_check("count verdict %s" % c[0], FeatureCheck.count_verdict(c[1], c[2]), c[3])
	var ids := {}
	for row: Dictionary in FeatureCheck.TABLE:
		ids[row["id"]] = true
	_check("check rows have unique ids", ids.size(), FeatureCheck.TABLE.size())
	for row: Dictionary in FeatureCheck.TABLE:
		if row.has("needs"):
			_check(
				"precondition %s is described" % row["needs"],
				FeatureCheck.NEEDS.has(row["needs"]),
				true
			)
