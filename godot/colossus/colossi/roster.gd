class_name Roster
## The Colossi in show order; each Reset brings the next. Placeholders until the rigged models
## are imported. The only place that names a Colossus.

## `model` is the prepared model (not in git, see assets/MODELS.md); "" while there is none.
const ENTRIES: Array[Dictionary] = [
	{"name": "Grock", "height_m": 28.0, "seed": 1, "model": "res://assets/models/grock/grock.gltf"},
	{"name": "Titan", "height_m": 34.0, "seed": 2, "model": ""},
	{"name": "Golem", "height_m": 22.0, "seed": 3, "model": ""},
]


## Names of the Colossi whose model file is missing: their stand-in takes their place.
static func missing_models() -> PackedStringArray:
	var out := PackedStringArray()
	for entry in ENTRIES:
		var path: String = entry["model"]
		if path != "" and not ResourceLoader.exists(path):
			out.append("%s (Colossus)" % entry["name"])
	return out


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
