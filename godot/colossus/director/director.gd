class_name Director
extends Camera3D
## The auto director: picks a shot on bar lines, follows like a heavy dolly,
## gives way to mouse Takeover and to a shot pinned over OSC.

const FOLLOW := 0.6
const AIM := 0.35
## The long walk (the Colossus is up to 1.6 km away): a shot that would show the giant a few pixels
## tall takes a telephoto lens aimed at it. The camera stays this far behind the Wanderer (m), at
## most, so it stays low on the Shrine's slope.
const WIDE_BACK_MAX := 24.0
const HERO_BACK := 24.0
## The close grip keeps this far from the surface the Wanderer hangs on (m).
const CLOSE_BACK := 3.0
## Room left around his upper body in the close grip for the Shake's swing and his climbing on
## while the dolly catches up (m).
const CLOSE_SWAY := 1.6
## Beyond this gap (m) the low hero shot goes telephoto: its own lens shows the giant under 100 px
## (about a tenth of the frame). The over-shoulder and close-grip shots stay on the Wanderer.
const HERO_RANGE := 200.0
## The narrowest lens (degrees of field of view) the long walk uses, per shot.
const WIDE_NARROWEST := 6.0
const HERO_NARROWEST := 8.0
## The low hero lens spans the Wanderer and the giant by this factor, so both sit inside the frame.
const HERO_SPAN_MARGIN := 1.5
## The low camera's line of sight to the Wanderer clears the land by this much (m), sampled
## SIGHT_SAMPLES times.
const SIGHT_MARGIN := 0.2
const SIGHT_SAMPLES := 16

var wanderer: Wanderer
var colossus: Colossus
var height_at: Callable = func(_x: float, _z: float) -> float: return 0.0
var phase: Arc.Phase = Arc.Phase.APPROACH
var shot: Shots.Shot = Shots.Shot.SCALE_WIDE
var takeover := Takeover.new(4.0)

var _bars_in_phase := 0
var _bars_on_shot := 0
var _aerial_bars := 0
var _pinned := 0
var _orbit := 0.0
var _thump := 0.0
var _yaw := 0.0
var _pitch := -0.2
var _snap := true
var _aim := Vector3.ZERO
var _time := 0.0
var _want_pos := Vector3.ZERO
var _want_aim := Vector3.ZERO
var _want_fov := 53.0
## Land samples along the line of sight on the long walk, reused every frame.
var _sight := PackedVector2Array()


func set_phase(p: Arc.Phase) -> void:
	phase = p
	_bars_in_phase = 0
	_cut_to(_pinned if _pinned > 0 else Shots.pick(p, 0, false, false, _aerial_bars))


func on_bar(drop: bool) -> void:
	_bars_in_phase += 1
	_bars_on_shot += 1
	_aerial_bars = _aerial_bars + 1 if shot == Shots.Shot.AERIAL else 0
	if takeover.active() or _pinned > 0:
		return
	if _bars_on_shot >= Shots.hold_bars(shot) or drop:
		var next := Shots.pick(phase, _bars_in_phase, colossus.is_shaking(), drop, _aerial_bars)
		if next != shot:
			_cut_to(next)


## A Shake started (connected to Colossus.shaken).
func on_shake(_strength: float) -> void:
	if wanderer.on_colossus() and not takeover.active() and _pinned == 0:
		if shot != Shots.Shot.CLOSE_GRIP:
			_cut_to(Shots.Shot.CLOSE_GRIP)


## Keys 1 to 5: cut now, ending any camera Takeover.
func force(s: Shots.Shot) -> void:
	takeover.release()
	_cut_to(s)


## /vj/cam: 1 to 5 hold that shot until released with 0, which hands the cut back.
func pin(s: int) -> void:
	if s == _pinned or s < 0 or s > Shots.Shot.AERIAL:
		return
	_pinned = s
	if s > 0:
		force(s as Shots.Shot)
	else:
		_cut_to(Shots.pick(phase, _bars_in_phase, false, false, _aerial_bars))


## The shot /vj/cam holds, 0 while the director cuts.
func pinned() -> int:
	return _pinned


## Jump to the current shot's framing on the next frame (after a teleport, hidden by a fade).
func snap() -> void:
	_snap = true


func thump(weight: float) -> void:
	_thump = maxf(_thump, weight)


func look_by_mouse(motion: Vector2) -> void:
	if not takeover.active():
		_yaw = rotation.y
		_snap = true
	takeover.touch()
	_yaw -= motion.x * 0.004
	_pitch = clampf(_pitch - motion.y * 0.004, -1.2, 0.5)


## Record the cut; _process applies lens and framing together on the next frame.
func _cut_to(s: Shots.Shot) -> void:
	shot = s
	_bars_on_shot = 0
	_snap = true


func _process(delta: float) -> void:
	if wanderer == null or colossus == null:
		return
	_time += delta
	var was_active := takeover.active()
	takeover.tick(delta)
	if was_active and not takeover.active():
		_cut_to(
			(
				_pinned
				if _pinned > 0
				else Shots.pick(phase, _bars_in_phase, false, false, _aerial_bars)
			)
		)
	if takeover.active():
		_takeover_place()
	else:
		_place(delta)
	var pos := _want_pos
	pos.y = maxf(pos.y, float(height_at.call(pos.x, pos.z)) + 0.3)
	if _snap:
		fov = _want_fov
		global_position = pos
		_aim = _want_aim
		_snap = false
	else:
		global_position = global_position.lerp(pos, 1.0 - exp(-delta / FOLLOW))
		_aim = _aim.lerp(_want_aim, 1.0 - exp(-delta / AIM))
		fov = lerpf(fov, _want_fov, 1.0 - exp(-delta / AIM))
	_thump = maxf(_thump - delta * 3.0, 0.0)
	# Offsets the rendered view only, so the shake never feeds back into the follow.
	v_offset = sin(_time * 40.0) * _thump * 0.15
	if global_position.distance_squared_to(_aim) > 0.01:
		look_at(_aim, Vector3.UP)
	if shot == Shots.Shot.CLOSE_GRIP and colossus.is_shaking():
		rotate_object_local(Vector3.FORWARD, colossus.roll)


func _takeover_place() -> void:
	var w := wanderer.global_position + Vector3.UP * 1.2
	var offset := (Vector3.BACK * 6.0).rotated(Vector3.RIGHT, _pitch).rotated(Vector3.UP, _yaw)
	_want_pos = w + offset
	_want_aim = w
	_want_fov = Shots.fov(Shots.Shot.SCALE_WIDE)


func _place(delta: float) -> void:
	var w := wanderer.global_position + Vector3.UP * 1.2
	var c := colossus.global_position
	var h := colossus.height_m
	var chest := c + Vector3.UP * h * 0.6
	var head_point := colossus.head_point()
	var head := head_point.global_position if head_point else chest
	var dir := Vector3(c.x - w.x, 0.0, c.z - w.z)
	dir = dir.normalized() if dir.length() > 0.1 else Vector3.FORWARD
	var side := dir.cross(Vector3.UP).normalized()
	var grip := wanderer.grip
	var gap := Vector3(c.x - w.x, 0.0, c.z - w.z).length()
	_want_fov = Shots.fov(shot)
	match shot:
		Shots.Shot.LOW_HERO:
			_want_pos = w + side * 3.5 - dir * 2.0 + Vector3.DOWN * 0.8
			if gap > HERO_RANGE:
				_long_walk(w, HERO_BACK, 1.5, -0.8, HERO_NARROWEST)
			else:
				_want_aim = head
		Shots.Shot.OVER_SHOULDER:
			if grip and grip.normal().dot(Vector3.UP) < 0.7:
				var climb_up := (head - grip.global_position).normalized()
				_want_pos = w + grip.normal() * 6.0 - climb_up * 2.5 + side * 1.5
				_want_aim = w + climb_up * 1.5
			elif grip:
				# Standing on top of the Colossus: behind the Wanderer, looking past him.
				var facing := -wanderer.global_transform.basis.z
				facing = Vector3(facing.x, 0.0, facing.z).normalized()
				_want_pos = w - facing * 4.0 + Vector3.UP * 1.0
				_want_aim = w + facing * 8.0 - Vector3.UP * 1.0
			else:
				_want_pos = w - dir * 4.0 + side + Vector3.UP * 0.3
				_want_aim = chest
		Shots.Shot.CLOSE_GRIP:
			var n := grip.normal() if grip else -dir
			# Aimed at the middle of his head, hands and hips, from far enough off the surface that
			# the lens holds them all: the Nomad hangs 2.4 m below the grip (the stand-in 1.7 m),
			# and a Shake swings him 0.6 m sideways.
			var body := wanderer.upper_body()
			var mid := (body[0] + body[1] + body[2]) / 3.0
			var span := maxf(body[0].distance_to(body[1]), body[1].distance_to(body[2]))
			span = maxf(span, body[0].distance_to(body[2])) + CLOSE_SWAY
			var back := maxf(CLOSE_BACK, span * 0.5 / tan(deg_to_rad(_want_fov) * 0.5))
			_want_pos = mid + n * back + side * 0.8
			_want_aim = mid
		Shots.Shot.AERIAL:
			_orbit += deg_to_rad(6.0) * delta
			_want_pos = c + Vector3(cos(_orbit) * 70.0, 60.0, sin(_orbit) * 70.0)
			_want_aim = chest
		_:
			if phase == Arc.Phase.FALL:
				# The collapse, seen across the topple from in front of the body.
				var front := -colossus.global_transform.basis.z
				front = Vector3(front.x, 0.0, front.z).normalized()
				var body := colossus.center()
				_want_pos = c + front * h * 2.6 + Vector3.UP * h * 0.25
				_want_aim = body
			else:
				# Telephoto from behind the Wanderer: the farther the giant, the farther back
				# and the longer the lens, so it towers over the small figure.
				var back := clampf(gap * 0.12, 9.0, WIDE_BACK_MAX)
				_want_pos = w - dir * back + Vector3.UP * (0.4 + back * 0.03)
				_want_aim = c + Vector3.UP * h * 0.45
				_want_fov = minf(_want_fov, fit_fov(h, gap + back, WIDE_NARROWEST))


## The long walk as a telephoto frame: the camera `back` m behind the Wanderer, `aside` m to his
## side and `rise` m above his eye. The lens and the aim span the Wanderer and the Colossus: from
## the lower of his feet and its feet to the higher of his head and its top, so both stay in frame
## wherever the ground climbs behind him. The lens is never narrower than `narrowest` degrees.
func _long_walk(w: Vector3, back: float, aside: float, rise: float, narrowest: float) -> void:
	var c := colossus.global_position
	var h := colossus.height_m
	var dir := Vector3(c.x - w.x, 0.0, c.z - w.z)
	var gap := dir.length()
	dir = dir.normalized() if gap > 0.1 else Vector3.FORWARD
	var pos := w - dir * back + dir.cross(Vector3.UP).normalized() * aside + Vector3.UP * rise
	pos.y = maxf(pos.y, float(height_at.call(pos.x, pos.z)) + 0.3)
	# On the Shrine's slope a crest can stand between the low camera and him: rise until the line
	# to his knees clears the land.
	var knees := w + Vector3.DOWN * 0.7
	if _sight.size() != SIGHT_SAMPLES:
		_sight.resize(SIGHT_SAMPLES)
	for k in _sight.size():
		var f := (k + 1.0) / (_sight.size() + 1.0)
		var p := pos.lerp(knees, f)
		_sight[k] = Vector2(f, float(height_at.call(p.x, p.z)))
	pos.y = clear_height(pos, knees, _sight, SIGHT_MARGIN)
	var feet := w.y - 1.2
	var lo := minf(elevation_deg(feet - pos.y, back), elevation_deg(c.y - pos.y, gap + back))
	var hi := maxf(
		elevation_deg(feet + 1.7 - pos.y, back), elevation_deg(c.y + h - pos.y, gap + back)
	)
	var lens := hero_lens(lo, hi, narrowest)
	var reach := gap + back
	_want_pos = pos
	_want_aim = pos + dir * reach + Vector3.UP * tan(deg_to_rad(lens.y)) * reach
	_want_fov = minf(_want_fov, lens.x)


## The lowest camera height from which the line to `target` passes `margin` m above the land:
## `ground` holds (share of the way from the camera, land height there) samples. Never below the
## camera's own height.
static func clear_height(
	cam: Vector3, target: Vector3, ground: PackedVector2Array, margin: float
) -> float:
	var y := cam.y
	for s in ground:
		if s.x < 1.0:
			y = maxf(y, (s.y + margin - target.y * s.x) / (1.0 - s.x))
	return y


## Angle (degrees) above the horizon of a point `rise` m up and `run` m away.
static func elevation_deg(rise: float, run: float) -> float:
	return rad_to_deg(atan2(rise, maxf(run, 1.0)))


## The lens that holds everything between `lo` and `hi` degrees of elevation: x is the vertical
## field of view, y the elevation to aim at. Never narrower than `narrowest`, never wider than 60.
static func hero_lens(lo: float, hi: float, narrowest: float) -> Vector2:
	return Vector2(clampf((hi - lo) * HERO_SPAN_MARGIN, narrowest, 60.0), (lo + hi) * 0.5)


## Vertical field of view that fits a figure `size` metres tall at `distance` into the frame.
static func fit_fov(size: float, distance: float, narrowest: float) -> float:
	return clampf(rad_to_deg(2.0 * atan(size * 0.75 / maxf(distance, 1.0))), narrowest, 60.0)
