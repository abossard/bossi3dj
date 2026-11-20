"""Write the original 128 BPM soundtrack for the bossi3dj rehearsal reel."""

import argparse
from pathlib import Path
import wave

import numpy as np


RATE = 48_000
BEAT = 22_500  # 128 BPM, exactly 64 bars in each two-minute phase
BAR = BEAT * 4
NOTE = 73.4162  # D2
TAU = 2 * np.pi
MEASURE_HZ = 20


def voice(freq, seconds, decay, harmonics):
    t = np.arange(round(RATE * seconds)) / RATE
    cycles = TAU * freq * t
    tone = sum(level * np.sin(order * cycles) for order, level in harmonics)
    return tone * (1 - np.exp(-180 * t)) * np.exp(-decay * t)


def write_score(path):
    rng = np.random.default_rng(441)
    t = np.arange(BEAT) / RATE
    kick = np.sin(TAU * (47 * t + 4.1 * (1 - np.exp(-23 * t)))) * np.exp(-12 * t)
    kick *= np.minimum(1, 770 * t)
    noise = rng.standard_normal(BEAT)
    hat = np.diff(noise, prepend=0) * np.exp(-68 * t) * np.minimum(1, 540 * t)
    clap = (noise - np.roll(noise, 4)) * np.exp(-27 * t) * np.minimum(1, 750 * t)
    clap /= 3
    kick = kick[:16_000]
    hat = hat[:5200]
    clap = clap[:12_500]
    bar_time = np.arange(BAR) / RATE
    mix = np.zeros((2, BAR * 2))

    def add(sound, start, gain, pan=0):
        idx = round(start * BEAT)
        event = mix[:, idx:idx + len(sound)]
        event[0] += sound * gain * (1 - pan) / 1.2
        event[1] += sound * gain * (1 + pan) / 1.2

    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as wav:
        wav.setparams((2, 2, RATE, 0, 'NONE', 'not compressed'))
        for bar in range(256):
            phase, local = divmod(bar, 64)
            absolute = bar_time + bar * BAR / RATE
            swell = 0.68 + 0.32 * np.sin(TAU * absolute / 30 - 0.8)
            pad_gain = (0.13, 0.075, 0.055, 0.145)[phase] * swell
            # Fifth and minor second beat gently against the D drone.
            for channel, detune in enumerate((-0.21, 0.18)):
                drone = np.sin(TAU * (NOTE + detune) * absolute)
                drone += 0.31 * np.sin(TAU * (NOTE * 1.5 + detune * 3) * absolute)
                drone += 0.24 * np.sin(TAU * (NOTE * 2 ** (1 / 12)) * absolute)
                mix[channel, :BAR] += pad_gain * drone

            if phase == 0:
                kick_steps = () if local < 8 else (0, 2) if local < 24 else (0, 1, 2, 3)
                bass_steps = (1.5, 3.5) if local >= 16 else ()
                kick_gain = 0.50 if local >= 24 else 0.26
            elif phase == 1:
                kick_steps = (0, 1, 2, 3) if local < 60 else (0, 2) if local < 63 else (0,)
                bass_steps = (0.5, 1.5, 2.5, 3.5)
                kick_gain = 0.70
            elif phase == 2:
                # A short mid-peak pocket makes the returning four-on-the-floor audible.
                kick_steps = (() if 28 <= local < 31 else (0, 2) if local == 31 else (0, 1, 2, 3))
                bass_steps = (0.5, 1.25, 1.75, 2.5, 3.5)
                kick_gain = 0.85
            else:
                kick_steps = (0, 1, 2, 3) if local < 8 else (0, 2) if local < 20 else ()
                bass_steps = (1.5, 3.5) if local < 16 else ()
                kick_gain = 0.53 - 0.017 * local

            for step in kick_steps:
                add(kick, step, kick_gain)
            if kick_steps and (phase in (1, 2) or phase == 0 and local >= 32):
                for step in (0.5, 1.5, 2.5, 3.5):
                    add(hat, step, 0.063 if phase == 2 else 0.046, 0.34 if step < 2 else -0.33)
                if phase in (1, 2) and local % 16 < 14:
                    add(clap, 1, 0.075)
                    add(clap, 3, 0.095)
                if phase == 2:
                    for step in (0.75, 1.75, 2.75, 3.75):
                        add(hat, step, 0.023, -0.36)

            if bass_steps:
                change = (0, 0, -2, 1)[(bar // 4) % 4]
                for i, step in enumerate(bass_steps):
                    semitones = change if i < len(bass_steps) - 1 else (0, 3, -2, 1)[bar % 4]
                    freq = NOTE / 2 * 2 ** (semitones / 12)
                    bass = voice(freq, 0.21, 13, ((1, 1), (2, 0.25), (3, 0.13), (5, 0.17)))
                    add(bass, step, (0.24, 0.36, 0.40, 0.20)[phase])

            motif_steps = (0, 2.75) if phase in (0, 3) else (0.25, 1.75, 3.25)
            motif_active = local % 8 in ((0, 4) if phase in (0, 3) else (0, 2, 4, 6))
            if motif_active and 4 <= local <= 56:
                for i, step in enumerate(motif_steps):
                    pitch = (0, 3, 7)[i] if (local // 4) % 2 else (0, 1, 7)[i]
                    freq = 4 * NOTE * 2 ** (pitch / 12)
                    lead = voice(freq, 0.37, 13, ((1, 1), (2, 0.30), (4, 0.27), (7, 0.09)))
                    lead_gain = (0.084, 0.086, 0.11, 0.071)[phase]
                    add(lead, step, lead_gain, -0.17)
                    add(lead, step + 0.75, lead_gain * 0.64, 0.56)
                    add(lead, step + 1.50, lead_gain * 0.28, -0.59)

            envelope = np.minimum(1, absolute / 6) * np.clip((480 - absolute) / 16, 0, 1)
            chunk = np.tanh(mix[:, :BAR] * 1.32) * envelope * 0.94
            wav.writeframes((chunk.T * 32767).astype('<i2').tobytes())
            mix[:, :BAR] = mix[:, BAR:]
            mix[:, BAR:] = 0


def score_levels(path):
    """Return 20 Hz broadband and 20–80 Hz levels from the actual stereo PCM."""
    with wave.open(str(path), 'rb') as wav:
        if wav.getsampwidth() != 2:
            raise ValueError('The score analyzer expects 16-bit PCM')
        rate, channels = wav.getframerate(), wav.getnchannels()
        window_size = rate // MEASURE_HZ
        window = np.hanning(window_size)
        band = (np.fft.rfftfreq(window_size, 1 / rate) >= 20) & (np.fft.rfftfreq(window_size, 1 / rate) <= 80)
        while data := wav.readframes(window_size):
            pcm = np.frombuffer(data, dtype='<i2').astype(np.float32).reshape(-1, channels) / 32768
            mono = pcm.mean(axis=1)
            if len(mono) < window_size:
                mono = np.pad(mono, (0, window_size - len(mono)))
            level = min(1.0, float(np.sqrt((mono ** 2).mean())) * 3.2)
            spectrum = np.fft.rfft(mono * window)
            low = min(1.0, float(np.linalg.norm(spectrum[band])) * 1.6 / window.sum())
            yield level, low


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    write_score(parser.parse_args().output)


if __name__ == '__main__':
    main()
