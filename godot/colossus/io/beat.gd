class_name Beat
## Beat helpers. Pure.

const FALLBACK_BPM := 90.0


## Number of fallback beats that have started by time `t`. Counting beats instead of sampling
## a pulse keeps every beat at any frame rate or time scale.
static func fallback_count(t: float, bpm: float = FALLBACK_BPM) -> int:
	return floori(t * bpm / 60.0)


static func rising(previous: float, current: float, threshold: float = 0.5) -> bool:
	return previous < threshold and current >= threshold


## Pull a step phase (0..1 per step) forward onto the coming step boundary when within `window`,
## so footfalls drift onto beats. Never pulls backward: a step only ever moves forward.
static func nudge(step_phase: float, window: float = 0.15, pull: float = 0.5) -> float:
	var p := fposmod(step_phase, 1.0)
	if 1.0 - p > window:
		return p
	return p + (1.0 - p) * pull
