"""Assemble the VJ reel and four muted Magic sources from project captures and Robot v1."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw, ImageFont

from rehearsal_score import write_score


ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / 'docs/video'
PACKAGE = ROOT / 'robot/package/v1'
OUTPUT = MEDIA / 'rehearsal-v3'
SIZE = (480, 270)
FPS = 24
BAR_SECONDS = 1.875
BAR_FRAMES = 45
PHASES = 'Arrive', 'Build', 'Peak', 'Release'
CREDIT = 'Security Bot Rig (CC BY), Blender Foundation, modified for the Robot Scene'
CREDIT_URL = 'https://studio.blender.org/characters/security-bot/v1/'

# Each row is an eight-bar phrase. Angle gaps are intentional edits at Key Poses.
BUILD = (
    'idle_guard/f guard_shuffle/s idle_guard_v2/s settle_low/s idle_low/s rise_guard/s',
    'idle_guard_v3/f take_hit/f mocap_jab_elbow/f guard_shuffle/s take_hit/s idle_guard_v4/s',
    'settle_low/f palm_strike/s idle_low/f rush_cross/s guard_shuffle/f',
    'mocap_jab_elbow_v2/s idle_guard_v5/f mocap_uppercut_jab/f front_kick/s guard_shuffle/f',
    'settle_low/s palm_strike/f idle_low/f rush_cross/f mocap_fist_fight/s',
    'leap_slam/s idle_crouch/s crouch_strike/f stand_up/f mocap_jab_elbow_v2/f',
    'mocap_flip_uppercut/f front_kick/s take_hit/f mocap_uppercut_jab_v2/s mocap_fist_fight_v2/f',
    'mocap_uppercut_jab_v3/s front_kick/f take_hit/s guard_shuffle/s idle_guard_v4/f idle_guard_v5/f',
)
PEAK = (
    'duel_idle/w circle/w knee_combo/l hammer_hit/w duel_idle_crouch/l core_strike/l',
    'hammer_dodge/w quake_stomp/w sweep_jump/l core_strike/w circle/l',
    'knee_combo/w hammer_hit/l core_strike/l hammer_dodge/l duel_idle_low/l sweep_jump/w duel_idle_crouch/w',
    'core_strike/w circle/w duel_idle/w duel_idle/l knee_combo/l duel_idle/w',
    'hammer_dodge/w quake_stomp/l sweep_jump/w core_strike/l knee_combo/l duel_idle/w',
    'circle/l hammer_hit/l core_strike/w hammer_dodge/l quake_stomp/w',
    'duel_idle_low/w sweep_jump/l core_strike/l knee_combo/w hammer_hit/w core_strike/w',
    'hammer_dodge/w quake_stomp/l sweep_jump/l core_strike/l circle/w',
)
ANGLES = {'f': 'front', 's': 'side', 'w': 'duel_wide', 'l': 'duel_low'}

# Capture, in point (seconds), length (bars), playback rate, flip.
ORBIT_SUN = ROOT / 'blender/review/out/issue25/rec/orbit_sun_on.mp4'
ARRIVE = (
    (MEDIA / 'gpu-terrain-round17.mp4', 2, 16, 0.725, False),
    (MEDIA / 'gpu-terrain-round17.mp4', 40, 8, 0.9, False),
    (MEDIA / 'terrain-test-after.mp4', 4, 8, 0.89, False),
    (MEDIA / 'gpu-terrain-round16.mp4', 10, 8, 0.94, True),
    (MEDIA / 'terrain-test-after.mp4', 67, 12, 0.82, False),
    (ORBIT_SUN, 12, 8, 0.98, True),
    (MEDIA / 'gpu-terrain-run.mp4', 171, 4, 0.78, False),
)
RELEASE = (
    (MEDIA / 'gpu-terrain-round17.mp4', 56, 8, 0.85, False),
    (MEDIA / 'terrain-test-after.mp4', 4, 8, 0.89, False),
    (MEDIA / 'path-camera-run-2-phone.mp4', 88, 8, 0.87, False),
    (MEDIA / 'gpu-terrain-run.mp4', 98, 8, 0.65, False),
    (MEDIA / 'gpu-terrain-run.mp4', 111, 4, 0.94, False),
    (MEDIA / 'gpu-terrain-run.mp4', 127, 4, 0.52, False),
    (MEDIA / 'gpu-terrain-test.mp4', 44.5, 8, 0.56, False),
    (MEDIA / 'path-camera-run-2-phone.mp4', 293, 16, 0.56, False),
)


def ffmpeg(*args):
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                    '-filter_threads', '2', '-filter_complex_threads', '2', *map(str, args)], check=True)


def encode(target, frames):
    return ('-an', '-frames:v', frames, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', 19,
            '-threads', 2, '-pix_fmt', 'yuv420p', '-video_track_timescale', 24000, target)


def join(inputs, output, additional=()):
    # All input names are generated, so the concat list uses relative paths and FFmpeg's safe mode.
    listing = inputs[0].parent / f'{output.stem}.concat'
    listing.write_text(''.join(f'file {path.name}\n' for path in inputs), encoding='utf-8')
    try:
        ffmpeg('-f', 'concat', '-i', listing, *additional, '-c:v', 'copy', '-movflags', '+faststart', output)
    finally:
        listing.unlink()


def timing(rate):
    width, height = SIZE
    return (f'scale={width}:{height}:flags=lanczos,setsar=1,settb=AVTB,'
            f'setpts=(PTS-STARTPTS)/{rate:.8f},fps={FPS},tpad=stop_mode=clone:stop_duration=0.13')


def credit_card(path):
    card = Image.new('RGBA', SIZE)
    draw = ImageDraw.Draw(card)
    font = ImageFont.truetype('/System/Library/Fonts/Menlo.ttc', 10)
    draw.rectangle((0, 213, SIZE[0], SIZE[1]), fill=(5, 5, 12, 224))
    draw.text((17, 225), 'Security Bot Rig  /  Blender Foundation  /  CC BY', font=font, fill='#f1dae6')
    draw.text((17, 242), 'studio.blender.org/characters/security-bot/v1/', font=font, fill='#d0b7c9')
    card.save(path)


def planet_shot(item, target, opening=False, closing=False):
    capture, start, bars, rate, flip = item
    length = bars * BAR_SECONDS
    filters = ('vflip,' if flip else '') + timing(rate)
    if opening:
        filters += ',fade=t=in:st=0:d=1.5'
    if closing:
        card = target.parent / 'credit.png'
        credit_card(card)
        filters += f',fade=t=out:st={length - 3.75}:d=3.75[v];[v][1:v]overlay=enable=gte(t\\,{length - 6})'
        ffmpeg('-ss', start, '-i', capture, '-i', card, '-filter_complex', filters,
               *encode(target, bars * BAR_FRAMES))
    else:
        ffmpeg('-ss', start, '-i', capture, '-vf', filters, *encode(target, bars * BAR_FRAMES))
    return target


def robot_shot(clip, bar, target, peak):
    angle = clip['angle']
    plate = PACKAGE / 'backdrop/arclink_city_1' / f'{angle}.mov'
    beauty = PACKAGE / clip['passes']['beauty']
    bars = clip['beats'] // 4
    rate = clip['frames'] / 30 / (bars * BAR_SECONDS)
    width, height = SIZE
    resize = f'scale={width}:{height}:flags=lanczos,setsar=1'
    gain = 0.016 if peak else 0.008
    if peak and 28 <= bar < 32 or not peak and bar >= 60:
        gain = 0.0
    # A small glow from the soundtrack's kick grid, with the bar offsets shared by the score.
    pulse = f"eq=brightness='{gain}*exp(-11*mod(t,0.46875))':eval=frame"
    grade = 'eq=contrast=1.055:brightness=0.005:saturation=0.90'
    framing = ''
    if not peak:
        crop = '456:256:12:12' if angle == 'front' else '432:244:24:0'
        framing = f',crop={crop},scale=480:270:flags=lanczos,setsar=1'
    filters = (f'[0:v]{resize},fps={FPS},setpts=PTS-STARTPTS[bg];'
               f'[1:v]format=rgba,{timing(rate)}[fg];'
               f'[bg][fg]overlay=shortest=1{framing},{grade},{pulse}')
    ffmpeg('-ss', (bar * BAR_SECONDS) % 7.6, '-stream_loop', -1, '-i', plate, '-i', beauty,
           '-filter_complex', filters, *encode(target, bars * BAR_FRAMES))
    return target


def robot_schedule(phrases, fixed_angle=None, total_bars=64):
    clips = {c['id']: c for c in json.loads((PACKAGE / 'manifest.json').read_text())['clips']}
    schedule = []
    bar = 0
    pose = 'guard'
    for phrase in phrases:
        phrase_start = bar
        for shot in phrase.split():
            move, angle = shot.split('/')
            clip = clips[f'{move}__{fixed_angle or ANGLES[angle]}']
            if clip['key_in'] != pose:
                raise ValueError(f"Bar {bar}: {clip['id']} starts in {clip['key_in']}, expected {pose}")
            schedule.append((clip, bar))
            bar += clip['beats'] // 4
            pose = clip['key_out']
        if bar - phrase_start != 8:
            raise ValueError(f'Phrase at bar {phrase_start} contains {bar - phrase_start} bars')
    if bar != total_bars or pose != 'guard':
        raise ValueError(f'Robot phase ends in {pose} on bar {bar}, expected guard on bar {total_bars}')
    return schedule


def alpha_shot(clip, target):
    bars = clip['beats'] // 4
    rate = clip['frames'] / 30 / (bars * BAR_SECONDS)
    timed = timing(rate)
    filters = (f'[0:v]format=rgba,{timed}[beauty];'
               f"[1:v]{timed},format=gray,lut=y='clip((val-2)*0.72,0,128)'[shadow];"
               '[2:v]format=rgba[black];[black][shadow]alphamerge=shortest=1[contact];'
               '[contact][beauty]overlay=shortest=1:format=auto,format=argb')
    ffmpeg('-i', PACKAGE / clip['passes']['beauty'], '-i', PACKAGE / clip['passes']['shadow'],
           '-f', 'lavfi', '-i', 'color=black:size=480x270:rate=24', '-filter_complex', filters,
           '-an', '-frames:v', bars * BAR_FRAMES, '-c:v', 'qtrle', '-pix_fmt', 'argb',
           '-video_track_timescale', 24000, target)
    return target


def render_foregrounds(output):
    """Pre-render only the Androids, with one camera-matched Angle per cue."""
    output.mkdir(parents=True, exist_ok=True)
    write_score(output / 'score.wav')
    with TemporaryDirectory(prefix='bossi3dj-alpha-') as folder, ThreadPoolExecutor(max_workers=3) as pool:
        for name, phrases, angle in (('build', BUILD, 'front'), ('peak', PEAK, 'duel_wide')):
            jobs = [pool.submit(alpha_shot, clip, Path(folder) / f'{i:03}.mov')
                    for i, (clip, _bar) in enumerate(robot_schedule(phrases, angle))]
            target = output / f'{name}-alpha.mov'
            join([job.result() for job in jobs], target)
            print(target, flush=True)


def chapters(path):
    lines = [';FFMETADATA1', 'title=bossi3dj | VJ rehearsal reel',
             f'comment={CREDIT}. {CREDIT_URL}']
    for i, phase in enumerate(PHASES):
        lines.extend(('[CHAPTER]', 'TIMEBASE=1/1000', f'START={120_000*i}', f'END={120_000*(i+1)}', f'title={phase}'))
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def render(output):
    output.mkdir(parents=True, exist_ok=True)
    score = output / 'score.wav'
    if not score.exists():
        write_score(score)
    with TemporaryDirectory(prefix='bossi3dj-edit-') as folder, ThreadPoolExecutor(max_workers=3) as pool:
        work = Path(folder)
        phase_paths = []
        for name, source in zip(PHASES, (ARRIVE, BUILD, PEAK, RELEASE), strict=True):
            dest = output / f'{name.lower()}.mp4'
            if name in ('Arrive', 'Release'):
                if sum(item[2] for item in source) != 64:
                    raise ValueError(f'{name} must contain 64 bars')
                jobs = [pool.submit(planet_shot, item, work / f'{name}-{i:03}.mp4',
                                    name == 'Arrive' and i == 0, name == 'Release' and i == len(source) - 1)
                        for i, item in enumerate(source)]
            else:
                jobs = [pool.submit(robot_shot, clip, bar, work / f'{name}-{i:03}.mp4', name == 'Peak')
                        for i, (clip, bar) in enumerate(robot_schedule(source))]
            join([job.result() for job in jobs], dest)
            phase_paths.append(dest)
            print(f'Wrote {name}', flush=True)
        metadata = work / 'chapters.txt'
        chapters(metadata)
        reel = output / 'bossi3dj-rehearsal.mp4'
        join(phase_paths, reel, ('-i', score, '-f', 'ffmetadata', '-i', metadata,
                               '-map', '0:v:0', '-map', '1:a:0', '-map_metadata', '2', '-map_chapters', '2',
                               '-c:a', 'aac', '-b:a', '192k'))
        print(reel)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--foreground-only', action='store_true', help='write alpha-only Robot phases for live compositing')
    args = parser.parse_args()
    (render_foregrounds if args.foreground_only else render)(args.output.resolve())


if __name__ == '__main__':
    main()
