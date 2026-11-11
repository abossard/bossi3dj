"""Round 12 grabs (exec in the open planet scene after DN["check_out"] is set): the round 11 list (CAM_0 to CAM_10 by day,
CAM_0, CAM_1, CAM_3, CAM_4 at night with /vj/grid 1, CAM_0 and CAM_3 with /vj/grid 0), plus CAM_1 at night with
/vj/grid 0 (the third pair for net_regularity.py) and the Flight shot CAM_11 at night with /vj/grid 1 and 0, its first
grab a warm-up for the streamed terrain. The flyover pair comes from grid_numbers.py (mode "fly")."""
import bpy

DN = bpy.app.driver_namespace
G1 = {"set": {"vj_grid": 1.0}, "tag": "grid1"}
G0 = {"set": {"vj_grid": 0.0}, "tag": "grid0"}
WARM = {"set": {"vj_grid": 1.0}, "tag": "warm"}
DN["check_list"] = ([(c, "day", 0.0, 0, None, {"set": {"vj_grid": 1.0}}) for c in range(11)]
                    + [(c, "night", 0.0, 0, None, G1) for c in (0, 1, 3, 4)]
                    + [(c, "night", 0.0, 0, None, G0) for c in (0, 1, 3)]
                    + [(11, "night", 0.0, 0, None, x) for x in (WARM, G1, G0)])
exec(open(bpy.path.abspath("//../review/check_jobs.py")).read())
