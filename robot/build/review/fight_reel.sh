#!/bin/zsh
# fight_reel.sh: the fight-clip reel (#32), over dark grey, top row front, bottom row side, each segment played twice:
#   1. today's idle_guard looped 8 bars (package v1, left) beside the capture guard's Idle family chained (right);
#   2. today's hand-keyed jab_cross, uppercut_combo and jab_jab_hook (package v1, left) beside the Mocap fight Moves
#      mocap_jab_elbow, mocap_uppercut_jab and mocap_fist_fight (right);
#   3. the takes: mocap_uppercut_jab, _v2, _v3 in three columns; then mocap_fist_fight | _v2 and mocap_jab_elbow | _v2.
# Reads robot/build/probe/fight (review/fight_batch.sh) and robot/build/probe/mocap.
# Output: robot/build/probe/fight/fight_reel.mp4 and fight_reel.txt.
set -e
cd "${0:A:h}/../../.."
O=robot/build/probe/fight; M=robot/build/probe/mocap; K=robot/package/v1/beauty; T=$O/reel_tmp; rm -rf $T; mkdir -p $T
CHAIN=(idle_guard idle_guard_v2 idle_guard_v3 idle_guard_v4 idle_guard_v5 idle_guard_v3 idle_guard_v2 idle_guard_v4)
len() { ffprobe -v error -show_entries format=duration -of csv=p=0 $1; }
BG="-f lavfi -i color=c=0x202020:s=1920x1080:r=30"
grid4() {   # grid4 OUT LEFT_FRONT RIGHT_FRONT LEFT_SIDE RIGHT_SIDE [SECONDS]
  local o=$1; shift 1
  nice -n 15 ffmpeg -v error -y -stream_loop -1 -i $1 -stream_loop -1 -i $2 -stream_loop -1 -i $3 -stream_loop -1 -i $4 ${=BG} \
    -filter_complex "[0:v]scale=960:540,setsar=1[a];[1:v]scale=960:540,setsar=1[b];[2:v]scale=960:540,setsar=1[c];[3:v]scale=960:540,setsar=1[d];[a][b][c][d]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0[g];[4:v][g]overlay,format=yuv420p" \
    -t $5 -r 30 -c:v libx264 -preset veryfast -crf 20 -an $o
}
: > $O/fight_reel.txt; t=0; i=0
seg() { i=$((i+1)); printf "%02d:%05.2f  %s\n" $((t/60)) $((t%60)) "$1" >> $O/fight_reel.txt; }
# 1
for a in front side; do
  ins=(); fl=""
  for k in {1..8}; do ins+=(-i $K/idle_guard__$a.mov); fl+="[$((k-1)):v]"; done
  nice -n 15 ffmpeg -v error -y ${ins[@]} -filter_complex "${fl}concat=n=8:v=1[v]" -map "[v]" -c:v qtrle $T/loop_$a.mov
  ins=(); fl=""; k=0
  for c in $CHAIN; do ins+=(-i $O/beauty/${c}__$a.mov); fl+="[$k:v]"; k=$((k+1)); done
  nice -n 15 ffmpeg -v error -y ${ins[@]} -filter_complex "${fl}concat=n=8:v=1[v]" -map "[v]" -c:v qtrle $T/chain_$a.mov
done
seg "guard Idle: left today's idle_guard looped 8 bars, right the capture guard's family chained (${CHAIN[*]})"
d=$(len $T/chain_front.mov); grid4 $T/01.mp4 $T/loop_front.mov $T/chain_front.mov $T/loop_side.mov $T/chain_side.mov $d; t=$((t + d))
# 2 and the two-take pairs of 3
for l r in $K/jab_cross $M/mocap_jab_elbow $K/uppercut_combo $M/mocap_uppercut_jab $K/jab_jab_hook $M/mocap_fist_fight \
           $M/mocap_fist_fight $M/mocap_fist_fight_v2 $M/mocap_jab_elbow $M/mocap_jab_elbow_v2; do
  a=$(len ${l}__front.mov); b=$(len ${r}__front.mov); d=$(( 2 * (a > b ? a : b) ))
  seg "left ${l:t} | right ${r:t}"
  grid4 $T/$(printf %02d $i).mp4 ${l}__front.mov ${r}__front.mov ${l}__side.mov ${r}__side.mov $d; t=$((t + d))
done
# 3: three takes of mocap_uppercut_jab
seg "mocap_uppercut_jab takes: left base, middle v2 (Uppercut Jab-2), right v3"
ins=(); for a in front side; do for v in mocap_uppercut_jab mocap_uppercut_jab_v2 mocap_uppercut_jab_v3; do ins+=(-stream_loop -1 -i $M/${v}__$a.mov); done; done
d=$((2 * $(len $M/mocap_uppercut_jab__front.mov)))
nice -n 15 ffmpeg -v error -y ${ins[@]} ${=BG} -filter_complex \
  "[0:v]scale=640:360,setsar=1[a];[1:v]scale=640:360,setsar=1[b];[2:v]scale=640:360,setsar=1[c];[3:v]scale=640:360,setsar=1[d];[4:v]scale=640:360,setsar=1[e];[5:v]scale=640:360,setsar=1[f];[a][b][c][d][e][f]xstack=inputs=6:layout=0_0|w0_0|w0+w1_0|0_h0|w0_h0|w0+w1_h0[g];[6:v][g]overlay=y=180,format=yuv420p" \
  -t $d -r 30 -c:v libx264 -preset veryfast -crf 20 -an $T/$(printf %02d $i).mp4; t=$((t + d))
ls $T/*.mp4 | sort | sed "s|.*/|file '|; s|$|'|" > $T/list.txt
nice -n 15 ffmpeg -v error -y -f concat -safe 0 -i $T/list.txt -c copy $O/fight_reel.mp4
rm -rf $T
echo $O/fight_reel.mp4 ${t}s
