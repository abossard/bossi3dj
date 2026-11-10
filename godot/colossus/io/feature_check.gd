class_name FeatureCheck
extends RefCounted
## The scene's self-check, one implementation for the page ("Check all") and `make godot-check`.
## Per control: drive it through the same path as OSC, let the scene step, read the number that
## the scene acts on (SceneProbe) and judge: effect, no effect or error. Values and holds are put
## back as found at the end; the Phase ends in Approach.

const EFFECT := "effect"
const NO_EFFECT := "no effect"
const ERROR := "error"
## Relative tolerance between the observed and the expected scene value.
const TOLERANCE := 0.02
## Frames the scene gets to act on a write: world values apply in the physics step.
const SETTLE_PHYSICS := 3
const SETTLE_PROCESS := 2
## Longest wait for a Phase or a Shake, in physics frames (60 per second of scene time).
const WAIT_FRAMES := 1800
const PULSES := 4
const OSC_ADDRESS := "/vj/fog"
const OSC_VALUE := 0.7

## What a row needs before it can act, by name: the one place for preconditions.
const NEEDS := {
	"wanderer_on_colossus": "Shake acts only while the Wanderer hangs on the Colossus",
}

## One row per control, in the order they run. `kind` picks the procedure, `probe` the SceneProbe
## key judged, `want` the expected shot or Phase.
const TABLE := [
	{"id": "level", "kind": "sweep", "address": "/vj/level", "probe": "sun_energy"},
	{"id": "bass", "kind": "sweep", "address": "/vj/bass", "probe": "weight"},
	{"id": "fog", "kind": "sweep", "address": "/vj/fog", "probe": "fog_density"},
	{"id": "fog_height", "kind": "sweep", "address": "/vj/fog_height", "probe": "fog_height"},
	{"id": "haze", "kind": "sweep", "address": "/vj/haze", "probe": "haze_density"},
	{"id": "intensity", "kind": "sweep", "address": "/vj/intensity", "probe": "exposure"},
	{"id": "shot_1", "kind": "shot", "address": "/vj/cam", "want": 1},
	{"id": "shot_2", "kind": "shot", "address": "/vj/cam", "want": 2},
	{"id": "shot_3", "kind": "shot", "address": "/vj/cam", "want": 3},
	{"id": "shot_4", "kind": "shot", "address": "/vj/cam", "want": 4},
	{"id": "shot_5", "kind": "shot", "address": "/vj/cam", "want": 5},
	{"id": "shot_auto", "kind": "auto", "address": "/vj/cam"},
	{"id": "beat", "kind": "beat", "address": "/vj/beat"},
	{"id": "beat_simulator", "kind": "simulator", "address": "/vj/beat"},
	{"id": "osc_packet", "kind": "osc", "address": OSC_ADDRESS},
	{"id": "hold", "kind": "hold", "address": OSC_ADDRESS},
	{"id": "defaults", "kind": "defaults"},
	{"id": "phase_climb", "kind": "phase", "want": "CLIMB"},
	{"id": "shake", "kind": "shake", "address": "/vj/shock", "needs": "wanderer_on_colossus"},
	{"id": "phase_fall", "kind": "phase", "want": "FALL"},
	{"id": "phase_reset", "kind": "phase", "want": "RESET"},
	{"id": "phase_approach", "kind": "phase", "want": "APPROACH"},
]

var main: ColossusMain
## One dictionary per finished row: id, kind, address, verdict, detail, observed, expected, ms.
var results: Array[Dictionary] = []
var running := false
var current := ""

var _vj: VjSignals
var _tree: SceneTree


func _init(scene: ColossusMain) -> void:
	main = scene
	_vj = scene.vj
	_tree = scene.get_tree()


## "effect" when the observations follow the expected scene values and move, "no effect" when
## they never moved, "error" when they moved to the wrong value. Pure.
static func sweep_verdict(got: Array, want: Array) -> String:
	if got.size() != want.size() or got.is_empty():
		return ERROR
	var lo: float = got.min()
	var hi: float = got.max()
	if is_equal_approx(lo, hi):
		return NO_EFFECT
	for i in got.size():
		if not close(got[i], want[i]):
			return ERROR
	return EFFECT


## Observed is the wanted value: effect; nothing moved from `before`: no effect; else error. Pure.
static func change_verdict(before: float, after: float, want: float) -> String:
	if is_equal_approx(after, want):
		return EFFECT
	return NO_EFFECT if is_equal_approx(after, before) else ERROR


## At least `want` events seen: effect; none: no effect; some: error. Pure.
static func count_verdict(seen: int, want: int) -> String:
	if seen >= want:
		return EFFECT
	return NO_EFFECT if seen == 0 else ERROR


static func close(a: float, b: float) -> bool:
	return absf(a - b) <= TOLERANCE * maxf(absf(a), absf(b)) + 1e-9


static func count_of(rows: Array, verdict: String) -> int:
	var n := 0
	for r: Dictionary in rows:
		if r["verdict"] == verdict:
			n += 1
	return n


## Run the rows named in `ids`, or all. Await it; progress shows in `results` and `current`.
func run(ids: Array = []) -> Array[Dictionary]:
	running = true
	results.clear()
	var values := {}
	for a: String in VjMap.addresses():
		values[a] = _vj.value(a)
	var holds := _vj.held_addresses()
	_vj.release_holds()
	for row: Dictionary in TABLE:
		if not ids.is_empty() and not ids.has(row["id"]):
			continue
		current = row["id"]
		var started := Time.get_ticks_msec()
		var r: Dictionary = await _run_row(row)
		r["ms"] = Time.get_ticks_msec() - started
		results.append(r)
	current = "restore"
	await _restore(values, holds)
	current = ""
	running = false
	return results


func _restore(values: Dictionary, holds: Array) -> void:
	if main.page:
		main.page.stop_sim()
	_vj.release_holds()
	for a: String in values:
		_vj.apply(a, values[a], VjSignals.SOURCE_PAGE)
	for a: String in holds:
		_vj.set_hold(a, true)
	main.arc.go_to(Arc.Phase.APPROACH)
	await _until(func() -> bool: return main.arc.phase == Arc.Phase.APPROACH)
	await _settle()


func _run_row(row: Dictionary) -> Dictionary:
	var need: String = row.get("needs", "")
	if need != "":
		var why := await _prepare(need)
		if why != "":
			return _result(row, ERROR, "precondition %s: %s" % [need, why])
	var r := _result(row, ERROR, "unknown kind %s" % row["kind"])
	match row["kind"]:
		"sweep":
			r = await _sweep(row)
		"shot":
			r = await _shot(row)
		"auto":
			r = await _auto(row)
		"beat":
			r = await _beat(row)
		"simulator":
			r = await _simulator(row)
		"osc":
			r = await _osc(row)
		"hold":
			r = await _hold(row)
		"defaults":
			r = await _defaults(row)
		"phase":
			r = await _phase(row)
		"shake":
			r = await _shake(row)
	return r


func _result(
	row: Dictionary,
	verdict: String,
	detail: String,
	observed: Variant = null,
	expected: Variant = null
) -> Dictionary:
	return {
		"id": row["id"],
		"kind": row["kind"],
		"address": row.get("address", ""),
		"verdict": verdict,
		"detail": detail,
		"observed": observed,
		"expected": expected,
	}


func _settle() -> void:
	for i in SETTLE_PHYSICS:
		await _tree.physics_frame
	for i in SETTLE_PROCESS:
		await _tree.process_frame


func _until(cond: Callable, limit: int = WAIT_FRAMES) -> bool:
	for i in limit:
		if cond.call():
			return true
		await _tree.physics_frame
	return cond.call()


func _probe(key: String) -> Variant:
	return SceneProbe.read(main)[key]


func _write(address: String, v: float) -> void:
	_vj.apply(address, v, VjSignals.SOURCE_PAGE)


## Make the precondition true. Returns "" when it holds, else why not.
func _prepare(need: String) -> String:
	if need != "wanderer_on_colossus":
		return "unknown precondition"
	main.arc.go_to(Arc.Phase.CLIMB)
	if not await _until(func() -> bool: return main.arc.phase == Arc.Phase.CLIMB):
		return "the Arc did not reach Climb"
	if main.wanderer.on_colossus():
		return ""
	var low: GrabPoint = null
	for p in main.colossus.grab_points():
		if low == null or p.global_position.y < low.global_position.y:
			low = p
	main.wanderer.place_at(low.global_position)
	main.wanderer.grab(main.wanderer.nearest_grip(Wanderer.REACH))
	await _settle()
	return "" if main.wanderer.on_colossus() else "no Grab Point within reach"


func _sweep(row: Dictionary) -> Dictionary:
	var address: String = row["address"]
	var spec: Dictionary = VjMap.ROWS[address]
	var got: Array[float] = []
	var want: Array[float] = []
	for v: float in [spec["lo"], spec["rest"], spec["hi"]]:
		_write(address, v)
		await _settle()
		got.append(float(_probe(row["probe"])))
		want.append(VjMap.scene_value(address, v))
	var verdict := sweep_verdict(got, want)
	return _result(
		row, verdict, "%s at min, default, max" % row["probe"], _round(got), _round(want)
	)


func _shot(row: Dictionary) -> Dictionary:
	var n: int = row["want"]
	_write("/vj/cam", 0.0)
	await _settle()
	var before := int(_probe("shot"))
	_write("/vj/cam", float(n))
	await _settle()
	var after := int(_probe("shot"))
	var verdict := change_verdict(before, after, n)
	if verdict == EFFECT and int(_probe("pinned")) != n:
		verdict = ERROR
	return _result(row, verdict, "director shot after pinning %d" % n, after, n)


func _auto(row: Dictionary) -> Dictionary:
	_write("/vj/cam", 3.0)
	await _settle()
	var before := int(_probe("pinned"))
	_write("/vj/cam", 0.0)
	await _settle()
	var after := int(_probe("pinned"))
	return _result(row, change_verdict(before, after, 0), "pinned shot after auto", after, 0)


func _beat(row: Dictionary) -> Dictionary:
	_write("/vj/beat", 0.0)
	await _settle()
	var before := int(_probe("beats"))
	for i in PULSES:
		_write("/vj/beat", 1.0)
		await _tree.process_frame
		await _tree.process_frame
		_write("/vj/beat", 0.0)
		await _tree.process_frame
		await _tree.process_frame
	var seen := int(_probe("beats")) - before
	return _result(row, count_verdict(seen, PULSES), "beats counted for %d pulses" % PULSES, seen)


func _simulator(row: Dictionary) -> Dictionary:
	if main.page == null:
		return _result(row, ERROR, "the control page is off (page_port 0)")
	var before := int(_probe("beats"))
	main.page.start_sim(240.0, 0)
	await _until(func() -> bool: return int(_probe("beats")) - before >= PULSES, 600)
	var seen := int(_probe("beats")) - before
	main.page.stop_sim()
	return _result(row, count_verdict(seen, PULSES), "beats counted from the simulator", seen)


## A real datagram to the OSC port: proves the udp path, not only the shared write.
func _osc(row: Dictionary) -> Dictionary:
	_write(OSC_ADDRESS, 0.1)
	await _settle()
	var packets := _vj.packets
	var udp := PacketPeerUDP.new()
	udp.set_dest_address("127.0.0.1", _vj.port)
	udp.put_packet(OscDecode.encode_float(OSC_ADDRESS, OSC_VALUE))
	await _until(func() -> bool: return _vj.packets > packets, 120)
	udp.close()
	await _settle()
	var got := _vj.value(OSC_ADDRESS)
	var verdict := change_verdict(0.1, got, OSC_VALUE)
	return _result(row, verdict, "value after one udp packet", _round([got]), OSC_VALUE)


func _hold(row: Dictionary) -> Dictionary:
	_write(OSC_ADDRESS, 0.9)
	_vj.set_hold(OSC_ADDRESS, true)
	var dropped := _vj.dropped
	var udp := PacketPeerUDP.new()
	udp.set_dest_address("127.0.0.1", _vj.port)
	udp.put_packet(OscDecode.encode_float(OSC_ADDRESS, 0.1))
	await _until(func() -> bool: return _vj.dropped > dropped, 120)
	udp.close()
	await _settle()
	var got := _vj.value(OSC_ADDRESS)
	_vj.set_hold(OSC_ADDRESS, false)
	var held_ok := _vj.dropped == dropped + 1 and is_equal_approx(got, 0.9)
	var verdict := EFFECT if held_ok else (NO_EFFECT if is_equal_approx(got, 0.1) else ERROR)
	return _result(row, verdict, "value after an OSC packet against a hold", got, 0.9)


func _defaults(row: Dictionary) -> Dictionary:
	for a: String in VjMap.addresses():
		_write(a, float(VjMap.ROWS[a]["hi"]))
	_vj.set_hold("/vj/fog", true)
	_vj.reset_defaults()
	await _settle()
	var off := 0.0
	for a: String in VjMap.addresses():
		off = maxf(off, absf(_vj.value(a) - VjMap.rest(a)))
	var ok := is_zero_approx(off) and _vj.held_addresses().is_empty()
	return _result(row, EFFECT if ok else ERROR, "largest distance from a rest value", off, 0.0)


func _phase(row: Dictionary) -> Dictionary:
	var want: Arc.Phase = Arc.Phase[row["want"]]
	var before := main.arc.phase
	main.arc.go_to(want)
	var reached: bool = await _until(func() -> bool: return main.arc.phase == want)
	var verdict := EFFECT if reached else (NO_EFFECT if main.arc.phase == before else ERROR)
	return _result(
		row,
		verdict,
		"Phase after the jump",
		Arc.name_of(main.arc.phase),
		Arc.name_of(want),
	)


func _shake(row: Dictionary) -> Dictionary:
	var shocks := int(_probe("shocks"))
	_vj.fire("/vj/shock", 1.0)
	var peak := 0.0
	for i in WAIT_FRAMES:
		await _tree.physics_frame
		peak = maxf(peak, float(_probe("shake_roll")))
		if peak > 0.0 and not bool(_probe("shaking")):
			break
	var seen := int(_probe("shocks")) - shocks
	var verdict := EFFECT if peak > 0.01 and seen == 1 else (NO_EFFECT if peak == 0.0 else ERROR)
	return _result(row, verdict, "largest Shake roll in radians", snappedf(peak, 0.001), 0.01)


func _round(values: Array) -> Array:
	var out: Array = []
	for v: float in values:
		out.append(snappedf(v, 0.000001))
	return out
