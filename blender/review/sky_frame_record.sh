#!/bin/bash
# Issue #25: before/after recordings of the SKY_FRAME variant with music, for the user's taste call.
#
#     blender/review/sky_frame_record.sh OUT_DIR CLIP...      (CLIP: a name, e.g. vantage_moon_off)
#
# Plays MUSIC straight into BlackHole 2ch (ffmpeg audiotoolbox, as robot/magic/live_test.py) so Magic hears it, then
# per clip waits for OUT_DIR/CLIP.flag (blend_live.py's "flag", written when the clip's shot starts) and records
# CAM_OUT for SECONDS (tools/syphon_record.py). At the end each clip gets the track's stretch from its flag's time:
# OUT_DIR/CLIP.mp4. Start the Blender jobs one after another while this runs. Binds no port, drives no Magic UI.
cd "$(dirname "$0")/../.." || exit 1
OUT=$1; shift
MUSIC=${MUSIC:-$HOME/Music/Tapes/drowning.mp3}
SECONDS_=${SECONDS_:-30}
FFMPEG=/opt/homebrew/bin/ffmpeg
mkdir -p "$OUT"
idx=$($FFMPEG -hide_banner -f lavfi -i anullsrc -t 0.1 -f audiotoolbox -list_devices true - 2>&1 |
      sed -n 's/.*\[\([0-9]*\)\] *BlackHole 2ch.*/\1/p' | head -1)
[ -z "$idx" ] && { echo "no BlackHole 2ch"; exit 1; }
t_music=$(python3 -c 'import time; print(time.time())')
$FFMPEG -v error -stream_loop -1 -i "$MUSIC" -f audiotoolbox -audio_device_index "$idx" - &
player=$!
trap 'kill $player 2>/dev/null' EXIT
for clip in "$@"; do
    PYTHONPATH=~/.local/lib/python3.13/site-packages python3.13 tools/syphon_record.py --app Blender --server CAM_OUT \
        --seconds "$SECONDS_" --fps 30 --size 960x540 --out "$OUT/$clip.video.mp4" --flag "$OUT/$clip.flag" || exit 1
done
kill $player
for clip in "$@"; do
    off=$(python3 -c "import os; print(max(os.path.getmtime('$OUT/$clip.flag') - $t_music, 0.0))")
    $FFMPEG -v error -y -i "$OUT/$clip.video.mp4" -stream_loop -1 -ss "$off" -i "$MUSIC" -map 0:v -map 1:a -c:v copy \
        -c:a aac -shortest "$OUT/$clip.mp4" && rm "$OUT/$clip.video.mp4"
    echo "$clip: music from $off s"
done
