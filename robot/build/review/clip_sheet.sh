#!/bin/zsh
# clip_sheet.sh PACKAGE CLIP OUT.png FRAME...: a contact sheet of a rendered Clip, each tile the beauty Pass over its
# Shadow Pass on a flat dark backdrop (#2a2420), labelled with the frame number. Uses blender/review/named_sheet.sh.
PKG=$1; CLIP=$2; OUT=$3; shift 3
TMP=$(mktemp -d)
files=()
for f in "$@"; do
  n=$(printf %04d $f)
  magick -size 1920x1080 xc:'#2a2420' "$PKG/shadow/$CLIP/$n.png" -composite "$PKG/beauty/$CLIP/$n.png" -composite \
    -depth 8 PNG24:"$TMP/$n.png"
  files+=("$TMP/$n.png")
done
zsh "${0:A:h}/../../../blender/review/named_sheet.sh" "$OUT" 4 "${files[@]}"
rm -rf "$TMP"
