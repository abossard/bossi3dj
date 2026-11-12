#!/bin/zsh
# round13_sheets.sh DIR OUTDIR: the two contact sheets for the user from the round 13 grabs (round13_jobs.py, the limb
# shot of orbit_jobs.py in the same DIR): OUTDIR/planet-round13-day.jpg and planet-round13-night.jpg, JPEG, 640 px
# tiles, each labelled with camera and state.
D=$1; O=$2
F=/System/Library/Fonts/Supplemental/Arial.ttf
mkdir -p $O
sheet() {
  out=$1; shift
  args=()
  while [ $# -gt 1 ]; do
    f=$D/$1.ppm; [ -f $f ] || f=$D/$1.png
    [ -f $f ] && args+=(-label "$2" $f)
    shift 2
  done
  magick montage -font $F -pointsize 18 -background '#181818' -fill white -geometry 640x360+4+4 -tile 3x "${args[@]}" -quality 88 $out
}
day=()
for c in 0 1 2 3 4 5 6 7 8 9 10; do day+=(CAM_${c}_day_f00_e0 "CAM_$c day"); done
day+=(CAM_4_day_f00_e0_p25 "CAM_4 day, path 25 %" CAM_4_day_f00_e0_p50 "CAM_4 day, path 50 %"
      CAM_5_day_f05_e0 "CAM_5 day, fog 0.5" CAM_5_day_f10_e0 "CAM_5 day, fog 1")
sheet $O/planet-round13-day.jpg "${day[@]}"
night=(CAM_0_night_f00_e0_grid1 "CAM_0 night, /vj/grid 1" CAM_1_night_f00_e0_grid1 "CAM_1 night, /vj/grid 1"
       CAM_3_night_f00_e0_grid1 "CAM_3 night, /vj/grid 1" CAM_4_night_f00_e0 "CAM_4 night" CAM_4_night_f10_e0 "CAM_4 night, fog 1"
       CAM_5_night_f05_e0 "CAM_5 night, fog 0.5" CAM_5_night_f10_e0 "CAM_5 night, fog 1" CAM_10_night_f00_e0 "CAM_10 night"
       CAM_10_night_f00_e0_neb0 "CAM_10 night, /vj/nebula 0" S9_orbit_limb "orbit limb, 200 mm")
sheet $O/planet-round13-night.jpg "${night[@]}"
ls -la $O/planet-round13-*.jpg
