"""Feature self-check of the scene, started from the control page (synthwave_web.py) or `make blender-check`.

For every vj_* control the page exposes: reset to defaults, freeze the clocks, set the control to min, default and
max (triggers: fire it), wait until the frame has settled and compare it with a baseline frame by pixels. The
frame is the Syphon preview (640x360, read back by syphon_out.py while a check asks for it). A control has an
effect when one of three numbers clears the noise floor: the mean absolute difference (0..255), the share of
changed pixels, or the mean signed difference per channel (a few stars add up to a bias the noise does not have).
The floor is the largest difference among REPLICATES untouched baselines, and the default cell. The applied value
is read back too.

The viewport keeps playing while the check runs: the picture is the average of AVERAGE frames, because the viewport's own
jitter and dither change every frame, and the clocks are frozen by the runtime (dt 0) except where a control needs time.

Nothing runs while no check runs: one bpy.app.timers callback exists from start() to the end of the check.
The end (done, aborted, failed) always restores the defaults, releases the holds this check took, puts the
beat simulator back and lets the clocks run.

PRECONDITIONS is the one table of states a control needs before it shows: the values to set, the cameras to
look through, clock time to step after the change. A control without a row runs on CAM_0 with defaults. A
control with no effect on its cameras is tried on the other cameras too, so a wrong camera never reads as dead.
"""
import json
import os
import struct
import time
import traceback
import zlib

import bpy
import numpy as np

PREFIX = "vj_"
TICK = 0.05             # s between steps of the check
MIN_FRAMES = 3          # preview frames to wait after any change
AVERAGE = 8             # frames averaged into one measurement: the viewport's own jitter (TAA, dither) changes every frame
SETTLE_EPS = 0.5        # mean abs diff (0..255) between the first and the second half of the averaged frames, or twice
                        # the noise floor when that is larger, below which the picture stands still
SETTLE_TIMEOUT = 8.0    # s before the average is taken as it is (noted as unsettled)
NO_FRAME_TIMEOUT = 12.0  # s without any new preview frame: the check cannot measure anything
CHANGED = 8             # a pixel counts as changed when a channel moves by more than this (of 255)
MAD_MIN, FRAC_MIN, BIAS_MIN = 0.05, 5e-4, 0.02    # smallest effect that counts, whatever the noise floor
NOISE_FACTOR = 2.0      # an effect clears the noise floor by this factor
RATIO_EPS = (0.01, 1e-4, 0.002)    # noise floor used for the ratio when it is zero (mad, frac, bias)
STRONG = 10.0           # x noise floor from which an effect needs no second look, and no other camera
REPLICATES = 3          # untouched baselines per camera and state, for the noise floor
PREVIEW_W, PREVIEW_H = 640, 360
BMP_HEADER = 54
PREVIEW_KEY, PREVIEW_WANTED = "syphon_preview", "syphon_preview_wanted"
SENDER_KEY, BRIDGE_KEY, RUNTIME_KEY = "syphon_out", "vj_osc_bridge", "vj_runtime"
FALLBACK = True         # look through the other cameras when the listed ones show no effect

# key -> what the control needs before it shows. Keys of a row:
#   set      values held while the control varies
#   cams     cameras to look through first (default: 0); "flight" is the Flight's shot
#   advance  s of clock time stepped after the change (speeds, triggers, anything that moves)
#   then     values set after the first settle (a cut for /vj/blend), before the advance
#   why      one line for the report
#   probe    scene properties the runtime writes when it has taken a trigger (any non-zero after the advance)
#   reads    what reads the control besides its own Attribute nodes and drivers: "rt_..." clocks the runtime derives
#            from it (counted like the control), "py:module.function" for Python readers (named in the report)
PRECONDITIONS = {
    "vj_nebula": {"set": {"vj_night": 1.0}, "cams": [10], "why": "the nebula is part of the night sky"},
    "vj_stars": {"set": {"vj_night": 1.0}, "why": "stars show at night"},
    "vj_moon": {"set": {"vj_night": 1.0}, "cams": [4], "why": "the moon is up at night"},
    "vj_moon_phase": {"set": {"vj_night": 1.0}, "cams": [3], "reads": ["py:star_system.sync"], "why": "the moon is up at night"},
    "vj_eclipse": {"set": {"vj_night": 1.0, "vj_moon_phase": 1.0}, "cams": [3], "reads": ["py:star_system.sync"],
                   "why": "lunar eclipse needs a full moon at night"},
    "vj_meteor": {"set": {"vj_night": 1.0}, "advance": 0.4, "reads": ["py:synthwave_runtime.meteors"], "probe": ["rt_met0_a", "rt_met1_a", "rt_met2_a"],
                  "why": "a shooting star is brightest at night and lasts about a second"},
    "vj_shock": {"cams": [2], "advance": 1.0, "reads": ["py:synthwave_runtime.shockwave"], "probe": ["rt_shock0_a", "rt_shock1_a", "rt_shock2_a", "rt_shock3_a"],
                 "why": "the wave needs a second to leave the pyramid"},
    "vj_grid": {"set": {"vj_night": 1.0}, "why": "planet: real mesh edges show from sunset, full at night, none by day"},
    "vj_bass": {"set": {"vj_night": 1.0}, "why": "planet: pulses the real mesh edges, which show only at night"},
    "vj_grid_speed": {"set": {"vj_night": 1.0}, "advance": 1.0,
                      "why": "island only: its night grid scrolls; the planet has no scrolling lines, no effect there is right"},
    "vj_cam_speed": {"cams": [4], "advance": 1.0, "reads": ["rt_cam_phase"], "why": "only shots on a path move with it"},
    "vj_fog_speed": {"set": {"vj_fog": 0.8}, "advance": 1.0, "reads": ["rt_fog_phase"], "why": "wind moves the fog bank"},
    "vj_star_speed": {"set": {"vj_night": 1.0}, "advance": 2.0, "reads": ["py:star_system.sync"], "why": "the stars drift against the sun"},
    "vj_flamingos": {"cams": [7], "why": "planet: a flock needs water in view: CAM_0 shows none, CAM_1's flock is too small at preview size (0.01 % of the pixels), CAM_7 shows it"},
    "vj_water": {"cams": [1], "why": "the sea shows from the low river shot"},
    "vj_fog_height": {"set": {"vj_fog": 0.7}, "why": "needs a fog bank"},
    "vj_fog_glow": {"set": {"vj_fog": 1.0, "vj_night": 0.5}, "why": "self-glow of a dense fog bank shows at dusk"},
    "vj_fog_hue": {"set": {"vj_fog": 1.0, "vj_night": 0.5}, "why": "tints a dense fog bank, most at dusk"},
    "vj_fog_noise": {"set": {"vj_fog": 0.7}, "why": "needs a fog bank"},
    "vj_fog_scale": {"set": {"vj_fog": 0.7}, "why": "needs a fog bank"},
    "vj_fog_beat": {"set": {"vj_fog": 0.7, "vj_beat": 1.0}, "why": "the fog pumps with the beat"},
    "vj_blend": {"set": {"vj_cam": 1.0}, "cams": [1], "then": {"vj_cam": 4.0}, "advance": 0.3, "reads": ["py:flight_rt.frame"],
                 "why": "shows on a cut, a moment after it"},
    "vj_boost": {"set": {"vj_flight": 0.66}, "cams": ["flight"], "advance": 2.0, "reads": ["py:flight_rt.frame"],
                 "why": "the accelerator works while the Flight skims or hovers"},
    "vj_flight": {"cams": ["flight"], "advance": 2.0, "reads": ["py:flight_rt.frame"],
                  "why": "a cell starts the Flight settled at the stage (flight_rt.quiesce); verify_flight checks the damping"},
    "vj_energy": {"advance": 2.0, "reads": ["py:flight_rt.frame"], "why": "every shot moves harder, eased over seconds"},
    "vj_hit": {"advance": 0.5, "reads": ["py:flight_rt.frame"], "why": "a wide-angle kick on the On-Air Camera"},
}


class Abort(Exception):
    pass


class Fatal(Exception):
    """The check cannot measure anything (no frames); the rows so far stay."""


def write_png(path, rgb):
    h, w, _ = rgb.shape
    raw = b"".join(b"\x00" + rgb[y].tobytes() for y in range(h))

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def diff(a, b):
    """(mean abs difference 0..255, share of pixels with a channel moved by more than CHANGED,
    largest mean signed difference of a channel)."""
    d = a.astype(np.float32) - b.astype(np.float32)
    return float(np.abs(d).mean()), float((np.abs(d).max(axis=2) > CHANGED).mean()), float(np.abs(d.mean(axis=(0, 1))).max())


def clears(stat, floor):
    return any(v >= max(lo, NOISE_FACTOR * f) for v, lo, f in zip(stat, (MAD_MIN, FRAC_MIN, BIAS_MIN), floor))


def ratio(stat, floor):
    return max(v / max(f, e) for v, f, e in zip(stat, floor, RATIO_EPS))


def widest(*stats):
    return tuple(max(col) for col in zip(*stats))


def readers(keys):
    """How many Attribute nodes and drivers read each property, from the scene data (Python readers are not counted)."""
    out = {k: {"nodes": 0, "drivers": 0} for k in keys}

    def trees():
        for coll in (bpy.data.node_groups, bpy.data.materials, bpy.data.worlds):
            for block in coll:
                tree = getattr(block, "node_tree", None) or (block if block.rna_type.identifier.endswith("Tree") else None)
                if tree is not None:
                    yield tree

    for tree in trees():
        for node in tree.nodes:
            if node.bl_idname == "ShaderNodeAttribute":
                name = node.attribute_name.strip("[]\"' ")
                if name in out:
                    out[name]["nodes"] += 1
    owners = [b for coll in (bpy.data.objects, bpy.data.cameras, bpy.data.lights, bpy.data.meshes, bpy.data.scenes,
                             bpy.data.materials, bpy.data.worlds, bpy.data.node_groups) for b in coll]
    owners += [t for t in trees()]
    for block in owners:
        ad = getattr(block, "animation_data", None)
        for fc in (ad.drivers if ad else ()):
            d = fc.driver
            text = d.expression + " " + " ".join(t.data_path + t.id.name if t.id else t.data_path
                                                  for v in d.variables for t in v.targets)
            for k in keys:
                if k in text:
                    out[k]["drivers"] += 1
    return out


class Check:
    def __init__(self, web, controls_fn, opts=None):
        self.web, self.controls_fn, self.opts = web, controls_fn, opts or {}
        self.ns = bpy.app.driver_namespace
        self.scene = bpy.context.scene
        self.runtime = self.ns.get(RUNTIME_KEY)
        self.bridge = self.ns.get(BRIDGE_KEY)
        self.abort_flag = False
        self.baselines = {}       # (cam, set, advance, then) -> (frame, floor)
        self.noise = (0.0, 0.0, 0.0)   # largest floor measured so far
        self.restore = None
        self.frames_dir = self.opts.get("frames_dir")
        self.result = {"state": "idle", "scene": self.scene.name, "rows": [], "progress": {"done": 0, "total": 0, "current": None}}
        self.gen = None
        self.registered = False
        self.public = "{}"        # JSON of the result, rebuilt on the main thread for the HTTP thread to serve

    # ---- lifecycle -------------------------------------------------------------------------------------------

    def start(self):
        self.result.update(state="running", started=time.time(), error=None)
        self.publish()
        self.gen = self.procedure()
        bpy.app.timers.register(self.step, first_interval=TICK)
        self.registered = True

    def step(self):
        try:
            if self.abort_flag:
                raise Abort()
            self.keep_alive()
            next(self.gen)
            return TICK
        except StopIteration:
            self.finish("done")
        except Abort:
            self.finish("aborted")
        except Fatal as e:
            self.finish("failed", str(e))
        except Exception:
            self.finish("failed", traceback.format_exc())
        return None

    def abort(self):
        self.abort_flag = True

    def keep_alive(self):
        self.ns[PREVIEW_WANTED] = time.time()
        self.runtime.freeze(True)


    def begin(self):
        scene, bridge = self.scene, self.bridge
        if self.runtime is None or bridge is None:
            raise Fatal("the runtime or the OSC bridge is not running (driver_namespace has no vj_runtime or vj_osc_bridge)")
        web = self.web
        self.restore = {"hold": set(bridge.hold), "sim": web.sim.on}
        web.sim.on = False
        self.controls = self.controls_fn(scene)
        self.by_key = {c["key"]: c for c in self.controls}
        self.defaults = {c["key"]: c["default"] for c in self.controls}
        bridge.hold = bridge.hold | set(self.by_key)
        self.keep_alive()
        self.runtime.quiesce()
        self.apply(self.defaults)
        self.clock0 = {k: scene[k] for k in self.runtime.CLOCKS if k in scene}

    def finish(self, state, error=None):
        """Always: defaults back, holds released, simulator and clocks as before. Safe to call twice."""
        if self.restore is not None:
            try:
                self.apply(self.defaults)
                self.bridge.hold = self.restore["hold"]
                self.web.sim.on = self.restore["sim"]
                self.runtime.freeze(False)
                self.runtime.quiesce()
                bad = {k: [float(self.scene[k]), v] for k, v in self.defaults.items()
                       if k in self.scene and abs(float(self.scene[k]) - v) > 1e-6 and k != "vj_cam"}
                self.result["defaults_restored"] = not bad
                self.result["off_default"] = bad
            except Exception:
                error = (error or "") + "\nrestore failed:\n" + traceback.format_exc()
            self.restore = None
        self.ns.pop(PREVIEW_WANTED, None)
        self.result["state"] = state
        self.result["error"] = error
        self.result["finished"] = time.time()
        self.result["counts"] = self.counts()
        self.registered = False
        self.publish()

    def publish(self):
        self.public = json.dumps(self.result)

    def counts(self):
        out = {}
        for r in self.result["rows"]:
            out[r["verdict"]] = out.get(r["verdict"], 0) + 1
        return out

    # ---- primitives (generators wait with `yield`) ------------------------------------------------------------

    def apply(self, values):
        self.web.apply(self.scene, self.bridge, {k: float(v) for k, v in values.items()}, "check")

    def previews(self):
        s = self.ns.get(SENDER_KEY)
        return s.previews if s is not None else 0

    def frame(self):
        bmp = self.ns.get(PREVIEW_KEY)
        if not bmp or len(bmp) != BMP_HEADER + PREVIEW_W * PREVIEW_H * 3:
            return None
        return np.frombuffer(bmp, np.uint8, offset=BMP_HEADER).reshape(PREVIEW_H, PREVIEW_W, 3)

    def wait_frames(self, n):
        n0, t0 = self.previews(), time.time()
        while self.previews() < n0 + n:
            if time.time() - t0 > NO_FRAME_TIMEOUT:
                raise Fatal("no new preview frame in %.0f s: is the 3D view in camera view and Syphon running?" % NO_FRAME_TIMEOUT)
            yield

    def settle(self):
        """Waits MIN_FRAMES new frames, then averages AVERAGE frames; takes another set while the average still moves.
        Returns (average frame as float32, settled)."""
        yield from self.wait_frames(MIN_FRAMES)
        prev, t0, eps = None, time.time(), max(SETTLE_EPS, 2.0 * self.noise[0])
        while True:
            batch = []
            while len(batch) < AVERAGE:
                yield from self.wait_frames(1)
                f = self.frame()
                if f is not None:
                    batch.append(f.astype(np.float32))
            cur = sum(batch) / len(batch)
            if prev is not None and diff(prev, cur)[0] <= eps:
                return cur, True
            prev = cur
            if time.time() - t0 > SETTLE_TIMEOUT:
                return cur, False

    def step_clocks(self, seconds):
        self.runtime.advance(seconds)
        t0 = time.time()
        while self.runtime.steps_left() > 0:
            if time.time() - t0 > NO_FRAME_TIMEOUT + seconds * 20:
                raise Fatal("the clocks did not step: no frame changes (is playback running?)")
            yield

    # ---- one measurement -----------------------------------------------------------------------------------------

    def state_for(self, pre, cam):
        state = dict(self.defaults)
        state.update(pre.get("set", {}))
        state["vj_cam"] = float(cam)
        return state

    def cell(self, key, value, pre, cam, fire=False):
        """Resets the clocks and events, sets the state, the control to `value` (None: untouched), steps the
        clocks, settles. Returns (frame, readback_ok, settled, probe)."""
        scene = self.scene
        self.runtime.quiesce()
        for k, v in self.clock0.items():
            scene[k] = v
        for k, c in self.by_key.items():      # a trigger the bridge still holds high would fire again as a new edge
            if c["trigger"]:
                scene[k] = 0.0
        self.bridge.pending.clear()
        state = self.state_for(pre, cam)
        readback = True
        if key is not None and not fire:
            state[key] = value
        self.apply(state)
        if fire:
            yield from self.wait_frames(2)
            self.apply({key: value})
            yield from self.wait_frames(2)
            readback = float(scene[key]) >= 0.5      # the bridge holds the edge high until a frame has seen it
            scene[key] = 0.0
            self.bridge.pending.clear()
        else:
            yield from self.wait_frames(1)
            if key == "vj_cam":
                shot = self.ns["vj_shot"]() if "vj_shot" in self.ns else scene.camera and scene.camera.name     # flight_rt
                readback = shot == "CAM_%d" % int(round(value))
            elif key is not None:
                readback = abs(float(scene[key]) - value) <= 1e-6 * max(1.0, abs(value))
        if pre.get("then"):
            yield from self.settle()
            self.apply(pre["then"])
        if pre.get("advance"):
            yield from self.step_clocks(pre["advance"])
        probe = any(abs(float(scene.get(n, 0.0))) > 0.0 for n in pre.get("probe", ())) if fire and pre.get("probe") else None
        frame, settled = yield from self.settle()
        return frame, readback, settled, probe

    @staticmethod
    def signature(pre, cam):
        return (cam, tuple(sorted(pre.get("set", {}).items())), pre.get("advance", 0.0), tuple(sorted(pre.get("then", {}).items())))

    def baseline(self, pre, cam):
        sig = self.signature(pre, cam)
        hit = self.baselines.get(sig)
        if hit is not None:
            return hit
        frames = []
        for _ in range(REPLICATES):
            f = (yield from self.cell(None, None, pre, cam))[0]
            frames.append(f)
        floor = widest(*[diff(frames[i], frames[j]) for i in range(REPLICATES) for j in range(i)])
        self.noise = widest(self.noise, floor)
        self.baselines[sig] = (frames[0], floor)
        return frames[0], floor

    def values_for(self, c):
        lo, hi, d = c["min"], c["max"], c["default"]
        if c["key"] == "vj_cam":
            return [float(v) for v in range(int(lo), int(hi) + 1)]
        if c["trigger"]:
            return sorted({min(max(v, lo), hi) for v in (0.5, 1.0, hi) if v >= 0.5})
        return list(dict.fromkeys([lo, d, (lo + hi) / 2.0, hi]))    # the middle too: hue 0 and hue 1 are the same colour

    def attempt(self, c, pre, cam, primary):
        key, trig = c["key"], c["trigger"]
        base, floor = yield from self.baseline(pre, cam)
        cells, frames = [], {"base": base}
        values = self.values_for(c)
        if not primary and key != "vj_cam" and not trig:
            values = [values[0], values[-1]]       # other cameras: the two ends only
        for v in values:
            frame, ok, settled, probe = yield from self.cell(key, v, pre, cam, fire=trig)
            stat = diff(frame, base)
            cells.append({"value": v, "mad": round(stat[0], 4), "frac": round(stat[1], 6), "bias": round(stat[2], 4),
                          "readback": ok, "settled": settled, "probe": probe})
            if v in (values[0], values[-1]):
                frames["min" if v == values[0] else "max"] = frame
        for x in cells:     # the default cell is the baseline state again: how far it lands is noise too
            if x["value"] == c["default"] and not trig:
                floor = widest(floor, (x["mad"], x["frac"], x["bias"]))
        for x in cells:
            x["effect"] = clears((x["mad"], x["frac"], x["bias"]), floor)
            x["ratio"] = round(ratio((x["mad"], x["frac"], x["bias"]), floor), 1)
        return {"cam": cam, "cells": cells, "floor": [round(floor[0], 4), round(floor[1], 6), round(floor[2], 4)]}, frames

    def row_for(self, c, attempts, frames, rd, error=None, confirmed=None):
        is_cam = c["key"] == "vj_cam"
        best = self.best(c, attempts) if attempts else None
        pre = PRECONDITIONS.get(c["key"], {})
        row = {"key": c["key"], "address": "/" + c["key"].replace("_", "/", 1), "min": c["min"], "max": c["max"],
               "default": c["default"], "trigger": c["trigger"], "why": pre.get("why", ""), "readers": rd,
               "cams_tried": [a["cam"] for a in attempts], "attempts": attempts}
        notes = []
        if error:
            row["verdict"] = "error"
            notes.append(error)
        else:
            judged = self.judged(c, best)
            if is_cam:      # the default cell is a cut like any other: every camera has to show
                bad_cam = [x["value"] for x in best["cells"] if not x["readback"]]
                still = [x["value"] for x in best["cells"] if x["value"] != 0.0 and not x["effect"]]
                row["verdict"] = "error" if bad_cam else "effect"
                if bad_cam:
                    notes.append("no camera cut for vj_cam %s" % bad_cam)
                if still:
                    notes.append("looks like CAM_0 at vj_cam %s" % still)
            else:
                bad = [x["value"] for x in best["cells"] if not x["readback"]]
                row["verdict"] = "error" if bad else ("effect" if self.effective(c, [best]) else "no effect")
                if bad:
                    notes.append("value %s not read back" % bad)
            if row["verdict"] == "effect" and confirmed is False:
                row["verdict"] = "no effect"
                notes.append("a weak or single-cell first effect did not repeat")
            elif confirmed:
                notes.append("weak or single-cell, repeated")
            probes = [x["probe"] for a in attempts for x in a["cells"] if x["probe"] is not None]
            if probes and row["verdict"] == "no effect":
                notes.append("the runtime took the trigger (%s) but no camera tried shows it" % ", ".join(pre["probe"][:1] + ["..."]) if any(probes)
                             else "the runtime never took the trigger (%s stayed 0)" % pre["probe"][0])
            if any(not x["settled"] for x in best["cells"]):
                notes.append("a frame did not settle")
            row["cam"] = best["cam"]
            top = max(judged, key=lambda x: x["ratio"])
            row["effect_mad"], row["effect_frac"], row["effect_bias"], row["ratio"] = top["mad"], top["frac"], top["bias"], top["ratio"]
            row["floor_mad"], row["floor_frac"], row["floor_bias"] = best["floor"]
            if row["verdict"] == "no effect" and not rd["nodes"] and not rd["drivers"]:
                notes.append("read only in Python by " + ", ".join(rd["python"]) if rd["python"] else "no shader or driver reads it")
        row["note"] = "; ".join(notes)
        if self.frames_dir and row["verdict"] != "effect":
            try:
                os.makedirs(self.frames_dir, exist_ok=True)
                for name, fr in frames.items():
                    path = os.path.join(self.frames_dir, "%s-cam%s-%s.png" % (c["key"], row["cams_tried"][0] if row["cams_tried"] else "x", name))
                    write_png(path, np.rint(fr[::-1, :, ::-1]).astype(np.uint8))      # the BMP is bottom-up BGR
            except OSError as e:
                row["note"] += "; frames not saved: %s" % e
        return row

    def cam_number(self, x):
        """A camera number, or "flight": the Flight's shot, which flight_rt adds as the last CAM_n (0 without one)."""
        if x != "flight":
            return int(x)
        fc = next((o for o in self.scene.objects if o.type == "CAMERA" and o.get("vj_flight_cam")), None)
        return int(fc.name[4:]) if fc is not None else 0

    def test(self, c, rd):
        pre = PRECONDITIONS.get(c["key"], {})
        cams = [self.cam_number(x) for x in pre.get("cams", [0])]
        if c["key"] == "vj_cam":
            cams = [0]
        attempts, frames, error, confirmed = [], {}, None, None
        try:
            for cam in cams:
                a, f = yield from self.attempt(c, pre, cam, primary=True)
                attempts.append(a)
                frames = frames or f
            if self.opts.get("fallback", FALLBACK) and c["key"] != "vj_cam":
                for cam in range(int(self.by_key["vj_cam"]["max"]) + 1):     # other cameras until one shows it strongly
                    if self.strength(c, attempts) >= STRONG:
                        break
                    if cam not in cams:
                        a, _ = yield from self.attempt(c, pre, cam, primary=False)
                        attempts.append(a)
            best = self.best(c, attempts)
            # a weak effect, or one strong cell with the other cells of its camera at the floor, has to repeat on fresh
            # baselines: a picture change off the stopped clocks between a cached baseline and one cell looks the same
            if self.effective(c, [best]) and (self.strength(c, [best]) < STRONG or self.lone(c, best)):
                self.baselines.pop(self.signature(pre, best["cam"]), None)
                again, _ = yield from self.attempt(c, pre, best["cam"], primary=True)
                attempts.append(again)
                confirmed = self.effective(c, [again])
        except (Abort, Fatal):
            raise
        except Exception:
            error = traceback.format_exc(limit=3)
        return self.row_for(c, attempts, frames, rd, error, confirmed)

    def judged(self, c, attempt):
        return [x for x in attempt["cells"] if x["value"] != c["default"] or c["key"] == "vj_cam"]

    def shown(self, c, attempt):
        """Cells that clear the floor and read back."""
        return [x for x in self.judged(c, attempt) if x["effect"] and x["readback"]]

    def effective(self, c, attempts):
        """One cell far above the floor, or two cells above it: a single marginal cell is noise."""
        return any(len(self.shown(c, a)) >= (1 if c["key"] == "vj_cam" else 2) or any(x["ratio"] >= STRONG for x in self.shown(c, a))
                   for a in attempts)

    def lone(self, c, attempt):
        """One cell shows, the other judged cells stay at the floor (vj_cam judges every cell on its own)."""
        return c["key"] != "vj_cam" and len(self.shown(c, attempt)) == 1 and len(self.judged(c, attempt)) > 1

    def strength(self, c, attempts):
        return max((x["ratio"] for a in attempts if self.effective(c, [a]) for x in self.shown(c, a)), default=0.0)

    def best(self, c, attempts):
        return max(attempts, key=lambda a: (self.effective(c, [a]), max((x["ratio"] for x in self.judged(c, a)), default=0.0)))

    def procedure(self):
        self.begin()
        yield from self.wait_frames(MIN_FRAMES)
        only = {k if k.startswith(PREFIX) else PREFIX + k for k in self.opts.get("only") or ()}
        plan = [c for c in self.controls if not only or c["key"] in only]
        names = {n for c in plan for n in [c["key"]] + [r for r in PRECONDITIONS.get(c["key"], {}).get("reads", []) if r.startswith("rt_")]}
        counted = readers(sorted(names))
        self.result["progress"].update(total=len(plan), done=0)
        for c in plan:
            self.result["progress"]["current"] = c["key"]
            self.publish()
            reads = PRECONDITIONS.get(c["key"], {}).get("reads", [])
            rd = {"nodes": 0, "drivers": 0, "python": [r[3:] for r in reads if r.startswith("py:")]}
            for n in [c["key"]] + [r for r in reads if r.startswith("rt_")]:
                rd["nodes"] += counted[n]["nodes"]
                rd["drivers"] += counted[n]["drivers"]
            row = yield from self.test(c, rd)
            self.result["rows"].append(row)
            self.result["progress"]["done"] += 1
            self.publish()
        self.result["progress"]["current"] = None
        self.result["noise_floor"] = {"mad": round(self.noise[0], 4), "frac": round(self.noise[1], 6), "bias": round(self.noise[2], 4)}
        self.result["settings"] = {"average": AVERAGE, "replicates": REPLICATES, "changed": CHANGED, "mad_min": MAD_MIN,
                                   "frac_min": FRAC_MIN, "bias_min": BIAS_MIN, "noise_factor": NOISE_FACTOR,
                                   "step_s": self.runtime.STEP}
