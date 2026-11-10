class_name VjMap
## The one table from a `/vj/*` wire value to a scene value. Pure: data and arithmetic.
##
## Contract (user decision 2026-11-10): every continuous control is 0..1 on the wire, each scene
## scales it to its own range, and the wire default gives the scene its tuned rest look.
## Per address: `lo`..`hi` is the wire range (anything else is clamped), `rest` the wire default
## (the value before any packet and after "defaults"). The scene value runs in two straight
## segments through `out_lo` at `lo`, `out_rest` at `rest` and `out_hi` at `hi`, so the default
## lands exactly on the tuned look and both ends keep their reach.
## `kind` is how the page draws the address and the check drives it.
## A new unit or meaning is a change of this data, not of code.
##
## - /vj/cam N picks the Nth director shot, 0-based, clamped to the last (0..4 give shots 1..5).
## - /vj/cam_auto 1 hands the cuts to the director, 0 pins the shot /vj/cam names.
## - /vj/shock keeps its strength: a trigger edge above 0.5, 1.4 and above marks a drop.
## - /vj/haze: the wire default 1 is the tuned look, so the scene's haze can only be lowered.

## How an address is drawn on the page and driven by the check.
enum Kind { LEVEL, TRIGGER, SHOT, TOGGLE }

const ROWS := {
	"/vj/level":
	{
		"drives": "sun glow through the cloud gap",
		"kind": Kind.LEVEL,
		"lo": 0.0,
		"hi": 1.0,
		"rest": 0.5,
		"out_lo": 1.4,
		"out_rest": 1.8,
		"out_hi": 2.6
	},
	"/vj/bass":
	{
		"drives": "footfall weight: camera thump, dust size",
		"kind": Kind.LEVEL,
		"lo": 0.0,
		"hi": 1.0,
		"rest": 0.0,
		"out_lo": 0.5,
		"out_rest": 0.5,
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
		"out_rest": 0.0,
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
		"out_rest": 0.0,
		"out_hi": 1.5
	},
	"/vj/fog":
	{
		"drives": "volumetric fog density",
		"kind": Kind.LEVEL,
		"lo": 0.0,
		"hi": 1.0,
		"rest": 0.35,
		"out_lo": 0.002,
		"out_rest": 0.003,
		"out_hi": 0.012
	},
	"/vj/fog_height":
	{
		"drives": "fog height, 10 to 90 m",
		"kind": Kind.LEVEL,
		"lo": 0.0,
		"hi": 1.0,
		"rest": 0.42,
		"out_lo": 10.0,
		"out_rest": 40.0,
		"out_hi": 90.0
	},
	"/vj/haze":
	{
		"drives": "distance haze, none to the tuned look",
		"kind": Kind.LEVEL,
		"lo": 0.0,
		"hi": 1.0,
		"rest": 1.0,
		"out_lo": 0.0,
		"out_rest": 0.00025,
		"out_hi": 0.00025
	},
	"/vj/intensity":
	{
		"drives": "overall exposure, 0.2 to 2",
		"kind": Kind.LEVEL,
		"lo": 0.0,
		"hi": 1.0,
		"rest": 0.5,
		"out_lo": 0.2,
		"out_rest": 1.0,
		"out_hi": 2.0
	},
	"/vj/cam":
	{
		"drives": "the Nth director shot, 0-based (0 to 4), used while cam_auto is 0",
		"kind": Kind.SHOT,
		"lo": 0.0,
		"hi": 4.0,
		"rest": 0.0,
		"out_lo": 1.0,
		"out_rest": 1.0,
		"out_hi": 5.0
	},
	"/vj/cam_auto":
	{
		"drives": "1 the director cuts, 0 the shot /vj/cam names is held",
		"kind": Kind.TOGGLE,
		"lo": 0.0,
		"hi": 1.0,
		"rest": 1.0,
		"out_lo": 0.0,
		"out_rest": 1.0,
		"out_hi": 1.0
	},
}


static func addresses() -> Array:
	return ROWS.keys()


static func known(address: String) -> bool:
	return ROWS.has(address)


static func rest(address: String) -> float:
	return float(ROWS[address]["rest"])


## The wire value as the scene stores it: clamped to the wire range, shots and toggles whole.
static func clamp_value(address: String, v: float) -> float:
	var row: Dictionary = ROWS[address]
	var c := clampf(v, float(row["lo"]), float(row["hi"]))
	var whole: bool = row["kind"] == Kind.SHOT or row["kind"] == Kind.TOGGLE
	return roundf(c) if whole else c


## The value the scene applies for a wire value `v`.
static func scene_value(address: String, v: float) -> float:
	var row: Dictionary = ROWS[address]
	var lo := float(row["lo"])
	var mid := float(row["rest"])
	var hi := float(row["hi"])
	var c := clamp_value(address, v)
	if c <= mid:
		var below := 1.0 if mid <= lo else (c - lo) / (mid - lo)
		return lerpf(float(row["out_lo"]), float(row["out_rest"]), below)
	return lerpf(float(row["out_rest"]), float(row["out_hi"]), (c - mid) / (hi - mid))
