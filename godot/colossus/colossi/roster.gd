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


## Makes what the Colossi share and take long to make, so a Reset builds the next one in a frame.
static func warm() -> void:
	for entry in ENTRIES:
		PlaceholderColossus.stone_bumps(entry["seed"])


static func make(index: int) -> Colossus:
	var entry: Dictionary = ENTRIES[index % ENTRIES.size()]
	var c := PlaceholderColossus.new()
	c.name = entry["name"]
	c.height_m = entry["height_m"]
	c.seed_value = entry["seed"]
	return c
