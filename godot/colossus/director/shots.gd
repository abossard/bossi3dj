class_name Shots
## The director's five shots and which one to take. Pure: decided from Phase, bar count and events.

enum Shot { SCALE_WIDE = 1, LOW_HERO = 2, OVER_SHOULDER = 3, CLOSE_GRIP = 4, AERIAL = 5 }

const MAX_AERIAL_BARS := 16


## Shot to cut to at a bar line. `bars_in_phase` counts bars since the Phase began.
static func pick(
	phase: Arc.Phase, bars_in_phase: int, shaking: bool, drop: bool, aerial_bars: int
) -> Shot:
	if shaking:
		return Shot.CLOSE_GRIP
	if drop and aerial_bars < MAX_AERIAL_BARS:
		return Shot.AERIAL
	match phase:
		Arc.Phase.APPROACH:
			return Shot.SCALE_WIDE if (bars_in_phase / 8) % 2 == 0 else Shot.LOW_HERO
		Arc.Phase.CLIMB:
			var cycle: Array[Shot] = [
				Shot.OVER_SHOULDER, Shot.CLOSE_GRIP, Shot.OVER_SHOULDER, Shot.LOW_HERO
			]
			return cycle[(bars_in_phase / 4) % cycle.size()]
		Arc.Phase.FALL:
			return Shot.SCALE_WIDE if bars_in_phase < 4 else Shot.CLOSE_GRIP
	return Shot.SCALE_WIDE


## Bars a shot holds before the director may cut again.
static func hold_bars(shot: Shot) -> int:
	match shot:
		Shot.LOW_HERO:
			return 8
		Shot.AERIAL:
			return 4
	return 4


static func lens_mm(shot: Shot) -> float:
	match shot:
		Shot.LOW_HERO:
			return 18.0
		Shot.OVER_SHOULDER:
			return 35.0
		Shot.CLOSE_GRIP:
			return 50.0
		Shot.AERIAL:
			return 28.0
	return 24.0


## Vertical field of view in degrees for a full-frame (24 mm tall) sensor.
static func fov(shot: Shot) -> float:
	return rad_to_deg(2.0 * atan(12.0 / lens_mm(shot)))
