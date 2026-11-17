"""Backdrop Plates for the Robot Scene: a Geo-Scatter biome as a megastructure behind the arena, one loop per Angle,
for Magic to draw behind the Clips. The Shot Cameras are locked, so one plate per Angle fits every Clip on it.

    python3 robot/backdrop/render_plates.py render [BIOME...] [--angles ANGLE...]   # Blender slot: base and glow stills
    python3 robot/backdrop/render_plates.py encode [BIOME...] [--angles ANGLE...]   # no Blender: loops, luma, composites
    python3 robot/backdrop/render_plates.py render BIOME --angles A... --set seed=2 sky=0.03 rim=2 --tag _v1   # a variant
    python3 robot/backdrop/render_plates.py preview BIOME --angles A... --tag _v1   # 480 px composites of a variant
    python3 robot/backdrop/render_plates.py promote BIOME --angles A... --tag _v1   # the variant becomes the plate
    python3 robot/backdrop/render_plates.py manifest              # the Manifest's `backdrops` from the plates on disk
    python3 robot/backdrop/render_plates.py reel                  # no Blender: docs/video/robot-backdrops.mp4

render: one Blender run per biome (plates_blender.py) writes robot/build/probe/backdrop/<biome>/<angle>_{base,glow}.png
at the package's size from the Angle's own Shot Camera, Eevee (the low quality path).
encode: blends base and glow into a seamless loop of LOOP_FRAMES (one slow swell of the biome's lights over 4 bars),
H.264 full range, to robot/package/v1/backdrop/<biome>/<angle>.mov; checks its luma per frame (not black); and writes
one composite still per Angle, the Android's beauty frame over the plate, to robot/build/probe/backdrop/<biome>/.
Needs the Biome Reader set up (robot/build/review/biome_reader_setup.py) with the kits' search paths.
"""
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"
BLEND = os.path.join(ROOT, "robot", "build", "robot.blend")
PACKAGE = os.path.join(ROOT, "robot", "package", "v1")
PROBE = os.path.join(ROOT, "robot", "build", "probe", "backdrop")
REEL = os.path.join(ROOT, "docs", "video", "robot-backdrops.mp4")
LIB = os.path.expanduser("~/Library/Application Support/Blender/data/scatter library/_biomes_/GreebleTown")

# scale and placement from preview rounds B1 to B3 (docs/handover/robot-assets.md): median part about 8 m.
# per_angle overrides scale, area or y0 on one Angle (round P1 fails: a thin dark band on the horizon). A taller
# scale keeps the instance count only if the area grows with it (Geo-Scatter's density is per local square metre).
BIOMES = {
    "arclink_city_1": {"biome": "Arclink City/arclink_city_1.biome", "scale": 1.0, "area": [200, 230], "y0": 15},
    "chipset_04": {"biome": "Binary Frames/chipset_04.biome", "scale": 20.0, "area": [120, 120], "y0": 8,
                   "per_angle": {"front": {"scale": 40.0, "area": [240, 240]},
                                 "duel_low": {"scale": 40.0, "area": [240, 240]}}},
    # y0 8 put a pipe behind the Android's head on side and one slab across the fighters on duel_low; at y0 30
    # front and duel_low thinned to a band (round P1). front passed at y0 8.
    "greeble_01": {"biome": "Future Scratch/greeble_01.biome", "scale": 4.0, "area": [200, 200], "y0": 30,
                   "per_angle": {"front": {"y0": 8},
                                 "duel_low": {"scale": 8.0, "area": [400, 400]}}},
    "greeble_03": {"biome": "Future Scratch/greeble_03.biome", "scale": 4.0, "area": [200, 200], "y0": 30},
}
GLOW = 3.0
LOOP_FRAMES = 232          # 16 beats at 124 BPM and 30 fps, the length of the 4 bar Clips
BLACK_LUMA = 8.0           # mean Y (0..255) below this counts as a black plate
# the Clip whose first beauty frame goes over each Angle's plate in the composite and the reel
SHOWCASE = {"front": "idle_guard__front", "side": "idle_guard__side",
            "duel_wide": "duel_idle__duel_wide", "duel_low": "duel_idle__duel_low"}


def _angles():
    with open(os.path.join(PACKAGE, "manifest.json")) as f:
        return [a["id"] for a in json.load(f)["angles"]]


def _run(cmd):
    print("+", " ".join(cmd[:6]), "...")
    subprocess.run(cmd, check=True)


def render(names, angles, sets, tag):
    """sets: overrides for every Angle of this run (a variant), applied over BIOMES and its per_angle."""
    for name in names:
        b = BIOMES[name]
        out = os.path.join(PROBE, name)
        os.makedirs(out, exist_ok=True)
        per = {a: dict(b.get("per_angle", {}).get(a, {}), **sets) for a in angles}
        job = dict(b, biome=os.path.join(LIB, b["biome"]), angles=angles, out=out, glow=GLOW, per_angle=per, tag=tag)
        path = os.path.join(out, "job%s.json" % tag)
        with open(path, "w") as f:
            json.dump(job, f, indent=1)
        _run([BLENDER, "-b", BLEND, "-P", os.path.join(ROOT, "robot", "backdrop", "plates_blender.py"), "--", path])


def _luma(mov):
    """Mean Y per frame of a movie, via signalstats."""
    res = subprocess.run(["ffprobe", "-v", "error", "-f", "lavfi", "-i",
                          "movie=%s,signalstats" % mov.replace(":", r"\:"),
                          "-show_entries", "frame_tags=lavfi.signalstats.YAVG", "-of", "csv=p=0"],
                         check=True, capture_output=True, text=True)
    return [float(v.strip(",")) for v in res.stdout.split()]


def encode(names, angles):
    path = os.path.join(PROBE, "encode_report.json")
    report = {}
    if os.path.isfile(path):          # a run on some Angles keeps the others' entries
        with open(path) as f:
            report = json.load(f)
    for name in names:
        src = os.path.join(PROBE, name)
        dst = os.path.join(PACKAGE, "backdrop", name)
        os.makedirs(dst, exist_ok=True)
        for angle in angles:
            mov = os.path.join(dst, angle + ".mov")
            swell = "0.5-0.5*cos(2*PI*N/%d)" % LOOP_FRAMES
            _run(["ffmpeg", "-v", "error", "-y",
                  "-loop", "1", "-framerate", "30", "-i", os.path.join(src, angle + "_base.png"),
                  "-loop", "1", "-framerate", "30", "-i", os.path.join(src, angle + "_glow.png"),
                  "-filter_complex", "[0][1]blend=all_expr='A*(1-(%s))+B*(%s)',format=yuvj420p" % (swell, swell),
                  "-frames:v", str(LOOP_FRAMES), "-c:v", "libx264", "-crf", "14", "-g", str(LOOP_FRAMES),
                  "-color_range", "pc", "-tag:v", "avc1", "-movflags", "+faststart", mov])
            y = _luma(mov)
            beauty = os.path.join(PACKAGE, "beauty", SHOWCASE[angle] + ".mov")
            comp = os.path.join(src, angle + "_composite.png")
            _run(["ffmpeg", "-v", "error", "-y", "-i", mov, "-i", beauty, "-filter_complex", "[0][1]overlay",
                  "-frames:v", "1", comp])
            report.setdefault(name, {})[angle] = {
                "frames": len(y), "luma_min": round(min(y), 1), "luma_max": round(max(y), 1),
                "black": min(y) < BLACK_LUMA, "loop_seam": round(abs(y[0] - y[-1]), 2), "composite": comp}
    with open(path, "w") as f:
        json.dump(report, f, indent=1)
    print(json.dumps({n: report[n] for n in names}, indent=1))


def preview(names, angles, tag):
    """No encode: the Angle's first beauty frame over the variant's base still, a 480 px tile for the reviewer."""
    for name in names:
        src = os.path.join(PROBE, name)
        for angle in angles:
            beauty = os.path.join(PACKAGE, "beauty", SHOWCASE[angle] + ".mov")
            _run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(src, angle + tag + "_base.png"), "-i", beauty,
                  "-filter_complex", "[0][1]overlay,scale=480:-2", "-frames:v", "1",
                  os.path.join(src, angle + tag + "_composite_480.png")])


def promote(names, angles, tag):
    """Make a reviewed variant the plate: copy its stills and report over the untagged names (then run encode)."""
    for name in names:
        src = os.path.join(PROBE, name)
        for angle in angles:
            for suffix in ("_base.png", "_glow.png", ".json"):
                shutil.copyfile(os.path.join(src, angle + tag + suffix), os.path.join(src, angle + suffix))
            print("promoted", name, angle, tag)


def manifest():
    """Set the Manifest's `backdrops` from the plates on disk: one entry per biome that has a plate for every Angle,
    in BIOMES order. Other keys stay as they are. build_robot.py rewrites manifest.json without it: run this after."""
    path = os.path.join(PACKAGE, "manifest.json")
    with open(path) as f:
        m = json.load(f)
    angles = [a["id"] for a in m["angles"]]
    m["backdrops"] = [{"id": name, "frames": LOOP_FRAMES,
                       "angles": {a: "backdrop/%s/%s.mov" % (name, a) for a in angles}}
                      for name in BIOMES
                      if all(os.path.isfile(os.path.join(PACKAGE, "backdrop", name, a + ".mov")) for a in angles)]
    with open(path, "w") as f:
        json.dump(m, f, indent=1)
        f.write("\n")
    print("backdrops", [b["id"] for b in m["backdrops"]])


def reel():
    """4 s per biome and Angle: the plate with the Angle's showcase Clip over it, in BIOMES then Angle order."""
    parts, inputs = [], []
    for name in BIOMES:
        for angle in _angles():
            inputs += ["-i", os.path.join(PACKAGE, "backdrop", name, angle + ".mov"),
                       "-stream_loop", "-1", "-i", os.path.join(PACKAGE, "beauty", SHOWCASE[angle] + ".mov")]
            i = len(parts)
            parts.append("[%d][%d]overlay=shortest=1,trim=duration=4,setpts=PTS-STARTPTS,scale=1280:720[v%d]"
                         % (2 * i, 2 * i + 1, i))
    graph = ";".join(parts) + ";" + "".join("[v%d]" % i for i in range(len(parts))) + \
        "concat=n=%d:v=1:a=0,format=yuv420p[out]" % len(parts)
    os.makedirs(os.path.dirname(REEL), exist_ok=True)
    _run(["ffmpeg", "-v", "error", "-y"] + inputs + ["-filter_complex", graph, "-map", "[out]",
                                                     "-c:v", "libx264", "-crf", "20", REEL])
    print("reel", REEL)


def main():
    cmd, rest = sys.argv[1], sys.argv[2:]
    opts = {"--angles": _angles(), "--set": [], "--tag": [""]}
    for flag in sorted(opts, key=lambda k: -rest.index(k) if k in rest else 0):   # parse flags from the right
        if flag in rest:
            i = rest.index(flag)
            rest, opts[flag] = rest[:i], rest[i + 1:]
    angles, tag = opts["--angles"], opts["--tag"][0]
    sets = {k: json.loads(v) for k, v in (s.split("=", 1) for s in opts["--set"])}
    names = rest or list(BIOMES)
    {"render": lambda: render(names, angles, sets, tag), "encode": lambda: encode(names, angles),
     "preview": lambda: preview(names, angles, tag), "promote": lambda: promote(names, angles, tag),
     "manifest": manifest, "reel": reel}[cmd]()


main()
