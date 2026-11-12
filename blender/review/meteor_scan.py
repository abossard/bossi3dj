"""Which camera sees the /vj/meteor streak: per fixed camera at night a frame before and one `advance` s after the
trigger, from the defaults and a quiesced runtime (the same shooting star every time), clocks frozen.
    DN["meteor_out"] = "/abs/dir"; optional DN["meteor_advance"] = 0.4; exec this file (Blender MCP)
Writes <dir>/m__cam<N>__lo.ppm and __hi.ppm (960x540); readme_pair_check-style numbers: meteor_scan_check.py DIR."""
import bpy

DN = bpy.app.driver_namespace
S = bpy.context.scene
OUT = DN["meteor_out"].rstrip("/") + "/"
TOOLS = bpy.path.abspath("//../review/")
ADV = DN.get("meteor_advance", 0.4)
RESET = ("RT = DN['vj_runtime']; RT.quiesce()\n"
         "for k in list(S.keys()):\n"
         "    if k.startswith('vj_') and k != 'vj_cam' and isinstance(S[k], (int, float)):\n"
         "        d = S.id_properties_ui(k).as_dict().get('default')\n"
         "        if d is not None:\n"
         "            S[k] = d\n")
jobs = []
for c in range(11):
    for tag, m in (("lo", 0.0), ("hi", 1.0)):
        jobs.append({"kind": "grab", "set": {"vj_cam": c, "vj_night": 1.0, "vj_meteor": m}, "phase": 0.0,
                     "exec": RESET + "DN['vj_runtime'].advance(%r)\n" % ADV, "settle": 4.0 if tag == "lo" else 2.5,
                     "out": OUT + "m__cam%d__%s.ppm" % (c, tag)})
DN["grab_jobs"] = jobs
exec(open(TOOLS + "grabber.py").read())
exec(open(TOOLS + "freeze_clocks.py").read())
