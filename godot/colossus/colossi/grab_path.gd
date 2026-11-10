class_name GrabPath
## Grab Path maths. Pure: works on positions and link indices, never on nodes.

const MIN_ALIGNMENT := 0.3


## Index into `candidates` of the link whose direction, projected onto the surface
## at `from`, best matches `wish`. -1 when no link lies within the alignment cone.
static func choose_link(
	from: Vector3, normal: Vector3, candidates: Array[Vector3], wish: Vector3
) -> int:
	var n := normal.normalized()
	var w := wish - n * wish.dot(n)
	if w.length_squared() < 1e-6:
		return -1
	w = w.normalized()
	var best := -1
	var best_dot := MIN_ALIGNMENT
	for i in candidates.size():
		var d := candidates[i] - from
		d -= n * d.dot(n)
		if d.length_squared() < 1e-6:
			continue
		var dot := d.normalized().dot(w)
		if dot > best_dot:
			best_dot = dot
			best = i
	return best


## True when every point reaches `goal` by following links (links[i] lists where point i leads).
static func all_reach(goal: int, links: Array[PackedInt32Array]) -> bool:
	if goal < 0 or goal >= links.size():
		return false
	var seen := {goal: true}
	var queue: Array[int] = [goal]
	while not queue.is_empty():
		var at: int = queue.pop_front()
		for i in links.size():
			if not seen.has(i) and links[i].has(at):
				seen[i] = true
				queue.append(i)
	return seen.size() == links.size()


## Next pendulum state [angle, velocity] for a body hanging `length` metres below its grip.
static func swing(
	angle: float, velocity: float, length: float, delta: float, damping: float = 0.6
) -> Vector2:
	var accel := -9.81 / maxf(length, 0.1) * sin(angle) - damping * velocity
	var v := velocity + accel * delta
	return Vector2(angle + v * delta, v)
