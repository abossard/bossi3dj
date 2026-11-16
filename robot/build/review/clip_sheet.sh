#!/bin/zsh
# clip_sheet.sh PACKAGE CLIP OUT.png FRAME...: a contact sheet of a rendered Clip, each tile the beauty Pass laid over its
# Shadow Pass on a flat dark backdrop (#2a2420), labelled with the frame number. The beauty comes from <clip>.mov
# (decoded with ffmpeg) or from the PNG frames of a --beauty png render. Uses blender/review/named_sheet.sh.
PKG=$1; CLIP=$2; OUT=$3; shift 3
TMP=$(mktemp -d)
files=()
for f in "$@"; do
  n=$(printf %04d $f)
  beauty="$PKG/beauty/$CLIP/$n.png"
  if [[ -f "$PKG/beauty/$CLIP.mov" ]]; then
    beauty="$TMP/beauty_$n.png"
    ffmpeg -v error -i "$PKG/beauty/$CLIP.mov" -vf "select=eq(n\,$f)" -frames:v 1 -pix_fmt rgba "$beauty"
  fi
  magick -size 1920x1080 xc:'#2a2420' "$PKG/shadow/$CLIP/$n.png" -composite "$beauty" -composite \
    -depth 8 PNG24:"$TMP/$n.png"
  files+=("$TMP/$n.png")
done
zsh "${0:A:h}/../../../blender/review/named_sheet.sh" "$OUT" 4 "${files[@]}"
rm -rf "$TMP"
