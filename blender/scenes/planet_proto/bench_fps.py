"""Playback fps of a scene's cameras in a GUI Blender, camera view, rendered shading.

Run it in its own Blender, never in the live show instance; -Y keeps the scene's own
runtime (OSC bridge, Syphon, web page) from starting:

    blender --factory-startup -Y --window-geometry X Y W H FILE.blend --python bench_fps.py -- \
        --out result.json --cases CAM_0,CAM_1:follow,CAM_2 [--seconds 10]

Each case cuts to the camera (CASE:MODE sets the planet camera's "lod" mode), waits for
shader compilation, then plays for --seconds and counts viewport redraws. A frame handler
advances the clocks the shaders read (planet_runtime.tick when the file has it, else the
same clocks here), so moving cameras move as in the show. Writes fps, frame-time
percentiles, region size and the scene's triangle count, then quits.
"""
import json
import math
import sys
import time

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default


OUT = arg("--out", "bench.json")
CASES = [c.split(":") for c in arg("--cases", "CAM_0").split(",")]
SECONDS = float(arg("--seconds", "10"))
S = bpy.context.scene
state = {"draws": [], "case": 0, "phase": "setup", "t0": 0.0, "results": [], "last": None}


def clock(scene, depsgraph=None):
    now = time.perf_counter()
    dt = 0.0 if state["last"] is None else min(max(now - state["last"], 0.0), 0.1)
    state["last"] = now
    t = scene.get("rt_time", 0.0) + dt
    scene["rt_time"] = t
    scene["rt_grid_phase"] = scene.get("rt_grid_phase", 0.0) + dt * scene.get("vj_grid_speed", 0.6)
    scene["rt_cam_phase"] = scene.get("rt_cam_phase", 0.0) + dt * scene.get("vj_cam_speed", 1.0)
    scene["rt_fog_phase"] = scene.get("rt_fog_phase", 0.0) + dt * scene.get("vj_fog_speed", 10.0)
    scene["rt_beat"] = math.exp(-5.0 * ((t * 124.0 / 60.0) % 1.0)) * 0.45
    scene.update_tag()


runtime = bpy.data.texts.get("planet_runtime.py")
if runtime is not None:
    runtime.as_module()          # installs planet_runtime.tick (rt_space, LOD anchor on cuts; clocks when standalone)
if runtime is None or bpy.data.texts.get("synthwave_runtime.py") is not None:
    bpy.app.handlers.frame_change_pre.append(clock)   # -Y keeps the island runtime off, so its clocks run here


def view3d():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                return win, area, next(r for r in area.regions if r.type == "WINDOW")
    return None, None, None


def on_draw():
    if state["phase"] == "measure":
        state["draws"].append(time.perf_counter())


def setup():
    win, area, region = view3d()
    if area is None:
        return 0.5
    with bpy.context.temp_override(window=win, area=area, region=region):
        bpy.ops.screen.screen_full_area(use_hide_panels=True)
    win, area, region = view3d()
    for w in bpy.context.window_manager.windows:
        w.screen.show_statusbar = False
    sp = area.spaces[0]
    sp.shading.type = "RENDERED"
    sp.shading.use_compositor = "ALWAYS"
    sp.overlay.show_overlays = False
    sp.show_gizmo = False
    sp.clip_start, sp.clip_end = 1.0, 250000.0
    sp.region_3d.view_perspective = "CAMERA"
    with bpy.context.temp_override(window=win, area=area, region=region):
        bpy.ops.view3d.view_center_camera()
    S.render.fps = 120
    S.sync_mode = "FRAME_DROP"
    bpy.types.SpaceView3D.draw_handler_add(on_draw, (), "WINDOW", "POST_PIXEL")
    state["phase"] = "next"
    return 0.5


def scene_tris():
    dg = bpy.context.evaluated_depsgraph_get()
    total, cache = 0, {}
    for inst in dg.object_instances:
        ob = inst.object
        if ob.type != "MESH":
            continue
        key = ob.data.as_pointer()
        if key not in cache:
            ob.data.calc_loop_triangles()
            cache[key] = len(ob.data.loop_triangles)
        total += cache[key]
    return total


def play(on):
    win, area, region = view3d()
    with bpy.context.temp_override(window=win, area=area, region=region):
        if bool(bpy.context.screen.is_animation_playing) != on:
            bpy.ops.screen.animation_play()


def step():
    if state["phase"] == "setup":
        return setup()
    if state["phase"] == "next":
        if state["case"] >= len(CASES):
            with open(OUT, "w") as f:
                json.dump(state["results"], f, indent=1)
            bpy.ops.wm.quit_blender()
            return None
        name, *mode = CASES[state["case"]]
        cam = S.objects[name]
        if mode:
            cam["lod"] = mode[0]
        S.camera = cam
        state["t0"] = time.perf_counter()
        state["phase"] = "warm"
        play(True)          # the cut and the shader compilation happen while playing
        return 1.0
    if state["phase"] == "warm":
        if bpy.app.is_job_running("SHADER_COMPILATION") or time.perf_counter() - state["t0"] < 8.0:
            return 0.5
        state["draws"] = []
        state["phase"] = "measure"
        state["t0"] = time.perf_counter()
        return SECONDS
    if state["phase"] == "measure":
        state["phase"] = "next"
        d = state["draws"]
        dts = sorted((b - a) * 1000.0 for a, b in zip(d, d[1:]))
        pct = lambda p: round(dts[min(int(p * len(dts)), len(dts) - 1)], 1) if dts else None
        win, area, region = view3d()
        name, *mode = CASES[state["case"]]
        state["results"].append({
            "case": ":".join([name, *mode]), "fps": round((len(d) - 1) / (d[-1] - d[0]), 1) if len(d) > 1 else 0.0,
            "frame_ms_p50": pct(0.5), "frame_ms_p95": pct(0.95), "frame_ms_max": round(dts[-1], 1) if dts else None,
            "region": [region.width, region.height], "tris": scene_tris(), "file": bpy.data.filepath})
        play(False)
        state["case"] += 1
        return 1.0


bpy.app.timers.register(step, first_interval=2.0, persistent=True)   # survives "Allow Execution" reloading the file
