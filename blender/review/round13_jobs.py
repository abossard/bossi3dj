"""Round 13 grabs (exec in the open planet scene after DN["check_out"] is set): every fixed camera by day (the plain on
CAM_0 and CAM_3, R13-KEEP elsewhere), CAM_5 in fog by day and night (the top band), CAM_2 in fog 1 (volume tile 8: no checker), CAM_4 by day on its path at 25 and
50 % (water step, crease) and at night in fog 1 (the haze), CAM_10 at night with /vj/nebula 0 and 1, and CAM_0, CAM_1,
CAM_3 at night with /vj/grid 1 (the night edges as before). The 200 mm limb shot comes from orbit_jobs.py
(DN["orbit_only"] = ["S9_orbit_limb"]). Numbers: round13_numbers.py."""
import bpy

DN = bpy.app.driver_namespace
NEB0 = {"set": {"vj_nebula": 0.0}, "tag": "neb0"}
G1 = {"set": {"vj_grid": 1.0}, "tag": "grid1"}
DN["check_list"] = ([(c, "day", 0.0, 0) for c in range(11)]
                    + [(5, t, f, 0) for t in ("day", "night") for f in (0.5, 1.0)]
                    + [(2, t, 1.0, 0) for t in ("day", "night")]
                    + [(4, "day", 0.0, 0, p) for p in (25, 50)]
                    + [(4, "night", 0.0, 0), (4, "night", 1.0, 0)]
                    + [(10, "night", 0.0, 0), (10, "night", 0.0, 0, None, NEB0)]
                    + [(c, "night", 0.0, 0, None, G1) for c in (0, 1, 3)])
exec(open(bpy.path.abspath("//../review/check_jobs.py")).read())
