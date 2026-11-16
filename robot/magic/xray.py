"""The Robot's audio analysis: Magic Globals that turn live audio into a beat clock and a section State. Stdlib only.

Adapted from the Music X-Ray example of mmv-skills (mmv-scene-recipes, on mmv-audio-reactivity's audio bank), cut down to
what the Clip Graph reads. Verified there in Magic 3 at 124 BPM; see the Robot hand-over (docs/handover/robot-magic.md).

Every Global reads the previous frame's values, so edge detectors use lag Globals. `globals_()` returns (name, value, source, mods)
rows in Builder form. The Clip Graph reads only these names:
  Section   the one source of the Intensity Tier: 0 intro (also silence), 2 buildup, 3 drop, 4 breakdown. Today a link to State;
            point it at another source (an OSC address, a song structure) and nothing else changes.
  Beats     running beat count, a bar line is a multiple of 4
  BeatFrac  0..1 inside the beat. Beats and BeatFrac both come from Phase and step in the same frame: Beats follows Phase through
            BeatInBar, BeatLag and BeatPulse (3 frames), so BeatFrac reads Phase through two lag Globals (live test 2026-11-16: read
            straight from Phase it wrapped 2 frames before Beats stepped, and /vj/clip_frame fell back one beat for those frames)
  Bpm       tempo in beats per minute
"""
SOURCE = "Source 0"
TEMPO_LO, SUB_LOW, SUB_HIGH, RISE_MIN, QUIET = 90, 0.3, 0.55, 0.06, 0.02
KICK_DECAY, KICK_THRESHOLD = 0.12, 0.6
SECTION, BEATS, BEAT_FRAC, BPM = "Section", "Beats", "BeatFrac", "Bpm"


def globals_(src=SOURCE):
    rows = []

    def g(name, value, source=None, mods=()):
        rows.append((name, value, source, list(mods)))

    ex = lambda e: ("Expression", e)
    fr = "audio:%s:Freq. Range:" % src
    tau = lambda beats: "(1 - exp(-Dt*max(Bpm, 60)/%g))" % (60 * beats)   # EMA step with a time constant in beats

    # audio bank: gain, bass, volume, clock, kick envelope and its pulse (a gate edge needs the lag Global, not y)
    g("Gain", 0.5)
    g("Bass", 0, fr + "20-80 Hz", [ex("x*Gain*4"), ("Smooth", 0.3), ("Clamp", 1)])
    g("Volume", 0, "audio:%s:Volume" % src, [ex("x*Gain*4"), ("Clamp", 1)])
    g("Time", 0, "calc", [("Increase", 1)])
    g("TimeLag", 0, "calc", [ex("Time")])
    g("Dt", 0.016, "calc", [ex("max(0.001, min(0.05, Time - TimeLag))")])
    g("KickRaw", 0, fr + "80-320 Hz", [ex("x*Gain*4")])
    g("Kick", 0, "calc", [ex("max(KickRaw, y*exp(-Dt/%g))" % KICK_DECAY), ("Clamp", 1)])
    g("KickGate", 0, "global:Kick", [("Threshold", KICK_THRESHOLD)])
    g("KickGateLag", 0, "calc", [ex("KickGate")])
    g("KickPulse", 0, "calc", [ex("if (KickGate > 0.5 and KickGateLag < 0.5, 1, 0)")])

    # tuning knobs
    g("TempoLo", TEMPO_LO)
    g("SubLow", SUB_LOW)
    g("SubHigh", SUB_HIGH)
    g("RiseMin", RISE_MIN)
    g("Quiet", QUIET)

    # snare/clap (1.2-5 kHz): onset = rise above the band's own recent average
    g("SnareRaw", 0, fr + "1.2k-5k Hz", [ex("x*Gain*4")])
    g("SnareAvg", 0, "calc", [ex("y + (SnareRaw - y)*(1 - exp(-Dt/0.15))")])
    g("Snare", 0, "calc", [ex("max(clamp((SnareRaw - SnareAvg*1.1)*8, 0, 1), y*exp(-Dt/0.1))")])
    g("SnareGate", 0, "global:Snare", [("Threshold", 0.3)])
    g("SnareGateLag", 0, "calc", [ex("SnareGate")])
    g("SnarePulse", 0, "calc", [ex("if (SnareGate > 0.5 and SnareGateLag < 0.5, 1, 0)")])

    # tempo: interval between kicks, folded into one tempo octave, a new tempo only when several intervals agree
    g("KickPulseLag", 0, "calc", [ex("KickPulse")])
    g("LastKickT", 0, "calc", [ex("if (KickPulse > 0.5, Time, y)")])
    g("BpmFold", 0, "calc", [ex(
        "if (KickPulse > 0.5 and Time - LastKickT > 0.2 and Time - LastKickT < 2, "
        "(60/(Time - LastKickT)) / pow(2, floor(log(60/(Time - LastKickT)/TempoLo)/log(2))), y)")])
    g("BpmMiss", 0, "calc", [ex("if (KickPulseLag > 0.5, if (abs(BpmFold - Bpm) < Bpm*0.06, 0, y + 1), y)")])
    g("BpmFoldLag", 0, "calc", [ex("if (KickPulseLag > 0.5, BpmFold, y)")])
    g("BpmAgree", 0, "calc", [ex("if (KickPulseLag > 0.5, if (abs(BpmFold - BpmFoldLag) < BpmFold*0.03, y + 1, 0), y)")])
    g(BPM, 120, "calc", [ex(
        "if (y < 1, 120, if (KickPulseLag > 0.5 and BpmFold > 1, "
        "if (abs(BpmFold - y) < y*0.06, y + (BpmFold - y)*0.2, if (BpmMiss >= 3 and BpmAgree >= 3, BpmFold, y)), y))")])

    # beat clock: runs on Bpm, each kick pulls it 35 % towards the nearest beat; 0..4 beats.
    # KickPulse arrives Latency seconds after the kick, so the beat it marks is Latency*Bpm/60 beats behind the clock.
    g("Latency", 0.04)
    err = lambda v: "(round(%s - Latency*Bpm/60) + Latency*Bpm/60 - %s)" % (v, v)
    g("Phase", 0, "calc", [ex("frac((y + Dt*Bpm/60 + if (KickPulse > 0.5, 0.35*%s, 0))/4)*4" % err("y"))])

    # bar grid: bar 1 is a guess (DownSlot 0) until a drop sets it
    g("BeatInBar", 0, "calc", [ex("floor((Phase - DownSlot) - 4*floor((Phase - DownSlot)/4))")])
    g("BeatLag", 0, "calc", [ex("BeatInBar")])
    g("BeatPulse", 0, "calc", [ex("if (abs(BeatInBar - BeatLag) > 0.5, 1, 0)")])
    g("BarPulse", 0, "calc", [ex("if (BeatInBar < 0.5 and BeatLag > 2.5, 1, 0)")])

    # levels over a beat, a bar, four bars
    g("ToneRaw", 0, "audio:%s:Tone" % src)
    g("BassPeak", 0, "calc", [ex("max(Bass, y*exp(-Dt/120), 0.05)")])
    g("SubFast", 0, "calc", [ex("y + (Bass/max(BassPeak, 0.05) - y)*" + tau(0.25))])
    g("SubBar", 0, "calc", [ex("y + (Bass/max(BassPeak, 0.05) - y)*" + tau(2))])
    g("VolSlow", 0, "calc", [ex("y + (Volume - y)*(1 - exp(-Dt/2))")])
    g("ToneBar", 0, "calc", [ex("if (y < 0.001, ToneRaw, y + (ToneRaw - y)*%s)" % tau(4))])
    g("ToneSlow", 0, "calc", [ex("if (y < 0.001, ToneRaw, y + (ToneRaw - y)*%s)" % tau(16))])
    g("ToneRise", 0, "calc", [ex("ToneBar - ToneSlow")])
    g("KickRate", 0, "calc", [ex("y*exp(-Dt*max(Bpm, 60)/240) + KickPulse")])     # about kicks per bar
    g("SnareRate", 0, "calc", [ex("y*exp(-Dt*max(Bpm, 60)/240) + SnarePulse")])   # about snares per bar
    g("SubOut", 0, "calc", [ex("if (BarPulse > 0.5, if (SubBar < SubLow, y + 1, 0), y)")])

    # drop: sub-bass back after >= 2 low bars; it sets the bar grid
    g("DropPulse", 0, "calc", [ex("if (SubFast > SubHigh and SubOut >= 2 and abs(State - 3) > 0.5 and y < 0.5, 1, 0)")])
    g("DownSlot", 0, "calc", [ex("if (DropPulse > 0.5, round(Phase - 0.25) - 4*floor(round(Phase - 0.25)/4), y)")])

    # section state, decided on bar lines (a drop switches at once)
    g("ThinBars", 0, "calc", [ex("if (BarPulse > 0.5, if (SubBar < SubLow and KickRate >= 2.5, y + 1, 0), y)")])
    g("State", 0, "calc", [ex(
        "if (DropPulse > 0.5, 3, if (BarPulse > 0.5, "
        "if (VolSlow < Quiet, 0, "
        "if (ThinBars >= 16 and y > 0.5, 0, "
        "if (abs(y - 3) < 0.5, if (SubBar < SubLow and KickRate < 0.5, 4, 3), "
        "if (SubBar < SubLow and (ToneRise > RiseMin or SnareRate >= 5), 2, "
        "if (SubBar < SubLow and KickRate < 0.5 and y > 0.5 and abs(y - 2) > 0.5, 4, y))))), y))")])

    # what the Clip Graph reads. A plain Global link reads the same frame.
    g(SECTION, 0, "global:State")
    g(BEATS, 0, "calc", [ex(
        "if (BeatPulse > 0.5, if (BeatInBar < 0.5, 4*ceil((y + 1)/4 - 0.001), y + 1), y)")])   # a bar line is a multiple of 4, never backwards
    g("PhaseLag1", 0, "calc", [ex("Phase")])
    g("PhaseLag2", 0, "calc", [ex("PhaseLag1")])
    g(BEAT_FRAC, 0, "calc", [ex("frac(PhaseLag2)")])      # frame f holds frac(Phase(f-3)), as Beats does
    return rows
