"""Builds projects/edm_analysis.magic: three EDM audio analysis variants for
Magic Music Visuals 3, each a scene of labelled meters, plus a Compare scene
that shows them side by side.

All variants share A's levels, onsets, vocals, hard bass and beat clock (a
tempo bank of resonators seeding an adaptive oscillator); they differ in
how they find the song structure:
- A: buildup from rising brightness, treble and snare rate; drop = the first
  strong kick after 3.5 s without one; breakdown = no strong kick for 4 beats.
- B: buildup from low bass presence with rising brightness or hit density,
  full after 24 beats; drop = low end jumping back (1.6x its 8 s mean) after a
  gap or a buildup; energy relative to a 45 s mean.
- C: the same buildup, full after 16 beats; A's drop.

Usage:
  python3 edm_analysis_magic.py [-o projects/edm_analysis.magic] [--tap]
  python3 edm_analysis_magic.py record PORT SECONDS OUT.jsonl
  python3 edm_analysis_magic.py sim REC.jsonl [--fps 120] [--series NAME,...]

--tap powers the OSC Tap scene: raw inputs to /raw/<Global> and the variant
picked by the TapVar Global (0..2) to /o/<signal>, at 127.0.0.1:TAP_PORT.
`record` logs that with timestamps; `sim` replays the raw inputs through the
Global expressions (double-buffered like Magic) and prints what each variant
detected.
"""
import argparse
import json
import math
import os
import re
import socket
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import magicproj as mp  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "projects", "edm_analysis.magic")
TAP_PORT = 9311
AUDIO_DEVICE = "BlackHole 2ch"
VARIANTS = "abc"
NAMES = {"a": "A  FLUX + PLL", "b": "B  A + MEDIUM BUILD + LOW-END DROP", "c": "C  A + FAST BUILD"}
BLURB = {"a": "log band flux onsets, tempo bank + phase-locked loop, build from brightness and snare rate",
         "b": "build when bass presence is low and brightness or hit density rise (24 beats), drop when the low end jumps back",
         "c": "build when bass presence is low and brightness or hit density rise (16 beats), A's drop"}

# (signal, label, kind): kind bar = level 0..1, lamp = onset envelope.
SIGNALS = [
    ("Sub", "SUB 20-80", "bar"), ("Bass", "BASS 80-320", "bar"), ("Hard", "HARD BASS", "bar"),
    ("Vol", "VOLUME", "bar"), ("VolNB", "NO-BASS VOL", "bar"), ("HatLvl", "HAT LEVEL", "bar"),
    ("Vocal", "VOCALS", "bar"), ("Width", "WIDTH", "bar"), ("Energy", "ENERGY /AVG", "bar"),
    ("Bright", "BRIGHT", "bar"),
    ("Kick", "KICK", "lamp"), ("Snare", "SNARE", "lamp"), ("Hat", "HAT", "lamp"), ("Beat", "BEAT", "lamp"),
    ("Phase", "PHASE", "hbar"), ("Conf", "LOCK", "hbar"), ("BPM", "BPM", "bpm"), ("BarPos", "BAR", "bar4"),
    ("Build", "BUILDUP", "hbar"), ("Break", "BREAKDOWN", "hbar"), ("Drop", "DROP", "hbar"),
]
CUSTOM = {"VocL": (300, 3400), "VocR": (300, 3400)}
MANUAL = {"TapVar": 0, "Lead": 0.04}


# --- Expression helpers (calculations) -----------------------------------------

def sm(v, tau):
    """One-pole smoother of `v`, time constant `tau` s, independent of frame rate."""
    return "y + ((%s) - y)*min(1, Dt/%g)" % (v, tau)


def warm(v, tau):
    """Long average that warms up from the first seconds after load."""
    return "y + ((%s) - y)*min(1, Dt/min(%g, 0.5 + Run))" % (v, tau)


def env(v, att, rel):
    return "var v := %s; y + (v - y)*min(1, Dt/if(v > y, %g, %g))" % (v, att, rel)


def G(name, expr):
    return (name, "calc", [("Expression", expr)])


def S(name, source):
    return (name, source, [])


# --- Globals (calculations) ----------------------------------------------------

def base():
    g = [("Clock", "calc", [("Increase", 1)]), G("ClockPrev", "Clock"),
         G("Dt", "max(0.0005, min(0.05, Clock - ClockPrev))")]
    for ch, c in ((0, "L"), (1, "R")):
        g += [S("%s%d" % (c, i), "audio:Source %d:Freq. Range:%d" % (ch, i)) for i in range(5)]
        g += [S(c + "V", "audio:Source %d:Volume" % ch), S("Voc" + c, "audio:Source %d:Freq. Range:5" % ch)]
    g += [S("Tone", "audio:Source 0:Tone"), S("Pitch", "audio:Source 0:Best Pitch")]
    g += [G("S%d" % i, "(L%d + R%d)/2" % (i, i)) for i in range(5)]
    g += [G("Vol", "(LV + RV)/2"), G("Voc", "(VocL + VocR)/2"),
          G("Live", env("if(Vol > 0.03, 1, 0)", 0.05, 1.5)),
          # Seconds since the music (re)started: long averages warm up from there.
          G("Run", "if(Live > 0.5, y + Dt, 0)"),
          # Level difference of the mid/high bands minus that of the (mono) sub.
          G("WRaw", "max(0, (abs(L2 - R2)/max(L2 + R2, 0.01) + abs(L3 - R3)/max(L3 + R3, 0.01) + "
                    "abs(L4 - R4)/max(L4 + R4, 0.01))/3 - abs(L0 - R0)/max(L0 + R0, 0.01))"),
          ("TapVar", None, []), G("TapJ", "1 - y"),
          # Seconds the shown beat phase runs ahead, to cover Magic's analysis latency.
          ("Lead", None, [])]
    # Per-band rise of log level per audio update (BU = 1 on update frames).
    g += [G("BC%d" % i, "log(1 + 20*S%d)/log(21)" % i) for i in range(5)]
    g += [G("BP%d" % i, "BC%d" % i) for i in range(5)]
    g += [G("BU", "if(BC3 != BP3 or BC4 != BP4, 1, 0)")]
    g += [G("BF%d" % i, "max(0, BC%d - BP%d)" % (i, i)) for i in range(5)]
    return g + tempo_bank()


BANK = 24  # resonators, 90-180 BPM in steps of 2^(1/24)


def bank_period(i):
    return 0.3334 * 2 ** (i / BANK)


def tempo_bank():
    """Shared tempo acquisition: leaky resonators (Scheirer) on the low-band
    onset strength. The strongest gives the period, refined between its
    neighbours, and the beat phase from its angle."""
    g = [G("TC", "log(1 + 10*(L0 + R0 + L1 + R1))"), G("TP", "TC"),
         G("TM", "if(TC != TP, y + (max(0, TC - TP) - y)*0.0053, y)"),
         # Onset strength per audio update, relative to its ~2 s mean, capped.
         G("TFa", "if(TC != TP, min(4, max(0, TC - TP)/max(TM, 0.0001)), 0)"), G("TFn", "TFa*TFa")]
    for i in range(BANK):
        w = "2*pi*Clock/%.5f" % bank_period(i)
        g += [G("Rc%d" % i, "y*exp(-Dt/10) + TFn*cos(%s)" % w), G("Rs%d" % i, "y*exp(-Dt/10) + TFn*sin(%s)" % w),
              G("RM%d" % i, "sqrt(Rc%d*Rc%d + Rs%d*Rs%d)" % (i, i, i, i))]
    pick = lambda f: " + ".join("if(abs(TIdx - %d) < 0.5, %s, 0)" % (i, f(i)) for i in range(BANK))
    g += [G("TKey", "max(%s)" % ", ".join("floor(1000*RM%d)*100 + %d" % (i, i) for i in range(BANK))),
          G("TIdx", "TKey - 100*floor(TKey/100)"),
          G("TMb", pick(lambda i: "RM%d" % i)),
          G("TMl", pick(lambda i: "RM%d" % max(0, i - 1))), G("TMr", pick(lambda i: "RM%d" % min(BANK - 1, i + 1))),
          G("TAng", pick(lambda i: "atan2(Rs%d, Rc%d)" % (i, i))),
          G("TMavg", "(%s)/%d" % (" + ".join("RM%d" % i for i in range(BANK)), BANK)),
          G("TD", "var c := TMl - 2*TMb + TMr; if(c < -0.000001, max(-0.5, min(0.5, 0.5*(TMl - TMr)/c)), 0)"),
          G("TPer", "0.3334*pow(2, (TIdx + TD)/%d)" % BANK),
          G("TPh", "var q := Clock/(0.3334*pow(2, TIdx/%d)) - TAng/(2*pi); q - floor(q)" % BANK),
          G("TConf", "min(1, max(0, (TMb/max(TMavg, 0.000001) - 1.3)/1.5))")]
    return g


def flux_onset(p, name, band, ratio, floor, refr, k, gate="1"):
    """Onset when the per-update rise of log(1 + 20*band) beats `ratio` times
    its mean rise (~0.2 s) plus `floor`; `refr` s refractory; envelope decays at `k`/s."""
    n = p + name
    return [G(n + "C", "log(1 + 20*%s)/log(21)" % band), G(n + "P", n + "C"),
            G(n + "U", "if(%sC != %sP, 1, 0)" % (n, n)), G(n + "F", "max(0, %sC - %sP)" % (n, n)),
            G(n + "M", "if(%sU > 0.5, y + (%sF - y)*0.05, y)" % (n, n)),
            G(n + "On", "if(%sU > 0.5 and %sF > %sM*%g + %g and Clock - %sT > %s and Live > 0.5 and %s, 1, 0)"
              % (n, n, n, ratio, floor, n, refr, gate)),
            G(n + "T", "if(%sOn > 0.5, Clock, y)" % n), G(n, "max(%sOn, y*exp(-Dt*%g))" % (n, k))]


def peak_onset(p, name, flux, frac, dec, floor, refr, k, gate="1"):
    """Onset when `flux` (per update) reaches `frac` of its recent maximum
    (decaying over `dec` s): only the strongest transients count (Dixon)."""
    n = p + name
    return [G(n + "F", flux), G(n + "G", "max(%sF, y*exp(-Dt/%g))" % (n, dec)),
            G(n + "On", "if(BU > 0.5 and %sF > %g*%sG and %sF > %g and Clock - %sT > %s and Live > 0.5 and %s, 1, 0)"
              % (n, frac, n, n, floor, n, refr, gate)),
            G(n + "T", "if(%sOn > 0.5, Clock, y)" % n), G(n, "max(%sOn, y*exp(-Dt*%g))" % (n, k))]


def ratio_onset(p, name, x, mean_tau, ratio, floor, refr, k, rearm, gate="1"):
    """Onset when `x` exceeds `ratio` times its `mean_tau` mean and `floor`;
    re-armed once x falls below `rearm` times the mean."""
    n = p + name
    return [G(n + "N", x), G(n + "M", sm(n + "N", mean_tau)),
            G(n + "On", "if(%sN > %sM*%g and %sN > %g and %sArm > 0.5 and Clock - %sT > %s and Live > 0.5 and %s, 1, 0)"
              % (n, n, ratio, n, floor, n, n, refr, gate)),
            G(n + "Arm", "if(%sOn > 0.5, 0, if(%sN < %sM*%g, 1, y))" % (n, n, n, rearm)),
            G(n + "T", "if(%sOn > 0.5, Clock, y)" % n), G(n, "max(%sOn, y*exp(-Dt*%g))" % (n, k))]


def pll(p, drive, kph, kp):
    """Adaptive oscillator (Large & Kolen): `drive` (onset strength per audio
    update) near the beat, weighted by a von Mises window, pulls the phase by
    `kph` and the period by `kp` of its error. Re-seeded from the tempo bank
    when coherence stays low or the period strays 8 % for 4 s."""
    w = "exp(4*(cos(2*pi*%s) - 1))"
    return [G(p + "Ph", "var p := y + Dt/{p}Per; var q := p - floor(p); var r := q - {k}*{d}*{w}*sin(2*pi*q)/(2*pi); "
                        "if({p}Seed > 0.5, TPh, r - floor(r))".format(p=p, k=kph, d=drive, w=w % "q")),
            G(p + "Per", "if(y < 0.3 or {p}Seed > 0.5, TPer, max(0.3334, min(0.6666, "
                         "y*(1 + {k}*{d}*{w}*sin(2*pi*{p}Ph)/(2*pi)))))".format(p=p, k=kp, d=drive, w=w % (p + "Ph"))),
            G(p + "OnB", "y + (%s*%s - y)*min(1, Dt/4)" % (drive, w % (p + "Ph"))),
            G(p + "All", "y + (%s - y)*min(1, Dt/4)" % drive), G(p + "Coh", "%sOnB/max(%sAll, 0.001)" % (p, p)),
            G(p + "Low", "if({p}Seed > 0.5, 0, if({p}Coh < 0.15 or abs({p}Per/TPer - 1) > 0.08, y + Dt, 0))".format(p=p)),
            G(p + "Seed", "if(%sLow > 4, 1, 0)" % p), G(p + "Conf", "min(1, 2.5*%sCoh)" % p)]


def on_beat(p, conf=0.3, width=0.15):
    """Gate: unlocked, or within `width` of a beat of the variant's own phase."""
    return "(%sConf < %g or abs(%sPh - round(%sPh)) < %g)" % (p, conf, p, p, width)


def clock_outputs(p):
    """Shown phase (Lead s ahead), beat events, count, pulse, BPM and bar
    position from the variant's internal phase <p>Ph and period <p>Per."""
    return [G(p + "Phase", "var q := %sPh + Lead/%sPer; q - floor(q)" % (p, p)), G(p + "PhasePrev", p + "Phase"),
            G(p + "Tick", "if(%sPhase < %sPhasePrev - 0.5, 1, 0)" % (p, p)),
            G(p + "Beats", "y + %sTick" % p),
            G(p + "Beat", "exp(-%sPhase*%sPer*10)*min(1, 0.3 + %sConf)" % (p, p, p)),
            G(p + "BPM", "60/%sPer" % p),
            # The drop is the downbeat: the beat it falls on, or the next one.
            G(p + "BeatOff", "if(%sDropEv > 0.5, %sBeats + if(%sPhase > 0.5, 1, 0), y)" % (p, p, p)),
            G(p + "BarPos", "(%sBeats - %sBeatOff) %% 4" % (p, p))]


def drop_outputs(p, hold):
    return [G(p + "DropT", "if(%sDropEv > 0.5, Clock, y)" % p), G(p + "Drop", "max(%sDropEv, y - Dt/%s)" % (p, hold))]


DROP_OK = "y < 0.5 and Clock > 8 and ({p}DropT == 0 or Clock - {p}DropT > 15)"


def variant_a():
    p = "a"
    g = []
    for name, src in (("Sub", "S0"), ("Bass", "S1"), ("Vol", "Vol"), ("VolNB", "(S2 + S3 + S4)/3"), ("HatLvl", "S4")):
        g += [G(p + name + "Avg", warm(src, 8)), G(p + name, env("min(1, (%s)/(2*max(%sAvg, 0.005)))" % (src, p + name), 0.01, 0.15))]
    # Kick: low-band flux on the beat, at least half the strongest of the
    # last 4 s, at most one per 0.6 beat.
    g += flux_onset(p, "Kick", "(S0 + S1)", 1.5, 0.01, "0.6*aPer", 9, on_beat(p, 0.3, 0.1) + " and aKickF > 0.5*aKickG")
    g += [G("aKickG", "max(aKickF, y*exp(-Dt/4))")]
    # Snare/clap: body (320-1.2k) and crack (1.2-5k) rising together, among
    # the strongest of the last 4 s. Hat: 5-20k rising without a low hit.
    g += peak_onset(p, "Snare", "sqrt(BF2*BF3)", 0.7, 4, 0.01, 0.2, 12)
    g += peak_onset(p, "Hat", "if(BF0 + BF1 < 0.02, BF4, 0)", 0.7, 2, 0.01, 0.08, 18)
    g += [
        # Hard bass: bass body and low mids (harmonics of a distorted bass)
        # high against the sub, compared with the track's own ratio.
        G("aBody", sm("S1 + S2", 0.3)), G("aS0s", sm("S0", 0.3)),
        # Log ratio, averaged only while the sub is there: without sub the
        # ratio explodes and would swamp the average.
        G("aHR", "log(max(aBody, 0.005)/max(aS0s, 0.005))"),
        G("aHRAvg", "if(aS0s > 0.5*aSubL, %s, y)" % warm("aHR", 20)),
        # Needs real sub and bass (against their 30 s means) and 6 s of music,
        # so a sparse intro or a song start does not read as hard bass.
        G("aBassL", warm("S1", 30)),
        # 0.4 = the track's typical ratio; 1.65x that ratio reads 1.
        G("aHard", env("min(1, max(0, 0.4 + 1.2*(aHR - aHRAvg)))*min(1, 2*aBass)*"
                       "min(1, aS0s/max(0.5*aSubL, 0.08))*min(1, S1/max(0.5*aBassL, 0.01))*if(Run > 6, 1, 0)", 0.8, 1.5)),
        G("aVocAvg", warm("Voc", 30)),
        G("aVocal", env("min(1, max(0, (Voc/max(aVocAvg, 0.005) - 0.5*(S1/max(aBassAvg, 0.005) + "
                        "S4/max(aHatLvlAvg, 0.005)))*3))*Live", 0.15, 0.6)),
        G("aWidth", env("min(1, 3*WRaw)", 0.2, 0.5)),
        G("aEn", sm("0.4*S0 + 0.25*S1 + 0.15*S2 + 0.12*S3 + 0.08*S4", 0.5)), G("aEnL", warm("aEn", 30)),
        G("aEnergy", "min(1, aEn/(2*max(aEnL, 0.005)))"),
        G("aBright", sm("min(1, max(0, (Tone - 0.3)/0.4))", 0.2)),
    ]
    g += pll(p, "TFa", 0.1, 0.01)
    g += clock_outputs(p)
    g += [
        # Structure keyed on strong kicks (sub above 60 % of its 30 s mean).
        G("aSubL", warm("S0", 30)), G("aLowS", sm("S0 + S1", 0.5)), G("aLowL", warm("S0 + S1", 30)),
        G("aVolL", warm("Vol", 30)),
        G("aStrong", "if(aKickOn > 0.5 and S0 > 0.6*aSubL, 1, 0)"), G("aSKT", "if(aStrong > 0.5, Clock, y)"),
        G("aGap", "Clock - aSKT"),
        G("aTone2", sm("Tone", 2)), G("aTone8", sm("Tone", 8)), G("aAir2", sm("S4", 2)), G("aAir8", sm("S4", 8)),
        G("aSnRate", "y + (aSnareOn/Dt - y)*min(1, Dt/2)"), G("aSnRateL", warm("aSnRate", 10)),
        G("aRise", "max(0, aTone2 - aTone8)*12 + max(0, aSnRate/max(aSnRateL, 0.5) - 1)*0.6 + "
                   "max(0, aAir2/max(aAir8, 0.01) - 1)*0.8"),
        G("aBuild", env("min(1, aRise)*if(aGap > 1.5, 1, 0.5)*(1 - min(1, 2*aDrop))*if(Run > 8, 1, 0)", 1.0, 0.5)),
        G("aBreak", env("if(aGap > 4*aPer and aLowS < 0.6*aLowL and Vol > 0.25*aVolL, 1, 0)*(1 - aBuild)", 1.0, 0.3)),
        G("aDropEv", "if(aStrong > 0.5 and Clock - aSKT > 3.5 and " + DROP_OK.format(p=p) + ", 1, 0)"),
    ]
    g += drop_outputs(p, 4)
    return g


SHARED = ("Sub", "Bass", "Hard", "Vol", "VolNB", "HatLvl", "Vocal", "Width", "Bright", "Kick", "KickOn", "Snare",
          "SnareOn", "Hat", "HatOn", "Ph", "Per", "Conf")


def presence_build(p, beats):
    """Buildup: sub presence under 35 % of typical (Synesthesia-style
    presence, 1 s attack, 3 s release) while brightness or the hit density
    rise; full after `beats` beats. Breakdown: sub presence under 20 % for 4 beats."""
    return [G(p + "SubTrack", warm("S0", 30)), G(p + "SubPres", env("S0/max(%sSubTrack, 0.005)/2" % p, 1, 3)),
            G(p + "HD", "y + ((aKickOn + aSnareOn + aHatOn)/Dt - y)*min(1, Dt/2)"), G(p + "HDL", sm(p + "HD", 6)),
            G(p + "Br2", sm("Tone", 2)), G(p + "Br6", sm("Tone", 6)),
            G(p + "BuildT", "if({p}SubPres < 0.35 and Run > 8 and ({p}Br2 > {p}Br6 + 0.005 or {p}HD > {p}HDL*1.15), "
                            "y + Dt, max(0, y - Dt*0.5))".format(p=p)),
            G(p + "Build", "min(1, {p}BuildT/({n}*aPer))*if({p}SubPres < 0.35, 1, 0)*(1 - min(1, 2*{p}Drop))".format(p=p, n=beats)),
            G(p + "VolTrack", warm("Vol", 30)),
            G(p + "BrkT", "if({p}SubPres < 0.2 and Vol > 0.2*{p}VolTrack, y + Dt, 0)".format(p=p)),
            G(p + "Break", env("if(%sBrkT > 4*aPer, 1, 0)*(1 - %sBuild)" % (p, p), 0.5, 0.3))]


def variant_b():
    p = "b"
    g = [G(p + n, "a" + n) for n in SHARED]
    g += clock_outputs(p)
    g += [G("bEn", sm("Vol", 1)), G("bEnL", warm("bEn", 45)), G("bEnergy", "min(1, bEn/(2*max(bEnL, 0.005)))")]
    g += presence_build(p, 24)
    g += [
        # Drop: the low end (0.1 s) jumps to 1.6x its 8 s mean and 70 % of its
        # 30 s mean, within 2 s of a gap in it or during a buildup.
        G("bLowF", sm("S0 + S1", 0.1)), G("bLow8", warm("S0 + S1", 8)), G("bLowL", warm("S0 + S1", 30)),
        G("bGapT", "if(bLowF < 0.35*bLowL, Clock, y)"),
        G("bDropEv", "if(bLowF > 1.6*bLow8 and bLowF > 0.7*bLowL and (Clock - bGapT < 2 or bBuild > 0.3) and "
                     + DROP_OK.format(p=p) + ", 1, 0)"),
    ]
    g += drop_outputs(p, 4)
    return g


def variant_c():
    p = "c"
    g = [G(p + n, "a" + n) for n in SHARED + ("Energy", "DropEv")]
    g += clock_outputs(p)
    g += presence_build(p, 16)
    g += drop_outputs(p, 4)
    return g


def all_globals():
    return base() + variant_a() + variant_b() + variant_c()


# --- Scenes (calculations) -----------------------------------------------------

HUES = {"bar": 0.55, "lamp": 0.08, "hbar": 0.8, "bar4": 0.33, "bpm": 0.14}


class Draw:
    """Rectangles and text in Magic coordinates (y -1..1, x about -1.78..1.78)."""

    def __init__(self, s):
        self.s, self.outs = s, []
        self.poly = s.node("Polygon", {"Sides": 4, "Fit": 1})

    def rect(self, x, y, w, h, hue, bri=1.0, alpha=1.0, fill=None, horiz=False):
        """Bottom-left (x, y). fill: Global name; the rectangle grows with it (0..1)."""
        sx, sy, tx, ty = w / 2, h / 2, x + w / 2, y + h / 2
        v = "max(0.002, min(1, x))"
        if fill and horiz:
            sx = ("global:" + fill, [("Expression", "%s*%g" % (v, w / 2))])
            tx = ("global:" + fill, [("Expression", "%g + %s*%g" % (x, v, w / 2))])
        elif fill:
            sy = ("global:" + fill, [("Expression", "%s*%g" % (v, h / 2))])
            ty = ("global:" + fill, [("Expression", "%g + %s*%g" % (y, v, h / 2))])
        sc = self.s.node("Scale", {"X": sx, "Y": sy, "Z": 1, "X For All": 0}, inputs=[self.poly])
        tr = self.s.node("Translate", {"X": tx, "Y": ty, "Z": 0}, inputs=[sc])
        col = self.s.node("ColorHSB", {"Hue": hue, "Saturation": 0.85 if bri != 1.0 or fill else 0.0, "Brightness": bri,
                                       "Alpha": alpha, "Override": 1, "Additive": 0}, inputs=[tr])
        self.outs.append(col)
        return col

    def lamp(self, x, y, w, h, hue, glob, expr="0.12 + 0.88*min(1, x)"):
        sc = self.s.node("Scale", {"X": w / 2, "Y": h / 2, "Z": 1, "X For All": 0}, inputs=[self.poly])
        tr = self.s.node("Translate", {"X": x + w / 2, "Y": y + h / 2, "Z": 0}, inputs=[sc])
        col = self.s.node("ColorHSB", {"Hue": hue, "Saturation": 0.9, "Brightness": ("global:" + glob, [("Expression", expr)]),
                                       "Alpha": 1, "Override": 1, "Additive": 0}, inputs=[tr])
        self.outs.append(col)

    def text(self, x, y, txt, size=2.4, bri=0.85, line=None, center=False):
        """Left edge at x unless `center`; Magic centres text on its position
        and a bold Menlo glyph is about 0.72 of its height (size = % of frame height)."""
        if not center:
            x += 0.0072 * size * max(len(s) for s in txt.split("\\\\")) if not line else 0.0072 * size * 3
        t = self.s.node("Text", {"Text": txt, "Font": "Menlo", "Align": 0, "Size": size, "Bold": 1, "Italic": 0,
                                 "Underline": 0, "Line #": line if line else -1})
        col = self.s.node("ColorHSB", {"Hue": 0, "Saturation": 0, "Brightness": bri, "Alpha": 1, "Override": 1,
                                       "Additive": 0}, inputs=[t])
        tr = self.s.node("Translate", {"X": x, "Y": y, "Z": 0}, inputs=[col])
        self.outs.append(tr)


BPM_LINES = "\\\\".join("%d" % b for b in range(60, 201))
BPM_LINE = [("Expression", "min(140, max(0, round(x) - 60))")]


def meter_scene(b, p):
    s = b.scene(NAMES[p].split()[0] + " " + NAMES[p].split(None, 1)[1].title())
    d = Draw(s)
    d.text(-1.7, 0.9, NAMES[p], 4)
    d.text(-1.7, 0.8, BLURB[p], 1.5, 0.6)
    bars = [x for x in SIGNALS if x[2] == "bar"]
    for i, (sig, label, _) in enumerate(bars):
        x = -1.7 + i * 0.205
        d.rect(x, -0.05, 0.15, 0.7, 0, 0.18)
        d.rect(x, -0.05, 0.15, 0.7, HUES["bar"] - i * 0.04, 1.0, fill=p + sig)
        d.text(x + 0.075, -0.12, label.replace(" ", "\\\\"), 1.8, center=True)
    lamps = [x for x in SIGNALS if x[2] == "lamp"]
    for i, (sig, label, _) in enumerate(lamps):
        x, y = 0.45 + (i % 2) * 0.62, 0.38 - (i // 2) * 0.43
        d.lamp(x, y, 0.55, 0.3, HUES["lamp"] + i * 0.06, p + sig)
        d.text(x, y - 0.06, label, 2.4)
    rows = [x for x in SIGNALS if x[2] == "hbar"]
    for i, (sig, label, _) in enumerate(rows):
        y = -0.42 - i * 0.12
        d.text(-1.7, y + 0.06, label, 2.4)
        d.rect(-1.1, y, 2.6, 0.07, 0, 0.18)
        d.rect(-1.1, y, 2.6, 0.07, HUES["hbar"] - i * 0.12, 1.0, fill=p + sig, horiz=True)
    for i in range(4):
        d.lamp(0.45 + i * 0.31, -0.3, 0.26, 0.1, HUES["bar4"], p + "BarPos", "if(abs(x - %d) < 0.5, 1, 0.12)" % i)
    d.text(0.45, -0.33, "BAR 1 2 3 4", 2.2)
    d.text(1.15, 0.93, "BPM", 2.4)
    d.text(1.15, 0.82, BPM_LINES, 6, 1.0, ("global:" + p + "BPM", BPM_LINE))
    d.lamp(1.15, 0.7, 0.55, 0.04, HUES["bpm"], p + "Beat")
    s.output(*reversed(d.outs))
    return s


COMPARE = [("Kick", "lamp"), ("Snare", "lamp"), ("Hat", "lamp"), ("Beat", "lamp"), ("Vocal", "bar"), ("Hard", "bar"),
           ("Build", "bar"), ("Break", "bar"), ("Drop", "bar"), ("Energy", "bar")]


def compare_scene(b):
    s = b.scene("Compare")
    d = Draw(s)
    d.text(-1.7, 0.9, "COMPARE  " + " ".join(VARIANTS.upper()), 4)
    for j, (sig, kind) in enumerate(COMPARE):
        d.text(-1.25 + j * 0.27, 0.72, sig.upper(), 2.0)
    d.text(1.5, 0.72, "BPM", 2.0)
    for i, p in enumerate(VARIANTS):
        y = 0.38 - i * 0.4
        d.text(-1.7, y + 0.1, NAMES[p].split()[0], 6, 1.0)
        for j, (sig, kind) in enumerate(COMPARE):
            x = -1.25 + j * 0.27
            if kind == "lamp":
                d.lamp(x, y, 0.22, 0.25, HUES["lamp"] + j * 0.06, p + sig)
            else:
                d.rect(x, y, 0.22, 0.25, 0, 0.18)
                d.rect(x, y, 0.22, 0.25, 0.55 - j * 0.05, 1.0, fill=p + sig)
        d.text(1.5, y + 0.12, BPM_LINES, 5, 1.0, ("global:" + p + "BPM", BPM_LINE))
        d.lamp(1.5, y, 0.25, 0.04, HUES["bpm"], p + "Beat")
    s.output(*reversed(d.outs))
    return s


RAW = ["L0", "L1", "L2", "L3", "L4", "R0", "R1", "R2", "R3", "R4", "LV", "RV", "VocL", "VocR", "Tone", "Pitch"]


def tap_scene(b):
    """OSC senders: raw inputs and the TapVar variant's signals (0 a, 1 b, 2 c)."""
    s = b.scene("OSC Tap")
    outs = []
    jit = [("Expression", "x + 0.00001*TapJ")]
    for r in RAW:
        outs.append(s.node("OSCSender", {"IP Addr.": "127.0.0.1", "Port": TAP_PORT, "Message": "/raw/" + r,
                                         "Value": ("global:" + r, jit)}))
    for sig, _, _ in SIGNALS:
        pick = "if(x < 0.5, a{0}, if(x < 1.5, b{0}, c{0})) + 0.00001*TapJ".format(sig)
        outs.append(s.node("OSCSender", {"IP Addr.": "127.0.0.1", "Port": TAP_PORT, "Message": "/o/" + sig,
                                         "Value": ("global:TapVar", [("Expression", pick)])}))
    outs.append(s.node("OSCSender", {"IP Addr.": "127.0.0.1", "Port": TAP_PORT, "Message": "/o/Clock",
                                     "Value": ("global:Clock",)}))
    s.output(*outs)
    return s


def build(tap=False, tap_var=0, first="b"):
    b = mp.Builder(syphon="edm-analysis", audio_device=AUDIO_DEVICE)
    for name, source, mods in all_globals():
        b.glob(name, MANUAL.get(name, 0), source, mods)
    # Magic opens on the first scene.
    makers = [("compare", lambda: compare_scene(b))] + [(p, lambda p=p: meter_scene(b, p)) for p in VARIANTS]
    makers.sort(key=lambda m: m[0] != first)
    shown = [make() for _, make in makers]
    tsc = tap_scene(b)
    for s in shown:
        s.output(s.scene_module(tsc))
    root = b.build()
    # The tap scene is drawn from every scene and powered only with --tap.
    for iv in mp.global_ivs(root):
        if iv.get("name") in CUSTOM:
            lo, hi = CUSTOM[iv.get("name")]
            iv.set("extraFeature1", str(lo))
            iv.set("extraFeature2", str(hi))
        if iv.get("name") == "TapVar":
            iv.set("value", str(tap_var))
    for n in root.iter("Node"):
        if n.get("pluginName") == "OSC Tap":
            power = mp.param(n, "Power")
            power.set("value", "1" if tap else "0")
    return root


# --- Simulation (calculations) -------------------------------------------------

def _round(v):
    return math.floor(v + 0.5) if v >= 0 else -math.floor(-v + 0.5)


def _if(c, a, b):
    return a if c else b


FUNCS = {"IF": _if, "min": min, "max": max, "abs": abs, "floor": math.floor, "round": _round, "exp": math.exp,
         "log": lambda v: math.log(v) if v > 0 else -1e30, "log2": lambda v: math.log2(v) if v > 0 else -1e30,
         "pow": lambda a, b: a ** b, "sqrt": math.sqrt, "frac": lambda v: v - math.floor(v), "cos": math.cos,
         "sin": math.sin, "atan2": math.atan2, "pi": math.pi}


def py_code(expr):
    """ExprTk (the subset used here) -> Python code that sets __r."""
    stmts = [s.strip() for s in expr.split(";") if s.strip()]
    conv = lambda s: re.sub(r"\bif\s*\(", "IF(", s).replace("^", "**")
    lines = []
    for s in stmts[:-1]:
        m = re.fullmatch(r"var\s+(\w+)\s*:=\s*(.*)", s, re.S)
        lines.append("%s = %s" % (m.group(1), conv(m.group(2))))
    lines.append("__r = " + conv(stmts[-1]))
    return compile("\n".join(lines), expr[:40], "exec")


def simulate(globals_, raw, fps=120.0, keep=None):
    """raw: {Global: [(t, value)]} sorted. Every Global reads the previous
    frame's values (Magic's double buffering). -> {name: [values per frame]}, times."""
    t0 = min(v[0][0] for v in raw.values())
    t1 = max(v[-1][0] for v in raw.values())
    progs = [(n, src, [py_code(e) if k == "Expression" else (k, e) for k, e in mods]) for n, src, mods in globals_]
    env = dict(FUNCS)
    for n, _, _ in globals_:
        env[n] = float(MANUAL.get(n, 0.0))
    idx = {k: 0 for k in raw}
    out = {n: [] for n in (keep or [])}
    times = []
    t = t0
    while t < t1:
        held = {}
        for k, series in raw.items():
            i = idx[k]
            while i + 1 < len(series) and series[i + 1][0] <= t:
                i += 1
            idx[k] = i
            held[k] = series[i][1]
        new = {}
        for n, src, mods in progs:
            x = held.get(n, 0.0) if src not in ("calc", None) else 0.0
            for m in mods:
                if isinstance(m, tuple):
                    x = x + (t - t0) if m[0] == "Increase" else x
                else:
                    env["x"], env["y"] = x, env[n]
                    try:
                        exec(m, env)
                        x = env["__r"]
                    except (ZeroDivisionError, OverflowError, ValueError):
                        x = 0.0
            new[n] = float(x) if src is not None else env[n]
        env.update(new)
        for n in out:
            out[n].append(env[n])
        times.append(t - t0)
        t += 1.0 / fps
    return out, times


def read_rec(path, prefix="/raw/"):
    raw = {}
    for line in open(path):
        t, addr, v = json.loads(line)
        if addr.startswith(prefix) and v is not None:
            raw.setdefault(addr[len(prefix):], []).append((t, v))
    return raw


def summary(out, times, p):
    dur = times[-1] - times[0]
    first = int(len(times) * 0.2)
    rate = lambda n: sum(1 for i in range(first, len(times)) if out[p + n + "On"][i] > 0.5) / (dur * 0.8)
    mean = lambda n: sum(out[p + n][first:]) / (len(times) - first)
    bpm = sorted(out[p + "BPM"][first:])
    drops = [round(times[i], 1) for i in range(1, len(times)) if out[p + "DropEv"][i] > 0.5]
    frac = lambda n, thr=0.5: sum(1 for v in out[p + n][first:] if v > thr) / (len(times) - first)
    return {"kick/s": round(rate("Kick"), 2), "snare/s": round(rate("Snare"), 2), "hat/s": round(rate("Hat"), 2),
            "bpm p10/50/90": [round(bpm[int(len(bpm) * q)], 1) for q in (0.1, 0.5, 0.9)],
            "conf": round(mean("Conf"), 2), "drops": drops, "build>0.5": round(frac("Build"), 2),
            "break>0.5": round(frac("Break"), 2), "vocal": round(mean("Vocal"), 2), "hard": round(mean("Hard"), 2),
            "width": round(mean("Width"), 2), "energy": round(mean("Energy"), 2)}


# --- Actions -------------------------------------------------------------------

def parse_osc(d):
    """Single-argument float/int messages (what OSCSender sends)."""
    a = d[:d.index(b"\0")].decode()
    i = (len(a) + 4) & ~3
    tags = d[i:d.index(b"\0", i)].decode()
    j = i + ((len(tags) + 4) & ~3)
    v = struct.unpack(">f" if tags[1:2] == "f" else ">i", d[j:j + 4])[0] if len(tags) > 1 else None
    return a, v


def record(port, seconds, path):
    if port in mp.RESERVED_PORTS:
        raise SystemExit("port %d is reserved" % port)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", port))
    s.settimeout(0.2)
    n, end = 0, time.time() + seconds
    with open(path, "w") as f:
        while time.time() < end:
            try:
                data, _ = s.recvfrom(65535)
            except socket.timeout:
                continue
            a, v = parse_osc(data)
            f.write(json.dumps([round(time.time(), 4), a, v]) + "\n")
            n += 1
    print("%d messages -> %s" % (n, path))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["record"]:
        return record(int(argv[1]), float(argv[2]), argv[3])
    if argv[:1] == ["sim"]:
        ap = argparse.ArgumentParser(prog="sim")
        ap.add_argument("rec")
        ap.add_argument("--fps", type=float, default=120)
        ap.add_argument("--series", default="")
        ap.add_argument("--every", type=float, default=0.5)
        a = ap.parse_args(argv[1:])
        series = [x for x in a.series.split(",") if x]
        keep = series + [p + n for p in VARIANTS for n in ("KickOn", "SnareOn", "HatOn", "Kick", "BPM", "Conf", "DropEv",
                                                           "Build", "Break", "Vocal", "Hard", "Width", "Energy")]
        names = {n for n, _, _ in all_globals()}
        keep = [k for k in dict.fromkeys(keep) if k in names]
        out, times = simulate(all_globals(), read_rec(a.rec), a.fps, keep)
        for p in VARIANTS:
            print(p, summary(out, times, p))
        if series:
            step = max(1, int(a.every * a.fps))
            print("t      " + " ".join("%9s" % s[:9] for s in series))
            for i in range(0, len(times), step):
                print("%6.1f " % times[i] + " ".join("%9.3f" % out[s][i] for s in series))
        return
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("-o", "--out", default=OUT)
    ap.add_argument("--tap", action="store_true", help="power the OSC Tap scene")
    ap.add_argument("--tap-var", type=int, default=0, help="variant on /o/*: 0 a, 1 b, 2 c")
    ap.add_argument("--first", default="b", choices=["compare"] + list(VARIANTS),
                    help="scene Magic opens on (default b, rated best)")
    a = ap.parse_args(argv)
    root = build(a.tap, a.tap_var, a.first)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    mp.write(a.out, root)
    problems = mp.check(root, os.path.dirname(os.path.abspath(a.out)))
    errors = [m for lvl, m in problems if lvl == "error"]
    print("wrote %s: %d Globals, %d errors, %d warnings" % (a.out, len(mp.global_ivs(root)), len(errors),
                                                            len(problems) - len(errors)))
    for m in errors[:20]:
        print("  error:", m)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
