class_name WandererPose
extends SkeletonModifier3D
## The Wanderer's pose when no clip is present (assets/MODELS.md): arms down from the rest T-pose,
## legs and arms swinging with the stride while he moves. Active only without clips.

const ARMS_DOWN := deg_to_rad(72.0)
const SWING := deg_to_rad(28.0)

## Smoothed ground speed (m/s) and stride phase (0..1), set by the body.
var speed := 0.0
var stride_phase := 0.0
var _bones := {}


func _process_modification() -> void:
	var skel := get_skeleton()
	if _bones.is_empty():
		for n in [
			"LeftUpperArm",
			"RightUpperArm",
			"LeftUpperLeg",
			"RightUpperLeg",
			"LeftLowerLeg",
			"RightLowerLeg"
		]:
			_bones[n] = skel.find_bone(n)
	var amount := clampf(speed / 1.6, 0.0, 1.0)
	var s := sin(stride_phase * TAU) * SWING * amount
	_turn(skel, "LeftUpperArm", Basis(Vector3.BACK, -ARMS_DOWN) * Basis(Vector3.RIGHT, -s * 0.6))
	_turn(skel, "RightUpperArm", Basis(Vector3.BACK, ARMS_DOWN) * Basis(Vector3.RIGHT, s * 0.6))
	_turn(skel, "LeftUpperLeg", Basis(Vector3.RIGHT, -s))
	_turn(skel, "RightUpperLeg", Basis(Vector3.RIGHT, s))
	_turn(skel, "LeftLowerLeg", Basis(Vector3.RIGHT, maxf(s, 0.0) * 1.2))
	_turn(skel, "RightLowerLeg", Basis(Vector3.RIGHT, maxf(-s, 0.0) * 1.2))


## Turns a bone by `turn` in the skeleton's space, about its own head, on top of its parent's pose.
func _turn(skel: Skeleton3D, bone: String, turn: Basis) -> void:
	var i: int = _bones[bone]
	var parent := skel.get_bone_parent(i)
	var parent_global := skel.get_bone_global_pose(parent) if parent >= 0 else Transform3D()
	var rest_global := parent_global * skel.get_bone_rest(i)
	var want := Transform3D(turn * rest_global.basis, rest_global.origin)
	skel.set_bone_global_pose(i, want)
