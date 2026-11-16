#!/bin/zsh
# preview_sheets.sh: one contact sheet per Move from the preview Clips over mid grey: first frame, each Hit frame
# (at most 4) and last frame, front Angle on the first row, side on the second. Into robot/build/probe/preview/sheets.
cd "${0:A:h}/../../.."
P=robot/build/probe/preview; S=$P/sheets; rm -rf $S; mkdir -p $S/tiles
python3 -c "import sys; sys.path.insert(0, 'robot/build'); import moves
for m in moves.MOVES.values():
    fr = [0] + sorted({h['f'] for h in moves.hit_frames(m)})[:4] + [moves.move_frames(m) - 1]
    print(m.name, *fr)" | while read m frames; do
  files=()
  for a in front side; do
    for f in ${=frames}; do
      t=$S/tiles/${m}__${a}_$(printf %04d $f).png
      ffmpeg -nostdin -v error -y -f lavfi -i color=c=0x808080:s=960x540 -i $P/beauty/${m}__$a.mov \
        -filter_complex "[1]select=eq(n\,$f),setpts=PTS-STARTPTS[s];[0][s]overlay=shortest=1" -frames:v 1 $t
      files+=($t)
    done
  done
  zsh blender/review/named_sheet.sh $S/$m.png ${#${=frames}} "${files[@]}"
done
