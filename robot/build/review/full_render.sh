#!/bin/zsh
# The v1 Clip Library render in two stages, 64 samples, beauty as qtrle: `idle` renders both idle_guard Clips and
# measures their flicker (check-renders); `rest` renders the other six Clips, exports Clip Data, Camera Tracks and the
# Manifest, measures all Clips. Writes robot/build/probe/full/<stage>.DONE and timings to <stage>.time.
cd "${0:A:h}/../../.."
B=/Applications/Blender.app/Contents/MacOS/Blender; PKG=robot/package/v1; P=robot/build/probe/full; STAGE=$1
pgrep -i blender >/dev/null && { echo "Blender running, abort"; exit 1; }
mkdir -p $P; rm -f $P/$STAGE.DONE
if [[ $STAGE == idle ]]; then clips=(idle_guard__front idle_guard__side)
else clips=(jab_cross__front jab_cross__side front_kick__front front_kick__side take_hit__front take_hit__side); fi
t0=$(date +%s)
for c in $clips; do
  rm -rf $PKG/beauty/$c $PKG/beauty/$c.mov $PKG/shadow/$c $PKG/depth/$c
  $B -b robot/build/robot.blend -P robot/build/build_robot.py -- render --package $PKG --clip $c --samples 64 >> $P/$STAGE.log 2>&1 || echo "FAIL $c" >> $P/$STAGE.log
  echo "$c $(( $(date +%s) - t0 ))" >> $P/$STAGE.time
done
[[ $STAGE == rest ]] && $B -b robot/build/robot.blend -P robot/build/build_robot.py -- export --package $PKG >> $P/$STAGE.log 2>&1
$B -b robot/build/robot.blend -P robot/build/build_robot.py -- check-renders --package $PKG --out $P/$STAGE.renders.json >> $P/$STAGE.log 2>&1
touch $P/$STAGE.DONE
