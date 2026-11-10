"""Builds projects/show.magic, the one Magic project that drives both scenes.

    python3 magic/show_magic.py [--port 9200] [--out FILE]

It is the synthwave project (synthwave_magic.py: audio analysis, every /vj/* control as a Global, the OSC senders,
Monitor and Readout overlays) with two Syphon sources: Blender's CAM_OUT and Godot's COLOSSUS_OUT. A Mix module
crossfades them, driven by the Global SceneMix (0 = Blender only, 1 = Godot only), and the effects run on the mix.
The senders go to the relay (osc/lab.py, udp 9200), which hands every packet to Blender (9201) and Godot (9202).
"""
import argparse
import os
import zlib

import synthwave_magic as sm

SYPHON_BLENDER = "CAM_OUT - Blender"
SYPHON_GODOT = "COLOSSUS_OUT - Godot"      # "<server> - <app>"; the app name of Godot_mono.app is a guess until Magic lists it
RELAY_PORT = 9200
MIX = "SceneMix"


def show_globals():
    """The synthwave Globals plus the fader between the two scenes, next to the other Magic-side controls."""
    out = list(sm.GLOBALS)
    at = next(i for i, g in enumerate(out) if g[0] == "Readout") + 1
    out.insert(at, sm.ctl(MIX, 0.0))
    return out


def build(port=RELAY_PORT, ip="127.0.0.1", blender=SYPHON_BLENDER, godot=SYPHON_GODOT):
    return sm.build(port, ip, blender, show_globals(), syphon2=godot, mix=MIX)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", type=int, default=RELAY_PORT, help="OSC target: 9200 = the relay (osc/lab.py), which feeds both scenes")
    ap.add_argument("--ip", default="127.0.0.1")
    ap.add_argument("--syphon-blender", default=SYPHON_BLENDER)
    ap.add_argument("--syphon-godot", default=SYPHON_GODOT)
    ap.add_argument("--out", default=os.path.join(sm.HERE, "projects", "show.magic"))
    a = ap.parse_args()
    xml = build(a.port, a.ip, a.syphon_blender, a.syphon_godot)
    with open(a.out, "wb") as f:
        f.write(sm.HEADER + zlib.compress(xml, 9))
    print("wrote %s (%d globals, %d OSC addresses -> %s:%d, Syphon %s + %s)" % (
        a.out, len(show_globals()), len(sm.OSC_OUT), a.ip, a.port, a.syphon_blender, a.syphon_godot))


if __name__ == "__main__":
    main()
