#!/bin/zsh
# mocap_reel.sh: the mocap proof (#31) beside today's hand-keyed Clips, one segment per pair, each played twice:
# left the hand-keyed package Clip (robot/package/v1/beauty), right the Mocap Clip (review/mocap_proof.py), top row
# front, bottom row side, over dark grey so the alpha shows. The shorter Clip loops to the longer one's length.
# Output: robot/build/probe/mocap/mocap_reel.mp4 and mocap_reel.txt (start times; this ffmpeg has no drawtext).
set -e
cd "${0:A:h}/../../.."
P=robot/build/probe/mocap; K=robot/package/v1/beauty; T=$P/reel_tmp; rm -rf $T; mkdir -p $T
PAIRS=("idle_guard mocap_idle" "uppercut_combo mocap_flip_uppercut")
i=0; t=0; : > $P/mocap_reel.txt
for pair in $PAIRS; do
  hand=${pair% *}; mo=${pair#* }
  len() { ffprobe -v error -show_entries format=duration -of csv=p=0 $1; }
  d=$(( 2 * ( $(len $K/${hand}__front.mov) > $(len $P/${mo}__front.mov) ? $(len $K/${hand}__front.mov) : $(len $P/${mo}__front.mov) ) ))
  i=$((i+1)); o=$T/$(printf %02d $i).mp4
  nice -n 15 ffmpeg -v error -y -stream_loop -1 -i $K/${hand}__front.mov -stream_loop -1 -i $P/${mo}__front.mov \
    -stream_loop -1 -i $K/${hand}__side.mov -stream_loop -1 -i $P/${mo}__side.mov \
    -f lavfi -i color=c=0x202020:s=1920x1080:r=30 -filter_complex \
    "[0:v]scale=960:540,setsar=1[a];[1:v]scale=960:540,setsar=1[b];[2:v]scale=960:540,setsar=1[c];[3:v]scale=960:540,setsar=1[d];[a][b][c][d]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0[g];[4:v][g]overlay,format=yuv420p" \
    -t $d -r 30 -c:v libx264 -preset veryfast -crf 20 -an $o
  printf "%02d:%05.2f  %s (left, hand-keyed) | %s (right, mocap); top front, bottom side\n" $((t/60)) $((t%60)) $hand $mo >> $P/mocap_reel.txt
  t=$((t + d))
  echo "file '$(basename $o)'" >> $T/list.txt
done
nice -n 15 ffmpeg -v error -y -f concat -safe 0 -i $T/list.txt -c copy $P/mocap_reel.mp4
rm -rf $T
echo $P/mocap_reel.mp4 ${t}s
