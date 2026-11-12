"""Round 14 grabs (exec in the open planet scene after DN["check_out"] is set): CAM_4 by day at path 25, 50 and 75 % (60, 120,
180 s) and at 0 %, CAM_1, CAM_8 and CAM_0 by day. Hard cuts (check_jobs.py), full size is read by the reviewer from the .png."""
import bpy

DN = bpy.app.driver_namespace
DN["check_list"] = [(4, "day", 0.0, 0, p) for p in (0, 25, 50, 75)] + [(c, "day", 0.0, 0) for c in (1, 8, 0)]
exec(open(bpy.path.abspath("//../review/check_jobs.py")).read())
