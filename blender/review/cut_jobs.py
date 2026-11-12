"""M1/M2: cuts through every camera and into CAM_3 and CAM_9 (the tracking shots) from far cameras, at day, sunset and
night, cameras moving (vj_cam_speed 1). Results: DN["grabber"]["log"] entries with worst_ms and aim_first."""
import bpy

DN = bpy.app.driver_namespace
SP = bpy.path.abspath("//../review/")
SEQ = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 0, 3, 7, 3, 8, 3, 9, 3, 10, 3, 0, 3, 8, 9, 6, 9, 10, 9]
jobs = []
for n in DN.get("cut_nights", (0.0, 0.5, 1.0)):
    jobs.append({"kind": "grab", "set": {"vj_night": n, "vj_fog": 0.0, "vj_shock": 0.0, "vj_eclipse": 0.0, "vj_moon_phase": 1.0,
                                         "vj_cam_speed": 1.0, "vj_blend": 0.0}, "settle": 1.0, "out": SP + "_warm.ppm"})   # hard cuts
    for c in SEQ:
        jobs.append({"kind": "cut", "cam": c, "watch": 1.5, "pre": 1.2, "tag": "n%g" % n})
DN["grab_jobs"] = jobs
exec(open(SP + "grabber.py").read())
