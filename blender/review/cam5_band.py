"""CAM_5's pale top band in fog: the top rows (0 to 5 of 540) against rows 8 to 13, per variant, in the live planet.
    DN["band_job"] = {"out": "/abs/band.json"}; exec this file; wait for DN["band_done"].
Variants on CAM_5 by day at /vj/fog 1, hard cut, each grabbed after 4 s: the path running (clocks on), the clocks frozen
(the camera still), and frozen with `volumetric_tile_size` 2 and 8; JOB["variants"] = [(name, frozen, tile, wait s), ...]
replaces that list. The frames are read from the Syphon texture."""
import json
import time

import bpy
import numpy as np

DN = bpy.app.driver_namespace
S = bpy.context.scene
JOB = DN["band_job"]
RT = DN["vj_runtime"]
BR = DN["vj_osc_bridge"]
DN["band_done"] = False
res = []


def frame():
    a = np.asarray(DN["syphon_out"].offscreen.texture_color.read())[:, :, :3].astype(np.float32)
    a = a[::-1] @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    h = a.shape[0] // 540
    return float(a[:6 * h].mean()), float(a[8 * h:14 * h].mean())


def run():
    BR.apply({"/vj/blend": [0.0], "/vj/night": [0.0], "/vj/fog": [1.0], "/vj/cam": [5.0]}, "band")
    yield 5.0
    tile0 = S.eevee.volumetric_tile_size
    variants = JOB.get("variants", [("running", False, tile0, 4.0), ("frozen", True, tile0, 4.0), ("frozen_tile2", True, "2", 4.0),
                                     ("frozen_tile8", True, "8", 4.0)])
    for name, frozen, tile, wait in variants:
        S.eevee.volumetric_tile_size = tile
        t = time.perf_counter()
        while time.perf_counter() - t < wait:
            RT.freeze(frozen)
            yield 0.2
        top, below = frame()
        res.append({"variant": name, "top": round(top, 1), "rows8_13": round(below, 1), "ratio": round(top / max(below, 1e-3), 3)})
    S.eevee.volumetric_tile_size = tile0
    RT.freeze(False)
    BR.apply({"/vj/fog": [S.id_properties_ui("vj_fog").as_dict()["default"]], "/vj/blend": [1.0], "/vj/cam": [0.0]}, "band")
    json.dump(res, open(JOB["out"], "w"))
    DN["band_done"] = True


gen = run()


def tick():
    try:
        return next(gen)
    except StopIteration:
        return None


bpy.app.timers.register(tick, first_interval=0.1)
