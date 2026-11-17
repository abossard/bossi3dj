#!/bin/zsh
# robot_preview_reel.sh [preview|package|exchanges]: one review video of every Move, front | side side by side, each played
# twice, plus an index of start times (this ffmpeg has no drawtext).
#   preview (default): the Eevee previews, newest per Move (probe/m4 over probe/preview/video)
#   package: the beauty Pass of robot/package/v1 (RGBA .mov), laid over dark grey so the alpha shows
#   exchanges: the Eevee previews of the Exchanges (review/preview_all.sh EXCHANGE...), duel_wide | duel_low
# Output: robot/build/probe/<mode>_reel.mp4 and <mode>_reel.txt
set -e
mode=${1:-preview}
P=robot/build/probe; T=$P/reel_tmp; rm -rf $T; mkdir -p $T
L=front; R=side
if [[ $mode == package ]]; then V=robot/package/v1/beauty; ext=mov; else V=$P/preview/video; ext=mp4; fi
[[ $mode == exchanges ]] && { V=$P/preview/beauty; ext=mov; L=duel_wide; R=duel_low; }
moves=($(ls $V/*__$L.$ext | xargs -n1 basename | sed "s/__$L.$ext//"))
i=0; t=0; : > $P/${mode}_reel.txt
for m in $moves; do
  f=$V/${m}__$L.$ext; s=$V/${m}__$R.$ext
  [[ $mode == preview && -f $P/m4/${m}__front.mp4 ]] && f=$P/m4/${m}__front.mp4 && s=$P/m4/${m}__side.mp4
  i=$((i+1)); o=$T/$(printf %02d $i).mp4
  nice -n 15 ffmpeg -v error -y -stream_loop 1 -i $f -stream_loop 1 -i $s -f lavfi -i color=c=0x202020:s=1920x540:r=30 -filter_complex \
    "[0:v]scale=960:540,setsar=1[a];[1:v]scale=960:540,setsar=1[b];[a][b]hstack[ab];[2:v][ab]overlay=shortest=1,format=yuv420p" \
    -r 30 -c:v libx264 -preset veryfast -crf 23 -an $o
  printf "%02d:%05.2f  %2d  %s  (left $L, right $R)\n" $((t/60)) $((t%60)) $i $m >> $P/${mode}_reel.txt
  d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 $o); t=$((t+d))
  echo "file '$(basename $o)'" >> $T/list.txt
done
nice -n 15 ffmpeg -v error -y -f concat -safe 0 -i $T/list.txt -c copy $P/${mode}_reel.mp4
rm -rf $T
echo $P/${mode}_reel.mp4 ${#moves} moves ${t}s
