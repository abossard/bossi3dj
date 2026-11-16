#!/bin/zsh
# Front-Angle review round 4: rebuild, sweep numbers at the front camera, frames 0 15 29 57 of every Move at 64 samples,
# contact sheets and one full-size frame for shot-reviewer. Writes robot/build/probe/r4/DONE.
cd "${0:A:h}/../../.."
B=/Applications/Blender.app/Contents/MacOS/Blender; P=robot/build/probe/r4
pgrep -i blender >/dev/null && { echo "Blender running, abort"; exit 1; }
rm -rf $P; mkdir -p $P
$B -b --factory-startup -P robot/build/build_robot.py -- build > $P/build.log 2>&1 || { echo BUILD FAIL; exit 1; }
$B -b robot/build/robot.blend -P robot/build/review/camera_sweep.py -- --azimuths=-35 2>&1 | grep -E "^SWEEP" | sed 's/^SWEEP //' > $P/sweep.json
for m in idle_guard jab_cross front_kick take_hit; do for f in 0 15 29 57; do
  $B -b robot/build/robot.blend -P robot/build/build_robot.py -- render --package $P --clip ${m}__front --frames $f-$f --samples 64 --beauty png >> $P/render.log 2>&1 || echo "FAIL $m $f"
done; done
for m in idle_guard jab_cross front_kick take_hit; do zsh robot/build/review/clip_sheet.sh $P ${m}__front $P/sheet_$m.png 0 15 29 57 >/dev/null 2>&1; done
magick -size 1920x1080 xc:'#2a2420' $P/shadow/jab_cross__front/0029.png -composite $P/beauty/jab_cross__front/0029.png -composite -depth 8 PNG24:$P/full_jab29.png
touch $P/DONE
