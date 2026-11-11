"""Round 10 frame time, one build at a time (exec in the open scene; run once on the round 9 build, once on round 10):
a day ground camera (CAM_0) and the orbit night view (CAM_PROOF_SPACE as orbit_jobs places it), 3 rounds interleaved.
Set DN["ab_out"] (json path) before exec."""
import bpy

DN = bpy.app.driver_namespace
TOOLS = bpy.path.abspath("//../review/")
exec(open(TOOLS + "proof_setup.py").read())
DN["orbit_out"], DN["orbit_only"] = "/tmp", ["none"]      # defines DN["orbit_view"], grabs nothing
exec(open(TOOLS + "orbit_jobs.py").read(), {})      # own namespace: its grabber's timer must not share `st` with ab
FIXED = {"vj_shock": 0.0, "vj_cam_speed": 0.0, "vj_fog": 0.0, "vj_eclipse": 0.0, "vj_moon_phase": 1.0, "vj_grid": 1.0}
DN["ab"] = {"cells": [
    {"name": "CAM_0_day", "set": dict(FIXED, vj_night=0.0, vj_cam=0.0), "exec": "S.camera = S.objects['CAM_0']"},
    {"name": "orbit_night", "set": dict(FIXED, vj_night=0.5),
     # placed 1.5 s into the settle, once the sun has followed vj_night
     "exec": "S.camera = S.objects['CAM_PROOF_SPACE']; "
             "bpy.app.timers.register(lambda: DN['orbit_view']('night', lens=35.0), first_interval=1.5)"}],
    "rounds": 3, "settle": 5.0, "measure": 10.0, "out": DN["ab_out"]}
exec(open(TOOLS + "ab_frametime.py").read())
