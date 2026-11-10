#!/bin/zsh
# sheets.sh DIR: converts DIR/*.ppm to PNG (truecolor) and builds labelled contact sheets:
# sheet_CAM_<n>.png (rows day/sunset/night, columns f0e0 f0e1 f05e0 f05e1 f1e0 f1e1) and sheet_CAM_4_loop.png
D=$1
F=/System/Library/Fonts/Supplemental/Arial.ttf
cd $D || exit 1
for f in *.ppm(N); do magick $f PNG24:${f%.ppm}.png && rm $f; done
for c in 0 1 2 3 4 5 6 7 8 9 10; do
  args=()
  for t in day sunset night; do
    for fe in f0_e0 f0_e1 f05_e0 f05_e1 f1_e0 f1_e1; do
      n=CAM_${c}_${t}_${fe}.png
      [ -f $n ] && args+=(-label "CAM_${c} ${t} ${fe/_/ }" $n)
    done
  done
  [ ${#args} -gt 0 ] && magick montage -font $F -pointsize 15 -background '#202020' -fill white -geometry 480x270+3+3 -tile 6x "${args[@]}" PNG24:sheet_CAM_${c}.png
done
args=()
for t in day sunset night; do
  for p in 0 25 50 75; do
    n=CAM_4_${t}_f0_e0_p${p}.png
    [ -f $n ] && args+=(-label "CAM_4 ${t} loop ${p}%" $n)
  done
done
[ ${#args} -gt 0 ] && magick montage -font $F -pointsize 15 -background '#202020' -fill white -geometry 480x270+3+3 -tile 4x "${args[@]}" PNG24:sheet_CAM_4_loop.png
args=()
for t in day sunset night; do for e in 0 1; do n=CAM_SYS_${t}_e${e}.png; [ -f $n ] && args+=(-label "CAM_SYS ${t} e${e}" $n); done; done
[ ${#args} -gt 0 ] && magick montage -font $F -pointsize 15 -background '#202020' -fill white -geometry 480x270+3+3 -tile 2x "${args[@]}" PNG24:sheet_CAM_SYS.png
args=()
for v in front back above moon; do n=CAM_SYS_${v}_night05_e0.png; [ -f $n ] && args+=(-label "system view ${v}, /vj/night 0.5" $n); done
[ ${#args} -gt 0 ] && magick montage -font $F -pointsize 15 -background '#202020' -fill white -geometry 480x270+3+3 -tile 2x "${args[@]}" PNG24:sheet_CAM_SYS_views.png
args=()
for t in day night; do for n in 0_ground 1_1k 2_10k 3_50k 4_165k; do f=PROOF_pull_${n}_${t}.png; [ -f $f ] && args+=(-label "pull-out ${n#*_} ${t}" $f); done; done
[ ${#args} -gt 0 ] && magick montage -font $F -pointsize 15 -background '#202020' -fill white -geometry 480x270+3+3 -tile 5x "${args[@]}" PNG24:sheet_PROOF_pull_out.png
args=()
for f in PROOF_lod_rings_day.png PROOF_lod_rings_night.png PROOF_stars_*.png(N); do [ -f $f ] && args+=(-label "${${f%.png}#PROOF_}" $f); done
[ ${#args} -gt 0 ] && magick montage -font $F -pointsize 15 -background '#202020' -fill white -geometry 480x270+3+3 -tile 4x "${args[@]}" PNG24:sheet_PROOF_lod_stars.png
ls sheet_*.png | wc -l
