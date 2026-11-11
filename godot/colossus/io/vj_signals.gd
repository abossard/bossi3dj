class_name VjSignals
extends Node
## The one owner of the /vj/* values (table in VjMap). A value stays until the next write, as in
## Blender: Magic sends only on change. Writes come from OSC (udp), the control page, its beat
## simulator and the self-check, all through apply(). Only /vj/beat keeps a fallback: while it is
## quiet an internal beat keeps time.

signal beat
signal bar(drop: bool)
signal shock(strength: float)

const PORT := 9201
## /vj/beat counts as quiet after this long without a write; then the internal beat runs.
const STALE := 2.0
## A fired trigger stays high this long, more than a frame so the edge is seen.
const PULSE_SECONDS := 0.1

## Who wrote a value. Only the page overrides a hold; OSC and the simulator yield to it.
const SOURCE_OSC := "osc"
const SOURCE_PAGE := "page"
const SOURCE_SIM := "sim"
const SOURCE_DEFAULT := "default"

## Set before the node enters the tree. Tests use their own port so they never meet the show.
var port := PORT
## Datagrams and messages received, writes taken, writes a hold refused, addresses not in VjMap.
var packets := 0
var messages := 0
var applied := 0
var dropped := 0
var ignored := 0
## Beats and shocks the scene has seen, from any source.
var beats := 0
var shocks := 0

var _udp := PacketPeerUDP.new()
var _values := {}
var _source := {}
var _writes := {}
var _at := {}
var _held := {}
var _pulses := {}
var _last_rx := -INF
var _time := 0.0
var _beat := 0.0
var _fallback_beat := -1
var _shock := 0.0
var _drop_pending := false


func _init() -> void:
	reset_defaults()


func _ready() -> void:
	var err := _udp.bind(port, "127.0.0.1")
	if err != OK:
		push_warning("VjSignals: cannot listen on udp %d (%s)" % [port, error_string(err)])


## True while any OSC arrived in the last STALE seconds.
func fresh() -> bool:
	return _time - _last_rx < STALE


## The address's current value: the last one written, the rest value before any write.
func value(address: String) -> float:
	return float(_values[address])


## Write a value through the one path. A hold refuses every source but the page.
## Returns whether the value was taken.
func apply(address: String, v: float, source: String) -> bool:
	if not VjMap.known(address):
		ignored += 1
		return false
	if _held.has(address) and source != SOURCE_PAGE:
		dropped += 1
		return false
	_values[address] = VjMap.clamp_value(address, v)
	_source[address] = source
	_writes[address] = int(_writes.get(address, 0)) + 1
	_at[address] = _time
	applied += 1
	return true


## Fire a trigger: high for PULSE_SECONDS, then back to 0.
func fire(address: String, strength: float = 1.0) -> void:
	if apply(address, strength, SOURCE_PAGE):
		_pulses[address] = PULSE_SECONDS


func set_hold(address: String, on: bool) -> void:
	if on and VjMap.known(address):
		_held[address] = true
	else:
		_held.erase(address)


func is_held(address: String) -> bool:
	return _held.has(address)


func held_addresses() -> Array:
	return _held.keys()


func release_holds() -> void:
	_held.clear()


## Every value back to its rest value and every hold released.
func reset_defaults() -> void:
	_held.clear()
	_pulses.clear()
	for address: String in VjMap.addresses():
		_values[address] = VjMap.rest(address)
		_source[address] = SOURCE_DEFAULT
		_writes[address] = 0
		_at[address] = -INF


## One address as the state page shows it.
func describe(address: String) -> Dictionary:
	return {
		"value": _values[address],
		"scene": VjMap.scene_value(address, _values[address]),
		"source": _source[address],
		"writes": _writes[address],
		"age": snappedf(_time - float(_at[address]), 0.01) if _at[address] > -INF else null,
		"held": _held.has(address),
	}


func _process(delta: float) -> void:
	_time += delta
	while _udp.get_available_packet_count() > 0:
		packets += 1
		for m in OscDecode.decode(_udp.get_packet()):
			var args: Array = m[1]
			if not args.is_empty() and (args[0] is float or args[0] is int):
				messages += 1
				_last_rx = _time
				apply(m[0], float(args[0]), SOURCE_OSC)
	if _time - float(_at["/vj/beat"]) < STALE:
		var b := value("/vj/beat")
		if Beat.rising(_beat, b):
			_on_beat()
		_beat = b
	else:
		_beat = 0.0
		var n := Beat.fallback_count(_time)
		if n != _fallback_beat:
			_fallback_beat = n
			_on_beat()
	var s := value("/vj/shock")
	if Beat.rising(_shock, s):
		shocks += 1
		shock.emit(s)
		if s >= 1.4:
			_drop_pending = true
	_shock = s
	# After the edges are seen, so a slow frame never swallows a fired trigger.
	if not _pulses.is_empty():
		_end_pulses(delta)


func _end_pulses(delta: float) -> void:
	for address: String in _pulses.keys():
		_pulses[address] = float(_pulses[address]) - delta
		if float(_pulses[address]) <= 0.0:
			_pulses.erase(address)
			_values[address] = 0.0


func _on_beat() -> void:
	beats += 1
	beat.emit()
	if beats % 4 == 0:
		bar.emit(_drop_pending)
		_drop_pending = false
