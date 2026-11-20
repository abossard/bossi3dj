"""Check dashboard cue requests against received pixels from a running Magic rehearsal."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.request import Request, urlopen

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
MAGICPROJ = ROOT / 'magic/magicproj.py'
SAMPLE_SIZE = (48, 27)
CUES = ('arrive', 'build', 'peak', 'release')


def media_reference(path):
    w, h = SAMPLE_SIZE
    rgb = subprocess.check_output(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', str(path),
                                   '-vf', f'fps=2,scale={w}:{h}', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'])
    return np.frombuffer(rgb, dtype=np.uint8).astype(np.int16).reshape(-1, h, w, 3)


def set_value(url, endpoint, body):
    request = Request(f'{url}/api/show/{endpoint}', data=json.dumps(body).encode(), method='PUT',
                      headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=3) as answer:
        return json.load(answer)['requested']


def cue_and_receive(url, name, output):
    body = {'scene': 'safe'} if name == 'safe' else {'cue': name}
    status = set_value(url, 'cue', body)
    raw = subprocess.check_output([sys.executable, str(MAGICPROJ), 'grab', '--server', 'MAGIC_OUT',
                                   '--timeout', '6', '--wait', '1', '--out', str(output)])
    picture = json.loads(raw)
    with Image.open(output) as file:
        pixels = np.asarray(file.convert('RGB').resize(SAMPLE_SIZE), dtype=np.int16)
    return status, picture, pixels


def audio_check(out, url, default):
    listed = subprocess.run(['ffmpeg', '-hide_banner', '-f', 'lavfi', '-i', 'anullsrc', '-t', '0.1',
                             '-f', 'audiotoolbox', '-list_devices', 'true', '-'], capture_output=True, text=True)
    device = re.search(r'\] \[(\d+)\]\s+BlackHole 2ch,', listed.stderr)
    if device is None:
        raise RuntimeError('BlackHole 2ch is unavailable')
    player = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-re', '-f', 'lavfi', '-i',
                               'sine=frequency=56:sample_rate=48000:duration=18', '-af', 'volume=4', '-ac', '2',
                               '-f', 'audiotoolbox', '-audio_device_index', device[1], '-'],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        dark = []
        for value in (0, 1):
            set_value(url, 'reactivity', {'value': value})
            _, _, pixels = cue_and_receive(url, 'build', out / f'audio-{value}.png')
            dark.append(round(float(np.quantile(pixels.mean(axis=2), 0.2)), 2))
        if player.poll() is not None:
            raise RuntimeError('BlackHole audio probe stopped before both frames were received')
    finally:
        player.terminate()
        player.wait(timeout=4)
        set_value(url, 'reactivity', {'value': default})
        set_value(url, 'cue', {'scene': 'safe'})
    if dark[1] - dark[0] < 4:
        raise RuntimeError(f'Audio reactivity did not visibly raise the shadows: {dark}')
    return {'shadow_luma_at_zero_and_full_reactivity': dark}


def check(media, url, audio=False):
    references = {cue: media_reference(media / f'{cue}.mp4') for cue in CUES}
    out = media / 'live-check'
    out.mkdir(parents=True, exist_ok=True)
    results = {}
    for label in ('boot-safe', *CUES, 'return-safe'):
        cue = label if label in CUES else 'safe'
        status, picture, pixels = cue_and_receive(url, cue, out / f'{label}.png')
        distances = {key: round(float(np.abs(r - pixels).mean(axis=(1, 2, 3)).min()), 2)
                     for key, r in references.items()}
        closest = min(distances, key=distances.get)
        result = {'requested': status, 'picture': picture, 'mean_rgb_distance': distances}
        results[label] = result
        print(json.dumps({label: result}), flush=True)
        if picture['size'] != [480, 270] or picture['lit'] < 0.01:
            raise RuntimeError(f'{label}: wrong size or dark program frame')
        if cue in CUES and (closest != cue or distances[cue] > 20):
            raise RuntimeError(f'{label}: received frame resembles {closest} at distance {distances[closest]}')
        if cue == 'safe':
            axis_variation = min(float(np.std(pixels, axis=axis).mean()) for axis in (0, 1))
            if axis_variation > 2 or np.std(pixels, axis=(0, 1)).max() < 0.5:
                raise RuntimeError(f'{label}: received picture lacks the Safe gradient')
    if audio:
        results['audio'] = audio_check(out, url, results['boot-safe']['requested']['reactivity'])
        print(json.dumps({'audio': results['audio']}), flush=True)
    (out / 'checks.json').write_text(json.dumps(results, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('media', type=Path)
    parser.add_argument('--url', default='http://127.0.0.1:8766')
    parser.add_argument('--audio', action='store_true', help='send a brief test tone to BlackHole 2ch')
    args = parser.parse_args()
    check(args.media.resolve(), args.url, args.audio)


if __name__ == '__main__':
    main()
