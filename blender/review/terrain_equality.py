"""The terrain gate's proof (flight-presentable.md, Part C): a fixed shot looks the same with the Flight runtime started
as stopped. Exec in the open planet scene with DN["eq_out"] = "/abs/folder/" (and optionally DN["eq_cases"] =
[(cam, night), ...]). Per case: two grabs started (A1, A2), two stopped (B1, B2), clocks frozen throughout
(freeze_clocks.py). Held: /vj/energy 0 (no pulse on the rig) and flight_rt.moved_pose replaced by the shot's own pose,
since the energy ellipse moves a fixed shot by at least 1 m at any energy; restored at the end. Compare with
terrain_equality_diff.py."""
import bpy

DN = bpy.app.driver_namespace
SP = bpy.path.abspath("//../review/")
OUT = DN["eq_out"].rstrip("/") + "/"
CASES = DN.get("eq_cases", [(0, 0.0), (1, 0.0), (0, 1.0)])
FR = "FR = DN['vj_runtime'].quiesce.__globals__['_state']['flight_rt']\n"
HOLD = FR + "FR.__dict__.setdefault('_moved', FR.moved_pose); FR.moved_pose = lambda ob, dg, drive: FR.pose_of(ob, dg)\n"
START = FR + "FR._state['lod'] or FR.start()\n" + HOLD + "FR.quiesce()\n"
STOP = FR + "FR._state['lod'] and FR.stop()\n"
RESTORE = FR + "FR._state['lod'] or FR.start()\nFR.moved_pose = FR.__dict__.pop('_moved', FR.moved_pose)\n"
LANDED = "S['rt_flock'] = 0.0; S['rt_flock_dir'] = -1.0\n"
FLOWN = "S['rt_flock'] = 60.0; S['rt_flock_dir'] = 1.0\n"
jobs = []
for cam, night in CASES:
    st = {"vj_cam": cam, "vj_night": night, "vj_energy": 0.0, "vj_hit": 0.0, "vj_shock": 0.0, "vj_cam_speed": 0.0,
          "vj_fog": 0.0, "vj_eclipse": 0.0, "vj_moon_phase": 1.0, "vj_nebula": 1.0}
    flock = FLOWN if night > 0.5 else LANDED
    name = OUT + "CAM_%d_n%d_" % (cam, int(night))
    jobs += [
        {"kind": "grab", "set": st, "exec": START + flock, "settle": 5.0, "phase": 0.0, "out": name + "A1.ppm"},
        {"kind": "grab", "settle": 2.0, "out": name + "A2.ppm"},
        {"kind": "grab", "exec": STOP, "set": {"vj_cam": cam}, "settle": 4.0, "out": name + "B1.ppm"},
        {"kind": "grab", "settle": 2.0, "out": name + "B2.ppm"},
    ]
jobs.append({"kind": "grab", "exec": RESTORE, "settle": 1.0, "out": OUT + "_restore.ppm"})
DN["grab_jobs"] = jobs
exec(open(SP + "grabber.py").read())
exec(open(SP + "freeze_clocks.py").read())
