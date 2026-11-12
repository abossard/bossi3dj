"""Full-size grabs of the Flight shot per stage, in the live planet Blender with flight_rt started:
    DN["fgrab_job"] = {"out": "/abs/dir", "seed": 1, "stages": ["orbit", "approach", "skim", "hover"]}; exec this file;
    wait for DN["fgrab_done"] (errors in DN["fgrab"]["err"]).
The Flight is reset on `seed` and flies live (clocks running) to each stage as flight_numbers.py does (that stage in
effect for 3 s; the Hover: fe at 1 and within 80 m of its water loop). Then the clocks stop (the pose holds), and it writes the Syphon frame, 1920x1080:
  <stage>_day.ppm         /vj/night 0
  <stage>_night_grid1.ppm /vj/night 1, /vj/grid 1
  <stage>_night_grid0.ppm /vj/night 1, /vj/grid 0
"probe": True adds per stage a ray probe (DN["fgrab"]["probe"]): what each of "grid" (default 9 x 5) points of the view
hits (the fog box and the atmosphere shell skipped), and every surface straight down.
each after `settle` s, then night 0 and the clocks run again. A stage's pose and terrain come from the seed, so a rerun
on the same seed shows the same region and track (the place on the track differs by the frame times)."""
import time

import bpy
import numpy as np

DN = bpy.app.driver_namespace
S = bpy.context.scene
JOB = DN["fgrab_job"]
OUT = JOB["out"].rstrip("/") + "/"
BRIDGE = DN["vj_osc_bridge"]
RT = DN["vj_runtime"]
FRAME = next(h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "frame" and h.__module__ == "flight_rt")
G = FRAME.__globals__
FS, LOD = G["_state"], G["lod_scene"]
FC = next(o for o in S.objects if o.type == "CAMERA" and o.get("vj_flight_cam"))
KEY = {"orbit": (0, 0.0), "approach": (1, 1.0 / 3.0), "skim": (2, 2.0 / 3.0), "hover": (3, 1.0)}
SETTLE, TIMEOUT, HOLD = JOB.get("settle", 3.0), JOB.get("timeout", 150.0), JOB.get("hold", 3.0)
LOOKS = (("day", {"vj_night": 0.0, "vj_grid": 1.0}), ("night_grid1", {"vj_night": 1.0, "vj_grid": 1.0}),
         ("night_grid0", {"vj_night": 1.0, "vj_grid": 0.0}))

old = DN.get("fgrab")
if old and old.get("handle"):
    try:
        bpy.types.SpaceView3D.draw_handler_remove(old["handle"], "WINDOW")
    except Exception:
        pass
st = {"want": None, "log": [], "handle": None, "err": None}
DN["fgrab"] = st
DN["fgrab_done"] = False


def send(**values):
    BRIDGE.hold = BRIDGE.hold | {"vj_cam", "vj_night"}
    BRIDGE.apply({"/" + k.replace("_", "/", 1): [float(v)] for k, v in values.items()}, "web")


def on_draw():
    rd = bpy.context.region_data
    w = st["want"]
    if rd is None or rd.view_perspective != "CAMERA" or w is None or time.perf_counter() < w["due"]:
        return
    st["want"] = None
    a = np.asarray(DN["syphon_out"].offscreen.texture_color.read())
    a = np.ascontiguousarray(a[:, :, :3][::-1])
    with open(w["out"], "wb") as f:
        f.write(b"P6\n%d %d\n255\n" % (a.shape[1], a.shape[0]) + a.tobytes())
    w["ok"] = True


def probe():
    """What fills the frame: a ray through each of 9 x 5 points of the view, the first object hit (the fog box and
    hidden objects skipped) and its distance; the camera's height over the clearance map and its fog props."""
    dg = bpy.context.evaluated_depsgraph_get()
    cam = S.camera
    mw = cam.matrix_world
    o = mw.translation.copy()
    fr = cam.data.view_frame(scene=S)
    nx, ny = JOB.get("grid", (9, 5))
    rows = []
    for j in range(ny):
        row = []
        for i in range(nx):
            x = fr[2].x + (fr[0].x - fr[2].x) * (i + 0.5) / nx
            y = fr[0].y + (fr[2].y - fr[0].y) * (j + 0.5) / ny
            d = (mw.to_3x3() @ type(o)((x, y, fr[0].z))).normalized()
            org, hit = o.copy(), None
            for _ in range(6):
                ok, loc, nrm, idx, ob, _m = S.ray_cast(dg, org, d)
                if not ok:
                    break
                if ob.name in ("Fog", "Atmosphere") or ob.hide_get():
                    org = loc + d * 0.5
                    continue
                me = ob.evaluated_get(dg).data
                mi = me.polygons[idx].material_index if 0 <= idx < len(me.polygons) else -1
                mat = me.materials[mi].name if 0 <= mi < len(me.materials) and me.materials[mi] else "?"
                hit = (ob.name, mat, round((loc - o).length, 1))
                break
            row.append(hit)
        rows.append(row)
    u, h = G["dr"].spherical(tuple(o))
    down = (G["fl"].CENTRE[0] - o.x, G["fl"].CENTRE[1] - o.y, G["fl"].CENTRE[2] - o.z)
    d = type(o)(down).normalized()
    org, column = o.copy(), []           # every surface straight down, to 300 m under the camera
    for _ in range(8):
        ok, loc, nrm, idx, ob, _m = S.ray_cast(dg, org, d, distance=300.0 - (org - o).length)
        if not ok:
            break
        me = ob.evaluated_get(dg).data
        mi = me.polygons[idx].material_index if 0 <= idx < len(me.polygons) else -1
        column.append((ob.name, me.materials[mi].name if 0 <= mi < len(me.materials) and me.materials[mi] else "?",
                       round((loc - o).length, 2), round(nrm.dot(-d), 2)))
        org = loc + d * 0.05
    M = FS["map"]
    return {"rows_top_to_bottom": rows, "agl_map": round(h - M.surface(u), 1), "down": column,
            "map_ground": round(M.ground(u) + 0.0, 2), "map_water": round(M._bilinear(M.w, u), 2), "cam_h": round(h, 2), "cam": cam.name,
            "lens": round(cam.data.lens, 1), "sky_frame": [round(v) for v in S.objects["Sky_Frame"].matrix_world.translation],
            "rig": [round(v) for v in o]}


def defaults():
    """Every /vj/* control back to its wire default (a grab run leaves its last state, /vj/boost 1 after the boost pair)."""
    for k in list(S.keys()):
        if k.startswith("vj_") and k != "vj_cam" and isinstance(S[k], (int, float)):
            d = S.id_properties_ui(k).as_dict().get("default")
            if d is not None:
                S[k] = d


def holes(name, extra=2.0):
    """One more day grab with the material of Sea_Underside (seen only through a hole in the land) swapped for pure
    green emission; then the green pixels counted and, for up to 40 of them, the blocks hit by rays 4 px to each side.
    Result in DN["fgrab"]["holes"][name]."""
    ob = S.objects["Sea_Underside"]
    mod = ob.modifiers[0]           # a GN shell: its material is the modifier's input "Material"
    ident = next(it.identifier for it in mod.node_group.interface.items_tree
                 if getattr(it, "in_out", "") == "INPUT" and it.name == "Material")
    sock = getattr(mod.properties.inputs, ident)
    old = sock.value
    m = bpy.data.materials.get("_hole_green") or bpy.data.materials.new("_hole_green")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    em, out = nt.nodes.new("ShaderNodeEmission"), nt.nodes.new("ShaderNodeOutputMaterial")
    em.inputs["Color"].default_value = (0.0, 1.0, 0.0, 1.0)
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    sock.value = m
    ob.update_tag()
    send(vj_night=0.0, vj_grid=1.0)
    if JOB.get("holes_offscreen"):
        # off the Syphon output: an OpenGL render of the camera view into an image file (Syphon publishes its own texture,
        # the render draws the viewport once; the swap lasts about one frame)
        S.render.filepath = OUT + "%s_holes_gl.png" % name
        S.render.image_settings.file_format = "PNG"
        yield 2.0
        RT.freeze(True)
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                if area.type == "VIEW_3D":
                    with bpy.context.temp_override(window=win, area=area):
                        bpy.ops.render.opengl(write_still=True, view_context=True)
        sock.value = old
        ob.update_tag()
        raw = None
        st.setdefault("holes", {})[name] = {"file": S.render.filepath}
        return
    w = st["want"] = {"due": time.perf_counter() + SETTLE + extra, "out": OUT + "%s_holes.ppm" % name}
    while "ok" not in w:
        RT.freeze(True)
        yield 0.1
    sock.value = old
    ob.update_tag()
    raw = open(w["out"], "rb").read()
    a = np.frombuffer(raw[raw.index(b"255\n") + 4:], np.uint8).reshape(1080, 1920, 3).astype(np.int16)
    green = (a[:, :, 1] > 200) & (a[:, :, 0] < 60) & (a[:, :, 2] < 60)
    ys, xs = np.nonzero(green)
    res = {"pixels": int(green.sum()), "rows_with_holes": int(green.any(axis=1).sum())}
    if len(xs):
        res["bbox"] = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
        dg = bpy.context.evaluated_depsgraph_get()
        cam = S.camera
        mw, fr = cam.matrix_world, cam.data.view_frame(scene=S)
        o = mw.translation.copy()

        def ray(px, py):
            x = fr[2].x + (fr[0].x - fr[2].x) * (px + 0.5) / 1920.0
            y = fr[0].y + (fr[2].y - fr[0].y) * (py + 0.5) / 1080.0
            d = (mw.to_3x3() @ type(o)((x, y, fr[0].z))).normalized()
            org = o.copy()
            for _ in range(6):
                ok, loc, nrm, idx, hit, _m = S.ray_cast(dg, org, d)
                if not ok:
                    return None
                if hit.name in ("Fog", "Atmosphere") or hit.hide_get():
                    org = loc + d * 0.5
                    continue
                return hit.name, round((loc - o).length)
            return None
        sides = []
        for k in np.linspace(0, len(xs) - 1, min(40, len(xs))).astype(int):
            px, py = int(xs[k]), int(ys[k])
            sides.append({"px": [px, py], "at": ray(px, py), "l": ray(px - 4, py), "r": ray(px + 4, py),
                          "u": ray(px, py - 4), "d": ray(px, py + 4)})
        # what is under each hole pixel's ray: the hit's height over the sea and the clearance map's ground and water there
        M = FS["map"]
        below = []
        for sd in sides:
            px, py = sd["px"]
            x = fr[2].x + (fr[0].x - fr[2].x) * (px + 0.5) / 1920.0
            y = fr[0].y + (fr[2].y - fr[0].y) * (py + 0.5) / 1080.0
            d = (mw.to_3x3() @ type(o)((x, y, fr[0].z))).normalized()
            org, hit_loc = o.copy(), None
            for _ in range(6):
                ok, loc, nrm, idx, hit, _m = S.ray_cast(dg, org, d)
                if not ok:
                    break
                if hit.name in ("Fog", "Atmosphere") or hit.hide_get():
                    org = loc + d * 0.5
                    continue
                hit_loc = loc
                break
            if hit_loc is not None:
                u, h_ = G["dr"].spherical(tuple(hit_loc))
                below.append({"px": sd["px"], "h": round(h_, 1), "map_ground": round(M.ground(u), 1), "map_water": round(M._bilinear(M.w, u), 1)})
        res["under_samples"] = below
        res["samples"] = sides
        lod = {}
        for sd in sides:
            for k_ in ("l", "r", "u", "d"):
                h = sd[k_]
                if h and h[0].startswith("LOD.slot"):
                    nodes = next((nd for b, (sob, nd) in LOD._state["shown"].items() if sob.name == h[0]), None)
                    lod[h[0]] = sorted({k[1] for k in nodes}) if nodes else None
        res["slot_depths"] = lod
    st.setdefault("holes", {})[name] = res


def run():
    t0 = time.perf_counter()
    now = lambda: time.perf_counter() - t0
    defaults()
    send(vj_blend=0.0, vj_flight=0.0, vj_night=0.0, vj_grid=1.0)
    G["quiesce"](JOB.get("seed", 1))
    send(vj_cam=float(FC.name[4:]))
    yield 2.0
    for name in JOB.get("stages", list(KEY)):
        k, key = KEY[name]
        send(vj_flight=key)
        t, since = now(), None
        while now() < t + TIMEOUT:
            F = FS.get("flight")
            ok = F is not None and abs(F.f - key) < 2e-3 and int(S.get("rt_flight_stage", -1)) == k and (name != "hover" or (F.fe >= 0.999 and F.gap < 80.0))
            since = (since or now()) if ok else None
            if since is not None and now() - since >= HOLD:
                break
            yield 0.1
        F = FS["flight"]
        RT.freeze(True)
        for look, values in LOOKS:
            send(**values)
            w = st["want"] = {"due": time.perf_counter() + SETTLE, "out": OUT + "%s_%s.ppm" % (name, look)}
            while "ok" not in w:
                RT.freeze(True)
                yield 0.1
            st["log"].append({"out": w["out"], "stage": int(S.get("rt_flight_stage", -1)), "f": round(F.f, 4), "fe": round(F.fe, 4),
                              "gap": round(F.gap, 1), "live": bool(LOD.live()), "near_missing": len(LOD._state.get("near_missing") or ()),
                              "reached": since is not None, "t": round(now(), 1)})
        if JOB.get("holes"):        # the backdrop under sea level painted pure green: what shows through the land
            yield from holes(name)
        if JOB.get("holes_nomorph"):     # the same with the stream's morph displacement off (Scale 0)
            vds = [n for m in LOD._state["mats"].values() for n in m.node_tree.nodes if n.type == "VECTOR_DISPLACEMENT"]
            for n in vds:
                n.inputs["Scale"].default_value = 0.0
            yield from holes(name + "_nomorph", 12.0)     # a node value change recompiles the shader
            for n in vds:
                n.inputs["Scale"].default_value = 1.0
        if JOB.get("probe"):
            st.setdefault("probe", {})[name] = probe()
        send(vj_night=0.0, vj_grid=1.0)
        RT.freeze(False)
    send(vj_flight=0.0, vj_blend=1.0, vj_cam=0.0)
    BRIDGE.hold = BRIDGE.hold - {"vj_cam", "vj_night"}


gen = run()


def tick():
    try:
        return next(gen)
    except StopIteration:
        pass
    except Exception:
        import traceback
        st["err"] = traceback.format_exc()
        RT.freeze(False)
    bpy.types.SpaceView3D.draw_handler_remove(st["handle"], "WINDOW")
    st["handle"] = None
    DN["fgrab_done"] = True
    return None


st["handle"] = bpy.types.SpaceView3D.draw_handler_add(on_draw, (), "WINDOW", "POST_PIXEL")
bpy.app.timers.register(tick, first_interval=0.1)
