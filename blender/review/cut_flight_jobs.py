"""M1 with the Flight shot: hard cuts (/vj/blend 0) into and out of CAM_11 and between fixed shots, by day, cameras
moving. Exec in the open planet scene; results in DN["grabber"]["log"] (worst_ms, first_ms per cut)."""
import bpy

DN = bpy.app.driver_namespace
SP = bpy.path.abspath("//../review/")
SEQ = DN.get("cut_seq", [0, 11, 0, 1, 11, 2, 3, 11, 5, 11, 7, 8, 11, 9, 0, 1])
jobs = [{"kind": "grab", "set": {"vj_night": 0.0, "vj_fog": 0.0, "vj_shock": 0.0, "vj_eclipse": 0.0, "vj_moon_phase": 1.0,
                                 "vj_cam_speed": 1.0, "vj_blend": 0.0, "vj_flight": 0.0, "vj_energy": 0.3}, "settle": 1.0,
         "out": SP + "_warm.ppm"}]
jobs += [{"kind": "cut", "cam": c, "watch": 1.5, "pre": 1.2, "tag": "flight"} for c in SEQ]
DN["grab_jobs"] = jobs
exec(open(SP + "grabber.py").read())
