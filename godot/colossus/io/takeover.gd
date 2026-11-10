class_name Takeover
extends RefCounted
## Performer Takeover of one target (Wanderer or camera).
## Active from any input until `idle` seconds pass without one.

var idle: float
var _since: float = INF


func _init(idle_seconds: float = 4.0) -> void:
	idle = idle_seconds


func touch() -> void:
	_since = 0.0


func tick(delta: float) -> void:
	_since += delta


## End the Takeover now.
func release() -> void:
	_since = INF


func active() -> bool:
	return _since < idle
