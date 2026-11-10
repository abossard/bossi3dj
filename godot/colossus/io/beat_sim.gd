class_name BeatSim
## Fake music for the control page, standing in for Magic. Pure: time and tempo in, signal out.
## A kick envelope at `bpm`, bass on the kick, a slow level swell and a shock every few beats.

## How long the shock stays high, in seconds.
const SHOCK_PULSE := 0.1


static func _beats(t: float, bpm: float) -> float:
	return t * bpm / 60.0


static func beat(t: float, bpm: float) -> float:
	return exp(-6.0 * fposmod(_beats(t, bpm), 1.0))


static func bass(t: float, bpm: float) -> float:
	return exp(-4.0 * fposmod(_beats(t, bpm), 1.0)) * 0.9


static func level(t: float, bpm: float) -> float:
	return 0.55 + 0.25 * sin(_beats(t, bpm) * PI / 16.0)


## 1.0 for SHOCK_PULSE seconds on every `every`-th beat, else 0. `every` 0 means never.
static func shock(t: float, bpm: float, every: int) -> float:
	if every <= 0:
		return 0.0
	var b := _beats(t, bpm)
	var into_beat := fposmod(b, 1.0) * 60.0 / bpm
	return 1.0 if int(floor(b)) % every == 0 and into_beat < SHOCK_PULSE else 0.0
