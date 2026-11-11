#!/bin/zsh
# named_sheet.sh OUT.png COLS FILE...: one labelled contact sheet of the given grabs (.ppm or .png), 480x270 tiles,
# each labelled with its file name; a .ppm gets a truecolor .png next to it first.
OUT=$1; COLS=$2; shift 2
args=()
for f in "$@"; do
  p=${f%.ppm}.png
  [ "$f" != "$p" ] && [ ! -f "$p" ] && magick "$f" PNG24:"$p"
  n=${p:t}
  args+=(-label ${n%.png} "$p")
done
magick montage -font /System/Library/Fonts/Supplemental/Arial.ttf -pointsize 14 -geometry 480x270+2+2 -tile ${COLS}x "${args[@]}" PNG24:"$OUT"
