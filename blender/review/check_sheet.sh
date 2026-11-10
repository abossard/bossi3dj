#!/bin/zsh
# check_sheet.sh DIR N COLS: waits for N .ppm files in DIR (newer than DIR/.mark), then builds DIR/sheet.png (labelled, 480x270)
D=$1; N=$2; COLS=${3:-3}
until [ $(find $D -name '*.ppm' -newer $D/.mark | wc -l) -ge $N ]; do sleep 3; done
sleep 1
cd $D
args=()
for f in $(ls -tr *.ppm); do [ $f -nt .mark ] && magick $f PNG24:${f%.ppm}.png && args+=(-label ${f%.ppm} ${f%.ppm}.png); done
magick montage -font /System/Library/Fonts/Supplemental/Arial.ttf -pointsize 14 -geometry 480x270+2+2 -tile ${COLS}x "${args[@]}" PNG24:sheet.png
echo done
