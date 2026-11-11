"""S9 proof: the pull-out (ground to 165 km, day and night) and four orbit views at full resolution (1920x1080):
the day side, the night side, the terminator and a limb close-up. Set DN["orbit_out"] before exec; DN["orbit_only"]
(optional) is a list of output names without extension to grab only those, e.g. ["S9_orbit_limb"]."""
import bpy
from mathutils import Vector

DN = bpy.app.driver_namespace
S = bpy.context.scene
TOOLS = bpy.path.abspath("//../review/")
OUT = DN["orbit_out"].rstrip("/") + "/"
exec(open(TOOLS + "proof_setup.py").read())
R = 16000.0
C = Vector((0.0, 0.0, -R))
FIXED = {"vj_shock": 0.0, "vj_cam_speed": 0.0, "vj_fog": 0.0, "vj_eclipse": 0.0, "vj_moon_phase": 1.0}
LANDED = "S['rt_flock'] = 0.0; S['rt_flock_dir'] = -1.0"
FLOWN = "S['rt_flock'] = 1.0; S['rt_flock_dir'] = 1.0"


def orbit_view(kind, dist=60000.0, lens=35.0):
    """Places CAM_PROOF_SPACE for one orbit view, from the current sun direction (rt_sun_*)."""
    s_ = Vector((S["rt_sun_x"], S["rt_sun_y"], S["rt_sun_z"])).normalized()
    side = s_.cross(Vector((1.0, 0.0, 0.0)))
    side = side.normalized() if side.length > 1e-3 else s_.orthogonal().normalized()
    d_ = {"day": (s_ * 0.8 + side * 0.6), "night": (-s_ * 0.8 + side * 0.6), "terminator": side,
          "limb": side}[kind].normalized()
    co = S.objects["CAM_PROOF_SPACE"]
    co.data.lens = lens
    pos = C + d_ * dist
    aim = C if kind != "limb" else C + (s_ * 0.2 + d_.cross(s_).normalized()).normalized() * R * 1.02
    DN["proof_aim"]("CAM_PROOF_SPACE", aim - pos, pos)


DN["orbit_view"] = orbit_view
jobs = []
for tn, tv in (("day", 0.0), ("night", 1.0)):
    st = dict(FIXED, vj_night=tv)
    ex = LANDED if tn == "day" else FLOWN
    jobs.append({"kind": "grab", "set": dict(st, vj_cam=0), "exec": ex, "phase": 0.0, "settle": 3.0, "full": True,
                 "out": OUT + "S9_pull_0_ground_%s.ppm" % tn})
    for k_, nm in enumerate(("1K", "10K", "50K", "165K")):
        jobs.append({"kind": "grab", "set": st, "camera": "CAM_PULL_" + nm, "exec": ex, "phase": None, "settle": 4.0, "full": True,
                     "out": OUT + "S9_pull_%d_%s_%s.ppm" % (k_ + 1, nm.lower(), tn)})
for kind, lens in (("day", 35.0), ("night", 35.0), ("terminator", 35.0), ("limb", 200.0)):
    jobs.append({"kind": "grab", "set": dict(FIXED, vj_night=0.5), "camera": "CAM_PROOF_SPACE", "phase": None, "settle": 4.0, "full": True,
                 "exec": FLOWN + "; DN['orbit_view']('%s', lens=%g)" % (kind, lens), "out": OUT + "S9_orbit_%s.ppm" % kind})
jobs.append({"kind": "grab", "set": dict(FIXED, vj_night=0.0, vj_cam=6), "exec": LANDED, "phase": 0.0, "settle": 4.0, "full": True,
             "out": OUT + "S9_CAM_6_day.ppm"})
jobs.append({"kind": "grab", "set": dict(FIXED, vj_night=1.0), "camera": "CAM_SYS", "exec": FLOWN, "phase": None, "settle": 4.0, "full": True,
             "out": OUT + "S9_CAM_SYS_night.ppm"})
only = DN.get("orbit_only")
if only:
    jobs = [j for j in jobs if j["out"].rsplit("/", 1)[-1][:-4] in only]
DN["grab_jobs"] = jobs
exec(open(TOOLS + "grabber.py").read())
