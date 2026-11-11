"""Round 10 numbers for /vj/grid. Set DN["grid_out"] and DN["grid_mode"] before exec.

mode "day": clocks frozen (exec freeze_clocks.py after this), by day on CAM_0, CAM_3 and CAM_PULL_10K:
    <cam>_day_g1a, <cam>_day_g1b (the noise floor) and <cam>_day_g0. /vj/grid must not change the frame.
mode "night" (DN["grid_exec"] adds code run before each grab, see terrain_equality.py's HOLD and STOP): clocks running, static CAM_0 at night: <cam>_night_g<0|1>_t0 and _t1, 1 s apart.
    The t0 to t1 difference must be no larger with /vj/grid 1 than with 0 (no line moves against the terrain).
mode "fly": clocks running, CAM_4 flying (cam speed 1) at night with /vj/grid 1: CAM_4_night_fly_a and _b, 1 s apart.
Compare with grid_diff.py."""
import bpy

DN = bpy.app.driver_namespace
OUT = DN["grid_out"].rstrip("/") + "/"
TOOLS = bpy.path.abspath("//../review/")
exec(open(TOOLS + "proof_setup.py").read())
FIXED = {"vj_shock": 0.0, "vj_cam_speed": 0.0, "vj_fog": 0.0, "vj_eclipse": 0.0, "vj_moon_phase": 1.0, "vj_nebula": 1.0}
LANDED = "S['rt_flock'] = 0.0; S['rt_flock_dir'] = -1.0"
FLOWN = "S['rt_flock'] = 60.0; S['rt_flock_dir'] = 1.0\n" + DN.get("grid_exec", "")   # grid_exec: more code per grab (the rig held, the Flight stopped)


def job(cam, st, name, settle, ex):
    j = {"kind": "grab", "set": dict(FIXED, **st), "exec": ex, "settle": settle, "out": OUT + name + ".ppm"}
    if isinstance(cam, int):
        j["set"]["vj_cam"] = cam
        j["phase"] = 0.0
    else:
        j["camera"], j["phase"] = cam, None
    return j


jobs = []
if DN["grid_mode"] == "day":
    for cam in (0, 3, "CAM_PULL_10K"):
        nm = cam if isinstance(cam, str) else "CAM_%d" % cam
        for tag, g in (("g1a", 1.0), ("g1b", 1.0), ("g0", 0.0)):
            jobs.append(job(cam, {"vj_night": 0.0, "vj_grid": g}, "%s_day_%s" % (nm, tag), 3.0, LANDED))
elif DN["grid_mode"] == "fly":
    jobs.append(job(4, {"vj_night": 1.0, "vj_grid": 1.0, "vj_cam_speed": 1.0}, "CAM_4_night_fly_a", 3.0, FLOWN))
    jobs.append(job(4, {"vj_night": 1.0, "vj_grid": 1.0, "vj_cam_speed": 1.0}, "CAM_4_night_fly_b", 1.0, FLOWN))
    jobs[-1]["phase"] = None      # flies on from where _a was grabbed
else:
    for g in (0.0, 1.0):
        jobs.append(job(0, {"vj_night": 1.0, "vj_grid": g}, "CAM_0_night_g%d_t0" % g, 3.0, FLOWN))
        jobs.append(job(0, {"vj_night": 1.0, "vj_grid": g}, "CAM_0_night_g%d_t1" % g, 1.0, FLOWN))
DN["grab_jobs"] = jobs
exec(open(TOOLS + "grabber.py").read())
