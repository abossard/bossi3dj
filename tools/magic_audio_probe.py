"""Verify native BlackHole input by following a short test tone through Magic to Blender."""

import argparse
import json
import subprocess
import time
from urllib.request import urlopen

from live_rehearsal_capture import blackhole, cue


def snapshot():
    with urlopen('http://127.0.0.1:9210/api/state', timeout=4) as source:
        return (json.load(source).get('osc') or {}).get('addresses') or {}


def values(state, field, default):
    row = state.get('/vj/' + field) or {}
    return row.get('n', 0), row.get('v', [default])[0]


def verify(dashboard):
    device = blackhole()
    cue(dashboard, 'build')
    time.sleep(1.0)
    baseline = snapshot()
    baseline_count, baseline_bass = values(baseline, 'bass', 0.0)
    player = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-re', '-f', 'lavfi', '-i',
                               'sine=frequency=56:sample_rate=48000:duration=7', '-af', 'volume=4', '-ac', '2',
                               '-f', 'audiotoolbox', '-audio_device_index', device, '-'], stdout=subprocess.DEVNULL)
    try:
        samples = []
        for _ in range(10):
            time.sleep(0.45)
            state = snapshot()
            count, bass = values(state, 'bass', 0.0)
            _, level = values(state, 'level', 0.50)
            samples.append((count, bass, level))
        peak = max(bass for _, bass, _ in samples)
        result = {'baseline_bass': baseline_bass, 'tone_bass_peak': peak,
                  'tone_level_peak': max(level for _, _, level in samples),
                  'new_bass_messages': max(count for count, _, _ in samples) - baseline_count}
        print(json.dumps(result, indent=2))
        return 0 if result['new_bass_messages'] > 0 and peak - baseline_bass > 0.02 else 1
    finally:
        if player.poll() is None:
            player.terminate()
            player.wait(timeout=5)
        cue(dashboard, 'safe')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dashboard', default='http://127.0.0.1:8766')
    return verify(parser.parse_args().dashboard)


if __name__ == '__main__':
    raise SystemExit(main())
