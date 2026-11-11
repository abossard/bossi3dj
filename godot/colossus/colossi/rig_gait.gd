class_name RigGait
extends SkeletonModifier3D
## The Colossus's own motion on an imported rig, after its idle clip: legs swing with the stride
## (the clip keeps the upper body), the hips bob, the spine rolls in a Shake, the head turns
## toward the Wanderer, and the foot IK targets are where the posed feet are, never below the land.
## Rotations are in the skeleton's space, about each bone's head, on top of the parent's pose;
## the rig faces +Z in its own space.

## Thigh, shin and upper arm angles per side (left first), set by the Colossus each tick.
var legs := PackedFloat32Array([0.0, 0.0, 0.0, 0.0])
var roll := 0.0
var yaw := 0.0
var bob := 0.0
var height_at: Callable = func(_x: float, _z: float) -> float: return 0.0
## Bone names: [thigh_l, shin_l, foot_l, thigh_r, shin_r, foot_r, upper_arm_l, upper_arm_r,
## spine, head, hips].
var bone_names := PackedStringArray()
## The ankle's height above the land at rest (m).
var ankle := 0.5
var foot_targets: Array[Marker3D] = []
var knee_poles: Array[Marker3D] = []
var _b := PackedInt32Array()


func _process_modification() -> void:
	var skel := get_skeleton()
	if _b.is_empty():
		for n in bone_names:
			_b.append(skel.find_bone(n))
	var rot := Quaternion(Vector3.UP, yaw)
	for side in 2:
		var o := side * 3
		# The rig faces +Z: a forward swing turns the leg about -X.
		_turn(skel, _b[o], Basis(Vector3.LEFT, legs[side * 2]))
		_turn(skel, _b[o + 1], Basis(Vector3.LEFT, legs[side * 2 + 1]))
		_turn(skel, _b[6 + side], Basis(Vector3.LEFT, -legs[side * 2] * 0.6), false)
	var spine := skel.get_bone_global_pose(_b[8])
	skel.set_bone_global_pose(
		_b[8], Transform3D(Basis(Vector3.FORWARD, roll) * spine.basis, spine.origin)
	)
	var head := skel.get_bone_global_pose(_b[9])
	skel.set_bone_global_pose(_b[9], Transform3D(Basis(rot) * head.basis, head.origin))
	var hips := skel.get_bone_pose_position(_b[10])
	skel.set_bone_pose_position(_b[10], hips + Vector3.UP * bob)
	var xf := skel.global_transform
	for side in 2:
		var o := side * 3
		var foot := xf * skel.get_bone_global_pose(_b[o + 2]).origin
		var land: float = height_at.call(foot.x, foot.z)
		foot.y = maxf(foot.y, land + ankle)
		foot_targets[side].global_position = foot
		var knee := xf * skel.get_bone_global_pose(_b[o + 1]).origin
		knee_poles[side].global_position = knee + xf.basis.z.normalized() * ankle * 4.0


## Turns a bone from its rest (legs: the clip's legs are replaced) or from its clip pose (arms),
## by `turn` in the skeleton's space about its head.
func _turn(skel: Skeleton3D, bone: int, turn: Basis, from_rest := true) -> void:
	var parent := skel.get_bone_parent(bone)
	var parent_global := skel.get_bone_global_pose(parent) if parent >= 0 else Transform3D()
	var base := (
		parent_global * skel.get_bone_rest(bone) if from_rest else skel.get_bone_global_pose(bone)
	)
	skel.set_bone_global_pose(bone, Transform3D(turn * base.basis, base.origin))
