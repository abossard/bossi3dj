"""Aim helpers for the proof cameras (CAM_PROOF_GROUND, CAM_PROOF_SPACE), into the driver namespace for grab jobs."""
import bpy
from mathutils import Matrix, Vector

DN = bpy.app.driver_namespace
S = bpy.context.scene
R = 16000.0
C = Vector((0.0, 0.0, -R))


def proof_aim(name, direction, loc=None):
    co = S.objects[name]
    if loc is not None:
        co.location = Vector(loc)
    d = Vector(direction).normalized()
    up = (co.location - C).normalized() if (co.location - C).length < 40000.0 else Vector((0.0, 0.0, 1.0))
    if abs(d.dot(up)) > 0.98:
        up = Vector((0.0, 1.0, 0.0))
    x = d.cross(up).normalized()
    co.rotation_euler = Matrix((x, x.cross(d), -d)).transposed().to_euler()


def seam_dir():
    """The star map's edge (u = 0/1) on the celestial equator, in world space for the current sky turn."""
    return Matrix.Rotation(-S.get("rt_star_ang", 0.0), 3, "X") @ Vector((0.0, -1.0, 0.0))


tgt = S.objects["CAM_2_target"].matrix_world.translation
H = tgt - (tgt - C).normalized() * 41.0
uh = (H - C).normalized()
look = H - S.objects["CAM_0"].matrix_world.translation
look = (look - uh * look.dot(uh)).normalized()
DN["proof_aim"] = proof_aim
DN["seam_dir"] = seam_dir
DN["proof_hi"] = tuple(H + uh * 400.0)                         # star views from 400 m over the plaza
DN["proof_lod_loc"] = tuple(H + uh * 300.0)                    # LOD rings: 300 m over the plaza, 20 deg down the valley
DN["proof_lod_dir"] = tuple(look * 0.94 - uh * 0.34)
