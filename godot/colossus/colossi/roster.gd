class_name Roster
## The Colossi in show order; each Reset brings the next. A Colossus with a prepared model is built
## on its rig (`rig`); without the model (not in git, see assets/MODELS.md), or without a rig yet,
## the rigged stand-in takes its place. The only place that names a Colossus.

const ENTRIES: Array[Dictionary] = [
	{"name": "Grock", "height_m": 28.0, "seed": 1, "model": GrockColossus.MODEL, "rig": "grock"},
	{"name": "Titan", "height_m": 34.0, "seed": 2, "model": "", "rig": ""},
	{"name": "Golem", "height_m": 22.0, "seed": 3, "model": "", "rig": ""},
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
	GrockColossus.warm()


static func make(index: int) -> Colossus:
	var entry: Dictionary = ENTRIES[index % ENTRIES.size()]
	var c: Colossus = PlaceholderColossus.new()
	if entry["rig"] == "grock" and GrockColossus.model_present():
		c = GrockColossus.new()
	c.name = entry["name"]
	c.height_m = entry["height_m"]
	c.seed_value = entry["seed"]
	return c
