"""Retarget a Mixamo capture onto the Android's rig as one baked Action per Mocap Clip (`mocap.<name>`), for the
build (#31). Timing, travel, plants and the end blends are `mocap.py`'s; this file is the Blender side.

Every body bone follows its capture bone (MAP): each bone takes the capture bone's world rotation, corrected by the
rest-pose difference (Mixamo rests in a T-pose, the Android with arms down), and forward kinematics on the Android's
own bone lengths gives the joints. The torso bones (hips, spine, chest, neck, head) are keyed directly; arms and
legs keep their IK, driven by the wrist and ankle and by a pole set beside the captured elbow and knee each frame, so
the IK solves the captured limb; the hands then take the captured hand rotation relative to the solved forearm and
the feet the captured foot rotation (flat on the floor while planted). Hips travel scales with the leg length.
weight.py's hit-stop comes through mocap.warp; its fist recoil moves the wrist targets, its stomp dip the hips.
"""
import os

import bpy
from mathutils import Matrix, Quaternion, Vector

import mocap
import moves
import weight

PACKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "mixamo", "packs")
SIDES = ((".L", "Left"), (".R", "Right"))
TORSO = {"hips": "Hips", "spine": "Spine", "chest": "Spine2", "neck": "Neck", "head": "Head"}
LIMBS = {"upperarm": "Arm", "forearm": "ForeArm", "hand": "Hand", "thigh": "UpLeg", "shin": "Leg", "foot": "Foot"}
MAP = {b: "mixamorig:" + m for b, m in TORSO.items()}
MAP.update({b + s: "mixamorig:" + side + m for b, m in LIMBS.items() for s, side in SIDES})
FK_ORDER = ["hips", "spine", "chest", "neck", "head"] + [b + s for s, _ in SIDES for b in ("upperarm", "forearm",
                                                                                           "hand", "thigh", "shin")]
POLE_M = 0.5
# bones a Mocap Clip keys beyond moves.py's channels; the key-table Actions key them at rest, so switching Actions
# never leaves one posed
EXTRA_BONES = ("neck", "hand.L", "hand.R", "elbow_pole.L", "elbow_pole.R", "knee_pole.L", "knee_pole.R")


def _rot(m):
    return m.to_3x3().normalized().to_quaternion()


class Source:
    """An imported Mixamo armature: rest data and world pose per (fractional) frame."""

    def __init__(self, path):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=path)
        self.objects = [o for o in bpy.data.objects if o not in before]
        self.rig = next(o for o in self.objects if o.type == "ARMATURE")
        self.action = self.rig.animation_data.action
        self.cache = {}
        mw = self.rig.matrix_world
        self.rest_rot = {b: _rot(mw @ self.rig.data.bones[s].matrix_local) for b, s in MAP.items()}
        self.rest_dir = {b: (mw @ self.rig.data.bones[s].tail_local - mw @ self.rig.data.bones[s].head_local)
                         .normalized() for b, s in MAP.items()}
        self.rest_head = {b: mw @ self.rig.data.bones[s].head_local for b, s in MAP.items()}

    def _whole(self, frame):
        if frame not in self.cache:
            bpy.context.scene.frame_set(frame)
            mw = self.rig.matrix_world
            self.cache[frame] = {b: ((mw @ self.rig.pose.bones[s].matrix).translation.copy(),
                                     _rot(mw @ self.rig.pose.bones[s].matrix)) for b, s in MAP.items()}
        return self.cache[frame]

    def pose(self, frame):
        """{our bone: (world head, world rotation)} at a fractional source frame: whole frames as captured, in
        between slerped (the capture's Euler curves would spin through a wrap at a subframe)."""
        a, b = self._whole(int(frame)), self._whole(int(frame) + 1)
        t = frame - int(frame)
        return {k: (a[k][0].lerp(b[k][0], t), a[k][1].slerp(b[k][1], t)) for k in a}

    def remove(self):
        arm_data = self.rig.data
        for o in self.objects:
            bpy.data.objects.remove(o)
        bpy.data.armatures.remove(arm_data)
        if self.action:
            bpy.data.actions.remove(self.action)


class Retarget:
    """The Android's rest data and the rotation offsets from a Source's rest pose to it."""

    def __init__(self, arm, src):
        self.arm = arm
        bones = arm.data.bones
        self.A = {b.name: b.matrix_local.copy() for b in bones}
        self.parent = {b.name: b.parent.name if b.parent else None for b in bones}
        self.length = {b.name: b.length for b in bones}
        self.offset = {}
        for b in MAP:
            tgt_dir = (bones[b].tail_local - bones[b].head_local).normalized()
            c = src.rest_dir[b].rotation_difference(tgt_dir)
            self.offset[b] = src.rest_rot[b].inverted() @ c.inverted() @ _rot(self.A[b])
        hip = bones["thigh.L"].head_local
        ankle = bones["shin.L"].tail_local
        src_leg = (src.rest_head["thigh.L"] - src.rest_head["foot.L"]).length
        self.scale = (hip - ankle).length / src_leg
        self.lift = bones["hips"].head_local.z - self.scale * src.rest_head["hips"].z
        self.sole = {s: _sole(arm, "foot" + s, self.A["foot" + s]) for s, _ in SIDES}

    def fk(self, pose):
        """World matrices of the FK bones and the foot rotations for one source pose."""
        P = {"root": self.A["root"]}
        for b in FK_ORDER:
            rot = (pose[b][1] @ self.offset[b]).to_matrix().to_4x4()
            if b == "hips":
                h = pose[b][0] * self.scale
                head = Vector((h.x, h.y, h.z + self.lift))
            else:
                p = self.parent[b]
                head = (P[p] @ self.A[p].inverted() @ self.A[b]).translation
            P[b] = Matrix.Translation(head) @ rot
        feet = {s: pose["foot" + s][1] @ self.offset["foot" + s] for s, _ in SIDES}
        return P, feet

    def tail(self, P, b):
        return P[b] @ Vector((0.0, self.length[b], 0.0))

    def local(self, P, b):
        p = self.parent[b]
        return (P[p] @ self.A[p].inverted() @ self.A[b]).inverted() @ P[b]

    def at(self, b, world):
        """Location of a root-parented control bone that puts its head at `world`."""
        return self.A[b].to_3x3().inverted() @ (world - self.A[b].translation)


def _sole(arm, bone, rest):
    """The foot parts' lowest vertices at rest, in the foot bone's rest frame: a foot whose sole points stay at or
    above the floor does not sink."""
    arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    verts = [o.matrix_world @ v.co for o in bpy.data.objects if o.get("robot_part") == bone for v in o.data.vertices]
    arm.data.pose_position = "POSE"
    bpy.context.view_layer.update()
    low = min(v.z for v in verts)
    return [rest.inverted() @ v for v in verts if v.z <= low + 0.02]


def _pole(root, mid, tip, prev, default):
    line = (tip - root).normalized()
    off = (mid - root) - line * (mid - root).dot(line)
    n = off.normalized() if off.length > 0.01 else (prev or default)
    return mid + n * POLE_M, n


def _flat(q, rest):
    """The foot rotation with tilt removed: its turn about Z from the rest pose only."""
    yaw = (q @ rest.inverted()).to_euler("XYZ").z
    return Quaternion((0.0, 0.0, 1.0), yaw) @ rest


def _impacts(rt, frames, travel, locked, stops):
    """weight.py's fist recoil and stomp dip as world offsets {frame: {"hips" | "hand.L" | "hand.R": Vector}}, faded out
    at the Clip's end."""
    seq = [{"hips": tuple(P["hips"].translation + t), "hand_l": tuple(rt.tail(P, "forearm.L") + t),
            "hand_r": tuple(rt.tail(P, "forearm.R") + t), "foot_l": locked[".L"][0][f], "foot_r": locked[".R"][0][f]}
           for f, ((P, _), t) in enumerate(zip(frames, travel))]
    at = lambda f: seq[int(f)]  # noqa: E731
    out = {}
    hand_recoil = [o for o in weight.recoil(seq, at, stops) if o[1] != "hips"]   # the capture's body reacts itself
    for f, ch, d in hand_recoil + weight.dip(seq, at, stops, landings=False):
        bone = {"hips": "hips", "hand_l": "hand.L", "hand_r": "hand.R"}[ch]
        o = out.setdefault(f, {})
        o[bone] = o.get(bone, Vector()) + Vector(d) * weight._end_weight(f, len(seq))
    return out


def _controls(rt, frames, stops=()):
    """Per frame {bone: (location, rotation)} for the control bones, plus the world hand rotations."""
    hips_xy = [(P["hips"].translation.x, P["hips"].translation.y) for P, _ in frames]
    travel = [Vector((x, y, 0.0)) for x, y in mocap.travel_offsets(hips_xy)]
    ankles = {s: [rt.tail(P, "shin" + s) + t for (P, _), t in zip(frames, travel)] for s, _ in SIDES}
    locked = {s: mocap.lock_feet([tuple(a) for a in ankles[s]]) for s, _ in SIDES}
    impacts = _impacts(rt, frames, travel, locked, stops)
    out, hands, prev = [], [], {}
    for f, ((P, feet), t) in enumerate(zip(frames, travel)):
        c = {}
        hit = impacts.get(f, {})
        L = rt.local(P, "hips")
        c["hips"] = (L.translation + rt.A["hips"].to_3x3().inverted() @ (t + hit.get("hips", Vector())),
                     L.to_quaternion())
        for b in ("spine", "chest", "neck", "head"):
            c[b] = (Vector(), rt.local(P, b).to_quaternion())
        for s, _ in SIDES:
            shoulder, elbow, wrist = P["upperarm" + s].translation + t, rt.tail(P, "upperarm" + s) + t, \
                rt.tail(P, "forearm" + s) + t
            c["hand_ik" + s] = (rt.at("hand_ik" + s, wrist + hit.get("hand" + s, Vector())), Quaternion())
            pole, prev["e" + s] = _pole(shoulder, elbow, wrist, prev.get("e" + s), Vector((0.0, 1.0, 0.0)))
            c["elbow_pole" + s] = (rt.at("elbow_pole" + s, pole), Quaternion())
            hip, knee = P["thigh" + s].translation + t, rt.tail(P, "thigh" + s) + t
            ankle = Vector(locked[s][0][f])
            reach = rt.length["thigh" + s] + rt.length["shin" + s] - 0.001
            if (ankle - hip).length > reach:      # a lock spot past the leg's reach: the foot follows the leg
                ankle = hip + (ankle - hip).normalized() * reach
            pole, prev["k" + s] = _pole(hip, knee, ankle, prev.get("k" + s), Vector((0.0, -1.0, 0.0)))
            c["knee_pole" + s] = (rt.at("knee_pole" + s, pole), Quaternion())
            rest = _rot(rt.A["foot" + s])
            w = locked[s][1][f]
            q = feet[s].slerp(_flat(feet[s], rest), w)
            sink = min((Matrix.Translation(ankle) @ q.to_matrix().to_4x4() @ v).z for v in rt.sole[s])
            ankle.z -= min(sink, 0.0)
            foot = Matrix.Translation(ankle) @ q.to_matrix().to_4x4()
            ik = foot @ (rt.A["foot_ik" + s].inverted() @ rt.A["foot" + s]).inverted()
            L = rt.A["foot_ik" + s].inverted() @ ik
            c["foot_ik" + s] = (L.translation, L.to_quaternion())
        out.append(c)
        hands.append({s: _rot(P["hand" + s]) for s, _ in SIDES})
    return out, hands


def _key_controls(arm, key):
    """Controls of a Key Pose, as apply_pose sets them; the extra bones at rest."""
    import build_robot as br
    br.apply_pose(arm, moves.KEY_POSES[key])
    c = {}
    for bone, _kind in set(br.CHANNEL_BONES.values()):
        pb = arm.pose.bones[bone]
        c[bone] = (pb.location.copy(), pb.rotation_euler.to_quaternion())
    for bone in EXTRA_BONES:
        c[bone] = (Vector(), Quaternion())
    return c


def _blend(a, b, w):
    if w <= 0.0:
        return a
    return {k: (a[k][0].lerp(b[k][0], w), a[k][1].slerp(b[k][1], w)) for k in a}


def _set(arm, controls):
    for bone, (loc, rot) in controls.items():
        pb = arm.pose.bones[bone]
        pb.location = loc
        pb.rotation_euler = rot.to_euler("XYZ", pb.rotation_euler)


def bake(arm, clip):
    """One Action `mocap.<name>`, a key per frame."""
    src = Source(os.path.join(PACKS, clip.fbx))
    rt = Retarget(arm, src)
    n = mocap.frames(clip)
    frames = [rt.fk(src.pose(s)) for s in mocap.warp(clip)]
    src.remove()
    controls, hands = _controls(rt, frames, mocap.stops(clip))
    keys = {k: _key_controls(arm, k) for k in (clip.key_in, clip.key_out) if k}
    act = bpy.data.actions.new("mocap." + clip.name)
    act.use_fake_user = True
    arm.animation_data.action = act
    first_hands = None
    for f in range(n):
        w_in, w_out = mocap.key_weight(clip, f)
        c = controls[f]
        if clip.idle:
            c = _blend(c, controls[0], mocap.loop_weight(clip, f))
        else:
            c = _blend(_blend(c, keys[clip.key_in], w_in), keys[clip.key_out], w_out)
        _set(arm, c)
        bpy.context.view_layer.update()
        hand = {}
        for s, _ in SIDES:
            fa = arm.pose.bones["forearm" + s].matrix
            parent = _rot(fa @ rt.A["forearm" + s].inverted() @ rt.A["hand" + s])
            hand[s] = parent.inverted() @ hands[f][s]
        if first_hands is None:
            first_hands = hand
        for s, _ in SIDES:
            q = hand[s]
            if clip.idle:
                q = q.slerp(first_hands[s], mocap.loop_weight(clip, f))
            else:
                q = q.slerp(Quaternion(), max(w_in, w_out))
            pb = arm.pose.bones["hand" + s]
            pb.rotation_euler = q.to_euler("XYZ", pb.rotation_euler)
        for bone in c:
            pb = arm.pose.bones[bone]
            pb.keyframe_insert("location", frame=f)
            pb.keyframe_insert("rotation_euler", frame=f)
        for s, _ in SIDES:
            arm.pose.bones["hand" + s].keyframe_insert("rotation_euler", frame=f)
    return act


def bake_all(arm):
    for clip in mocap.CLIPS.values():
        bake(arm, clip)
