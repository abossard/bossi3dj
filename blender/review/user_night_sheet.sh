#!/bin/zsh
# user_night_sheet.sh GRAB_DIR OUT.jpg: CAM_0, CAM_1, CAM_3, CAM_4 night pairs, /vj/grid 0 left and 1 right, 640 px tiles, labelled.
d=$1; args=()
for c in 0 1 3 4; do for g in 0 1; do args+=(-label "CAM_$c night, /vj/grid $g" $d/CAM_${c}_night_f00_e0_grid$g.png); done; done
magick montage -font /System/Library/Fonts/Supplemental/Arial.ttf -pointsize 18 -geometry 640x360+3+3 -tile 2x -quality 88 "${args[@]}" $2
