"""Quick check sheet: DN["check_list"] = [(cam (int or name), time, fog, eclipse[, phase[, extra]])], DN["check_out"] = folder.
extra: {"set": {vj_*: value}, "tag": "neb0"} holds more controls and adds _<tag> to the name.
Grabs each into <folder>/<cam>_<time>_f<fog>_e<eclipse>[_p<phase>][_<tag>].ppm"""
import bpy

DN = bpy.app.driver_namespace
SP = bpy.path.abspath("//../review/")
OUT = DN["check_out"].rstrip("/") + "/"
TV = {"day": 0.0, "sunset": 0.5, "night": 1.0}
LANDED = "S['rt_flock'] = 0.0; S['rt_flock_dir'] = -1.0"
FLOWN = "S['rt_flock'] = 60.0; S['rt_flock_dir'] = 1.0"
jobs = []
for item in DN["check_list"]:
    cam, tn, fog, e = item[:4]
    ph = item[4] if len(item) > 4 and item[4] is not None else None
    extra = item[5] if len(item) > 5 else {}
    mph = 0.0 if (e == 1 and tn in ("day", "sunset")) else 1.0
    st = {"vj_shock": 0.0, "vj_cam_speed": 0.0, "vj_night": TV[tn], "vj_fog": fog, "vj_eclipse": float(e), "vj_moon_phase": mph,
          "vj_nebula": 1.0, **extra.get("set", {})}
    job = {"kind": "grab", "set": st, "settle": 3.0, "exec": LANDED if tn == "day" else FLOWN,
           "out": OUT + "%s_%s_f%s_e%d%s.ppm" % (cam if isinstance(cam, str) else "CAM_%d" % cam, tn, str(fog).replace(".", ""), e,
                                                  ("_p%d" % ph if ph is not None else "") + ("_" + extra["tag"] if "tag" in extra else ""))}
    if isinstance(cam, str):
        job["camera"] = cam
    else:
        st["vj_cam"] = cam
    if isinstance(cam, int) and cam == 4:
        job["phase"] = bpy.context.scene.objects["CAM_4"].get("path_period", 240.0) * (ph or 0.0) / 100.0
    else:
        job["phase"] = 0.0
    jobs.append(job)
DN["grab_jobs"] = jobs
exec(open(SP + "grabber.py").read())
