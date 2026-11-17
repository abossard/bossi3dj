#!/bin/zsh
# mocap_reel.sh [NAME LEFT RIGHT [LEFT RIGHT ...]]: Clips side by side for the user to judge (#31), one segment per
# pair, each played twice: LEFT and RIGHT are Clip paths without the Angle (…/beauty/jab_cross reads
# jab_cross__front.mov and jab_cross__side.mov); top row front, bottom row side, over dark grey so the alpha shows.
# The shorter Clip loops to the longer one's length. Default: the mocap proof, hand-keyed package Clips left, Mocap
# Clips right, as mocap_reel.
# Output: robot/build/probe/mocap/<NAME>.mp4 and <NAME>.txt (start times; this ffmpeg has no drawtext).
set -e
cd "${0:A:h}/../../.."
P=robot/build/probe/mocap; K=robot/package/v1/beauty; T=$P/reel_tmp; rm -rf $T; mkdir -p $T
if (( $# )); then NAME=$1; shift; PAIRS=("$@"); else
  NAME=mocap_reel; PAIRS=($K/idle_guard $P/mocap_idle $K/uppercut_combo $P/mocap_flip_uppercut); fi
len() { ffprobe -v error -show_entries format=duration -of csv=p=0 $1; }
i=0; t=0; : > $P/$NAME.txt
for l r in $PAIRS; do
  a=$(len ${l}__front.mov); b=$(len ${r}__front.mov); d=$(( 2 * (a > b ? a : b) ))
  i=$((i+1)); o=$T/$(printf %02d $i).mp4
  nice -n 15 ffmpeg -v error -y -stream_loop -1 -i ${l}__front.mov -stream_loop -1 -i ${r}__front.mov \
    -stream_loop -1 -i ${l}__side.mov -stream_loop -1 -i ${r}__side.mov \
    -f lavfi -i color=c=0x202020:s=1920x1080:r=30 -filter_complex \
    "[0:v]scale=960:540,setsar=1[a];[1:v]scale=960:540,setsar=1[b];[2:v]scale=960:540,setsar=1[c];[3:v]scale=960:540,setsar=1[d];[a][b][c][d]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0[g];[4:v][g]overlay,format=yuv420p" \
    -t $d -r 30 -c:v libx264 -preset veryfast -crf 20 -an $o
  printf "%02d:%05.2f  left %s | right %s; top front, bottom side\n" $((t/60)) $((t%60)) $l $r >> $P/$NAME.txt
  t=$((t + d))
  echo "file '$(basename $o)'" >> $T/list.txt
done
nice -n 15 ffmpeg -v error -y -f concat -safe 0 -i $T/list.txt -c copy $P/$NAME.mp4
rm -rf $T
echo $P/$NAME.mp4 ${t}s
