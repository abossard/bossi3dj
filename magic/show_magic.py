"""Builds projects/show.magic, the one Magic project that drives both scenes.

    python3 magic/show_magic.py [--port 9201] [--out FILE]

It is the synthwave project (synthwave_magic.py: audio analysis, every /vj/* control as a Global, the OSC senders,
Monitor and Readout overlays) with two Syphon sources: Blender's CAM_OUT and Godot's COLOSSUS_OUT. A Mix module
crossfades them, driven by the Global SceneMix (0 = Blender only, 1 = Godot only), and the effects run on the mix.
The senders go straight to the scene on udp 9201: Blender's bridge and the Godot Colossus Scene both listen there, and only one of them runs at a time.
"""
import argparse
import os
import zlib

import synthwave_magic as sm

SYPHON_BLENDER = "CAM_OUT - Blender"
SYPHON_GODOT = "COLOSSUS_OUT - Godot"      # "<server> - <app>"; the app name of Godot_mono.app is a guess until Magic lists it
SYPHON_OUT = "MAGIC_OUT"                   # Magic's own output ("MAGIC_OUT - Magic"): the mixed picture, 1920x1080, for read-back and for another app
SCENE_PORT = 9201
MIX = "SceneMix"


def show_globals():
    """The synthwave Globals plus the fader between the two scenes, next to the other Magic-side controls."""
    out = list(sm.GLOBALS)
    at = next(i for i, g in enumerate(out) if g[0] == "Readout") + 1
    out.insert(at, sm.ctl(MIX, 0.0))
    return out


def show_synthetic():
    """The show's Globals on the synthetic signal of synthwave_magic: music the analysis can follow without any audio input."""
    base = {g[0] for g in sm.synthetic_globals()}
    return [g for g in sm.synthetic_globals()] + [g for g in show_globals() if g[0] not in base]


def build(port=SCENE_PORT, ip="127.0.0.1", blender=SYPHON_BLENDER, godot=SYPHON_GODOT, output=SYPHON_OUT, globals_=None):
    return sm.build(port, ip, blender, globals_ or show_globals(), syphon2=godot, mix=MIX, output=output)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", type=int, default=SCENE_PORT, help="OSC target: 9201 = the scene (Blender bridge or Godot Colossus Scene), 9200 = the optional relay (osc/lab.py)")
    ap.add_argument("--ip", default="127.0.0.1")
    ap.add_argument("--syphon-blender", default=SYPHON_BLENDER)
    ap.add_argument("--syphon-godot", default=SYPHON_GODOT)
    ap.add_argument("--syphon-out", default=SYPHON_OUT, help="Magic's own Syphon server name")
    ap.add_argument("--synthetic", action="store_true", help="test build: synthetic EDM signal and timed controls, no audio")
    ap.add_argument("--out", default=os.path.join(sm.HERE, "projects", "show.magic"))
    a = ap.parse_args()
    xml = build(a.port, a.ip, a.syphon_blender, a.syphon_godot, a.syphon_out, show_synthetic() if a.synthetic else None)
    with open(a.out, "wb") as f:
        f.write(sm.HEADER + zlib.compress(xml, 9))
    print("wrote %s (%d globals, %d OSC addresses -> %s:%d, Syphon %s + %s, out %s)" % (
        a.out, len(show_globals()), len(sm.OSC_OUT), a.ip, a.port, a.syphon_blender, a.syphon_godot, a.syphon_out))


if __name__ == "__main__":
    main()
