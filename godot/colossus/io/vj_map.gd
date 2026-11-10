class_name VjMap
## The one table from a `/vj/*` contract value to a scene value. Pure: data and arithmetic.
##
## Per address: `lo`..`hi` is the range the scene accepts (anything else is clamped), `rest` the
## value before any packet and after "defaults" (the tuned overcast dusk look), `out_lo`..`out_hi`
## the scene value at `lo` and `hi`, `kind` how the page draws and the check drives it.
## Changing a unit or a meaning (/vj/fog_height, /vj/cam) is a change of this data, not of code.
##
## Assumptions until the contract decision (osc/CONTROLS.md, "Open mismatches"):
## - /vj/fog_height arrives in metres, as Magic sends it (0..60). It is the height of the fog in
##   metres, so 25 gives 25 m and never kilometres. Rest 40 m is the old rest of 0.375 (10..90 m).
## - /vj/cam is a director shot 1..5, 0 hands the cut back to the director. Above 5 clamps to 5.
## - /vj/intensity 0..2 reaches the scene as exposure 0.2..2, so 0 clamps to 0.2.

## How an address is drawn on the page and driven by the check.
enum Kind { LEVEL, TRIGGER, SHOT }

const ROWS := {
	"/vj/level":
	{
		"drives": "sun glow through the cloud gap",
		"kind": Kind.LEVEL,
		"lo": 0.0,
		"hi": 1.0,
		"rest": 1.0 / 3.0,
		"out_lo": 1.4,
		"out_hi": 2.6
	},
	"/vj/bass":
	{
		"drives": "footfall weight: camera thump, dust size",
		"kind": Kind.LEVEL,
		"lo": 0.0,
		"hi": 1.0,
		"rest": 0.5,
		"out_lo": 0.0,
		"out_hi": 1.0
	},
	"/vj/beat":
	{
		"drives": "footfall timing, cut points, dust (internal 90 BPM while quiet)",
		"kind": Kind.TRIGGER,
		"lo": 0.0,
		"hi": 1.0,
		"rest": 0.0,
		"out_lo": 0.0,
		"out_hi": 1.0
	},
	"/vj/shock":
	{
		"drives": "Shake while the Wanderer hangs on the Colossus; 1.4+ marks a drop",
		"kind": Kind.TRIGGER,
		"lo": 0.0,
		"hi": 1.5,
		"rest": 0.0,
		"out_lo": 0.0,
		"out_hi": 1.5
	},
	"/vj/fog":
	{
		"drives": "volumetric fog density",
		"kind": Kind.LEVEL,
		"lo": 0.0,
		"hi": 1.0,
		"rest": 0.1,
		"out_lo": 0.002,
		"out_hi": 0.012
	},
	"/vj/fog_height":
	{
		"drives": "fog height in metres",
		"kind": Kind.LEVEL,
		"lo": 0.0,
		"hi": 60.0,
		"rest": 40.0,
		"out_lo": 0.0,
		"out_hi": 60.0
	},
	"/vj/haze":
	{
		"drives": "distance haze",
		"kind": Kind.LEVEL,
		"lo": 0.0,
		"hi": 1.0,
		"rest": 0.05,
		"out_lo": 0.0002,
		"out_hi": 0.0012
	},
	"/vj/intensity":
	{
		"drives": "overall exposure",
		"kind": Kind.LEVEL,
		"lo": 0.2,
		"hi": 2.0,
		"rest": 1.0,
		"out_lo": 0.2,
		"out_hi": 2.0
	},
	"/vj/cam":
	{
		"drives": "director shot 1 to 5 pinned, 0 hands the cut back",
		"kind": Kind.SHOT,
		"lo": 0.0,
		"hi": 5.0,
		"rest": 0.0,
		"out_lo": 0.0,
		"out_hi": 5.0
	},
}


static func addresses() -> Array:
	return ROWS.keys()


static func known(address: String) -> bool:
	return ROWS.has(address)


static func rest(address: String) -> float:
	return float(ROWS[address]["rest"])


## The contract value as the scene stores it: clamped to the accepted range, shots whole.
static func clamp_value(address: String, v: float) -> float:
	var row: Dictionary = ROWS[address]
	var c := clampf(v, float(row["lo"]), float(row["hi"]))
	return roundf(c) if row["kind"] == Kind.SHOT else c


## The value the scene applies for a contract value `v`.
static func scene_value(address: String, v: float) -> float:
	var row: Dictionary = ROWS[address]
	var lo := float(row["lo"])
	var hi := float(row["hi"])
	var t := (clamp_value(address, v) - lo) / (hi - lo)
	return lerpf(float(row["out_lo"]), float(row["out_hi"]), t)
