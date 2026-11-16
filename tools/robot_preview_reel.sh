#!/bin/zsh
# robot_preview_reel.sh: one review video of every Move's preview, front | side side by side, each played twice,
# plus an index of start times (this ffmpeg has no drawtext). Uses the newest preview per Move (probe/m4 over
# probe/preview/video). Output: robot/build/probe/preview_reel.mp4 and preview_reel.txt
set -e
P=robot/build/probe; V=$P/preview/video; T=$P/reel_tmp; rm -rf $T; mkdir -p $T
moves=($(ls $V/*__front.mp4 | xargs -n1 basename | sed 's/__front.mp4//'))
i=0; t=0; : > $P/preview_reel.txt
for m in $moves; do
  f=$V/${m}__front.mp4; s=$V/${m}__side.mp4
  [[ -f $P/m4/${m}__front.mp4 ]] && f=$P/m4/${m}__front.mp4 && s=$P/m4/${m}__side.mp4
  i=$((i+1)); o=$T/$(printf %02d $i).mp4
  nice -n 15 ffmpeg -v error -y -stream_loop 1 -i $f -stream_loop 1 -i $s -filter_complex \
    "[0:v]scale=960:540,setsar=1[a];[1:v]scale=960:540,setsar=1[b];[a][b]hstack,format=yuv420p" \
    -r 30 -c:v libx264 -preset veryfast -crf 23 -an $o
  printf "%02d:%05.2f  %2d  %s  (left front, right side)\n" $((t/60)) $((t%60)) $i $m >> $P/preview_reel.txt
  d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 $o); t=$((t+d))
  echo "file '$(basename $o)'" >> $T/list.txt
done
nice -n 15 ffmpeg -v error -y -f concat -safe 0 -i $T/list.txt -c copy $P/preview_reel.mp4
rm -rf $T
echo $P/preview_reel.mp4 ${#moves} moves ${t}s
