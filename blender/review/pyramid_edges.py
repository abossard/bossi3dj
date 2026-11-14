"""Live variants of the pyramids' neon edges (the Wireframe node in the Pyramid material), for flicker.py cases.
In the live planet Blender: DN["pe_variant"] = {"size": px, "beat": 0..1, "edges": 0..1, "stripes": 0..1}; exec this
file. "stripes" scales the count of the body's bands (26 per height; 0: none). Values not given go back to the build's
(size 2.5, edges 1, stripes 1; the build has no beat on the edges since round 16, so "beat" acts on the capstone only). The material is the build's again on the next rebuild.
Several variants, each measured with flicker.py's cases:
    DN["pe_runs"] = {"out": "/abs/dir", "variants": {name: variant}, "job": fl_job without "out"}; exec this file;
    wait for DN["pe_done"]; one <dir>/<name>.json per variant; the build's edges after.
Frames of each variant at each shot (full size Syphon grabs, camera stopped there):
    DN["pe_grab"] = {"out": "/abs/dir", "shots": {name: {vj_key: value}}, "variants": {name: variant}, "settle": 12};
    exec this file; wait for DN["pe_done"]; <dir>/<shot>_<variant>.png.
"""
import os

import bpy

DN = bpy.app.driver_namespace
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else DN["pe_here"]
nt = bpy.data.materials["Pyramid"].node_tree
def apply(V):
    wf = next(n for n in nt.nodes if n.type == "WIREFRAME")
    wf.inputs["Size"].default_value = V.get("size", 2.5)


    def beat_mul(k):
        """The MULTIPLY node that scales rt_beat by k (7: the edges, 4: the capstone)."""
        for n in nt.nodes:
            if n.type == "MATH" and n.operation == "MULTIPLY":
                a = n.inputs[0]
                if a.is_linked and a.links[0].from_node.type == "ATTRIBUTE" and a.links[0].from_node.attribute_name == "rt_beat":
                    if abs(n.get("pe_k", n.inputs[1].default_value) - k) < 1e-4:
                        n["pe_k"] = k
                        return n
        raise LookupError(k)


    for k in (7.0, 4.0):
        try:
            beat_mul(k).inputs[1].default_value = k * V.get("beat", 1.0)
        except LookupError:         # 7: gone from the build in round 16
            pass
    band = next(n for n in nt.nodes if n.type == "MATH" and n.operation == "MULTIPLY" and n.outputs[0].links
                and n.outputs[0].links[0].to_node.type == "MATH" and n.outputs[0].links[0].to_node.operation == "FRACT")
    band.inputs[1].default_value = 26.0 * V.get("stripes", 1.0)
    # edges off: the Wireframe's factor into its mix scaled to 0
    mul = next((n for n in nt.nodes if n.label == "pe_scale"), None)
    if V.get("edges", 1.0) != 1.0 or mul is not None:
        if mul is None:
            mix = wf.outputs[0].links[0].to_node
            mul = nt.nodes.new("ShaderNodeMath")
            mul.label = "pe_scale"
            mul.operation = "MULTIPLY"
            nt.links.new(wf.outputs[0], mul.inputs[0])
            nt.links.new(mul.outputs[0], mix.inputs[0])
        mul.inputs[1].default_value = V.get("edges", 1.0)


def runs():
    R = DN.pop("pe_runs")
    DN["pe_done"] = False
    try:
        for name, v in R["variants"].items():
            apply(v)
            job = dict(R["job"])
            job["out"] = os.path.join(R["out"], name + ".json")
            DN["fl_job"] = job
            exec(compile(open(os.path.join(HERE, "flicker.py")).read(), "flicker.py", "exec"), {"__name__": "flicker"})
            yield 1.0
            while not DN.get("fl_done"):
                yield 1.0
    finally:
        apply({})
        DN["pe_done"] = True


def grabs():
    import time
    import numpy as np
    J = DN.pop("pe_grab")
    DN["pe_done"] = False
    BR = DN["vj_osc_bridge"]
    S = bpy.context.scene
    tick_h = next(h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "synthwave_tick")
    defaults = {k: v for k, v in tick_h.__globals__["DEFAULTS"].items() if k in S}
    hold0 = set(BR.hold)
    st = {"want": False, "img": None, "last": -1}

    def draw():
        sy = DN.get("syphon_out")
        if not st["want"] or sy is None or sy.offscreen is None or sy.frames == st["last"]:
            return
        st["last"] = sy.frames
        a = np.asarray(sy.offscreen.texture_color.read())
        st["img"] = a if a.dtype != np.uint8 else a.astype(np.float32) / 255.0
        st["want"] = False

    handle = bpy.types.SpaceView3D.draw_handler_add(draw, (), "WINDOW", "POST_PIXEL")

    def wait(s_):
        t = time.perf_counter()
        while time.perf_counter() - t < s_:
            yield 0.1
    try:
        BR.hold = {k for k in S.keys() if k.startswith("vj_")}
        for shot, vals in J["shots"].items():
            v = dict(defaults)
            v.update(vals)
            BR.apply({"/" + k.replace("_", "/", 1): [float(x)] for k, x in v.items()}, "pyramid_edges")
            yield from wait(J.get("settle", 12.0))
            BR.apply({"/vj/cam_speed": [0.0]}, "pyramid_edges")
            yield from wait(1.0)
            for name, var in J["variants"].items():
                apply(var)
                yield from wait(1.0)
                st["want"], st["img"] = True, None
                while st["img"] is None:
                    yield 0.02
                h, w = st["img"].shape[:2]
                im = bpy.data.images.new("pe_tmp", w, h, alpha=True)
                px = np.array(st["img"], np.float32)
                px[..., 3] = 1.0
                im.pixels.foreach_set(px.ravel())
                im.filepath_raw, im.file_format = os.path.join(J["out"], "%s_%s.png" % (shot, name)), "PNG"
                im.save()
                bpy.data.images.remove(im)
    finally:
        apply({})
        BR.hold = set()
        BR.apply({"/" + k.replace("_", "/", 1): [float(x)] for k, x in defaults.items()}, "pyramid_edges")
        BR.hold = hold0
        bpy.types.SpaceView3D.draw_handler_remove(handle, "WINDOW")
        DN["pe_done"] = True


if "pe_runs" in DN or "pe_grab" in DN:
    gen = runs() if "pe_runs" in DN else grabs()

    def tick():
        try:
            return next(gen)
        except StopIteration:
            return None
    bpy.app.timers.register(tick, first_interval=0.1)
else:
    apply(DN.get("pe_variant", {}))
