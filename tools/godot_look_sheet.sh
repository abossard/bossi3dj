#!/bin/zsh
# godot_look_sheet.sh OUT.jpg LOOK_DIR CAPTURE_DIR READ_DIR: the contact sheet for the user, 640x360 tiles, 3 columns,
# each labelled with its frame name: the Phase frames of `make godot-capture` (1 to 6), the low hero frames of
# `make godot-wanderer-read` (start, 1000 m, 450 m) and shot 1, 3 and 5 of `make godot-look`.
OUT=$1; LOOK=$2; CAP=$3; READ=$4
magick montage -font /System/Library/Fonts/Supplemental/Arial.ttf -pointsize 18 -geometry 640x360+2+2 -tile 3x \
  -label 1-approach-scale-wide $CAP/1-approach-scale-wide.png -label 2-approach-low-hero $CAP/2-approach-low-hero.png \
  -label 3-climb-over-shoulder $CAP/3-climb-over-shoulder.png -label 4-shake-close-grip $CAP/4-shake-close-grip.png \
  -label 5-climb-aerial $CAP/5-climb-aerial.png -label 6-fall-toppling $CAP/6-fall-toppling.png \
  -label low-hero-start $READ/low-hero-start.png -label low-hero-1000m $READ/low-hero-1000m.png \
  -label low-hero-450m $READ/low-hero-450m.png -label shot-1 $LOOK/shot-1.png -label shot-3 $LOOK/shot-3.png \
  -label shot-5 $LOOK/shot-5.png -quality 85 JPEG:"$OUT"
