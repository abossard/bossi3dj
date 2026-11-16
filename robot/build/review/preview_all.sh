#!/bin/zsh
# preview_all.sh: every Clip of moves.py on both Angles through `render --preview` (Eevee, 960x540, beauty only)
# into robot/build/probe/preview/beauty/<clip>.mov, one Blender at a time. Writes robot/build/probe/preview/DONE.
cd "${0:A:h}/../../.."
B=/Applications/Blender.app/Contents/MacOS/Blender; P=robot/build/probe/preview
pgrep -i blender >/dev/null && { echo "Blender running, abort"; exit 1; }
rm -rf $P; mkdir -p $P
$B -b --factory-startup -P robot/build/build_robot.py -- build > $P/build.log 2>&1 || { echo BUILD FAIL > $P/DONE; exit 1; }
t0=$(date +%s)
for m in $(python3 -c "import sys; sys.path.insert(0, 'robot/build'); import moves; print(' '.join(moves.MOVES))"); do
  for a in front side; do
    $B -b robot/build/robot.blend -P robot/build/build_robot.py -- render --package $P --clip ${m}__$a --preview >> $P/render.log 2>&1 \
      || echo "FAIL ${m}__$a" >> $P/fails.txt
  done
done
echo "$(( $(date +%s) - t0 )) s" > $P/time.txt
touch $P/DONE
