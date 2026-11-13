"""Builds projects/synthwave_pyramids.magic, the Magic Music Visuals project
that plays the synthwave_pyramids.blend scene.

    python3 magic/synthwave_magic.py [--port 9201] [--out FILE]

Magic shows Blender's Syphon frame with audio-driven post effects and sends
every /vj/* address the scene reads over OSCSender. All audio analysis lives
in Globals, so every control is one Global that MIDI or OSC learn can bind.
Format notes (verified against Magic 3.0b6 saves): .magic = 3 header bytes +
zlib XML; a parameter links to a Global with layerID 2147483646 and
feature=<global id>; modifier types are the index into Magic's modifier list.
"""
import argparse
import json
import os
import xml.etree.ElementTree as ET
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
# The contract (osc/contract.json) is the one source of every address, its wire range and wire default.
with open(os.path.join(HERE, "..", "osc", "contract.json")) as _f:
    CONTRACT = {r["address"]: r for r in json.load(_f)["controls"]}
HEADER = b"L*h"                  # copied from master.magic; Magic does not check it
GLOBAL_LAYER = 2147483646        # "Globals" source
AUDIO_LAYER, OSC_LAYER = 2, 3    # Layer ids below
OSC_IN_PORT = 11111              # SwiftVJ forwards Synesthesia OSC here (Config.oscMagicPort)

OP = {name: i for i, name in enumerate([
    "Gate", "Scale", "Offset", "Power", "Smooth", "Wrap", "Random", "Ramp",
    "Sine", "Triangle", "Threshold", "Average", "Peak", "Exponent", "Clamp",
    "Step", "Increase", "Trigger", "Invert", "Hold", "Delay", "Expression",
    "RandomTrigger"])}

# Audio feature 1 = Freq. Range; sub 0..4 = 20-80, 80-320, 320-1.2k,
# 1.2k-5k, 5k-20k Hz (0 Volume, 2 Best Pitch, 3 Tone are unused here).
FREQ = 1

# ---------------------------------------------------------------- Globals
# (name, source, value, [(modifier, param, expression)])
# source: None = manual control, ("audio", feature, sub), ("global", name),
# ("osc", address) or "calc" (no input, the modifiers compute it).
# Order matters: a Global that reads a later one sees its previous value.


def ex(expr):
    return ("Expression", 0, expr)


def ctl(name, value):
    return (name, None, value, [])


# The controls the music steers. Each gets Takeover: <Name>Prev (its value a frame ago), <Name>Touch (the clock of its last change by hand
# or MIDI, 0 = never) and <Name>Follow (Follow, or 0 while the touch is younger than Takeover x 60 s). Its Out uses <Name>Follow.
STEERED = ["Level", "Bass", "Beat", "Hue", "Intensity", "Strobe", "GridSpeed", "CamSpeed", "Path", "Target", "Height", "Fog", "FogGlow"]


def takeover(name):
    return [("%sPrev" % name, "calc", 0, [ex(name)]),
            ("%sTouch" % name, "calc", 0, [ex("if(Clock > 1 and abs(%s - %sPrev) > 0.0001, Clock, y)" % (name, name))]),
            ("%sFollow" % name, "calc", 0, [ex("Follow*if(%sTouch > 0 and Clock - %sTouch < Takeover*60, 0, 1)" % (name, name))])]


GLOBALS = [
    # Controls, 0..1 so a MIDI CC maps straight on.
    # Every /vj/* address has a control Global named like it (/vj/fog_height: FogHeight), set here by hand. It holds the
    # contract's default. Where the music drives the address (Follow below), the control is the value while no music plays
    # and the base the music moves. Takeover: a control you touch (by hand or MIDI) is yours for Takeover x 60 s, then the
    # music steers it again (<Name>Follow below). An index control is a 0..1 fader over its stops (Path, Target, Cam).
    ctl("Gain", 0.5),        # input sensitivity, 0.5 = x2
    ctl("Master", 1.0),      # overall brightness, scales Intensity and Strobe
    ctl("React", 1.0),       # the music mapping on/off: 0 = the controls alone, 1 = music drives the addresses it can
    ctl("Level", 0.5),       # /vj/level
    ctl("Bass", 0.0),        # /vj/bass
    ctl("Beat", 0.0),        # /vj/beat
    ctl("Intensity", 0.5),   # /vj/intensity
    ctl("Auto", 1.0),        # automatic build/drop/breakdown direction
    ctl("Blackout", 0.0),
    ctl("Strobe", 0.0),      # /vj/strobe: flash on every beat, 0..1
    ctl("Buildup", 0.0),     # manual build fader, adds to the detector
    ctl("Drop", 0.0),        # momentary pad: fire a drop now
    ctl("Shock", 0.0),       # momentary pad: shockwave from the next pyramid
    ctl("ShockKick", 1.0),   # shockwave on heavy kicks
    ctl("Meteor", 0.0),      # momentary pad: shooting star
    ctl("Hue", 0.0),         # /vj/hue base, the music walks it by HueDrift
    ctl("HueDrift", 0.05),   # hue walk per bar and per drop
    ctl("CamAuto", 1.0),     # /vj/cam_auto, Godot only: 1 = Godot's director cuts by itself, 0 = it holds the shot Cam picks
    ctl("Cam", 0.0),         # /vj/cam, Godot only: 0..1 -> shot 0..11 (a scene without that many takes its last)
    ctl("Path", 0.0),        # /vj/path: 0..1 -> path 0..3 (orbit, follow the land, rise and descend, vantage)
    ctl("Target", 0.0),      # /vj/target: 0..1 -> target 0..6 (pyramids, lake, river, coast, moon, sun, planet)
    ctl("Height", 0.3),      # /vj/height: 0 just over the ground, 0.5 about 800 m, 1 space (log scale in the scene)
    ctl("Takeover", 0.33),   # /vj/takeover: how long a touched control stays yours, 0..1 = 0..60 s (0.33 = 20 s)
    ctl("CamSpeed", 0.25),   # /vj/cam_speed
    ctl("GridSpeed", 0.15),  # /vj/grid_speed
    ctl("Sun", 1.0), ctl("Moon", 1.0), ctl("Pyramids", 1.0),
    ctl("Grid", 1.0), ctl("Stars", 1.0), ctl("Water", 1.0),
    ctl("MoonPhase", 1.0),   # moon on its orbit: 0 new (next to the sun), 1 full (opposite)
    ctl("Eclipse", 0.0),     # lines the orbit up: lunar at full moon, solar at new moon
    ctl("StarSpeed", 0.0),   # star drift against the sun, 0..1 = 0..10 deg/s
    ctl("Night", 0.0),       # sun height: 0 +20 deg, 0.5 half set, 1 -18 deg (night); lowering it runs time backwards
    ctl("Nebula", 1.0),      # night 3D nebula strength
    ctl("Flamingos", 1.0),   # flock size, 0 hides them
    ctl("Fog", 0.35),        # 0 removes the fog volume
    ctl("FogHeight", 0.41),  # 1..60 m
    ctl("FogGlow", 0.3),     # x2
    ctl("FogHue", 0.0),
    ctl("FogNoise", 0.6),
    ctl("FogScale", 0.25),   # 10..1000 m
    ctl("FogSpeed", 0.25),   # x40 m/s
    ctl("Blend", 0.5),       # /vj/blend, Fade Time: how long a change of path or target flies, 0 cuts, 0..1 = 0..60 s
    ctl("Energy", 0.3),      # /vj/energy, planet scene: how hard the cameras move
    ctl("Hit", 0.0),         # momentary pad: speed surge with a wide-angle kick
    ctl("FogBeat", 0.5),     # how much fog pulses on the beat
    ctl("Haze", 1.0),        # distance haze; 0 with Fog 0 is a fog-free view
    ctl("FxGlow", 0.0), ctl("FxTrails", 0.0), ctl("FxBlur", 0.0),
    ctl("FxChroma", 0.0), ctl("FxShake", 0.0), ctl("FxKaleido", 0.0),
    ctl("Monitor", 0.0),     # analysis meters over the output
    ctl("Readout", 0.0),     # OSC values being sent, over the output

    # Bands, gain-normalised.
    ("Sub", ("audio", FREQ, 0), 0, [ex("x*Gain*4")]),
    ("Low", ("audio", FREQ, 1), 0, [ex("x*Gain*4")]),
    ("Mid", ("audio", FREQ, 2), 0, [ex("x*Gain*4")]),
    ("HiMid", ("audio", FREQ, 3), 0, [ex("x*Gain*4")]),
    ("Air", ("audio", FREQ, 4), 0, [ex("x*Gain*4")]),

    # Seconds and the time since the last evaluation, so the slow trackers
    # below behave the same at any frame or audio-block rate.
    ("ClockPrev", "calc", 0, [ex("Clock")]),
    ("Clock", "calc", 0, [("Increase", 1, "x")]),
    ("Dt", "calc", 0.016, [ex("max(0.001, min(0.05, Clock - ClockPrev))")]),

    # Onsets: a fast follower (~10 ms) above a slow one (~0.3 s) plus a floor
    # scaled to the track's own recent peak, so any input level works. A
    # refractory time stops one hit firing twice; the envelopes then decay
    # in seconds (Magic's Peak holds far too long).
    ("SubAvg", ("global", "Sub"), 0, [("Average", 0.5, "x")]),
    ("HiMidAvg", ("global", "HiMid"), 0, [("Average", 0.5, "x")]),
    ("AirAvg", ("global", "Air"), 0, [("Average", 0.3, "x")]),
    ("KickBand", "calc", 0, [ex("Sub + 0.5*Low")]),
    ("KFast", ("global", "KickBand"), 0, [ex("y + (x - y)*min(1, Dt/0.012)")]),
    ("KSlow", ("global", "KickBand"), 0, [ex("y + (x - y)*min(1, Dt/0.3)")]),
    ("KRef", ("global", "KFast"), 0.1, [ex("max(x, y*exp(-Dt/10), 0.02)")]),
    ("KRaw", "calc", 0, [ex("if(KFast > KSlow*1.25 + KRef*0.06 and Clock - KickT > 0.22, 1, 0)")]),
    # Once the beat clock is locked, only onsets near the beat count as kicks,
    # so off-beat bass notes neither flash nor pull the clock.
    ("KOn", "calc", 0, [ex("if(KRaw > 0.5 and (Lock < 0.45 or abs(Phase + 0.5 - floor(Phase + 0.5) - 0.5) < 0.15), 1, 0)")]),
    # Beat period from the kick intervals, folded into 100-200 BPM; a
    # consistent interval moves it fast, an outlier only a little.
    # Magic starts a calculated Global at 0, hence the 128 BPM seed.
    ("Period", "calc", 0.469, [ex("if(y < 0.29, 0.469, if(KOn > 0.5, if(Clock - KickT >= 0.3 and Clock - KickT <= 0.6, "
                                  "y + (Clock - KickT - y)*if(abs(Clock - KickT - y) < 0.05*y, 0.25, 0.04), "
                                  "if(Clock - KickT > 0.6 and Clock - KickT <= 1.2, "
                                  "y + ((Clock - KickT)/2 - y)*if(abs((Clock - KickT)/2 - y) < 0.05*y, 0.15, 0.02), y)), y))"), ex("max(0.3, min(0.6, x))")]),
    ("GapAtKick", "calc", 0, [ex("if(KOn > 0.5, Clock - KickT, y)")]),  # kick-free time before this kick
    ("KickT", "calc", 0, [ex("if(KOn > 0.5, Clock, y)")]),
    ("KickGap", "calc", 0, [ex("Clock - KickT")]),
    ("Kick", ("global", "KOn"), 0, [ex("max(x, y*exp(-Dt*9))")]),
    ("SFast", ("global", "HiMid"), 0, [ex("y + (x - y)*min(1, Dt/0.01)")]),
    ("SSlow", ("global", "HiMid"), 0, [ex("y + (x - y)*min(1, Dt/0.35)")]),
    ("SnOn", "calc", 0, [ex("if(SFast > SSlow*1.4 + 0.02 and Clock - SnareT > 0.12, 1, 0)")]),
    ("SnareT", "calc", 0, [ex("if(SnOn > 0.5, Clock, y)")]),
    ("Snare", ("global", "SnOn"), 0, [ex("max(x, y*exp(-Dt*10))")]),
    ("HFast", ("global", "Air"), 0, [ex("y + (x - y)*min(1, Dt/0.008)")]),
    ("HSlow", ("global", "Air"), 0, [ex("y + (x - y)*min(1, Dt/0.2)")]),
    ("HatOn", "calc", 0, [ex("if(HFast > HSlow*1.4 + 0.015 and Clock - HatT > 0.06, 1, 0)")]),
    ("HatT", "calc", 0, [ex("if(HatOn > 0.5, Clock, y)")]),
    ("Hat", ("global", "HatOn"), 0, [ex("max(x, y*exp(-Dt*16))")]),
    # Beat clock: Phase runs 0..1 per beat and each kick pulls it toward 0.
    # Lock is how well kicks land on it; it fades over ~6 s without kicks, so
    # the pulse holds through a missed kick but not through a breakdown.
    ("Lock", "calc", 0, [ex("if(KOn > 0.5, y + (max(0, 1 - 5*abs(Phase + 0.5 - floor(Phase + 0.5) - 0.5)) - y)*0.25, max(0, y - Dt/6))")]),
    ("PhasePrev", "calc", 0, [ex("Phase")]),
    ("Phase", "calc", 0, [ex("(y + Dt/Period - if(KOn > 0.5, 0.3*(y + 0.5 - floor(y + 0.5) - 0.5), 0)) - "
                             "floor(y + Dt/Period - if(KOn > 0.5, 0.3*(y + 0.5 - floor(y + 0.5) - 0.5), 0))")]),
    ("Tick", "calc", 0, [ex("if(Phase < PhasePrev - 0.5, 1, 0)")]),
    ("Pulse", "calc", 0, [ex("exp(-Phase*Period*8)")]),
    ("BPM", "calc", 128, [ex("60/Period")]),
    ("ExtBeat", ("osc", "/audio/beat/onbeat"), 0, [ex("max(x, y*exp(-Dt*9))")]),
    ("BeatNow", "calc", 0, [ex("max(Kick, ExtBeat, Lock*Pulse)")]),
    ("Beats", ("global", "Tick"), 0, [("Trigger", 0.5, "x")]),  # running count on the beat clock
    ("Bars", ("global", "Beats"), 0, [ex("floor(x/4)")]),

    # Energy now and over the last seconds.
    ("EnergyNow", "calc", 0, [ex("min(1, 0.4*Sub + 0.25*Low + 0.15*Mid + 0.12*HiMid + 0.08*Air)"), ("Smooth", 0.6, "x")]),
    ("EnergyAvg", ("global", "EnergyNow"), 0, [("Average", 1, "x"), ("Smooth", 0.97, "x")]),
    # Is there music? Live is 1 while the input carries sound and fades over 3 s after it stops. Follow is how much the music
    # drives the addresses it can: Live x React. With no sound or React 0 every address holds its control (the contract default).
    ("Live", "calc", 0, [ex("if(EnergyNow > 0.004, 1, max(0, y - Dt/3))")]),
    ("Follow", "calc", 0, [ex("Live*React")]),
    # Path and target move on: one step on every drop and every 16 bars.
    ("Moves", "calc", 0, [ex("floor(Bars/16) + Drops")]),
    *[g for name in STEERED for g in takeover(name)],

    # EDM structure, keyed on the kick: 1.5-4 s without one is a breakdown, or
    # a build while the highs rise (riser, snare roll); the first kick after
    # 6 s or more without one is the drop. HiLong rises slowly so risers stand out.
    ("SubLong", ("global", "SubAvg"), 0, [ex("y + (x - y)*min(1, Dt/if(x > y, 2, 40))")]),
    ("HiAvg", "calc", 0, [ex("(HiMidAvg + AirAvg)*0.5")]),
    ("HiLong", ("global", "HiAvg"), 0, [ex("y + (x - y)*min(1, Dt/if(x > y, if(x > y*2, 1, 12), 3))")]),
    ("HiRise", "calc", 0, [ex("max(0, min(1, (HiAvg/max(HiLong, 0.02) - 1)*1.5))"), ("Smooth", 0.95, "x")]),
    ("NoKick", "calc", 0, [ex("min(1, max(0, (KickGap - 1.5)/2.5))")]),
    ("BuildAuto", "calc", 0, [ex("NoKick*min(1, 0.25 + 1.5*HiRise)"), ("Smooth", 0.95, "x")]),
    ("Build", "calc", 0, [ex("min(1, max(Buildup, Auto*BuildAuto))")]),
    ("Breakdown", "calc", 0, [ex("Auto*NoKick*max(0, 1 - 1.5*HiRise)"), ("Smooth", 0.95, "x")]),
    ("DropEvt", "calc", 0, [ex("if(Drop > 0.5 or (Auto > 0.5 and Clock > 10 and KOn > 0.5 and GapAtKick > 6 and DropEnv < 0.2), 1, 0)")]),
    ("Drops", ("global", "DropEvt"), 0, [("Trigger", 0.5, "x")]),
    ("DropEnv", "calc", 0, [ex("max(DropEvt, y - Dt/6)")]),
    # Shockwave on heavy kicks (near the track's recent peak): about every
    # second kick, every kick while a drop is fresh, strength 0.6 rising to
    # 1.5 on the drop itself. Blender runs up to four waves at once.
    ("ShockOn", "calc", 0, [ex("if(ShockKick > 0.5 and Follow > 0.05 and KOn > 0.5 and KFast > KRef*0.6 and "
                               "Clock - ShockT > if(DropEnv > 0.3, 0.35, 0.9), 1, 0)")]),
    ("ShockAmp", "calc", 0.6, [ex("if(DropEvt > 0.5 or Shock > 0.5, 1.5, if(ShockOn > 0.5, min(1.5, 0.6 + 0.8*DropEnv), y))")]),
    ("ShockT", "calc", -1, [ex("if(ShockOn > 0.5 or DropEvt > 0.5 or Shock > 0.5, Clock, y)")]),

    # Values sent to the scenes (/vj/*), in wire units: 0..1 for every continuous control (osc/CONTROLS.md).
    # Level and bass relative to the track's own average, so any input level works.
    ("OutLevel", "calc", 0.5, [ex("Level + LevelFollow*(min(1, 0.4*EnergyNow/max(EnergyAvg, 0.02) + 0.3*BeatNow) - Level)")]),
    ("OutBass", "calc", 0, [ex("Bass + BassFollow*(min(1, 0.35*Sub/max(SubLong, 0.03) + 0.5*Kick) - Bass)")]),
    ("OutBeat", "calc", 0, [ex("Beat + BeatFollow*(BeatNow - Beat)")]),
    ("OutHue", "calc", 0, [ex("frac(Hue + HueFollow*HueDrift*(Bars/8 + Drops*0.25))")]),
    ("OutIntensity", "calc", 0.5, [ex("Master*(1 - Blackout)*Intensity*(1 + IntensityFollow*(Auto*(0.35*DropEnv + 0.15*Build - 0.25*Breakdown) - 0.15))")]),
    ("OutStrobe", "calc", 0, [ex("Master*(1 - Blackout)*min(1, max(Strobe, StrobeFollow*Auto*DropEnv*0.5)*BeatNow^4 + StrobeFollow*Auto*Build*Build*Snare^4*0.6)")]),
    # 0..4 cells/s on the wire as 0..1
    ("OutGridSpeed", "calc", 0.15, [ex("min(1, max(0, GridSpeed*(1 + GridSpeedFollow*(0.5*EnergyAvg + 0.8*DropEnv + 0.4*Build - 0.4*Breakdown))))")]),
    # An index: shot N of the scene, 0-based. A scene with fewer shots takes its last.
    ("OutCam", "calc", 0, [ex("floor(Cam*11.999)")]),
    ("OutCamAuto", "calc", 1, [ex("if(CamAuto > 0.5, 1, 0)")]),
    # 0..4 on the wire as 0..1
    # The Path Camera: path and target step on with the music (Moves), height sinks on builds and rises in breakdowns.
    ("OutPath", "calc", 0, [ex("if(PathFollow > 0.5, Moves % 4, floor(Path*3.999))")]),
    ("OutTarget", "calc", 0, [ex("if(TargetFollow > 0.5, (Moves*3) % 7, floor(Target*6.999))")]),
    ("OutHeight", "calc", 0.3, [ex("min(1, max(0, Height + HeightFollow*Auto*(0.2*Breakdown - 0.2*Build - 0.1*DropEnv)))"), ("Smooth", 0.95, "x")]),
    ("OutTakeover", ("global", "Takeover"), 0.33, []),
    ("OutCamSpeed", "calc", 0.25, [ex("min(1, max(0, CamSpeed*(1 + CamSpeedFollow*Auto*(0.5*Build + 0.8*DropEnv - 0.3*Breakdown))))")]),
    ("OutSun", ("global", "Sun"), 1, [("Smooth", 0.95, "x")]),
    ("OutMoon", ("global", "Moon"), 1, [("Smooth", 0.95, "x")]),
    ("OutMoonPhase", ("global", "MoonPhase"), 1, [("Smooth", 0.95, "x")]),
    ("OutEclipse", ("global", "Eclipse"), 0, [("Smooth", 0.95, "x")]),
    ("OutStarSpeed", ("global", "StarSpeed"), 0, [("Smooth", 0.95, "x")]),
    ("OutPyramids", ("global", "Pyramids"), 1, [("Smooth", 0.95, "x")]),
    ("OutGrid", ("global", "Grid"), 1, [("Smooth", 0.95, "x")]),
    ("OutStars", ("global", "Stars"), 1, [("Smooth", 0.95, "x")]),
    ("OutWater", ("global", "Water"), 1, [("Smooth", 0.95, "x")]),
    ("OutNight", ("global", "Night"), 0, [("Smooth", 0.95, "x")]),
    ("OutNebula", ("global", "Nebula"), 1, [("Smooth", 0.95, "x")]),
    ("OutFlamingos", ("global", "Flamingos"), 1, [("Smooth", 0.95, "x")]),
    ("OutHaze", ("global", "Haze"), 1, [("Smooth", 0.95, "x")]),
    ("OutFog", "calc", 0.35, [ex("max(Fog, min(0.6, Fog + FogFollow*Auto*Breakdown*0.3))"), ("Smooth", 0.95, "x")]),
    ("OutFogHeight", ("global", "FogHeight"), 0.41, [("Smooth", 0.95, "x")]),
    ("OutFogGlow", "calc", 0.3, [ex("min(1, FogGlow*(1 + FogGlowFollow*Auto*0.5*DropEnv))")]),
    ("OutFogHue", ("global", "FogHue"), 0, [("Smooth", 0.95, "x")]),
    ("OutFogNoise", ("global", "FogNoise"), 0.6, [("Smooth", 0.95, "x")]),
    ("OutFogScale", ("global", "FogScale"), 0.25, [("Smooth", 0.95, "x")]),
    ("OutFogSpeed", ("global", "FogSpeed"), 0.25, [("Smooth", 0.95, "x")]),
    ("OutFogBeat", ("global", "FogBeat"), 0.5, [("Smooth", 0.95, "x")]),
    # A 50 ms pulse at the wave's strength, so every trigger is a new rising edge.
    ("OutShock", "calc", 0, [ex("if(Clock - ShockT < 0.05 and ShockT > 0, ShockAmp, 0)")]),
    ("OutMeteor", "calc", 0, [ex("if(Meteor > 0.5, 1, 0)")]),
    ("OutHit", "calc", 0, [ex("if(Hit > 0.5, 1, 0)")]),
    # Planet scene controls that are plain faders here; the scene eases them itself.
    ("OutBlend", ("global", "Blend"), 0.5, []),
    ("OutEnergy", ("global", "Energy"), 0.3, []),

    # Magic-side effect amounts: manual faders only, so Magic adds nothing over Blender's frame by default.
    ("GlowAmt", "calc", 0, [ex("FxGlow")]),
    ("TrailAmt", "calc", 0, [ex("FxTrails")]),
    ("BlurAmt", "calc", 0, [ex("FxBlur")]),
    ("ChromaAmt", "calc", 0, [ex("FxChroma")]),
]

# One sender per contract row: (address, Global). osc/contract.json holds the address list; a test checks both ways.
OSC_OUT = [
    ("/vj/level", "OutLevel"), ("/vj/bass", "OutBass"), ("/vj/beat", "OutBeat"),
    ("/vj/hue", "OutHue"), ("/vj/intensity", "OutIntensity"), ("/vj/strobe", "OutStrobe"),
    ("/vj/grid_speed", "OutGridSpeed"), ("/vj/cam", "OutCam"), ("/vj/cam_auto", "OutCamAuto"), ("/vj/cam_speed", "OutCamSpeed"),
    ("/vj/path", "OutPath"), ("/vj/target", "OutTarget"), ("/vj/height", "OutHeight"), ("/vj/takeover", "OutTakeover"),
    ("/vj/sun", "OutSun"), ("/vj/moon", "OutMoon"), ("/vj/moon_phase", "OutMoonPhase"), ("/vj/pyramids", "OutPyramids"),
    ("/vj/grid", "OutGrid"), ("/vj/stars", "OutStars"), ("/vj/water", "OutWater"),
    ("/vj/night", "OutNight"), ("/vj/shock", "OutShock"), ("/vj/nebula", "OutNebula"),
    ("/vj/fog", "OutFog"), ("/vj/fog_height", "OutFogHeight"), ("/vj/fog_glow", "OutFogGlow"),
    ("/vj/fog_hue", "OutFogHue"), ("/vj/fog_noise", "OutFogNoise"), ("/vj/fog_scale", "OutFogScale"),
    ("/vj/fog_speed", "OutFogSpeed"), ("/vj/fog_beat", "OutFogBeat"),
    ("/vj/meteor", "OutMeteor"), ("/vj/flamingos", "OutFlamingos"), ("/vj/haze", "OutHaze"),
    ("/vj/eclipse", "OutEclipse"), ("/vj/star_speed", "OutStarSpeed"),
    ("/vj/blend", "OutBlend"), ("/vj/energy", "OutEnergy"),
    ("/vj/hit", "OutHit"),
]

# What the music does to an address, in plain words. An address in this dict follows the music while Follow is above 0 and its control
# was not touched within the Takeover pause (its Out Global reads <Name>Follow); every other address is its control Global alone. The handbook table (magic_manual.py) is built from this and the project.
MUSIC = {
    "/vj/level": "Loudness against the track's own average, plus the beat.",
    "/vj/bass": "Sub-bass against its recent average, plus the kick.",
    "/vj/beat": "The beat clock: kick, or Synesthesia's onbeat on OSC in.",
    "/vj/hue": "Walks on by HueDrift every bar and every drop.",
    "/vj/intensity": "Lifts on drops and builds, dips in breakdowns (Auto 1).",
    "/vj/strobe": "Flashes on the beat during a drop and on snare rolls in a build (Auto 1); Strobe adds a flash on every beat.",
    "/vj/grid_speed": "Faster with energy, drops and builds, slower in breakdowns.",
    "/vj/path": "Steps to the next path on every drop and every 16 bars.",
    "/vj/target": "Steps on with the path, through all seven targets.",
    "/vj/height": "Sinks on builds and drops, rises in breakdowns (Auto 1).",
    "/vj/cam_speed": "Faster on builds and drops, slower in breakdowns (Auto 1).",
    "/vj/fog": "Thickens in a breakdown, up to 0.6 (Auto 1).",
    "/vj/fog_glow": "Glows brighter on a drop (Auto 1).",
    "/vj/shock": "A wave on heavy kicks and on every drop (ShockKick 1); the Shock pad fires one now.",
}

# Readout rows: (top value, display step, wire default), all from the contract.
READOUT = {a: (r["max"], 1 if r["kind"] == "int" else 0.01, r["default"]) for a, r in CONTRACT.items()}

# --synthetic: a test build that needs no audio or controller. A 24-bar
# loop at 128 BPM (8 full, 4 breakdown, 4 build with a snare roll, 8 drop)
# plus noise replaces the bands, and the controls run on timers.
SYN_BAR = "((Clock*128/240) % 24)"
SYN_FULL = "(%s < 8 or %s >= 16)" % (SYN_BAR, SYN_BAR)
SYN_BUILD = "(%s >= 12 and %s < 16)" % (SYN_BAR, SYN_BAR)
SYN_K = "((%s - 12)/4)" % SYN_BAR
SYN_KICK = "exp(-frac(Clock*128/60)*12)"
SYNTHETIC = {
    "Sub": "if(%s, 0.25*%s + 0.05, 0)" % (SYN_FULL, SYN_KICK),
    "Low": "if(%s, 0.15*%s + 0.08, if(%s, 0.08, 0.03))" % (SYN_FULL, SYN_KICK, SYN_BUILD),
    "Mid": "0.05",
    "HiMid": "0.04 + if(%s, 0.15*exp(-frac(Clock*128/120 + 0.5)*15), 0) + if(%s, 0.15*(0.5 + 0.5*%s)*exp(-frac(Clock*128/240*pow(2, 1 + min(3, floor(%s*4))))*15), 0)"
             % (SYN_FULL, SYN_BUILD, SYN_K, SYN_K),
    "Air": "0.03 + if(%s, 0.08*%s, 0) + if(%s, 0.05*exp(-frac(Clock*128/30)*20), 0)" % (SYN_BUILD, SYN_K, SYN_FULL),
}
SYNTHETIC_CONTROLS = {
    "Strobe": "if(frac(Clock/50) > 0.85, 0.8, 0)",
    "Hue": "0.5 - 0.5*cos(Clock*0.05)",
    "HueDrift": "0.3",
    "CamAuto": "if(frac(Clock/60) < 0.5, 1, 0)",
    "Cam": "(floor(frac(Clock/20)*7) + 0.5)/7",
    "Sun": "if(frac(Clock/23) < 0.8, 1, 0)",
    "Moon": "if(frac(Clock/29 + 0.3) < 0.8, 1, 0)",
    "Pyramids": "if(frac(Clock/31 + 0.5) < 0.8, 1, 0)",
    "Grid": "if(frac(Clock/37 + 0.2) < 0.85, 1, 0)",
    "Stars": "if(frac(Clock/41 + 0.6) < 0.85, 1, 0)",
    "Water": "if(frac(Clock/43 + 0.1) < 0.85, 1, 0)",
    "Night": "0.5 - 0.5*cos(Clock*6.283/90)",
    "MoonPhase": "0.5 + 0.5*cos(Clock*0.05)",
    "FxTrails": "max(0, sin(Clock*0.21))*0.6",
    "FxBlur": "max(0, sin(Clock*0.17 + 1))*0.5",
    "FxChroma": "max(0, sin(Clock*0.13 + 2))*0.6",
    "FxShake": "max(0, sin(Clock*0.11 + 3))*0.5",
    "FxKaleido": "if(frac(Clock/70) > 0.85, 1, 0)",
    "Blackout": "if(frac(Clock/45) > 0.98, 1, 0)",
    "Shock": "if(frac(Clock/17) > 0.97, 1, 0)",
    "Meteor": "if(frac(Clock/13) > 0.95, 1, 0)",
    "Flamingos": "if(frac(Clock/47 + 0.4) < 0.85, 1, 0)",
    "Haze": "0.5 + 0.5*cos(Clock*0.07)",
    "Fog": "0.35 + 0.35*sin(Clock*0.09)",
    "FogHue": "frac(Clock/80)",
    "FogGlow": "0.3 + 0.2*sin(Clock*0.15)",
    "Monitor": "1",
    "Readout": "1",
}


def synthetic_globals():
    out = []
    for name, src, value, ops in GLOBALS:
        if name in SYNTHETIC:
            out.append((name, "calc", 0, [ex(SYNTHETIC[name]), ("Random", 0.02, "x"), ex("x*Gain*4")]))
        elif name in SYNTHETIC_CONTROLS:
            out.append((name, "calc", value, [ex(SYNTHETIC_CONTROLS[name])]))
        else:
            out.append((name, src, value, ops))
    return out

METERS = ["Sub", "Low", "Mid", "HiMid", "Air", "Kick", "Snare", "Hat", "Pulse", "Lock", "BeatNow",
          "EnergyNow", "EnergyAvg", "Build", "Breakdown", "NoKick", "DropEnv", "Follow"]


# ---------------------------------------------------------------- XML


class Project:
    def __init__(self):
        self.gid = {}
        self.next_iv = 1
        self.next_node = 1
        self.scenes = []         # (name, root_node, nodes, positions)

    # InputValue -------------------------------------------------------
    def iv(self, name, value, src=None, ops=()):
        e = ET.Element("InputValue", name=name, id=str(self.next_iv), globalsUseID="1")
        self.next_iv += 1
        if src is None:
            e.attrib.update(linked="0", open="0", layerID="-1", feature="0", subFeature="0")
        elif src == "calc":
            e.attrib.update(linked="1", open="1", layerID="-1", feature="0", subFeature="0")
        elif src[0] == "audio":
            e.attrib.update(linked="1", open="1", layerID=str(AUDIO_LAYER), feature=str(src[1]), subFeature=str(src[2]))
        elif src[0] == "global":
            e.attrib.update(linked="1", open="1", layerID=str(GLOBAL_LAYER), feature=str(self.gid[src[1]]))
        elif src[0] == "osc":
            e.attrib.update(linked="1", open="1", layerID=str(OSC_LAYER), featureString=src[1])
        e.attrib.update(featureVersion="1", value=fmt(value))
        vo = ET.SubElement(e, "ValueOperators")
        for kind, param, expr in ops:
            ET.SubElement(vo, "ValueOperator", type=str(OP[kind]), param=fmt(param), bypassed="0",
                          paramLayerID="-1", paramFeature="-1", paramSubFeature="-1", paramFeatureString="",
                          bypassLayerID="-1", bypassFeature="-1", bypassSubFeature="-1", bypassMidiToggle="0",
                          bypassFeatureString="", paramMidiScale="1", paramString=expr)
        return e

    def link(self, name, value, global_name, expr=None):
        return self.iv(name, value, ("global", global_name), [ex(expr)] if expr else [])

    # Node ---------------------------------------------------------------
    def node(self, plugin, params=(), children=(), scene_id=None, bypass=None, power=None, magic=False):
        """params: InputValue elements; bypass/power: (global, expr) to link them."""
        nid = self.next_node
        self.next_node += 1
        e = ET.Element("Node", pluginName=plugin, magicNode="1" if magic else "0", disabled="0", bypassed="0",
                       bypassParamUsed="1" if bypass else "0", powerParamUsed="1" if power else "0",
                       dontRestart="0", id=str(nid))
        if scene_id is not None:
            e.set("sceneID", str(scene_id))
        ch = ET.SubElement(e, "Children")
        for c in children:
            ET.SubElement(ch, "Child", id=c.get("id"))
        ivs = ET.SubElement(e, "InputValues")
        if not magic:
            for p in params:
                ivs.append(p)
            if plugin not in ("SyphonClient", "OSCSender", "Polygon", "Text"):
                ivs.append(self.link("Bypass", 0, *bypass) if bypass else self.iv("Bypass", 0))
            ivs.append(self.link("Power", 1, *power) if power else self.iv("Power", 1))
        return e

    def scene_module(self, name, power=None):
        sid = [s[0] for s in self.scenes].index(name)
        return self.node(name, scene_id=sid, power=power)

    def add_scene(self, name):
        self.scenes.append([name, None, [], {}])
        return len(self.scenes) - 1

    def fill_scene(self, sid, root_children, nodes, positions):
        root = self.node("Magic", children=root_children, magic=True)
        self.scenes[sid][1:] = [root, nodes, positions]
        positions[root.get("id")] = (max([p[0] for p in positions.values()] + [0]) + 230, 15)


def fmt(v):
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def chain(*nodes):
    """Connects nodes left to right: each node becomes the only input of the next."""
    for a, b in zip(nodes, nodes[1:]):
        ET.SubElement(b.find("Children"), "Child", id=a.get("id"))
    return nodes[-1]


def build(port, ip, syphon, globals_=GLOBALS, captions=None, audio=None, trails_fx=False, syphon2=None, mix="SceneMix", output=None):
    """captions: (lines, global) for a timed text line in the Readout scene;
    audio: an audio file Magic plays in a loop and analyses instead of BlackHole;
    syphon2: a second SyphonClient server; the Program scene then crossfades the two with a Mix module
    whose Amount is the Global `mix` (0 = syphon only, 1 = syphon2 only), which globals_ must hold;
    output: Magic's own Syphon server name (1920x1080), None leaves Magic's output off."""
    p = Project()
    globals_el = ET.Element("Globals")
    for name, *_ in globals_:
        p.gid[name] = p.next_iv
        p.next_iv += 1
    p.next_iv = 1
    for name, src, value, ops in globals_:
        globals_el.append(p.iv(name, value, src, ops))
    assert [int(e.get("id")) for e in globals_el] == [p.gid[g[0]] for g in globals_]

    master, program, oscout, monitor, readout = (p.add_scene(n) for n in ("Master", "Program", "OSC Out", "Monitor", "Readout"))
    off = "if(x < 0.01, 1, 0)"   # bypass while an amount is zero

    # Program: the scene frame(s) through bypassable effects.
    syphon_in = p.node("SyphonClient", [p.iv("Server", syphon)])
    sources = [syphon_in]
    if syphon2:
        syphon_in2 = p.node("SyphonClient", [p.iv("Server", syphon2)])
        # Mix draws black while its second server is missing, even at Amount 0 (Godot is parked): bypassed while the fader is down, it passes the first source on.
        crossfade = p.node("Mix", [p.link("Amount", 0.0, mix)], children=[syphon_in, syphon_in2], bypass=(mix, "if(x < 0.01, 1, 0)"))
        sources = [syphon_in, syphon_in2, crossfade]
        syphon_in = crossfade
    bloom = p.node("Bloom", [p.iv("BlurAmount", 12.0), p.link("Intensity", 1.0, "GlowAmt", "x*(0.6 + 0.8*Kick)")],
                   bypass=("GlowAmt", off))
    chroma = p.node("Chroma Zoom", [p.iv("Master_zoom", 1), p.link("Red_zoom", 1, "ChromaAmt", "1 - x*(0.02 + 0.06*Kick)"),
                                    p.iv("Green_zoom", 1), p.link("Blue_zoom", 1, "ChromaAmt", "1 + x*(0.02 + 0.06*Kick)"),
                                    p.iv("Center X", 0), p.iv("Center Y", 0)], bypass=("ChromaAmt", off))
    radial = p.node("RadialBlur", [p.link("Distance", 0.25, "BlurAmt", "x*(0.1 + 0.3*BeatNow)"), p.iv("Density", 0.5)],
                    bypass=("BlurAmt", off))
    # Magic's Trails draws behind its input through alpha, which an opaque
    # Syphon frame hides, and the usual feedback shaders key dark pixels to
    # their (black) history. effects/Synthwave Trails.fs only ever brightens;
    # Magic finds it once that folder is an Additional Module Folder.
    trails = p.node("Synthwave Trails", [p.link("amount", 0.5, "TrailAmt"), p.iv("zoom", 0.2)],
                    bypass=("TrailAmt", off)) if trails_fx else None
    kaleido = p.node("Kaleidoscope", [p.iv("Iterations", 6), p.iv("Zoom", 1.0), p.link("Rotation", 0, "Clock", "frac(x*0.02)"),
                                      p.iv("Fill Edges", 1)], bypass=("FxKaleido", "if(x < 0.5, 1, 0)"))
    shake = p.node("Shake", [p.link("Magnitude", 0, "FxShake", "x*(0.2 + Kick)*0.05"), p.iv("Intensity", 1), p.iv("Speed", 1)],
                   bypass=("FxShake", off))
    fx = [n for n in (syphon_in, bloom, chroma, radial, trails, kaleido, shake) if n is not None]
    chain(*fx)
    shift = 200 if syphon2 else 0   # two sources stand in a column in front of the Mix
    pos = {n.get("id"): (15 + shift + i * 200, 15) for i, n in enumerate(fx)}
    for i, n in enumerate(sources[:-1]):
        pos[n.get("id")] = (15, 15 + i * 160)
    p.fill_scene(program, [shake], sources[:-1] + fx, pos)

    # OSC Out: one OSCSender per /vj/* address, drawn by the Master scene.
    # OSCSender only sends on change, so a value that starts at its final
    # number would never reach Blender: jitter every value for 2 s at load,
    # toward the middle of its range. Each value is clamped to the range
    # Blender takes, so a Global dragged past 1 in Magic cannot overdrive it.
    def out(addr):
        top = READOUT[addr][0]
        jitter = "if(Clock < 2, if(x > %g, -1, 1)*0.001*frac(Clock*13), 0)" % (top / 2)
        return [ex("min(%g, max(0, x + %s))" % (top, jitter))]
    senders = [p.node("OSCSender", [p.iv("IP Addr.", ip), p.iv("Port", port), p.iv("Message", addr),
                                    p.iv("Value", 0, ("global", g), out(addr))]) for addr, g in OSC_OUT]
    p.fill_scene(oscout, senders, senders, {n.get("id"): (15 + (i % 5) * 200, 15 + (i // 5) * 160) for i, n in enumerate(senders)})

    # Monitor: one bar per analysis Global, bottom-anchored, labelled.
    mon_nodes, mon_roots, pos = [], [], {}
    for i, g in enumerate(METERS):
        xpos = -1.6 + i * 3.2 / (len(METERS) - 1)
        bar = [p.node("Polygon", [p.iv("Sides", 4), p.iv("Fit", 1)]),
               p.node("Scale", [p.iv("X", 0.035), p.link("Y", 0.01, g, "max(0.005, x*0.8)"), p.iv("Z", 1), p.iv("X For All", 0)]),
               p.node("Translate", [p.iv("X", round(xpos, 3)), p.link("Y", 0, g, "max(0.005, x*0.8) - 0.85"), p.iv("Z", 0)]),
               p.node("ColorHSB", [p.iv("Hue", round(i / len(METERS), 3)), p.iv("Saturation", 0.8), p.iv("Brightness", 1),
                                   p.iv("Alpha", 0.85), p.iv("Override", 1)])]
        label = [p.node("Text", [p.iv("Text", g), p.iv("Font", "Verdana"), p.iv("Align", 0), p.iv("Size", 4),
                                 p.iv("Bold", 1), p.iv("Italic", 0), p.iv("Underline", 0), p.iv("Line #", -1)]),
                 p.node("Translate", [p.iv("X", round(xpos, 3)), p.iv("Y", -0.93), p.iv("Z", 0)])]
        for j, n in enumerate(bar + label):
            pos[n.get("id")] = (15 + j * 200, 15 + i * 120)
        mon_nodes += bar + label
        mon_roots += [chain(*bar), chain(*label)]
    p.fill_scene(monitor, mon_roots, mon_nodes, pos)

    # Readout: one line per address with the value being sent, yellow while
    # it differs from the scene default. Text cannot print a number, so each
    # row holds every displayable value as a line and Line # picks one.
    rd_nodes, rd_roots, pos = [], [], {}
    rows = [(addr, g, READOUT[addr]) for addr, g in OSC_OUT]
    gap = min(0.062, 1.8 / (len(rows) - 1))  # every row between y 0.9 and -0.9
    for i, (addr, g, (top, step, default)) in enumerate(rows):
        digits = len(("%g" % step).partition(".")[2])
        lines = "\\\\".join("%-15s%7.*f" % (addr, digits, k * step) for k in range(int(round(top / step)) + 1))
        n, r = caption_text(p, lines, 2.2, 1.42, round(0.9 - i * gap, 3), (g, "min(%d, max(0, round(x/%g)))" % (round(top / step), step)),
                     (g, "if(abs(x - %g) > %g, 1, 0)" % (default, step * 1.5)))
        rd_nodes += n
        rd_roots += r
    if captions:
        lines, g = captions
        n, r = caption_text(p, "\\\\".join(lines), 3.2, -0.35, -0.92, (g, None))
        rd_nodes += n
        rd_roots += r
    for j, n in enumerate(rd_nodes):
        pos[n.get("id")] = (15 + (j % 3) * 200, 15 + (j // 3) * 120)
    p.fill_scene(readout, rd_roots, rd_nodes, pos)

    # Master: overlays, program with blackout, OSC senders underneath.
    mon_mod = p.scene_module("Monitor", power=("Monitor", "if(x > 0.5, 1, 0)"))
    rd_mod = p.scene_module("Readout", power=("Readout", "if(x > 0.5, 1, 0)"))
    prog_mod = p.scene_module("Program")
    blackout = p.node("Transparency", [p.link("Amount", 0, "Blackout")], children=[prog_mod])
    osc_mod = p.scene_module("OSC Out")
    m_nodes = [mon_mod, rd_mod, prog_mod, blackout, osc_mod]
    p.fill_scene(master, [mon_mod, rd_mod, blackout, osc_mod], m_nodes,
                 {mon_mod.get("id"): (215, 15), rd_mod.get("id"): (415, 15), prog_mod.get("id"): (15, 160),
                  blackout.get("id"): (215, 160), osc_mod.get("id"): (215, 305)})
    return project_xml(p, globals_el, audio, output)


def caption_text(p, text, size, x, y, line, highlight=None):
    """Text at (x, y) over a black drop shadow. line: (global, expr) linked to
    Line #; highlight: (global, expr) linked to the yellow saturation."""
    nodes, roots = [], []
    for dx, bright in ((0.005, 0), (0, 1)):
        sat = p.link("Saturation", 0, *highlight) if highlight and bright else p.iv("Saturation", 0)
        n = [p.node("Text", [p.iv("Text", text), p.iv("Font", "Menlo"), p.iv("Align", 0), p.iv("Size", size), p.iv("Bold", 1),
                             p.iv("Italic", 0), p.iv("Underline", 0), p.link("Line #", 0, *line)]),
             p.node("ColorHSB", [p.iv("Hue", 0.14), sat, p.iv("Brightness", bright), p.iv("Alpha", 0.9), p.iv("Override", 1)]),
             p.node("Translate", [p.iv("X", x + dx), p.iv("Y", y - dx), p.iv("Z", 0)])]
        nodes += n
        roots.append(chain(*n))
    return nodes, roots


def project_xml(p, globals_el, audio=None, output=None):
    root = ET.Element("Project", looping="1" if audio else "0", playlistChangesTabs="0", videoSharing="0", videoSharingWidth="1280",
                      videoSharingHeight="720", fixedMagicSize="1", fontSize="13", audioFilePanelHeight="0",
                      version="1.5", actualVersion="3")
    if output:
        root.set("videoSharing", "1")
        root.set("videoSharingName", output)
        root.set("videoSharingWidth", "1920")
        root.set("videoSharingHeight", "1080")
    ET.SubElement(root, "RenderSettings", width="1920", height="1080", fps="60", duration="600", usePlaylist="0",
                  format="1001", quality="7", outputFolder="", outputFile="")
    ET.SubElement(root, "PlaylistMidiConfig", layerID="-1", featureString="", feature="-1", subFeature="-1",
                  prevLayerID="-1", prevFeatureString="", prevFeature="-1", prevSubFeature="-1", nextLayerID="-1",
                  nextFeatureString="", nextFeature="-1", nextSubFeature="-1", playlistStartTimes="0",
                  playlistMidiConfig="0", playlistDetails="1", playlistTransitions="0")
    files = ET.SubElement(root, "SoundFiles")
    afiles = ET.SubElement(root, "AudioFiles", version="2")
    if audio:
        for parent, tag in ((files, "SoundFile"), (afiles, "AudioFile")):
            ET.SubElement(parent, tag, filename=os.path.abspath(audio), isMuted="0", isSoloed="0", offset="0")
    tracks = ET.SubElement(root, "Tracks")
    ET.SubElement(tracks, "Track", id="1", channel="0", isInput="1", name="BlackHole 2ch 0", deviceName="BlackHole 2ch")
    ET.SubElement(tracks, "Track", id="2", channel="1", isInput="1", name="BlackHole 2ch 1", deviceName="BlackHole 2ch")
    for ch in range(17):
        ET.SubElement(tracks, "Track", id=str(3 + ch), channel=str(ch), isInput="1", name="IAC Driver MagicBus",
                      deviceName="", isMidi="1")
    ET.SubElement(tracks, "Track", id="20", channel=str(OSC_IN_PORT), isInput="1", name="Open Sound Control",
                  deviceName="", isOSC="1")
    if audio:
        for ch in range(2):
            ET.SubElement(tracks, "Track", id=str(21 + ch), channel=str(ch), isInput="0",
                          name="%s %d" % (os.path.basename(audio), ch), soundFileIndex="0", audioFileIndex="0")
    layers = ET.SubElement(root, "Layers")
    ET.SubElement(layers, "Layer", name="Source 0", id=str(AUDIO_LAYER), trackID="21" if audio else "1", gain="0", gainVisible="0")
    ET.SubElement(layers, "Layer", name="OSC In", id=str(OSC_LAYER), trackID="20", gain="0", gainVisible="0")

    scenes = ET.SubElement(root, "Scenes")
    tabs = ET.Element("Tabs")
    for sid, (name, rnode, nodes, positions) in enumerate(p.scenes):
        s = ET.SubElement(scenes, "Scene", name=name, id=str(sid), isPostProcessing="0",
                          excludedFromPostProcessing="0", keepInGfxMem="0")
        ET.SubElement(s, "Root").append(rnode)
        nl = ET.SubElement(s, "Nodes")
        for n in nodes:
            nl.append(n)
        tab = ET.SubElement(tabs, "Tab")
        for n in [rnode] + nodes:
            x, y = positions[n.get("id")]
            ET.SubElement(tab, "Node", x=str(x), y=str(y), id=n.get("id"), expanded="1", annotation="",
                          annotationVisible="0")
    pl = ET.SubElement(ET.SubElement(root, "Playlists"), "Playlist", linkAutoAdvance="0", random="0")
    ET.SubElement(pl, "Scene", id="0", style="1", duration="2", sceneDuration="30", enabled="1", layerID="-1")
    root.append(tabs)
    tv = ET.SubElement(root, "TabsVisible")
    sti = ET.SubElement(root, "SceneTreeItems")
    for sid in range(len(p.scenes)):
        ET.SubElement(tv, "TabVis", sceneID=str(sid))
        ET.SubElement(sti, "SceneTreeItem", id=str(sid), group="0")
    root.append(globals_el)
    ET.indent(root, "  ")
    return b'<?xml version="1.0" encoding="UTF-8"?>\n\n' + ET.tostring(root, encoding="utf-8") + b"\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", type=int, default=9201, help="OSC target: 9201 = Blender bridge, 9200 = lab.py relay")
    ap.add_argument("--ip", default="127.0.0.1")
    ap.add_argument("--syphon", default="CAM_OUT - Blender", help='SyphonClient server, "<sender> - <app>"')
    ap.add_argument("--synthetic", action="store_true", help="test build: synthetic EDM signal and timed controls, no audio")
    ap.add_argument("--trails", action="store_true", help="add the Synthwave Trails effect (needs effects/ as a Magic module folder)")
    ap.add_argument("--audio", help="play and analyse this audio file (looped) instead of the BlackHole input")
    ap.add_argument("--out", default=os.path.join(HERE, "projects", "synthwave_pyramids.magic"))
    a = ap.parse_args()
    xml = build(a.port, a.ip, a.syphon, synthetic_globals() if a.synthetic else GLOBALS, audio=a.audio, trails_fx=a.trails)
    with open(a.out, "wb") as f:
        f.write(HEADER + zlib.compress(xml, 9))
    print("wrote %s (%d globals, %d OSC addresses -> %s:%d)" % (a.out, len(GLOBALS), len(OSC_OUT), a.ip, a.port))


if __name__ == "__main__":
    main()
