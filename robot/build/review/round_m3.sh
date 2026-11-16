#!/bin/zsh
# round_m3.sh [ROUND MOVE...]: a Moves preview round: build, check, the stomp's foot contact, previews of the named
# Moves (M3: the three fixed after M2), sheets and the preview video. Writes robot/build/probe/<round>/DONE; Blender
# closes before the sheets.
cd "${0:A:h}/../../.."
B=/Applications/Blender.app/Contents/MacOS/Blender; P=robot/build/probe/${1:-m3}
todo=(${@:2}); (( ${#todo} )) || todo=(power_stomp ground_pound rush_cross)
pgrep -i blender >/dev/null && { echo "Blender running, abort"; exit 1; }
rm -rf $P; mkdir -p $P
$B -b --factory-startup -P robot/build/build_robot.py -- build > $P/build.log 2>&1 || { echo BUILD FAIL > $P/DONE; exit 1; }
$B -b robot/build/robot.blend -P robot/build/build_robot.py -- check --out $P/check.json > $P/check.log 2>&1
$B -b robot/build/robot.blend -P robot/build/review/foot_contact.py -- power_stomp 2>&1 | grep '^CONTACT' | sed 's/^CONTACT //' > $P/contact.json
zsh robot/build/review/preview_all.sh $todo
echo "blender closed $(date +%T)" > $P/blender_closed.txt
zsh robot/build/review/preview_video.sh && zsh robot/build/review/preview_sheets.sh
touch $P/DONE
