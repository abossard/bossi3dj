"""Round 11 frame time, one build at a time (exec in the open scene; run once on the round 10 build, once on round 11):
CAM_0 by day and at night with /vj/grid 1 (the real edges on the plain), 3 rounds interleaved.
Set DN["ab_out"] (json path) before exec."""
import bpy

DN = bpy.app.driver_namespace
TOOLS = bpy.path.abspath("//../review/")
exec(open(TOOLS + "proof_setup.py").read())
FIXED = {"vj_shock": 0.0, "vj_cam_speed": 0.0, "vj_fog": 0.0, "vj_eclipse": 0.0, "vj_moon_phase": 1.0, "vj_grid": 1.0, "vj_cam": 0.0}
DN["ab"] = {"cells": [
    {"name": "CAM_0_day", "set": dict(FIXED, vj_night=0.0), "exec": "S.camera = S.objects['CAM_0']"},
    {"name": "CAM_0_night", "set": dict(FIXED, vj_night=1.0), "exec": "S.camera = S.objects['CAM_0']"}],
    "rounds": 3, "settle": 5.0, "measure": 10.0, "out": DN["ab_out"]}
exec(open(TOOLS + "ab_frametime.py").read())
