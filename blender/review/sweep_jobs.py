"""Altitude sweep for the globe handover (FL2): CAM_PROOF_GROUND over the pyramids, 60 deg down along CAM_0's view,
from DN["sweep_alts"] (m), one grab per altitude into DN["sweep_out"]/<tag>_<time>_<alt>.ppm, for the times in
DN["sweep_times"]. A frame-difference trace over the grabs shows any pop."""
import math

import bpy
from mathutils import Vector

DN = bpy.app.driver_namespace
S = bpy.context.scene
TOOLS = bpy.path.abspath("//../review/")
OUT = DN["sweep_out"].rstrip("/") + "/"
TAG = DN.get("sweep_tag", "sweep")
exec(open(TOOLS + "proof_setup.py").read())
R = 16000.0
C = Vector((0.0, 0.0, -R))
tgt = S.objects["CAM_2_target"].matrix_world.translation
H = tgt - (tgt - C).normalized() * 41.0
uh = (H - C).normalized()
look = H - S.objects["CAM_0"].matrix_world.translation
look = (look - uh * look.dot(uh)).normalized()


def sweep_place(alt):
    pos = H + uh * alt - look * (alt / math.tan(math.radians(60.0)))
    DN["proof_aim"]("CAM_PROOF_GROUND", H - pos, pos)


DN["sweep_place"] = sweep_place
TV = {"day": 0.0, "sunset": 0.5, "night": 1.0}
jobs = []
for tn in DN.get("sweep_times", ("day", "sunset", "night")):
    st = {"vj_shock": 0.0, "vj_cam_speed": 0.0, "vj_fog": 0.0, "vj_eclipse": 0.0, "vj_moon_phase": 1.0, "vj_night": TV[tn]}
    for k_, alt in enumerate(DN["sweep_alts"]):
        jobs.append({"kind": "grab", "set": st if k_ == 0 else None, "camera": "CAM_PROOF_GROUND", "phase": None,
                     "settle": 3.0 if k_ == 0 else 1.2, "exec": "DN['sweep_place'](%r)" % alt,
                     "out": OUT + "%s_%s_%05d.ppm" % (TAG, tn, int(alt))})
DN["grab_jobs"] = jobs
exec(open(TOOLS + "grabber.py").read())
