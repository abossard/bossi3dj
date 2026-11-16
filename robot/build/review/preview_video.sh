#!/bin/zsh
# preview_video.sh [OUT.mp4]: one H.264 video of the preview Clips (robot/build/probe/preview), each Move once on the
# front then the side Angle, over a mid-grey backdrop, labelled with Move, tier, bars and Angle. 960x540, 30 fps.
cd "${0:A:h}/../../.."
P=robot/build/probe/preview; OUT=${1:-docs/video/robot-moves-preview.mp4}; T=$P/video; rm -rf $T; mkdir -p $T
python3 -c "import sys; sys.path.insert(0, 'robot/build'); import moves
for m in moves.MOVES.values(): print(m.name, m.tier, m.beats // 4, m.key_in, m.key_out)" | while read m tier bars kin kout; do
  for a in front side; do
    [[ -f $P/beauty/${m}__$a.mov ]] || continue
    magick -size 960x60 xc:none -font /System/Library/Fonts/Supplemental/Arial.ttf -pointsize 26 -fill white \
      -stroke black -strokewidth 1 -annotate +16+40 "$m   $tier   ${bars} bar   $kin > $kout   ($a)" $T/${m}__$a.png
    ffmpeg -nostdin -v error -y -f lavfi -i color=c=0x808080:s=960x540:r=30 -i $P/beauty/${m}__$a.mov -i $T/${m}__$a.png \
      -filter_complex "[0][1]overlay=shortest=1[v];[v][2]overlay=0:0" -c:v libx264 -pix_fmt yuv420p -crf 20 -r 30 $T/${m}__$a.mp4
    echo "file '${m}__$a.mp4'" >> $T/list.txt
  done
done
mkdir -p ${OUT:h}
ffmpeg -v error -y -f concat -safe 0 -i $T/list.txt -c copy $OUT
