#!/bin/zsh
# library_render.sh [MOVE...]: the Clip Library into robot/package/v1, resumable; QUALITY=low (Eevee, minutes) or
# high (Cycles at SAMPLES, default 64; hours). <package>/quality/<clip> records each Clip's quality, and a Clip counts
# as complete only at the quality asked for, so a high run replaces a low package Clip by Clip; FORCE=1 renders all: one Clip per Blender run, a
# Clip already complete (review/clip_complete.py) is skipped, so a stop costs at most one Clip. Order: the Clip Library's order (library.py)
# with ground_pound last, then the Exchanges (exchanges.py) on the duel Angles. Builds and checks first and stops on a failed check; stops when another Blender runs.
# Named Moves render in that order instead. DEADLINE=HH:MM: no Clip starts that the last measured seconds per frame
# (SPF to begin with) say ends later. Then encodes each Clip, exports Clip Data, Camera Tracks and the Manifest, keeps
# only Moves complete on every Angle in it (review/manifest_complete.py), and runs the validator.
# Log and timings: robot/build/probe/library/; DONE or STOPPED there at the end.
cd "${0:A:h}/../../.."
setopt null_glob
B=/Applications/Blender.app/Contents/MacOS/Blender; PKG=robot/package/v1; P=robot/build/probe/library
mkdir -p $P; rm -f $P/DONE $P/STOPPED
SAMPLES=${SAMPLES:-64}; spf=${SPF:-16}; QUALITY=${QUALITY:-high}   # low: Eevee (build_robot.use_low); high: Cycles
mkdir -p $PKG/quality
complete() { [[ -z $FORCE ]] && python3 robot/build/review/clip_complete.py $PKG $1 $2 && [[ "$(cat $PKG/quality/$1 2>/dev/null)" == $QUALITY ]]; }
deadline=0; [[ -n $DEADLINE ]] && deadline=$(date -j -f "%Y-%m-%d %H:%M" "$(date +%Y-%m-%d) $DEADLINE" +%s)
stop() { echo "$(date +%T) $1" | tee -a $P/progress.txt > $P/STOPPED; exit 1; }
pgrep -i blender >/dev/null && stop "another Blender runs"
$B -b --factory-startup -P robot/build/build_robot.py -- build > $P/build.log 2>&1 || stop "build failed"
$B -b robot/build/robot.blend -P robot/build/build_robot.py -- check --out $P/check.json > $P/check.log 2>&1 || stop "check failed"
jq -e '[to_entries[].value | select(.planted_sole_error_m > 0.005 or .planted_ankle_gap_m > 0.005 or .lowest_point_m < -0.005)] | length == 0' $P/check.json >/dev/null \
  || stop "check out of bounds"
python3 -c "import sys; sys.path.insert(0, 'robot/build'); import moves, library, exchanges as X
L = library.LIBRARY
order = sys.argv[1:] or [m for m in L if m != 'ground_pound'] + ['ground_pound'] + list(X.EXCHANGES)
for m in order:
    ex = X.EXCHANGES.get(m)
    print(m, moves.move_frames(ex.android if ex else L[m]), 'duel_wide duel_low' if ex else 'front side')" "$@" > $P/order.txt
echo "$(date +%T) start" >> $P/progress.txt
while read -u 3 m n angles; do
  for a in ${=angles}; do
    c=${m}__$a
    complete $c $n && { echo "$(date +%T) skip $c" >> $P/progress.txt; continue; }
    pgrep -i blender >/dev/null && stop "another Blender runs before $c"
    if (( deadline && $(date +%s) + n * spf + 30 > deadline )); then echo "$(date +%T) cut $c (needs $(( n * spf )) s)" >> $P/progress.txt; continue; fi
    rm -f $PKG/quality/$c
    rm -rf $PKG/beauty/$c $PKG/beauty/$c.mov $PKG/beauty/${c}_[0-9]*.mov $PKG/shadow/$c $PKG/shadow/$c.mov $PKG/depth/$c $PKG/depth/$c.mov
    t0=$(date +%s)
    $B -b robot/build/robot.blend -P robot/build/build_robot.py -- render --package $PKG --clip $c --samples $SAMPLES --quality $QUALITY >> $P/render.log 2>&1 < /dev/null \
      || stop "render failed on $c"
    nice -n 10 .venv/bin/python robot/build/encode_passes.py --package $PKG --clip $c >> $P/encode.log 2>&1 || stop "encode failed on $c"
    python3 robot/build/review/clip_complete.py $PKG $c $n || stop "$c incomplete after render"
    echo $QUALITY > $PKG/quality/$c
    took=$(( $(date +%s) - t0 )); spf=$(( (took + n - 1) / n ))
    label=$QUALITY; [[ $QUALITY == high ]] && label="high, $SAMPLES samples"
    echo "$(date +%T) done $c $n frames $took s ($label)" >> $P/progress.txt
  done
done 3< $P/order.txt
$B -b robot/build/robot.blend -P robot/build/build_robot.py -- export --package $PKG > $P/export.log 2>&1 || stop "export failed"
python3 robot/build/review/manifest_complete.py $PKG >> $P/progress.txt 2>&1 || stop "manifest filter failed"
python3 robot/magic/manifest.py $PKG/manifest.json > $P/validator.txt 2>&1; echo "validator exit $?" >> $P/validator.txt
echo "$(date +%T) finished" >> $P/progress.txt
touch $P/DONE
