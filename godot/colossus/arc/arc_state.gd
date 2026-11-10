class_name ArcState
extends Node
## Owns the current Phase of the Arc, and the one clock that ends the Fall.

signal phase_changed(phase: Arc.Phase)

## The Fall ends this long after the body settles...
const HOLD_AFTER_SETTLE := 4.0
## ...or after this long in any case, when it never settles.
const FALL_TIMEOUT := 15.0

var phase: Arc.Phase = Arc.Phase.APPROACH
var _in_phase := 0.0
var _settled_at := INF


func send(event: Arc.Event) -> void:
	var next := Arc.next(phase, event)
	if next == phase:
		return
	phase = next
	_in_phase = 0.0
	_settled_at = INF
	phase_changed.emit(next)


## The fallen body came to rest; the Fall holds on it, then ends.
func body_settled() -> void:
	if phase == Arc.Phase.FALL and _settled_at == INF:
		_settled_at = _in_phase


func _process(delta: float) -> void:
	_in_phase += delta
	if phase != Arc.Phase.FALL:
		return
	if _in_phase - _settled_at >= HOLD_AFTER_SETTLE or _in_phase >= FALL_TIMEOUT:
		send(Arc.Event.FALL_SETTLED)
