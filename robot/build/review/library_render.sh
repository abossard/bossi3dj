#!/bin/zsh
# library_render.sh: the Clip Library at 64 samples into robot/package/v1, resumable: one Clip per Blender run, a
# Clip already complete (review/clip_complete.py) is skipped, so a stop costs at most one Clip. Order: moves.py order
# with ground_pound last. Builds and checks first and stops on a failed check; stops when another Blender runs.
# Then encodes each Clip, exports Clip Data, Camera Tracks and the Manifest, and runs the validator.
# Log and timings: robot/build/probe/library/; DONE or STOPPED there at the end.
cd "${0:A:h}/../../.."
setopt null_glob
B=/Applications/Blender.app/Contents/MacOS/Blender; PKG=robot/package/v1; P=robot/build/probe/library
mkdir -p $P; rm -f $P/DONE $P/STOPPED
stop() { echo "$(date +%T) $1" | tee -a $P/progress.txt > $P/STOPPED; exit 1; }
pgrep -i blender >/dev/null && stop "another Blender runs"
$B -b --factory-startup -P robot/build/build_robot.py -- build > $P/build.log 2>&1 || stop "build failed"
$B -b robot/build/robot.blend -P robot/build/build_robot.py -- check --out $P/check.json > $P/check.log 2>&1 || stop "check failed"
jq -e '[to_entries[].value | select(.planted_sole_error_m > 0.005 or .planted_ankle_gap_m > 0.005 or .lowest_point_m < -0.005)] | length == 0' $P/check.json >/dev/null \
  || stop "check out of bounds"
python3 -c "import sys; sys.path.insert(0, 'robot/build'); import moves
order = [m for m in moves.MOVES if m != 'ground_pound'] + ['ground_pound']
for m in order: print(m, moves.move_frames(moves.MOVES[m]))" > $P/order.txt
echo "$(date +%T) start" >> $P/progress.txt
while read -u 3 m n; do
  for a in front side; do
    c=${m}__$a
    python3 robot/build/review/clip_complete.py $PKG $c $n && { echo "$(date +%T) skip $c" >> $P/progress.txt; continue; }
    pgrep -i blender >/dev/null && stop "another Blender runs before $c"
    rm -rf $PKG/beauty/$c $PKG/beauty/$c.mov $PKG/beauty/${c}_[0-9]*.mov $PKG/shadow/$c $PKG/shadow/$c.mov $PKG/depth/$c $PKG/depth/$c.mov
    t0=$(date +%s)
    $B -b robot/build/robot.blend -P robot/build/build_robot.py -- render --package $PKG --clip $c --samples 64 >> $P/render.log 2>&1 < /dev/null \
      || stop "render failed on $c"
    nice -n 10 .venv/bin/python robot/build/encode_passes.py --package $PKG --clip $c >> $P/encode.log 2>&1 || stop "encode failed on $c"
    python3 robot/build/review/clip_complete.py $PKG $c $n || stop "$c incomplete after render"
    echo "$(date +%T) done $c $n frames $(( $(date +%s) - t0 )) s" >> $P/progress.txt
  done
done 3< $P/order.txt
$B -b robot/build/robot.blend -P robot/build/build_robot.py -- export --package $PKG > $P/export.log 2>&1 || stop "export failed"
python3 robot/magic/manifest.py $PKG/manifest.json > $P/validator.txt 2>&1; echo "validator exit $?" >> $P/validator.txt
echo "$(date +%T) finished" >> $P/progress.txt
touch $P/DONE
