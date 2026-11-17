#!/bin/zsh
# hand_crops.sh OUT_DIR CLIP:FRAME...: full-size crops (300x300, over dark grey) around both hands and the head of
# each package Clip frame, from the Clip Data points, into one labelled sheet OUT_DIR/hands.png (3 tiles per frame).
cd "${0:A:h}/../../.."
PKG=robot/package/v1; O=$1; shift; mkdir -p $O/tiles
files=()
for cf in "$@"; do
  c=${cf%:*}; f=${cf#*:}
  for p in hand_l hand_r head; do
    xy=($(jq -r --argjson f $f --arg p $p '.frames[$f][$p] | "\((.[0]*1920|floor)) \((.[1]*1080|floor))"' $PKG/clip_data/$c.json))
    x=$(( xy[1] - 150 )); y=$(( xy[2] - 150 )); (( x < 0 )) && x=0; (( y < 0 )) && y=0
    (( x > 1620 )) && x=1620; (( y > 780 )) && y=780
    t=$O/tiles/${c}_$(printf %04d $f)_$p.png
    ffmpeg -nostdin -v error -y -f lavfi -i color=c=0x202020:s=300x300 -i $PKG/beauty/$c.mov -filter_complex \
      "[1]select=eq(n\,$f),setpts=PTS-STARTPTS,crop=300:300:${x}:${y}[s];[0][s]overlay=shortest=1" -frames:v 1 $t
    files+=(-label ${${t:t}%.png} $t)
  done
done
magick montage -font /System/Library/Fonts/Supplemental/Arial.ttf -pointsize 14 -geometry 300x300+2+2 -tile 6x "${files[@]}" PNG24:$O/hands.png
