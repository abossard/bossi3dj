"""Grabs for the README's OSC manual, in the live Blender (planet or island), clocks frozen, timer-stepped through grabber.py.

Through the Blender MCP:  DN["readme_out"] = "/abs/dir"; exec(open(bpy.path.abspath("//../review/readme_pairs.py")).read())
Optional: DN["readme_phase"] = seconds on the path for the pairs of a path camera (default 0), DN["readme_only"] = ["vj_fog", ...] (keys), DN["readme_cams"] = False (no camera pictures), DN["readme_extra"] = False,
DN["readme_cam_for"] = {"vj_meteor": 9} and DN["readme_advance"] = {"vj_star_speed": 30.0} override a pair's camera and advance; DN["readme_set"] = {"vj_meteor": {"vj_grid": 0.0}} holds more controls in both halves;
DN["readme_exec"] = {"vj_meteor": "import random; random.seed(24)\n"} runs after the reset (the first shooting star after a
reset is drawn from Python's random: seed 24 puts it across CAM_0's sky).
Writes <out>/plan.json first, then the frames (960x540 .ppm):
  <key>__cam<N>__lo.ppm, __lo2.ppm (the low state again: the noise floor), __hi.ppm
      one pair per control, from the row of synthwave_check.PRECONDITIONS (its camera, its preconditions, its advance, its
      `then`): low = wire 0, high = wire 1; a trigger: lo = before, hi = during (after the row's advance)
  cam__<N>__p<K>.ppm      every camera by day, at a few phases for the cameras on a path
  extra__*.ppm            hero frames: sunset, dense fog, night with the moon
Every job starts from the defaults (RESET) and a quiesced runtime; freeze_clocks.py keeps the clocks still, `advance` steps them.
Check the pairs by number with readme_pair_check.py."""
import importlib.util
import json
import os

import bpy

DN = bpy.app.driver_namespace
S = bpy.context.scene
OUT = DN["readme_out"].rstrip("/") + "/"
TOOLS = bpy.path.abspath("//../review/")
os.makedirs(OUT, exist_ok=True)

spec = importlib.util.spec_from_file_location("synthwave_check", bpy.path.abspath("//synthwave_check.py"))
CHECK = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CHECK)
PRE = CHECK.PRECONDITIONS
FLIGHT_CAM = 11
PLANET = S.objects.get("Planet_Centre") is not None
NCAM = len([o for o in S.objects if o.type == "CAMERA" and o.name.startswith("CAM_") and o.name[4:].isdigit()])
CYCLIC = {"vj_hue", "vj_fog_hue"}      # 1 is 0 again: the high state is half way round
CAM_FOR = {"vj_moon": 3, "vj_stars": 1, "vj_meteor": 2, "vj_pyramids": 2}     # where the row's own camera shows too little (self-check fallbacks;
# the moon: CAM_3 tracks it at night, CAM_4 had it out of frame)
CAM_FOR.update(DN.get("readme_cam_for", {}))
ADVANCE = {"vj_star_speed": 30.0}        # s: the stars' drift shows only over a longer interval (2 s was under the noise)
ADVANCE.update(DN.get("readme_advance", {}))
SET_FOR = DN.get("readme_set", {})      # more held controls for a pair, e.g. {"vj_meteor": {"vj_grid": 0.0}}
EXEC_FOR = DN.get("readme_exec", {})    # python after the reset, e.g. {"vj_meteor": "import random; random.seed(24)\n"}
SKIP = {"vj_cam", "vj_cam_auto"} | (set() if not PLANET else {"vj_grid_speed"})
ISLAND_ONLY_OK = {"vj_grid_speed"}

RESET = ("RT = DN['vj_runtime']; RT.quiesce()\n"
         "for k in list(S.keys()):\n"
         "    if k.startswith('vj_') and k != 'vj_cam' and isinstance(S[k], (int, float)):\n"
         "        d = S.id_properties_ui(k).as_dict().get('default')\n"
         "        if d is not None:\n"
         "            S[k] = d\n")


def advance(s):
    return "DN['vj_runtime'].advance(%r)\n" % s if s else ""


def cam_of(row):
    c = (row or {}).get("cams", [0])[0]
    return FLIGHT_CAM if c == "flight" else c


keys = sorted(k for k in S.keys() if k.startswith("vj_") and isinstance(S[k], (int, float)))
if DN.get("readme_only"):
    keys = [k for k in keys if k in DN["readme_only"]]
rows = []
for k in keys:
    if k in SKIP:
        continue
    ui = S.id_properties_ui(k).as_dict()
    trig = ui.get("description") == "trigger"
    row = PRE.get(k, {})
    rows.append({"key": k, "cam": CAM_FOR.get(k, cam_of(row)), "lo": ui.get("min", 0.0), "hi": ui.get("max", 1.0), "trigger": trig, "set": dict(row.get("set", {}), **SET_FOR.get(k, {})), "then": row.get("then"), "advance": ADVANCE.get(k, row.get("advance", 0.0))})

jobs, plan = [], []
last_cam = [None]


def job(name, cam, values, ex, settle, phase=0.0):
    if cam >= NCAM and not (PLANET and cam == FLIGHT_CAM):
        return
    st = dict(values)
    st.setdefault("vj_cam", cam)      # a `then` state may cut to another camera itself
    if cam != FLIGHT_CAM:              # a hard cut: at the default 1 the Director blends and a grab can land mid-blend.
        st.setdefault("vj_blend", 0.0)   # Not into the Flight: a hard cut there waits for the stream (lod_scene hold) for a
        # wall-time while the clocks step, and the reset Flight no longer repeats (/vj/boost floor 20.9 against 0.74)
    j = {"kind": "grab", "set": st, "exec": ex, "settle": settle if cam == last_cam[0] else settle + 2.5, "out": OUT + name + ".ppm"}
    if phase is not None:
        j["phase"] = phase
    last_cam[0] = cam
    jobs.append(j)


def pair(r):
    k, cam, pre = r["key"], r["cam"], dict(r["set"])
    base = "%s__cam%d" % (k, cam)
    lo, hi = float(r["lo"]), float(r["hi"])
    if k in CYCLIC:
        hi = lo + 0.5 * (hi - lo)
    states = (("lo", lo), ("lo2", lo), ("hi", hi))
    for tag, v in states:
        values = dict(pre)
        values[k] = v
        ex = RESET + EXEC_FOR.get(k, "")
        if r["then"]:       # a state the control shows only after a change (a cut for /vj/blend): the first settle is thrown away
            job("_discard", cam, dict(pre), RESET, 2.0)
            values.update(r["then"])
            ex = ""
        if r["trigger"]:
            values[k] = 1.0 if tag == "hi" else 0.0
        # the clocks step 0.1 s a drawn frame (frames of 40 to 60 ms): a long advance needs its time before the grab
        wait = 0.6 * r["advance"] if r["advance"] > 2.0 else 0.0
        job(base + "__" + tag, cam, values, ex + advance(r["advance"]), (2.0 if tag != "lo2" else 1.5) + wait, DN.get("readme_phase", 0.0))
    plan.append({"key": k, "cam": cam, "base": base, "trigger": r["trigger"], "lo": 0.0 if r["trigger"] else lo, "hi": 1.0 if r["trigger"] else hi})


for r in rows:
    pair(r)

if DN.get("readme_cams", True):
    paths = {4: (0.0, 60.0, 120.0, 180.0), 5: (0.0, 17.0, 35.0, 52.0), 6: (0.0, 30.0, 60.0, 90.0), 10: (0.0, 11.0, 22.0, 34.0)}
    for c in range(NCAM):
        for i, ph in enumerate(paths.get(c, (0.0,)) if PLANET else (0.0, 25.0, 50.0) if c >= 4 else (0.0,)):
            job("cam__%d__p%d" % (c, i), c, {"vj_night": 0.0}, RESET, 3.0, ph)
    if PLANET:
        job("cam__%d__p0" % FLIGHT_CAM, FLIGHT_CAM, {"vj_night": 0.0}, RESET + advance(2.0), 3.0)
        job("cam__%d__p1" % FLIGHT_CAM, FLIGHT_CAM, {"vj_night": 0.0, "vj_flight": 0.66}, RESET + advance(30.0), 3.0)
        job("cam__%d__p2" % FLIGHT_CAM, FLIGHT_CAM, {"vj_night": 0.0, "vj_flight": 1.0}, RESET + advance(60.0), 3.0)

if DN.get("readme_extra", True) and PLANET:
    for c in (0, 2):
        job("extra__sunset_cam%d" % c, c, {"vj_night": 0.3}, RESET, 3.0)
        job("extra__fog_cam%d" % c, c, {"vj_night": 0.0, "vj_fog": 0.9}, RESET, 3.0)
    job("extra__moon_night_cam3", 3, {"vj_night": 1.0, "vj_moon_phase": 1.0}, RESET, 3.0)

old = json.load(open(OUT + "plan.json")) if os.path.exists(OUT + "plan.json") else {"pairs": []}
merged = [p for p in old["pairs"] if p["key"] not in {q["key"] for q in plan}] + plan      # a partial run keeps the pairs it did not redo
with open(OUT + "plan.json", "w") as f:
    json.dump({"planet": PLANET, "pairs": merged, "jobs": [os.path.basename(j["out"]) for j in jobs], "settings": {"cams": NCAM}}, f, indent=1)
DN["grab_jobs"] = jobs
exec(open(TOOLS + "grabber.py").read())
exec(open(TOOLS + "freeze_clocks.py").read())
