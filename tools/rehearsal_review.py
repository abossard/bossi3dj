"""Check the rehearsal export and make four 480-pixel contact sheets for review."""

import argparse
import io
from itertools import groupby
import json
from pathlib import Path
import re
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageOps


PHASES = ('Arrive', 'Build', 'Peak', 'Release')
SAMPLES = (2, 15, 29, 43, 58, 73, 88, 103, 115)


def ffmpeg(*args, stdout=False):
    return subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-threads', '2', *map(str, args)],
                          stdout=subprocess.PIPE if stdout else subprocess.DEVNULL,
                          stderr=subprocess.PIPE, check=True)


def frame(video, second):
    raw = ffmpeg('-ss', second, '-i', video, '-frames:v', 1, '-f', 'image2pipe', '-c:v', 'png', '-',
                 stdout=True).stdout
    with Image.open(io.BytesIO(raw)) as image:
        return image.convert('RGB')


def contact_sheets(video, out, phases=PHASES, phase_seconds=120, offsets=SAMPLES):
    for i, phase in enumerate(phases):
        sheet = Image.new('RGB', (480 * 3, 292 * 3), '#111016')
        draw = ImageDraw.Draw(sheet)
        for j, offset in enumerate(offsets):
            seconds = phase_seconds * i + offset
            x, y = (j % 3) * 480, (j // 3) * 292
            sheet.paste(frame(video, seconds).resize((480, 270)), (x, y))
            elapsed = int(seconds)
            draw.text((x + 8, y + 272), f'{phase}  {elapsed // 60:02d}:{elapsed % 60:02d}', fill='white')
        sheet.save(out / f'{phase.lower()}-sheet.jpg', quality=88)


def source_proof(folder):
    """Place the live Blender and final Magic frames side by side for each cue."""
    sheet = Image.new('RGB', (960, 4 * 292), '#111016')
    draw = ImageDraw.Draw(sheet)
    for i, phase in enumerate(PHASES):
        y = i * 292
        for x, app in ((0, 'blender'), (480, 'magic')):
            with Image.open(folder / f'{app}-{phase.lower()}.png') as image:
                picture = image.convert('RGB').resize((480, 270))
                sheet.paste(ImageOps.flip(picture) if app == 'blender' else picture, (x, y))
            draw.text((x + 8, y + 272), f'{phase}  {app.title()}', fill='white')
    sheet.save(folder / 'source-proof.jpg', quality=88)


def longest_repeat(video):
    hashes = ffmpeg('-i', video, '-an', '-f', 'framemd5', '-', stdout=True).stdout.decode()
    fingerprints = (line.rsplit(',', 1)[1].strip() for line in hashes.splitlines() if not line.startswith('#'))
    return round(max(sum(1 for _ in group) for _, group in groupby(fingerprints)) / 24, 3)


def motion(video, phases=PHASES, phase_seconds=120):
    size = 96, 54
    raw = ffmpeg('-i', video, '-an', '-vf', f'scale={size[0]}:{size[1]},format=gray',
                 '-pix_fmt', 'gray', '-f', 'rawvideo', '-', stdout=True).stdout
    frames = np.frombuffer(raw, dtype=np.uint8).reshape(-1, size[1], size[0])
    stats = {}
    phase_length = phase_seconds * 24
    for i, name in enumerate(phases):
        # Exclude the intentional change between phases and the standby reveal.
        batch = frames[i * phase_length + 36:(i + 1) * phase_length]
        if len(batch) < 2:
            break
        change = np.abs(np.diff(batch.astype(np.int16), axis=0)).mean(axis=(1, 2))
        luma = np.abs(np.diff(batch.mean(axis=(1, 2))))
        stats[name] = {'frame_change_p95': round(float(np.quantile(change, .95)), 2),
                       'mean_luma_jump_p99': round(float(np.quantile(luma, .99)), 2)}
    return stats


def review(video, out, cinema=False):
    out.mkdir(parents=True, exist_ok=True)
    probe = subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_chapters',
                                     '-show_format', '-of', 'json', str(video)])
    container = json.loads(probe)
    streams = container['streams']
    v = next(s for s in streams if s['codec_type'] == 'video')
    a = next(s for s in streams if s['codec_type'] == 'audio')
    chapters = [(s['tags']['title'], float(s['start_time']), float(s['end_time'])) for s in container['chapters']]
    phases = ('Android', 'Exchange') if cinema else PHASES
    phase_seconds = 30 if cinema else 120
    size = (960, 540) if cinema else (480, 270)
    expected = [(name, phase_seconds * i, phase_seconds * (i + 1)) for i, name in enumerate(phases)]
    duration = len(phases) * phase_seconds
    assert (v['width'], v['height'], v['avg_frame_rate']) == (*size, '24/1'), v
    assert int(v['nb_frames']) == duration * 24, v
    assert abs(float(a['duration']) - duration) < 0.03, a
    assert chapters == expected, chapters

    log = ffmpeg('-i', video, '-an', '-vf', 'scale=160:90,blackdetect=d=0.4:pix_th=0.08,freezedetect=n=-58dB:d=0.5',
                 '-f', 'null', '-').stderr.decode()
    black = re.findall(r'black_start:([\d.]+) black_end:([\d.]+)', log)
    freezes = re.findall(r'lavfi\.freezedetect\.freeze_(start|end): ([\d.]+)', log)
    sound = ffmpeg('-i', video, '-vn', '-af', 'ebur128=peak=true', '-f', 'null', '-').stderr.decode()
    integrated = re.findall(r'^\s+I:\s+(-?[\d.]+) LUFS', sound, flags=re.MULTILINE)
    true_peak = re.findall(r'^\s+Peak:\s+(-?[\d.]+) dBFS', sound, flags=re.MULTILINE)
    data = {'format': f'{size[0]}x{size[1]} @ 24 fps', 'duration': float(container['format']['duration']),
            'chapters': chapters, 'video_frames': int(v['nb_frames']),
            'near_black_intervals': [[float(start), float(end)] for start, end in black],
            'freeze_events': [[kind, float(second)] for kind, second in freezes],
            'longest_identical_frame_run_s': longest_repeat(video),
            'motion_by_phase': motion(video, phases, phase_seconds),
            'integrated_lufs': float(integrated[-1]), 'true_peak_dbfs': float(true_peak[-1])}
    (out / 'measurements.json').write_text(json.dumps(data, indent=2) + '\n')
    offsets = (0.8, 2.4, 6.1, 9.9, 12.2, 16.9, 20.3, 25.4, 28.9) if cinema else SAMPLES
    contact_sheets(video, out, phases, phase_seconds, offsets)
    if cinema:
        impact_sheet(video, out)
    print(json.dumps(data, indent=2))


def impact_sheet(video, out):
    director = json.loads((video.parent / 'director.json').read_text())
    featured = (
        ('build', ('mocap_jab_elbow_v2', 'mocap_flip_uppercut', 'palm_strike', 'mocap_uppercut_jab_v3')),
        ('peak', ('knee_combo', 'hammer_hit', 'core_strike', 'quake_stomp')),
    )
    chosen = []
    for i, (phase, moves) in enumerate(featured):
        for move in moves:
            shot = next(row for row in director[phase] if row['clip'].split('__')[0] == move)
            hit = max(shot['hits'], key=lambda event: event['strength'])
            chosen.append((i * 30 + hit['second'] + 0.23, move))
    sheet = Image.new('RGB', (960, 292 * 4), '#111016')
    draw = ImageDraw.Draw(sheet)
    for i, (seconds, name) in enumerate(chosen):
        x, y = (i % 2) * 480, (i // 2) * 292
        sheet.paste(frame(video, seconds).resize((480, 270)), (x, y))
        draw.text((x + 8, y + 272), f'{seconds:05.2f}s  {name}', fill='white')
    sheet.save(out / 'impacts-sheet.jpg', quality=90)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reel', type=Path)
    parser.add_argument('out', type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--motion-only', action='store_true')
    modes.add_argument('--robot-cinema', action='store_true')
    args = parser.parse_args()
    if args.motion_only:
        print(json.dumps(motion(args.reel), indent=2))
    else:
        review(args.reel, args.out, args.robot_cinema)


if __name__ == '__main__':
    main()
