class_name WandererClips
## The Wanderer's animation slots and where each one comes from. A Mixamo clip dropped into
## assets/mixamo/ under its slot's file name is picked up at the next start; a slot without its
## file plays its fallback slot (assets/MODELS.md lists the files). Mixamo bones are renamed to
## Godot's humanoid profile here, at runtime, so nothing of Mixamo is saved in the project.

const DIR := "res://assets/mixamo/"
## Slot, file, fallback slot, and whether the fallback holds its first frame (a still pose).
const SLOTS: Array[Dictionary] = [
	{"slot": "idle", "file": "idle.fbx", "fallback": "", "hold": false},
	{"slot": "walk", "file": "walk.fbx", "fallback": "idle", "hold": false},
	{"slot": "run", "file": "run.fbx", "fallback": "walk", "hold": false},
	{"slot": "hang_idle", "file": "hang_idle.fbx", "fallback": "shimmy_left", "hold": true},
	{"slot": "shimmy_left", "file": "shimmy_left.fbx", "fallback": "hang_idle", "hold": false},
	{"slot": "shimmy_right", "file": "shimmy_right.fbx", "fallback": "hang_idle", "hold": false},
	{"slot": "climb_up", "file": "climb_up.fbx", "fallback": "hang_idle", "hold": false},
	{"slot": "climb_down", "file": "climb_down.fbx", "fallback": "hang_idle", "hold": false},
	{"slot": "hang_swing", "file": "hang_swing.fbx", "fallback": "hang_idle", "hold": false},
	{"slot": "fall_idle", "file": "fall_idle.fbx", "fallback": "idle", "hold": false},
	{"slot": "stand_up", "file": "stand_up.fbx", "fallback": "idle", "hold": false},
]
## Slots that loop; the others play once (stand_up) or loop as the state holds.
const ONE_SHOT := ["stand_up"]
## Mixamo bone (after Godot's FBX import turns ':' into '_') to the humanoid profile name.
## Spine1 has no place on the Nomad (Hips, Spine, Chest): Chest takes Spine2, so the shoulders sit
## where Mixamo's do.
const BONES := {
	"Hips": "Hips",
	"Spine": "Spine",
	"Spine2": "Chest",
	"Neck": "Neck",
	"Head": "Head",
	"Shoulder": "Shoulder",
	"Arm": "UpperArm",
	"ForeArm": "LowerArm",
	"Hand": "Hand",
	"HandThumb1": "ThumbMetacarpal",
	"HandThumb2": "ThumbProximal",
	"HandThumb3": "ThumbDistal",
	"HandIndex1": "IndexProximal",
	"HandIndex2": "IndexIntermediate",
	"HandIndex3": "IndexDistal",
	"HandMiddle1": "MiddleProximal",
	"HandMiddle2": "MiddleIntermediate",
	"HandMiddle3": "MiddleDistal",
	"HandRing1": "RingProximal",
	"HandRing2": "RingIntermediate",
	"HandRing3": "RingDistal",
	"HandPinky1": "LittleProximal",
	"HandPinky2": "LittleIntermediate",
	"HandPinky3": "LittleDistal",
	"UpLeg": "UpperLeg",
	"Leg": "LowerLeg",
	"Foot": "Foot",
	"ToeBase": "Toes",
}


## Which clip each slot plays, given the slots whose file is present: slot -> [source slot, hold].
## A slot whose fallback chain reaches no present file maps to ["", false] (procedural pose).
static func resolve(present: PackedStringArray) -> Dictionary:
	var by_slot := {}
	for s in SLOTS:
		by_slot[s["slot"]] = s
	var out := {}
	for s in SLOTS:
		var slot: String = s["slot"]
		var hold := false
		var seen := PackedStringArray()
		while slot != "" and not present.has(slot) and not seen.has(slot):
			seen.append(slot)
			hold = hold or bool(by_slot[slot]["hold"])
			slot = by_slot[slot]["fallback"]
		out[s["slot"]] = [slot if present.has(slot) else "", hold and present.has(slot)]
	return out


## Humanoid profile name of a Mixamo bone ("mixamorig_LeftArm" -> "LeftUpperArm"); bones without
## a place keep their own name with the prefix cut ("Spine1").
static func bone_name(mixamo: String) -> String:
	var n := mixamo.trim_prefix("mixamorig_").trim_prefix("mixamorig:")
	var side := ""
	if n.begins_with("Left"):
		side = "Left"
	elif n.begins_with("Right"):
		side = "Right"
	var rest := n.substr(side.length())
	if BONES.has(rest) and (side != "" or rest in ["Hips", "Spine", "Spine2", "Neck", "Head"]):
		return side + BONES[rest]
	return n


## Removes the clip's net travel: the Hips position track drifts linearly from its first key to
## its last over the clip, and that drift is taken out, so walking, shimmying and hopping clips
## play in place and the scene moves the body. Bumps inside the cycle stay.
static func in_place(anim: Animation, hips_track: int) -> void:
	var n := anim.track_get_key_count(hips_track)
	if n < 2:
		return
	var first: Vector3 = anim.track_get_key_value(hips_track, 0)
	var drift: Vector3 = anim.track_get_key_value(hips_track, n - 1) - first
	var length := maxf(anim.track_get_key_time(hips_track, n - 1), 0.001)
	for k in n:
		var t := anim.track_get_key_time(hips_track, k)
		var v: Vector3 = anim.track_get_key_value(hips_track, k)
		anim.track_set_key_value(hips_track, k, v - drift * (t / length))


## A clip that holds the first frame of `anim` (a still pose, for a slot whose clip is missing).
static func first_frame(anim: Animation) -> Animation:
	var still := Animation.new()
	still.length = 1.0
	still.loop_mode = Animation.LOOP_LINEAR
	for t in anim.get_track_count():
		if anim.track_get_key_count(t) == 0:
			continue
		var i := still.add_track(anim.track_get_type(t))
		still.track_set_path(i, anim.track_get_path(t))
		still.track_insert_key(i, 0.0, anim.track_get_key_value(t, 0))
	return still


## Ground speed (m/s) at which a walk or run clip's planted foot does not slide: how fast the
## lower foot moves backwards relative to the hips, averaged over the frames it is planted.
## `foot_z` and `foot_y` are the foot's forward and up position relative to the hips, sampled
## every `dt` seconds over one cycle.
static func stride_speed(
	foot_z: PackedFloat32Array, foot_y: PackedFloat32Array, dt: float
) -> float:
	if foot_z.size() < 3:
		return 0.0
	var low := INF
	for y in foot_y:
		low = minf(low, y)
	var sum := 0.0
	var n := 0
	for i in range(1, foot_z.size()):
		if foot_y[i] < low + 0.02 and foot_y[i - 1] < low + 0.02:
			sum += (foot_z[i - 1] - foot_z[i]) / dt
			n += 1
	return absf(sum / n) if n > 0 else 0.0
