class_name WandererBrain
## Where the autonomous Wanderer wants to go. Pure: positions in, world-space wish out.

const WAIT_DISTANCE := 70.0


static func wish(
	phase: Arc.Phase,
	on_colossus: bool,
	me: Vector3,
	colossus: Vector3,
	entry: Vector3,
	grip: Vector3,
	head: Vector3
) -> Vector3:
	match phase:
		Arc.Phase.APPROACH:
			var to := Vector3(colossus.x - me.x, 0.0, colossus.z - me.z)
			return Vector3.ZERO if to.length() < WAIT_DISTANCE else to.normalized()
		Arc.Phase.CLIMB:
			if on_colossus:
				var up := head - grip
				return Vector3.ZERO if up.length() < 0.5 else up.normalized()
			var to_entry := Vector3(entry.x - me.x, 0.0, entry.z - me.z)
			return Vector3.ZERO if to_entry.length() < 0.5 else to_entry.normalized()
	return Vector3.ZERO
