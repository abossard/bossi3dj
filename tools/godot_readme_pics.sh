#!/bin/zsh
# godot_readme_pics.sh PNG_DIR OUT_DIR: the JPEGs of the README's OSC manual from the frames of
# `make godot-readme-pics`: <name>-godot.jpg as a pair (each half 480 px wide, labelled), cam-godot.jpg
# as a strip of the five pinned shots and cam-godot-<wire>.jpg one per shot. A pair that shows nothing
# is left out (check with tools/png_pair_diff.py first); pass the names to build in NAMES.
IN=$1; OUT=$2; mkdir -p $OUT
F=/System/Library/Fonts/Supplemental/Arial.ttf
pair() { # name label_a label_b file_a file_b
  magick montage -font $F -pointsize 16 -geometry 480x270+1+1 -tile 2x -label "$2" $IN/$4.png -label "$3" $IN/$5.png -quality 85 JPEG:$OUT/$1-godot.jpg
}
names=(${=NAMES:-level intensity fog fog_height haze shock})
for n in $names; do
  case $n in
    level) pair level "/vj/level 0" "/vj/level 1" level-low level-high;;
    intensity) pair intensity "/vj/intensity 0" "/vj/intensity 1" intensity-low intensity-high;;
    fog) pair fog "/vj/fog 0" "/vj/fog 1" fog-low fog-high;;
    fog_height) pair fog_height "/vj/fog_height 0" "/vj/fog_height 1" fog_height-low fog_height-high;;
    haze) pair haze "/vj/haze 0" "/vj/haze 1" haze-low haze-high;;
    shock) pair shock "before the shock" "during the Shake" shock-low shock-high;;
    bass) pair bass "/vj/bass 0" "/vj/bass 1" bass-low-foot bass-high-foot;;
    beat) pair beat "/vj/beat 0" "/vj/beat 1" beat-low beat-high;;
  esac
done
magick montage -font $F -pointsize 16 -geometry 480x270+1+1 -tile 5x \
  -label "0 Scale Wide" $IN/cam-0.png -label "1 Low Hero" $IN/cam-1.png -label "2 Over Shoulder" $IN/cam-2.png \
  -label "3 Close Grip" $IN/cam-3.png -label "4 Aerial" $IN/cam-4.png -quality 85 JPEG:$OUT/cam-godot.jpg
for w in 0 1 2 3 4; do magick $IN/cam-$w.png -resize 480x JPEG:$OUT/cam-godot-$w.jpg; done
