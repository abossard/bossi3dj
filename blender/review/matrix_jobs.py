"""Builds the visual-check grab matrix (docs/research/synthwave-visual-check.md) and starts grabber.py.
Set DN["matrix_out"] (folder) and optionally DN["matrix_cams"] (list of camera numbers) before exec."""
import bpy

DN = bpy.app.driver_namespace
SP = bpy.path.abspath("//../review/")
OUT = DN["matrix_out"].rstrip("/") + "/"
CAMS = DN.get("matrix_cams", list(range(11)))
TIMES = (("day", 0.0), ("sunset", 0.5), ("night", 1.0))
FOGS = (("0", 0.0), ("05", 0.5), ("1", 1.0))
LOOP = (0, 25, 50, 75)
FIXED = {"vj_shock": 0.0, "vj_cam_speed": 0.0, "vj_blend": 0.0}   # blend 0: hard cuts, no grab mid-blend
LANDED = "S['rt_flock'] = 0.0; S['rt_flock_dir'] = -1.0"   # a settled day: the flamingos are home (rt_flock counts down in real time)
FLOWN = "S['rt_flock'] = 1.0; S['rt_flock_dir'] = 1.0"      # sunset and night: about 3 s into the flock's take-off (it flies off within 30 s)
jobs = []
for c in CAMS:
    first = True
    for tn, tv in TIMES:
        for fn, fv in FOGS:
            for e in (0, 1):
                phase = 0.0 if (e == 1 and tn in ("day", "sunset")) else 1.0
                jobs.append({"kind": "grab", "set": dict(FIXED, vj_cam=c, vj_night=tv, vj_fog=fv, vj_eclipse=float(e), vj_moon_phase=phase),
                             "exec": LANDED if tn == "day" else FLOWN,
                             "phase": 0.0, "settle": 3.0 if first else 2.0, "out": OUT + "CAM_%d_%s_f%s_e%d.ppm" % (c, tn, fn, e)})
                first = False
if DN.get("matrix_loop", True):
    period = bpy.context.scene.objects["CAM_4"].get("path_period", 240.0)
    for tn, tv in TIMES:
        for p in LOOP:
            jobs.append({"kind": "grab", "set": dict(FIXED, vj_cam=4, vj_night=tv, vj_fog=0.0, vj_eclipse=0.0, vj_moon_phase=1.0),
                         "exec": LANDED if tn == "day" else FLOWN,
                         "phase": period * p / 100.0, "settle": 3.0, "out": OUT + "CAM_4_%s_f0_e0_p%d.ppm" % (tn, p)})
if DN.get("matrix_sys", True):       # the system view: CAM_SYS by time and eclipse, the 4 views at /vj/night 0.5
    for tn, tv in TIMES:
        for e in (0, 1):
            phase = 0.0 if (e == 1 and tn in ("day", "sunset")) else 1.0
            jobs.append({"kind": "grab", "set": dict(FIXED, vj_night=tv, vj_fog=0.0, vj_eclipse=float(e), vj_moon_phase=phase),
                         "camera": "CAM_SYS", "settle": 3.0, "out": OUT + "CAM_SYS_%s_e%d.ppm" % (tn, e)})
    for view in ("FRONT", "BACK", "ABOVE", "MOON"):
        jobs.append({"kind": "grab", "set": dict(FIXED, vj_night=0.5, vj_fog=0.0, vj_eclipse=0.0, vj_moon_phase=1.0),
                     "camera": "CAM_SYS_" + view, "settle": 3.0, "out": OUT + "CAM_SYS_%s_night05_e0.ppm" % view.lower()})
if DN.get("matrix_proof", True):     # proof shots: the pull-out (S8), the LOD rings (G2), the celestial poles and the map's seam (S6)
    exec(open(SP + "proof_setup.py").read())
    for tn, tv in (("day", 0.0), ("night", 1.0)):
        st = dict(FIXED, vj_night=tv, vj_fog=0.0, vj_eclipse=0.0, vj_moon_phase=1.0)
        ex = LANDED if tn == "day" else FLOWN
        jobs.append({"kind": "grab", "set": dict(st, vj_cam=0), "exec": ex, "phase": 0.0, "settle": 3.0, "out": OUT + "PROOF_pull_0_ground_%s.ppm" % tn})
        for k_, nm in enumerate(("1K", "10K", "50K", "165K")):
            jobs.append({"kind": "grab", "set": st, "camera": "CAM_PULL_" + nm, "exec": ex, "phase": None, "settle": 4.0,
                         "out": OUT + "PROOF_pull_%d_%s_%s.ppm" % (k_ + 1, nm.lower(), tn)})
        jobs.append({"kind": "grab", "set": st, "camera": "CAM_PROOF_GROUND", "phase": None, "settle": 4.0, "out": OUT + "PROOF_lod_rings_%s.ppm" % tn,
                     "exec": ex + "; DN['proof_aim']('CAM_PROOF_GROUND', DN['proof_lod_dir'], DN['proof_lod_loc'])"})
    st = dict(FIXED, vj_night=1.0, vj_fog=0.0, vj_eclipse=0.0, vj_moon_phase=1.0)
    for nm, cam, aim in (("ground_north_pole", "CAM_PROOF_GROUND", "(1.0, 0.0, 0.08), DN['proof_hi']"),
                         ("ground_south_pole", "CAM_PROOF_GROUND", "(-1.0, 0.0, 0.08), DN['proof_hi']"),
                         ("space_north_pole", "CAM_PROOF_SPACE", "(1.0, 0.0, 0.0), (165000.0, 0.0, -16000.0)"),
                         ("space_south_pole", "CAM_PROOF_SPACE", "(-1.0, 0.0, 0.0), (-165000.0, 0.0, -16000.0)"),
                         ("space_map_seam", "CAM_PROOF_SPACE", "DN['seam_dir'](), (165000.0, 0.0, -16000.0)")):
        jobs.append({"kind": "grab", "set": st, "camera": cam, "phase": None, "settle": 4.0, "out": OUT + "PROOF_stars_%s.ppm" % nm,
                     "exec": FLOWN + "; DN['proof_aim']('%s', %s)" % (cam, aim)})
DN["grab_jobs"] = jobs
exec(open(SP + "grabber.py").read())
