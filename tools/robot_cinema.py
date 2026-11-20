"""Build the Camera Track-matched Robot close-up and Exchange media for Magic."""

import argparse
import json
import math
from pathlib import Path
import random
import subprocess
from tempfile import TemporaryDirectory

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from rehearsal_reel import BAR_FRAMES, BAR_SECONDS, FPS, MEDIA, PACKAGE, PEAK, ffmpeg, join, robot_schedule
from rehearsal_score import write_score


OUTPUT = MEDIA / 'rehearsal-robot-cinema-v2'
SIZE = (960, 540)
SPARK_SIZE = (480, 270)
SOLO = (
    'idle_guard_v2/f guard_shuffle/f mocap_jab_elbow_v2/f take_hit/f mocap_flip_uppercut/f',
    'settle_low/f palm_strike/f rush_cross/f mocap_uppercut_jab_v3/f idle_guard_v4/f',
)
SOLO_FRAMING = (1.0, 1.75, 1.72, 1.0, 1.62, 1.18, 2.15, 1.0, 1.62, 1.9)
DUEL_FRAMING = (1.0, 1.0, 1.28, 1.0, 1.25, 1.33, 1.0, 1.0, 1.08, 1.22, 1.0)
EMBER_LIFETIME = 0.64


def resize_at_rate(size, rate):
    w, h = size
    return (f'scale={w}:{h}:flags=lanczos,setsar=1,settb=AVTB,'
            f'setpts=(PTS-STARTPTS)/{rate:.8f},fps={FPS},tpad=stop_mode=clone:stop_duration=0.13')


def hit_events(clip, data, bar):
    duration = clip['beats'] / 4 * BAR_SECONDS
    by_frame = {}
    for hit in data['hits']:
        if hit['strength'] <= 0 or not all(0 <= p <= 1 for p in hit['point'][:2]):
            continue
        earlier = by_frame.get(hit['f'])
        if earlier is None or (bool(hit.get('target')), hit['strength']) > (bool(earlier.get('target')), earlier['strength']):
            by_frame[hit['f']] = hit
    return [
        {'second': bar * BAR_SECONDS + hit['f'] / clip['frames'] * duration,
         'point': hit['point'][:2], 'strength': hit['strength'],
         'limb': hit['limb'], 'target': hit.get('target')}
        for hit in by_frame.values()
    ]


def framing(clip, data, zoom):
    if zoom == 1:
        return 1, 0.5, 0.5
    frames = data['frames']
    if clip['angle'] == 'front':
        # Use the region from the head to the hands and torso. Hold one crop through the Move.
        anchors = [(f['head'][0], f['head'][1] + 0.14) for f in frames]
    else:
        anchors = [((f['head'][0] + f['g_core'][0]) / 2, (f['head'][1] + f['g_core'][1]) / 2)
                   for f in frames]
    cx, cy = np.median(anchors, axis=0)
    margin = 0.5 / zoom
    cx, cy = np.clip((cx, cy), margin, 1 - margin)
    return zoom, round(float(cx), 4), round(float(cy), 4)


def spray(hit, width, height):
    source_x, source_y = (p * s for p, s in zip(hit['point'], (width, height), strict=True))
    rng = random.Random(f'{hit["second"]:.6f}/{hit["limb"]}')
    strength = hit['strength']
    ground = hit['target'] == 'floor' or hit['limb'].startswith('g_foot')
    particles = []
    for _ in range(13 + round(strength * 22)):
        angle = rng.uniform(-math.pi, 0 if ground else math.pi)
        speed = rng.uniform(56, 190) * (0.72 + strength * 0.46)
        particles.append((speed * math.cos(angle), speed * math.sin(angle), rng.uniform(0.30, EMBER_LIFETIME),
                          rng.uniform(0.028, 0.075), rng.randrange(116, 235)))
    return source_x, source_y, particles


def spark_frame(t, sprays):
    frame = Image.new('RGBA', SPARK_SIZE)
    for hit, (x, y, particles) in sprays:
        dt = t - hit['second']
        if not 0 <= dt < EMBER_LIFETIME:
            continue
        glow = Image.new('RGBA', SPARK_SIZE)
        heads = ImageDraw.Draw(glow)
        draw = ImageDraw.Draw(frame)
        heat = max(0, 1 - dt / 0.18) * hit['strength']
        if heat:
            radius = 5.0 + 2.0 * heat
            heads.ellipse((x-radius, y-radius, x+radius, y+radius), fill=(255, 125, 32, round(182 * heat)))
            draw.ellipse((x-2, y-2, x+2, y+2), fill=(255, 235, 190, round(245 * heat)))
        for dx, dy, life, trail, green in particles:
            if dt >= life:
                continue
            tail = max(0.0, dt - trail)
            a = round(245 * (1 - dt / life) ** 1.05)
            point = x + dx * dt, y + dy * dt + 132 * dt * dt
            old = x + dx * tail, y + dy * tail + 132 * tail * tail
            draw.line((old, point), fill=(255, green, 64, a), width=2 if green >= 165 else 1)
            if a >= 140:
                px, py = point
                draw.ellipse((px-0.8, py-0.8, px+0.8, py+0.8), fill=(255, 232, 177, a))
        frame = Image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(3)), frame)
    return frame.tobytes()


def render_shot(clip, hits, output):
    w, h = SIZE
    sw, sh = SPARK_SIZE
    bars = clip['beats'] // 4
    frames = bars * BAR_FRAMES
    rate = clip['frames'] / 30 / (bars * BAR_SECONDS)
    scale = resize_at_rate(SIZE, rate)
    # The Shadow Pass stores coverage. Carry it as dark alpha under the beauty, over the live floor.
    base_filter = (f'[0:v]format=rgba,{scale}[beauty];'
                   f"[1:v]{scale},format=gray,lut=y='clip((val-2)*0.72,0,128)'[shadow];"
                   '[2:v]format=rgba[black];[black][shadow]alphamerge=shortest=1[contact];'
                   '[contact][beauty]overlay=shortest=1:format=auto')
    inputs = ['-i', str(PACKAGE / clip['passes']['beauty']), '-i', str(PACKAGE / clip['passes']['shadow']),
              '-f', 'lavfi', '-i', f'color=black:size={w}x{h}:rate={FPS}']
    args = ['-an', '-frames:v', str(frames), '-c:v', 'qtrle', '-pix_fmt', 'argb',
            '-video_track_timescale', '24000', str(output)]
    if not hits:
        ffmpeg(*inputs, '-filter_complex', base_filter + ',format=argb', *args)
        return
    composite = (base_filter + '[robot];'
                 f'[3:v]scale={w}:{h}:flags=bilinear,format=rgba[sparks];'
                 '[robot][sparks]overlay=shortest=1:format=auto,format=argb')
    spark_input = ['-f', 'rawvideo', '-pixel_format', 'rgba', '-video_size', f'{sw}x{sh}', '-framerate', str(FPS), '-i', '-']
    command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-filter_complex_threads', '2',
               *inputs, *spark_input, '-filter_complex', composite, *args]
    sprays = [(hit, spray(hit, sw, sh)) for hit in hits]
    with subprocess.Popen(command, stdin=subprocess.PIPE) as child:
        try:
            for i in range(frames):
                child.stdin.write(spark_frame(i / FPS, sprays))
        finally:
            child.stdin.close()
        if child.wait() != 0:
            raise RuntimeError(f"Could not render {clip['id']} with its Hit sparks")


def render_phase(name, phrases, angle, crops, output, work):
    files = []
    shots = []
    for i, ((clip, bar), zoom) in enumerate(zip(robot_schedule(phrases, angle, total_bars=16), crops, strict=True)):
        data = json.loads((PACKAGE / clip['clip_data']).read_text())
        hits = hit_events(clip, data, bar)
        base = bar * BAR_SECONDS
        local = [dict(hit, second=round(hit['second'] - base, 7)) for hit in hits]
        files.append(work / f'{name}-{i:02d}.mov')
        render_shot(clip, local, files[-1])
        shots.append({'clip': clip['id'], 'start': base, 'framing': framing(clip, data, zoom), 'hits': hits})
    target = output / f'{name}-alpha.mov'
    join(files, target)
    print(f'{name}: {len(shots)} shots, {sum(len(shot["hits"]) for shot in shots)} projected Hits', flush=True)
    return shots


def build(output):
    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='bossi3dj-cinema-') as folder:
        work = Path(folder)
        solo = render_phase('build', SOLO, 'front', SOLO_FRAMING, output, work)
        duel = render_phase('peak', PEAK[:2], 'duel_wide', DUEL_FRAMING, output, work)
        score = work / 'original-score.wav'
        write_score(score)
        ffmpeg('-ss', 210, '-i', score, '-t', 60, '-af', 'afade=t=in:d=0.6,afade=t=out:st=58.5:d=1.5',
               '-c:a', 'pcm_s16le', output / 'score.wav')
    (output / 'director.json').write_text(json.dumps({'bpm': 128, 'fps': FPS, 'build': solo, 'peak': duel}, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    build(parser.parse_args().output.resolve())


if __name__ == '__main__':
    main()
