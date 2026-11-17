#!/bin/zsh
# variant_batch.sh: the first variant batch (#32) at low quality into robot/build/probe/variants, a package of its
# own: the Idle variants and jab_cross with its takes are rendered and encoded, the base Idle Clips are copied from
# robot/package/v1 (the Idle bases carry no weight layer, so they are unchanged), then Clip Data and the Manifest are
# exported, the Manifest is cut to the complete Moves and validated. The Mocap takes render into
# robot/build/probe/mocap (review/mocap_proof.py). Progress in robot/build/probe/variants/progress.txt, DONE at the end.
set -e
cd "${0:A:h}/../../.."
B=/Applications/Blender.app/Contents/MacOS/Blender; V=robot/package/v1; O=robot/build/probe/variants
mkdir -p $O/beauty $O/shadow $O/depth; rm -f $O/DONE
log() { echo "$(date +%T) $1" >> $O/progress.txt; }
clips=($(python3 -c "import sys; sys.path.insert(0, 'robot/build'); import moves
print(' '.join(n for n, m in moves.MOVES.items() if m.variant_of) + ' jab_cross')"))
for m in $clips; do
  for a in front side; do
    c=${m}__$a
    [[ -f $O/beauty/$c.mov && -f $O/depth/$c.mov ]] && { log "skip $c"; continue; }
    nice -n 5 $B -b robot/build/robot.blend -P robot/build/build_robot.py -- render --package $O --clip $c --quality low \
      < /dev/null >> $O/render.log 2>&1
    nice -n 10 .venv/bin/python robot/build/encode_passes.py --package $O --clip $c >> $O/encode.log 2>&1
    log "done $c"
  done
done
for m in idle_guard idle_low idle_crouch; do
  for a in front side; do for p in beauty shadow depth; do cp $V/$p/${m}__$a.mov $O/$p/; done; done
done
nice -n 5 $B -b robot/build/robot.blend -P robot/build/review/mocap_proof.py -- mocap_flip_uppercut mocap_flip_uppercut_v2 \
  mocap_flip_uppercut_v3 >> $O/render.log 2>&1
log "done mocap takes"
$B -b robot/build/robot.blend -P robot/build/build_robot.py -- export --package $O > $O/export.log 2>&1
python3 robot/build/review/manifest_complete.py $O >> $O/progress.txt 2>&1
python3 robot/magic/manifest.py $O/manifest.json > $O/validator.txt 2>&1 && r=0 || r=$?; echo "validator exit $r" >> $O/validator.txt
log finished
touch $O/DONE
