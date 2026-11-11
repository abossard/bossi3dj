class_name Shots
## The director's five shots and which one to take. Pure: decided from Phase, bar count and events.

enum Shot { SCALE_WIDE = 1, LOW_HERO = 2, OVER_SHOULDER = 3, CLOSE_GRIP = 4, AERIAL = 5 }

const MAX_AERIAL_BARS := 16
## The climb shots look at a dark body with the low dusk sun behind it: a lamp of this energy hangs
## on the camera (the sky's bounce), the exposure is lifted by this factor and the contrast eased
## to this share of the scene's, so the Wanderer and the surface he holds read (tests/climb_light.gd
## has the numbers). Every other shot keeps the dusk as it is.
const CLIMB_LAMP := 3.0
const CLIMB_EXPOSURE := 1.8
const CLIMB_CONTRAST := 1.0 / 1.2


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


## The look that belongs to a shot: x the energy of the lamp on the camera, y the exposure factor,
## z the share of the scene's contrast. Only the over-shoulder and close grip shots on the Colossus
## change it.
static func look(shot: Shot, climbing: bool) -> Vector3:
	if climbing and (shot == Shot.OVER_SHOULDER or shot == Shot.CLOSE_GRIP):
		return Vector3(CLIMB_LAMP, CLIMB_EXPOSURE, CLIMB_CONTRAST)
	return Vector3(0.0, 1.0, 1.0)
