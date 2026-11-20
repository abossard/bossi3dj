"""Capture the 60-second Chrome Foundry cut from Magic's live Syphon output."""

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time

from live_rehearsal_capture import MAGIC_PORT, RECORDER, blackhole, cue, encode_message, grab, transmit_score
from rehearsal_reel import FPS, join
from rehearsal_score import MEASURE_HZ, score_levels
from robot_cinema import OUTPUT, SIZE
from show_protocol import ROBOT_FRAMING, ROBOT_RESTART


PHASE_SECONDS = 30


def send(udp, address, values):
    udp.sendto(encode_message(address, values), ('127.0.0.1', MAGIC_PORT))


def wait_picture(dashboard, phase, out):
    cue(dashboard, phase)
    until = time.monotonic() + 22
    while time.monotonic() < until:
        pic = grab('Magic', 'MAGIC_OUT', out / f'{phase}-on-air.png')
        if pic['size'] != list(SIZE):
            raise RuntimeError(f'Magic program is {pic["size"]}; load the 960x540 Robot cinema project')
        # The native standby gradient is identical across each row.
        width_change = max(max(sum(p) for p in row) - min(sum(p) for p in row) for row in pic['grid'])
        if width_change >= 5 and pic['lit'] >= 0.035:
            world = grab('Blender', 'ROBOT_LIVE', out / f'{phase}-blender.png')
            if world['size'] != list(SIZE):
                raise RuntimeError(f'Robot Live World is {world["size"]}; launch Blender with --robot-cinema')
            return
        time.sleep(0.25)
    raise RuntimeError(f'The {phase} cue never published its Robot composite')


def record_phase(dashboard, phase, shots, levels, out, udp, token, native_device=None, score_offset=0):
    send(udp, ROBOT_FRAMING, [1.0, 0.5, 0.5])
    wait_picture(dashboard, phase, out)
    print(f'{phase}: live Magic and Blender pictures verified', flush=True)
    width, height = SIZE
    start_flag, ready_flag = (out / filename for filename in ('.capture-start', '.capture-armed'))
    start_flag.unlink(missing_ok=True)
    ready_flag.unlink(missing_ok=True)
    route = out / f'{phase}-program.mp4'
    env = dict(os.environ, PYTHONPATH=str(Path.home() / '.local/lib/python3.13/site-packages'))
    record = subprocess.Popen(['python3.13', str(RECORDER), '--app', 'Magic', '--server', 'MAGIC_OUT',
                               '--seconds', str(PHASE_SECONDS), '--fps', str(FPS), '--size', f'{width}x{height}',
                               '--vflip', '--crf', '17', '--flag', str(start_flag), '--ready', str(ready_flag),
                               '--out', str(route)], env=env)
    stop_audio = threading.Event()
    audio = None
    player = None
    try:
        until = time.monotonic() + 18
        while not ready_flag.exists():
            if record.poll() is not None or time.monotonic() >= until:
                raise RuntimeError(f'Magic recorder did not arm for {phase}')
            time.sleep(0.15)
        send(udp, ROBOT_FRAMING, list(shots[0]['framing']))
        send(udp, ROBOT_RESTART, [token])
        start_flag.touch()
        start = time.monotonic()
        if native_device is None:
            audio = threading.Thread(target=transmit_score, args=(levels, start, stop_audio), daemon=True)
            audio.start()
        else:
            player = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-re', '-ss', str(score_offset),
                                       '-i', str(out / 'score.wav'), '-t', str(PHASE_SECONDS), '-f', 'audiotoolbox',
                                       '-audio_device_index', native_device, '-'], stdout=subprocess.DEVNULL)
        for shot in shots[1:]:
            left = start + shot['start'] - time.monotonic()
            if left > 0:
                time.sleep(left)
            if record.poll() is not None:
                raise RuntimeError(f'The {phase} capture ended before {shot["clip"]}')
            send(udp, ROBOT_FRAMING, list(shot['framing']))
        if record.wait(timeout=15) != 0:
            raise RuntimeError(f'Recorder did not finish the {phase} cue')
    finally:
        stop_audio.set()
        if audio is not None:
            audio.join(timeout=1)
        if player is not None and player.poll() is None:
            player.terminate()
            player.wait(timeout=5)
        if record.poll() is None:
            record.terminate()
            record.wait(timeout=5)
        start_flag.unlink(missing_ok=True)
        ready_flag.unlink(missing_ok=True)
    return route


def capture(out, dashboard, native_audio=False):
    director = json.loads((out / 'director.json').read_text())
    score = out / 'score.wav'
    device = blackhole() if native_audio else None
    levels = [] if native_audio else list(score_levels(score))
    token = int(time.monotonic()) % 8000000
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            routes = []
            for i, phase in enumerate(('build', 'peak')):
                n = PHASE_SECONDS * MEASURE_HZ
                routes.append(record_phase(dashboard, phase, director[phase], levels[i*n:(i+1)*n],
                                           out, udp, token + i, device, i * PHASE_SECONDS))
            send(udp, ROBOT_FRAMING, [1.0, 0.5, 0.5])
    finally:
        cue(dashboard, 'safe')

    tags = out / 'chapters.txt'
    tags.write_text(';FFMETADATA1\ntitle=Chrome Foundry | bossi3dj Robot Scene\n'
                    'comment=Security Bot Rig (CC BY), Blender Foundation, modified for the Robot Scene. '
                    'https://studio.blender.org/characters/security-bot/v1/\n'
                    '[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=30000\ntitle=Android\n'
                    '[CHAPTER]\nTIMEBASE=1/1000\nSTART=30000\nEND=60000\ntitle=Exchange\n')
    result = out / 'chrome-foundry-live.mp4'
    join(routes, result, ('-i', score, '-f', 'ffmetadata', '-i', tags, '-map', '0:v:0', '-map', '1:a:0',
                          '-map_metadata', '2', '-map_chapters', '2', '-c:a', 'aac', '-b:a', '192k'))
    print(result, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--dashboard', default='http://127.0.0.1:8766')
    parser.add_argument('--native-audio', action='store_true', help='play the score to native Magic input over BlackHole')
    args = parser.parse_args()
    capture(args.output.resolve(), args.dashboard, args.native_audio)


if __name__ == '__main__':
    main()
