class_name WandererFeet
extends SkeletonModifier3D
## Feet on the land, and where the body has to hang. After the clip's pose, each foot's IK target
## is where the clip put it, raised or lowered by how far the land under it differs from the land
## under the body; the hips drop to let the lower foot reach. The leg IK after this modifier
## follows the targets; on flat ground it is off, so the clip's legs stay untouched.

## The land may lift or drop a foot this far (m).
const MAX_OFFSET := 0.4
## Below this difference the legs keep the clip's pose (m).
const FLAT := 0.01
const ARM_SHARE := 0.92
## Ankle to toe tip, and the hand targets' distance off the surface (m).
const TOES := 0.12
const GRIP_OFF := 0.05

var body: WandererBody
## Set by the body: true while the Wanderer stands or walks on the land.
var grounded := true
var legs: TwoBoneIK3D
## Where the clip's pose wants the body to hang from a grip, read before the hand IK: the origin
## this far below the hand targets (m) and this far off the surface (m). The toes touch the surface
## and the shoulders sit ARM_SHARE of an arm's length from the grip, so the IK bends the elbows
## a little and never pulls a straight arm.
var hang_reach := 2.0
var hang_out := 0.3
var foot_l := Marker3D.new()
var foot_r := Marker3D.new()
var knee_l := Marker3D.new()
var knee_r := Marker3D.new()
var _drop := 0.0
var _weight := 0.0
var _hips := -1
var _feet := PackedInt32Array()
var _knees := PackedInt32Array()
var _shoulders := PackedInt32Array()
var _arm := 0.6


func _ready() -> void:
	for m in [foot_l, foot_r, knee_l, knee_r]:
		m.top_level = true
		add_child(m)


func _process_modification_with_delta(delta: float) -> void:
	var skel := get_skeleton()
	if _hips < 0:
		_hips = skel.find_bone("Hips")
		_feet = PackedInt32Array([skel.find_bone("LeftFoot"), skel.find_bone("RightFoot")])
		_knees = PackedInt32Array([skel.find_bone("LeftLowerLeg"), skel.find_bone("RightLowerLeg")])
		_shoulders = PackedInt32Array(
			[skel.find_bone("LeftUpperArm"), skel.find_bone("RightUpperArm")]
		)
		var lower := skel.find_bone("LeftLowerArm")
		var hand := skel.find_bone("LeftHand")
		_arm = (
			skel.get_bone_global_rest(_shoulders[0]).origin.distance_to(
				skel.get_bone_global_rest(lower).origin
			)
			+ skel.get_bone_global_rest(lower).origin.distance_to(
				skel.get_bone_global_rest(hand).origin
			)
		)
	_fit_hang(skel)
	var xf := skel.global_transform
	var origin := body.global_position
	var g0: float = body.height_at.call(origin.x, origin.z)
	var lowest := 0.0
	var steepest := 0.0
	for i in 2:
		var at := xf * skel.get_bone_global_pose(_feet[i]).origin
		var knee := xf * skel.get_bone_global_pose(_knees[i]).origin
		var off := clampf(float(body.height_at.call(at.x, at.z)) - g0, -MAX_OFFSET, MAX_OFFSET)
		lowest = minf(lowest, off)
		steepest = maxf(steepest, absf(off))
		var target := foot_l if i == 0 else foot_r
		target.global_position = at + Vector3.UP * off
		var forward := -body.global_transform.basis.z
		(knee_l if i == 0 else knee_r).global_position = knee + forward * 0.5
	var want := 1.0 if grounded and steepest > FLAT else 0.0
	_weight = move_toward(_weight, want, delta / 0.2)
	_drop = lerpf(_drop, lowest if grounded else 0.0, 1.0 - exp(-delta / 0.15))
	if legs:
		legs.influence = _weight
	var p := skel.get_bone_pose_position(_hips)
	skel.set_bone_pose_position(_hips, p + Vector3.UP * _drop)


## The hang that fits this frame's clip pose (skeleton space: +Z is forward, toward the surface).
func _fit_hang(skel: Skeleton3D) -> void:
	var toe := maxf(
		skel.get_bone_global_pose(_feet[0]).origin.z, skel.get_bone_global_pose(_feet[1]).origin.z
	)
	var sh := (
		(
			skel.get_bone_global_pose(_shoulders[0]).origin
			+ skel.get_bone_global_pose(_shoulders[1]).origin
		)
		* 0.5
	)
	hang_out = maxf(toe + TOES, 0.1)
	var ahead := hang_out - GRIP_OFF - sh.z
	var reach := _arm * ARM_SHARE
	hang_reach = sh.y + sqrt(maxf(reach * reach - ahead * ahead, 0.01))
