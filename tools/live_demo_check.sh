#!/bin/bash
# The full live test of the planet as the user's demo check (first run 2026-11-14). Needs the Blender slot, Magic running
# with show.magic loaded by the user and BlackHole 2ch as the default output. Opens nothing in Magic, drives no UI.
#
#     tools/live_demo_check.sh [open] [page] [artnet] [music] [osc] [steer] [record] [stop]     (no argument: all, in this order)
#
# open    make blender-open SCENE=planet (its start check must say ready)
# page    tools/blender_page_test.py against 9210
# artnet  osc/artnet_live_test.py
# music   afplay MUSIC in the background, then 3 s of BlackHole's level (input :0) must be above -60 dB
# osc     Magic must send: within 20 s the bridge's OSC message count (/api/state osc.addresses) must grow, else the
#         remaining steps are skipped and only stop runs
# steer   tools/magic_steering_check.py: 180 s of path, target, height from Magic, then the height takeover
# record  90 s of CAM_OUT, nothing held, then blender/review/video_flicker.py per 15 s stage
# stop    stops afplay, then make blender-kill (the next session rebuilds)
# Outputs: blender/review/out/demo-check-<date>/ (git-ignored), one log per step, summary.txt with each step's exit code.
cd "$(dirname "$0")/.." || exit 1
MUSIC=${MUSIC:-$HOME/Music/Tapes/drowning.mp3}
OUT=blender/review/out/demo-check-$(date +%Y-%m-%d)
mkdir -p "$OUT"
steps=("$@")
[ ${#steps[@]} -eq 0 ] && steps=(open page artnet music osc steer record stop)

run() {   # name, command...: tee the log, record the exit code in $rc
    local name=$1; shift
    echo "== $name: $*"
    "$@" 2>&1 | tee "$OUT/$name.log"
    rc=${PIPESTATUS[0]}
    echo "$name $rc" >> "$OUT/summary.txt"
    echo "== $name exit $rc"
}

osc_count() {   # OSC messages the bridge has received over all addresses
    curl -s -m 5 http://127.0.0.1:9210/api/state | python3 -c 'import json,sys; print(sum(a["n"] for a in ((json.load(sys.stdin).get("osc") or {}).get("addresses") or {}).values()))'
}

osc_gate() {
    local n0 n
    n0=$(osc_count) || return 1
    for _ in $(seq 20); do
        sleep 1
        n=$(osc_count) || return 1
        [ "$n" -gt "$n0" ] && { echo "Magic sends: $((n - n0)) OSC messages since the gate started"; return 0; }
    done
    echo "Magic sent no OSC to 9201 in 20 s: is its audio input BlackHole 2ch and is music playing?"
    return 1
}

skip=0
for s in "${steps[@]}"; do
    [ $skip -eq 1 ] && [ "$s" != stop ] && { echo "== $s skipped"; continue; }
    case $s in
        open)   run open make blender-open SCENE=planet ;;
        page)   run page python3 tools/blender_page_test.py ;;
        artnet) run artnet python3 osc/artnet_live_test.py ;;
        music)  afplay "$MUSIC" & echo $! > "$OUT/afplay.pid"
                sleep 2
                run music sh -c 'ffmpeg -hide_banner -f avfoundation -i ":0" -t 3 -af volumedetect -f null - 2>&1 |
                                 awk "/mean_volume|max_volume/ {print} /mean_volume/ {m = \$5} END {exit (m != \"\" && m > -60 ? 0 : 1)}"' ;;
        osc)    run osc osc_gate; [ "$rc" -ne 0 ] && skip=1 ;;
        steer)  run steer python3 tools/magic_steering_check.py --observe 180 --key vj_height ;;
        record) run record env PYTHONPATH="$HOME/.local/lib/python3.13/site-packages" python3.13 tools/syphon_record.py \
                    --app Blender --server CAM_OUT --seconds 90 --fps 30 --size 960x540 --out "$OUT/unheld.mp4" --vflip
                run flicker .venv/bin/python blender/review/video_flicker.py "$OUT/unheld.mp4" 15 ;;
        stop)   [ -f "$OUT/afplay.pid" ] && kill "$(cat "$OUT/afplay.pid")" 2>/dev/null; rm -f "$OUT/afplay.pid"
                run kill make blender-kill ;;
        *)      echo "unknown step $s"; exit 2 ;;
    esac
done
