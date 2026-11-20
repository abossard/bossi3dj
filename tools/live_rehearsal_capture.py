"""Record the real four-cue Magic program with both Blender Worlds in one session."""

import argparse
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import threading
import time
from urllib.request import Request, urlopen

from rehearsal_reel import chapters
from rehearsal_score import MEASURE_HZ, score_levels


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'osc'))
from lab import encode_message
from show_protocol import AUDIO_LEVEL, AUDIO_SUB, MAGIC_PORT


MAGICPROJ = ROOT / 'magic/magicproj.py'
RECORDER = ROOT / 'tools/syphon_record.py'
CUES = ('arrive', 'build', 'peak', 'release')
PHASE_SECONDS = 120


def cue(dashboard, phase):
    body = {'scene': 'safe'} if phase == 'safe' else {'cue': phase}
    request = Request(f'{dashboard}/api/show/cue', method='PUT', data=json.dumps(body).encode(),
                      headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=5) as response:
        return json.load(response)


def grab(app, server, out):
    command = [sys.executable, str(MAGICPROJ), 'grab', '--app', app, '--server', server,
               '--out', str(out), '--timeout', '5']
    return json.loads(subprocess.check_output(command, timeout=15))


def preflight(out, dashboard):
    """Check the final program pixels as well as the direct live input of each cue."""
    results = {}
    for phase in ('safe', *CUES, 'safe'):
        cue(dashboard, phase)
        server = 'ROBOT_LIVE' if phase in ('build', 'peak') else 'CAM_OUT'
        deadline = time.monotonic() + 25
        while True:
            picture = grab('Magic', 'MAGIC_OUT', out / f'magic-{phase}.png')
            row_spread = max(max(sum(rgb) for rgb in row) - min(sum(rgb) for rgb in row)
                             for row in picture['grid'])
            right_source = row_spread <= 3 if phase == 'safe' else row_spread > 3
            if picture['lit'] >= 0.01 and right_source:
                break
            if time.monotonic() >= deadline:
                raise RuntimeError(f'{phase} did not reach its live program picture: {picture}')
            time.sleep(0.4)
        if picture['size'] != [480, 270]:
            raise RuntimeError(f'{phase} program size is {picture["size"]}, expected 480×270')
        direct = grab('Blender', server, out / f'blender-{phase}.png') if phase != 'safe' else None
        results[phase] = {'program': picture, 'blender': direct}
        print(f'{phase}: {picture["server"]}, source {server if direct else "Safe"}, lit {picture["lit"]:.3f}', flush=True)
    (out / 'preflight.json').write_text(json.dumps(results, indent=2) + '\n')


def blackhole():
    call = subprocess.run(['ffmpeg', '-hide_banner', '-f', 'lavfi', '-i', 'anullsrc', '-t', '0.1',
                           '-f', 'audiotoolbox', '-list_devices', 'true', '-'], capture_output=True, text=True)
    match = re.search(r'\] \[(\d+)\]\s+BlackHole 2ch,', call.stderr)
    if match is None:
        raise RuntimeError('BlackHole 2ch is missing')
    return match[1]


def sample_controls(out, elapsed):
    try:
        with urlopen('http://127.0.0.1:9210/api/state', timeout=0.6) as response:
            state = json.load(response)
        found = (state.get('osc') or {}).get('addresses') or {}
        fields = {name: found.get('/vj/' + name) for name in ('level', 'bass', 'beat', 'energy', 'angle')}
        with (out / 'capture-controls.jsonl').open('a') as stream:
            stream.write(json.dumps({'seconds': round(elapsed, 3), 'scene': state.get('scene'), **fields}) + '\n')
        return fields
    except (OSError, ValueError):
        return {}


def transmit_score(levels, start, stop):
    """Supply measurements from the identical score on the recording clock."""
    destination = ('127.0.0.1', MAGIC_PORT)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
        index = 0
        while index < len(levels):
            if stop.wait(max(0, start + index / MEASURE_HZ - time.monotonic())):
                break
            index = int((time.monotonic() - start) * MEASURE_HZ)
            if index >= len(levels):
                break
            for address, value in zip((AUDIO_LEVEL, AUDIO_SUB), levels[index], strict=True):
                udp.sendto(encode_message(address, [float(value)]), destination)
            index += 1
        for address in (AUDIO_LEVEL, AUDIO_SUB):
            udp.sendto(encode_message(address, [0.0]), destination)


def record(out, dashboard, project_score, osc_score):
    score = out / 'media/score.wav'
    if not score.is_file():
        raise RuntimeError(f'Missing rehearsal score: {score}')
    device = None if project_score or osc_score else blackhole()
    levels = list(score_levels(score)) if osc_score else []
    launch, armed = out / '.capture-start', out / '.capture-armed'
    launch.unlink(missing_ok=True)
    armed.unlink(missing_ok=True)
    (out / 'capture-controls.jsonl').unlink(missing_ok=True)
    raw = out / 'magic-program.mp4'
    environment = dict(os.environ, PYTHONPATH=str(Path.home() / '.local/lib/python3.13/site-packages'))
    recorder = subprocess.Popen(['python3.13', str(RECORDER), '--app', 'Magic', '--server', 'MAGIC_OUT',
                                 '--seconds', '480', '--fps', '24', '--size', '480x270', '--vflip', '--crf', '19',
                                 '--flag', str(launch), '--ready', str(armed), '--out', str(raw)], env=environment)
    player = None
    osc_player = None
    stop_score = threading.Event()
    playing_in_magic = False
    heard_audio = False
    try:
        deadline = time.monotonic() + 25
        while not armed.exists():
            if recorder.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError('Magic recorder failed to arm')
            time.sleep(0.2)
        cue(dashboard, CUES[0])
        # Give the first World time to draw before the timed four-phase run.
        time.sleep(1.0)
        if project_score:
            subprocess.run([sys.executable, str(MAGICPROJ), 'play'], check=True)
            playing_in_magic = True
        launch.touch()
        start = time.monotonic()
        if osc_score:
            osc_player = threading.Thread(target=transmit_score, args=(levels, start, stop_score), daemon=True)
            osc_player.start()
        elif not project_score:
            player = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-re', '-i', str(score), '-f', 'audiotoolbox',
                                       '-audio_device_index', device, '-'], stdout=subprocess.DEVNULL)
        print('0:00 Arrive', flush=True)
        for i, phase in enumerate(CUES[1:], 1):
            remaining = start + i * PHASE_SECONDS - time.monotonic()
            while remaining > 0:
                if recorder.poll() is not None or (player is not None and player.poll() is not None):
                    raise RuntimeError(f'Recording or audio playback ended before {phase}')
                elapsed = time.monotonic() - start
                controls = sample_controls(out, elapsed)
                level = (controls.get('level') or {}).get('v', [0.5])[0]
                bass = (controls.get('bass') or {}).get('v', [0.0])[0]
                heard_audio = heard_audio or level > 0.502 or bass > 0.003
                if elapsed >= 20 and not heard_audio:
                    raise RuntimeError('Magic did not send a music response to Blender during the first 20 seconds')
                time.sleep(min(remaining, 5))
                remaining = start + i * PHASE_SECONDS - time.monotonic()
            cue(dashboard, phase)
            print(f'{2*i}:00 {phase.title()}', flush=True)
        deadline = start + 480 + 70
        while recorder.poll() is None and time.monotonic() < deadline:
            sample_controls(out, time.monotonic() - start)
            time.sleep(5)
        if recorder.poll() != 0:
            raise RuntimeError('Magic Syphon recorder failed')
    finally:
        for process in (recorder, player):
            if process is not None and process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
        launch.unlink(missing_ok=True)
        armed.unlink(missing_ok=True)
        stop_score.set()
        if osc_player is not None:
            osc_player.join(timeout=1)
        if playing_in_magic:
            subprocess.run([sys.executable, str(MAGICPROJ), 'play'], check=False)
        cue(dashboard, 'safe')
    meta = out / 'chapters.txt'
    chapters(meta)
    target = out / 'bossi3dj-live-showreel.mp4'
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(raw), '-i', str(score),
                    '-f', 'ffmetadata', '-i', str(meta), '-map', '0:v:0', '-map', '1:a:0', '-map_metadata', '2',
                    '-map_chapters', '2', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', str(target)], check=True)
    print(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    parser.add_argument('--dashboard', default='http://127.0.0.1:8766')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--probe-only', action='store_true')
    mode.add_argument('--record-only', action='store_true')
    audio = parser.add_mutually_exclusive_group()
    audio.add_argument('--project-score', action='store_true', help='play the configured score inside Magic')
    audio.add_argument('--osc-score', action='store_true', help='send measurements of the score to the OSC audio input')
    args = parser.parse_args()
    out = args.out.resolve()
    probes = out / 'live-check'
    probes.mkdir(parents=True, exist_ok=True)
    if not args.record_only:
        preflight(probes, args.dashboard)
    if not args.probe_only:
        record(out, args.dashboard, args.project_score, args.osc_score)


if __name__ == '__main__':
    main()
