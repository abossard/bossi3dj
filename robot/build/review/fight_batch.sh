#!/bin/zsh
# fight_batch.sh: the fight-clip batch (#32) at low quality, beauty for review: the guard Idle family (idle_guard on
# the capture guard and its variants) into robot/build/probe/fight/beauty, the Mocap fight Moves and their takes into
# robot/build/probe/mocap (review/mocap_proof.py). Progress in robot/build/probe/fight/progress.txt, DONE at the end.
set -e
cd "${0:A:h}/../../.."
B=/Applications/Blender.app/Contents/MacOS/Blender; O=robot/build/probe/fight
mkdir -p $O; rm -f $O/DONE
log() { echo "$(date +%T) $1" >> $O/progress.txt; }
for m in idle_guard idle_guard_v2 idle_guard_v3 idle_guard_v4 idle_guard_v5; do
  for a in front side; do
    [[ -f $O/beauty/${m}__$a.mov ]] && { log "skip ${m}__$a"; continue; }
    nice -n 5 $B -b robot/build/robot.blend -P robot/build/build_robot.py -- render --package $O --clip ${m}__$a \
      --quality low < /dev/null >> $O/render.log 2>&1
    log "done ${m}__$a"
  done
done
nice -n 5 $B -b robot/build/robot.blend -P robot/build/review/mocap_proof.py -- mocap_fist_fight mocap_fist_fight_v2 \
  mocap_jab_elbow mocap_jab_elbow_v2 mocap_uppercut_jab mocap_uppercut_jab_v2 mocap_uppercut_jab_v3 >> $O/render.log 2>&1
log "done mocap fight Moves"
touch $O/DONE
