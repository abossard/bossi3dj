#!/bin/zsh
# variant_reel.sh: the proof reel of the first variant batch (#32), over dark grey, top row front, bottom row side.
#   1. The guard Idle family chained over 8 bars (right) beside the base Idle looped 8 times (left), as Magic would
#      play an Idle with no Move to leave into.
#   2. jab_cross and its two takes, then mocap_flip_uppercut and its two takes, three columns (base, v2, v3), each
#      played twice.
# Reads robot/build/probe/variants (review/variant_batch.sh) and robot/build/probe/mocap.
# Output: robot/build/probe/variants/variant_reel.mp4 and variant_reel.txt.
set -e
cd "${0:A:h}/../../.."
O=robot/build/probe/variants; M=robot/build/probe/mocap; T=$O/reel_tmp; rm -rf $T; mkdir -p $T
CHAIN=(idle_guard idle_guard_v2 idle_guard_v3 idle_guard_v4 idle_guard_v5 idle_guard_v3 idle_guard_v2 idle_guard_v4)
len() { ffprobe -v error -show_entries format=duration -of csv=p=0 $1; }
# 1: one stream per side and Angle, then a 2 x 2 grid
for a in front side; do
  ins=(); fl=""
  for i in {1..8}; do ins+=(-i $O/beauty/idle_guard__$a.mov); fl+="[$((i-1)):v]"; done
  nice -n 15 ffmpeg -v error -y ${ins[@]} -filter_complex "${fl}concat=n=8:v=1[v]" -map "[v]" -c:v qtrle $T/loop_$a.mov
  ins=(); fl=""; i=0
  for c in $CHAIN; do ins+=(-i $O/beauty/${c}__$a.mov); fl+="[$i:v]"; i=$((i+1)); done
  nice -n 15 ffmpeg -v error -y ${ins[@]} -filter_complex "${fl}concat=n=8:v=1[v]" -map "[v]" -c:v qtrle $T/chain_$a.mov
done
nice -n 15 ffmpeg -v error -y -i $T/loop_front.mov -i $T/chain_front.mov -i $T/loop_side.mov -i $T/chain_side.mov \
  -f lavfi -i color=c=0x202020:s=1920x1080:r=30 -filter_complex \
  "[0:v]scale=960:540,setsar=1[a];[1:v]scale=960:540,setsar=1[b];[2:v]scale=960:540,setsar=1[c];[3:v]scale=960:540,setsar=1[d];[a][b][c][d]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0[g];[4:v][g]overlay=shortest=1,format=yuv420p" \
  -r 30 -c:v libx264 -preset veryfast -crf 20 -an $T/01.mp4
t=$(len $T/01.mp4)
printf "00:00.00  guard Idle: left idle_guard looped 8 bars, right the family chained (%s)\n" "${CHAIN[*]}" > $O/variant_reel.txt
# 2: three takes per Move
i=1
for base dir in jab_cross $O/beauty mocap_flip_uppercut $M; do
  i=$((i+1)); o=$T/$(printf %02d $i).mp4
  d=0; for v in $base ${base}_v2 ${base}_v3; do x=$(len $dir/${v}__front.mov); (( x > d )) && d=$x; done; d=$((2 * d))
  ins=(); for a in front side; do for v in $base ${base}_v2 ${base}_v3; do ins+=(-stream_loop -1 -i $dir/${v}__$a.mov); done; done
  nice -n 15 ffmpeg -v error -y ${ins[@]} -f lavfi -i color=c=0x202020:s=1920x1080:r=30 -filter_complex \
    "[0:v]scale=640:360,setsar=1[a];[1:v]scale=640:360,setsar=1[b];[2:v]scale=640:360,setsar=1[c];[3:v]scale=640:360,setsar=1[d];[4:v]scale=640:360,setsar=1[e];[5:v]scale=640:360,setsar=1[f];[a][b][c][d][e][f]xstack=inputs=6:layout=0_0|w0_0|w0+w1_0|0_h0|w0_h0|w0+w1_h0[g];[6:v][g]overlay=y=180,format=yuv420p" \
    -t $d -r 30 -c:v libx264 -preset veryfast -crf 20 -an $o
  printf "%02d:%05.2f  %s takes: left base, middle v2, right v3\n" $((t/60)) $((t%60)) $base >> $O/variant_reel.txt
  t=$((t + $(len $o)))
done
ls $T/*.mp4 | sort | sed "s|.*/|file '|; s|$|'|" > $T/list.txt
nice -n 15 ffmpeg -v error -y -f concat -safe 0 -i $T/list.txt -c copy $O/variant_reel.mp4
rm -rf $T
echo $O/variant_reel.mp4 ${t}s
