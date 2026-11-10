class_name VjSignals
extends Node
## Latest /vj/* values from Magic (relayed by lab.py). Each address is fresh for STALE seconds
## after its last packet; while /vj/beat is quiet an internal beat keeps time.

signal beat
signal bar(drop: bool)
signal shock(strength: float)

const PORT := 9202
const STALE := 2.0

## Set before the node enters the tree. Tests use their own port so they never meet the show.
var port := PORT

var _udp := PacketPeerUDP.new()
var _values := {}
var _rx := {}
var _last_rx := -INF
var _time := 0.0
var _beat := 0.0
var _beats := 0
var _fallback_beat := -1
var _shock := 0.0
var _drop_pending := false


func _ready() -> void:
	var err := _udp.bind(port, "127.0.0.1")
	if err != OK:
		push_warning("VjSignals: cannot listen on udp %d (%s)" % [port, error_string(err)])


## True while any OSC arrived in the last STALE seconds.
func fresh() -> bool:
	return _time - _last_rx < STALE


## The address's last value while it is fresh, else `default`.
func value(address: String, default: float) -> float:
	return float(_values[address]) if _is_fresh(address) else default


func _is_fresh(address: String) -> bool:
	return _time - float(_rx.get(address, -INF)) < STALE


func _process(delta: float) -> void:
	_time += delta
	while _udp.get_available_packet_count() > 0:
		for m in OscDecode.decode(_udp.get_packet()):
			var args: Array = m[1]
			if not args.is_empty() and (args[0] is float or args[0] is int):
				_values[m[0]] = float(args[0])
				_rx[m[0]] = _time
				_last_rx = _time
	if _is_fresh("/vj/beat"):
		var b := value("/vj/beat", 0.0)
		if Beat.rising(_beat, b):
			_on_beat()
		_beat = b
	else:
		_beat = 0.0
		var n := Beat.fallback_count(_time)
		if n != _fallback_beat:
			_fallback_beat = n
			_on_beat()
	var s := value("/vj/shock", 0.0)
	if Beat.rising(_shock, s):
		shock.emit(s)
		if s >= 1.4:
			_drop_pending = true
	_shock = s


func _on_beat() -> void:
	_beats += 1
	beat.emit()
	if _beats % 4 == 0:
		bar.emit(_drop_pending)
		_drop_pending = false
