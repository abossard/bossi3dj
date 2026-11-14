"""Scene health for the live Blender, as one dict. Run it before every grab, fps reading or save.

Through the Blender MCP:  exec(open(bpy.path.abspath("//../review/health.py")).read())
The dict lands in `result` and in driver_namespace["health"]. `problems` lists what would spoil
a grab or a save; an empty list means the scene is ready.
"""
import os

import bpy

DN = bpy.app.driver_namespace
S = bpy.context.scene


def views():
    out = []
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                space = area.spaces.active
                out.append({"perspective": space.region_3d.view_perspective, "shading": space.shading.type,
                            "size": [area.width, area.height]})
    return out


def off_default():
    """vj_* properties that differ from their default: saving now would bake them into the .blend."""
    out = {}
    for key in S.keys():
        if not key.startswith("vj_") or not isinstance(S[key], (int, float)):
            continue
        default = S.id_properties_ui(key).as_dict().get("default")
        if default is not None and abs(float(S[key]) - float(default)) > 1e-6:
            out[key] = [round(float(S[key]), 4), default]
    return out


def long_drivers(limit=250):
    """Driver expressions near Blender's 256-character cut, which truncates silently."""
    out = []
    for coll in (bpy.data.objects, bpy.data.materials, bpy.data.node_groups, bpy.data.worlds, bpy.data.scenes):
        for block in coll:
            anim = getattr(block, "animation_data", None)
            for fc in (anim.drivers if anim else ()):
                if len(fc.driver.expression) >= limit:
                    out.append([block.name, fc.data_path, len(fc.driver.expression)])
    return out


def stale_texts():
    """Embedded text blocks whose text differs from the file they stand for (Blender runs the stored copy, not the file).
    A block without a path stands for the file of its name next to the .blend or in planet_proto/."""
    out = []
    for tx in bpy.data.texts:
        candidates = [bpy.path.abspath(tx.filepath)] if tx.filepath else [bpy.path.abspath(p + tx.name) for p in ("//", "//planet_proto/")]
        path = next((c for c in candidates if os.path.exists(c)), None)
        if path is None:
            continue
        with open(path) as f:
            if f.read().rstrip("\n") != tx.as_string().rstrip("\n"):
                out.append(tx.name)
    return out


def terrain():
    """The GPU terrain on a planet scene: its land and water grids shown, its height map loaded (None elsewhere)."""
    if S.objects.get("Planet_Hydro") is None:
        return None
    land, water, img = S.objects.get("GT_Land"), S.objects.get("GT_Water"), bpy.data.images.get("GT_Map")
    shown = all(o is not None and not o.hide_viewport for o in (land, water)) and img is not None and img.has_data
    return {"shown": bool(shown), "map": list(img.size) if img is not None else None}


def health():
    bridge, sender = DN.get("vj_osc_bridge"), DN.get("syphon_out")
    h = {
        "file": bpy.data.filepath, "blender": bpy.app.version_string, "dirty": bpy.data.is_dirty,
        "autoexec_failed": bool(bpy.app.autoexec_fail),
        "camera": S.camera.name if S.camera else None,
        "playing": bool(bpy.context.screen and bpy.context.screen.is_animation_playing),
        "border": S.render.use_border,
        "views": views(),
        "tick_handlers": [f.__name__ for f in bpy.app.handlers.frame_change_pre],
        "osc": None if bridge is None else {"port": bridge.port, "received": bridge.received,
                                           "applied": bridge.applied, "hold": sorted(bridge.hold)},
        "syphon": None if sender is None else {"frames": sender.frames, "failed": sender.failed},
        "off_default": off_default(),
        "long_drivers": long_drivers(),
        "stale_texts": stale_texts(),
        "terrain": terrain(),
    }
    p = []
    if not any(v["perspective"] == "CAMERA" for v in h["views"]):
        p.append("no 3D view is in camera view: Syphon publishes nothing and grabs are stale")
    if any(v["shading"] != "RENDERED" for v in h["views"] if v["perspective"] == "CAMERA"):
        p.append("camera view is not in Rendered shading")
    if "synthwave_tick" not in h["tick_handlers"]:
        p.append("runtime is not running (open with --enable-autoexec, see `make blender-open`)")
    if h["tick_handlers"].count("synthwave_tick") > 1:
        p.append("runtime registered more than once: stale handlers after a rebuild")
    if h["osc"] is None:
        p.append("OSC bridge is not running")
    elif h["osc"]["hold"]:
        p.append("bridge holds %s: release them before handing Blender on" % ", ".join(h["osc"]["hold"]))
    if h["syphon"] is None:
        p.append("Syphon sender is not running")
    if h["long_drivers"]:
        p.append("driver expressions at the 256-character limit")
    if h["stale_texts"]:
        p.append("embedded text differs from its file (Blender runs the embedded copy): %s" % ", ".join(h["stale_texts"]))
    if h["terrain"] is not None and not h["terrain"]["shown"]:
        p.append("the GPU terrain is not shown (flight_rt did not start it: %s)" % h["terrain"])
    if h["off_default"]:
        p.append("vj_* values differ from defaults: reset before saving the .blend")
    h["problems"] = p
    return h


result = DN["health"] = health()
