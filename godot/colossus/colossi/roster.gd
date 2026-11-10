class_name Roster
## The Colossi in show order; each Reset brings the next. Placeholders until the rigged models
## are imported. The only place that names a Colossus.

const ENTRIES: Array[Dictionary] = [
	{"name": "Grock", "height_m": 28.0, "seed": 1},
	{"name": "Titan", "height_m": 34.0, "seed": 2},
	{"name": "Golem", "height_m": 22.0, "seed": 3},
]


static func size() -> int:
	return ENTRIES.size()


static func make(index: int) -> Colossus:
	var entry: Dictionary = ENTRIES[index % ENTRIES.size()]
	var c := PlaceholderColossus.new()
	c.name = entry["name"]
	c.height_m = entry["height_m"]
	c.seed_value = entry["seed"]
	return c
